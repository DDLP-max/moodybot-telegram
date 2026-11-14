# -*- coding: utf-8 -*-
"""X mention webhook: CRC, signature, dedup, and a dry run that does not post."""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from aiohttp.test_utils import TestClient, TestServer

from conversation_context import ConversationLog
from telegram_lifecycle import WEBHOOK_PATH, BotRuntime
from x_integration.events import Mention, parse_delivery
from x_integration.reply import draft_mention_reply
from x_integration.signature import crc_response, sign
from x_integration.state import MentionLedger
from x_integration.webhook import X_WEBHOOK_PATH, bind_ledger, post_reply, process_mention


SECRET = "test-oauth2-client-secret"
MENTION = {
    "data": {
        "id": "evt-1",
        "event_type": "post.mention.create",
        "post": {
            "id": "post-1",
            "author_id": "user-9",
            "conversation_id": "conv-1",
            "text": "@moodybot what do you think of Carla Gugino?",
        },
    }
}
CHAT = {
    "data": {
        "id": "evt-chat",
        "event_type": "chat.received",
        "post": {"id": "nope", "author_id": "user-9", "text": "dm"},
    }
}


def _signed(payload: dict) -> tuple:
    raw = json.dumps(payload).encode("utf-8")
    return raw, {"X-Twitter-Webhooks-Signature-OAuth2": sign(SECRET, raw)}


def _runtime_app():
    runtime = BotRuntime(
        mode="webhook",
        install_signals=False,
        webhook_base="https://moodybot-telegram-whook.onrender.com",
        webhook_secret_token="a" * 32,
        listen_port=0,
    )
    return runtime.build_http_app()


def test_crc_and_signature_and_telegram_route_unchanged():
    os.environ["X_OAUTH2_CLIENT_SECRET"] = SECRET
    os.environ.pop("X_REPLIES_ENABLED", None)
    app = _runtime_app()
    telegram = None
    x_get = None
    for resource in app.router.resources():
        if resource.canonical == WEBHOOK_PATH:
            telegram = resource
        if resource.canonical == X_WEBHOOK_PATH:
            x_get = resource
    assert telegram is not None
    assert x_get is not None

    async def _run():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            missing = await client.get(X_WEBHOOK_PATH)
            assert missing.status == 400
            ok = await client.get(X_WEBHOOK_PATH, params={"crc_token": "challenge"})
            assert ok.status == 200
            body = await ok.json()
            assert body == crc_response("challenge", SECRET)
            raw, headers = _signed(CHAT)
            unsigned = await client.post(X_WEBHOOK_PATH, data=raw)
            assert unsigned.status == 401
            rejected = await client.post(X_WEBHOOK_PATH, data=b"tampered", headers=headers)
            assert rejected.status == 401
            ignored = await client.post(X_WEBHOOK_PATH, data=raw, headers=headers)
            assert ignored.status == 200
            ignored_body = await ignored.json()
            assert ignored_body["reason"] == "chat"
            health = await client.get("/health")
            assert health.status == 200
            health_body = await health.json()
            assert "mode" in health_body
            assert "x" not in health_body
        finally:
            await client.close()

    asyncio.run(_run())


def test_dry_run_dedup_loop_and_spend_never_post():
    posted = []

    def _boom(*_args, **_kwargs):
        posted.append("posted")
        raise AssertionError("post_reply must not run while replies are disabled")

    import x_integration.webhook as webhook_mod
    import x_integration.reply as reply_mod

    original_draft = reply_mod.draft_mention_reply
    original_post = webhook_mod.post_reply

    def _draft(text, conversation_id, complete=None):
        return "Still thinking about the mention."

    reply_mod.draft_mention_reply = _draft
    webhook_mod.post_reply = _boom
    os.environ["X_BOT_USER_ID"] = "bot-1"
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "1"
    os.environ["X_REPLIES_ENABLED"] = "false"
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            first = process_mention(_mention("evt-1", "post-1", "user-9"), ledger=book)
            assert first == {"status": "dry_run", "posted": False}
            row = book.get("evt-1")
            assert row["status"] == "dry_run"
            assert row["reply_text"] == "Still thinking about the mention."
            again = process_mention(_mention("evt-1", "post-1", "user-9"), ledger=book)
            assert again["status"] == "duplicate"
            own = process_mention(_mention("evt-own", "post-own", "bot-1"), ledger=book)
            assert own["reason"] == "own_post"
            second = process_mention(_mention("evt-2", "post-2", "user-9"), ledger=book)
            assert second["reason"] == "spend_limit"
            assert posted == []
            try:
                post_reply("post-1", "no")
                raise AssertionError("disabled post_reply returned")
            except RuntimeError as exc:
                assert "disabled" in str(exc)
    finally:
        reply_mod.draft_mention_reply = original_draft
        webhook_mod.post_reply = original_post
        os.environ.pop("X_REPLIES_ENABLED", None)


def test_chat_is_not_a_mention_and_retry_then_dies():
    delivery = parse_delivery(CHAT)
    assert delivery.reason == "chat"
    mention = parse_delivery(MENTION)
    assert isinstance(mention, Mention)
    assert mention.post_id == "post-1"

    import x_integration.reply as reply_mod

    calls = {"n": 0}
    original = reply_mod.draft_mention_reply

    def _fail(text, conversation_id, complete=None):
        calls["n"] += 1
        raise RuntimeError("model down")

    reply_mod.draft_mention_reply = _fail
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "10"
    os.environ["X_BOT_USER_ID"] = "bot-1"
    os.environ["X_REPLIES_ENABLED"] = "false"
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            for _ in range(3):
                try:
                    process_mention(_mention("evt-r", "post-r", "user-9"), ledger=book)
                    raise AssertionError("expected failure")
                except RuntimeError:
                    pass
            done = process_mention(_mention("evt-r", "post-r", "user-9"), ledger=book)
            assert done["status"] == "dead"
            assert calls["n"] == 3
    finally:
        reply_mod.draft_mention_reply = original


