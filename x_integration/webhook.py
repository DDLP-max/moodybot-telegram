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
    one_reply_gate_enabled,
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
    if replies_enabled() and book.activation_blocks_publish():
        return {
            "status": "activation_stopped",
            "reason": book.activation_status()["stop_reason"],
        }
    if replies_enabled() and book.automatic_reply_allowance()["remaining"] <= 0:
        existing = book.publication(mention.post_id)
        if existing and str(existing.get("status") or "") in {"posted", "ambiguous", "failed", "pending"}:
            return {"status": "duplicate", "reason": str(existing.get("status") or "")}
        return {"status": "publish_limit"}
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

    try:
        reply = draft_mention_reply(mention.text, mention.conversation_id)
    except Exception:
        if one_reply_gate_enabled():
            book.stop_activation("generation_failed", mention.post_id)
            book.release_pending_event(mention.event_id)
            return {"status": "not_sent", "reason": "generation_failed"}
        raise
    if one_reply_gate_enabled() and not str(reply or "").strip():
        book.stop_activation("generation_failed", mention.post_id)
        book.release_pending_event(mention.event_id)
        return {"status": "not_sent", "reason": "generation_failed"}
    if replies_enabled():
        return _publish_automatic(book, mention, reply)
    book.finish(
        mention.event_id,
        status="dry_run",
        reply_text=reply,
        post_id=mention.post_id,
    )
    return {"status": "dry_run", "posted": False}


def _activation_reason(kind: str, http_status: int) -> str:
    if kind == "posted":
        return "posted"
    if kind == "ambiguous":
        return "ambiguous"
    if http_status == 403:
        return "rejected"
    if kind == "failed":
        return "rejected"
    return "ambiguous"


def _publish_automatic(book: MentionLedger, mention: Mention, reply: str) -> dict:
    """Post once. A write that X may have accepted is never sent again."""
    from x_integration.account_probe import validated_user_token
    from x_integration.publish_once import send_reply

    armed = one_reply_gate_enabled()
    slot = book.reserve_automatic_publication(mention.post_id, reply)
    if slot == "cap":
        return {"status": "publish_limit"}
    if slot != "claimed":
        if slot in {"posted", "ambiguous", "failed"}:
            book.finish(
                mention.event_id,
                status=slot,
                reply_text=reply,
                skip_reason=slot,
                post_id=mention.post_id,
            )
        return {"status": "duplicate", "reason": slot}
    check = validated_user_token(book)
    if not check.get("ok"):
        book.release_automatic_reservation(mention.post_id)
        if armed:
            book.stop_activation("authentication_failed", mention.post_id)
            book.release_pending_event(mention.event_id)
        return {
            "status": "not_sent",
            "reason": "token_invalid",
            "http_status": int(check.get("http_status") or 0),
        }
    if armed:
        from x_integration.post_length import fits_post

        if not fits_post(reply):
            book.release_automatic_reservation(mention.post_id)
            book.stop_activation("reply_too_long", mention.post_id)
            book.release_pending_event(mention.event_id)
            return {"status": "not_sent", "reason": "reply_too_long"}
        if book.claim_activation_attempt(mention.post_id) != "claimed":
            book.release_automatic_reservation(mention.post_id)
            book.release_pending_event(mention.event_id)
            return {
                "status": "activation_stopped",
                "reason": book.activation_status()["stop_reason"],
            }
    outcome = send_reply(str(check.get("token") or ""), mention.post_id, reply)
    kind = str(outcome.get("outcome") or "ambiguous")
    http_status = int(outcome.get("http_status") or 0)
    if kind == "failed" and http_status == 0 and outcome.get("detail") == "reply_too_long":
        book.release_automatic_reservation(mention.post_id)
        if armed:
            book.finish_activation("reply_too_long")
            book.release_pending_event(mention.event_id)
        return {"status": "not_sent", "reason": "reply_too_long"}
    if kind not in {"posted", "failed", "ambiguous"}:
        kind = "ambiguous"
    problem = outcome.get("problem") if isinstance(outcome.get("problem"), dict) else None
    book.finish_publication(
        mention.post_id,
        status=kind,
        x_reply_id=str(outcome.get("x_reply_id") or ""),
        http_status=int(outcome.get("http_status") or 0),
        detail=str(outcome.get("detail") or ""),
        problem=problem,
    )
    book.finish(
        mention.event_id,
        status=kind,
        reply_text=reply,
        skip_reason="" if kind == "posted" else kind,
        post_id=mention.post_id,
    )
    if armed:
        book.finish_activation(_activation_reason(kind, http_status))
    return {
        "status": kind,
        "http_status": int(outcome.get("http_status") or 0),
        "x_reply_id": str(outcome.get("x_reply_id") or ""),
    }


def post_reply(in_reply_to_tweet_id: str, text: str, token: str = "") -> None:
    """Live posting is refused until a dry run has succeeded and the flag is on.

    The flag is read by process_mention. This function is the only place a
    post would be sent, and it stays unreachable while the flag is off.
    """
    if not replies_enabled():
        raise RuntimeError("X replies are disabled")
    access = (token or "").strip()
    if not access:
        from x_integration.account_probe import validated_user_token

        check = validated_user_token()
        if not check.get("ok"):
            raise RuntimeError("X reply token is not valid")
        access = str(check.get("token") or "")
    if not access or not in_reply_to_tweet_id or not text.strip():
        raise RuntimeError("X reply is not configured")
    from x_integration.publish_once import send_reply

    outcome = send_reply(access, in_reply_to_tweet_id, text)
    if outcome.get("outcome") != "posted":
        raise RuntimeError(str(outcome.get("detail") or "X reply was not posted"))
