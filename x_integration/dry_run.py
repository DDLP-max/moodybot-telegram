# -*- coding: utf-8 -*-
"""One controlled mention draft. Nothing is posted.

The production ledger is read, not claimed. The draft, the replay, and
the spend-cap check use a separate SQLite file so the polling cursor
and the live daily counter stay where they were.
"""
from __future__ import annotations

import os

from x_integration.events import Mention
from x_integration.state import daily_model_limit, ledger_from_env, replies_enabled, state_dir
from x_integration.webhook import process_mention

CONFIRMED_USERNAME = "MoodyBotAI"
CONFIRMED_USER_ID = "1912252811469025282"
CHOSEN_POST_ID = "2119262820428865635"
POST_URL = "https://api.x.com/2/tweets/{post_id}"
DRY_RUN_FILENAME = "dry-run.sqlite"


def run_controlled_dry_run(
    username: str,
    user_id: str,
    *,
    post_id: str = CHOSEN_POST_ID,
    fetch_post=None,
) -> dict:
    production = ledger_from_env()
    before_since = production.get_since_id()
    before_calls = production.model_calls_today()
    base = {
        "post_id": post_id,
        "authenticated_username": username,
        "authenticated_user_id": user_id,
        "production_database": str(production.path),
        "production_since_id_before": before_since,
        "production_model_calls_before": before_calls,
        "replies_enabled": replies_enabled(),
        "poll_enabled": (os.environ.get("X_POLL_ENABLED") or "").strip().lower() == "true",
        "daily_limit": daily_model_limit(),
    }
    if replies_enabled() or base["poll_enabled"]:
        return {**base, "state": "refused", "reason": "flags_enabled"}
    if username != CONFIRMED_USERNAME or user_id != CONFIRMED_USER_ID:
        return {**base, "state": "refused", "reason": "unexpected_account"}
    token = (os.environ.get("X_USER_ACCESS_TOKEN") or "").strip()
    if not token:
        return {**base, "state": "refused", "reason": "token_missing"}
    try:
        post = (fetch_post or _fetch_post)(post_id, token)
    except Exception:
        return _closed(production, before_since, before_calls, {**base, "state": "error", "reason": "post_read_failed"})
    if post.get("status") != 200:
        return _closed(
            production,
            before_since,
            before_calls,
            {**base, "state": "error", "reason": "post_read_failed", "post_status": post.get("status"), "post_problem": post.get("problem") or {}},
        )
    if post.get("author_id") == user_id:
        return _closed(production, before_since, before_calls, {**base, "state": "refused", "reason": "own_post"})
    text = str(post.get("text") or "").strip()
    if not text or not post.get("author_id"):
        return _closed(production, before_since, before_calls, {**base, "state": "refused", "reason": "incomplete_post"})

    side_path = state_dir()[0] / DRY_RUN_FILENAME
    from x_integration.state import MentionLedger

    side = MentionLedger(side_path)
    mention = Mention(
        event_id=f"dry-run:{post_id}",
        post_id=post_id,
        author_id=str(post["author_id"]),
        text=text,
        conversation_id=str(post.get("conversation_id") or post_id),
    )
    try:
        first = process_mention(mention, ledger=side)
    except Exception:
        first = {"status": "error"}
    calls_after_first = side.model_calls_today()
    try:
        second = process_mention(mention, ledger=side)
    except Exception:
        second = {"status": "error"}
    calls_after_second = side.model_calls_today()
    stored = _stored(side, mention.event_id, post_id)
    blocked = _cap_blocks(side)
    result = {
        **base,
        "state": "done",
        "source_post": {
            "post_id": post_id,
            "created_at": post.get("created_at") or "",
            "author_id": str(post.get("author_id") or ""),
            "author_username": post.get("author_username") or "",
            "conversation_id": str(post.get("conversation_id") or ""),
            "text": text,
        },
        "first_status": first.get("status"),
        "second_status": second.get("status"),
        "model_calls_after_first": calls_after_first,
        "model_calls_after_replay": calls_after_second,
        "deduplicated": second.get("status") == "duplicate" and calls_after_second == calls_after_first,
        "stored": stored,
        "cap_blocks_next": blocked,
        "side_database": str(side.path),
        "reply_text": stored.get("reply_text") or "",
    }
    return _redact(_closed(production, before_since, before_calls, result), token)


def _cap_blocks(side) -> bool:
    limit = daily_model_limit()
    while side.model_calls_today() < limit:
        if not side.reserve_model_call(limit):
            return True
    return side.reserve_model_call(limit) is False


def _closed(production, before_since: str, before_calls: int, result: dict) -> dict:
    after_since = production.get_since_id()
    after_calls = production.model_calls_today()
    result["production_since_id_after"] = after_since
    result["production_model_calls_after"] = after_calls
    result["production_cursor_unchanged"] = after_since == before_since
    result["production_spend_unchanged"] = after_calls == before_calls
    return result


def _stored(side, event_id: str, post_id: str) -> dict:
    conn = side._connect()
    try:
        row = conn.execute(
            """
            SELECT status, post_id, author_id, conversation_id, reply_text
            FROM events WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
        link = conn.execute(
            "SELECT event_id FROM replied_posts WHERE post_id = ?",
            (post_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"linked": False}
    status, stored_post, author_id, conversation_id, reply_text = row
    return {
        "status": status,
        "post_id": stored_post,
        "author_id": author_id,
        "conversation_id": conversation_id,
        "reply_text": reply_text,
        "linked_event_id": link[0] if link else "",
        "linked": bool(link) and link[0] == event_id and stored_post == post_id and bool(reply_text),
    }


def _fetch_post(post_id: str, token: str) -> dict:
    import httpx

    response = httpx.get(
        POST_URL.format(post_id=post_id),
        headers={"Authorization": f"Bearer {token}"},
        params={
            "tweet.fields": "author_id,created_at,conversation_id,text,note_tweet",
            "expansions": "author_id",
            "user.fields": "username",
        },
        timeout=20,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200 or not isinstance(payload, dict):
        return {"status": response.status_code, "problem": _problem(payload, token)}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    note = data.get("note_tweet") if isinstance(data.get("note_tweet"), dict) else {}
    note_text = note.get("text") if isinstance(note.get("text"), str) else ""
    text = note_text.strip() or (data.get("text") if isinstance(data.get("text"), str) else "")
    author_id = str(data.get("author_id") or "")
    username = ""
    includes = payload.get("includes") if isinstance(payload.get("includes"), dict) else {}
    for user in includes.get("users") or []:
        if isinstance(user, dict) and str(user.get("id") or "") == author_id:
            username = str(user.get("username") or "")
            break
    return {
        "status": 200,
        "author_id": author_id,
        "author_username": username,
        "created_at": str(data.get("created_at") or ""),
        "conversation_id": str(data.get("conversation_id") or post_id),
        "text": " ".join(text.split()),
    }


def _problem(payload, token: str) -> dict:
    if not isinstance(payload, dict):
        return {}
    kept = {}
    for key in ("title", "detail", "type", "reason", "status"):
        if payload.get(key) in (None, ""):
            continue
        text = " ".join(str(payload[key]).split())[:240]
        if token and token in text:
            text = "[redacted]"
        kept[key] = text
    return kept


def _redact(value, token: str):
    if not token:
        return value
    if isinstance(value, str):
        return value.replace(token, "[redacted]")
    if isinstance(value, dict):
        return {key: _redact(item, token) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, token) for item in value]
    return value
