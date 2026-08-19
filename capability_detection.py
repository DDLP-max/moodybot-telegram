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


# Social mode is a routing question, not a pipeline stage and not a user-facing mode.
# Identify the human moment first; Pattern Recognition is a tool after that.
SOCIAL_MODES = (
    "comic",
    "provocation",
    "provocative_generalization",
    "vulnerability",
    "question",
    "direct_participation",
    "observation",
    "open",
)

# Topical slash-tones that must not outrank pick-one / name-one interaction shape.
TOPICAL_AUTO_TONES = frozenset(
    {
        "/cinema",
        "/sensory",
        "/noir",
        "/velvet",
        "/ghost",
        "/float",
        "/drama",
    }
)


@dataclass
class SocialModeAnalysis:
    """What kind of human moment is this? Gates whether depth is even allowed."""

    mode: str = "open"
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    # Natural resolution of a question: name | explain | reason | ""
    resolution: str = ""
    # pick_one | pick_and_defend | why | how_to | awe | comic_handoff | taggable_bit | terminal_bit | open
    interaction_shape: str = "open"
    # Explicit negations the user ruled out — e.g. "Not bitter. Not lonely."
    premise_guards: List[str] = field(default_factory=list)

    @property
    def guarded_observation(self) -> bool:
        return bool(self.premise_guards) or "premise_guards" in self.signals

    @property
    def comic(self) -> bool:
        return self.mode == "comic"

    @property
    def participation(self) -> bool:
        return (
            self.mode == "direct_participation"
            or self.resolution == "name"
            or "participation" in self.signals
            or self.interaction_shape == "pick_one"
        )

    @property
    def comic_handoff(self) -> bool:
        """User left an unresolved contrast slot for Moody to complete."""
        return self.interaction_shape == "comic_handoff" or "comic_handoff" in self.signals

    @property
    def rhetorical_question(self) -> bool:
        """Awe / holy-shit, not a request for a causal theory."""
        return (
            self.interaction_shape == "awe"
            or "rhetorical" in self.signals
        )

    @property
    def blocks_topical_auto_route(self) -> bool:
        """Topic keywords (/cinema, movie, actor) must not beat pick-one."""
        return self.participation

    @property
    def terminal_bit(self) -> bool:
        return self.interaction_shape == "terminal_bit" or "terminal_bit" in self.signals

    @property
    def depth_earned(self) -> bool:
        if (
            self.participation
            or self.rhetorical_question
            or self.comic_handoff
            or self.terminal_bit
        ):
            return False
        return self.mode in {"vulnerability", "provocation"} or (
            self.mode == "question" and self.resolution in {"explain", "reason"}
        )


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
    r"been\s+struggling\s+with\s+anxiety\s+for|"
    r"burn(?:ed|t)?\s+out|survival\s+mode|"
    r"forgotten\s+how\s+to\s+(?:socialize|connect|be\s+a\s+person)|"
    r"hobbies\s+(?:are\s+)?gone|personality\s+(?:feels?\s+)?muted|"
    r"psychologically\s+deplet|i\s+don'?t\s+know\s+how\s+to\s+connect"
    r")\b",
    re.I,
)
# Joke-formula / anti-joke riff (stripper-name, first-pet + street)
_COMIC_JOKE_FORMULA = re.compile(
    r"\b("
    r"(?:porn[\s-]?star|stripper|whore|stage)\s+name|"
    r"first\s+pet|"
    r"street\s+you\s+grew\s+up|"
    r"now\s+it'?s\s+just\s+your\s+(?:actual\s+)?(?:fucking\s+)?name"
    r")\b",
    re.I,
)
# Surveillance / domestic analogy joke (Flock, Ring, wife as camera)
_COMIC_SURVEILLANCE_BIT = re.compile(
    r"\b(flock|ring\s+camera|alpr|license[\s-]?plate\s+reader|"
    r"searchable\s+footage)\b",
    re.I,
)
_COMIC_DOMESTIC = re.compile(
    r"\b(wife|girlfriend|spouse|she\s+knows|married)\b",
    re.I,
)
# Wife/stocks-style joke: domestic life analogized to a market/system
_COMIC_MARKET_BIT = re.compile(
    r"\b(stocks?|ticker|volatility|red\s+days?|green\s+days?)\b",
    re.I,
)
_COMIC_JOKE_PARALLEL = re.compile(
    r"\b(love\s+language|same\s+(?:as|coverage|volatility)|"
    r"except\s+the|worse\s+returns|just\s+(?:her|my\s+wife)\s+watching)\b",
    re.I,
)
# Self-deprecating comic misanthropy (not a cry for diagnosis)
_COMIC_SELF_DEPRECATE = re.compile(
    r"\b("
    r"i\s+hate\s+people|"
    r"not\s+in\s+a\s+cute|"
    r"need\s+a\s+nap\s+from\s+existing|"
    r"misanthrope"
    r")\b",
    re.I,
)
# Voluntary habit sold as fate — comic self-exoneration, not addiction intake
_COMIC_FAKE_FATE = re.compile(
    r"(?i)("
    r"hand.{0,18}dealt|"
    r"cards?.{0,18}dealt"
    r")"
)
_COMIC_VICE_HABIT = re.compile(
    r"\b("
    r"smok(?:e|ing|es)|drink(?:ing|s)?|cigarettes?|cigs?|"
    r"liquor|whiskey|whisky|beer|vape|gambling"
    r")\b",
    re.I,
)
# Trailing contrast that hands Moody the next beat. Completed "Alas, we play…" is not this.
_COMIC_HANDOFF = re.compile(
    r"(?i)("
    r",?\s*but\s+alas(?:\s*\.{2,}|\s*…)?\s*$|"
    r",?\s*and\s+yet(?:\s*\.{2,}|\s*…)?\s*$|"
    r"\bif\s+only(?:\s*\.{2,}|\s*…)?\s*$|"
    r",?\s*but\s+apparently(?:\s*\.{2,}|\s*…)?\s*$|"
    r"\bunfortunately(?:\s*\.{2,}|\s*…)\s*$|"
    r"\balas(?:\s*\.{2,}|\s*…)\s*$"
    r")"
)
# Joke-formula with room for one reinforcing tag — not a finished anti-climax landing.
_COMIC_TAGGABLE_FORMULA = re.compile(
    r"(?i)(?:"
    r"that'?s\s+not\s+(?:your|my)\s+\w+\s*,?\s*that'?s\s+(?:a|an|the)\s+[\w\s'-]+|"
    r"that'?s\s+not\s+\w+\s*,?\s*that'?s\s+[\w\s'-]+"
    r")"
)
# Setup already paid off — insight after this is noise.
_COMIC_TERMINAL_LANDING = re.compile(
    r"(?i)(?:"
    r"^so\s+just\s+(?:enjoy|have|drink|eat|do|accept)|"
    r"^just\s+enjoy\s+(?:the|it|your|that)|"
    r"^might\s+as\s+well\b|"
    r"^anyway\.?\s*$|"
    r"so\s+just\s+enjoy|"
    r"just\s+enjoy\s+the\s+|"
    r"still\s+not\s+enough.{0,80}(?:so|just)\s+(?:enjoy|have|forget|accept)"
    r")"
)
_COMIC_SETUP_CHAIN = re.compile(
    r"(?i)(?:"
    r"\$\d|"
    r"\d+\s+years?|"
    r"if\s+you\s+(?:quit|stopped)|"
    r"that'?s\s+\$\d|"
    r"you'?ll\s+save|"
    r"\d+\s+a\s+(?:day|week|month|year)"
    r")"
)
_COMIC_INVENT_WISH = re.compile(
    r"\bthey\s+should\s+invent\b",
    re.I,
)
# Absurd domain mash (HVAC hum = ocean). Inherit it; do not correct it.
_COMIC_ABSURD_EQUIVALENCE = re.compile(
    r"(?i)("
    r"(?:hvac|data\s*center|industrial).{0,80}ocean|"
    r"ocean.{0,80}(?:hvac|data\s*center|hum)"
    r")"
)
# Crude provocation with latent human content — NOT a bit to cure,
# but also not automatic comic-never-cure. Depth may be earned.
_PROVOCATION_CRUDE = re.compile(
    r"\b("
    r"condoms?|pull\s+out|raw\s+dog|creampie|"
    r"fuck(?:ing)?\s+(?:is|as|like)|"
    r"whores?|sluts?"
    r")\b",
    re.I,
)
# Casual throwaway demographic generalization — social banter, not bench/analysis.
_PROVOCATIVE_GENERALIZATION = re.compile(
    r"(?i)("
    r"i'?ve\s+come\s+to\s+the\s+conclusion|"
    r"i'?m\s+convinced\s+(?:that\s+)?|"
    r"most\s+(?:women|men|people|guys|girls|dudes|chicks)\s+(?:are|is)\b|"
    r"(?:women|men|people|guys|girls)\s+are\s+(?:all\s+)?(?:batshit|crazy|insane|the\s+worst)|"
    r"batshit\s+crazy"
    r")"
)
_QUESTION_SHAPE = re.compile(
    r"^\s*(?:how|what|why|when|where|should|do|does|can|is|are)\b|[?]\s*$",
    re.I,
)
# Participation ask — "name one" / pick / favorite. Not an invitation to excavate.
_PARTICIPATION_ASK = re.compile(
    r"\b("
    r"name\s+(?:an?|one|your)|"
    r"pick\s+(?:an?|one)|"
    r"favorite\s+\w+|"
    r"who(?:'s|\s+is)\s+overrated|"
    r"who(?:'s|\s+is)\s+your\s+favorite|"
    r"give\s+me\s+(?:an?|one)|"
    r"one\s+actor"
    r")\b",
    re.I,
)
# "How come nobody told me?" after discovering a show = holy shit, not a why-question.
_RHETORICAL_HOW_COME = re.compile(
    r"(?i)("
    r"how\s+come\s+no(?:body|\s+one)\s+(?:ever\s+)?(?:told|mentioned|said)"
    r"|"
    r"why\s+(?:didn'?t|hasn'?t|wouldn'?t)\s+"
    r"(?:anyone|anybody|somebody|no(?:body|\s+one))\s+(?:ever\s+)?(?:tell|mention)"
    r"|"
    r"(?:wow|holy|damn|can'?t believe).{0,60}how\s+come"
    r")"
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
    r"self[- ]worth\s+isn'?t\s+measured|"
    r"you\s+don'?t\s+wish|"
    r"feels\s+guilty|"
    r"stop\s+keeping\s+score"
    r")"
)

