# -*- coding: utf-8 -*-
"""Publishing eligibility is the authoritative engagement decision.

Structural checks and the conversation decision are one result. A mention
is required and is not sufficient. Keyword hits inside statements do not
make a post eligible.
"""
from __future__ import annotations


def classify_mention(
    tweet: dict,
    *,
    user_id: str,
    floor: str,
    already_replied: bool,
    context: dict | None = None,
    conversation: dict | None = None,
    complete=None,
) -> dict:
    """Return the one decision observation and publishing both use."""
    from x_integration.engagement import authoritative_decision

    decision = authoritative_decision(
        tweet,
        user_id=user_id,
        floor=floor,
        already_replied=already_replied,
        context=context,
        conversation=conversation,
        complete=complete,
    )
    return {
        "post_id": decision["post_id"],
        "author_id": decision["author_id"],
        "eligible": bool(decision["publish"]),
        "classification": decision["filter_classification"],
        "reason": decision["filter_reason"],
        "engagement": decision,
    }
