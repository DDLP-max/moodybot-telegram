# -*- coding: utf-8 -*-
"""Signature Line — rare earned ending, never a required module.

PRIMARY RULE: the body is allowed to be the last line.

If the final sentence is already sharp, complete, specific, memorable,
and rhythmically final — STOP WRITING.

Do not ask "what can I add?"
Ask "did I already say enough?"

Pipeline:
  draft_body
  → epistemic / quality checks
  → body_already_lands()  → BODY_ENDS_RESPONSE (preferred)
  → else attempt signature discovery
  → if none: BODY_ENDS_RESPONSE
  → deletion + redundancy tests (if A ≥ B, delete candidate)
  → surface render
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

MAX_WORDS = 18
MAX_WORDS_EXCEPTIONAL = 22
MIN_WORDS = 4
DISCOVERY_THRESHOLD = 0.72
SIMILARITY_REJECT = 0.62
# Shorter paraphrase / near-echo of the thesis
REDUNDANCY_REJECT = 0.55

NO_SIGNATURE_FOUND = "NO_SIGNATURE_FOUND"

# Cadence that already ends the piece — nothing after these.
TERMINAL_RHYTHM_EXAMPLES = (
    r"before the example spreads",
    r"the paper trail does the talking",
    r"the relationship was already telling you",
    r"the performance runs out",
    r"before the example becomes contagious",
    r"examples are more dangerous than arguments",
)

TERMINAL_RHYTHM_STRUCTURAL = re.compile(
    r"(?:"
    r"\b(?:before|once|until)\b.+\b(?:spreads?|contagious|runs?\s+out|ends?|talking|telling you)\b"
    r"|"
    r"\b(?:not|isn't|aren't|wasn't|weren't)\b.+\b(?:it's|it is|they're|they are|he's|she's)\b"
    r"|"
    r"\b(?:because|so)\b.+\b(?:more dangerous|already|no longer|instead)\b"
    r"|"
    r"\b(?:punish(?:es|ed)?|polices?|threatens?|enforces?|survives?)\b.+\b(?:before|once|until)\b"
    r")",
    re.IGNORECASE,
)

LANDING_INSIGHT_MARKERS = re.compile(
    r"\b(?:"
    r"enforcement|disciplinary|threatens?|reveals?|betrayal|convenience|"
    r"protection|resentment|defection|loyalty|narrative|grievance|"
    r"already|stopped|becomes?|explains?|survives?|pretending|"
    r"punish(?:es|ed)?|breach|collective|subtractive"
    r")\b",
    re.IGNORECASE,
)

DANGLING_THREAD = re.compile(
    r"(?:"
    r"\b(?:because|since|which means|which is why|and then|so that)\s*$"
    r"|"
    r"\b(?:for example|for instance|such as)\s*[,:]?\s*$"
    r"|"
    r":\s*$"
    r"|"
    r"\b(?:however|although|though|but)\s*$"
    r")",
    re.IGNORECASE,
)

_RECENT_SIGNATURES: Deque[str] = deque(maxlen=32)

ENGAGEMENT_MARKERS = (
    "do you want", "would you like", "let me know", "say the word",
    "does that make sense", "what do you think", "tell me more",
    "subscribe", "@moodybot", "tag me",
)

SUMMARY_MARKERS = (
    "in other words", "to summarize", "to sum up", "in summary",
    "basically", "all in all", "the bottom line is", "to put it simply",
)

# Bumper stickers / fake profundity
GENERIC_APHORISMS = (
    "everything happens for a reason", "life is complicated",
    "truth always wins", "truth wins", "power corrupts",
    "trust the process", "you got this", "stay strong",
    "believe in yourself", "it is what it is", "live your truth",
    "time heals all wounds", "knowledge is power", "change is hard",
    "the truth hurts", "gratitude matters", "movements need enemies",
    "everything changes", "stories protect themselves",
    "boundaries matter", "people are complex",
)

AI_PROFOUND_MARKERS = (
    "in a world where", "at the end of the day", "the reality is that",
    "it's important to remember", "a powerful reminder", "speaks volumes",
    "the human condition", "more than meets the eye",
)


@dataclass
class SignatureLineScore:
    """Discovery score — below threshold means do not generate."""

    novel_insight: float = 0.0
    unexpected: float = 0.0
    inevitable: float = 0.0
    adds_meaning: float = 0.0
    different_abstraction: float = 0.0
    reasons: List[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return (
            self.novel_insight
            + self.unexpected
            + self.inevitable
            + self.adds_meaning
            + self.different_abstraction
        ) / 5.0

    @property
    def ok(self) -> bool:
        return self.total >= DISCOVERY_THRESHOLD and not self.reasons


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _content_tokens(text: str) -> set:
    stop = {
        "the", "and", "for", "that", "this", "with", "from", "about", "have",
        "what", "when", "where", "which", "your", "you", "how", "did", "does",
        "are", "was", "were", "been", "into", "than", "then", "just", "like",
        "not", "but", "its", "it's", "they", "them", "their", "our", "out",
        "all", "any", "can", "could", "would", "should", "will",
    }
    return {
        t for t in re.findall(r"[a-z0-9']+", _norm(text))
        if len(t) > 2 and t not in stop
    }


def is_single_sentence(text: str) -> bool:
    s = (text or "").strip()
    if not s or s[-1] not in ".!":
        return False
    body = s[:-1]
    if "?" in body or "!" in body or "." in body:
        return False
    return True


def _body_sentences(body: str) -> List[str]:
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", (body or "").strip())
        if s.strip() and not s.strip().endswith("?")
    ]


def final_paragraph(text: str) -> str:
    paras = re.split(r"\n\s*\n", (text or "").strip())
    return (paras[-1] if paras else "").strip()


def semantic_similarity(a: str, b: str) -> float:
    ta, tb = _content_tokens(a), _content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta | tb), 1)


def is_shorter_paraphrase(line: str, body: str) -> bool:
    """True when candidate is a shorter compression of a body sentence."""
    line_toks = _content_tokens(line)
    if len(line_toks) < 3:
        return False
    line_wc = word_count(line)
    for sent in _body_sentences(body):
        sent_toks = _content_tokens(sent)
        if not sent_toks:
            continue
        if line_toks <= sent_toks and line_wc < word_count(sent):
            return True
        overlap = len(line_toks & sent_toks) / max(len(line_toks), 1)
        if overlap >= 0.8 and line_wc <= word_count(sent) and len(line_toks - sent_toks) <= 1:
            return True
    return False


def is_semantically_redundant(line: str, body: str) -> bool:
    """Candidate is substantially a paraphrase of final sentence / thesis / para."""
    if not line or not body:
        return False
    if body_already_said_this(line, body) or is_shorter_paraphrase(line, body):
        return True
    final = _body_sentences(body)[-1] if _body_sentences(body) else ""
    fp = final_paragraph(body)
    targets = [t for t in (final, fp, body) if t]
    for target in targets:
        sim = semantic_similarity(line, target)
        if sim >= SIMILARITY_REJECT:
            novel = _content_tokens(line) - _content_tokens(target)
            if len(novel) < 2:
                return True
        if sim >= REDUNDANCY_REJECT and word_count(line) <= word_count(target):
            novel = _content_tokens(line) - _content_tokens(target)
            if len(novel) < 3 and not adds_deeper_layer(line, body):
                return True
    return False


def body_already_said_this(line: str, body: str) -> bool:
    """Restatement / shortening / echo of anything the body already said."""
    line_n = _norm(line)
    line_toks = _content_tokens(line)
    if not line_n or not body or not line_toks:
        return False
    for sent in _body_sentences(body):
        sent_n = _norm(sent)
        sent_toks = _content_tokens(sent)
        if not sent_n or not sent_toks:
            continue
        if line_n == sent_n or line_n.rstrip(".!") == sent_n.rstrip(".!"):
            return True
        # Shortening paraphrase
        if line_toks <= sent_toks and len(line_toks) >= 3:
            return True
        overlap = len(line_toks & sent_toks) / max(len(line_toks), 1)
        if overlap >= 0.72 and len(line_toks - sent_toks) <= 2:
            return True
        # Near-identical with a tacked qualifier ("..., not protection")
        if overlap >= 0.85:
            return True
    # Also compare to final paragraph as a whole
    fp = final_paragraph(body)
    if fp and semantic_similarity(line, fp) >= SIMILARITY_REJECT:
        # Allow only if clearly higher abstraction with novel hinges
        if len(_content_tokens(line) - _content_tokens(fp)) < 2:
            return True
    return False


def adds_deeper_layer(line: str, body: str) -> bool:
    """Body explains. Signature reveals — new abstraction, not rewording."""
    if not body:
        return False
    line_toks = _content_tokens(line)
    body_toks = _content_tokens(body)
    if not line_toks:
        return False
    novel = line_toks - body_toks
    reveal_turn = bool(
        re.search(
            r"\b(becomes?|became|stopped being|already ending|runs?\s+out|"
            r"pretending|needs? permission|survives by|long before|"
            r"was already|no longer|instead|don't end|rarely end|"
            r"explains?|announces itself)\b",
            _norm(line),
        )
    )
    if re.search(r"\b(matter|matters|important|real|true|valid)\b\.?$", _norm(line)):
        return False
    return reveal_turn and len(novel) >= 2


def has_terminal_rhythm(final: str) -> bool:
    """Clear terminal cadence — reversal, consequence, contrast, image, decisive close."""
    lower = (final or "").strip().lower().rstrip(".!")
    if not lower:
        return False
    for example in TERMINAL_RHYTHM_EXAMPLES:
        if example in lower:
            return True
    if TERMINAL_RHYTHM_STRUCTURAL.search(lower):
        return True
    # Decisive clause: compressed insight ending on a hard noun/verb
    if LANDING_INSIGHT_MARKERS.search(lower) and len(lower.split()) >= 10:
        if re.search(
            r"\b(?:spreads?|talking|telling|runs?\s+out|resentment|defection|"
            r"enforcement|narrative|breach|loyalty|betrayal)\.?$",
            lower,
        ):
            return True
    return False


def body_already_lands(body: str) -> bool:
    """Preferred landing detector — true when the body should be the last line.

    True when the final sentence / paragraph:
      1. completes the argument
      2. carries the strongest insight
      3. leaves no logical thread dangling
      4. has clear terminal rhythm
      5. would be diluted by another sentence
    """
    text = (body or "").strip()
    if not text:
        return False
    last = final_paragraph(text)
    if not last or last.endswith("?"):
        return False
    lower = last.lower()
    if any(m in lower for m in ENGAGEMENT_MARKERS):
        return False
    if any(m in lower for m in ("seen it named", "what about ", "say the word")):
        return False
    if any(m in lower for m in SUMMARY_MARKERS):
        return False
    sentences = [s.strip() for s in re.split(r"(?<=[.!])\s+", last) if s.strip()]
    if not sentences:
        return False
    final = sentences[-1]
    if final[-1] not in ".!":
        return False
    stem = final.rstrip(".!").strip()
    if DANGLING_THREAD.search(stem):
        return False
    wc = len(final.split())
    if wc < 7:
        return False

    rhythm = has_terminal_rhythm(final)
    insight = bool(LANDING_INSIGHT_MARKERS.search(final))
    hedging = bool(re.search(r"\b(maybe|perhaps|might|seems? to)\b", final.lower()))
    # Multi-sentence body whose last line lands = argument complete
    multi = len(_body_sentences(text)) >= 2
    solid = wc >= 12 and not hedging and insight
    # Strong single landing line with terminal rhythm
    rhythmic_close = rhythm and wc >= 8 and not hedging
    # Preferred: finished analytic prose
    if rhythmic_close and (insight or multi or wc >= 14):
        return True
    if solid and (rhythm or multi):
        return True
    # Completed argument: earlier sentences set up; final insight closes
    if insight and multi and wc >= 7 and not hedging:
        return True
    return False


def body_alone_stronger_or_equal(body: str, signature: str) -> bool:
    """Deletion test core: A (body alone) ≥ B (body + candidate) → discard candidate."""
    if not signature or not signature.strip():
        return True
    if body_already_lands(body):
        return True
    if is_semantically_redundant(signature, body):
        return True
    if body_already_said_this(signature, body):
        return True
    if is_shorter_paraphrase(signature, body):
        return True
    if not adds_deeper_layer(signature, body):
        return True
    fp = final_paragraph(body)
    if fp and semantic_similarity(signature, fp) >= SIMILARITY_REJECT:
        return True
    # Floating bumper sticker with no hinge
    if not _content_tokens(signature) & (_content_tokens(body) | _content_tokens(fp or "")):
        if word_count(signature) <= 8:
            return True
    return False


def deletion_test(body: str, signature: str) -> bool:
    """Authoritative gate. True = keep signature. False = delete it.

    Generate candidate, then compare A (body alone) vs B (body + candidate).
    If A is equal or stronger — DELETE. Return BODY_ENDS_RESPONSE.
    """
    if not signature or not signature.strip():
        return False
    if body_alone_stronger_or_equal(body, signature):
        return False
    return True


def score_discovery(
    line: str,
    *,
    body: str = "",
    user_message: str = "",
) -> SignatureLineScore:
    """Score whether a candidate is a genuine discovery."""
    s = SignatureLineScore()
    lower = _norm(line)
    line_toks = _content_tokens(line)
    body_toks = _content_tokens(body)
    novel = line_toks - body_toks if body_toks else line_toks

    if any(a in lower for a in GENERIC_APHORISMS):
        s.reasons.append("bumper_sticker")
        return s
    if any(m in lower for m in AI_PROFOUND_MARKERS):
        s.reasons.append("fake_profundity")
        return s
    if body_already_said_this(line, body):
        s.reasons.append("restates_or_shortens")
        return s
    if not deletion_test(body, line):
        s.reasons.append("fails_deletion_test")
        return s

    # Novel insight
    s.novel_insight = min(1.0, len(novel) / 3.0) if novel else 0.0
    # Unexpected: not a subset paraphrase
    s.unexpected = 1.0 if len(novel) >= 2 else 0.35
    # Inevitable: lexical hinge OR earned higher-order reveal after the body
    overlap = line_toks & body_toks
    deeper = adds_deeper_layer(line, body)
    if overlap:
        s.inevitable = 1.0
    elif deeper and len(novel) >= 2:
        # Conceptual inevitability — new abstraction implied by the body
        s.inevitable = 0.9
    else:
        s.inevitable = 0.2
    # Adds meaning
    s.adds_meaning = 1.0 if deeper else 0.0
    # Different abstraction level (not same nouns restated)
    s.different_abstraction = 1.0 if len(novel) >= 2 and deeper else 0.25

    if s.total < DISCOVERY_THRESHOLD:
        s.reasons.append("below_discovery_threshold")
    return s


# Compat alias used by older tests
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


def score_signature_line(
    line: str,
    *,
    body: str = "",
    user_message: str = "",
    anchors: Optional[List[str]] = None,
    central_insight: str = "",
) -> SignatureQuality:
    """Legacy boolean gate wrapped around discovery score + hard rejects."""
    _ = anchors
    _ = central_insight
    q = SignatureQuality()
    lower = _norm(line)
    disc = score_discovery(line, body=body, user_message=user_message)

    q.specificity = not any(a in lower for a in GENERIC_APHORISMS)
    if not q.specificity:
        q.reasons.append("specificity:generic")
    q.authorship = not any(m in lower for m in AI_PROFOUND_MARKERS + ENGAGEMENT_MARKERS)
    if not q.authorship:
        q.reasons.append("authorship:fail")
    q.compression = not body_already_said_this(line, body) and (
        not body or adds_deeper_layer(line, body)
    )
    if not q.compression:
        q.reasons.append("compression:restates_or_no_depth")
    q.inevitability = (
        disc.inevitable >= 0.5
        and "fails_deletion_test" not in disc.reasons
        and "restates_or_shortens" not in disc.reasons
    )
    if not q.inevitability:
        q.reasons.append("inevitability:fail")
    # "Memory" reframed: structural fitness, not quotability chase
    q.memory = (
        is_single_sentence(line)
        and MIN_WORDS <= word_count(line) <= MAX_WORDS_EXCEPTIONAL
        and not line.endswith("?")
    )
    if not q.memory:
        q.reasons.append("memory:structure")
    if disc.reasons:
        q.reasons.extend(disc.reasons)
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
    if not deletion_test(body, s) and body:
        return False, "REJECTED:fails_deletion_test"
    quality = score_signature_line(
        s,
        body=body,
        user_message=user_message,
        anchors=anchors,
        central_insight=central_insight,
    )
    if not quality.ok:
        return False, "REJECTED:" + (quality.reasons[0] if quality.reasons else "quality")
    disc = score_discovery(s, body=body, user_message=user_message)
    if not disc.ok:
        return False, "REJECTED:" + (disc.reasons[0] if disc.reasons else "discovery")
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
        "anchors": list(getattr(plan, "anchors", None) or []),
        "intent": getattr(plan, "intent", None) or "",
        "selected_command": getattr(plan, "selected_command", None) or "",
    }


def last_line_is_signature(
    text: str,
    *,
    user_message: str = "",
    anchors: Optional[List[str]] = None,
    central_insight: str = "",
) -> bool:
    paras = re.split(r"\n\s*\n", (text or "").strip())
    if len(paras) < 2:
        return False
    last = paras[-1].strip()
    prior = "\n\n".join(paras[:-1]).strip()
    ok, _ = validate_signature_line(
        last,
        body=prior,
        user_message=user_message,
        anchors=anchors,
        central_insight=central_insight,
        check_novelty=False,
    )
    return ok


def _candidate_bank(user_message: str, body: str) -> List[str]:
    """Optional discoveries — never mandatory slogans."""
    blob = f"{user_message} {_norm(body)}".lower()
    bank: List[Tuple[Tuple[str, ...], Tuple[str, ...]]] = [
        (
            ("feminist", "feminism", "praising", "pick me", "loyalty", "equality"),
            (
                "The moment gratitude becomes betrayal, the argument stopped being about equality.",
                "The moment gratitude needs permission, the argument changed.",
            ),
        ),
        (
            ("boundary", "boundaries"),
            (
                "Boundaries don't end relationships — they reveal the ones that were already ending.",
            ),
        ),
        (
            ("dirty talk", "porn", "script"),
            (
                "The script usually survives by making the new language feel ordinary.",
            ),
        ),
    ]
    out: List[str] = []
    for keys, lines in bank:
        if any(k in blob for k in keys):
            out.extend(lines)
    return out


def discover_signature_line(
    plan: Any,
    draft: str,
    *,
    user_message: str = "",
) -> Optional[str]:
    """Attempt to DISCOVER an ending. None / NO_SIGNATURE_FOUND is success."""
    fields = _plan_fields(plan)
    body = (draft or "").strip()
    if body.endswith("?"):
        sents = re.split(r"(?<=[.!?])\s+", body)
        if len(sents) >= 2:
            body = " ".join(sents[:-1]).rstrip()

    # If body already landed, do not hunt for a quote
    if body_already_lands(body):
        return None

    # Already has a true deeper last paragraph
    if last_line_is_signature(
        body,
        user_message=user_message,
        anchors=list(fields.get("anchors") or []),
        central_insight=fields.get("central_insight") or "",
    ):
        last = final_paragraph(body)
        prior = "\n\n".join(re.split(r"\n\s*\n", body)[:-1])
        if deletion_test(prior, last):
            return last

    # Try conversation-conditioned candidates — accept only if discovery score passes
    for cand in _candidate_bank(user_message, body):
        if _norm(cand) in _RECENT_SIGNATURES:
            continue
        disc = score_discovery(cand, body=body, user_message=user_message)
        if not disc.ok:
            continue
        ok, _ = validate_signature_line(
            cand,
            body=body,
            user_message=user_message,
            allow_exceptional_length=True,
            check_novelty=True,
        )
        if ok and deletion_test(body, cand):
            return cand

    return None


def generate_signature_line(
    plan: Any,
    draft: str,
    *,
    user_message: str = "",
) -> Optional[str]:
    """Compat name — discovery only. Never manufactures obligatory profundity."""
    return discover_signature_line(plan, draft, user_message=user_message)


def craft_signature_line(user_message: str, body: str) -> Optional[str]:
    return discover_signature_line({}, body, user_message=user_message)


def ensure_signature_line(
    text: str,
    user_message: str,
    *,
    plan: Any = None,
) -> Tuple[str, bool, Optional[str]]:
    """Attach a Signature Line only if discovered AND it survives deletion test.

    Returns (text, modified, signature_or_none).
    None signature with unmodified/stripped body = BODY_ENDS_RESPONSE outcome.
    """
    base = (text or "").strip()
    if base.endswith("?"):
        sents = re.split(r"(?<=[.!?])\s+", base)
        if len(sents) >= 2:
            base = " ".join(sents[:-1]).rstrip()

    # Body already finished — stop writing
    if body_already_lands(base):
        return base, False, None

    if last_line_is_signature(base, user_message=user_message):
        paras = re.split(r"\n\s*\n", base)
        line = paras[-1].strip()
        prior = "\n\n".join(paras[:-1]).strip()
        if deletion_test(prior, line):
            remember_signature_line(line)
            return base, False, line
        # Deletion test failed — strip the fake ending
        return prior or base, True, None

    line = discover_signature_line(plan or {}, base, user_message=user_message)
    if not line:
        return base, False, None

    if not deletion_test(base, line):
        return base, False, None

    disc = score_discovery(line, body=base, user_message=user_message)
    if not disc.ok:
        return base, False, None

    out = f"{base.rstrip()}\n\n{line}"
    # Final deletion test on the assembled piece
    if not deletion_test(base, line):
        return base, False, None

    remember_signature_line(line)
    return out, True, line
