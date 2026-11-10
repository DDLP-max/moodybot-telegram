# -*- coding: utf-8 -*-
"""Publish one short reply to a chosen parent. Polling stays off.

The draft comes from the existing mention pipeline. The send is the
existing one-shot publisher. A later boot reads the marker and does not
post again, including after a definite rejection.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable, Optional

from x_integration.dry_run import CONFIRMED_USER_ID, CONFIRMED_USERNAME, _fetch_post
from x_integration.events import Mention
from x_integration.post_length import trim_to_post, weighted_length
from x_integration.state import MentionLedger, state_dir

POST_ID = "2119945360684744777"
PARENT_AUTHOR_ID = "2082957781293035520"
PARENT_USERNAME = "MattCanham805"
MARKER_NAME = f"live-reply-{POST_ID}.json"
DRAFT_NAME = f"live-reply-{POST_ID}.sqlite"
REPLY_LIMIT = 200
_URL = re.compile(r"https?://\S+", re.IGNORECASE)


def run_live_reply(
    root: Optional[Path] = None,
    *,
    fetch_post: Optional[Callable] = None,
    generate: Optional[Callable] = None,
    publish: Optional[Callable] = None,
    retrieve: Optional[Callable] = None,
) -> dict:
    directory = Path(root) if root is not None else state_dir()[0]
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / MARKER_NAME
    production = MentionLedger(directory / "mentions.sqlite")
    existing = _recorded(production)
    if existing:
        existing["checks"] = _checks(existing)
        return _with_retrieve_once(existing, directory, retrieve)
    if marker.is_file():
        previous = _read_marker(marker)
        if previous.get("state") in {"finished", "ambiguous", "refused"}:
            previous["rerun"] = False
            return previous
    if _flags_on():
        return _write_marker(marker, {"state": "refused", "reason": "automatic_flags_enabled", "posted": False, "post_id": POST_ID})
    token = (os.environ.get("X_USER_ACCESS_TOKEN") or "").strip()
    if not token:
        return _write_marker(marker, {"state": "error", "reason": "token_missing", "posted": False, "post_id": POST_ID, "rerun": True})
    try:
        post = (fetch_post or _fetch_post)(POST_ID, token)
    except Exception:
        return _write_marker(marker, {"state": "error", "reason": "post_read_failed", "posted": False, "post_id": POST_ID, "rerun": True})
    if post.get("status") != 200:
        return _write_marker(
            marker,
            {
                "state": "error",
                "reason": "post_read_failed",
                "posted": False,
                "post_id": POST_ID,
                "post_status": post.get("status") or 0,
                "problem": post.get("problem") or {},
                "rerun": True,
            },
        )
    if str(post.get("author_id") or "") != PARENT_AUTHOR_ID:
        return _write_marker(marker, {"state": "refused", "reason": "unexpected_parent", "posted": False, "post_id": POST_ID})
    if str(post.get("author_username") or "") not in {"", PARENT_USERNAME}:
        return _write_marker(marker, {"state": "refused", "reason": "unexpected_parent", "posted": False, "post_id": POST_ID})
    draft_path = directory / DRAFT_NAME
    raw = (generate or _generate)(post, draft_path)
    reply = _plain_reply(raw)
    if not reply:
        return _write_marker(marker, {"state": "refused", "reason": "reply_not_plain", "posted": False, "post_id": POST_ID})
    _store_draft(draft_path, post, reply)
    _write_marker(marker, {"state": "sending", "posted": False, "post_id": POST_ID})
    if production.publication(POST_ID):
        return _with_retrieve_once(_recorded(production), directory, retrieve)
    outcome = (publish or _publish)(directory, reply)
    saved = _recorded(production) or {}
    result = _outcome(outcome, saved, reply)
    if result.get("posted") and result.get("x_reply_id"):
        result["retrieved"] = _safe_retrieve(retrieve, token, result["x_reply_id"])
    result["checks"] = _checks(result)
    return _write_marker(marker, result)


def _generate(post: dict, draft_path: Path) -> str:
    from x_integration.publish_once import stored_draft
    from x_integration.webhook import process_mention

    side = MentionLedger(draft_path)
    mention = Mention(
        event_id=f"dry-run:{POST_ID}",
        post_id=POST_ID,
        author_id=str(post.get("author_id") or ""),
        text=str(post.get("text") or ""),
        conversation_id=str(post.get("conversation_id") or POST_ID),
    )
    process_mention(mention, ledger=side)
    return stored_draft(draft_path, POST_ID)


def _publish(directory: Path, reply: str) -> dict:
    from x_integration.publish_once import execute_publish

    return execute_publish(
        post_id=POST_ID,
        draft_text=reply,
        confirm=f"POST:{POST_ID}",
        production=MentionLedger(directory / "mentions.sqlite"),
        draft_db=directory / DRAFT_NAME,
    )


def _store_draft(draft_path: Path, post: dict, reply: str) -> None:
    side = MentionLedger(draft_path)
    event_id = f"dry-run:{POST_ID}"
    side.claim(
        event_id,
        POST_ID,
        str(post.get("author_id") or ""),
        str(post.get("conversation_id") or POST_ID),
    )
    side.finish(event_id, status="dry_run", reply_text=reply, post_id=POST_ID)


def _plain_reply(text: str) -> str:
    """The live test posts plain text under 200 weighted characters."""
    without_urls = _URL.sub(" ", text or "")
    plain = "".join(character for character in without_urls if 32 <= ord(character) <= 126)
    plain = " ".join(plain.split()).strip()
    plain = trim_to_post(plain, REPLY_LIMIT)
    if not plain or weighted_length(plain) > REPLY_LIMIT or _URL.search(plain):
        return ""
    return plain


def _outcome(outcome: dict, saved: dict, reply: str) -> dict:
    status = str(saved.get("status") or outcome.get("status") or "")
    posted = status == "posted" and bool(saved.get("x_reply_id") or outcome.get("x_reply_id"))
    if status == "ambiguous":
        state = "ambiguous"
    elif status in {"posted", "failed"}:
        state = "finished"
    else:
        state = "refused"
    problem = saved.get("problem") or outcome.get("problem") or {}
    return {
        "state": state,
        "posted": posted,
        "rerun": False,
        "post_id": POST_ID,
        "parent_author_id": PARENT_AUTHOR_ID,
        "status": status,
        "x_reply_id": str(saved.get("x_reply_id") or outcome.get("x_reply_id") or ""),
        "http_status": int(saved.get("http_status") or outcome.get("http_status") or 0),
        "detail": str(saved.get("detail") or outcome.get("detail") or ""),
        "problem": problem if isinstance(problem, dict) else {},
        "created_at": str(saved.get("created_at") or outcome.get("created_at") or ""),
        "updated_at": str(saved.get("updated_at") or outcome.get("updated_at") or ""),
        "weighted_length": weighted_length(reply),
        "reply_text": reply,
        "poll_enabled": _flag("X_POLL_ENABLED"),
        "replies_enabled": _flag("X_REPLIES_ENABLED"),
    }


def _checks(result: dict) -> dict:
    retrieved = result.get("retrieved") if isinstance(result.get("retrieved"), dict) else {}
    row_ok = result.get("status") == "posted"
    return {
        "reply_id_returned": bool(result.get("x_reply_id")),
        "reply_retrieved": retrieved.get("status") == 200,
        "reply_parent_matches": str(retrieved.get("in_reply_to") or "") == POST_ID,
        "reply_author_matches": str(retrieved.get("author_id") or "") == CONFIRMED_USER_ID
        and str(retrieved.get("author_username") or "") in {"", CONFIRMED_USERNAME},
        "row_reply_id": row_ok and bool(result.get("x_reply_id")),
        "row_parent_id": result.get("post_id") == POST_ID and row_ok,
        "row_timestamp": bool(result.get("created_at")) and bool(result.get("updated_at")),
        "flags_off": result.get("poll_enabled") is False and result.get("replies_enabled") is False,
        "weighted_length": int(result.get("weighted_length") or 0) <= REPLY_LIMIT,
    }


def _recorded(production: MentionLedger) -> dict:
    row = production.publication(POST_ID)
    if not row:
        return {}
    status = str(row.get("status") or "")
    if status == "pending":
        return {
            "state": "ambiguous",
            "posted": False,
            "rerun": False,
            "reason": "pending",
            "post_id": POST_ID,
            "status": status,
            "x_reply_id": "",
            "http_status": 0,
            "detail": "",
            "problem": {},
            "created_at": row.get("created_at") or "",
            "updated_at": row.get("updated_at") or "",
        }
    posted = status == "posted" and bool(row.get("x_reply_id"))
    return {
        "state": "ambiguous" if status == "ambiguous" else "finished",
        "posted": posted,
        "rerun": False,
        "post_id": POST_ID,
        "parent_author_id": PARENT_AUTHOR_ID,
        "status": status,
        "x_reply_id": row.get("x_reply_id") or "",
        "http_status": row.get("http_status") or 0,
        "detail": row.get("detail") or "",
        "problem": row.get("problem") or {},
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
        "weighted_length": weighted_length(row.get("reply_text") or ""),
        "reply_text": row.get("reply_text") or "",
        "poll_enabled": _flag("X_POLL_ENABLED"),
        "replies_enabled": _flag("X_REPLIES_ENABLED"),
    }


def _with_retrieve_once(result: dict, directory: Path, retrieve: Optional[Callable]) -> dict:
    recorded = dict(result)
    recorded["rerun"] = False
    marker = directory / MARKER_NAME
    previous = _read_marker(marker) if marker.is_file() else {}
    if previous.get("retrieved"):
        recorded["retrieved"] = previous["retrieved"]
        recorded["checks"] = previous.get("checks") or _checks(recorded)
        return recorded
    if recorded.get("posted") and recorded.get("x_reply_id"):
        token = (os.environ.get("X_USER_ACCESS_TOKEN") or "").strip()
        recorded["retrieved"] = _safe_retrieve(retrieve, token, recorded["x_reply_id"])
        recorded["checks"] = _checks(recorded)
        _write_marker(marker, recorded)
    return recorded


def _safe_retrieve(retrieve: Optional[Callable], token: str, reply_id: str) -> dict:
    try:
        found = (retrieve or _retrieve)(token, reply_id)
    except Exception:
        return {"status": 0, "in_reply_to": "", "author_id": "", "author_username": ""}
    if not isinstance(found, dict):
        return {"status": 0, "in_reply_to": "", "author_id": "", "author_username": ""}
    return found


def _retrieve(token: str, reply_id: str) -> dict:
    import httpx

    response = httpx.get(
        f"https://api.x.com/2/tweets/{reply_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "tweet.fields": "author_id,conversation_id,referenced_tweets",
            "expansions": "author_id",
            "user.fields": "username",
        },
        timeout=20,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else {}
    author_id = str(data.get("author_id") or "")
    username = ""
    includes = payload.get("includes") if isinstance(payload, dict) and isinstance(payload.get("includes"), dict) else {}
    for user in includes.get("users") or []:
        if isinstance(user, dict) and str(user.get("id") or "") == author_id:
            username = str(user.get("username") or "")
            break
    in_reply_to = ""
    for item in data.get("referenced_tweets") or []:
        if isinstance(item, dict) and item.get("type") == "replied_to":
            in_reply_to = str(item.get("id") or "")
            break
    kept = {
        "status": response.status_code,
        "in_reply_to": in_reply_to,
        "author_id": author_id,
        "author_username": username,
    }
    if response.status_code != 200 and isinstance(payload, dict):
        problem = {}
        for key in ("type", "title", "detail", "reason", "errors", "required_enrollment", "status"):
            if payload.get(key) in (None, ""):
                continue
            problem[key] = payload.get(key)
        kept["problem"] = problem
    return kept


def _flags_on() -> bool:
    return _flag("X_POLL_ENABLED") or _flag("X_REPLIES_ENABLED")


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() == "true"


def _read_marker(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"state": "error", "posted": False, "rerun": True}
    if isinstance(data, dict):
        return data
    return {"state": "error", "posted": False, "rerun": True}


def _write_marker(path: Path, result: dict) -> dict:
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result
