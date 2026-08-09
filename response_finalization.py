# -*- coding: utf-8 -*-
"""Protective finalization — infrastructure, not authorship.

CONTRACT (protect-only-v1) — see docs/PROTECT_ONLY_FINALIZER.md

Generation creates. Finalization protects. Nothing else.

Before changing this module, answer ONE question:
  Does this prevent a defect, or does it change the writing?
  If it changes the writing → move to generation or delete.

Finalization may ONLY:
  1. Remove obvious hallucinated mechanics
  2. Remove generic assistant garbage
  3. Fix broken formatting
  4. Remove duplicated ideas
  5. Enforce safety (malformed/banned closers)

If the draft is coherent: DO NOT TOUCH IT.
Average creative rewrites target ≈ 0.
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
from recognition_callbacks import is_generic_followup
from recognition_landing import (
    CREATIVE_ENDING_TOOLS_ENABLED,
    LANDING_ENGINE_VERSION,
    apply_landing,
    protective_cleanup,
    select_landing,
    strip_malformed_closers,
)
from signature_language import extract_signature_language
from surface_render import final_surface_render, response_text_after_surface_semantically_equals

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

# Distance 4 — invented hidden schemes / deception / engineered plots.
HIDDEN_SCHEME_REWRITES = [
    (
        r"\b(?:he|she|they)\s+used the lockout(?: kit| issue| situation)? as a (?:pretext|setup|ruse)\b",
        "He later made a move after getting her number - that doesn't prove the lockout itself was a setup",
    ),
    (
        r"\b(?:deliberately|intentionally)\s+(?:engineered|exploited|manipulated|tricked)\b",
        "the behavior shows a clear personal move - inventing a long game goes further than the facts",
    ),
    (
        r"\b(?:he|she|they)\s+(?:tricked|cornered)\b",
        "he made a personal move",
    ),
    (
        r"\bplanned (?:this|it) from the (?:start|beginning)\b",
        "made a clear personal move once he had the number",
    ),
    (
        r"\bhad been planning\b",
        "later made a personal move",
    ),
    (
        r"\bengineered the (?:situation|lockout|encounter)\b",
        "made a personal move after the number exchange",
    ),
]

# Distance 3 — consequential attributions that overreach ordinary pursuit.
CONSEQUENTIAL_REWRITES = [
    (
        r"\b[Hh]e wanted control\b",
        "He's making a move - whether that includes a control dynamic is less certain than the romantic interest",
    ),
    (
        r"\b[Hh]e lied to get (?:her|his|their) number\b",
        "He got the number in a practical frame, then made a personal move - lying isn't established",
    ),
    (
        r"\bsecretly (?:has|have) another (?:partner|girlfriend|boyfriend)\b",
        "they may want convenience more than commitment - a secret partner isn't established",
    ),
    (
        r"\bplanned (?:your|their) termination\b",
        "they are protecting their position - a termination plan isn't established",
    ),
]

# Invented quantitative specificity only (obvious hallucination).
INVENTED_PRECISION_REWRITES = [
    (
        r"\b[Tt]he average person'?s sexual vocabulary has been trained by thousands of hours\b",
        "People now have vastly more exposure to explicit material than they did in 1995",
    ),
    (r"\bthousands of hours\b", "vastly more exposure"),
    (r"\b\d{1,3}(?:,\d{3})+\s+hours\b", "vastly more exposure"),
    (r"\b(?:hundreds|thousands|millions) of (?:hours|times)\b", "vastly more exposure"),
    (r"\b\d{2,}\s*%\b", "a sizable share"),
]


ClaimClass = str  # OBSERVATION | ORDINARY_INFERENCE | INTERPRETIVE_THESIS | CONSEQUENTIAL_ATTRIBUTION | HIDDEN_SCHEME


def classify_inference_distance(sentence: str) -> Tuple[int, ClaimClass]:
    """Return (distance 0-4, claim class) for a sentence."""
    s = (sentence or "").lower()
    if not s.strip():
        return 0, "OBSERVATION"

    scheme_markers = (
        "pretext", "engineered", "tricked", "setup", "ruse", "from the start",
        "from the beginning", "had been planning", "deliberately exploited",
        "deliberately manipulated", "deliberately engineered", "cornered",
        "planned your termination", "secretly has another", "secretly have another",
    )
    if any(m in s for m in scheme_markers):
        return 4, "HIDDEN_SCHEME"

    consequential_markers = (
        "wanted control", "lied to get", "afraid of him", "afraid of her",
        "gaslight", "predator", "groom",
    )
    if any(m in s for m in consequential_markers):
        return 3, "CONSEQUENTIAL_ATTRIBUTION"

    ordinary_markers = (
        "making a move", "interested in", "wants her", "wants him",
        "get laid", "romantically", "sexually interested", "personal move",
        "more personal", "read the number as", "interpreted the number",
        "low priority", "convenience more than commitment", "protecting their position",
        "social enforcement", "protecting the narrative", "disciplinary tool",
        "functions as", "works as",
    )
    if any(m in s for m in ordinary_markers):
        return 1, "ORDINARY_INFERENCE"

    thesis_markers = (
        "performative", "industrialized", "mainstream", "optionality",
        "monetized", "reference library", "cultural", "porn helped",
        "online culture",
    )
    if any(m in s for m in thesis_markers):
        return 2, "INTERPRETIVE_THESIS"

    # Default: treat as observation/low-distance unless clearly speculative scheme language
    return 0, "OBSERVATION"


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
    governing_pattern: Optional[str] = None  # invisible rule — not a prose sentence
    central_insight: Optional[str] = None  # legacy alias of governing_pattern
    original_subject: Optional[str] = None
    closing_strategy: str = "none"  # legacy alias of landing
    landing: str = "silence"  # body_ends_response | signature_line | callback | action | silence
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


def infer_governing_pattern(user_message: str, draft: str = "") -> str:
    """Diagnostic: short rule-shaped pattern — not a mid-essay analytical sentence.

    Prefer the opening take when it reads like a noticed rule.
    Never prefer mid-draft consultant vocabulary as the logged 'insight'.
    """
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", (draft or "").strip())
        if s.strip() and not s.strip().endswith("?")
    ]
    if sentences:
        first = sentences[0]
        fl = first.lower()
        # Opening take that sounds like a rule / observation
        if 12 <= len(first) <= 180 and any(
            w in fl
            for w in (
                "rule", "because", "stopped", "promise", "trust", "cost",
                "move", "when", "didn't", "did not", "not because", "playing",
            )
        ):
            # Skip if it dumps internal analysis labels
            if not any(
                bad in fl
                for bad in (
                    "incentive structure", "narrative contract", "coherence",
                    "framework", "governing mechanism", "systemic",
                )
            ):
                return first.rstrip(".!")
        # Otherwise first short concrete sentence beats a middle-essay dump
        if 12 <= len(first) <= 140:
            if not any(
                bad in fl
                for bad in (
                    "incentive structure", "narrative contract",
                    "framework", "governing mechanism",
                )
            ):
                return first.rstrip(".!")
    subject = extract_original_subject(user_message)
    return f"pattern about {subject}" if subject else ""


def infer_central_insight(user_message: str, draft: str) -> str:
    """Legacy name — returns governing_pattern."""
    return infer_governing_pattern(user_message, draft)


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
    body: str = "",
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

    decision = select_landing(
        user_message,
        selected_command=selected_command,
        body=body,
        practical=practical,
        grief=grief,
        technical=technical,
        roast=roast,
        missing_info=missing,
    )
    landing = decision.landing.lower()

    if missing:
        intent = "clarify"
        confidence = "low"
        primary = "Clarification"
    elif practical:
        intent = "action"
        confidence = "medium"
        primary = "Practical Next Action"
    elif grief:
        intent = "witness"
        confidence = "high"
        primary = "Quiet Presence"
    elif technical:
        intent = "technical"
        confidence = "medium"
        primary = "Operational Intelligence"
    elif insight:
        intent = "explore"
        confidence = "medium"
        primary = "Cultural Analysis" if is_cultural_or_insight(user_message) else "Pattern Recognition"
    else:
        intent = "respond"
        confidence = "medium"
        primary = "Emotional State Recognition"

    subject = extract_original_subject(user_message)
    anchors = extract_conversation_anchors(user_message)
    # Legacy closing_strategy field mirrors landing for telemetry compatibility
    legacy_map = {
        "body_ends_response": "none",
        "signature_line": "ritual_line",
        "recognition_callback": "recognition_callback",
        "recognition_statement": "ritual_line",
        "recognition_observation": "ritual_line",
        "action": "action_line",
        "silence": "silence",
    }
    return ResponsePlan(
        intent=intent,
        primary_capability=primary,
        supporting_capability="Epistemic Calibration",
        evidence_confidence=confidence,
        needs_practical_action=practical,
        expected_shift_from="confusion" if insight else None,
        expected_shift_to="clarity" if insight else ("action" if practical else None),
        governing_pattern=None,
        central_insight=None,
        original_subject=subject,
        closing_strategy=legacy_map.get(landing, "none"),
        landing=landing,
        allow_question=decision.allow_question,
        missing_required_info=missing,
        channel=channel,
        mode=mode,
        selected_command=selected_command or "/thoughts",
        anchors=list(anchors.all_anchors),
    )


CORE_WRITE_DIRECTIVE = """CORE WRITE RULE (highest priority for this reply):

