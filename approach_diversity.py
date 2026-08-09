# -*- coding: utf-8 -*-
"""Approach diversity — craft check, not a routing layer.

Same mechanism. Different authentic rhetorical entries and landings.
Used by regression tests (and optional live batch review).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple

# Opening moves EI (and other lenses) may use without changing the mechanism
OPENING_MOVES = (
    "observation",
    "contradiction",
    "image",
    "irony",
    "reversal",
    "relocation",  # "isn't really about X" — valid, but not the only door
    "other",
)

# Soft detectors — heuristics for batch review, not generation selectors
_RELOCATION = re.compile(
    r"\b(isn'?t|is not|aren'?t|are not)\s+really\s+about\b|"
    r"\bnot\s+(really\s+)?about\b.+\bit'?s\b",
    re.I,
)
_OBSERVATION = re.compile(
    r"^(people usually|people only|most people|you can tell|"
    r"the tell is|watch what|notice how)\b",
    re.I,
)
_CONTRADICTION = re.compile(
    r"^(funny|odd|strange|weird)\s+(thing|part)|"
    r"\bthe irony is\b|"
    r"^it always feels like\b",
    re.I,
)
_IMAGE = re.compile(
    r"\b(only works if|like a|sounds like|looks like|feels like a)\b",
    re.I,
)
_IRONY = re.compile(
    r"\b(keep repeating|have to keep|the moment you|"
    r"stopped being|probably stopped)\b",
    re.I,
)
_REVERSAL = re.compile(
    r"\b(tells you (far )?more about|far more about the speaker|"
    r"reveals the speaker|about the (man|woman|person) (saying|doing))\b",
    re.I,
)

_ENDING_REVEAL_SPEAKER = re.compile(
    r"\b(reveal(s|ing)? the speaker|about the speaker|"
    r"mirror was pointed|confession)\b",
    re.I,
)


def first_sentence(text: str) -> str:
    body = (text or "").strip()
    if not body:
        return ""
    para = re.split(r"\n\s*\n+", body)[0].strip()
    parts = re.split(r"(?<=[.!?])\s+", para)
    return (parts[0] if parts else para).strip()


def last_substantive_sentence(text: str) -> str:
    body = re.sub(r"\s*🥃\s*", " ", text or "").strip()
    if not body:
        return ""
    paras = [p for p in re.split(r"\n\s*\n+", body) if p.strip()]
    last = paras[-1] if paras else body
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", last) if s.strip()]
    return parts[-1] if parts else last


def classify_opening_move(text: str) -> str:
    """Heuristic label for the rhetorical entry — not a routing decision."""
    first = first_sentence(text)
    if not first:
        return "other"
    if _RELOCATION.search(first):
        return "relocation"
    if _OBSERVATION.search(first):
        return "observation"
    if _CONTRADICTION.search(first):
        return "contradiction"
    if _REVERSAL.search(first):
        return "reversal"
    if _IRONY.search(first):
        return "irony"
    if _IMAGE.search(first):
        return "image"
    return "other"


def ending_is_reveal_speaker(text: str) -> bool:
    return bool(_ENDING_REVEAL_SPEAKER.search(last_substantive_sentence(text)))


def opening_distribution(samples: Iterable[str]) -> Dict[str, int]:
    return dict(Counter(classify_opening_move(s) for s in samples))


def dominant_share(dist: Dict[str, int]) -> Tuple[Optional[str], float]:
    total = sum(dist.values())
    if not total:
        return None, 0.0
    move, n = max(dist.items(), key=lambda kv: kv[1])
    return move, n / total


def openings_too_convergent(
    samples: List[str],
    *,
    max_dominant_share: float = 0.6,
    min_samples: int = 5,
) -> bool:
    """True when one opening move dominates a same-lens batch."""
    if len(samples) < min_samples:
        return False
    _, share = dominant_share(opening_distribution(samples))
    return share >= max_dominant_share


def endings_too_convergent(
    samples: List[str],
    *,
    max_reveal_share: float = 0.7,
    min_samples: int = 5,
) -> bool:
    """True when endings almost always resolve as 'revealing the speaker'."""
    if len(samples) < min_samples:
        return False
    hits = sum(1 for s in samples if ending_is_reveal_speaker(s))
    return (hits / len(samples)) >= max_reveal_share
