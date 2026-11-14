# -*- coding: utf-8 -*-
"""The user's explicit request outranks style length.

Safety and the channel's real delivery limit still apply.
A short prompt is not a short job. A simple question is not an essay.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
}

_COUNT = re.compile(
    r"\b(?:name|list|give|provide|share|offer)\s+(?:me\s+)?"
    r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|fifteen|twenty)\s+"
    r"(?:distinct\s+|different\s+|giant\s+|separate\s+)?"
    r"(companies|reasons|examples|ways|points|items|things|steps|businesses)\b",
    re.I,
)
_ONE_SENTENCE = re.compile(r"\b(?:in\s+)?one sentence\b", re.I)
_ONE_EACH = re.compile(r"\bone sentence each\b", re.I)
_YES_NO = re.compile(r"^(?:yes or no\b)", re.I)
_THOROUGH = re.compile(
    r"\b(thoroughly|in detail|walk me through|explain how|explain the)\b",
    re.I,
)
_DISCUSS = re.compile(
    r"\b(?:discuss|cover|including|address)\s+([^.?\n]{8,180})",
    re.I,
)

# Generation ceilings. These are model limits, not a style budget.
OUTPUT_TOKEN_CEILING = 2000
CONTINUATION_TOKEN_CEILING = 1500


@dataclass(frozen=True)
class UserRequest:
    kind: str  # counted | one_sentence | yes_no | thorough | open
    count: int = 0
    unit: str = ""
    one_sentence_each: bool = False
    dimensions: tuple = ()


def _number(token: str) -> int:
    token = (token or "").strip().lower()
    if token.isdigit():
        value = int(token)
        return value if 1 <= value <= 20 else 0
    return _NUMBER.get(token, 0)


def parse_user_request(text: str) -> UserRequest:
    """Read an explicit output request. Prompt length is not an input."""
    raw = (text or "").strip()
    match = _COUNT.search(raw)
    if match:
        count = _number(match.group(1))
        if count:
            return UserRequest(
                "counted",
                count=count,
                unit=match.group(2).lower(),
                one_sentence_each=bool(_ONE_EACH.search(raw)),
            )
    if _ONE_SENTENCE.search(raw):
        return UserRequest("one_sentence")
    if _YES_NO.search(raw):
        return UserRequest("yes_no")
    dimensions = ()
    discussed = _DISCUSS.search(raw)
    if discussed:
        parts = [
            part.strip(" .")
            for part in re.split(r",|\band\b", discussed.group(1))
            if part.strip(" .")
        ]
        dimensions = tuple(part for part in parts if 0 < len(part.split()) <= 6)[:6]
    if _THOROUGH.search(raw) or len(dimensions) >= 2:
        return UserRequest("thorough", dimensions=dimensions)
    return UserRequest("open")


def request_guidance(text: str) -> str:
    """Turn instruction. It overrides shape, SNAP, and one-beat length talk."""
    spec = parse_user_request(text)
    header = (
        "\nUSER REQUEST (overrides shape, SNAP, one-beat, sentence caps, and word budgets):\n"
        "Safety and the channel's real delivery limit still apply. "
        "Personality is the voice of the answer. It is not permission to drop what they asked for. "
        "Do not infer the job from how short the prompt is. "
        "Do not pad a simple question into an essay.\n"
    )
    if spec.kind == "counted":
        each = " One sentence each." if spec.one_sentence_each else ""
        return header + (
            f"Deliver exactly {spec.count} distinct {spec.unit}.{each} "
            "Do not stop early. Do not replace the list with one observation. "
            "Predictions and judgments are opinions, not established facts.\n"
        )
    if spec.kind == "one_sentence":
        return header + "Exactly one sentence. Put the answer in it. Do not add a second.\n"
    if spec.kind == "yes_no":
        return (
            header
            + "Answer directly. Add an explanation only when it earns its place.\n"
        )
    if spec.kind == "thorough":
        extra = ""
        if spec.dimensions:
            extra = " Cover each of these: " + "; ".join(spec.dimensions) + "."
        return header + (
            "Answer every part they named, with enough detail that the question is actually answered."
            + extra
            + " Do not omit a requested dimension to sound sharper.\n"
        )
    return header + (
        "Answer the question at its natural length. "
        "A short question can take a short answer. Do not invent a paragraph quota.\n"
    )


def content_is_protected(text: str) -> bool:
    """An explicit multi-part request must survive formatting."""
    return parse_user_request(text).kind in {"counted", "thorough"}


def delivered_item_count(text: str) -> int:
    body = re.sub(r"\s*🥃\s*$", "", (text or "").strip())
    numbered = re.findall(r"(?m)^\s*(?:\d+[\).\:]|[-•])\s+\S", body)
    if len(numbered) >= 2:
        return len(numbered)
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", body) if part.strip()]
    return len(parts)


def completion_gap(user_message: str, text: str) -> str:
    """One regeneration instruction when a requested count is missing. Empty if met."""
    spec = parse_user_request(user_message)
    if spec.kind != "counted" or spec.count <= 0:
        return ""
    got = delivered_item_count(text)
    if got >= spec.count:
        return ""
    each = " One sentence each." if spec.one_sentence_each else ""
    return (
        f"The draft delivered {got} items. The user asked for exactly {spec.count} "
        f"distinct {spec.unit}.{each} Return the complete answer with every requested item. "
        "Do not summarize the list into fewer items. Keep the same voice. "
        "Predictions stay opinions."
    )
