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


# Drawer shortcuts — sometimes brilliant, often favorite-mechanism inserts
_DRAWER_SHORTCUT = re.compile(
    r"\bwhat they actually want\b|"
    r"\bwhat (he|she|people) actually (want|wanted|need|needed)\b|"
    r"\bthe real (problem|reason|issue|engine|question|fear) is\b|"
    r"\bit isn'?t (really )?about\b|"
    r"\bthat'?s not (really )?about\b|"
    r"\bthe (real )?problem isn'?t\b",
    re.I,
)

# EI favorite drawers that steal the topic
_REJECTION_FEAR_DRAWER = re.compile(
    r"\bescape hatch\b|\bbeing refused\b|\bturned down\b|"
    r"\bfear of rejection\b|\brisk being refused\b|"
    r"\bvisibility means\b|\bcan be (turned down|laughed at|ignored)\b",
    re.I,
)

_EFFORT_TOPIC = re.compile(
    r"\beffort\b|\bmake a plan\b|\bfollow through\b|\bexecut|"
    r"\bthoughtful\b|\battractive quality\b",
    re.I,
)

_INVENTED_SOCIOLOGY = re.compile(
    r"\bsame people (complaining|who complain)\b|"
    r"\balso the ones who never\b|"
    r"\beveryone (is|who'?s) (single|childless)\b",  # only if response invents blame not in prompt
    re.I,
)


def drawer_shortcut_present(response: str) -> bool:
    return bool(_DRAWER_SHORTCUT.search(response or ""))


def mechanism_drift(user_message: str, response: str) -> bool:
    """
    True when the response introduces a plausible emotional mechanism that
    isn't the strongest fit for THIS prompt (favorite-drawer insert).

    Not architecture — lens refinement. Not always wrong — often just not best.
    """
    user = user_message or ""
    resp = response or ""
    if not resp.strip():
        return False

    # Effort / evidence prompt → rejection-fear pivot
    if _EFFORT_TOPIC.search(user) and _REJECTION_FEAR_DRAWER.search(resp):
        # Drift if effort is no longer the spine, or drawer shortcut opens the pivot
        effort_in_resp = bool(re.search(r"\beffort\b", resp, re.I))
        if _DRAWER_SHORTCUT.search(resp) or not effort_in_resp:
            return True
        # "what they actually want" under an effort prompt = classic EI steal
        if re.search(r"\bwhat they actually want\b", resp, re.I):
            return True

    # Invented sociology not grounded in the prompt
    if _INVENTED_SOCIOLOGY.search(resp) and not _INVENTED_SOCIOLOGY.search(user):
        # Only count as drift when paired with a drawer shortcut or topic steal
        if _DRAWER_SHORTCUT.search(resp) or _REJECTION_FEAR_DRAWER.search(resp):
            return True

    return False


def mechanism_drift_examples(user_message: str) -> List[str]:
    """PASS lines grounded in common drifted prompts."""
    if _EFFORT_TOPIC.search(user_message or ""):
        return [
            "✓ Effort isn't attractive because it's romantic. It's attractive because it's evidence.",
            "✓ Effort is attractive because it answers a question words never can: "
            "are you willing to inconvenience yourself for me?",
            "✓ Attention is cheap. Effort isn't. That's why people trust one more than the other.",
        ]
    return [
        "✓ Stay on the prompt's strongest mechanism — not EI's favorite drawer.",
        "✓ That's like saying a prison cell is just a room.",
    ]


def protected_discovery_indices(draft_sentences: List[str]) -> Set[int]:
    """Indices Editor must not delete to satisfy brevity."""
    return {i for i, s in enumerate(draft_sentences) if looks_like_discovery(s)}

