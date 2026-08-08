# -*- coding: utf-8 -*-
"""Closing strategy selection for MoodyBot recognition callbacks.

The model generates the actual callback text from conversation context.
This module only chooses the strategy and flags generic chatbot closers.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

ClosingStrategy = str  # RECOGNITION_CALLBACK | RITUAL_LINE | ACTION_LINE | SILENCE | NONE

GENERIC_FOLLOWUP_PATTERNS = [
    r"\bdo you want\b",
    r"\bwould you like\b",
    r"\bdoes that make sense\b",
    r"\bwhat do you want to explore\b",
    r"\bwhich aspect\b",
    r"\banything else\b",
    r"\bwhat are you actually asking\b",
    r"\bshould we go deeper\b",
    r"\bwant me to unpack\b",
    r"\bwant me to\b",
    r"\bexplore that further\b",
    r"\bexplain more\b",
    r"\bwhich aspect are you interested in\b",
    r"\bif you want\b",
    r"\bif you'?d like\b",
    r"\bsay the word\b",
    r"\bi can also\b",
    r"\bi can give you\b",
    r"\blet me know if\b",
    r"\bwe can go deeper\b",
    r"\bwant to unpack\b",
    r"\bdo you want examples\b",
    r"\bwould examples help\b",
    r"\bif you want examples\b",
]

CLOSER_INSTRUCTIONS = {
    "RECOGNITION_CALLBACK": (
        "Closing strategy: RECOGNITION_CALLBACK. "
        "If a closer is useful, end with one short generated recognition callback "
        "tied to this exchange’s subject and central insight. "
        "Invite the user to notice what shifted. "
        "Do not ask a generic chatbot follow-up or topic-routing menu question."
    ),
    "RITUAL_LINE": (
        "Closing strategy: RITUAL_LINE. "
        "Close with a ritual / poetic line if earned. No follow-up question."
    ),
    "ACTION_LINE": (
        "Closing strategy: ACTION_LINE. "
        "Close with a concrete next step. A recognition callback is optional; prefer action. "
        "Do not end with a generic chatbot follow-up question."
    ),
    "SILENCE": (
        "Closing strategy: SILENCE. "
        "Do not add a follow-up question. End cleanly. Another line would dilute it."
    ),
    "NONE": (
        "Closing strategy: NONE. "
        "No manufactured closer. Do not add a generic chatbot follow-up question."
    ),
}


def select_closing_strategy(
    *,
    user_message: str,
    created_reframe: bool = False,
    practical_request: bool = False,
    grief_or_trauma: bool = False,
    roast_mode: bool = False,
    technical_only: bool = False,
    missing_required_info: bool = False,
) -> ClosingStrategy:
    """Select a closing strategy. Questions are optional — never forced."""
    text = (user_message or "").lower()

    if missing_required_info:
        # Clarification belongs in the body, not as a fake recognition closer.
        return "NONE"

    if grief_or_trauma or any(
        w in text for w in ("grief", "died", "funeral", "i can't stop crying", "trauma")
    ):
        return "SILENCE"

    if roast_mode or text.startswith("/roast") or text.startswith("/savage"):
        return "NONE"

    if practical_request or any(
        p in text
        for p in (
            "what should i do",
            "should i reply",
            "what do i say",
            "what now",
            "how should i handle",
        )
    ):
        return "ACTION_LINE"

    if technical_only and not created_reframe:
        return "NONE"

    if any(p in text for p in ("/validate", "/velvet", "/numb", "/ghost")):
        return "RITUAL_LINE"

    # Recognition callback is the default *question* closer when insight work fits.
    if created_reframe or any(
        p in text
        for p in (
            "what does it mean",
            "why did",
            "how come",
            "is this normal",
            "culture",
            "pattern",
            "between",
            "influence",
            "relationship",
            "why do they",
            "what changed",
        )
    ):
        return "RECOGNITION_CALLBACK"

    return "NONE"


def closer_instruction(strategy: ClosingStrategy) -> str:
    """System-facing instruction for the selected strategy."""
    return CLOSER_INSTRUCTIONS.get(strategy, CLOSER_INSTRUCTIONS["NONE"])


def is_generic_followup(text: str) -> bool:
    """Return True if the closing text looks like a generic chatbot follow-up."""
    if not text:
        return False
    # Inspect last ~280 chars as the closer zone
    closer = text.strip()[-280:].lower()
    return any(re.search(pat, closer) for pat in GENERIC_FOLLOWUP_PATTERNS)


def validate_recognition_callback(question: str, subject_tokens: Optional[list] = None) -> Dict[str, bool]:
    """Lightweight quality gate for a candidate recognition callback."""
    q = (question or "").strip()
    subject_tokens = subject_tokens or []
    lower = q.lower()
    return {
        "is_question": q.endswith("?"),
        "single_sentence": q.count("?") <= 1 and q.count(".") <= 1,
        "not_generic": not is_generic_followup(q),
        "has_subject_callback": (
            not subject_tokens
            or any(tok.lower() in lower for tok in subject_tokens if len(tok) > 3)
        ),
        "brief": len(q.split()) <= 28,
    }


def diagnose_closing(user_message: str, response_text: str, **kwargs) -> Dict[str, str]:
    """Optional telemetry-friendly summary. Does not require logging response text."""
    strategy = select_closing_strategy(user_message=user_message, **kwargs)
    return {
        "closing_strategy": strategy.lower(),
        "generic_followup_detected": str(is_generic_followup(response_text)).lower(),
    }
