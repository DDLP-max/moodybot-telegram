# -*- coding: utf-8 -*-
"""Discovery protection — shared by Editor (Gold) and Inspector.

Invariant:
  Editor may remove bridges before discoveries.
  Discovery sentences are protected.

Paraphrase collapse:
  The response preserves the prompt's conclusion instead of contributing a new one.
  Routing question: Has the author already done Moody's job?
  If yes — rotate, deepen, challenge, reveal adjacent. Never summarize.
  Prison-cell standard: don't argue on the prompt's terms; escape the frame.
"""

from __future__ import annotations

import re
from typing import List, Set


def _words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text or "")


def _sentences(text: str) -> List[str]:
    body = re.sub(r"\s*🥃\s*", " ", text or "").strip()
    if not body:
        return []
    parts = re.split(r"(?<=[.!?])\s+", body.replace("\n\n", " ").replace("\n", " "))
    return [s.strip() for s in parts if s and s.strip()]


def _token_set(text: str) -> set:
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are",
        "was", "were", "be", "been", "that", "this", "it", "as", "with", "by",
        "from", "at", "they", "them", "their", "you", "your", "her", "his",
        "she", "he", "when", "who", "what", "why", "how", "not", "but",
    }
    return {w.lower() for w in _words(text) if len(w) > 2 and w.lower() not in stop}


def overlap_ratio(a: str, b: str) -> float:
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, min(len(sa), len(sb)))


# Stealable / mechanism-naming shapes (prompt or draft)
_DISCOVERY_SHAPE = re.compile(
    r"\b(exit that didn'?t|bad guy|giveaway|autobiographical|"
    r"comes with a warranty|isn'?t perfection|uncertainty that comes|"
    r"without carrying the guilt|memory has a new job|"
    r"rewrite(?:s|ing)? (?:it|the ending|the story) for|"
    r"preserve the self|softer story)\b|"
    r"^(every |nobody wants |the fantasy |people rarely |most breakups |"
    r"the story changes |the line about )\b",
    re.I,
)

# Soft bookends that often survive bad compression
_BOOKEND = re.compile(
    r"^(sure\.?|yeah\.?|right\.?|exactly\.?|ok\.?|okay\.?)$|"
    r"\blet (her|him|them) have\b|"
    r"\byou wanted forever\b",
    re.I,
)


def looks_like_discovery(sentence: str) -> bool:
    s = (sentence or "").strip()
    n = len(_words(s))
    if n < 6 or n > 40:
        return False
    if _BOOKEND.search(s) and n <= 12:
        return False
    if _DISCOVERY_SHAPE.search(s):
        # "softer story" alone is spear/bookend — need more meat
        if re.search(r"\bsofter story\b", s, re.I) and n < 12:
            return False
        return True
    # Contrast mechanism inside one sentence (wanted X / wanted Y + cost)
    if (
        re.search(r"\bwanted\b.+\bwanted\b", s, re.I)
        and re.search(r"\b(without|exit|guilt|bad|story|self)\b", s, re.I)
        and n >= 10
    ):
        return True
    return False


def prompt_has_discovery(user_message: str) -> bool:
    return any(looks_like_discovery(s) for s in _sentences(user_message or ""))


def discovery_sentences(text: str) -> List[str]:
    return [s for s in _sentences(text or "") if looks_like_discovery(s)]


def response_adds_discovery(user_message: str, response: str) -> bool:
    """True if response lands a discovery that isn't mostly the user's own line."""
    user = user_message or ""
    for s in _sentences(response or ""):
        if not looks_like_discovery(s):
            continue
        if overlap_ratio(s, user) < 0.55:
            return True
    return False


def paraphrase_collapse(user_message: str, response: str) -> bool:
    """
    True when the response preserves the prompt's conclusion instead of
    contributing a new one (author already did Moody's job; Moody stayed
    inside their frame and abridged it).
    """
    user = user_message or ""
    resp = response or ""
    if not prompt_has_discovery(user):
        return False
    if response_adds_discovery(user, resp):
        return False
    if overlap_ratio(resp, user) >= 0.48:
        return True
    ss = _sentences(resp)
    if ss and all((_BOOKEND.search(s) or len(_words(s)) <= 6) for s in ss):
        return True
    prompt_disc = discovery_sentences(user)
    if prompt_disc and ss and len(_words(resp)) <= 45:
        kept_disc = any(overlap_ratio(s, prompt_disc[0]) >= 0.55 for s in ss)
        if not kept_disc and any(_BOOKEND.search(s) for s in ss):
            return True
    return False


def protected_discovery_indices(draft_sentences: List[str]) -> Set[int]:
    """Indices Editor must not delete to satisfy brevity."""
    return {i for i, s in enumerate(draft_sentences) if looks_like_discovery(s)}
