# -*- coding: utf-8 -*-
"""Authoritative finalization pass for MoodyBot responses.

ANALYZE → ROUTE → GENERATE DRAFT → FINALIZE → USER

Deterministic gates run always. No second LLM pass unless a caller opts in later.
Web and Telegram must call finalize_response() — do not duplicate this logic.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from recognition_callbacks import (
    closer_instruction,
    is_generic_followup,
    select_closing_strategy,
)

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
    "people now", "people today", "in 1995", "in 2026",
]

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


@dataclass
class FinalizeResult:
    text: str
    plan: ResponsePlan
    epistemic_rewrite: bool = False
    generic_cta_removed: bool = False
    finalization_rewrite: bool = False
    closer_replaced: bool = False
    diagnostics: Dict[str, str] = field(default_factory=dict)


def _normalize_strategy(strategy: str) -> str:
    return (strategy or "NONE").upper().replace("-", "_")


def _strategy_to_plan_value(strategy: str) -> str:
    return _normalize_strategy(strategy).lower()


def extract_original_subject(user_message: str) -> str:
    text = re.sub(r"^/\w+\s*", "", (user_message or "").strip())
    # Prefer first clause / question body
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
    # Prefer a mid/late substantive sentence from the draft as the "insight" anchor.
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

    # Clarification exception: allow a real question, but not a recognition callback.
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

    # Single-block: strip last sentence if it matches.
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) >= 2 and detect_generic_cta(sentences[-1]):
        return " ".join(sentences[:-1]).rstrip(), True

    # Fallback: truncate at first generic marker in closer zone
    closer_start = max(0, len(text) - 320)
    head, tail = text[:closer_start], text[closer_start:]
    for pat in GENERIC_CTA_PATTERNS:
        m = re.search(pat, tail, flags=re.IGNORECASE)
        if m:
            return (head + tail[: m.start()]).rstrip(" \n\t-—,"), True
    return text, False


def run_epistemic_check(draft: str, plan: ResponsePlan) -> Tuple[str, bool]:
    """Recalibrate unsupported causal / motive claims without hedge-soup."""
    text = draft or ""
    changed = False

    for pattern, replacement in UNSUPPORTED_CAUSAL:
        new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if n:
            text = new_text
            changed = True

    # Population-level absolute certainty softeners (light touch).
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

    return text, changed


def _recent_closer_collision(candidate: str) -> bool:
    norm = re.sub(r"\s+", " ", (candidate or "").strip().lower())
    if not norm:
        return False
    for prev in _RECENT_CLOSERS:
        if norm == prev or (len(norm) > 20 and norm[:40] == prev[:40]):
            return True
    return False


def generate_recognition_callback(user_message: str, plan: ResponsePlan, draft: str = "") -> str:
    """Generate a one-sentence recognition callback from this exchange (not a canned library)."""
    subject = plan.original_subject or extract_original_subject(user_message)
    vocab = extract_high_signal_vocabulary(user_message, draft)
    insight = plan.central_insight or infer_central_insight(user_message, draft)

    # Pull a concrete noun phrase from subject/vocab for specificity.
    anchor = subject
    for v in vocab:
        if v.lower() not in anchor.lower() and len(v) > 4:
            anchor = f"{subject} / {v}"
            break

    # Structural shapes — filled from this conversation's vocabulary.
    shapes = [
        f"What changed in your sense of {subject} once that was visible?",
        f"Which part of {subject} stopped sounding extreme once you saw where the script came from?",
        f"What got wider in your definition of {vocab[0] if vocab else subject} after reading that?",
        f"What stopped looking innocent once the incentive behind {subject} was visible?",
        f"Which assumption about {subject} just lost some oxygen?",
        f"What became obvious once you separated the behavior in {subject} from the motive?",
    ]

    # Prefer a shape that mentions a high-signal token from the user question.
    preferred = None
    um = (user_message or "").lower()
    for shape in shapes:
        if any(v in shape.lower() for v in vocab[:3]):
            preferred = shape
            break
    candidate = preferred or shapes[hash(subject) % len(shapes)]

    # Novelty: rotate if recently used.
    if _recent_closer_collision(candidate):
        for shape in shapes:
            if not _recent_closer_collision(shape):
                candidate = shape
                break

    # Keep one sentence, end with ?
    candidate = candidate.strip()
    if not candidate.endswith("?"):
        candidate += "?"
    # Soft length cap
    if len(candidate.split()) > 28:
        candidate = f"What shifted in how you see {subject}?"
    # Avoid sounding like the banned service desk
    if detect_generic_cta(candidate):
        candidate = f"What part of {subject} looks different now?"
    _ = insight  # retained for future richer generation / logging
    _ = anchor
    if "porn" in um or "dirty talk" in um:
        alt = "What changed in your sense of what now counts as ordinary dirty talk?"
        if not _recent_closer_collision(alt):
            candidate = alt
    return candidate


def validate_recognition_callback_quality(
    question: str,
    user_message: str,
    plan: ResponsePlan,
) -> Dict[str, bool]:
    q = (question or "").strip()
    lower = q.lower()
    subject_bits = re.findall(r"[A-Za-z']{4,}", (plan.original_subject or "") + " " + (user_message or ""))
    subject_hit = any(tok.lower() in lower for tok in subject_bits if len(tok) > 3)
    return {
        "specificity": subject_hit or bool(re.search(r"\b(that|this|now|once|after)\b", lower)),
        "callback": subject_hit or "that" in lower or "this" in lower,
        "shift": any(w in lower for w in ("changed", "shift", "wider", "stopped", "looks", "sense", "assumption", "obvious", "oxygen")),
        "not_generic": not detect_generic_cta(q),
        "novel": not _recent_closer_collision(q),
        "brief": len(q.split()) <= 32,
        "is_question": q.endswith("?"),
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
) -> Tuple[str, bool]:
    """Enforce closing strategy. Returns (text, closer_replaced)."""
    strategy = plan.closing_strategy
    body, closer = _split_body_and_closer(text)
    replaced = False

    if strategy in {"silence", "none"}:
        if closer and (closer.endswith("?") or detect_generic_cta(closer)):
            return body, True
        # Also strip trailing questions glued to last paragraph
        if body.endswith("?") and strategy == "silence":
            sentences = re.split(r"(?<=[.!?])\s+", body)
            if len(sentences) >= 2:
                return " ".join(sentences[:-1]).rstrip(), True
        return text if not replaced else body, replaced

    if strategy == "action_line":
        if detect_generic_cta(closer) or (closer.endswith("?") and not plan.needs_practical_action):
            # Keep body; drop generic question closer
            return body if body else text, True
        if closer and detect_generic_cta(closer):
            return body, True
        return text, False

    if strategy == "ritual_line":
        if closer.endswith("?") or detect_generic_cta(closer):
            return body, True
        return text, False

    if strategy == "recognition_callback":
        # Clarification exception handled upstream via strategy none + allow_question
        quality_ok = False
        if closer.endswith("?") and not detect_generic_cta(closer):
            checks = validate_recognition_callback_quality(closer, user_message, plan)
            quality_ok = all(
                [
                    checks["not_generic"],
                    checks["is_question"],
                    checks["brief"],
                    checks["shift"] or checks["callback"],
                ]
            )
        if quality_ok:
            _RECENT_CLOSERS.append(re.sub(r"\s+", " ", closer.lower()))
            return text, False

        callback = generate_recognition_callback(user_message, plan, draft=body or text)
        checks = validate_recognition_callback_quality(callback, user_message, plan)
        if not checks["not_generic"] or not checks["is_question"]:
            return body or text, True
        _RECENT_CLOSERS.append(re.sub(r"\s+", " ", callback.lower()))
        base = body or text
        # Remove existing trailing question before attaching
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
    """Run the authoritative finalization gates. Draft must not go to users raw."""
    t0 = time.time()
    plan = plan or build_response_plan(
        user_message,
        selected_command=selected_command,
        channel=channel,
        mode=mode,
    )
    plan.central_insight = plan.central_insight or infer_central_insight(user_message, draft)
    plan.original_subject = plan.original_subject or extract_original_subject(user_message)

    text = (draft or "").strip()
    epistemic_rewrite = False
    generic_removed = False
    closer_replaced = False

    # 1) Epistemic / motivation calibration
    text, epistemic_rewrite = run_epistemic_check(text, plan)

    # 2) Generic continuation CTA — hard failure → remove
    # Exception: true clarification when missing info and body is short.
    if plan.missing_required_info and len(text.split()) < 40:
        pass  # allow clarification question in body
    else:
        text, generic_removed = strip_generic_cta(text)

    # 3) Closing strategy enforcement
    text, closer_replaced = _apply_closing_strategy(text, plan, user_message)

    # 4) Overwrite / compression
    text, compressed = compress_if_overwritten(text)

    finalization_rewrite = epistemic_rewrite or generic_removed or closer_replaced or compressed
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
        "epistemic_rewrite": str(epistemic_rewrite).lower(),
        "generic_cta_removed": str(generic_removed).lower(),
        "finalization_rewrite": str(finalization_rewrite).lower(),
        "closer_replaced": str(closer_replaced).lower(),
        "duration_ms": str(duration_ms),
    }
    logger.info("finalization %s", diagnostics)

    return FinalizeResult(
        text=text.strip(),
        plan=plan,
        epistemic_rewrite=epistemic_rewrite,
        generic_cta_removed=generic_removed,
        finalization_rewrite=finalization_rewrite,
        closer_replaced=closer_replaced,
        diagnostics=diagnostics,
    )


def prompt_content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def plan_as_dict(plan: ResponsePlan) -> Dict:
    return asdict(plan)