THINK abstractly. SPEAK concretely.
MoodyBot sees systems. MoodyBot does not talk ABOUT systems.

MoodyBot does not describe what happened. MoodyBot explains why it felt the way it did.

Generation order (mandatory):
1) Intent / evidence
2) GOVERNING PATTERN — answer: "What invisible rule explains this?" (not "what sentence summarizes this?")
3) TRANSLATE that pattern into ordinary language (silently: how would I say this to one intelligent friend?)
4) WRITE: concrete claim → one or two proofs of what someone would notice → STOP

Never dump internal reasoning labels into prose.
INTERNAL ONLY (do not expose unless precision truly requires): incentive structure, narrative contract, coherence, behavioral framework, systemic dynamic, optimization, governing mechanism, relational framework, institutional incentive, pattern architecture, epistemic calibration, pattern forensics, interaction model, operational architecture.

Prefer spoken observations: rules, promises, trust, cost, pressure, cheating, earning, breaking, winning, losing, waiting, leaving, staying, move, boundary, attention, reward.

First sentence = concrete claim with tension.
GOOD: "The show stopped playing by its own rules." / "He's making a move." / "People don't trust you yet."
BAD: "The series abandoned the incentive structure..." / "The relationship exhibits..." / "The trust architecture is underdeveloped."

