# -*- coding: utf-8 -*-
"""One signed mention through the real handler, then the same event again.

The secret exists only inside this test. Replies stay off.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from aiohttp.test_utils import TestClient, TestServer

from telegram_lifecycle import WEBHOOK_PATH, BotRuntime
from x_integration.diagnose import report
from x_integration.signature import sign
from x_integration.state import MentionLedger
from x_integration.webhook import X_WEBHOOK_PATH, bind_ledger

TEST_SECRET = "dedicated-x-webhook-test-secret"
EVENT_ID = "evt-signed-synthetic-1"


def test_signed_mention_drafts_once_and_duplicate_does_not():
    import x_integration.reply as reply_mod
    import x_integration.webhook as webhook_mod

    calls = {"draft": 0, "post": 0}
    original_draft = reply_mod.draft_mention_reply
    original_post = webhook_mod.post_reply

    def _draft(text, conversation_id, complete=None):
        calls["draft"] += 1
        assert "synthetic mention" in text
        return "Draft held for the test."

    def _post(*_args, **_kwargs):
        calls["post"] += 1
        raise AssertionError("post_reply ran while replies are disabled")

    reply_mod.draft_mention_reply = _draft
    webhook_mod.post_reply = _post
    os.environ["X_OAUTH2_CLIENT_SECRET"] = TEST_SECRET
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "25"
    os.environ["X_BOT_USER_ID"] = "bot-not-the-author"
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            bind_ledger(book)
            app = BotRuntime(
                mode="webhook",
                install_signals=False,
                webhook_base="https://moodybot-telegram-whook.onrender.com",
                webhook_secret_token="b" * 32,
                listen_port=0,
            ).build_http_app()
            raw = json.dumps(
                {
                    "data": {
                        "id": EVENT_ID,
                        "event_type": "post.mention.create",
                        "post": {
                            "id": "post-signed-1",
                            "author_id": "user-signed-1",
                            "conversation_id": "conv-signed-1",
                            "text": "@moodybot synthetic mention",
                        },
                    }
                }
            ).encode("utf-8")
            headers = {"X-Twitter-Webhooks-Signature-OAuth2": sign(TEST_SECRET, raw)}

            async def _run():
                client = TestClient(TestServer(app))
                await client.start_server()
                try:
                    telegram = await client.post(
                        WEBHOOK_PATH,
                        data=b"{}",
                        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
                    )
                    assert telegram.status == 403
                    first = await client.post(X_WEBHOOK_PATH, data=raw, headers=headers)
                    assert first.status == 200
                    assert await first.json() == {"status": "dry_run", "posted": False}
                    second = await client.post(X_WEBHOOK_PATH, data=raw, headers=headers)
                    assert second.status == 200
                    assert await second.json() == {"status": "duplicate"}
                finally:
                    await client.close()

            asyncio.run(_run())
            assert calls == {"draft": 1, "post": 0}
            row = book.get(EVENT_ID)
            assert row["status"] == "dry_run"
            assert row["attempts"] == 1
            with sqlite3.connect(book.path) as conn:
                spent = conn.execute("SELECT model_calls FROM spend").fetchone()
            conn.close()
            assert spent[0] == 1
    finally:
        reply_mod.draft_mention_reply = original_draft
        webhook_mod.post_reply = original_post
        bind_ledger(None)
        os.environ.pop("X_REPLIES_ENABLED", None)


def test_diagnose_is_read_only_and_hides_row_content():
    os.environ["X_STATE_DIR"] = ""
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "x-state"
            os.environ["X_STATE_DIR"] = str(root)
            before = report()
            assert before["x_state_dir_source"] == "environment"
            assert before["database_filename"] == "mentions.sqlite"
            assert before["database_path"].endswith("mentions.sqlite")
            assert before["file_exists"] is False
            assert before["database_accessible"] is False
            assert not (root / "mentions.sqlite").exists()

            book = MentionLedger(root / "mentions.sqlite")
            book.claim("evt-hidden", "post-hidden", "user-hidden", "conv-hidden")
            book.finish(
                "evt-hidden",
                status="dry_run",
                reply_text="USER CONTENT SHOULD NOT APPEAR",
                post_id="post-hidden",
            )
            info = report()
            rendered = "\n".join(f"{key}={info[key]}" for key in info)
            assert info["file_exists"] is True
            assert info["database_accessible"] is True
            assert info["database_access"] == "ok"
            assert "events" in info["tables"].split(",")
            assert "USER CONTENT SHOULD NOT APPEAR" not in rendered
            assert "user-hidden" not in rendered
            assert "evt-hidden" not in rendered
    finally:
        os.environ.pop("X_STATE_DIR", None)


if __name__ == "__main__":
    test_diagnose_is_read_only_and_hides_row_content()
    test_signed_mention_drafts_once_and_duplicate_does_not()
    print("signed delivery ok")
