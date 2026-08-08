# -*- coding: utf-8 -*-
"""Recognition Landing — how a MoodyBot response comes to rest.

A Landing is the final movement of the piece.
It is NOT a required question template.

Landing types:
  RECOGNITION_STATEMENT
  RECOGNITION_CALLBACK   (question — exception, not default)
  RECOGNITION_OBSERVATION
  ACTION
  SILENCE

The user should never notice the architecture.
They should only notice that the ending feels inevitable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from signature_language import (
    extract_signature_language,
    remember_signature_use,
    transform_signature_callback,
)

LandingType = str

# Patterns that prove the closer is machine-stapled topic debris.
BROKEN_CLOSER_PATTERNS = [
    r"^what about\b.+\blooks different\b",
    r"^what about\b.+\bseen it named\b",
    r"\bhate \w+ looks\b",
    r"\bfeminists?\b.+\blooks different\b",
    r"\bwhat about (?:the )?(?:\w+\s+){2,6}looks\b",
    r"\bstill holds\?$",
]


@dataclass
class LandingDecision:
    landing: LandingType
    allow_question: bool
    reason: str


def is_grammatical_english(text: str) -> bool:
    """Lightweight gate — reject obviously broken AI-stapled closers."""
    s = (text or "").strip()
    if not s:
        return False
    if len(s.split()) < 3:
        return False
    lower = s.lower()
    if any(re.search(pat, lower) for pat in BROKEN_CLOSER_PATTERNS):
        return False
    # "What about X Y Z looks..." style
    if lower.startswith("what about ") and " looks " in lower:
        return False
    # Fragment markers
    if re.search(r"\b(?:feminists?|women|men|porn|dirty talk)\b.+\b(?:looks different|seen it named)\b", lower):
        return False
    # Must end in . ! or ?
    if s[-1] not in ".!?":
        return False
    # Reject doubled function-words / broken stacks
    if re.search(r"\b(\w+)\s+\1\b", lower):
        return False
    return True


def would_keep_if_nobody_could_reply(text: str) -> bool:
    """Would this sentence earn its place in an essay with no reply button?"""
    s = (text or "").strip()
    if not s:
        return False
    if not is_grammatical_english(s):
        return False
    lower = s.lower()
    # Customer-support / engagement debris
    if any(
        p in lower
        for p in (
            "do you want",
            "would you like",
            "let me know",
            "say the word",
            "does that make sense",
            "seen it named",
            "what about ",
        )
    ):
        return False
    # Forced reflective menu
    if lower.startswith("what part of that") or lower.startswith("which aspect"):
        return False
    return True


def body_already_lands(body: str) -> bool:
    """True if the draft already ends on a complete, non-question insight."""
    text = (body or "").strip()
    if not text:
        return False
    last = re.split(r"\n\s*\n", text)[-1].strip()
    if last.endswith("?"):
        return False
    # Prefer substantive ending sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!])\s+", last) if s.strip()]
    if not sentences:
        return False
    final = sentences[-1]
    return len(final.split()) >= 6 and final[-1] in ".!"


def extract_best_statement_from_body(body: str) -> Optional[str]:
    """Pull a strong non-question sentence that could serve as the landing."""
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", (body or "").strip())
        if s.strip() and not s.strip().endswith("?")
    ]
    # Prefer later, medium-length insight sentences
    candidates = [s for s in sentences if 8 <= len(s.split()) <= 32]
    if not candidates:
        candidates = [s for s in sentences if 6 <= len(s.split()) <= 40]
    if not candidates:
        return None
    return candidates[-1]


def craft_recognition_statement(user_message: str, body: str) -> Optional[str]:
    """Build a statement landing — never a topic-noun question template."""
    # If body already has a strong ending, do not invent a new one.
    if body_already_lands(body):
        return None  # signal: keep body as-is

    existing = extract_best_statement_from_body(body)
    if existing and would_keep_if_nobody_could_reply(existing):
        # Reuse as landing only if it isn't already the final line
        last = re.split(r"\n\s*\n", (body or "").strip())[-1].strip()
        if existing in last and last.endswith(existing[-1] if existing else ""):
            return None
        return existing

    um = (user_message or "").lower()
    # Topic-aware statement bank — literary landings, not templates glued to nouns
    if any(w in um for w in ("feminist", "feminism", "praising men", "loyalty")):
        return "Once gratitude becomes defection, the conversation has already changed."
    if any(w in um for w in ("dirty talk", "porn", "1995", "sexual language")):
        return "The interesting shift isn't that the language got dirtier — it's that the script library got larger."
    if any(w in um for w in ("doorman", "flowers", "wine")):
        return "The move is clear. The next line is hers."
    if any(w in um for w in ("cancel", "late at night", "low priority", "only calls")):
        return "Convenience dressed as connection is still just convenience."
    if any(w in um for w in ("manager", "credit", "workplace", "boss")):
        return "They're protecting position. Your move is about visibility, not their inner life."

    # Generic strong landing when insight work happened but no specialty match
    if existing:
        return existing
    return None


def craft_recognition_observation(body: str) -> Optional[str]:
    existing = extract_best_statement_from_body(body)
    if existing and would_keep_if_nobody_could_reply(existing):
        return existing
    return None


def craft_callback_question(user_message: str, conversation_id: str = "") -> Optional[str]:
    """Question landings only when authorial signature language exists."""
    signatures = extract_signature_language(user_message)
    if not signatures.protected:
        return None
    q = transform_signature_callback(signatures, conversation_id=conversation_id)
    if not q:
        return None
    if not q.endswith("?"):
        q += "?"
    if not is_grammatical_english(q):
        return None
    if not would_keep_if_nobody_could_reply(q):
        # Signature questions are allowed to be questions — soften the "what about" ban
        if q.lower().startswith("what about"):
            return None
    remember_signature_use(conversation_id or "default", q, signatures)
    return q


def select_landing(
    user_message: str,
    *,
    selected_command: str = "/thoughts",
    body: str = "",
    practical: bool = False,
    grief: bool = False,
    technical: bool = False,
    roast: bool = False,
    missing_info: bool = False,
) -> LandingDecision:
    """Choose how the response should come to rest. Questions are the exception."""
    um = (user_message or "").lower()
    signatures = extract_signature_language(user_message)

    if missing_info:
        return LandingDecision("SILENCE", False, "clarification belongs in the body")

    if grief or selected_command in {"/ghost", "/numb"}:
        return LandingDecision("SILENCE", False, "grief/weight")

    if roast or selected_command in {"/roast", "/savage", "/cut"}:
        return LandingDecision("SILENCE", False, "killshot should stand")

    if practical or any(
        p in um
        for p in ("what should i do", "what do i say", "how should i handle", "what now")
    ):
        return LandingDecision("ACTION", False, "practical request")

    if technical:
        return LandingDecision("SILENCE", False, "technical — no emotional closer")

    # Authorial signature phrase present → question can earn its place
    if signatures.protected and any(
        s in um for s in ("stretch", "carrying", "cracked", "got stretched")
    ):
        return LandingDecision(
            "RECOGNITION_CALLBACK",
            True,
            "authorial signature invites rhetorical callback",
        )

    # Politics / cultural criticism / relationship analysis → statement preferred
    if any(
        w in um
        for w in (
            "feminist", "feminism", "politics", "political", "culture", "cultural",
            "society", "porn", "dirty talk", "relationship", "why do", "why does",
            "praising", "loyalty",
        )
    ):
        if body_already_lands(body):
            return LandingDecision("SILENCE", False, "insight already landed")
        return LandingDecision(
            "RECOGNITION_STATEMENT",
            False,
            "criticism/insight — statement beats question",
        )

    if body_already_lands(body):
        return LandingDecision("SILENCE", False, "body already complete")

    # Confession / soft emotional — observation or statement, question optional
    if selected_command in {"/validate", "/velvet"} or any(
        w in um for w in ("i feel", "i'm scared", "confession", "i hate that i")
    ):
        return LandingDecision("RECOGNITION_OBSERVATION", False, "emotional — observe, don't quiz")

    return LandingDecision("RECOGNITION_STATEMENT", False, "default: land, don't quiz")


def apply_landing(
    text: str,
    user_message: str,
    decision: LandingDecision,
    *,
    conversation_id: str = "",
) -> Tuple[str, bool]:
    """Apply landing to draft. Returns (text, modified).

    May REMOVE a bad closer without replacing it.
    Never append a broken question to prove the module exists.
    """
    parts = re.split(r"\n\s*\n", (text or "").strip())
    if len(parts) >= 2:
        body, closer = "\n\n".join(parts[:-1]).rstrip(), parts[-1].strip()
    else:
        body, closer = (text or "").strip(), ""

    def _strip_trailing_question(base: str) -> str:
        if base.rstrip().endswith("?"):
            sentences = re.split(r"(?<=[.!?])\s+", base.rstrip())
            if len(sentences) >= 2:
                return " ".join(sentences[:-1]).rstrip()
        return base

    # Always drop broken / engagement closers
    if closer and (
        not is_grammatical_english(closer)
        or not would_keep_if_nobody_could_reply(closer)
        or closer.endswith("?")
        and decision.landing != "RECOGNITION_CALLBACK"
    ):
        # Strip bad closer; may replace below
        text_body = body if body else _strip_trailing_question(text or "")
        closer = ""
        body = text_body
        modified_strip = True
    else:
        modified_strip = False

    landing = decision.landing

    if landing == "SILENCE":
        base = body or _strip_trailing_question(text or "")
        # Remove trailing questions
        base = _strip_trailing_question(base)
        if closer and closer.endswith("?"):
            return base, True
        return (base if modified_strip or closer == "" else text), modified_strip or bool(closer.endswith("?") if closer else False)

    if landing == "ACTION":
        base = body or text
        if closer and (closer.endswith("?") or not would_keep_if_nobody_could_reply(closer)):
            return _strip_trailing_question(base), True
        return text if not modified_strip else base, modified_strip

    if landing == "RECOGNITION_CALLBACK":
        # Keep a good existing signature question
        if (
            closer.endswith("?")
            and is_grammatical_english(closer)
            and extract_signature_language(user_message).protected
            and any(
                stem in closer.lower()
                for stem in extract_signature_language(user_message).stems
            )
        ):
            return text, False

        q = craft_callback_question(user_message, conversation_id=conversation_id)
        base = _strip_trailing_question(body or text)
        if not q:
            # Fall back to statement — never invent topic-noun questions
            stmt = craft_recognition_statement(user_message, base)
            if stmt and would_keep_if_nobody_could_reply(stmt):
                # Only append if not already present
                if stmt not in base:
                    return f"{base.rstrip()}\n\n{stmt}", True
            return base, True
        if q in base:
            return base, True
        return f"{base.rstrip()}\n\n{q}", True

    if landing in {"RECOGNITION_STATEMENT", "RECOGNITION_OBSERVATION"}:
        base = _strip_trailing_question(body or text)
        if body_already_lands(base):
            return base, True if (closer or modified_strip) else modified_strip

        if landing == "RECOGNITION_OBSERVATION":
            stmt = craft_recognition_observation(base) or craft_recognition_statement(
                user_message, base
            )
        else:
            stmt = craft_recognition_statement(user_message, base)

        if not stmt:
            return base, True if (closer or modified_strip) else modified_strip
        if not would_keep_if_nobody_could_reply(stmt) or not is_grammatical_english(
            stmt if stmt.endswith((".", "!", "?")) else stmt + "."
        ):
            return base, True if (closer or modified_strip) else modified_strip
        if not stmt.endswith((".", "!", "?")):
            stmt += "."
        if stmt in base:
            return base, True if (closer or modified_strip) else modified_strip
        return f"{base.rstrip()}\n\n{stmt}", True

    return text, modified_strip