Every paragraph: "What would a perceptive person actually notice?" — not "what analytical category is this?"
One excellent proof beats three shallow examples.
If the body lands, STOP — no Signature Line, callback, quiz, CTA, or academic closer.

Do NOT open with throat-clearing. Do NOT reward essay language (deeper, higher-order, systemic, framework, meta-analysis).
Do NOT require metaphor, noir, or poetic costume. Keep real technical/legal terms when they are the precise terms.

Product test: reader thinks "I've never looked at it like that" — not "that was a sophisticated explanation."

If practical action was requested, end with a concrete next step.
"""


def plan_closer_instruction(plan: ResponsePlan) -> str:
    """Generation guidance — insight-first. Not a closer-module compliance checklist."""
    _ = plan
    extra = ""
    if plan.needs_practical_action:
        extra = "\nUser asked for action — include a concrete next step. No quiz question."
    elif plan.intent == "technical":
        extra = "\nTechnical mode: cause → fix. No poetry unless it helps."
    elif plan.intent == "witness":
        extra = "\nWitness mode: stay with the weight. No forced closer."
    return CORE_WRITE_DIRECTIVE + extra


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
    """Remove obvious hallucinated mechanics only. Never polish prose."""
    _ = plan
    text = draft or ""
    changed = False

    for pattern, replacement in HIDDEN_SCHEME_REWRITES:
        new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if n:
            text = new_text
            changed = True

    for pattern, replacement in CONSEQUENTIAL_REWRITES:
        new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if n:
            text = new_text
            changed = True

    for pattern, replacement in INVENTED_PRECISION_REWRITES:
        new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if n:
            text = new_text
            changed = True

    return text, changed


def should_rewrite_claim(sentence: str) -> bool:
    """True only for distance 3–4 (or invented precision handled separately)."""
    distance, _claim = classify_inference_distance(sentence)
    return distance >= 3


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
    """Compat wrapper — only returns a question when signature language earns it.

    Never staples topic nouns into 'What about X looks different...'
    """
    from recognition_landing import craft_callback_question, craft_recognition_statement

    _ = plan
    _ = anchors
    q = craft_callback_question(user_message, conversation_id=conversation_id)
    if q:
        return q
    stmt = craft_recognition_statement(user_message, draft or "")
    return stmt or ""


def validate_recognition_callback_quality(
    question: str,
    user_message: str,
    plan: ResponsePlan,
    anchors: Optional[ConversationAnchors] = None,
) -> Dict[str, bool]:
    """Landing quality — grammar and essay-worthiness beat module compliance."""
    from recognition_landing import is_grammatical_english, would_keep_if_nobody_could_reply
    from signature_language import rhetorical_callback_quality

    _ = anchors
    _ = plan
    q = (question or "").strip()
    signatures = extract_signature_language(user_message)
    rq = rhetorical_callback_quality(q, user_message, signatures)
    grammatical = is_grammatical_english(q) if q.endswith("?") else (
        is_grammatical_english(q if q.endswith((".", "!")) else q + ".")
    )
    return {
        "specificity": True,
        "callback": True,
        "anchor": (not signatures.protected) or rq["preserves_signature"],
        "rhetorical": grammatical and would_keep_if_nobody_could_reply(q) if q.endswith("?") else grammatical,
        "no_synonym_destruction": rq["no_synonym_destruction"],
        "shift": True,
        "not_generic": not detect_generic_cta(q),
        "novel": not _recent_closer_collision(q),
        "brief": len(q.split()) <= 42,
        "is_question": q.endswith("?"),
        "grammatical": grammatical,
    }


def _apply_closing_strategy(
    text: str,
    plan: ResponsePlan,
    user_message: str,
    anchors: Optional[ConversationAnchors] = None,
) -> Tuple[str, bool, bool]:
    """Protective landing cleanup. Returns (text, modified, landing_added).

    landing_added is True only if a creative ending was actually appended.
    On the default path this should almost always be False.
    """
    if anchors is not None and not plan.anchors:
        plan.anchors = list(anchors.all_anchors)

    before = (text or "").strip()
    decision = select_landing(
        user_message,
        selected_command=plan.selected_command,
        body=text,
        practical=plan.needs_practical_action,
        grief=plan.intent == "witness",
        technical=plan.intent == "technical",
        roast=plan.selected_command in {"/roast", "/savage", "/cut"},
        missing_info=plan.missing_required_info,
    )
    plan.landing = decision.landing.lower()
    legacy_map = {
        "body_ends_response": "none",
        "signature_line": "ritual_line",
        "recognition_callback": "recognition_callback",
        "recognition_statement": "ritual_line",
        "recognition_observation": "ritual_line",
        "action": "action_line",
        "silence": "silence",
    }
    plan.allow_question = decision.allow_question and CREATIVE_ENDING_TOOLS_ENABLED

    # Default: protective strip only — never invent endings
    if not CREATIVE_ENDING_TOOLS_ENABLED:
        cleaned, mod = protective_cleanup(before)
        # Still honor silence/action selection for trailing questions
        if decision.landing in {"SILENCE", "ACTION", "BODY_ENDS_RESPONSE"}:
            new_text, apply_mod = apply_landing(
                cleaned, user_message, decision, plan=plan
            )
            mod = mod or apply_mod
        else:
            new_text = cleaned
        plan.landing = "body_ends_response" if decision.landing not in {
            "SILENCE", "ACTION"
        } else decision.landing.lower()
        plan.closing_strategy = legacy_map.get(plan.landing, "none")
        return new_text, mod, False

    new_text, modified = apply_landing(
        text, user_message, decision, plan=plan
    )
    from signature_line import last_line_is_signature as _last_is_sig

    landing_added = False
    if decision.landing in {
        "SIGNATURE_LINE",
        "RECOGNITION_STATEMENT",
        "RECOGNITION_OBSERVATION",
        "RECOGNITION_CALLBACK",
    }:
        if decision.landing == "RECOGNITION_CALLBACK" and new_text.rstrip().endswith("?"):
            landing_added = len(new_text) > len(before)
        elif _last_is_sig(new_text, user_message=user_message):
            landing_added = True
        else:
            plan.landing = "body_ends_response"
    plan.closing_strategy = legacy_map.get(plan.landing, plan.closing_strategy)
    if modified:
        last = new_text.strip().split("\n\n")[-1] if new_text else ""
        if last:
            _RECENT_CLOSERS.append(re.sub(r"\s+", " ", last.lower()))
    return new_text, modified, landing_added


def remove_duplicate_paragraphs(text: str) -> Tuple[str, bool]:
    """Drop consecutive duplicate paragraphs only — not paraphrase scoring."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    if len(paras) < 2:
        return (text or "").strip(), False
    kept: List[str] = []
    for p in paras:
        if kept and _normalize_compare(p) == _normalize_compare(kept[-1]):
            continue
        kept.append(p)
    out = "\n\n".join(kept)
    return out, out != (text or "").strip()


