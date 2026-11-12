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


MAX_CHAIN_DEPTH = 6
MAX_CHAIN_LOOKUPS = 4
_CHAIN_STATUS = {
    "deleted": "deleted_parent",
    "protected": "protected_parent",
    "missing": "missing_parent",
}


def walk_reply_chain(
    start: dict,
    index: dict,
    fetch=None,
    *,
    max_depth: int = MAX_CHAIN_DEPTH,
    max_lookups: int = MAX_CHAIN_LOOKUPS,
) -> dict:
    """Follow in_reply_to ids toward the root. Depth and lookups are capped."""
    posts = []
    seen = {str(start.get("id") or "")}
    parent_id = str(start.get("parent_id") or "")
    lookups = 0
    stop = ""
    depth = 0
    while parent_id and depth < max_depth:
        if parent_id in seen:
            stop = "cycle"
            break
        seen.add(parent_id)
        post = index.get(parent_id)
        if post is None:
            if fetch is None:
                stop = "missing_parent"
                break
            if lookups >= max_lookups:
                stop = "lookup_budget"
                break
            lookups += 1
            fetched = fetch(parent_id)
            if not isinstance(fetched, dict) or not str(fetched.get("id") or ""):
                stop = "missing_parent"
                break
            post = fetched
            index[str(post.get("id") or parent_id)] = post
        status = str(post.get("status") or "")
        if status in _CHAIN_STATUS:
            stop = _CHAIN_STATUS[status]
            break
        posts.append(post)
        parent_id = str(post.get("parent_id") or "")
        depth += 1
    if parent_id and not stop and depth >= max_depth:
        stop = "depth_limit"
    return {"posts": posts, "stop": stop, "lookups": lookups}


def trace_question(tweet: dict, posts: list, *, fetch=None) -> dict:
    """The human question this invitation answers. Grok's answer is not a question."""
    from question_scope import extract_questions

    index = {}
    for post in posts:
        if isinstance(post, dict) and str(post.get("id") or ""):
            index[str(post.get("id"))] = post
    current_id = str(tweet.get("id") or "")
    stored = dict(index.get(current_id) or {})
    current = {key: value for key, value in tweet.items() if key != "context_posts"}
    if stored.get("text"):
        current["text"] = stored["text"]
        current["text_complete"] = stored.get("text_complete", True)
    for key in ("parent_id", "author_id", "author_username", "conversation_id"):
        if not current.get(key) and stored.get(key):
            current[key] = stored[key]
    if current_id:
        index[current_id] = current
    reply_parent = current_id
    conversation_id = str(current.get("conversation_id") or "")
    empty = {
        "sufficient": False,
        "question_id": "",
        "question_text": "",
        "question_author_id": "",
        "question_conversation_id": conversation_id,
        "reply_parent_id": reply_parent,
        "question_origin": "",
        "reason": "insufficient_context",
        "grok_id": "",
        "grok_answer": "",
    }
    own = _current_questions(current)
    if own:
        return _recovered(current, own, "current", reply_parent, conversation_id, "", "")
    chain = walk_reply_chain(current, index, fetch)
    grok_answer = ""
    grok_id = ""
    truncated = False
    for post in chain["posts"]:
        if author_is_ai(str(post.get("author_id") or ""), str(post.get("author_username") or "")):
            if not grok_id:
                grok_answer = post.get("text") if isinstance(post.get("text"), str) else ""
                grok_id = str(post.get("id") or "")
            continue
        if post.get("author_is_bot"):
            continue
        if post.get("text_complete") is False:
            truncated = True
            continue
        questions = _human_questions(post)
        if questions:
            found = _recovered(
                post, questions, "earlier", reply_parent, conversation_id, grok_id, grok_answer
            )
            return found
    reason = chain["stop"] or ("incomplete_text" if truncated else "insufficient_context")
    if not current.get("parent_id") and not chain["posts"]:
        loose = _single_unlinked_question(index, current_id)
        if loose is False:
            reason = "ambiguous_question"
        elif loose is not None:
            post, questions = loose
            if not grok_id:
                for item in index.values():
                    if str(item.get("id") or "") == current_id:
                        continue
                    if author_is_ai(str(item.get("author_id") or ""), str(item.get("author_username") or "")):
                        grok_answer = item.get("text") if isinstance(item.get("text"), str) else ""
                        grok_id = str(item.get("id") or "")
                        break
            return _recovered(
                post, questions, "earlier", reply_parent, conversation_id, grok_id, grok_answer
            )
    empty["reason"] = reason
    empty["grok_id"] = grok_id
    empty["grok_answer"] = grok_answer
    preset = str(tweet.get("chain_stop") or "")
    if preset and reason == "missing_parent":
        empty["reason"] = preset
    return empty


def _recovered(post, questions, origin, reply_parent, conversation_id, grok_id, grok_answer) -> dict:
    return {
        "sufficient": True,
        "question_id": str(post.get("id") or ""),
        "question_text": " ".join(item["text"] for item in questions),
        "question_author_id": str(post.get("author_id") or ""),
        "question_conversation_id": str(post.get("conversation_id") or conversation_id),
        "reply_parent_id": reply_parent,
        "question_origin": origin,
        "reason": "",
        "grok_id": grok_id,
        "grok_answer": grok_answer,
    }


def _current_questions(post: dict) -> list:
    from question_scope import extract_questions

    text = post.get("text") if isinstance(post.get("text"), str) else ""
    found = extract_questions(text, source_post_id=str(post.get("id") or ""), channel="x")
    if found.get("needs_context"):
        return []
    return [
        item for item in found.get("questions") or []
        if item.get("self_contained") and item.get("origin") == "current"
    ]


def _human_questions(post: dict) -> list:
    from question_scope import extract_questions

    text = post.get("text") if isinstance(post.get("text"), str) else ""
    found = extract_questions(text, source_post_id=str(post.get("id") or ""), channel="direct")
    return [
        item for item in found.get("questions") or []
        if item.get("self_contained") and item.get("origin") == "current"
    ]


def _single_unlinked_question(index: dict, current_id: str):
    """Used when the mention is not a reply. More than one human question is ambiguous."""
    found = []
    for post in index.values():
        if str(post.get("id") or "") == current_id:
            continue
        if author_is_ai(str(post.get("author_id") or ""), str(post.get("author_username") or "")):
            continue
        if post.get("author_is_bot") or post.get("text_complete") is False:
            continue
        questions = _human_questions(post)
        if questions:
            found.append((post, questions))
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        return False
    return None


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

    question = str(recovered.get("question_text") or "").strip()
    if recovered.get("question_origin") == "earlier" and question:
        source = question
        brief = ""
    else:
        source = invitation
        brief = battle_brief(recovered)
    text = draft_mention_reply(
        source,
        conversation_id,
        complete=complete,
        brief=brief,
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
        "question_origin": decision.get("question_origin") or "",
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
        "question_text": decision.get("question_text") or "",
        "question_author_id": decision.get("question_author_id") or "",
        "question_conversation_id": decision.get("question_conversation_id") or "",
        "reply_parent_id": decision.get("reply_parent_id") or "",
        "question_origin": decision.get("question_origin") or "",
        "question_sufficient": bool(decision.get("question_sufficient")),
        "safety_flags": list(decision.get("safety_flags") or []),
        "reply": reply,
        "drafted": drafted,
        "objective": decision.get("objective") or "",
    }
