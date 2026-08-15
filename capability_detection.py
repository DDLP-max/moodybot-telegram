# -*- coding: utf-8 -*-
"""HIDDEN_TRANSACTION + ESCALATION_PAYOFF + comic-premise gate.

HIDDEN_TRANSACTION: what MoodyBot sees (unstated exchange under the stated event).
ESCALATION_PAYOFF: how MoodyBot tells a story (beats that escalate → concrete stop).
COMIC_PREMISE: recognize exaggerated comic bits before therapeutic reframing.

Evidence-gated. Never slash commands. Never exposed as user-facing modes.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger("moodybot")

# Confidence gates (spec)
HT_FLOOR = 0.55
HT_STRONG = 0.75
COMIC_FLOOR = 0.55


@dataclass
class HiddenTransactionAnalysis:
    surface_event: str = ""
    stated_goal: Optional[str] = None
    observed_behavior: List[str] = field(default_factory=list)
    underlying_desire: Optional[str] = None
    underlying_fear: Optional[str] = None
    risk_holder: Optional[str] = None
    risk_transfer: Optional[str] = None
    actual_transaction: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def active(self) -> bool:
        return self.confidence >= HT_FLOOR and bool(self.actual_transaction)


@dataclass
class EscalationPayoffAnalysis:
    active: bool = False
    beat_signals: List[str] = field(default_factory=list)
    concrete_payoff_hint: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ComicPremiseAnalysis:
    """Exaggerated comic premise — heighten/tag; never cure."""

    active: bool = False
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    never_cure: bool = True

    @property
    def should_block_therapy(self) -> bool:
        return self.active and self.confidence >= COMIC_FLOOR


# --- surface / motive mismatch cues ---
_INSUFFICIENT_JUSTIFICATION = re.compile(
    r"\b("
    r"expensive|budget|approve[sd]?|vendor|consultant|mckinsey|deloitte|"
    r"cybersecurity|compliance|security\s+software|letterhead|"
    r"hire[sd]?\s+(?:an?\s+)?actor|fake\s+demo|basically\s+nothing|"
    r"already\s+knows?\s+what|rubber[\s-]?stamp|"
    r"status|reputation|cover\s+(?:his|her|their)\s+|"
    r"blame|scapegoat|somebody\s+else\s+to\s+blame|"
    r"are\s+they\s+serious|is\s+(?:he|she|they)\s+serious|"
    r"permission\s+to|stop\s+protecting|auditioning|"
    r"why\s+would\s+they|what(?:'s|\s+is)\s+really\s+|"
    r"buying\s+(?:certainty|cover|status|absolution|validation)"
    r")\b",
    re.I,
)

_RISK_TRANSFER = re.compile(
    r"\b("
    r"blame|cover|letterhead|someone\s+else(?:'s)?|"
    r"reputational|career\s+protect|transfer\s+of\s+blame|"
    r"external\s+validation|institutional\s+cover|"
    r"professional\s+cover|liability|scapegoat"
    r")\b",
    re.I,
)

_ESCALATION_STORY = re.compile(
    r"\b("
    r"and\s+then|then\s+(?:he|she|they|the)|"
    r"hired?\s+an?\s+actor|scare[sd]?|"
    r"approves?\s+more|budget\s+increase|"
    r"pontoon|boat\s+sank|sank\s+at\s+the\s+dock|"
    r"increasingly|worse|even\s+more|finally|"
    r"reveal|turns?\s+out|secret(?:ly)?"
    r")\b",
    re.I,
)

_CONCRETE_PAYOFF = re.compile(
    r"\b("
    r"pontoon\s+boat|bought\s+a\s+boat|sank\s+at\s+the\s+dock|"
    r"it\s+sank|dock\.?$|bought\s+(?:the\s+)?boat"
    r")\b",
    re.I,
)

_TECHNICAL_NO_HT = re.compile(
    r"\b("
    r"fiber\s+connector|replace\s+(?:a\s+)?fiber|how\s+do\s+i\s+(?:fix|replace|install)|"
    r"which\s+api|stack\s+trace|null\s+pointer|sql\s+query|compile\s+error"
    r")\b",
    re.I,
)

_MORAL_TAIL = re.compile(
    r"(?is)(?:\n\n|\s+)("
    r"(?:and\s+)?that'?s\s+the\s+lesson|"
    r"sometimes\s+(?:life|the\s+thing)|"
    r"the\s+moral\s+is|"
    r"which\s+just\s+goes\s+to\s+show|"
    r"in\s+the\s+end,?\s+(?:maybe|we|you)|"
    r"maybe\s+that'?s\s+what\s+we'?re\s+all"
    r").*$"
)

# Comic premise cues — conspicuous exaggeration / absurd optimization / punchline unlock
_COMIC_OPTIMIZATION = re.compile(
    r"\b("
    r"bulk(?:ing)?|cut(?:ting)?|macros?|body[- ]?fat|calorie|PR\b|personal\s+record|"
    r"optimize|optimization|protocol|phase\s+(?:one|two|1|2|three|3)|"
    r"unlock|level\s+up|beginner\s+program|advanced\s+(?:compound|movement)"
    r")\b",
    re.I,
)
_COMIC_BASIC_SOCIAL = re.compile(
    r"\b("
    r"look(?:ing)?\s+(?:\w+\s+)?(?:women|people|girls|her|him)\s+in\s+the\s+eyes|"
    r"eye\s+contact|saying\s+hello|talk(?:ing)?\s+to\s+(?:women|girls|strangers)|"
    r"ask(?:ing)?\s+(?:someone|her|him)\s+out|hold(?:ing)?\s+a\s+conversation"
    r")\b",
    re.I,
)
_COMIC_ABSURD_DELAY = re.compile(
    r"\b("
    r"only\s+\d+\s+more\s+years?|in\s+\d+\s+more\s+years?|"
    r"after\s+\d+\s+years?\s+of|once\s+i\s+(?:finish|complete|hit)|"
    r"then\s+i\s+(?:can|could|will)\s+begin|begin\s+phase"
    r")\b",
    re.I,
)
_COMIC_PUNCHLINE_FRAME = re.compile(
    r"\b("
    r"phase\s+(?:one|1)\s+of|finally\s+(?:ready|allowed)\s+to|"
    r"earn(?:ed|ing)?\s+the\s+right\s+to|graduate\s+to"
    r")\b",
    re.I,
)
# Genuine distress — do not treat as a bit
_COMIC_GENUINE_DISTRESS = re.compile(
    r"\b("
    r"i'?m\s+(?:really\s+)?(?:scared|terrified|depressed|suicidal)|"
    r"panic\s+attack|can'?t\s+leave\s+the\s+house|trauma|abuse|"
    r"been\s+struggling\s+with\s+anxiety\s+for"
    r")\b",
    re.I,
)
# Known failure mode: curing the joke with therapist aphorism
_PREMISE_CURE = re.compile(
    r"(?i)("
    r"the\s+body\s+isn'?t\s+the\s+gatekeeper|"
    r"the\s+story\s+is\.?$|"
    r"the\s+real\s+(?:issue|problem)\s+is|"
    r"it'?s\s+not\s+(?:really\s+)?about\s+(?:your\s+)?(?:body|muscles?|physique)|"
    r"what\s+you'?re\s+really\s+afraid\s+of|"
    r"once\s+you\s+accept\s+yourself|"
    r"self[- ]worth\s+isn'?t\s+measured"
    r")"
)


def detect_comic_premise(user_message: str) -> ComicPremiseAnalysis:
    """Detect exaggerated comic premises before therapeutic reframing.

    When an apparently vulnerable statement contains conspicuous exaggeration,
    absurd sequencing, impossible optimization, or punchline construction,
    treat it as a bit — never cure the premise.
    """
    text = (user_message or "").strip()
    out = ComicPremiseAnalysis()
    if not text or _TECHNICAL_NO_HT.search(text) or _COMIC_GENUINE_DISTRESS.search(text):
        return out

    signals: List[str] = []
    score = 0.0

    if _COMIC_OPTIMIZATION.search(text):
        signals.append("optimization_frame")
        score += 0.3
    if _COMIC_BASIC_SOCIAL.search(text):
        signals.append("basic_social_unlock")
        score += 0.3
    if _COMIC_ABSURD_DELAY.search(text):
        signals.append("absurd_delay")
        score += 0.25
    if _COMIC_PUNCHLINE_FRAME.search(text):
        signals.append("punchline_frame")
        score += 0.25

    # Fitness protocol applied to trivial human act = strong comic compound
    if "optimization_frame" in signals and "basic_social_unlock" in signals:
        score += 0.2
        signals.append("fitness_to_social_absurdism")

    out.signals = signals
    out.confidence = round(min(0.95, score), 2)
    # Need compound evidence — not bare "eye contact" alone
    out.active = out.confidence >= COMIC_FLOOR and len(signals) >= 2
    out.never_cure = True
    return out


def looks_like_premise_cure(draft: str) -> bool:
    """True when a reply 'cures' a comic premise with therapist reframing."""
    body = re.sub(r"\s*🥃\s*$", "", (draft or "").strip())
    if not body:
        return False
    return bool(_PREMISE_CURE.search(body))


def detect_hidden_transaction(user_message: str) -> HiddenTransactionAnalysis:
    """Evidence-gated hidden-transaction detection. Never invent motives for tech how-tos."""
    text = (user_message or "").strip()
    analysis = HiddenTransactionAnalysis(surface_event=text[:160])
    if not text or _TECHNICAL_NO_HT.search(text):
        return analysis

    evidence: List[str] = []
    score = 0.0

    just_hits = _INSUFFICIENT_JUSTIFICATION.findall(text)
    if just_hits:
        evidence.extend(sorted({h.lower() for h in just_hits})[:8])
        score += 0.25 + 0.05 * min(4, len(just_hits))

    risk_hits = _RISK_TRANSFER.findall(text)
    if risk_hits:
        evidence.extend(sorted({h.lower() for h in risk_hits})[:6])
        score += 0.3

    # Domain-shaped propositions (only when cues present)
    low = text.lower()
    if re.search(r"\b(cybersecurity|security\s+software|vendor)\b", low) and (
        re.search(r"\b(blame|cover|approve|budget|scare|actor|fake)\b", low)
    ):
        analysis.stated_goal = "buy cybersecurity / risk reduction"
        analysis.underlying_fear = "career or reputational failure if security fails"
        analysis.risk_transfer = "professional cover transferred to vendor/process"
        analysis.actual_transaction = (
            "reputational/career risk transfer — buying someone else to blame"
        )
        analysis.underlying_desire = "absolution if the system fails"
        analysis.risk_holder = "executive / CFO"
        score = max(score, 0.82)
        evidence.append("cybersecurity + blame/cover/approval cues")

    elif re.search(r"\b(mckinsey|deloitte|consultant|consulting)\b", low) and (
        re.search(r"\balready\s+knows?|rubber[\s-]?stamp|recommend\s+it|letterhead\b", low)
        or re.search(r"\bhire[sd]?\b", low)
    ):
        analysis.stated_goal = "get expert recommendation"
        analysis.actual_transaction = (
            "external validation / institutional cover / blame transfer"
        )
        analysis.underlying_desire = "permission to do what management already decided"
        analysis.risk_transfer = "recommendation arrives on someone else's letterhead"
        score = max(score, 0.8)
        evidence.append("consultant + predecided/cover cues")

    elif re.search(
        r"\b("
        r"are\s+they\s+serious|is\s+(?:he|she)\s+serious|"
        r"serious\s+about\s+(?:us|me|this|the\s+relationship)|"
        r"partner\s+is\s+serious|whether\s+(?:their|the)\s+partner\s+is\s+serious|"
        r"asks?\s+whether\s+.*\bserious\b"
        r")\b",
        low,
    ):
        analysis.stated_goal = "ask whether the partner is serious"
        analysis.actual_transaction = "permission to lower emotional defenses"
        analysis.underlying_fear = "getting hurt if they stop protecting themselves"
        analysis.underlying_desire = "stop auditioning / stop self-protection"
        score = max(score, 0.68)  # inference band unless more evidence
        evidence.append("seriousness question under affection/uncertainty")

    elif score >= HT_FLOOR and not analysis.actual_transaction:
        # Generic but gated: expensive/status without functional story
        if re.search(r"\b(expensive|premium|status|signal)\b", low):
            analysis.actual_transaction = (
                "unstated exchange (status, certainty, or cover) under the stated purchase"
            )
            score = min(score, 0.72)  # stay cautious without specific mechanism

    analysis.evidence = evidence
    analysis.observed_behavior = evidence[:5]
    analysis.confidence = round(min(0.95, score), 2)
    if analysis.confidence < HT_FLOOR:
        analysis.actual_transaction = None
        analysis.confidence = min(analysis.confidence, HT_FLOOR - 0.01)
    return analysis


def detect_escalation_payoff(user_message: str) -> EscalationPayoffAnalysis:
    """Detect chronological escalation stories with a concrete terminal payoff."""
    text = (user_message or "").strip()
    out = EscalationPayoffAnalysis()
    if not text or _TECHNICAL_NO_HT.search(text):
        return out

    beats = _ESCALATION_STORY.findall(text)
    payoff = _CONCRETE_PAYOFF.search(text)
    # Also treat multi-beat "then" chains as story-shaped
    then_count = len(re.findall(r"\bthen\b", text, flags=re.I))
    score = 0.0
    signals: List[str] = []
    if beats:
        signals.extend(sorted({b.lower() for b in beats})[:8])
        score += 0.35 + 0.08 * min(5, len(beats))
    if then_count >= 2:
        signals.append(f"then_x{then_count}")
        score += 0.25
    if payoff:
        out.concrete_payoff_hint = payoff.group(0)
        signals.append(f"payoff:{payoff.group(0).lower()}")
        score += 0.35

    # Chronological list / multi-sentence story without tech how-to
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) >= 4 and then_count >= 1:
        score += 0.15
        signals.append("multi_beat_story")

    out.beat_signals = signals
    out.confidence = round(min(0.95, score), 2)
    out.active = out.confidence >= 0.55 and (then_count >= 2 or bool(payoff) or len(beats) >= 2)
    return out


def strip_post_payoff_moral(text: str) -> Tuple[str, bool]:
    """Remove moral/lesson tails after a concrete payoff. Typography-safe."""
    body = (text or "").rstrip()
    if not body:
        return body, False
    m = _MORAL_TAIL.search(body)
    if not m:
        return body, False
    # Only strip if something concrete already landed before the moral
    head = body[: m.start()].rstrip()
    if len(head) < 20:
        return body, False
    return head, True


def draft_has_terminal_payoff(text: str) -> bool:
    """True if the draft already ends on a concrete payoff (no moral needed)."""
    body = re.sub(r"\s*🥃\s*$", "", (text or "").strip())
    if not body:
        return False
    last = body.split("\n\n")[-1].strip()
    if _CONCRETE_PAYOFF.search(last):
        return True
    # Short concrete closer after longer body
    if len(body.split("\n\n")) >= 3 and len(last.split()) <= 14:
        if re.search(r"\b(boat|dock|sank|bought|approved|walked\s+away)\b", last, re.I):
            return True
    return False


def capability_guidance(
    ht: HiddenTransactionAnalysis,
    ep: EscalationPayoffAnalysis,
    comic: Optional[ComicPremiseAnalysis] = None,
) -> str:
    """Injection for plan_closer_instruction — compressed, evidence-bound."""
    parts: List[str] = []
    if comic and comic.should_block_therapy:
        parts.append(
            "\nCOMIC PREMISE (gate before therapeutic reframing — not a mode):\n"
            f"Confidence={comic.confidence:.2f} signals={','.join(comic.signals[:6])}.\n"
            "NEVER CURE THE PREMISE. The distortion IS the joke.\n"
            "Heighten the bit or add a sharper tag. Stay inside the user's frame.\n"
            "Do NOT reframe as sincere insecurity. Do NOT therapist-aphorism the setup.\n"
            "FAIL: \"The body isn't the gatekeeper. The story is.\"\n"
            "PASS: stay in the fitness/protocol absurdity applied to basic human contact.\n"
        )
    if ht.active:
        tone = (
            "strong Moody formulation allowed"
            if ht.confidence >= HT_STRONG
            else "express cautiously (Part of what may be happening… / less like X more like Y)"
        )
        parts.append(
            "\nCAPABILITY — HIDDEN_TRANSACTION (intelligence, not a mode):\n"
            f"Confidence={ht.confidence:.2f} ({tone}).\n"
            f"Surface: {ht.surface_event[:120]}\n"
            f"Actual transaction (internal): {ht.actual_transaction}\n"
            "Move: surface event → human incentive → fear/desire → risk/power → "
            "hidden transaction → broader pattern. Prefer concrete over abstract cynicism.\n"
            "Do NOT claim everything is secretly about status/childhood/power.\n"
            "Do NOT invent motives beyond the evidence.\n"
        )
    if ep.active:
        parts.append(
            "\nNARRATIVE — ESCALATION_PAYOFF (structure, not a persona):\n"
            "ordinary setup → anomaly → reveal → complication → escalation → "
            "concrete payoff → STOP.\n"
            "Every beat must raise stakes, reveal, reframe, or advance the payoff. "
            "No decorative paragraphs. No moral after the payoff. "
            "The concrete final detail IS the landing.\n"
        )
    if ht.active and ep.active:
        parts.append(
            "Both active: expose the hidden exchange inside the escalating story; "
            "still stop on the concrete payoff.\n"
        )
    return "".join(parts)


def log_capability_trace(
    ht: HiddenTransactionAnalysis,
    ep: EscalationPayoffAnalysis,
    comic: Optional[ComicPremiseAnalysis] = None,
) -> None:
    logger.info(
        "CAPABILITY_TRACE hidden_transaction=%s confidence=%.2f",
        1 if ht.active else 0,
        ht.confidence,
    )
    logger.info(
        "CAPABILITY_TRACE escalation_payoff=%s confidence=%.2f",
        1 if ep.active else 0,
        ep.confidence,
    )
    if comic is not None:
        logger.info(
            "CAPABILITY_TRACE comic_premise=%s confidence=%.2f never_cure=%s",
            1 if comic.active else 0,
            comic.confidence,
            1 if (comic.active and comic.never_cure) else 0,
        )
    if ep.active:
        logger.info("NARRATIVE_TRACE structure=ESCALATION_PAYOFF")
