# -*- coding: utf-8 -*-
"""Persistent opt-out. Checked before classification and again before a post.

A clear instruction directed at MoodyBot is enough. Quoted text, hypotheticals,
and an incidental "stop" are not. Nothing here sends a confirmation reply.
"""
from __future__ import annotations

import re
from typing import Optional


_BOT = re.compile(r"(?i)(?<!\w)@MoodyBotAI\b")
_QUOTED = re.compile(r"(?:\"[^\"]*\"|“[^”]*”|«[^»]*»)")
_HYPOTHETICAL = re.compile(
    r"(?i)\b(?:if|when|suppose|supposing|imagine|what if|hypothetically|"
    r"someone says|if i say)\b"
)
_NEGATED_STOP = re.compile(r"(?i)\b(?:do not|don't|dont|never|no)\s+stop\b")
_BARE_STOP = re.compile(r"(?i)^(?:please\s+)?stop[.!]*$")
_PHRASES = (
    ("stop_replying", re.compile(r"(?i)\bstop\s+replying(?:\s+to\s+me)?\b")),
    ("opt_out", re.compile(r"(?i)\bopt[\s-]?out\b")),
    ("unsubscribe", re.compile(r"(?i)\bunsubscribe\b")),
    ("leave_alone", re.compile(r"(?i)\bleave\s+me\s+alone\b")),
    ("do_not_reply", re.compile(r"(?i)\b(?:do not|don't|dont)\s+reply(?:\s+to\s+me)?\b")),
    ("do_not_contact", re.compile(r"(?i)\b(?:do not|don't|dont)\s+contact\s+me\b")),
    ("remove_me", re.compile(r"(?i)\bremove\s+me(?:\s+from\s+your\s+replies)?\b")),
)


def detect_opt_out(text: str, *, directed: Optional[bool] = None) -> str:
    """Return a reason code, or an empty string when this is not an opt-out."""
    unquoted = _QUOTED.sub(" ", text or "")
    addressed = _BOT.search(unquoted) is not None if directed is None else directed
    if not addressed:
        return ""
    if _HYPOTHETICAL.search(unquoted):
        return ""
    residue = _BOT.sub(" ", unquoted)
    residue = re.sub(r"\s+", " ", residue).strip(" \t\r\n.,!?")
    if _NEGATED_STOP.search(residue):
        return ""
    for reason, pattern in _PHRASES:
        if pattern.search(residue):
            return reason
    if _BARE_STOP.match(residue):
        return "stop"
    return ""


def screen_mention(book, tweet: dict) -> Optional[dict]:
    """Record or enforce opt-out before the ordinary classifier runs."""
    from x_integration.engagement import read_post_text

    text, _complete, _source = read_post_text(tweet)
    author_id = str(tweet.get("author_id") or "").strip()
    if not author_id.isdigit():
        return None
    reason = detect_opt_out(text)
    if reason:
        book.record_opt_out(
            author_id,
            str(tweet.get("author_username") or ""),
            str(tweet.get("id") or ""),
            reason,
        )
        book.note_opt_out_suppression(author_id, str(tweet.get("id") or ""), "command")
        return _decision(tweet, reason)
    if book.is_opted_out(author_id):
        book.note_opt_out_suppression(author_id, str(tweet.get("id") or ""), "eligibility")
        return _decision(tweet, "suppressed")
    return None


def screen_author(book, author_id: str, username: str, post_id: str, text: str) -> str:
    """Same gate for a delivery that is already a Mention. Empty means continue."""
    author_id = str(author_id or "").strip()
    if not author_id.isdigit():
        return ""
    reason = detect_opt_out(text or "")
    if reason:
        book.record_opt_out(author_id, username, post_id, reason)
        book.note_opt_out_suppression(author_id, post_id, "command")
        return "opt_out"
    if book.is_opted_out(author_id):
        book.note_opt_out_suppression(author_id, post_id, "eligibility")
        return "opt_out"
    return ""


def _decision(tweet: dict, reason: str) -> dict:
    post_id = str(tweet.get("id") or "")
    author_id = str(tweet.get("author_id") or "")
    engagement = {
        "post_id": post_id,
        "author_id": author_id,
        "author_username": str(tweet.get("author_username") or ""),
        "conversation_id": str(tweet.get("conversation_id") or post_id),
        "classification": "OPT_OUT",
        "confidence": 1.0,
        "reason": "opt_out",
        "respond": False,
        "action": "skip",
        "mode": "C",
        "objective": "none",
        "safety_flags": [],
        "context_ids": [],
        "model": "rules",
        "text_complete": True,
        "text_source": "text",
        "publish": False,
    }
    return {
        "post_id": post_id,
        "author_id": author_id,
        "eligible": False,
        "classification": "opt_out",
        "reason": reason or "opt_out",
        "engagement": engagement,
    }