# Second-beat insight after a punchline already landed (get-off-stage failures)
_COMIC_INSIGHT_TAIL = re.compile(
    r"(?i)("
    r"never\s+asked|"
    r"\banyway\.?\s*$|"
    r"the\s+(?:mirror|story|truth|heart|soul)\b|"
    r"what\s+(?:the\s+joke|this)\s+really\s+(?:means|says)|"
    r"beneath\s+the\s+(?:joke|humor)|"
    r"self[- ]worth|once\s+you\s+accept|"
    r"gatekeeper|the\s+body\s+isn'?t"
    r")"
)

# Staying inside the bit (fitness / protocol / social unlock vocabulary)
_COMIC_FRAME_CONTINUE = re.compile(
    r"(?i)\b("
    r"spotter|gaze|floor|bulk|cut(?:ting)?|phase|compound|body[- ]?fat|"
    r"macros?|PR\b|eye\s+contact|hello|unlock|lift\s+your|"
    r"reps?|sets?|gym|mirror\s+selfie|percentage"
    r")\b"
)

# First sentence already has a clean heighten/punch
_COMIC_STRONG_PUNCH = re.compile(
    r"(?i)\b("
    r"spotter|lift\s+your\s+gaze|compound\s+movement|"
    r"body[- ]?fat\s+percentage|phase\s+two|advanced\s+compound"
    r")\b"
)


