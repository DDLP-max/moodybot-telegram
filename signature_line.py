# -*- coding: utf-8 -*-
"""Signature Line Engine — the sentence the reader remembers tomorrow.

MoodyBot is a writer. The last sentence is a first-class writing object.

It is NOT a closer.
It is NOT a CTA.
It is NOT a summary.
It is the fingerprint left behind after the body releases its tension.

Recognition Callback / Action / Silence are alternate endings.
Signature Line is the preferred landing for analysis, criticism, and pattern work.

generate_signature_line(plan, draft) runs AFTER the body exists.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

MAX_WORDS = 18
MAX_WORDS_EXCEPTIONAL = 22
MIN_WORDS = 4

_RECENT_SIGNATURES: Deque[str] = deque(maxlen=32)

ENGAGEMENT_MARKERS = (
    "do you want",
    "would you like",
    "let me know",
    "say the word",
    "does that make sense",
    "what do you think",
    "tell me more",
    "feel free",
    "reach out",
    "subscribe",
    "@moodybot",
    "tag me",
)

SUMMARY_MARKERS = (
    "in other words",
    "to summarize",
    "to sum up",
    "in summary",
    "basically",
    "all in all",
    "the bottom line is",
    "what this means is",
    "as i said",
    "as mentioned",
    "to put it simply",
)

# Fortune-cookie / slogan factory — instant fail (SPECIFICITY)
GENERIC_APHORISMS = (
    "everything happens for a reason",
    "life is complicated",
    "truth always wins",
    "power corrupts",
    "trust the process",
    "you got this",
    "stay strong",
    "believe in yourself",
    "it is what it is",
    "live your truth",
    "time heals all wounds",
    "what doesn't kill you",
    "follow your heart",
    "be yourself",
    "knowledge is power",
    "love conquers all",
    "change is hard",
    "people are complex",
    "nothing is black and white",
    "the truth hurts",
)

AI_PROFOUND_MARKERS = (
    "in a world where",
    "at the end of the day",
    "the reality is that",
    "it's important to remember",
    "one thing is clear",
    "this serves as a reminder",
    "a powerful reminder",
    "speaks volumes",
    "more than meets the eye",
    "the human condition",
)


@dataclass
class SignatureQuality:
    specificity: bool = False
    compression: bool = False
    authorship: bool = False
    inevitability: bool = False
    memory: bool = False
    reasons: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(
            (
                self.specificity,
                self.compression,
                self.authorship,
                self.inevitability,
                self.memory,
            )
        )

    def as_dict(self) -> Dict[str, str]:
        return {
            "specificity": str(self.specificity).lower(),
            "compression": str(self.compression).lower(),
            "authorship": str(self.authorship).lower(),
            "inevitability": str(self.inevitability).lower(),
            "memory": str(self.memory).lower(),
            "fail_reasons": ",".join(self.reasons),
        }


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_single_sentence(text: str) -> bool:
    s = (text or "").strip()
    if not s or s[-1] not in ".!":
        return False
    body = s[:-1]
    if "?" in body or "!" in body:
        return False
    if "." in body:
        return False
    return True


def _content_tokens(text: str) -> set:
    stop = {
        "the", "and", "for", "that", "this", "with", "from", "about", "have",
        "what", "when", "where", "which", "your", "you", "how", "did", "does",
        "are", "was", "were", "been", "into", "than", "then", "just", "like",
        "not", "but", "its", "it's", "they", "them", "their", "our", "out",
        "all", "any", "can", "could", "would", "should", "will", "been",
    }
    return {
        t
        for t in re.findall(r"[a-z0-9']+", _norm(text))
        if len(t) > 2 and t not in stop
    }


def is_single_sentence_ok(text: str) -> bool:
    return is_single_sentence(text)


# ---------------------------------------------------------------------------
# Quality tests — the sentence the user remembers tomorrow
# ---------------------------------------------------------------------------


def test_specificity(line: str, conversation_tokens: set) -> Tuple[bool, str]:
    """Could this appear after 100 unrelated answers? If yes: FAIL."""
    lower = _norm(line)
    for aphorism in GENERIC_APHORISMS:
        if aphorism in lower or lower.rstrip(".!") == aphorism:
            return False, "generic_aphorism"
    # Extremely abstract with no conversation contact
    line_toks = _content_tokens(line)
    if conversation_tokens and line_toks:
        overlap = line_toks & conversation_tokens
        # Allow literary compression that keeps at least one concrete hinge
        # OR strong structural turn words with concrete nouns
        concrete = {t for t in line_toks if t not in {
            "moment", "argument", "story", "truth", "power", "people", "life",
            "world", "thing", "things", "always", "never", "often", "usually",
        }}
        if not overlap and not concrete:
            return False, "no_conversation_hinge"
    return True, "ok"


def test_compression(line: str, body: str) -> Tuple[bool, str]:
    """Does it reduce the response into a sharper insight — not repeat it?"""
    if any(m in _norm(line) for m in SUMMARY_MARKERS):
        return False, "mechanical_summary"
    if not body:
        return True, "ok"
    line_n = _norm(line)
    sentences = [
        _norm(s)
        for s in re.split(r"(?<=[.!?])\s+", body.strip())
        if s.strip() and not s.strip().endswith("?")
    ]
    if not sentences:
        return True, "ok"
    # Exact echo of a body sentence fails (unless isolating it as the last line)
    # High overlap with the immediately previous sentence fails
    prev = sentences[-1]
    if line_n == prev:
        return True, "ok"  # promoting the body's own landing sentence is compression
    line_toks = _content_tokens(line)
    prev_toks = _content_tokens(prev)
    if line_toks and prev_toks:
        overlap = len(line_toks & prev_toks) / max(len(line_toks), 1)
        if overlap >= 0.85 and word_count(line) >= word_count(prev) * 0.9:
            return False, "repeats_previous"
    # Must be shorter or equal sharpness vs average body sentence
    if sentences and word_count(line) > 22:
        return False, "not_compressed"
    return True, "ok"


def test_authorship(line: str) -> Tuple[bool, str]:
    """Writer, not AI trying to sound profound."""
    lower = _norm(line)
    if any(m in lower for m in ENGAGEMENT_MARKERS):
        return False, "engagement"
    if any(m in lower for m in AI_PROFOUND_MARKERS):
        return False, "ai_profound"
    if any(m in lower for m in GENERIC_APHORISMS):
        return False, "slogan"
    if lower.startswith(("so,", "so ", "look,", "well,", "anyway,", "remember,")):
        return False, "chat_opener"
    # Stacked abstractions without verbs of change feel manufactured
    if re.search(r"\b(journey|empower|vibrant|delve|tapestry|landscape of)\b", lower):
        return False, "ai_thesaurus"
    return True, "ok"


def test_inevitability(line: str, body: str, conversation_tokens: set) -> Tuple[bool, str]:
    """After the body, does this feel like the sentence that had to come next?"""
    line_toks = _content_tokens(line)
    if not line_toks:
        return False, "empty_tokens"
    pool = _content_tokens(body) | conversation_tokens
    if not pool:
        return True, "ok"
    overlap = line_toks & pool
    # Literary turn can earn inevitability with one shared hinge or body imagery
    has_turn = bool(
        re.search(
            r"\b(but|becomes?|before|after|where|when|don't|doesn't|isn't|"
            r"stops?|started|reveals?|explains?|pretending|usually|already|"
            r"never|only|without|instead|rarely|needs?|runs?\s+out)\b",
            _norm(line),
        )
    )
    if overlap:
        return True, "ok"
    if has_turn and word_count(line) <= 12:
        return True, "ok"
    return False, "not_earned_by_body"


def test_memory(line: str) -> Tuple[bool, str]:
    """Would someone screenshot this?"""
    wc = word_count(line)
    if wc < MIN_WORDS or wc > MAX_WORDS_EXCEPTIONAL:
        return False, "bad_length"
    if not is_single_sentence(line):
        return False, "not_one_sentence"
    if line.strip().endswith("?"):
        return False, "question"
    # Short punch OR clear turn
    if wc <= 10:
        return True, "ok"
    has_turn = bool(
        re.search(
            r"\b(but|becomes?|before|after|where|when|don't|doesn't|"
            r"stops?|started|reveals?|explains?|pretending|usually|"
            r"already|never|only|without|instead|rarely|needs?)\b",
            _norm(line),
        )
    )
    return (True, "ok") if has_turn else (False, "no_residue")


def score_signature_line(
    line: str,
    *,
    body: str = "",
    user_message: str = "",
    anchors: Optional[List[str]] = None,
    central_insight: str = "",
) -> SignatureQuality:
    conversation_tokens = (
        _content_tokens(user_message)
        | _content_tokens(central_insight)
        | _content_tokens(" ".join(anchors or []))
        | _content_tokens(body)
    )
    q = SignatureQuality()
    ok, reason = test_specificity(line, conversation_tokens)
    q.specificity = ok
    if not ok:
        q.reasons.append(f"specificity:{reason}")
    ok, reason = test_compression(line, body)
    q.compression = ok
    if not ok:
        q.reasons.append(f"compression:{reason}")
    ok, reason = test_authorship(line)
    q.authorship = ok
    if not ok:
        q.reasons.append(f"authorship:{reason}")
    ok, reason = test_inevitability(line, body, conversation_tokens)
    q.inevitability = ok
    if not ok:
        q.reasons.append(f"inevitability:{reason}")
    ok, reason = test_memory(line)
    q.memory = ok
    if not ok:
        q.reasons.append(f"memory:{reason}")
    return q


def validate_signature_line(
    text: str,
    *,
    body: str = "",
    user_message: str = "",
    anchors: Optional[List[str]] = None,
    central_insight: str = "",
    allow_exceptional_length: bool = False,
    check_novelty: bool = True,
) -> Tuple[bool, str]:
    """Hard gate. Returns (ok, reason)."""
    s = (text or "").strip()
    if not s:
        return False, "REJECTED:empty"
    if s.endswith("?"):
        return False, "REJECTED:question"
    if not is_single_sentence(s):
        return False, "REJECTED:not_one_sentence"
    wc = word_count(s)
    limit = MAX_WORDS_EXCEPTIONAL if allow_exceptional_length else MAX_WORDS
    if wc > limit:
        return False, "REJECTED:too_long"
    if wc < MIN_WORDS:
        return False, "REJECTED:too_short"
    if check_novelty and _norm(s) in _RECENT_SIGNATURES:
        return False, "REJECTED:slogan_reuse"
    quality = score_signature_line(
        s,
        body=body,
        user_message=user_message,
        anchors=anchors,
        central_insight=central_insight,
    )
    if not quality.ok:
        return False, "REJECTED:" + (quality.reasons[0] if quality.reasons else "quality")
    return True, "ok"


def remember_signature_line(text: str) -> None:
    n = _norm(text)
    if n:
        _RECENT_SIGNATURES.append(n)


def _plan_fields(plan: Any) -> Dict[str, Any]:
    if plan is None:
        return {}
    if isinstance(plan, dict):
        return plan
    return {
        "central_insight": getattr(plan, "central_insight", None) or "",
        "original_subject": getattr(plan, "original_subject", None) or "",
        "primary_capability": getattr(plan, "primary_capability", None) or "",
        "intervention": getattr(plan, "intervention", None) or "",
        "expected_shift_from": getattr(plan, "expected_shift_from", None) or "",
        "expected_shift_to": getattr(plan, "expected_shift_to", None) or "",
        "anchors": list(getattr(plan, "anchors", None) or []),
        "intent": getattr(plan, "intent", None) or "",
        "selected_command": getattr(plan, "selected_command", None) or "",
    }


def signature_line_appropriate(plan: Any, user_message: str = "") -> bool:
    """Preferred for analysis / criticism / pattern / psychology / politics."""
    fields = _plan_fields(plan)
    intent = (fields.get("intent") or "").lower()
    if intent in {"witness", "technical", "clarify", "action"}:
        return False
    if fields.get("needs_practical_action"):
        return False
    cmd = (fields.get("selected_command") or "").lower()
    if cmd in {"/ghost", "/numb", "/roast", "/savage", "/cut"}:
        return False
    um = (user_message or "").lower()
    if any(
        p in um
        for p in ("what should i do", "what do i say", "how should i handle", "what now")
    ):
        return False
    # Default yes for substantial analytic modes
    return True


def last_line_is_signature(
    text: str,
    *,
    user_message: str = "",
    anchors: Optional[List[str]] = None,
    central_insight: str = "",
) -> bool:
    paras = re.split(r"\n\s*\n", (text or "").strip())
    last = (paras[-1] if paras else "").strip()
    body = "\n\n".join(paras[:-1]) if len(paras) > 1 else ""
    ok, _ = validate_signature_line(
        last,
        body=body,
        user_message=user_message,
        anchors=anchors,
        central_insight=central_insight,
        check_novelty=False,
    )
    return ok


def extract_signature_from_body(
    body: str,
    *,
    user_message: str = "",
    anchors: Optional[List[str]] = None,
    central_insight: str = "",
) -> Optional[str]:
    """Discover a last sentence already living inside the draft."""
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", (body or "").strip())
        if s.strip() and not s.strip().endswith("?")
    ]
    best: Optional[str] = None
    for s in reversed(sentences):
        others = " ".join(x for x in sentences if x != s)
        ok, _ = validate_signature_line(
            s,
            body=others,
            user_message=user_message,
            anchors=anchors,
            central_insight=central_insight,
            allow_exceptional_length=True,
            check_novelty=False,
        )
        if ok:
            best = s
            break
    return best


def _compress_candidate(
    sentence: str,
    *,
    user_message: str = "",
    body: str = "",
    anchors: Optional[List[str]] = None,
    central_insight: str = "",
) -> Optional[str]:
    s = (sentence or "").strip()
    if not s:
        return None
    candidates = []
    for sep in (" — ", " - ", ": ", "; "):
        if sep in s:
            right = s.split(sep)[-1].strip()
            if not right.endswith((".", "!")):
                right += "."
            candidates.append(right)
    trimmed = re.sub(
        r"\s+(?:because|since|which|that|when)\b.+$",
        ".",
        s,
        count=1,
        flags=re.IGNORECASE,
    )
    if trimmed != s:
        if not trimmed.endswith((".", "!")):
            trimmed = trimmed.rstrip(",;:") + "."
        candidates.append(trimmed)
    for c in candidates:
        ok, _ = validate_signature_line(
            c,
            body=body,
            user_message=user_message,
            anchors=anchors,
            central_insight=central_insight,
            allow_exceptional_length=True,
            check_novelty=True,
        )
        if ok:
            return c
    return None


def _conversation_conditioned_line(
    user_message: str,
    plan_fields: Dict[str, Any],
    body: str,
) -> Optional[str]:
    """Last-resort lines that still hinge on THIS conversation — not slogans."""
    um = (user_message or "").lower()
    insight = (plan_fields.get("central_insight") or "").lower()
    subject = (plan_fields.get("original_subject") or "").lower()
    blob = f"{um} {insight} {subject} {_norm(body)}"

    bank = [
        (
            ("feminist", "feminism", "praising", "pick me", "loyalty", "equality"),
            (
                "The moment gratitude becomes betrayal, the argument stopped being about equality.",
                "The script usually survives by making disagreement feel like betrayal.",
                "The moment gratitude needs permission, the argument changed.",
            ),
        ),
        (
            ("boundary", "boundaries"),
            ("Boundaries rarely end relationships — they reveal them.",),
        ),
        (
            ("story", "narrative", "defending", "women"),
            (
                "The story started defending itself long before it started defending people.",
                "The story started defending itself long before it started defending women.",
            ),
        ),
        (
            ("power", "control", "authority"),
            ("Power usually announces itself by pretending it doesn't exist.",),
        ),
        (
            ("backstage", "behind the scenes"),
            ("The backstage explains the stage.",),
        ),
        (
            ("paper trail", "receipts", "evidence", "emails", "performance"),
            ("The paper trail is where the performance runs out.",),
        ),
        (
            ("dirty talk", "porn", "1995", "sexual language", "script"),
            ("The script library grew — the language only followed.",),
        ),
        (
            ("cancel", "late at night", "low priority", "only calls"),
            ("Convenience dressed as connection is still just convenience.",),
        ),
        (
            ("doorman", "flowers", "wine"),
            ("The move is clear — the next line is hers.",),
        ),
    ]
    for keys, lines in bank:
        if any(k in blob for k in keys):
            for line in lines:
                if _norm(line) in _RECENT_SIGNATURES:
                    continue
                ok, _ = validate_signature_line(
                    line,
                    body=body,
                    user_message=user_message,
                    anchors=list(plan_fields.get("anchors") or []),
                    central_insight=plan_fields.get("central_insight") or "",
                    allow_exceptional_length=True,
                )
                if ok:
                    return line
    return None


def generate_signature_line(
    plan: Any,
    draft: str,
    *,
    user_message: str = "",
) -> Optional[str]:
    """Write the last sentence after the body exists.

    Returns one sentence or None if nothing earns the fingerprint.
    Prefer discovery inside the draft over manufacturing a slogan.
    """
    fields = _plan_fields(plan)
    body = (draft or "").strip()
    anchors = list(fields.get("anchors") or [])
    insight = fields.get("central_insight") or ""

    # Strip trailing engagement/question debris before discovery
    if body.endswith("?"):
        sents = re.split(r"(?<=[.!?])\s+", body)
        if len(sents) >= 2:
            body = " ".join(sents[:-1]).rstrip()

    # 1) Body already ends with a true Signature Line — keep it
    if last_line_is_signature(
        body,
        user_message=user_message,
        anchors=anchors,
        central_insight=insight,
    ):
        return re.split(r"\n\s*\n", body)[-1].strip()

    # 2) Discover a sentence already living in the body
    extracted = extract_signature_from_body(
        body,
        user_message=user_message,
        anchors=anchors,
        central_insight=insight,
    )
    if extracted:
        return extracted

    # 3) Compress a late body sentence (react to the draft)
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", body)
        if s.strip() and not s.strip().endswith("?")
    ]
    for s in reversed(sentences[-5:]):
        compressed = _compress_candidate(
            s,
            user_message=user_message,
            body=body,
            anchors=anchors,
            central_insight=insight,
        )
        if compressed:
            return compressed

    # 4) Conversation-conditioned fallback (still must pass quality gates)
    return _conversation_conditioned_line(user_message, fields, body)


# Compat aliases used by recognition_landing
def craft_signature_line(user_message: str, body: str) -> Optional[str]:
    return generate_signature_line(
        {"central_insight": "", "anchors": []},
        body,
        user_message=user_message,
    )


def ensure_signature_line(
    text: str,
    user_message: str,
    *,
    plan: Any = None,
) -> Tuple[str, bool, Optional[str]]:
    """Attach a Signature Line when one can be earned. Only one landing wins."""
    base = (text or "").strip()
    fields = _plan_fields(plan)
    anchors = list(fields.get("anchors") or [])
    insight = fields.get("central_insight") or ""

    if last_line_is_signature(
        base,
        user_message=user_message,
        anchors=anchors,
        central_insight=insight,
    ):
        line = re.split(r"\n\s*\n", base)[-1].strip()
        remember_signature_line(line)
        return base, False, line

    if base.endswith("?"):
        sents = re.split(r"(?<=[.!?])\s+", base)
        if len(sents) >= 2:
            base = " ".join(sents[:-1]).rstrip()

    line = generate_signature_line(plan or {}, base, user_message=user_message)
    if not line:
        return base, False, None

    ok, _ = validate_signature_line(
        line,
        body=base,
        user_message=user_message,
        anchors=anchors,
        central_insight=insight,
        allow_exceptional_length=True,
        check_novelty=False,
    )
    if not ok:
        return base, False, None

    paras = re.split(r"\n\s*\n", base)
    last = (paras[-1] if paras else "").strip()
    if last == line:
        remember_signature_line(line)
        return base, False, line

    # If discovered mid-body, isolate as final paragraph (don't leave duplicate)
    if line in base and last != line:
        # Remove only a trailing duplicate occurrence
        if last.endswith(line):
            base = base[: base.rfind(line)].rstrip()
        elif line in last:
            without = last.replace(line, "").strip(" ,;")
            paras[-1] = without
            base = "\n\n".join(p for p in paras if p.strip())

    out = f"{base.rstrip()}\n\n{line}" if base else line
    remember_signature_line(line)
    return out, True, line
