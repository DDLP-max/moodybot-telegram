# -*- coding: utf-8 -*-
"""GET CRC and POST deliveries for /api/x/webhook.

Chat and DM events are ignored. A mention is drafted and stored.
Nothing is posted to X unless X_REPLIES_ENABLED=true.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from aiohttp import web

from x_integration.events import Ignored, Mention, parse_delivery
from x_integration.signature import (
    crc_response,
    delivery_is_authentic,
    oauth1_consumer_secret,
    oauth2_client_secret,
)
from x_integration.state import (
    MentionLedger,
    bot_user_id,
    daily_model_limit,
    ledger_from_env,
    replies_enabled,
)

logger = logging.getLogger("moodybot")

X_WEBHOOK_PATH = "/api/x/webhook"
_LEDGER: Optional[MentionLedger] = None


def get_ledger() -> MentionLedger:
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = ledger_from_env()
    return _LEDGER


def bind_ledger(ledger: Optional[MentionLedger]) -> None:
    global _LEDGER
    _LEDGER = ledger


async def handle_x_crc(request: web.Request) -> web.Response:
    token = (request.query.get("crc_token") or "").strip()
    if not token:
        return web.Response(status=400, text="missing crc_token")
    secret = oauth2_client_secret() or oauth1_consumer_secret()
    if not secret:
        logger.warning("X CRC rejected: signing secret is not configured")
        return web.json_response({"error": "signing_secret_unset"}, status=503)
    return web.json_response(crc_response(token, secret))


async def handle_x_event(request: web.Request) -> web.Response:
    raw = await request.read()
    if not delivery_is_authentic(
        raw,
        request.headers,
        oauth2_secret=oauth2_client_secret(),
        oauth1_secret=oauth1_consumer_secret(),
    ):
        logger.warning("X delivery rejected: signature mismatch")
        return web.Response(status=401, text="invalid signature")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return web.Response(status=400, text="invalid json")
    delivery = parse_delivery(payload)
    if isinstance(delivery, Ignored):
        logger.info(
            "X delivery ignored reason=%s type=%s",
            delivery.reason,
            delivery.event_type or "-",
        )
        return web.json_response({"status": "ignored", "reason": delivery.reason})
    processor = request.app.get("x_processor") or process_mention
    try:
        result = await asyncio.to_thread(processor, delivery)
    except Exception:
        logger.exception("X mention processing failed event_id=%s", delivery.event_id)
        return web.json_response({"status": "retry"}, status=500)
    status = int(result.get("http_status") or 200)
    body = {key: value for key, value in result.items() if key != "http_status"}
    return web.json_response(body, status=status)


def process_mention(mention: Mention, *, ledger: Optional[MentionLedger] = None) -> dict:
    book = ledger or get_ledger()
    claim = book.claim(
        mention.event_id, mention.post_id, mention.author_id, mention.conversation_id
    )
    if claim.duplicate:
        return {"status": "duplicate"}
    if claim.dead:
        return {"status": "dead"}
    own = bot_user_id()
    if own and mention.author_id == own:
        book.finish(mention.event_id, status="skipped", skip_reason="own_post")
        return {"status": "skipped", "reason": "own_post"}
    if book.already_replied(mention.post_id):
        book.finish(mention.event_id, status="skipped", skip_reason="already_replied")
        return {"status": "skipped", "reason": "already_replied"}
    if not book.reserve_model_call(daily_model_limit()):
        book.finish(mention.event_id, status="skipped", skip_reason="spend_limit")
        return {"status": "skipped", "reason": "spend_limit"}
    from x_integration.reply import draft_mention_reply

    reply = draft_mention_reply(mention.text, mention.conversation_id)
    if replies_enabled():
        post_reply(mention.post_id, reply)
        book.finish(
            mention.event_id,
            status="posted",
            reply_text=reply,
            post_id=mention.post_id,
        )
        return {"status": "posted"}
    book.finish(
        mention.event_id,
        status="dry_run",
        reply_text=reply,
        post_id=mention.post_id,
    )
    return {"status": "dry_run", "posted": False}


def post_reply(in_reply_to_tweet_id: str, text: str) -> None:
    """Live posting is refused until a dry run has succeeded and the flag is on.

    The flag is read by process_mention. This function is the only place a
    post would be sent, and it stays unreachable while the flag is off.
    """
    if not replies_enabled():
        raise RuntimeError("X replies are disabled")
    token = (__import__("os").environ.get("X_USER_ACCESS_TOKEN") or "").strip()
    if not token or not in_reply_to_tweet_id or not text.strip():
        raise RuntimeError("X reply is not configured")
    import httpx

    response = httpx.post(
        "https://api.x.com/2/tweets",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "text": text,
            "reply": {"in_reply_to_tweet_id": in_reply_to_tweet_id},
        },
        timeout=20,
    )
    response.raise_for_status()
