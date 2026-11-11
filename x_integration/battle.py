# -*- coding: utf-8 -*-
"""AI invitation context and an offline battle harness.

This module does not post to X. The persona drafter is the existing
mention path. A recovered question is passed through as a brief.
"""
from __future__ import annotations

import re

from x_integration.engagement import (
    DIRECT_CHALLENGE,
    authoritative_decision,
    read_post_text,
)
from x_integration.post_length import AUTONOMOUS_LIMIT, weighted_length

GROK_USER_ID = "1720665183188922368"
KNOWN_AI_IDS = frozenset({GROK_USER_ID})
KNOWN_AI_NAMES = frozenset({"grok"})
_QUESTION = re.compile(r"\?")
_SUPPLIED = re.compile(
    r"(?i)\b(?:grok says|here(?:'s| is)\s+grok(?:'s|’s)?\s+answer)\b"
)


def author_is_ai(author_id: str, username: str = "", automated: bool = False) -> bool:
    """Known identities and an explicit automation flag. A name alone is not enough."""
    if str(author_id or "") in KNOWN_AI_IDS:
        return True
    if str(username or "").strip().lower() in KNOWN_AI_NAMES:
        return True
    return bool(automated)


def recover_question(posts: list[dict], invitation: str) -> dict:
    """Find the question already in the thread. Never invent one."""
    from x_integration.engagement import _direct_invite

    prior = [post for post in posts if isinstance(post, dict)]
    question = None
    for post in prior:
        text = post.get("text") if isinstance(post.get("text"), str) else ""
        if _direct_invite(text):
            continue
        if _QUESTION.search(text):
            question = post
            break
    grok_answer = ""
    grok_id = ""
    if question is not None:
        for post in prior:
            if post is question:
                continue
            if author_is_ai(str(post.get("author_id") or ""), str(post.get("author_username") or "")):
                grok_answer = post.get("text") if isinstance(post.get("text"), str) else ""
                grok_id = str(post.get("id") or "")
                break
    if question is not None:
        return {
            "sufficient": True,
            "question_id": str(question.get("id") or ""),
            "question_text": question.get("text") if isinstance(question.get("text"), str) else "",
            "grok_id": grok_id,
            "grok_answer": grok_answer,
        }
    if _SUPPLIED.search(invitation or ""):
        return {
            "sufficient": True,
            "question_id": "",
            "question_text": invitation,
            "grok_id": "",
            "grok_answer": "",
        }
    return {
        "sufficient": False,
        "question_id": "",
        "question_text": "",
        "grok_id": "",
        "grok_answer": "",
    }


def battle_brief(recovered: dict) -> str:
    """Tell the existing drafter which question to answer. Do not assume another answer is wrong."""
    question = str(recovered.get("question_text") or "").strip()
    if not question:
        return ""
    return (
        "Answer this question directly in your own words. "
        "Do not copy another answer, and do not assume another answer is wrong. "
        "If evidence is missing, say so.\n"
        + question
    )


def draft_battle_reply(recovered: dict, invitation: str, conversation_id: str, complete) -> str:
    from x_integration.reply import draft_mention_reply

    text = draft_mention_reply(
        invitation,
        conversation_id,
        complete=complete,
        brief=battle_brief(recovered),
    )
    if weighted_length(text) > AUTONOMOUS_LIMIT:
        raise RuntimeError("battle draft exceeded the autonomous limit")
    return text


def evaluate_fixture(fixture: dict, *, user_id: str, complete, ledger=None) -> dict:
    """Run the real decision, recovery, drafter, and publish gate. Does not post."""
    posts = []
    for post in fixture.get("posts") or []:
        text, _complete, _source = read_post_text(post)
        item = dict(post)
        item["text"] = text
        posts.append(item)
    invitation = posts[-1]
    prior = posts[:-1]
    decision = authoritative_decision(
        invitation,
        user_id=user_id,
        floor="0",
        already_replied=bool(fixture.get("already_replied")),
        context={"posts": prior},
        conversation=fixture.get("conversation"),
        complete=complete,
    )
    recovered = {
        "sufficient": bool(decision.get("question_sufficient")),
        "question_id": decision.get("original_question_id") or "",
        "question_text": decision.get("question_text") or "",
        "grok_answer": decision.get("grok_answer") or "",
    }
    reply = ""
    drafted = False
    if decision.get("publish") and decision.get("classification") != "UNSAFE":
        reply = draft_battle_reply(
            recovered,
            invitation.get("text") or "",
            str(invitation.get("conversation_id") or invitation.get("id")),
            complete,
        )
        drafted = True
        grok_answer = str(recovered.get("grok_answer") or "").strip()
        if grok_answer and reply.strip() == grok_answer:
            decision["publish"] = False
            decision["reason"] = "copied_answer"
    if ledger is not None and decision.get("classification") == DIRECT_CHALLENGE:
        ledger.record_battle(
            decision,
            inviting_account=str(invitation.get("author_id") or ""),
            question_id=str(decision.get("original_question_id") or ""),
        )
    return {
        "post_id": str(invitation.get("id") or ""),
        "classification": decision.get("classification"),
        "confidence": decision.get("confidence"),
        "reason": decision.get("reason"),
        "action": decision.get("action"),
        "publish": bool(decision.get("publish")),
        "loop_outcome": decision.get("loop_outcome") or "",
        "question_id": decision.get("original_question_id") or "",
        "question_sufficient": bool(decision.get("question_sufficient")),
        "safety_flags": list(decision.get("safety_flags") or []),
        "reply": reply,
        "drafted": drafted,
        "objective": decision.get("objective") or "",
    }
