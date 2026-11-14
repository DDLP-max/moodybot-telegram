# -*- coding: utf-8 -*-
"""Authenticated read of what the ledger stored and what X still shows.

The route does not post, move the cursor, or open the database for writing.
A cursor value is reported beside the rows. It is not a publication.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from aiohttp import web

from x_integration.reply_audit import (
    AUDIT_HEADER,
    BOT_USER_ID,
    audit_authorized,
    retrieve_tweet,
    verify_retrieved,
)

ACTIVITY_PATH = "/api/x/activity"
_LANES = (
    "dry_runs",
    "historical_publications",
    "automatic_replies",
    "battle_replies",
    "visible_without_ledger_publication",
)


def read_activity_ledger(path: Path) -> dict:
    """Copy the rows the view needs. The access token is not a row."""
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        since_id = ""
        if _has_table(conn, "poll_state"):
            row = conn.execute(
                "SELECT since_id FROM poll_state WHERE name = 'mentions'"
            ).fetchone()
            since_id = str(row["since_id"] or "") if row else ""
        token = ""
        if _has_table(conn, "oauth_cache"):
            row = conn.execute(
                "SELECT access_token FROM oauth_cache WHERE name = 'user'"
            ).fetchone()
            token = str(row["access_token"] or "") if row else ""
        return {
            "since_id": since_id,
            "access_token": token,
            "publications": _all_rows(conn, "publications"),
            "events": _all_rows(conn, "events"),
            "engagement": _all_rows(conn, "engagement_decisions"),
            "reviews": _all_rows(conn, "mention_reviews"),
            "battles": _all_rows(conn, "battle_events"),
            "generations": _all_rows(conn, "generation_calls"),
            "audits": _all_rows(conn, "publication_audits"),
        }
    finally:
        conn.close()


def assemble_activity(ledger: dict, account_posts: list, parents: dict) -> dict:
    """Group stored rows and X posts. Confirmation requires a retrieved tweet."""
    engagement = {str(row.get("post_id") or ""): row for row in ledger.get("engagement") or []}
    reviews = {str(row.get("post_id") or ""): row for row in ledger.get("reviews") or []}
    battles = {str(row.get("post_id") or ""): row for row in ledger.get("battles") or []}
    generations = _generations(ledger.get("generations") or [])
    events_by_post: dict[str, list] = {}
    for event in ledger.get("events") or []:
        events_by_post.setdefault(str(event.get("post_id") or ""), []).append(event)
    replies = {
        str(post.get("id") or ""): post
        for post in account_posts
        if str(post.get("id") or "")
    }
    known_reply_ids = set()
    lanes = {name: [] for name in _LANES}
    publication_ids = set()
    for row in ledger.get("publications") or []:
        mention_id = str(row.get("post_id") or "")
        publication_ids.add(mention_id)
        reply_id = str(row.get("x_reply_id") or "")
        if reply_id:
            known_reply_ids.add(reply_id)
        item = _item(
            mention_id=mention_id,
            engagement=engagement.get(mention_id),
            review=reviews.get(mention_id),
            battle=battles.get(mention_id),
            generation=generations.get(mention_id),
            event=_preferred_event(events_by_post.get(mention_id) or []),
            publication=row,
            retrieved=replies.get(reply_id),
            parent=parents.get(mention_id),
        )
        lanes[_lane(item)].append(item)
    for post_id, events in events_by_post.items():
        if post_id in publication_ids:
            continue
        event = _preferred_event(events)
        if str(event.get("status") or "") != "dry_run":
            continue
        item = _item(
            mention_id=post_id,
            engagement=engagement.get(post_id),
            review=reviews.get(post_id),
            battle=battles.get(post_id),
            generation=generations.get(post_id),
            event=event,
            publication=None,
            retrieved=None,
            parent=parents.get(post_id),
        )
        lanes["dry_runs"].append(item)
    for post in account_posts:
        reply_id = str(post.get("id") or "")
        parent_id = str(post.get("in_reply_to_tweet_id") or "")
        if not reply_id or not parent_id or reply_id in known_reply_ids:
            continue
        if str(post.get("author_id") or "") != BOT_USER_ID:
            continue
        item = _item(
            mention_id=parent_id,
            engagement=engagement.get(parent_id),
            review=reviews.get(parent_id),
            battle=battles.get(parent_id),
            generation=generations.get(parent_id),
            event=_preferred_event(events_by_post.get(parent_id) or []),
            publication=None,
            retrieved=post,
            parent=parents.get(parent_id),
        )
        stored_battle = str(item.get("battle_response_id") or "")
        item["x_reply_id"] = reply_id
        item["published_text"] = _tweet_text(post)
        item["published_text_source"] = "x_api"
        item["ledger_status"] = "absent"
        item["publication_status"] = "absent"
        item["battle_response_id"] = stored_battle if stored_battle == reply_id else ""
        item["x_verification"] = _unledgered_verification(post, parent_id)
        item["application_published"] = False
        lane = "battle_replies" if item["battle_response_id"] else "visible_without_ledger_publication"
        lanes[lane].append(item)
    audits = []
    for row in ledger.get("audits") or []:
        audits.append({
            "origin": str(row.get("origin") or ""),
            "publishing_path": str(row.get("publishing_path") or ""),
            "event_id": str(row.get("event_id") or ""),
            "parent_id": str(row.get("parent_id") or ""),
            "reply_text": str(row.get("reply_text") or ""),
            "x_reply_id": str(row.get("x_reply_id") or ""),
            "http_status": int(row.get("http_status") or 0),
            "outcome": str(row.get("outcome") or ""),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
        })
    return {
        "since_id": str(ledger.get("since_id") or ""),
        "lanes": lanes,
        "audits": audits,
    }


def run_activity(database: Optional[Path] = None, include_opt_outs: bool = False) -> dict:
    from x_integration.state import MentionLedger, ledger_path

    path = database or ledger_path()
    if not path.is_file():
        return {
            "since_id": "",
            "error": "database_missing",
            "lanes": {name: [] for name in _LANES},
            "opt_out": _empty_opt_out(),
        }
    ledger = read_activity_ledger(path)
    token = str(ledger.pop("access_token", "") or "")
    account_http = 0
    account_posts: list = []
    parents: dict = {}
    if token:
        account_http, account_posts = fetch_account_posts(token)
        parents = _load_parents(token, ledger, account_posts)
        account_posts = _fill_reply_lookups(token, ledger, account_posts)
    result = assemble_activity(ledger, account_posts, parents)
    result["account_posts_http_status"] = account_http
    book = MentionLedger(path)
    result["opt_out"] = book.opt_out_summary()
    if include_opt_outs:
        result["opt_outs"] = book.list_opt_outs()
    return _scrub(result)


def _empty_opt_out() -> dict:
    return {
        "enforcement_active": True,
        "opted_out_users": 0,
        "opt_outs_24h": 0,
        "replies_suppressed": 0,
        "last_result": "",
        "last_at": "",
    }


def fetch_account_posts(token: str) -> tuple[int, list]:
    """Recent posts from the bot account. The token is not copied out."""
    import httpx

    try:
        response = httpx.get(
            f"https://api.x.com/2/users/{BOT_USER_ID}/tweets",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "max_results": 20,
                "exclude": "retweets",
                "tweet.fields": "author_id,created_at,conversation_id,text,note_tweet,referenced_tweets",
            },
            timeout=20,
        )
    except httpx.TimeoutException:
        return 0, []
    except httpx.TransportError:
        return 0, []
    if response.status_code != 200:
        return int(response.status_code), []
    try:
        body = response.json()
    except ValueError:
        return int(response.status_code), []
    found = []
    for item in body.get("data") or []:
        if isinstance(item, dict):
            found.append(_tweet(item))
    return int(response.status_code), found


async def handle_activity(request: web.Request) -> web.Response:
    import asyncio

    if not audit_authorized(request.headers.get(AUDIT_HEADER, "")):
        return web.Response(status=401, text="unauthorized")
    payload = {}
    if request.can_read_body:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if isinstance(body, dict):
            payload = body
    action = str(payload.get("opt_out_action") or "")
    if action == "record":
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id.isdigit():
            return web.Response(status=400, text="user_id required")

        def _record() -> None:
            from x_integration.state import ledger_from_env

            ledger_from_env().record_opt_out(
                user_id,
                str(payload.get("username") or ""),
                str(payload.get("source_post_id") or "operator"),
                str(payload.get("reason") or "operator"),
            )

        await asyncio.to_thread(_record)
    result = await asyncio.to_thread(run_activity, None, action == "list")
    return web.json_response(result)


def _item(
    *,
    mention_id: str,
    engagement: Optional[dict],
    review: Optional[dict],
    battle: Optional[dict],
    generation: Optional[dict],
    event: Optional[dict],
    publication: Optional[dict],
    retrieved: Optional[dict],
    parent: Optional[dict],
) -> dict:
    engagement = engagement or {}
    review = review or {}
    battle = battle or {}
    generation = generation or {}
    event = event or {}
    publication = publication or {}
    retrieved = retrieved or {}
    parent = parent or {}
    stored_text = str(publication.get("reply_text") or "")
    reply_id = str(publication.get("x_reply_id") or retrieved.get("id") or "")
    lookup = dict(retrieved)
    lookup["expected_parent_id"] = mention_id
    verified = verify_retrieved(stored_text, reply_id, lookup) if reply_id else {}
    author_id = str(engagement.get("author_id") or event.get("author_id") or parent.get("author_id") or "")
    classification = str(engagement.get("classification") or review.get("classification") or "")
    reason = str(engagement.get("reason") or review.get("reason") or "")
    battle_response_id = str(battle.get("response_id") or "")
    ledger_status = str(publication.get("status") or "")
    if not ledger_status and str(event.get("status") or "") == "dry_run":
        ledger_status = "dry_run"
    incoming = _tweet_text(parent)
    x_text = _tweet_text(retrieved)
    if stored_text:
        published = stored_text
        source = "ledger"
    elif x_text and ledger_status == "posted":
        published = x_text
        source = "x_api"
    else:
        published = ""
        source = ""
    verification = str(verified.get("verification_status") or "")
    if not reply_id:
        verification = ""
    return {
        "mention_id": mention_id,
        "author_id": author_id,
        "author_username": str(parent.get("author_username") or retrieved.get("author_username") or ""),
        "classification": classification,
        "classification_reason": reason,
        "extracted_question": "",
        "extracted_question_source": "not_stored",
        "incoming_text": incoming,
        "model_generation_status": str(generation.get("status") or "") or "not_recorded",
        "model_cost_usd": generation.get("cost_usd", None),
        "publication_status": ledger_status,
        "publishing_origin": str(publication.get("origin") or ""),
        "battle_response_id": battle_response_id,
        "x_reply_id": reply_id if ledger_status != "dry_run" else "",
        "verified_parent_id": str(verified.get("in_reply_to_tweet_id") or ""),
        "published_text": published,
        "published_text_source": source,
        "x_verification": verification,
        "body_match": str(verified.get("body_match") or ""),
        "retrieval_http_status": int(verified.get("http_status") or retrieved.get("http_status") or 0),
        "ledger_status": ledger_status or "absent",
        "application_published": ledger_status == "posted" and verification == "confirmed",
    }


def _lane(item: dict) -> str:
    """Battle only when the ledger stored a battle response id."""
    if str(item.get("battle_response_id") or ""):
        return "battle_replies"
    origin = str(item.get("publishing_origin") or "")
    if origin == "automatic":
        return "automatic_replies"
    if item.get("ledger_status") == "dry_run":
        return "dry_runs"
    return "historical_publications"


def _unledgered_verification(post: dict, parent_id: str) -> str:
    accessible = str(post.get("availability") or "") == "accessible" and int(post.get("http_status") or 0) == 200
    author_ok = str(post.get("author_id") or "") == BOT_USER_ID
    parent_ok = str(post.get("in_reply_to_tweet_id") or "") == parent_id
    if accessible and author_ok and parent_ok:
        return "accessible_not_in_ledger"
    if not accessible:
        return str(post.get("availability") or "not_retrieved")
    return "not_in_ledger"


def _generations(rows: list) -> dict:
    grouped: dict[str, dict] = {}
    ordered = sorted(rows, key=lambda row: int(row.get("id") or 0))
    for row in ordered:
        post_id = str(row.get("post_id") or "")
        if not post_id:
            continue
        current = grouped.setdefault(post_id, {"status": "", "cost_usd": None, "seen": False})
        current["status"] = str(row.get("status") or "")
        current["seen"] = True
        charged = row.get("charged_usd")
        if charged is None:
            continue
        current["cost_usd"] = round(float(current["cost_usd"] or 0) + float(charged), 6)
    return {
        post_id: {"status": item["status"], "cost_usd": item["cost_usd"]}
        for post_id, item in grouped.items()
    }


def _preferred_event(events: list) -> dict:
    if not events:
        return {}
    for status in ("posted", "dry_run"):
        for event in events:
            if str(event.get("status") or "") == status:
                return event
    return events[-1]


def _load_parents(token: str, ledger: dict, account_posts: list) -> dict:
    needed = set()
    for row in ledger.get("publications") or []:
        post_id = str(row.get("post_id") or "")
        if post_id.isdigit():
            needed.add(post_id)
    for post in account_posts:
        parent_id = str(post.get("in_reply_to_tweet_id") or "")
        if parent_id.isdigit():
            needed.add(parent_id)
    found = {}
    for post_id in sorted(needed)[:30]:
        found[post_id] = retrieve_tweet(token, post_id)
    return found


def _fill_reply_lookups(token: str, ledger: dict, account_posts: list) -> list:
    by_id = {str(post.get("id") or ""): post for post in account_posts}
    for row in ledger.get("publications") or []:
        reply_id = str(row.get("x_reply_id") or "")
        if reply_id.isdigit() and reply_id not in by_id:
            by_id[reply_id] = retrieve_tweet(token, reply_id)
    return list(by_id.values())


def _tweet(item: dict) -> dict:
    note = item.get("note_tweet") if isinstance(item.get("note_tweet"), dict) else {}
    return {
        "id": str(item.get("id") or ""),
        "author_id": str(item.get("author_id") or ""),
        "author_username": "",
        "text": item.get("text") if isinstance(item.get("text"), str) else "",
        "note_text": note.get("text") if isinstance(note.get("text"), str) else "",
        "in_reply_to_tweet_id": _replied_to(item),
        "conversation_id": str(item.get("conversation_id") or ""),
        "created_at": str(item.get("created_at") or ""),
        "http_status": 200,
        "availability": "accessible",
    }


def _tweet_text(tweet: dict) -> str:
    note = str(tweet.get("note_text") or "").strip()
    text = str(tweet.get("text") or "").strip()
    return note or text


def _replied_to(tweet: dict) -> str:
    for ref in tweet.get("referenced_tweets") or []:
        if isinstance(ref, dict) and ref.get("type") == "replied_to":
            return str(ref.get("id") or "")
    return ""


def _all_rows(conn: sqlite3.Connection, table: str) -> list:
    if not _has_table(conn, table):
        return []
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _scrub(value):
    if isinstance(value, dict):
        return {
            key: _scrub(item)
            for key, item in value.items()
            if key not in {"access_token", "refresh_token", "authorization"}
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value