def fix_broken_formatting(text: str) -> Tuple[str, bool]:
    """Whitespace / newline collapse only. No opener trimming. No prose compress."""
    original = text or ""
    out = re.sub(r"\n{3,}", "\n\n", original)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = out.strip()
    return out, out != original.strip()


def _normalize_compare(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


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
    """Protect only. If not obviously broken — ship it."""
    t0 = time.time()
    plan = plan or build_response_plan(
        user_message,
        selected_command=selected_command,
        channel=channel,
        mode=mode,
    )
    pattern = plan.governing_pattern or plan.central_insight or infer_governing_pattern(
        user_message, draft
    )
    plan.governing_pattern = pattern
    plan.central_insight = pattern  # legacy alias
    plan.original_subject = plan.original_subject or extract_original_subject(user_message)

    anchors = extract_conversation_anchors(user_message, draft)
    plan.anchors = list(anchors.all_anchors)

    def _last_sentence(blob: str) -> str:
        paras = re.split(r"\n\s*\n", (blob or "").strip())
        last = (paras[-1] if paras else "").strip()
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", last) if s.strip()]
        return sents[-1] if sents else last

    body_generated = (draft or "").strip()
    text = body_generated
    draft_last = _last_sentence(text)
    epistemic_rewrite = False
    generic_removed = False
    closer_replaced = False
    surface_cleaned = False
    landing_added = False
    deduped = False
    post_reasons: List[str] = []

    # 1) Obvious hallucinated mechanics only
    text, epistemic_rewrite = run_epistemic_check(text, plan)
    if epistemic_rewrite:
        post_reasons.append("hallucinated_mechanics")
    after_epistemic_last = _last_sentence(text)

    # 2) Generic assistant garbage / CTA
    if not (plan.missing_required_info and len(text.split()) < 40):
        text, generic_removed = strip_generic_cta(text)
        if generic_removed:
            post_reasons.append("cta_removed")

    # 3) Safety: strip only obviously broken closers (no writing tools)
    text, closer_replaced, landing_added = _apply_closing_strategy(
        text, plan, user_message, anchors
    )
    if closer_replaced:
        post_reasons.append("malformed_closer_stripped")
    if landing_added:
        # Should be ~never on default path
        post_reasons.append("landing_added")
    after_landing = text
    after_landing_last = _last_sentence(after_landing)

    # 4) Duplicate paragraphs
    text, deduped = remove_duplicate_paragraphs(text)
    if deduped:
        post_reasons.append("duplicate_removed")

    # 5) Broken formatting + typography (no prose repair)
    text, formatted = fix_broken_formatting(text)
    if formatted:
        post_reasons.append("format_fix")

    text, surface_cleaned = final_surface_render(text)
    after_surface_last = _last_sentence(text)

    if not response_text_after_surface_semantically_equals(after_landing, text):
        import os

        if os.environ.get("MOODYBOT_STRICT_SURFACE", "1") == "1" and os.environ.get(
            "MOODYBOT_ENV", "development"
        ) != "production":
            # Whiskey watermark alone is allowed; meaning changes are not
            body_a = re.sub(r"\s*🥃\s*", " ", after_landing).strip()
            body_b = re.sub(r"\s*🥃\s*", " ", text).strip()
            if _normalize_compare(body_a) != _normalize_compare(body_b):
                raise AssertionError(
                    "SURFACE_INVARIANT: final_surface_render changed wording beyond typography"
                )
        text = strip_malformed_closers(text)
        post_reasons.append("surface_safety_strip")

    if surface_cleaned:
        post_reasons.append("surface_typography")

    post_finalizer_changed = _normalize_compare(body_generated) != _normalize_compare(
        re.sub(r"\s*🥃\s*", " ", text)
    )
    creative_touch = landing_added
    finalization_rewrite = (
        epistemic_rewrite
        or generic_removed
        or closer_replaced
        or deduped
        or formatted
        or surface_cleaned
    )
    duration_ms = int((time.time() - t0) * 1000)

    diagnostics = {
        "event": "moodybot_generation",
        "mode": plan.mode,
        "channel": plan.channel,
        "prompt_hash": prompt_hash or "",
        "git_commit": git_commit or "",
        "landing_engine_version": LANDING_ENGINE_VERSION,
        "creative_ending_tools": str(CREATIVE_ENDING_TOOLS_ENABLED).lower(),
        "governing_pattern": (plan.governing_pattern or "")[:240],
        "core_insight": (plan.governing_pattern or "")[:240],  # deprecated alias
        "body_generated": body_generated[:400],
        "post_finalizer_changed_text": str(post_finalizer_changed).lower(),
        "post_finalizer_reason": ",".join(post_reasons) if post_reasons else "none",
        "landing_added": str(landing_added).lower(),
        "cta_removed": str(generic_removed).lower(),
        "creative_touch": str(creative_touch).lower(),
        "primary_capability": plan.primary_capability or "",
        "supporting_capability": plan.supporting_capability or "",
        "intervention": plan.intervention or "",
        "voice": plan.voice or "",
        "closing_strategy": plan.closing_strategy,
        "landing": plan.landing,
        "anchors": ",".join(plan.anchors[:6]),
        "epistemic_rewrite": str(epistemic_rewrite).lower(),
        "generic_cta_removed": str(generic_removed).lower(),
        "finalization_rewrite": str(finalization_rewrite).lower(),
        "closer_replaced": str(closer_replaced).lower(),
        "surface_cleaned": str(surface_cleaned).lower(),
        "duration_ms": str(duration_ms),
        "draft_last_sentence": draft_last[:240],
        "after_epistemic_last_sentence": after_epistemic_last[:240],
        "after_landing_last_sentence": after_landing_last[:240],
        "after_surface_render_last_sentence": after_surface_last[:240],
        "final_http_last_sentence": after_surface_last[:240],
    }
    if (plan.mode or "").lower() == "dynamic":
        logger.info("DYNAMIC_TRACE_START")
        logger.info(
            "DYNAMIC_TRACE %s",
            {
                "git_commit": git_commit or "",
                "prompt_hash": prompt_hash or "",
                "route": f"{plan.channel}/finalize_response",
                "generation_function": "finalize_response",
                "landing_engine_version": LANDING_ENGINE_VERSION,
                "draft_last_sentence": draft_last[:240],
                "after_epistemic_last_sentence": after_epistemic_last[:240],
                "after_landing_last_sentence": after_landing_last[:240],
                "after_surface_render_last_sentence": after_surface_last[:240],
                "final_http_last_sentence": after_surface_last[:240],
            },
        )
        logger.info("DYNAMIC_TRACE_END")
    logger.info("finalization %s", diagnostics)
    logger.info("landing_engine_version=%s", LANDING_ENGINE_VERSION)

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
