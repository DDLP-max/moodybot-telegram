# -*- coding: utf-8 -*-
"""Poll @mentions with the standard X API.

The signed webhook stays in place. This path is the one a Personal
project can call. One pass reads a bounded number of pages, oldest
mention first. Authorization failures, rate limits, and credit errors
end the pass and the background loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from x_integration.events import Mention
from x_integration.state import (
    MentionLedger,
    bot_user_id,
    daily_model_limit,
    ledger_from_env,
)

logger = logging.getLogger("moodybot")

MENTIONS_URL = "https://api.x.com/2/users/{user_id}/mentions"
MAX_PAGES = 5
MAX_RESULTS = 100
# Mentions older than this post are history. The cursor starts just before it.
ACTIVATION_POST_ID = "2119952806698520807"
_POLL_LOCK = threading.Lock()
_STOP_STATUSES = frozenset({
    "unauthorized",
    "rate_limited",
    "insufficient_credits",
    "not_configured",
    "error",
})


@dataclass
class FetchResult:
    status: str
    tweets: list = field(default_factory=list)
    next_token: str = ""
    http_status: int = 0


Fetch = Callable[[str, str, str, str], FetchResult]


def poll_interval_seconds() -> int:
    raw = (os.environ.get("X_POLL_INTERVAL_SECONDS") or "300").strip()
    try:
        value = int(raw)
    except ValueError:
        return 300
    return value if value >= 60 else 60


def _read_token(book: MentionLedger, fetch: Optional[Fetch]) -> tuple[str, dict]:
    """Tests pass fetch and keep their own token. Production validates one token."""
    if fetch is not None:
        token = book.cached_access_token() or (os.environ.get("X_USER_ACCESS_TOKEN") or "").strip()
        return token, {}
    from x_integration.account_probe import validated_user_token

    check = validated_user_token(book)
    public = {
        "token_source": check.get("source") or "",
        "users_me_status": int(check.get("http_status") or 0),
        "username": check.get("username") or "",
    }
    if not check.get("ok"):
        return "", public
    return str(check.get("token") or ""), public


def poll_once(
    *,
    ledger: Optional[MentionLedger] = None,
    fetch: Optional[Fetch] = None,
    max_pages: int = MAX_PAGES,
) -> dict:
    """Read one bounded window. Does not post while replies are disabled."""
    book = ledger or ledger_from_env()
    user_id = bot_user_id()
    token, token_meta = _read_token(book, fetch)
    if not user_id or not token:
        stopped = {"status": "unauthorized" if token_meta else "not_configured", "drafted": 0, "since_id": book.get_since_id()}
        stopped.update(token_meta)
        return stopped
    since_id = book.get_since_id()
    fetcher = fetch or fetch_mentions
    collected: list[dict] = []
    pagination = ""
    for page in range(max_pages):
        result = fetcher(user_id, token, since_id, pagination)
        if result.status != "ok":
            return {
                "status": result.status,
                "http_status": result.http_status,
                "drafted": 0,
                "since_id": since_id,
            }
        collected.extend(result.tweets)
        if not result.next_token:
            break
        pagination = result.next_token
        if page == max_pages - 1:
            return {"status": "truncated", "drafted": 0, "since_id": since_id}
    if not collected:
        return {"status": "empty", "drafted": 0, "since_id": since_id}
    return _apply(book, _oldest_first(collected))


def fetch_mentions(
    user_id: str,
    token: str,
    since_id: str,
    pagination_token: str,
) -> FetchResult:
    import httpx

    params = {
        "max_results": MAX_RESULTS,
        "tweet.fields": "author_id,conversation_id,text,referenced_tweets",
        "expansions": "author_id,referenced_tweets.id",
        "user.fields": "username",
    }
    if since_id:
        params["since_id"] = since_id
    if pagination_token:
        params["pagination_token"] = pagination_token
    response = httpx.get(
        MENTIONS_URL.format(user_id=user_id),
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=20,
    )
    body = response.text or ""
    status = _classify(response.status_code, body)
    if status != "ok":
        logger.warning("X mention read stopped status=%s http=%s", status, response.status_code)
        return FetchResult(status=status, http_status=response.status_code)
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    meta = payload.get("meta") if isinstance(payload, dict) else {}
    tweets = [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    includes = payload.get("includes") if isinstance(payload, dict) else {}
    users = {}
    for user in (includes or {}).get("users") or []:
        if isinstance(user, dict):
            users[str(user.get("id") or "")] = str(user.get("username") or "")
    parents = {}
    for parent in (includes or {}).get("tweets") or []:
        if isinstance(parent, dict):
            parents[str(parent.get("id") or "")] = parent
    for tweet in tweets:
        tweet["author_username"] = users.get(str(tweet.get("author_id") or ""), "")
        parent_id = ""
        for ref in tweet.get("referenced_tweets") or []:
            if isinstance(ref, dict) and ref.get("type") == "replied_to":
                parent_id = str(ref.get("id") or "")
                break
        parent = parents.get(parent_id) or {}
        tweet["parent_id"] = parent_id
        tweet["parent_author_id"] = str(parent.get("author_id") or "")
        tweet["parent_text"] = parent.get("text") if isinstance(parent.get("text"), str) else ""
    next_token = str((meta or {}).get("next_token") or "")
    return FetchResult(status="ok", tweets=tweets, next_token=next_token, http_status=200)


def observe_once(
    *,
    ledger: Optional[MentionLedger] = None,
    fetch: Optional[Fetch] = None,
) -> dict:
    """Read mentions once. Does not draft, post, or move the cursor backward.

    The cursor is advanced only up to the activation post, so older mentions
    stay behind it and are not published later.
    """
    if not _POLL_LOCK.acquire(blocking=False):
        return {"status": "overlap", "discovered": 0, "queued": [], "filtered": []}
    try:
        return _observe_once(ledger=ledger, fetch=fetch)
    finally:
        _POLL_LOCK.release()


def _observe_once(*, ledger: Optional[MentionLedger], fetch: Optional[Fetch]) -> dict:
    from x_integration.dry_run import CONFIRMED_USER_ID

    book = ledger or ledger_from_env()
    user_id = bot_user_id() or CONFIRMED_USER_ID
    token, token_meta = _read_token(book, fetch)
    floor = str(int(ACTIVATION_POST_ID) - 1)
    current = book.get_since_id()
    if not current or int(current) < int(floor):
        book.set_since_id(floor)
    if not token:
        stopped = {
            "status": "unauthorized" if token_meta else "not_configured",
            "discovered": 0,
            "queued": [],
            "filtered": [],
            "since_id": book.get_since_id(),
            "replies_enabled": _replies_on(),
            "published": 0,
        }
        stopped.update(token_meta)
        return stopped
    result = (fetch or fetch_mentions)(user_id, token, "", "")
    if result.status != "ok":
        stopped = {
            "status": result.status,
            "http_status": result.http_status,
            "discovered": 0,
            "queued": [],
            "filtered": [],
            "since_id": book.get_since_id(),
            "replies_enabled": _replies_on(),
            "published": 0,
        }
        stopped.update(token_meta)
        return stopped
    queued = []
    filtered = []
    for tweet in _oldest_first(result.tweets):
        item = _classify_mention(book, tweet, user_id, floor)
        if item["classification"] != "historical":
            book.record_classification(item["post_id"], item["classification"], item["reason"])
        if item["queued"]:
            queued.append({"post_id": item["post_id"], "author_id": item["author_id"]})
        else:
            filtered.append({"post_id": item["post_id"], "reason": item["classification"]})
    observed = {
        "status": "ok",
        "discovered": len(queued) + len(filtered),
        "queued": queued,
        "filtered": sorted(filtered, key=lambda item: item["reason"] == "historical")[:30],
        "since_id": book.get_since_id(),
        "replies_enabled": _replies_on(),
        "published": 0,
    }
    observed.update(token_meta)
    return observed


def _classify_mention(book: MentionLedger, tweet: dict, user_id: str, floor: str) -> dict:
    from x_integration.eligibility import classify_mention

    post_id = str(tweet.get("id") or "").strip()
    decision = classify_mention(
        tweet,
        user_id=user_id,
        floor=floor,
        already_replied=book.already_replied(post_id) if post_id else False,
    )
    decision["queued"] = bool(decision["eligible"])
    return decision


def _replies_on() -> bool:
    from x_integration.state import replies_enabled

    return replies_enabled()


def _publishing_mode() -> bool:
    """Publish only in an explicit mode. A consumed one-reply gate stays shut."""
    from x_integration.state import (
        ledger_from_env,
        one_reply_gate_enabled,
        operating_mode,
        replies_enabled,
    )

    if not replies_enabled():
        return False
    mode = operating_mode()
    if mode == "limited_beta":
        return True
    if mode == "one_reply_test" and one_reply_gate_enabled():
        return not ledger_from_env().activation_blocks_publish()
    return False


async def poll_loop(stop_event: asyncio.Event, record=None) -> None:
    """Read on the poll interval.

    Replies off: observe only. That pass does not draft or post, so the
    eligible mention stays claimable. Replies on: one publishing pass at a time.
    """
    from datetime import datetime, timezone

    cycle = 0
    while not stop_event.is_set():
        cycle += 1
        publishing = _publishing_mode()
        if publishing and not _POLL_LOCK.acquire(blocking=False):
            logger.info("X mention poll skipped because a pass is already running")
            try:
                await asyncio.wait_for(stop_event.wait(), poll_interval_seconds())
            except asyncio.TimeoutError:
                continue
            continue
        try:
            try:
                if publishing:
                    result = await asyncio.to_thread(poll_once)
                else:
                    result = await asyncio.to_thread(observe_once)
            except Exception:
                logger.exception("X mention poll failed")
                return
            status = str(result.get("status") or "")
            if publishing and status == "unauthorized":
                from x_integration.account_probe import refresh_access_token

                _http, refreshed = await asyncio.to_thread(refresh_access_token)
                if refreshed:
                    try:
                        result = await asyncio.to_thread(poll_once)
                    except Exception:
                        logger.exception("X mention poll failed after refresh")
                        return
                    status = str(result.get("status") or "")
            result["cycle"] = cycle
            result["polled_at"] = datetime.now(timezone.utc).isoformat()
            result["state"] = "publishing" if publishing else "observed"
            logger.info(
                "X mention poll cycle=%s status=%s discovered=%s drafted=%s",
                cycle,
                status,
                result.get("discovered", 0),
                result.get("drafted", 0),
            )
            if record is not None:
                record(dict(result))
        finally:
            if publishing:
                _POLL_LOCK.release()
        if status in _STOP_STATUSES:
            return
        try:
            await asyncio.wait_for(stop_event.wait(), poll_interval_seconds())
        except asyncio.TimeoutError:
            continue


def _apply(book: MentionLedger, tweets: list[dict]) -> dict:
    from x_integration.webhook import process_mention

    drafted = 0
    own = bot_user_id()
    limit = daily_model_limit()
    for tweet in tweets:
        post_id = str(tweet.get("id") or "").strip()
        if not post_id.isdigit():
            continue
        author_id = str(tweet.get("author_id") or "").strip()
        text = tweet.get("text") if isinstance(tweet.get("text"), str) else ""
        mention = Mention(
            event_id=f"poll:{post_id}",
            post_id=post_id,
            author_id=author_id,
            text=text.strip() or ".",
            conversation_id=str(tweet.get("conversation_id") or post_id),
        )
        decision = _classify_mention(book, tweet, own or "", book.get_since_id() or "0")
        if decision["classification"] != "historical":
            book.record_classification(
                post_id, decision["classification"], decision["reason"]
            )
        if not decision["eligible"]:
            if decision["classification"] != "historical":
                book.set_since_id(post_id)
            continue
        needs_model = author_id != own and not book.already_replied(post_id) and bool(text.strip())
        if needs_model and book.model_calls_today() >= limit:
            return {
                "status": "spend_limit",
                "drafted": drafted,
                "since_id": book.get_since_id(),
            }
        if not text.strip():
            book.set_since_id(post_id)
            continue
        outcome = process_mention(mention, ledger=book)
        if outcome.get("status") in {
            "not_sent",
            "publish_limit",
            "activation_stopped",
            "publish_halted",
            "not_publishing",
        }:
            return {
                "status": str(outcome.get("status")),
                "drafted": drafted,
                "since_id": book.get_since_id(),
            }
        if outcome.get("status") == "dry_run":
            drafted += 1
        if outcome.get("reason") == "spend_limit":
            return {
                "status": "spend_limit",
                "drafted": drafted,
                "since_id": book.get_since_id(),
            }
        book.set_since_id(post_id)
    return {"status": "ok", "drafted": drafted, "since_id": book.get_since_id()}


def _oldest_first(tweets: list[dict]) -> list[dict]:
    ranked = []
    for tweet in tweets:
        post_id = str(tweet.get("id") or "")
        if post_id.isdigit():
            ranked.append((int(post_id), tweet))
    ranked.sort(key=lambda item: item[0])
    seen = set()
    ordered = []
    for _number, tweet in ranked:
        post_id = str(tweet.get("id"))
        if post_id in seen:
            continue
        seen.add(post_id)
        ordered.append(tweet)
    return ordered


def _classify(http_status: int, body: str) -> str:
    if http_status == 429:
        return "rate_limited"
    if http_status == 402:
        return "insufficient_credits"
    if http_status in {401, 403}:
        lowered = body.lower()
        if "credit" in lowered or "insufficient" in lowered:
            return "insufficient_credits"
        return "unauthorized"
    if http_status != 200:
        return "error"
    return "ok"
