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
_STOP_STATUSES = frozenset({
    "unauthorized",
    "rate_limited",
    "insufficient_credits",
    "not_configured",
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


def poll_once(
    *,
    ledger: Optional[MentionLedger] = None,
    fetch: Optional[Fetch] = None,
    max_pages: int = MAX_PAGES,
) -> dict:
    """Read one bounded window. Does not post while replies are disabled."""
    book = ledger or ledger_from_env()
    user_id = bot_user_id()
    token = book.cached_access_token() or (os.environ.get("X_USER_ACCESS_TOKEN") or "").strip()
    if not user_id or not token:
        return {"status": "not_configured", "drafted": 0, "since_id": book.get_since_id()}
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
        "tweet.fields": "author_id,conversation_id",
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
    next_token = str((meta or {}).get("next_token") or "")
    return FetchResult(status="ok", tweets=tweets, next_token=next_token, http_status=200)


async def poll_loop(stop_event: asyncio.Event) -> None:
    """Keep reading until stop, or until a read is refused."""
    while not stop_event.is_set():
        try:
            result = await asyncio.to_thread(poll_once)
        except Exception:
            logger.exception("X mention poll failed")
            return
        status = str(result.get("status") or "")
        if status == "unauthorized":
            from x_integration.account_probe import refresh_access_token

            _http, refreshed = await asyncio.to_thread(refresh_access_token)
            if refreshed:
                try:
                    result = await asyncio.to_thread(poll_once)
                except Exception:
                    logger.exception("X mention poll failed after refresh")
                    return
                status = str(result.get("status") or "")
        logger.info(
            "X mention poll status=%s drafted=%s",
            status,
            result.get("drafted", 0),
        )
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
