# -*- coding: utf-8 -*-
"""Shared question extraction and answer completeness.

X, Telegram, and web call these functions. Publishing limits stay with
the caller. A pointer such as "your turn" is not a question, and a
quoted or third-party question is not a request to MoodyBot.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

_QUOTE = re.compile(r'"[^"]*"|“[^”]*”')
_MENTION = re.compile(r"@\w+")
_MOODY = re.compile(r"(?i)@MoodyBotAI\b")
_OTHER_LEAD = re.compile(r"(?i)^\s*@(?!MoodyBotAI\b)\w+")
_THIRD_PARTY = re.compile(
    r"(?i)(?:\b(?:you|someone|people|we|just|please|go)\s+)?"
    r"(?:\bshould\s+)?\b(?:ask|asking|asked|tell|telling|consult|ping)\s+@MoodyBotAI\b"
)
_COMPOUND = re.compile(
    r",?\s+\band\s+(?=(?:why|how|what|who|where|when|which)\b)",
    re.IGNORECASE,
)
_EXPLICIT_START = re.compile(
    r"(?i)^(?:what|why|how|who|where|when|which|whose)\b"
)
_IMPLICIT = re.compile(
    r"(?i)\b(?:explain|tell me|help me|compare|break down|weigh in|define)\b"
)
_POINTER = re.compile(
    r"(?i)\b(?:your\s+turn|same\s+question|what(?:'s|\s+is)\s+your\s+answer|"
    r"your\s+take|second\s+opinion|do\s+you\s+agree|can\s+you\s+verify)\b"
)
_ANAPHORA = re.compile(
    r"(?i)\b(?:he|she|him|her|his|their|he's|she's|they're)\b|\b(?:this|that|it|they|them)\b"
)
_RHETORICAL = re.compile(
    r"(?i)\b(?:let's see what|what you've got|what a \w+|i wonder why)\b"
)
_CAUSAL = re.compile(
    r"(?i)\b(?:because|so that|that's why|the reason|keeps|without|forgets|"
    r"confuses|mistakes|instead|rather than)\b"
)
_UNCERTAIN = re.compile(
    r"(?i)\b(?:i don't know|i do not know|can't say|cannot say|not enough here)\b"
)
_STOP = frozenset(
    """
    a an the of to and or for in on with from at by as is are was were be
    do does did so many people what why how who where when which whose this
    that these those it its into about than then just your you they them
    their between
    """.split()
)


def extract_questions(
    text: str,
    *,
    note_text: str = "",
    context_posts: Optional[list] = None,
    source_post_id: str = "",
    channel: str = "direct",
) -> dict:
    """Pull answerable questions. Current text wins over the parent thread."""
    source = note_text.strip() if isinstance(note_text, str) and note_text.strip() else (text or "")
    unquoted = _QUOTE.sub(" ", source)
    addressed = _addressed_to_moody(source, unquoted, channel)
    questions = []
    if addressed:
        questions = _from_text(unquoted, source, source_post_id, "current", 0.93)
    needs_context = False
    refers_back = bool(_POINTER.search(unquoted) or _IMPLICIT.search(unquoted))
    if addressed and not questions and refers_back:
        earlier = _from_context(context_posts or [])
        if earlier:
            questions = earlier
        else:
            needs_context = True
    elif addressed and not questions and _IMPLICIT.search(unquoted) and _dangling(unquoted):
        needs_context = True
    return {
        "questions": questions,
        "count": len(questions),
        "source_post_id": questions[0]["source_post_id"] if questions else source_post_id,
        "addressed_to_moody": addressed,
        "needs_context": needs_context and not questions,
        "confidence": questions[0]["confidence"] if questions else (0.4 if needs_context else 0.0),
    }


def assess_answer(extraction: dict, answer: str) -> list[dict]:
    """Mark each question answered, partial, unanswered, or cannot_answer."""
    reply = answer or ""
    verdicts = []
    for question in extraction.get("questions") or []:
        if question.get("needs_context") or extraction.get("needs_context"):
            verdict = "cannot_answer"
        elif _UNCERTAIN.search(reply):
            verdict = "cannot_answer"
        else:
            verdict = _cover(question, reply)
        verdicts.append({
            "question": question.get("text") or "",
            "verdict": verdict,
        })
    return verdicts


def revision_instruction(extraction: dict, verdicts: list[dict]) -> str:
    """One rewrite request. It names the missing part and does not add a lecture."""
    missing = [
        item["question"]
        for item in verdicts
        if item.get("verdict") in {"partial", "unanswered", "cannot_answer"}
    ]
    joined = " ".join(missing) if missing else "the unanswered part"
    return (
        "Rewrite one reply in the same voice. The draft missed this part: "
        + joined
        + ". Cover it inside the same reply. Do not add a separate explanation, "
        "a list, or a second post."
    )


def length_instruction(extraction: dict) -> str:
    parts = " ".join(item.get("text") or "" for item in extraction.get("questions") or [])
    return (
        "Rewrite the reply under 200 weighted characters. Cover every part: "
        + parts
        + ". Keep one voice. Do not drop a part to make it fit, and do not post twice."
    )


def explicit_partial(extraction: dict, verdicts: list[dict], limit: int, answer: str = "") -> str:
    """A short, labeled partial. Used only when one post cannot hold the full answer."""
    from x_integration.post_length import weighted_length

    note = "That's the first half. Ask for the rest."
    sentence = ""
    if answer.strip():
        sentence = re.split(r"(?<=[.!?])\s+", answer.strip())[0]
    candidate = (sentence + " " + note).strip() if sentence else note
    if weighted_length(candidate) <= limit:
        return candidate
    if weighted_length(note) <= limit:
        return note
    return ""


def settle_reply(
    extraction: dict,
    answer: str,
    *,
    limit: Optional[int] = None,
    shorten: Optional[Callable[[str], str]] = None,
) -> dict:
    """Decide whether an answer may be published.

    One shorten call is allowed. A part is never cut off without saying so.
    """
    from x_integration.post_length import weighted_length

    verdicts = assess_answer(extraction, answer)
    text = (answer or "").strip()
    strategy = "complete"
    shortened = False
    if _incomplete(verdicts):
        return {
            "publish": False,
            "text": "",
            "strategy": "incomplete",
            "verdicts": verdicts,
            "fits": False,
        }
    if limit is not None and weighted_length(text) > limit and shorten is not None:
        shortened = True
        candidate = str(shorten(length_instruction(extraction)) or "").strip()
        candidate_verdicts = assess_answer(extraction, candidate)
        if candidate and not _incomplete(candidate_verdicts) and weighted_length(candidate) <= limit:
            return {
                "publish": True,
                "text": candidate,
                "strategy": "complete",
                "verdicts": candidate_verdicts,
                "fits": True,
                "shortened": True,
            }
        if candidate and not _incomplete(candidate_verdicts):
            text = candidate
            verdicts = candidate_verdicts
    if limit is not None and text and weighted_length(text) > limit:
        partial = explicit_partial(extraction, verdicts, limit, text)
        if not partial:
            return {
                "publish": False,
                "text": "",
                "strategy": "incomplete",
                "verdicts": verdicts,
                "fits": False,
                "shortened": shortened,
            }
        return {
            "publish": True,
            "text": partial,
            "strategy": "partial",
            "verdicts": assess_answer(extraction, partial),
            "fits": weighted_length(partial) <= limit,
            "shortened": shortened,
        }
    fits = True if limit is None else weighted_length(text) <= limit
    if not text or not fits:
        return {
            "publish": False,
            "text": "",
            "strategy": "incomplete",
            "verdicts": verdicts,
            "fits": False,
            "shortened": shortened,
        }
    return {
        "publish": True,
        "text": text,
        "strategy": strategy,
        "verdicts": verdicts,
        "fits": fits,
        "shortened": shortened,
    }


def _incomplete(verdicts: list[dict]) -> bool:
    if not verdicts:
        return False
    return any(item.get("verdict") != "answered" for item in verdicts)


def _addressed_to_moody(source: str, unquoted: str, channel: str) -> bool:
    if channel != "x":
        return True
    if _THIRD_PARTY.search(unquoted) and not _request_to_moody(unquoted):
        return False
    if not _MOODY.search(source):
        return False
    if _QUOTE.sub(" ", source).strip() and not unquoted.strip():
        return False
    if _trailing_only(unquoted):
        return False
    return True


def _request_to_moody(unquoted: str) -> bool:
    if _POINTER.search(unquoted):
        return True
    for part in _sentences(unquoted):
        if _MOODY.search(part) and (_EXPLICIT_START.search(part.strip()) or _IMPLICIT.search(part)):
            return True
    return bool(_EXPLICIT_START.search(unquoted.strip()) or "?" in unquoted)


def _trailing_only(unquoted: str) -> bool:
    """@grok asks the question and @MoodyBotAI is only a trailing tag."""
    if not _OTHER_LEAD.search(unquoted):
        return False
    match = _MOODY.search(unquoted)
    if match is None:
        return False
    after = unquoted[match.end():]
    return not re.search(r"[A-Za-z0-9?]", after)


def _from_context(posts: list) -> list[dict]:
    found = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        text = post.get("text") if isinstance(post.get("text"), str) else ""
        note = ""
        raw_note = post.get("note_tweet")
        if isinstance(raw_note, dict) and isinstance(raw_note.get("text"), str):
            note = raw_note["text"]
        source = note.strip() or text
        if not source or _POINTER.search(source):
            continue
        found = _from_text(
            _QUOTE.sub(" ", source),
            source,
            str(post.get("id") or ""),
            "earlier",
            0.84,
        )
        if found:
            return found
    return []


def _from_text(unquoted: str, source: str, post_id: str, origin: str, confidence: float) -> list[dict]:
    questions = []
    for sentence in _sentences(unquoted):
        if _RHETORICAL.search(sentence) or _pointer_sentence(sentence):
            continue
        pieces = _independent_pieces(sentence)
        for piece in pieces:
            raw = " ".join(piece.split()).strip(" .")
            cleaned = " ".join(_MENTION.sub(" ", raw).split()).strip(" .")
            if not cleaned or _pointer_sentence(cleaned):
                continue
            starts = _EXPLICIT_START.search(cleaned) is not None
            asks = "?" in sentence or "?" in cleaned
            verb = re.search(
                r"(?i)\b(?:is|are|do|does|did|can|could|should|would)\b",
                cleaned,
            ) is not None
            explicit = (starts and (asks or _IMPLICIT.search(cleaned) is not None or verb)) or (
                "?" in cleaned
                and _RHETORICAL.search(cleaned) is None
                and len(_terms(cleaned)) >= 1
            )
            implicit = bool(_IMPLICIT.search(cleaned))
            if not explicit and not implicit:
                continue
            if not cleaned.endswith("?") and (explicit or "?" in sentence):
                cleaned = cleaned + "?"
            span = _span(source, piece)
            questions.append({
                "text": cleaned,
                "source_post_id": post_id,
                "span": span,
                "self_contained": _self_contained(cleaned),
                "needs_context": not _self_contained(cleaned),
                "confidence": confidence if explicit or "?" in sentence else 0.8,
                "origin": origin,
                "kind": "explicit" if explicit or "?" in sentence else "implicit",
            })
    return [item for item in questions if item["self_contained"]]


def _independent_pieces(sentence: str) -> list[str]:
    parts = [part.strip() for part in _COMPOUND.split(sentence) if part and part.strip()]
    return parts or [sentence]


def _sentences(text: str) -> list[str]:
    chunks = []
    for block in re.split(r"[\n]+", text):
        pieces = re.split(r"(?<=[.!?])\s+", block.strip())
        chunks.extend(piece.strip() for piece in pieces if piece.strip())
    return chunks


def _pointer_sentence(sentence: str) -> bool:
    if _POINTER.search(sentence) is None:
        return False
    leftover = _POINTER.sub(" ", sentence)
    leftover = _MENTION.sub(" ", leftover)
    return len(re.findall(r"[A-Za-z0-9']+", leftover)) < 3


def _self_contained(question: str) -> bool:
    """A pointer or a question about an unnamed 'he' or 'this' still needs context."""
    if _pointer_sentence(question) or _dangling(question):
        return False
    if _ANAPHORA.search(question) and not re.search(
        r"(?i)\bbetween\s+[a-z]+\s+and\s+[a-z]+", question
    ):
        return False
    return len(_terms(question)) >= 1


def _dangling(text: str) -> bool:
    words = re.findall(r"[A-Za-z0-9']+", _MENTION.sub(" ", text))
    if not words:
        return True
    return words[-1].lower() in {"this", "that", "it"} and len(words) <= 3


def _span(source: str, piece: str) -> list[int]:
    needle = " ".join(piece.split()).strip()
    if not needle:
        return [0, 0]
    start = source.lower().find(needle.lower().rstrip("?"))
    if start < 0:
        return [0, 0]
    return [start, start + len(needle.rstrip("?"))]


def _cover(question: dict, answer: str) -> str:
    kind, terms = _demand(question.get("text") or "")
    hay = answer.lower()
    present = [term for term in terms if term in hay]
    if kind == "contrast":
        if len(present) >= 2:
            return "answered"
        if present:
            return "partial"
        return "unanswered"
    if kind == "cause":
        if present and _CAUSAL.search(answer):
            return "answered"
        if present or _CAUSAL.search(answer):
            return "partial"
        return "unanswered"
    if len(present) >= max(1, min(2, len(terms))):
        return "answered"
    names = [term for term in terms if len(term) > 5]
    if names and any(term in hay for term in names):
        return "answered"
    if present:
        return "partial"
    return "unanswered"


def _demand(question: str) -> tuple[str, list[str]]:
    text = question.lower()
    between = re.search(r"between\s+([a-z]+)\s+and\s+([a-z]+)", text)
    if between or re.search(r"\b(difference|differ|compare)\b", text):
        terms = [between.group(1), between.group(2)] if between else _terms(text)[:2]
        return "contrast", terms
    if re.search(r"\bwhy\b", text):
        return "cause", _terms(text)[:5]
    return "topic", _terms(text)[:4]


def _terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return [word for word in words if word not in _STOP and len(word) > 3]