def test_dry_run_uses_the_finalizer_and_does_not_call_the_model():
    import conversation_context

    original = conversation_context.conversation_log
    os.environ["X_REPLIES_ENABLED"] = "false"
    try:
        with TemporaryDirectory() as tmp:
            conversation_context.conversation_log = ConversationLog(Path(tmp))

            def _complete(messages):
                assert messages[-1]["role"] == "user"
                assert "Carla Gugino" in messages[-1]["content"]
                return "Gugino walks in already knowing the room."

            text = draft_mention_reply(
                "@moodybot what do you think of Carla Gugino?",
                "conv-1",
                complete=_complete,
            )
            assert text.strip()
            assert "Gugino" in text or "room" in text
            stored = conversation_context.conversation_log.recent("x-conv-1")
            assert stored[-1]["role"] == "assistant"
    finally:
        conversation_context.conversation_log = original
        os.environ.pop("X_REPLIES_ENABLED", None)


def test_overlong_reply_is_cut_to_a_standard_post():
    import conversation_context
    from x_integration.post_length import fits_post

    original = conversation_context.conversation_log
    os.environ["X_REPLIES_ENABLED"] = "false"
    long_reply = (
        "Gugino already knows the room. The same point, said again so the post cannot fit. " * 8
    ).strip()
    calls = {"n": 0}
    try:
        with TemporaryDirectory() as tmp:
            conversation_context.conversation_log = ConversationLog(Path(tmp))

            def _complete(messages):
                calls["n"] += 1
                system = " ".join(
                    str(item.get("content") or "")
                    for item in messages
                    if item.get("role") == "system"
                )
                if "Cover what honestly fits" in system:
                    return "Gugino already knows the room. \U0001f943"
                return long_reply

            text = draft_mention_reply(
                "@moodybot what do you think of Carla Gugino?",
                "conv-long",
                complete=_complete,
            )
    finally:
        conversation_context.conversation_log = original
        os.environ.pop("X_REPLIES_ENABLED", None)
    assert fits_post(text)
    assert "Gugino" in text
    assert calls["n"] >= 2


def test_model_call_does_not_block_the_event_loop():
    os.environ["X_OAUTH2_CLIENT_SECRET"] = SECRET
    app = _runtime_app()
    entered = threading.Event()

    def _slow(_mention):
        entered.set()
        time.sleep(0.6)
        return {"status": "dry_run", "posted": False}

    app["x_processor"] = _slow

    async def _run():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            raw, headers = _signed(MENTION)
            post_task = asyncio.create_task(
                client.post(X_WEBHOOK_PATH, data=raw, headers=headers)
            )
            for _ in range(50):
                if entered.is_set():
                    break
                await asyncio.sleep(0.02)
            assert entered.is_set()
            started = time.monotonic()
            health = await client.get("/health")
            elapsed = time.monotonic() - started
            assert health.status == 200
            assert elapsed < 0.3
            telegram = await client.post(
                WEBHOOK_PATH,
                data=b"{}",
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            )
            assert telegram.status == 403
            assert time.monotonic() - started < 0.3
            posted = await post_task
            assert posted.status == 200
            body = await posted.json()
            assert body["status"] == "dry_run"
            assert body["posted"] is False
        finally:
            await client.close()

    asyncio.run(_run())


def test_dedup_and_spend_survive_restart_and_concurrent_writers():
    import x_integration.reply as reply_mod

    original = reply_mod.draft_mention_reply
    reply_mod.draft_mention_reply = lambda text, conversation_id, complete=None: "held"
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "25"
    os.environ["X_BOT_USER_ID"] = "bot-1"
    os.environ["X_REPLIES_ENABLED"] = "false"
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            first = MentionLedger(path)
            assert process_mention(_mention("evt-keep", "post-keep", "user-9"), ledger=first)[
                "status"
            ] == "dry_run"
            del first
            reopened = MentionLedger(path)
            again = process_mention(_mention("evt-keep", "post-keep", "user-9"), ledger=reopened)
            assert again["status"] == "duplicate"
            ledgers = [MentionLedger(path) for _ in range(8)]

            def _one(index: int):
                return ledgers[index % len(ledgers)].reserve_model_call(25)

            with ThreadPoolExecutor(max_workers=8) as pool:
                reserved = list(pool.map(_one, range(40)))
            # The completed mention above already reserved one call.
            assert reserved.count(True) == 24
            assert reserved.count(False) == 16
            restarted = MentionLedger(path)
            assert restarted.reserve_model_call(25) is False
            blocked = process_mention(_mention("evt-over", "post-over", "user-3"), ledger=restarted)
            assert blocked["reason"] == "spend_limit"
    finally:
        reply_mod.draft_mention_reply = original


def _mention(event_id: str, post_id: str, author_id: str) -> Mention:
    return Mention(
        event_id=event_id,
        post_id=post_id,
        author_id=author_id,
        text="@moodybot what do you think of Carla Gugino?",
        conversation_id="conv-1",
    )


if __name__ == "__main__":
    test_crc_and_signature_and_telegram_route_unchanged()
    test_dry_run_dedup_loop_and_spend_never_post()
    test_chat_is_not_a_mention_and_retry_then_dies()
    test_dry_run_uses_the_finalizer_and_does_not_call_the_model()
    test_overlong_reply_is_cut_to_a_standard_post()
    test_model_call_does_not_block_the_event_loop()
    test_dedup_and_spend_survive_restart_and_concurrent_writers()
    bind_ledger(None)
    print("x webhook dry run ok")
