# -*- coding: utf-8 -*-
"""Controlled dry run writes a side ledger and leaves production alone."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.dry_run import (
    CONFIRMED_USER_ID,
    CONFIRMED_USERNAME,
    run_controlled_dry_run,
)
from x_integration.state import MentionLedger


def _clear():
    for key in (
        "X_USER_ACCESS_TOKEN",
        "X_STATE_DIR",
        "X_POLL_ENABLED",
        "X_REPLIES_ENABLED",
        "X_DAILY_MODEL_CALL_LIMIT",
    ):
        os.environ.pop(key, None)


def _post(author_id="77", text="summon @MoodyBotAI access-secret-value"):
    def fetch(post_id, token):
        assert token == "access-secret-value"
        return {
            "status": 200,
            "author_id": author_id,
            "author_username": "MattCanham805",
            "created_at": "2026-11-08T02:56:45.000Z",
            "conversation_id": "2119097552092250463",
            "text": text,
        }

    return fetch


def test_dry_run_links_reply_dedupes_and_spares_production():
    os.environ["X_USER_ACCESS_TOKEN"] = "access-secret-value"
    os.environ["X_POLL_ENABLED"] = "false"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "25"
    calls = {"n": 0}

    def fake_draft(text, conversation_id, complete=None):
        calls["n"] += 1
        assert "access-secret-value" in text
        return "A dry reply that stays unposted."

    import x_integration.reply as reply

    original = reply.draft_mention_reply
    reply.draft_mention_reply = fake_draft
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            production = MentionLedger(Path(tmp) / "mentions.sqlite")
            production.set_since_id("100")
            result = run_controlled_dry_run(
                CONFIRMED_USERNAME,
                CONFIRMED_USER_ID,
                fetch_post=_post(),
            )
            reopened = MentionLedger(Path(tmp) / "mentions.sqlite")
            assert reopened.get_since_id() == "100"
            assert reopened.model_calls_today() == 0
    finally:
        reply.draft_mention_reply = original
        _clear()
    assert calls["n"] == 1
    assert result["first_status"] == "dry_run"
    assert result["second_status"] == "duplicate"
    assert result["deduplicated"] is True
    assert result["model_calls_after_first"] == 1
    assert result["model_calls_after_replay"] == 1
    assert result["cap_blocks_next"] is True
    assert result["daily_limit"] == 25
    assert result["stored"]["linked"] is True
    assert result["stored"]["post_id"] == result["post_id"]
    assert result["stored"]["author_id"] == "77"
    assert result["reply_text"] == "A dry reply that stays unposted."
    assert result["production_cursor_unchanged"] is True
    assert result["production_spend_unchanged"] is True
    assert result["side_database"].endswith("dry-run.sqlite")
    assert "access-secret-value" not in json.dumps(result)


def test_dry_run_refuses_a_different_account():
    os.environ["X_USER_ACCESS_TOKEN"] = "access-secret-value"
    os.environ["X_POLL_ENABLED"] = "false"
    os.environ["X_REPLIES_ENABLED"] = "false"
    called = {"n": 0}

    def fetch(*_args, **_kwargs):
        called["n"] += 1
        return {"status": 200}

    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            MentionLedger(Path(tmp) / "mentions.sqlite")
            result = run_controlled_dry_run(
                "AskMoodyBot",
                "999",
                fetch_post=fetch,
            )
    finally:
        _clear()
    assert called["n"] == 0
    assert result["state"] == "refused"
    assert result["reason"] == "unexpected_account"


if __name__ == "__main__":
    test_dry_run_links_reply_dedupes_and_spares_production()
    test_dry_run_refuses_a_different_account()
    print("dry run ok")