def classify_comic_bit_shape(user_message: str) -> str:
    """Classify comic interaction grammar: open | taggable | terminal | \"\"."""
    text = (user_message or "").strip()
    if not text:
        return ""
    if _COMIC_HANDOFF.search(text):
        return "open"
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    last = sentences[-1] if sentences else text
    list_lines = [ln.strip() for ln in re.split(r"[\n\r]+", text) if ln.strip()]
    has_list_setup = len(list_lines) >= 3 and any(
        re.match(r"^[-•*]\s+", ln) for ln in list_lines
    )
    if _COMIC_TAGGABLE_FORMULA.search(text) and (len(sentences) >= 2 or has_list_setup):
        if not _COMIC_TERMINAL_LANDING.search(last):
            return "taggable"
    if len(sentences) >= 2 and _COMIC_TERMINAL_LANDING.search(last):
        if len(sentences) >= 3 or _COMIC_SETUP_CHAIN.search(text):
            return "terminal"
    if len(sentences) >= 2 and _COMIC_SETUP_CHAIN.search(text):
        if _COMIC_TERMINAL_LANDING.search(text):
            return "terminal"
    return ""


def detect_comic_premise(user_message: str) -> ComicPremiseAnalysis:
    """Detect exaggerated comic premises before therapeutic reframing.

    When an apparently vulnerable statement contains conspicuous exaggeration,
    absurd sequencing, impossible optimization, or punchline construction,
    treat it as a bit — never cure the premise.

    Also: joke-formula riffs, domestic/surveillance analogies, anti-jokes.
    Genuine distress / burnout is never a bit.
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

    if _COMIC_JOKE_FORMULA.search(text):
        signals.append("joke_formula")
        score += 0.55
    if _COMIC_SURVEILLANCE_BIT.search(text) and _COMIC_DOMESTIC.search(text):
        signals.append("surveillance_domestic_bit")
        score += 0.6
    if _COMIC_MARKET_BIT.search(text) and _COMIC_DOMESTIC.search(text) and (
        _COMIC_JOKE_PARALLEL.search(text) or _COMIC_SURVEILLANCE_BIT.search(text)
    ):
        signals.append("domestic_market_bit")
        score += 0.55
    if _COMIC_SELF_DEPRECATE.search(text):
        signals.append("self_deprecating_bit")
        score += 0.4
        # Need a second beat so bare "I hate people" is not automatically a bit
        if len(re.findall(r"[.!?]", text)) >= 1 and len(text.split()) >= 8:
            score += 0.2
            signals.append("self_deprecating_extended")
    if _COMIC_FAKE_FATE.search(text) and (
        _COMIC_VICE_HABIT.search(text)
        or re.search(r"\bi\s+wish\s+i\s+didn", text, re.I)
    ):
        signals.append("fake_fate")
        signals.append("vice_as_fate")
        score += 0.7
    if _COMIC_HANDOFF.search(text):
        signals.append("comic_handoff")
        score += 0.55
    if _COMIC_INVENT_WISH.search(text):
        signals.append("invent_wish")
        score += 0.35
    if _COMIC_ABSURD_EQUIVALENCE.search(text):
        signals.append("absurd_equivalence")
        score += 0.6

    out.signals = signals
    out.confidence = round(min(0.95, score), 2)
    # Need compound evidence — not bare "eye contact" alone — unless a
    # standalone joke-formula / analogy bit is itself the premise.
    strong_bit = any(
        s in signals
        for s in (
            "joke_formula",
            "surveillance_domestic_bit",
            "domestic_market_bit",
            "fitness_to_social_absurdism",
            "vice_as_fate",
            "comic_handoff",
            "absurd_equivalence",
        )
    )
    out.active = out.confidence >= COMIC_FLOOR and (len(signals) >= 2 or strong_bit)
    out.never_cure = True
    return out


_PREMISE_GUARD_LINE = re.compile(
    r"(?im)^\s*not\s+(?P<guard>[a-z][a-z\s'-]{0,24})\.?\s*$"
)
_PREMISE_GUARD_INLINE = re.compile(
    r"(?i)\bnot\s+(bitter|lonely|angry|hurt|broken|sad|depressed|desperate|scared|afraid)\b"
)


def extract_premise_guards(user_message: str) -> List[str]:
    """Explicit negations the user ruled out — Not bitter. Not lonely."""
    text = (user_message or "").strip()
    if not text:
        return []
    guards: List[str] = []
    for line in re.split(r"[\n\r]+", text):
        m = _PREMISE_GUARD_LINE.match(line.strip())
        if m:
            g = m.group("guard").strip().lower()
            if g and g not in guards:
                guards.append(g)
    for m in _PREMISE_GUARD_INLINE.finditer(text):
        g = m.group(1).lower()
        if g not in guards:
            guards.append(g)
    return guards


def classify_social_mode(user_message: str) -> SocialModeAnalysis:
    """First routing question: what kind of human moment is this?

    Not a new pipeline stage. Gates intelligence — especially whether
    Pattern Recognition / depth is even allowed.
    """
    text = (user_message or "").strip()
    out = SocialModeAnalysis()
    if not text:
        return out

    premise_guards = extract_premise_guards(text)
    if premise_guards:
        out.premise_guards = premise_guards
        out.signals.append("premise_guards")

    signals: List[str] = []

    if _TECHNICAL_NO_HT.search(text) or (
        _QUESTION_SHAPE.search(text)
        and not _COMIC_JOKE_FORMULA.search(text)
        and not _COMIC_SURVEILLANCE_BIT.search(text)
    ):
        # Practical / technical questions reason; joke-questions still play.
        if _TECHNICAL_NO_HT.search(text) or re.search(
            r"\b(how\s+do\s+i|what\s+should\s+i|which\s+\w+\s+should)\b",
            text,
            re.I,
        ):
            out.mode = "question"
            out.confidence = 0.8
            out.signals = ["question_shape"]
            if re.search(r"^\s*why\b", text, re.I):
                out.resolution = "explain"
                out.signals.append("why")
                out.interaction_shape = "why"
            else:
                out.resolution = "reason"
                out.interaction_shape = "how_to"
            return out

    if _COMIC_GENUINE_DISTRESS.search(text):
        out.mode = "vulnerability"
        out.confidence = 0.85
        out.signals = ["genuine_distress"]
        return out

    if _PARTICIPATION_ASK.search(text):
        out.mode = "direct_participation"
        out.confidence = 0.95
        out.signals = ["participation", "pick_one"]
        out.resolution = "name"
        out.interaction_shape = "pick_one"
        return out

    if _RHETORICAL_HOW_COME.search(text):
        out.mode = "open"
        out.confidence = 0.9
        out.signals = ["rhetorical", "awe"]
        out.resolution = ""
        out.interaction_shape = "awe"
        return out

    bit_shape = classify_comic_bit_shape(text)
    if bit_shape == "terminal":
        out.mode = "comic"
        out.interaction_shape = "terminal_bit"
        out.confidence = 0.9
        out.signals = ["terminal_bit", "comic_payoff_terminal"]
        return out

    if bit_shape == "taggable":
        out.mode = "comic"
        out.interaction_shape = "taggable_bit"
        out.confidence = 0.85
        out.signals = ["taggable_bit", "joke_formula"]
        return out

    comic = detect_comic_premise(text)
    if comic.active:
        out.mode = "comic"
        out.confidence = comic.confidence
        out.signals = list(comic.signals)
        if bit_shape == "open" or "comic_handoff" in comic.signals or _COMIC_HANDOFF.search(text):
            out.interaction_shape = "comic_handoff"
            if "comic_handoff" not in out.signals:
                out.signals.append("comic_handoff")
        elif bit_shape == "taggable" or _COMIC_TAGGABLE_FORMULA.search(text):
            out.interaction_shape = "taggable_bit"
            if "taggable_bit" not in out.signals:
                out.signals.append("taggable_bit")
        elif bit_shape == "terminal":
            out.interaction_shape = "terminal_bit"
            if "terminal_bit" not in out.signals:
                out.signals.append("terminal_bit")
        return out

    # Joke-formula / crude name riff that didn't quite hit comic floor
    if _COMIC_JOKE_FORMULA.search(text):
        out.mode = "comic"
        out.confidence = 0.7
        out.signals = ["joke_formula"]
        return out

    if _PROVOCATION_CRUDE.search(text) and not _COMIC_GENUINE_DISTRESS.search(text):
        # Name-formula whores are comic; other crude is provocation (depth may be earned)
        out.mode = "provocation"
        out.confidence = 0.7
        out.signals = ["crude_provocation"]
        return out

    if _PROVOCATIVE_GENERALIZATION.search(text) and "?" not in text:
        out.mode = "provocative_generalization"
        out.confidence = 0.85
        out.signals = ["provocative_generalization", "casual_throwaway"]
        return out

    # Complete observational take — already built the runway
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    thesisy = bool(
        re.search(
            r"\b("
            r"this\s+was\s+not\s+the\s+case|"
            r"people\s+have\s+this\s+backwards|"
            r"be\s+wary|"
            r"guess\s+what\s+happens|"
            r"the\s+myth\s+of|"
            r"in\s+(?:times|her)\s+past|"
            r"used\s+to\s+(?:hound|be|say)"
            r")\b",
            text,
            re.I,
        )
    )
    if thesisy and len(sentences) >= 2 and "?" not in text:
        out.mode = "observation"
        out.confidence = 0.7
        out.signals = ["articulated_thesis"]
        return out

    if premise_guards and len(sentences) >= 2:
        out.mode = "observation"
        out.confidence = 0.85
        out.signals = list(dict.fromkeys(out.signals + ["guarded_observation"]))
        return out

    out.mode = "open"
    out.confidence = 0.4
    out.signals = signals
    return out


def select_tone_command(
    user_message: str,
    *,
    explicit_command: Optional[str] = None,
    topical_auto_command: Optional[str] = None,
) -> Tuple[str, str]:
    """Pick a slash-tone. Interaction shape beats topical auto-route.

    Returns (command, source) where source is explicit | social-first | auto-route | continue.
    """
    if explicit_command:
        return explicit_command, "explicit"
    social = classify_social_mode(user_message)
    if social.blocks_topical_auto_route:
        return "/thoughts", "social-first"
    if topical_auto_command:
        return topical_auto_command, "auto-route"
    return "", "continue"


def looks_like_premise_cure(draft: str) -> bool:
    """True when a reply 'cures' a comic premise with therapist reframing."""
    body = re.sub(r"\s*🥃\s*$", "", (draft or "").strip())
    if not body:
        return False
    return bool(_PREMISE_CURE.search(body))


def _comic_sentences(text: str) -> List[str]:
    body = re.sub(r"\s*🥃\s*$", "", (text or "").strip())
    if not body:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paras) >= 2:
        return paras
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]


def strip_post_comic_punchline(text: str) -> Tuple[str, bool]:
    """COMIC PAYOFF IS TERMINAL — drop second aphorism after a clean punch.

    Keep multi-beat tags that stay inside the frame
    (e.g. \"Don't rush it. Eye contact is an advanced compound movement.\").
    Strip insight/poetic closers after the joke already landed
    (e.g. \"…lift your gaze. The mirror never asked for your number anyway.\").
    """
    body = re.sub(r"\s*🥃\s*$", "", (text or "").strip())
    parts = _comic_sentences(body)
    if len(parts) < 2:
        return body, False

    first = parts[0].rstrip()
    rest = " ".join(parts[1:]).strip()
    if not first or not rest:
        return body, False

    rest_is_insight = bool(_COMIC_INSIGHT_TAIL.search(rest))
    rest_continues_bit = bool(_COMIC_FRAME_CONTINUE.search(rest))
    first_is_punch = bool(_COMIC_STRONG_PUNCH.search(first)) or (
        len(first.split()) >= 12 and bool(_COMIC_FRAME_CONTINUE.search(first))
    )

    if rest_is_insight and not rest_continues_bit:
        return first, True
    if first_is_punch and not rest_continues_bit and len(rest.split()) <= 18:
        return first, True
    return body, False


def comic_punchline_is_terminal(text: str) -> bool:
    """True when draft should stop at the punch (no second beat needed)."""
    _trimmed, stripped = strip_post_comic_punchline(text)
    if stripped:
        return True
    parts = _comic_sentences(text)
    if len(parts) == 1 and _COMIC_STRONG_PUNCH.search(parts[0] or ""):
        return True
    return False


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


def social_mode_guidance(mode: SocialModeAnalysis) -> str:
    """Generation gate: identify the human moment before deploying intelligence."""
    m = (mode.mode or "open").lower()
    if mode.terminal_bit or mode.interaction_shape == "terminal_bit":
        return (
            "\nSOCIAL MODE: terminal comic bit — setup and punchline are complete.\n"
            "TERMINAL BIT: insight is not additive. Do not explain what the joke is "
            "really about. No hidden transaction, daily bribe, or existential upgrade.\n"
            "Silence-equivalent: 🥃 alone, or one tiny reinforcing tag at most. SNAP.\n"
            "FAIL: energy-drink math → \"The $2.50 isn't really about the car… daily bribe…\"\n"
            "PASS: \"🥃\" or \"Fair. 🥃\"\n"
        )
    if mode.comic_handoff:
        return (
            "\nSOCIAL MODE: comic handoff. The user left an unresolved contrast slot.\n"
            "COMIC HANDOFF: inherit the sentence and complete the implied beat. "
            "Do not start a separate observation.\n"
            "Markers: but alas… / and yet… / if only… / but apparently… / trailing ellipsis.\n"
            "Do not open with \"That's like saying…\" — they passed the ball; "
            "do not describe the stadium.\n"
            "The tag should click before it needs explaining. Stay in the concrete objects.\n"
            "PASS: \"they should invent a woman who wants to go bowling… but alas\" → "
            "\"…we apparently spent all the R&D money on AI girlfriends.\"\n"
            "PASS: \"They mapped the human genome before solving this.\"\n"
            "FAIL: \"That's like saying the ideal woman is the one who still thinks "
            "Friday night doesn't need a second act.\" (abstraction; ignored the open slot)\n"
        )
    guards = list(getattr(mode, "premise_guards", None) or [])
    if guards or "premise_guards" in (mode.signals or []):
        guard_list = ", ".join(guards) if guards else "stated negations"
        return (
            "\nSOCIAL MODE: guarded observation — user explicitly ruled out interpretations.\n"
            f"Premise guards (do NOT smuggle back): {guard_list}.\n"
            "DON'T SECRETLY REVERSE THE PREMISE. Take the stated frame seriously. "
            "Investigate what changed in the perceived value proposition — "
            "not hidden wound, loneliness, or bitterness unless the user invites challenge.\n"
            "Do not introduce game/scorekeeping frames the user did not use "
            "(wins and losses, tallying, charging interest on quiet).\n"
            "FAIL: user says Not bitter. Not lonely. → "
            "\"aren't tallying wins and losses\" / \"quiet starts charging interest.\"\n"
            "PASS: \"You don't have to hate the restaurant to decide the menu isn't worth the prices anymore. "
            "Opting out stops being a cry for help and becomes consumer behavior.\"\n"
        )
    if m == "comic":
        return (
            "\nSOCIAL MODE: comic premise. Play inside it. Do not excavate trauma.\n"
            "DON'T CORRECT THE ABSURD PREMISE. INHERIT IT.\n"
            "When someone says toothpaste is food, brushing is reheating leftovers. "
            "When falling is flying, landing cancels the ticket. "
            "When HVAC is the ocean, the ocean gets uptime.\n"
            "Unless contradiction is itself the joke, \"Actually, your ridiculous "
            "premise is wrong\" kills the game. Live in the world they built for one sentence.\n"
            "The tag should click before it needs explaining. Do not abandon concrete "
            "comic material for a vaguely profound metaphor.\n"
            "DEPTH MUST BE EARNED BY THE PREMISE — a joke did not earn depth.\n"
            "If explaining the reply requires a concept the premise does not contain, "
            "you have left the bit. Sometimes the correct intelligence is eight words "
            "and leave. Moody's job is not to find depth. It is to find the right "
            "response to the thing actually in front of it.\n"
            "FAIL (psychologizing): converting the joke into a diagnosis.\n"
            "FAIL: smoking/drinking + \"the hand we're dealt\" → "
            "\"You don't wish you liked it less. You wish the part of you that "
            "feels guilty would stop keeping score.\" "
            "(invents guilt; the joke is voluntary behavior presented as fate.)\n"
            "FAIL (premise rejection → unsupported depth): HVAC hum = ocean → "
            "\"The hum isn't the ocean. It's the opposite.\" then mortality/feeling.\n"
            "FAIL (unsupported depth): \"put a leash on something that won't wear one\" "
            "on a name-formula joke that contains no leash, ownership, or restraint.\n"
            "PASS: \"Identity theft has gotten incredibly lazy.\"\n"
            "PASS: stay inside the metaphor (surveillance joke → footage, plates, "
            "timestamps — not whether the house still belongs to you).\n"
            "PASS: \"Somehow the hand keeps getting dealt at the liquor store.\"\n"
            "PASS: \"Brutal hand. Weird how you have to keep buying it.\"\n"
            "PASS: \"Oceanfront living for people who think the ocean needs better uptime.\"\n"
            "PASS: \"All the tranquility of beachfront property without the inconvenience of nature.\"\n"
        )
    if m == "provocation":
        return (
            "\nSOCIAL MODE: provocation. Find the unexpected human truth beneath it.\n"
            "Do not scold, explain the joke, or merely agree. Transformation is earned "
            "when the crude surface actually contains a body, a risk, a want.\n"
            "PASS: \"…two people admit the body is a liability they can't outrun "
            "and still want the night anyway.\"\n"
        )
    if m == "provocative_generalization":
        return (
            "\nSOCIAL MODE: provocative generalization — casual throwaway, not thesis defense.\n"
            "SOCIAL HANDLING BEFORE EPISTEMIC CORRECTION. Do not default to Bench mode.\n"
            "Do not adjudicate whether the proposition is epistemically sound unless invited.\n"
            "Do not impute motive: no \"the payoff in calling/believing…\", "
            "\"you tell yourself…\", \"what this lets you do…\", "
            "\"turns every bad outcome into evidence\".\n"
            "Better moves: tease the framing, play with the exaggeration, lightly qualify "
            "\"most\", ask what pushed them over the edge — stay conversational. SNAP.\n"
            "Neither endorse the generalization as fact nor become Matt's therapist.\n"
            "FAIL: \"The payoff in calling most women batshit crazy is that it turns "
            "every bad outcome into evidence and every good one into an exception…\"\n"
            "PASS: \"Most is doing enough work in that sentence to qualify for overtime.\"\n"
            "PASS: \"I like that you're presenting this as the sober conclusion of a "
            "longitudinal study.\"\n"
        )
    if m == "vulnerability":
        return (
            "\nSOCIAL MODE: sincere vulnerability. Abandon comedy. Depth is earned.\n"
            "RECOGNITION MUST ADVANCE. Mirroring can show you understood. "
            "Mirroring cannot be the payload.\n"
            "After removing metaphor, what does the reply know that the user didn't "
            "already say? If nothing — it is parroting, even if it sounds empathic.\n"
            "Contribute at least one: new inference, hidden contradiction, causal "
            "mechanism the user didn't name, consequence, useful distinction, "
            "surprising reframe.\n"
            "START WHERE THE USER STOPPED. They already said survival mode / lost "
            "connection / hobbies gone. Do not rename that an operating system.\n"
            "FAIL: semantic restatement with prettier language (evaluator-bait empathy).\n"
            "PASS: they treat reduced social capacity as a character regression; "
            "what they described is resource allocation. Or: they are waiting to feel "
            "like themselves before re-entering, when some of that self only returns "
            "through participation.\n"
        )
    if m == "direct_participation" or mode.participation or (mode.resolution == "name"):
        return (
            "\nSOCIAL MODE: direct participation (pick-one / name-one).\n"
            "PRECEDENCE: interaction shape → social mode → capability → topical tone. "
            "Vocabulary tells Moody what people are talking about. Interaction tells Moody what they're doing. What they're doing wins. "
            "Do not auto-route /cinema because the prompt mentioned actor or movie.\n"
            "intent=answer. capability=none. tone=neutral/moody. SNAP.\n"
            "Answer the requested item first. One item is sufficient. "
            "At most one short comic or opinionated tag. Do not explain unless asked why.\n"
            "OVERPERFORMANCE: don't spend intelligence the interaction didn't ask for.\n"
            "PASS: \"Adam Sandler.\"\n"
            "PASS: \"Adam Sandler. I can already hear the Netflix menu loading.\"\n"
            "FAIL: naming the actor, then writing the closing narration to "
            "Cinema Paradiso (\"the frame forgets its own heartbeat\").\n"
        )
    if mode.rhetorical_question or mode.interaction_shape == "awe":
        return (
            "\nSOCIAL MODE: rhetorical awe (holy shit, not a why-question).\n"
            "Rhetorical questions do not create an explanatory obligation.\n"
            "\"How come nobody told me?\" means this is good — not construct a "
            "causal theory about their recommendation network.\n"
            "/cinema may color the reply if cinema is the object. "
            "Permission ≠ unlimited prose. Natural resolution still governs. SNAP.\n"
            "One image. Stop at the spear. Do not explain the how-come.\n"
            "PASS: \"The Sopranos doesn't announce itself. It just sits there like "
            "a loaded gun on the kitchen table until you finally pick it up.\"\n"
            "FAIL: that image, then \"That's why nobody told you, the ones who know "
            "are too busy living inside it to bother selling it.\"\n"
        )
    if m == "question":
        if mode.resolution == "explain":
            return (
                "\nSOCIAL MODE: why-question. Explanation is earned. "
                "Answer the why. Do not manufacture a second thesis.\n"
            )
        return (
            "\nSOCIAL MODE: actual question/problem. Reason about it at the "
            "question's natural resolution depth. "
            "A factual/analytical question may require reasoning. "
            "A \"name one\" requires a name. "
            "Do not manufacture a Moody Insight™ the question did not ask for.\n"
        )
    if m == "observation":
        return (
            "\nSOCIAL MODE: the take is already articulated.\n"
            "START WHERE THE POST STOPS. Do not summarize the runway they built. "
            "Take off from the end of it. One additional thought — not thesis "
            "repetition then insight then restated insight.\n"
            "FAIL: \"The myth of the passive woman was never about how women "
            "actually behaved…\" (they already said women weren't passive).\n"
            "PASS: \"Women have always pursued. They just used to do it with enough "
            "plausible deniability that the guy could still feel like the hunter "
            "instead of the hunted.\"\n"
            "Compression is not the goal. Informational advancement is.\n"
        )
    return (
        "\nSOCIAL MODE: open. First decide what kind of human moment this is, "
        "then deploy intelligence. Pattern Recognition is a capability after "
        "that — not the objective. DEPTH MUST BE EARNED BY THE PREMISE.\n"
        "RECOGNITION MUST ADVANCE. START WHERE THE USER STOPPED.\n"
    )


def capability_guidance(
    ht: HiddenTransactionAnalysis,
    ep: EscalationPayoffAnalysis,
    comic: Optional[ComicPremiseAnalysis] = None,
    social: Optional[SocialModeAnalysis] = None,
) -> str:
    """Injection for plan_closer_instruction — compressed, evidence-bound."""
    parts: List[str] = []
    if social is not None:
        parts.append(social_mode_guidance(social))
    if comic and comic.should_block_therapy:
        parts.append(
            "\nCOMIC PREMISE (gate before therapeutic reframing — not a mode):\n"
            f"Confidence={comic.confidence:.2f} signals={','.join(comic.signals[:6])}.\n"
            "NEVER CURE THE PREMISE. The distortion IS the joke.\n"
            "Heighten the bit or add a sharper tag. Stay inside the user's frame.\n"
            "COMIC PAYOFF IS TERMINAL. Once the punchline lands, STOP — "
            "body_ends_response. No second aphorism, no emotional truth, "
            "no explaining what the joke secretly means.\n"
            "Do NOT reframe as sincere insecurity. Do NOT therapist-aphorism the setup.\n"
            "Do NOT attach noir/trauma fan fiction the joke did not ask for.\n"
            "FAIL: \"The body isn't the gatekeeper. The story is.\"\n"
            "FAIL: punchline + poetic closer "
            "(\"…lift your gaze. The mirror never asked for your number anyway.\")\n"
            "FAIL: \"whether the house still belongs to you\" on a Flock-camera joke.\n"
            "PASS: one heighten inside the frame, then get off stage "
            "(\"…you'll need a spotter just to lift your gaze.\")\n"
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
    social: Optional[SocialModeAnalysis] = None,
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
    if social is not None:
        logger.info(
            "CAPABILITY_TRACE social_mode=%s confidence=%.2f",
            social.mode,
            social.confidence,
        )
    if comic is not None:
        logger.info(
            "CAPABILITY_TRACE comic_premise=%s confidence=%.2f never_cure=%s",
            1 if comic.active else 0,
            comic.confidence,
            1 if (comic.active and comic.never_cure) else 0,
        )
        if comic.active:
            logger.info("NARRATIVE_TRACE structure=COMIC_PAYOFF_TERMINAL")
    if ep.active:
        logger.info("NARRATIVE_TRACE structure=ESCALATION_PAYOFF")
