# -*- coding: utf-8 -*-
"""Authoritative finalization pass for MoodyBot responses.

ANALYZE → ROUTE → GENERATE DRAFT → FINALIZE → USER

Pipeline:
  epistemic rewrite
  → generic CTA strip
  → recognition callback / closing strategy
  → anchor enforcement
  → compression
  → FINAL SURFACE RENDER (immutable after this)

Deterministic gates run always. Web and Telegram must call finalize_response().
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from conversation_anchors import (
    ConversationAnchors,
    extract_conversation_anchors,
)
from recognition_callbacks import (
    closer_instruction,
    is_generic_followup,
    select_closing_strategy,
)
from signature_language import (
    belongs_only_to_this_conversation,
    extract_signature_language,
    remember_signature_use,
    rhetorical_callback_quality,
    transform_signature_callback,
)
from surface_render import final_surface_render

logger = logging.getLogger("moodybot.finalization")

# In-process novelty memory (not persisted; enough to stop mechanical reuse).
_RECENT_CLOSERS: Deque[str] = deque(maxlen=24)

GENERIC_CTA_PATTERNS = [
    r"\bif you want\b",
    r"\bif you'?d like\b",
    r"\bwant me to\b",
    r"\bwould you like\b",
    r"\bdo you want\b",
    r"\bsay the word\b",
    r"\bi can also\b",
    r"\bi can give you\b",
    r"\blet me know if\b",
    r"\bwe can go deeper\b",
    r"\bwant to unpack\b",
    r"\banything else\??\b",
    r"\bdoes that make sense\b",
    r"\bwhat would you like\b",
    r"\bwhich aspect\b",
    r"\bwhat are you actually asking\b",
    r"\bdo you want examples\b",
    r"\bwould examples help\b",
    r"\bif you want examples\b",
    r"\bwant more\b",
    r"\bshould we go deeper\b",
    r"\bexplore that further\b",
    r"\bexplain more\b",
]

POPULATION_MARKERS = [
    "generations", "men", "women", "society", "culture", "bedrooms",
    "porn", "relationships", "workplaces", "mainstream", "everyone",
    "people now", "people today", "in 1995", "in 2026", "the average",
    "millennials", "generation", "gen z", "gen x",
]

# Phrase-level unsupported causal / motive claims (applied first).
UNSUPPORTED_CAUSAL = [
    (r"\bthe shift is real\b", "There does seem to be a change in the reference library"),
    (
        r"(?:[Ii]nternet\s+)?porn(?:ography)?\s+(?:has\s+)?(?:turned|made)\s+dirty talk into a full script",
        "Porn is one obvious influence on that shift - not the only one - and it helped give dirty talk a much larger script library",
    ),
    (
        r"\bporn(?:ography)?\s+(?:has\s+)?(?:turned|made|caused)\b",
        "Porn amplified",
    ),
    (r"\bmainstream in a lot of bedrooms\b",
     "much easier to encounter as ordinary sexual vocabulary"),
    (r"\b[Hh]e (?:read|saw|took) (?:it|that|her(?: number)?) as access\b",
     "The flowers suggest he understood the exchange more personally than she did"),
    (r"\b[Hh]e (?:read|saw|took) (?:it|that|her) as\b",
     "The exchange appears to have been read more personally than intended as"),
    (r"\b[Hh]e wanted control\b", "His motive is uncertain. The boundary shift isn't"),
    (r"\b[Hh]e wanted\b", "His motive is uncertain; he may have wanted"),
    (r"\b[Hh]e meant\b", "His intent is uncertain; he may have meant"),
]

# Broad cultural monocausal / invented-certainty patterns.
BROAD_CULTURAL_CAUSAL = [
    (
        r"\b[Tt]he language changed because the consumption changed\b",
        "Part of the shift tracks with how consumption changed - alongside broader internet culture and wider exposure to explicit language",
    ),
    (
        r"\b[Tt]he average person'?s sexual vocabulary has been trained by thousands of hours\b",
        "For many people, sexual vocabulary has been shaped by a much larger online reference library",
    ),
    (
        r"\b[Tt]he average person'?s\b",
        "For many people, ",
    ),
    (
        r"\bthousands of hours\b",
        "a lot of exposure",
    ),
    (
        r"\b(?:almost )?everyone\b",
        "a lot of people",
    ),
    (
        r"\bmost people\b",
        "many people",
    ),
    (
        r"\balmost all\b",
        "a large share of",
    ),
    (
        r"\b[Pp]orn changed dirty talk\b",
        "Porn is probably one of the biggest influences on dirty talk, alongside broader internet culture, changing erotica, and much wider exposure to explicit sexual language",
    ),
    (
        r"\b[Ss]ociety (?:has )?(?:now )?(?:became|become|is)\b",
        "A major cultural pattern appears to be",
    ),
    (
        r"\b[Pp]eople now\b",
        "A lot of people now",
    ),
    (
        r"\b[Tt]he culture (?:has )?(?:made|turned|caused)\b",
        "Part of the cultural shift appears to have",
    ),
    (
        r"\b[Tt]he camera needs\s+(\w+)",
        r"Camera-facing sex culture often leans on \1",
    ),
]


@dataclass
class ResponsePlan:
    intent: str = "explore"
    primary_capability: Optional[str] = None
    supporting_capability: Optional[str] = None
    intervention: Optional[str] = None
    voice: Optional[str] = None
    evidence_confidence: str = "medium"  # high | medium | low
    needs_practical_action: bool = False
    expected_shift_from: Optional[str] = None
    expected_shift_to: Optional[str] = None
    central_insight: Optional[str] = None
    original_subject: Optional[str] = None
    closing_strategy: str = "none"  # recognition_callback | ritual_line | action_line | silence | none
    allow_question: bool = False
    missing_required_info: bool = False
    channel: str = "telegram"
    mode: str = "dynamic"
    selected_command: str = "/thoughts"
    anchors: List[str] = field(default_factory=list)


@dataclass
class FinalizeResult:
    text: str
    plan: ResponsePlan
    epistemic_rewrite: bool = False
    generic_cta_removed: bool = False
    finalization_rewrite: bool = False
    closer_replaced: bool = False
    surface_cleaned: bool = False
    diagnostics: Dict[str, str] = field(default_factory=dict)


def _normalize_strategy(strategy: str) -> str:
    return (strategy or "NONE").upper().replace("-", "_")


def _strategy_to_plan_value(strategy: str) -> str:
    return _normalize_strategy(strategy).lower()


def extract_original_subject(user_message: str) -> str:
    text = re.sub(r"^/\w+\s*", "", (user_message or "").strip())
    chunk = re.split(r"[.?!\n]", text)[0].strip()
    words = [w for w in re.findall(r"[A-Za-z']+", chunk) if len(w) > 2]
    stop = {
        "the", "and", "for", "that", "this", "with", "from", "about", "have",
        "what", "when", "where", "which", "your", "you", "how", "did", "does",
        "are", "was", "were", "been", "into", "than", "then", "just", "like",
    }
    signal = [w for w in words if w.lower() not in stop][:6]
    return " ".join(signal) if signal else (chunk[:80] or "this")


def extract_high_signal_vocabulary(user_message: str, draft: str = "") -> List[str]:
    blob = f"{user_message} {draft}"
    words = re.findall(r"[A-Za-z']{4,}", blob)
    stop = {
        "that", "this", "with", "from", "about", "have", "what", "when", "where",
        "which", "your", "just", "like", "they", "them", "their", "been", "were",
        "would", "could", "should", "there", "here", "into", "than", "then",
        "really", "something", "someone", "because", "moodybot",
    }
    out: List[str] = []
    for w in words:
        lw = w.lower()
        if lw in stop:
            continue
        if lw not in out:
            out.append(lw)
        if len(out) >= 10:
            break
    return out


def infer_central_insight(user_message: str, draft: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", draft or "") if s.strip()]
    candidates = [s for s in sentences if 40 <= len(s) <= 180 and not s.endswith("?")]
    if candidates:
        return candidates[min(len(candidates) - 1, max(0, len(candidates) // 2))]
    return extract_original_subject(user_message)


def needs_clarification(user_message: str) -> bool:
    text = (user_message or "").strip().lower()
    if not text:
        return True
    vague = (
        text in {"should i send it?", "should i take it?", "should i?", "what do i do?", "and?"},
        bool(re.fullmatch(r"should i (send|take|do) it\??", text)),
        bool(re.fullmatch(r"(send|take) it\??", text)),
    )
    return any(vague)


def is_technical_question(user_message: str) -> bool:
    text = (user_message or "").lower()
    markers = (
        "telegram", "worker", "crash", "dying", "deploy", "render", "httpx",
        "python", "stack", "exception", "timeout", "webhook", "getupdates",
        "docker", "latency", "memory leak", "where does", "architecture",
        "session state", "api key", "env var",
    )
    return any(m in text for m in markers)


def is_practical_request(user_message: str) -> bool:
    text = (user_message or "").lower()
    return any(
        p in text
        for p in (
            "what should i do",
            "should i reply",
            "what do i say",
            "what now",
            "how should i handle",
            "how do i fix",
            "next move",
            "should she",
            "should i send",
            "how do i handle",
        )
    )


def is_grief_or_trauma(user_message: str) -> bool:
    text = (user_message or "").lower()
    return any(
        p in text
        for p in (
            "grief", "died", "funeral", "i can't stop crying", "trauma",
            "he's dead", "she's dead", "i didn't say goodbye", "passed away",
        )
    )


def is_cultural_or_insight(user_message: str) -> bool:
    text = (user_message or "").lower()
    return any(
        p in text
        for p in (
            "culture", "cultural", "between", "influence", "pattern",
            "what changed", "why does", "what does it mean", "porn",
            "dirty talk", "relationship", "is this normal", "society",
            "stretched", "carrying", "cracked", "script",
        )
    )


def build_response_plan(
    user_message: str,
    *,
    selected_command: str = "/thoughts",
    channel: str = "telegram",
    mode: str = "dynamic",
) -> ResponsePlan:
    missing = needs_clarification(user_message)
    practical = is_practical_request(user_message)
    grief = is_grief_or_trauma(user_message)
    technical = is_technical_question(user_message) or selected_command in {
        "/dev", "/clinical", "/tighten"
    }
    roast = selected_command in {"/roast", "/savage", "/cut"}
    insight = is_cultural_or_insight(user_message) or selected_command in {
        "/thoughts", "/velvet", "/contrast", "/cinema", "/noir", "/sensory"
    }

    strategy = select_closing_strategy(
        user_message=user_message,
        created_reframe=insight and not technical and not practical and not grief,
        practical_request=practical,
        grief_or_trauma=grief,
        roast_mode=roast,
        technical_only=technical,
        missing_required_info=missing,
    )

    if missing:
        allow_q = True
        strategy = "NONE"
        intent = "clarify"
        confidence = "low"
        primary = "Clarification"
    elif practical:
        allow_q = False
        intent = "action"
        confidence = "medium"
        primary = "Practical Next Action"
    elif grief:
        allow_q = False
        intent = "witness"
        confidence = "high"
        primary = "Quiet Presence"
    elif technical:
        allow_q = False
        intent = "technical"
        confidence = "medium"
        primary = "Operational Intelligence"
    elif insight:
        allow_q = strategy == "RECOGNITION_CALLBACK"
        intent = "explore"
        confidence = "medium"
        primary = "Cultural Analysis" if is_cultural_or_insight(user_message) else "Pattern Recognition"
    else:
        allow_q = False
        intent = "respond"
        confidence = "medium"
        primary = "Emotional State Recognition"

    subject = extract_original_subject(user_message)
    anchors = extract_conversation_anchors(user_message)
    return ResponsePlan(
        intent=intent,
        primary_capability=primary,
        supporting_capability="Epistemic Calibration",
        evidence_confidence=confidence,
        needs_practical_action=practical,
        expected_shift_from="confusion" if insight else None,
        expected_shift_to="clarity" if insight else ("action" if practical else None),
        central_insight=None,
        original_subject=subject,
        closing_strategy=_strategy_to_plan_value(strategy),
        allow_question=allow_q or missing,
        missing_required_info=missing,
        channel=channel,
        mode=mode,
        selected_command=selected_command or "/thoughts",
        anchors=list(anchors.all_anchors),
    )


def plan_closer_instruction(plan: ResponsePlan) -> str:
    return closer_instruction(_normalize_strategy(plan.closing_strategy))


def detect_generic_cta(text: str) -> bool:
    if not text:
        return False
    closer = text.strip()[-320:].lower()
    if is_generic_followup(text):
        return True
    return any(re.search(pat, closer) for pat in GENERIC_CTA_PATTERNS)


def strip_generic_cta(text: str) -> Tuple[str, bool]:
    """Remove trailing generic continuation CTAs. Returns (text, removed)."""
    if not text or not detect_generic_cta(text):
        return text, False

    parts = re.split(r"\n\s*\n", text.strip())
    if len(parts) >= 2 and detect_generic_cta(parts[-1]):
        return "\n\n".join(parts[:-1]).rstrip(), True

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) >= 2 and detect_generic_cta(sentences[-1]):
        return " ".join(sentences[:-1]).rstrip(), True

    closer_start = max(0, len(text) - 320)
    head, tail = text[:closer_start], text[closer_start:]
    for pat in GENERIC_CTA_PATTERNS:
        m = re.search(pat, tail, flags=re.IGNORECASE)
        if m:
            return (head + tail[: m.start()]).rstrip(" \n\t-—,"), True
    return text, False


def run_epistemic_check(draft: str, plan: ResponsePlan) -> Tuple[str, bool]:
    """Recalibrate unsupported causal / motive / quantitative claims without hedge-soup."""
    text = draft or ""
    changed = False

    for pattern, replacement in UNSUPPORTED_CAUSAL + BROAD_CULTURAL_CAUSAL:
        new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if n:
            text = new_text
            changed = True

    # Population-level absolute certainty softeners.
    if any(m in text.lower() for m in POPULATION_MARKERS):
        soft, n = re.subn(
            r"\b(?:everyone|all (?:men|women|people))\b",
            "a lot of people",
            text,
            flags=re.IGNORECASE,
        )
        if n:
            text, changed = soft, True
        soft, n = re.subn(
            r"\bporn(?:ography)? (?:caused|created|invented)\b",
            "porn amplified",
            text,
            flags=re.IGNORECASE,
        )
        if n:
            text, changed = soft, True

    # Invented quantitative certainty
    soft, n = re.subn(
        r"\b\d{2,}\s*%\b",
        "a sizable share",
        text,
    )
    if n:
        text, changed = soft, True
    soft, n = re.subn(
        r"\b(?:hundreds|thousands|millions) of (?:hours|people|times)\b",
        "a lot of exposure",
        text,
        flags=re.IGNORECASE,
    )
    if n:
        text, changed = soft, True

    if plan.evidence_confidence in {"low", "medium"} and re.search(
        r"\bthe shift is real\b", text, flags=re.IGNORECASE
    ):
        text = re.sub(
            r"\bthe shift is real\b",
            "there does seem to be a real shift in the reference library",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        changed = True

    # Avoid introducing hedge-soup tokens if a prior rewrite somehow added them
    for weak in (r"\bone might argue\b", r"\bperhaps\b", r"\bpossibly\b"):
        if re.search(weak, text, flags=re.IGNORECASE):
            text = re.sub(weak, "Part of the pattern is", text, count=1, flags=re.IGNORECASE)
            changed = True

    return text, changed


def _recent_closer_collision(candidate: str) -> bool:
    norm = re.sub(r"\s+", " ", (candidate or "").strip().lower())
    if not norm:
        return False
    for prev in _RECENT_CLOSERS:
        if norm == prev or (len(norm) > 20 and norm[:40] == prev[:40]):
            return True
    return False


def generate_recognition_callback(
    user_message: str,
    plan: ResponsePlan,
    draft: str = "",
    anchors: Optional[ConversationAnchors] = None,
    *,
    conversation_id: str = "",
) -> str:
    """Generate a RHETORICAL recognition callback from signature language.

    Priority: protected signature phrase → transform → callback.
    Never synonymize distinctive authorial wording into topical reflections.
    """
    _ = anchors  # retained for callers; rhetorical path uses signature_language
    _ = draft
    signatures = extract_signature_language(user_message)
    subject = plan.original_subject or extract_original_subject(user_message)

    # 1) Rhetorical transform from protected signature language
    if signatures.protected:
        candidate = transform_signature_callback(
            signatures, conversation_id=conversation_id
        )
        if candidate:
            candidate = candidate.strip()
            if not candidate.endswith("?"):
                candidate += "?"
            quality = rhetorical_callback_quality(candidate, user_message, signatures)
            if quality["preserves_signature"] and quality["no_synonym_destruction"]:
                remember_signature_use(conversation_id or "default", candidate, signatures)
                return candidate

    # 2) No signature available — subject echo WITHOUT synonymizing missing fingerprints
    # Prefer literal subject words over "what changed / what shifted" templates.
    subject_words = [w for w in re.findall(r"[A-Za-z']+", subject) if len(w) > 3][:4]
    if subject_words:
        focus = " ".join(subject_words[:3])
        candidate = f"What about {focus} looks different now that you've seen it named?"
    else:
        candidate = "What part of that still has a fingerprint on you?"

    candidate = candidate.strip()
    if not candidate.endswith("?"):
        candidate += "?"
    if len(candidate.split()) > 40:
        candidate = f"What about {subject_words[0] if subject_words else 'that'} still holds?"
    if detect_generic_cta(candidate):
        candidate = f"What about {subject_words[0] if subject_words else 'that'} still holds?"
    return candidate


def validate_recognition_callback_quality(
    question: str,
    user_message: str,
    plan: ResponsePlan,
    anchors: Optional[ConversationAnchors] = None,
) -> Dict[str, bool]:
    """Rhetorical quality gate — signature preservation beats topical relevance."""
    _ = anchors
    _ = plan
    q = (question or "").strip()
    signatures = extract_signature_language(user_message)
    rq = rhetorical_callback_quality(q, user_message, signatures)
    return {
        "specificity": rq["conversation_specific"],
        "callback": rq["preserves_signature"] or not signatures.protected,
        "anchor": rq["preserves_signature"] or not signatures.protected,
        "rhetorical": rq["conversation_specific"],
        "no_synonym_destruction": rq["no_synonym_destruction"],
        "shift": rq["preserves_signature"] or rq["conversation_specific"],
        "not_generic": not detect_generic_cta(q) and rq["not_generic_reflective"],
        "novel": not _recent_closer_collision(q),
        "brief": rq["brief"],
        "is_question": rq["is_question"],
    }


def _split_body_and_closer(text: str) -> Tuple[str, str]:
    parts = re.split(r"\n\s*\n", (text or "").strip())
    if len(parts) >= 2:
        return "\n\n".join(parts[:-1]).rstrip(), parts[-1].strip()
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) >= 2 and sentences[-1].endswith("?"):
        return " ".join(sentences[:-1]).rstrip(), sentences[-1].strip()
    return text.strip(), ""


def _apply_closing_strategy(
    text: str,
    plan: ResponsePlan,
    user_message: str,
    anchors: Optional[ConversationAnchors] = None,
) -> Tuple[str, bool]:
    """Enforce closing strategy + anchor check. Returns (text, closer_replaced)."""
    strategy = plan.closing_strategy
    body, closer = _split_body_and_closer(text)
    anchors = anchors or extract_conversation_anchors(user_message, body or text)

    if strategy in {"silence", "none"}:
        if closer and (closer.endswith("?") or detect_generic_cta(closer)):
            return body, True
        if body.endswith("?") and strategy == "silence":
            sentences = re.split(r"(?<=[.!?])\s+", body)
            if len(sentences) >= 2:
                return " ".join(sentences[:-1]).rstrip(), True
        return text, False

    if strategy == "action_line":
        if closer and (detect_generic_cta(closer) or closer.endswith("?")):
            return body if body else text, True
        return text, False

    if strategy == "ritual_line":
        if closer.endswith("?") or detect_generic_cta(closer):
            return body, True
        return text, False

    if strategy == "recognition_callback":
        signatures = extract_signature_language(user_message)
        quality_ok = False
        if closer.endswith("?") and not detect_generic_cta(closer):
            checks = validate_recognition_callback_quality(closer, user_message, plan, anchors)
            quality_ok = all(
                [
                    checks["not_generic"],
                    checks["is_question"],
                    checks["brief"],
                    checks["rhetorical"],
                    checks["no_synonym_destruction"],
                    checks["anchor"],
                ]
            )
        if quality_ok:
            remember_signature_use("default", closer, signatures)
            _RECENT_CLOSERS.append(re.sub(r"\s+", " ", closer.lower()))
            return text, False

        callback = generate_recognition_callback(
            user_message, plan, draft=body or text, anchors=anchors
        )
        # Hard rhetorical enforcement when signature language exists
        if signatures.protected and not belongs_only_to_this_conversation(callback, signatures):
            callback = transform_signature_callback(signatures) or callback
            if callback and not callback.endswith("?"):
                callback += "?"
        checks = validate_recognition_callback_quality(callback, user_message, plan, anchors)
        if not checks["not_generic"] or not checks["is_question"]:
            return body or text, True
        remember_signature_use("default", callback, signatures)
        _RECENT_CLOSERS.append(re.sub(r"\s+", " ", callback.lower()))
        base = body or text
        if base.rstrip().endswith("?"):
            sentences = re.split(r"(?<=[.!?])\s+", base.rstrip())
            if len(sentences) >= 2:
                base = " ".join(sentences[:-1]).rstrip()
        return f"{base.rstrip()}\n\n{callback}", True

    return text, False


def compress_if_overwritten(text: str) -> Tuple[str, bool]:
    """Light compression: collapse triple newlines; trim filler openers."""
    original = text
    text = re.sub(r"\n{3,}", "\n\n", text or "")
    text = re.sub(r"^(?:Look,?|So,?|Well,?)\s+", "", text.strip(), count=1, flags=re.IGNORECASE)
    return text, text != original


def finalize_response(
    draft: str,
    user_message: str,
    plan: Optional[ResponsePlan] = None,
    *,
    selected_command: str = "/thoughts",
    channel: str = "telegram",
    mode: str = "dynamic",
    prompt_hash: str = "",
    git_commit: str = "",
) -> FinalizeResult:
    """Run the authoritative finalization gates. Draft must not go to users raw.

    After final_surface_render, text is immutable for this pass.
    """
    t0 = time.time()
    plan = plan or build_response_plan(
        user_message,
        selected_command=selected_command,
        channel=channel,
        mode=mode,
    )
    plan.central_insight = plan.central_insight or infer_central_insight(user_message, draft)
    plan.original_subject = plan.original_subject or extract_original_subject(user_message)

    anchors = extract_conversation_anchors(user_message, draft)
    plan.anchors = list(anchors.all_anchors)

    text = (draft or "").strip()
    epistemic_rewrite = False
    generic_removed = False
    closer_replaced = False
    surface_cleaned = False

    # 1) Epistemic / motivation / cultural / quantitative calibration
    text, epistemic_rewrite = run_epistemic_check(text, plan)

    # 2) Generic continuation CTA — hard failure → remove
    if plan.missing_required_info and len(text.split()) < 40:
        pass
    else:
        text, generic_removed = strip_generic_cta(text)

    # 3) Closing strategy + recognition callback + anchor enforcement
    text, closer_replaced = _apply_closing_strategy(text, plan, user_message, anchors)

    # 4) Compression
    text, compressed = compress_if_overwritten(text)

    # 5) FINAL SURFACE RENDER — nothing may modify text after this
    text, surface_cleaned = final_surface_render(text)

    finalization_rewrite = (
        epistemic_rewrite or generic_removed or closer_replaced or compressed or surface_cleaned
    )
    duration_ms = int((time.time() - t0) * 1000)

    diagnostics = {
        "event": "moodybot_generation",
        "mode": plan.mode,
        "channel": plan.channel,
        "prompt_hash": prompt_hash or "",
        "git_commit": git_commit or "",
        "primary_capability": plan.primary_capability or "",
        "supporting_capability": plan.supporting_capability or "",
        "intervention": plan.intervention or "",
        "voice": plan.voice or "",
        "closing_strategy": plan.closing_strategy,
        "anchors": ",".join(plan.anchors[:6]),
        "epistemic_rewrite": str(epistemic_rewrite).lower(),
        "generic_cta_removed": str(generic_removed).lower(),
        "finalization_rewrite": str(finalization_rewrite).lower(),
        "closer_replaced": str(closer_replaced).lower(),
        "surface_cleaned": str(surface_cleaned).lower(),
        "duration_ms": str(duration_ms),
    }
    logger.info("finalization %s", diagnostics)

    return FinalizeResult(
        text=text,
        plan=plan,
        epistemic_rewrite=epistemic_rewrite,
        generic_cta_removed=generic_removed,
        finalization_rewrite=finalization_rewrite,
        closer_replaced=closer_replaced,
        surface_cleaned=surface_cleaned,
        diagnostics=diagnostics,
    )


def prompt_content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def plan_as_dict(plan: ResponsePlan) -> Dict:
    return asdict(plan)
