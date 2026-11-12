# -*- coding: utf-8 -*-
"""Read one publication from the production ledger and verify it on X.

The route is not /health. It does not post, move the cursor, or change a flag.
The database is opened read-only. The access token is never returned.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from pathlib import Path
from typing import Optional

from aiohttp import web

TARGET_POST_ID = "2120746490700386493"
BOT_USER_ID = "1912252811469025282"
AUDIT_PATH = "/api/x/reply-audit"
# sha256 of the one-time diagnostic token. The token itself is not in git.
DIAGNOSTIC_TOKEN_SHA256 = "5b3492130d67e436a571a48b05820417ee0f56bb6f8024f18d2793406ec58295"
_PUBLISH_COLUMNS = (
    "post_id",
    "reply_text",
    "x_reply_id",
    "status",
    "http_status",
    "detail",
    "problem_json",
    "created_at",
    "updated_at",
    "origin",
)
_EVENT_COLUMNS = (
    "event_id",
    "status",
    "attempts",
    "post_id",
    "author_id",
    "conversation_id",
    "reply_text",
    "skip_reason",
    "updated_at",
)


def diagnostic_authorized(header: str, expected_hash: str = DIAGNOSTIC_TOKEN_SHA256) -> bool:
    presented = (header or "").strip()
    if not presented or not expected_hash:
        return False
    digest = hashlib.sha256(presented.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, expected_hash)


def read_post_records(path: Path, post_id: str = TARGET_POST_ID) -> dict:
    """Read publication, event, and replied_posts rows. Does not write."""
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        publications = _rows(conn, "publications", _PUBLISH_COLUMNS, "post_id = ?", (post_id,))
        events = _rows(
            conn,
            "events",
            _EVENT_COLUMNS,
            "post_id = ? OR event_id = ?",
            (post_id, f"poll:{post_id}"),
        )
        replied = _rows(conn, "replied_posts", ("post_id", "event_id"), "post_id = ?", (post_id,))
        token = ""
        if _has_table(conn, "oauth_cache"):
            row = conn.execute(
                "SELECT access_token FROM oauth_cache WHERE name = 'user'"
            ).fetchone()
            token = str(row["access_token"] or "") if row else ""
    finally:
        conn.close()
    for row in publications:
        raw = row.pop("problem_json", "")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        row["problem"] = parsed if isinstance(parsed, dict) else {}
    return {
        "post_id": post_id,
        "publications": publications,
        "events": events,
        "replied_posts": replied,
        "access_token": token,
    }


def verify_retrieved(stored_text: str, stored_reply_id: str, retrieved: dict) -> dict:
    """Compare a ledger row with one authenticated tweet lookup."""
    text = retrieved.get("text") if isinstance(retrieved.get("text"), str) else ""
    note = retrieved.get("note_text") if isinstance(retrieved.get("note_text"), str) else ""
    published = note.strip() or text
    author_id = str(retrieved.get("author_id") or "")
    parent_id = str(retrieved.get("in_reply_to_tweet_id") or "")
    http_status = int(retrieved.get("http_status") or 0)
    availability = str(retrieved.get("availability") or "")
    author_ok = author_id == BOT_USER_ID
    parent_ok = parent_id == TARGET_POST_ID
    text_ok = bool(stored_text) and published == stored_text
    accessible = availability == "accessible" and http_status == 200
    reasons = []
    if not stored_reply_id:
        reasons.append("ledger_has_no_reply_id")
    if not accessible:
        reasons.append(availability or "not_retrieved")
    if stored_reply_id and author_id and not author_ok:
        reasons.append("author_mismatch")
    if stored_reply_id and parent_id and not parent_ok:
        reasons.append("parent_mismatch")
    if stored_reply_id and published and not text_ok:
        reasons.append("text_mismatch")
    return {
        "author_id": author_id,
        "author_username": str(retrieved.get("author_username") or ""),
        "author_matches": author_ok,
        "in_reply_to_tweet_id": parent_id,
        "parent_matches": parent_ok,
        "text": text,
        "note_text": note,
        "text_matches": text_ok,
        "http_status": http_status,
        "availability": availability,
        "x_error": retrieved.get("error") if isinstance(retrieved.get("error"), dict) else {},
        "discrepancy": bool(reasons),
        "discrepancy_reasons": reasons,
    }


def assemble_audit(records: dict, reply_lookup: Optional[dict], direct_replies: list) -> dict:
    """Drop the token and state what the ledger and X each say."""
    publication = records["publications"][0] if records["publications"] else None
    stored_reply_id = str((publication or {}).get("x_reply_id") or "")
    stored_text = str((publication or {}).get("reply_text") or "")
    stored_status = str((publication or {}).get("status") or "")
    verification = verify_retrieved(stored_text, stored_reply_id, reply_lookup or {})
    if stored_status == "posted" and verification["discrepancy"]:
        verification["ledger_says_posted_but_x_does_not_confirm"] = True
    else:
        verification["ledger_says_posted_but_x_does_not_confirm"] = False
    owners = []
    for item in direct_replies:
        owners.append({
            "id": str(item.get("id") or ""),
            "author_id": str(item.get("author_id") or ""),
            "author_username": str(item.get("author_username") or ""),
            "in_reply_to_tweet_id": str(item.get("in_reply_to_tweet_id") or ""),
            "text": item.get("text") if isinstance(item.get("text"), str) else "",
            "is_moodybot": str(item.get("author_id") or "") == BOT_USER_ID,
        })
    return {
        "post_id": records["post_id"],
        "publications": records["publications"],
        "events": records["events"],
        "replied_posts": records["replied_posts"],
        "stored_x_reply_id": stored_reply_id,
        "stored_reply_text": stored_text,
        "stored_status": stored_status,
        "stored_http_status": int((publication or {}).get("http_status") or 0),
        "stored_detail": str((publication or {}).get("detail") or ""),
        "stored_problem": (publication or {}).get("problem") or {},
        "parent_post_id": records["post_id"],
        "reply_verification": verification,
        "direct_replies": owners,
        "direct_reply_search": {
            "http_status": int((reply_lookup or {}).get("search_http_status") or 0),
            "error": (reply_lookup or {}).get("search_error") or {},
        },
    }


def run_reply_audit(database: Optional[Path] = None) -> dict:
    from x_integration.state import ledger_path

    path = database or ledger_path()
    if not path.is_file():
        return {"post_id": TARGET_POST_ID, "error": "database_missing", "database": str(path)}
    records = read_post_records(path, TARGET_POST_ID)
    token = records.pop("access_token", "")
    reply_id = ""
    if records["publications"]:
        reply_id = str(records["publications"][0].get("x_reply_id") or "")
    lookup = {"search_http_status": 0, "search_error": {}}
    replies: list = []
    if not token:
        lookup["availability"] = "token_unavailable"
        lookup["http_status"] = 0
    else:
        original = retrieve_tweet(token, TARGET_POST_ID)
        if reply_id:
            lookup.update(retrieve_tweet(token, reply_id))
        lookup["original_post"] = {
            "http_status": original.get("http_status"),
            "availability": original.get("availability"),
            "author_id": original.get("author_id"),
            "public_metrics": original.get("public_metrics") or {},
            "error": original.get("error") or {},
        }
        search_status, search_error, replies = search_direct_replies(token, TARGET_POST_ID)
        lookup["search_http_status"] = search_status
        lookup["search_error"] = search_error
    return assemble_audit(records, lookup, replies)


def retrieve_tweet(token: str, tweet_id: str) -> dict:
    """GET one tweet. The token is not copied into the result."""
    import httpx

    try:
        response = httpx.get(
            f"https://api.x.com/2/tweets/{tweet_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "tweet.fields": "author_id,conversation_id,text,note_tweet,referenced_tweets,withheld,public_metrics",
                "expansions": "author_id",
                "user.fields": "username",
            },
            timeout=20,
        )
    except httpx.TimeoutException:
        return {"http_status": 0, "availability": "timeout", "error": {"title": "timeout"}}
    except httpx.TransportError:
        return {"http_status": 0, "availability": "transport", "error": {"title": "transport"}}
    return _interpret_tweet(response, token)


def search_direct_replies(token: str, post_id: str) -> tuple[int, dict, list]:
    import httpx

    query = f"in_reply_to_tweet_id:{post_id}"
    try:
        response = httpx.get(
            "https://api.x.com/2/tweets/search/recent",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "query": query,
                "max_results": 10,
                "tweet.fields": "author_id,text,note_tweet,referenced_tweets,conversation_id",
                "expansions": "author_id",
                "user.fields": "username",
            },
            timeout=20,
        )
    except httpx.TimeoutException:
        return 0, {"title": "timeout"}, []
    except httpx.TransportError:
        return 0, {"title": "transport"}, []
    error = _error_body(response, token)
    if response.status_code != 200:
        return response.status_code, error, []
    try:
        body = response.json()
    except ValueError:
        return response.status_code, {"title": "unreadable"}, []
    names = _usernames(body)
    found = []
    data = body.get("data") if isinstance(body, dict) else None
    for item in data or []:
        if not isinstance(item, dict):
            continue
        parent = _replied_to(item)
        if parent != post_id:
            continue
        note = item.get("note_tweet") if isinstance(item.get("note_tweet"), dict) else {}
        note_text = note.get("text") if isinstance(note.get("text"), str) else ""
        text = note_text.strip() or (item.get("text") if isinstance(item.get("text"), str) else "")
        author_id = str(item.get("author_id") or "")
        found.append({
            "id": str(item.get("id") or ""),
            "author_id": author_id,
            "author_username": names.get(author_id, ""),
            "in_reply_to_tweet_id": parent,
            "text": text,
        })
    return response.status_code, {}, found


async def handle_reply_audit(request: web.Request) -> web.Response:
    import asyncio

    header = request.headers.get("X-Diagnostic-Token", "")
    if not diagnostic_authorized(header):
        return web.Response(status=401, text="unauthorized")
    result = await asyncio.to_thread(run_reply_audit)
    return web.json_response(result)


def _rows(conn: sqlite3.Connection, table: str, columns: tuple, where: str, args: tuple) -> list:
    if not _has_table(conn, table):
        return []
    present = set(_column_names(conn, table))
    selected = [name for name in columns if name in present]
    if not selected:
        return []
    sql = f"SELECT {', '.join(selected)} FROM {table} WHERE {where}"
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _column_names(conn: sqlite3.Connection, table: str) -> list:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _interpret_tweet(response, token: str) -> dict:
    status = int(response.status_code)
    error = _error_body(response, token)
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    withheld = data.get("withheld") if isinstance(data.get("withheld"), dict) else {}
    if status == 200 and data and withheld:
        availability = "withheld"
    elif status == 200 and data:
        availability = "accessible"
    elif status == 404:
        availability = "unavailable"
    elif status == 403:
        availability = "restricted"
    else:
        availability = "error"
    names = _usernames(body)
    note = data.get("note_tweet") if isinstance(data.get("note_tweet"), dict) else {}
    author_id = str(data.get("author_id") or "")
    return {
        "http_status": status,
        "availability": availability,
        "id": str(data.get("id") or ""),
        "author_id": author_id,
        "author_username": names.get(author_id, ""),
        "text": data.get("text") if isinstance(data.get("text"), str) else "",
        "note_text": note.get("text") if isinstance(note.get("text"), str) else "",
        "in_reply_to_tweet_id": _replied_to(data),
        "withheld": withheld,
        "public_metrics": data.get("public_metrics") if isinstance(data.get("public_metrics"), dict) else {},
        "error": error,
    }


def _usernames(body: dict) -> dict:
    names = {}
    includes = body.get("includes") if isinstance(body.get("includes"), dict) else {}
    for user in includes.get("users") or []:
        if isinstance(user, dict):
            names[str(user.get("id") or "")] = str(user.get("username") or "")
    return names


def _replied_to(tweet: dict) -> str:
    for ref in tweet.get("referenced_tweets") or []:
        if isinstance(ref, dict) and ref.get("type") == "replied_to":
            return str(ref.get("id") or "")
    return ""


def _error_body(response, token: str) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    source = payload
    errors = payload.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        source = errors[0]
    kept = {}
    for key in ("title", "detail", "type", "status"):
        if key not in source or source[key] in (None, ""):
            continue
        text = " ".join(str(source[key]).split())[:240]
        if token and token in text:
            text = "[redacted]"
        kept[key] = text
    return kept
