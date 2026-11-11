# -*- coding: utf-8 -*-
"""One mention decision for observation and publishing.

A mention of @MoodyBotAI is required before a reply is allowed. It is not
enough on its own. Uncertain intent is left for review and is not published.
"""
from __future__ import annotations

import re

_MENTION = re.compile(r"(?i)(?<!\w)@MoodyBotAI\b")
_REQUEST = re.compile(
    r"(?i)(?:"
    r"\?|"
    r"\bwhat(?:'s|\s+(?:is|are|should|do|would|can|about))\b|"
    r"\bwhy\b|"
    r"\bhow\s+(?:do|should|can|would|to|did)\b|"
    r"\b(?:can|could|would|will)\s+you\b|"
    r"\bshould\s+i\b|"
    r"\b(?:tell me|help me|weigh in|say more|go on|elaborate)\b|"
    r"\byour\s+(?:take|thoughts|advice|view|opinion)\b|"
    r"\bplease\b"
    r")"
)
_FOLLOW_UP = re.compile(
    r"(?i)\b(?:say more|go on|what else|another|elaborate|continue|your turn|follow up)\b"
)
_CONTRIBUTION = re.compile(
    r"(?i)\b(?:stay|keep going|focus on|remember|hang in|one (?:small )?step|"
    r"progress|momentum|you(?:'ve| have) got|don't give up)\b"
)
_SPAM = re.compile(
    r"(?i)\b(?:giveaway|follow me|check out my|subscribe|promo code|airdrop|dm me)\b"
)


def classify_mention(
    tweet: dict,
    *,
    user_id: str,
    floor: str,
    already_replied: bool,
) -> dict:
    """Return one eligibility decision. `eligible` is true only for a request."""
    post_id = str(tweet.get("id") or "").strip()
    author_id = str(tweet.get("author_id") or "").strip()
    username = str(tweet.get("author_username") or "")
    text = tweet.get("text") if isinstance(tweet.get("text"), str) else ""
    parent_author = str(tweet.get("parent_author_id") or "").strip()
    body = _MENTION.sub(" ", text)
    body = re.sub(r"(?i)@\w+", " ", body)
    words = body.split()

    def decision(classification: str, reason: str, eligible: bool = False) -> dict:
        return {
            "post_id": post_id,
            "author_id": author_id,
            "eligible": eligible,
            "classification": classification,
            "reason": reason,
        }

    if not post_id.isdigit():
        return decision("invalid_id", "invalid_id")
    if floor.isdigit() and int(post_id) <= int(floor):
        return decision("historical", "historical")
    if user_id and author_id == user_id:
        return decision("own_post", "own_post")
    if username.lower().endswith("bot") and author_id != user_id:
        return decision("other_bot", "other_bot")
    if already_replied:
        return decision("already_replied", "duplicate_parent")
    if not _MENTION.search(text):
        return decision("not_mentioned", "not_mentioned")
    if not words:
        return decision("empty", "empty")
    if _SPAM.search(body):
        return decision("spam", "spam")
    requested = _REQUEST.search(body) is not None
    replying_to_bot = bool(user_id) and parent_author == user_id
    if requested and replying_to_bot and _FOLLOW_UP.search(body):
        return decision("eligible", "follow_up", True)
    if requested and replying_to_bot:
        return decision("eligible", "follow_up", True)
    if requested:
        return decision("eligible", "direct_request", True)
    if replying_to_bot or _CONTRIBUTION.search(body):
        return decision("not_requested", "contribution")
    return decision("uncertain", "review")
