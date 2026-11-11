# -*- coding: utf-8 -*-
"""X's standard post length. Premium long posts are a different permission.

Weights follow Twitter Text config v3: characters in the listed ranges
count as one, everything else counts as two, and a URL counts as 23.
@MoodyBotAI is not a Premium account, so a longer post is refused.
"""
from __future__ import annotations

import re

POST_LIMIT = 280
AUTONOMOUS_LIMIT = 200
_SCALE = 100
_DEFAULT_WEIGHT = 200
_URL_LENGTH = 23
_RANGES = (
    (0, 4351, 100),
    (8192, 8205, 100),
    (8208, 8223, 100),
    (8242, 8247, 100),
)
_URL = re.compile(r"https?://\S+", re.IGNORECASE)


def weighted_length(text: str) -> int:
    """Return the length X uses for the standard 280 cap."""
    source = text or ""
    total = 0
    cursor = 0
    for match in _URL.finditer(source):
        total += _span_weight(source[cursor:match.start()])
        total += _URL_LENGTH * _SCALE
        cursor = match.end()
    total += _span_weight(source[cursor:])
    return total // _SCALE


def fits_post(text: str) -> bool:
    return weighted_length(text) <= POST_LIMIT


def fits_autonomous(text: str) -> bool:
    return weighted_length(text) <= AUTONOMOUS_LIMIT


def fit_x_post(text: str, shorten=None, limit: int = POST_LIMIT) -> str:
    """Return a post that fits. `shorten` may rewrite once; trimming is the backstop."""
    cleaned = (text or "").strip()
    if weighted_length(cleaned) <= limit:
        return cleaned
    if shorten is not None:
        try:
            rewritten = str(shorten(cleaned) or "").strip()
        except Exception:
            rewritten = ""
        if rewritten and weighted_length(rewritten) <= limit:
            return rewritten
        if rewritten and weighted_length(rewritten) < weighted_length(cleaned):
            cleaned = rewritten
    return trim_to_post(cleaned, limit)


def trim_to_post(text: str, limit: int = POST_LIMIT) -> str:
    """Drop trailing sentences, then trailing words, until the text fits."""
    compact = " ".join((text or "").split())
    if weighted_length(compact) <= limit:
        return compact
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", compact) if part]
    kept = []
    for sentence in sentences:
        candidate = " ".join(kept + [sentence])
        if weighted_length(candidate) <= limit:
            kept.append(sentence)
            continue
        break
    if kept:
        return " ".join(kept)
    words = compact.split()
    while words and weighted_length(" ".join(words)) > limit:
        words.pop()
    return " ".join(words)


def _span_weight(fragment: str) -> int:
    return sum(_weight(ord(character)) for character in fragment)


def _weight(code: int) -> int:
    for start, end, weight in _RANGES:
        if start <= code <= end:
            return weight
    return _DEFAULT_WEIGHT
