# -*- coding: utf-8 -*-
"""Landing selection — which single ending mechanism wins.

Chase inevitable, not memorable.
The ending must be earned. Not generated.

Possible endings (only ONE wins):
  BODY_ENDS_RESPONSE  — body already landed; stop writing
  SIGNATURE_LINE      — discovered higher-order insight (optional)
  RECOGNITION_CALLBACK — user's authorial language returns
  ACTION
  SILENCE

NO_SIGNATURE_FOUND is success — not a failure to manufacture profundity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from signature_language import (
    extract_signature_language,
    remember_signature_use,
    transform_signature_callback,
)
from signature_line import (
    body_already_lands,
    craft_signature_line,
    ensure_signature_line,
    generate_signature_line,
    last_line_is_signature,
    validate_signature_line,
)

LandingType = str

LANDING_ENGINE_VERSION = "earned-ending-v1"

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


def validate_landing(closer: str) -> Tuple[bool, str]:
    """Hard rejection gate for landings. Returns (ok, reason)."""
    s = (closer or "").strip()
    if not s:
        return True, "empty"
    lower = s.lower()
    if any(re.search(pat, lower) for pat in BROKEN_CLOSER_PATTERNS):
        return False, "REJECTED:malformed_topic_staple"
    if lower.startswith("what about ") and " looks " in lower:
        return False, "REJECTED:what_about_looks"
    if lower.startswith("what about ") and "hate" in lower:
        return False, "REJECTED:what_about_hate_stack"
    if re.search(r"now that you've seen it named\??$", lower):
        return False, "REJECTED:seen_it_named_template"
    if re.search(
        r"\b(?:feminists?|women|men|porn|dirty talk)\b.+\b(?:looks different|seen it named)\b",
        lower,
    ):
        return False, "REJECTED:topic_noun_staple"
    return True, "ok"


def is_grammatical_english(text: str) -> bool:
    """Lightweight gate — reject obviously broken AI-stapled closers."""
    s = (text or "").strip()
    if not s:
        return False
    if len(s.split()) < 3:
        return False
    ok, _reason = validate_landing(s)
    if not ok:
        return False
    lower = s.lower()
    # Must end in . ! or ?
    if s[-1] not in ".!?":
        return False
    # Reject doubled function-words / broken stacks
    if re.search(r"\b(\w+)\s+\1\b", lower):
        return False
    return True


def strip_malformed_closers(text: str) -> str:
    """Nuclear strip — remove banned closer sentences anywhere near the ending."""
    out = (text or "").strip()
    if not out:
        return out
    if not re.search(
        r"seen it named|what about .+ looks different|what about .+\bhate\b",
        out,
        flags=re.IGNORECASE,
    ):
        return out
    sentences = re.split(r"(?<=[.!?])\s+", out)
    kept = []
    for s in sentences:
        ok, _ = validate_landing(s)
        if ok and "seen it named" not in s.lower():
            kept.append(s)
    return " ".join(kept).strip() if kept else out


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
    """Compat wrapper — Signature Line is the authoritative statement ending."""
    return craft_signature_line(user_message, body)


def craft_recognition_observation(body: str) -> Optional[str]:
    """Observation landings defer to Signature Line extraction."""
    return craft_signature_line("", body)


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
    """Evaluate body first. Only attempt an ending if the body has not landed."""
    um = (user_message or "").lower()
    signatures = extract_signature_language(user_message)

    if missing_info:
        return LandingDecision("SILENCE", False, "clarification belongs in the body")

    if grief or selected_command in {"/ghost", "/numb"}:
        return LandingDecision("SILENCE", False, "grief/weight")

    if roast or selected_command in {"/roast", "/savage", "/cut"}:
        return LandingDecision("SILENCE", False, "killshot should stand")

    if technical:
        return LandingDecision("SILENCE", False, "technical — stop")

    if practical or any(
        p in um
        for p in ("what should i do", "what do i say", "how should i handle", "what now")
    ):
        return LandingDecision("ACTION", False, "practical request")

    authorial_hooks = (
        "stretch", "stretched", "carrying", "cracked", "got stretched",
        "the room changed", "room changed",
    )
    if signatures.protected and any(s in um for s in authorial_hooks):
        return LandingDecision(
            "RECOGNITION_CALLBACK",
            True,
            "authorial language returns as callback",
        )

    # Highest-priority writer move: stop when the body is already finished
    if body and body_already_lands(body):
        return LandingDecision(
            "BODY_ENDS_RESPONSE",
            False,
            "body already landed — stop writing",
        )

    # Opportunity only — discovery may still return NO_SIGNATURE_FOUND
    return LandingDecision(
        "SIGNATURE_LINE",
        False,
        "attempt discovery; stop if none earned",
    )


def apply_landing(
    text: str,
    user_message: str,
    decision: LandingDecision,
    *,
    conversation_id: str = "",
    plan: Any = None,
) -> Tuple[str, bool]:
    """Apply exactly one landing. Signature Line is generated from the body."""
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

    def _finish(out: str, modified: bool) -> Tuple[str, bool]:
        cleaned = strip_malformed_closers(out)
        return cleaned, modified or cleaned != (out or "").strip()

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
            return _finish(base, True)
        return _finish(
            (base if modified_strip or closer == "" else text),
            modified_strip or bool(closer.endswith("?") if closer else False),
        )

    if landing == "ACTION":
        base = body or text
        if closer and (closer.endswith("?") or not would_keep_if_nobody_could_reply(closer)):
            return _finish(_strip_trailing_question(base), True)
        return _finish(text if not modified_strip else base, modified_strip)

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
            return _finish(text, False)

        q = craft_callback_question(user_message, conversation_id=conversation_id)
        base = _strip_trailing_question(body or text)
        if not q:
            # Do not manufacture a Signature Line to replace a failed callback
            return _finish(base, True if modified_strip or closer else False)
        if q in base:
            return _finish(base, True)
        return _finish(f"{base.rstrip()}\n\n{q}", True)

    if landing == "BODY_ENDS_RESPONSE":
        base = _strip_trailing_question(body or text)
        # Strip any manufactured closer; body is the ending
        return _finish(base, True if (closer or modified_strip) else False)

    if landing in {
        "SIGNATURE_LINE",
        "RECOGNITION_STATEMENT",
        "RECOGNITION_OBSERVATION",
    }:
        base = _strip_trailing_question(body or text)

        # Re-check: body may already be finished
        if body_already_lands(base):
            return _finish(base, True if (closer or modified_strip) else False)

        # Discovery only — NO_SIGNATURE_FOUND is success
        out, mod, sig = ensure_signature_line(base, user_message, plan=plan)
        if sig and last_line_is_signature(out, user_message=user_message):
            return _finish(out, True if (mod or closer or modified_strip) else mod)

        # Discovery failed or deletion test stripped it — body ends the response
        return _finish(base, True if (closer or modified_strip or mod) else False)

    return _finish(text, modified_strip)
