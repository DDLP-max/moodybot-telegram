# -*- coding: utf-8 -*-
"""LIVE_TEST removes the one-reply gate and stops on a dollar budget."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.events import Mention
from x_integration.state import (
    MentionLedger,
    automatic_reply_limit,
    operating_mode,
)
from x_integration.webhook import process_mention


BOT = "1912252811469025282"
POST = "2120746490700386493"


def _clear():
    for key in (
        "X_REPLIES_ENABLED",
        "X_ONE_REPLY_GATE",
        "X_OPERATING_MODE",
        "X_BOT_USER_ID",
        "X_DAILY_MODEL_CALL_LIMIT",
        "X_LIVE_TEST_REPLY_LIMIT",
        "X_OPENROUTER_BUDGET_USD",
        "X_OPENROUTER_CALL_RESERVE_USD",
        "X_STATE_DIR",
        "OPENROUTER_API_KEY",
    ):
        os.environ.pop(key, None)


def _mention(post_id: str, text: str) -> Mention:
    return Mention(
        event_id=f"poll:{post_id}",
        post_id=post_id,
        author_id="2082957781293035520",
        author_username="MattCanham805",
        text=text,
        conversation_id=post_id,
    )


def test_live_test_is_explicit_and_unknown_modes_stay_disabled():
    os.environ["X_OPERATING_MODE"] = "live_test"
    assert operating_mode() == "live_test"
    assert automatic_reply_limit() == 100
    os.environ["X_LIVE_TEST_REPLY_LIMIT"] = "0"
    assert automatic_reply_limit() == 100
    os.environ["X_LIVE_TEST_REPLY_LIMIT"] = "40"
    assert automatic_reply_limit() == 40
    os.environ["X_OPERATING_MODE"] = "limited_beta"
    assert automatic_reply_limit() == 5
    os.environ["X_OPERATING_MODE"] = "beta"
    assert operating_mode() == "disabled"
    _clear()


def test_stopped_one_reply_gate_does_not_block_live_test():
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_ONE_REPLY_GATE"] = "true"
    os.environ["X_OPERATING_MODE"] = "live_test"
    os.environ["X_BOT_USER_ID"] = BOT
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "1"
    sent = []
    import x_integration.account_probe as probe
    import x_integration.publish_once as publish_mod
    import x_integration.reply as reply_mod
    import x_integration.webhook as webhook_mod

    original_token = probe.validated_user_token
    original_send = publish_mod.send_reply
    original_draft = reply_mod.draft_mention_reply
    original_parent = webhook_mod._confirm_parent
    probe.validated_user_token = lambda book=None: {
        "ok": True,
        "token": "cached-access",
        "http_status": 200,
        "username": "MoodyBotAI",
        "user_id": BOT,
    }
    reply_mod.draft_mention_reply = lambda text, conversation_id, complete=None, brief="": "Noted."
    webhook_mod._confirm_parent = lambda token, post_id: {
        "ok": True,
        "reason": "authorized",
        "http_status": 200,
    }

    def send(token, post_id, text, **_extra):
        sent.append((post_id, text))
        return {"outcome": "posted", "http_status": 201, "detail": "", "x_reply_id": "reply-live"}

    publish_mod.send_reply = send
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            book.stop_activation("posted", "2119952806698520807")
            for number in range(5):
                post_id = str(3000 + number)
                assert book.reserve_automatic_publication(post_id, "prior") == "claimed"
                book.finish_publication(post_id, status="posted", x_reply_id=f"old-{number}", http_status=201)
            assert book.automatic_reply_allowance()["limit"] == 100
            assert book.automatic_reply_allowance()["remaining"] == 95
            result = process_mention(
                _mention(POST, "@MoodyBotAI what should I do"),
                ledger=book,
            )
            assert result["status"] == "posted"
            assert result["x_reply_id"] == "reply-live"
            assert sent == [(POST, "Noted.")]
            assert book.activation_status()["mode"] == "stopped"
            assert book.activation_status()["remaining"] == 0
            unrelated = process_mention(
                _mention("2120990000000000001", "I wonder why people do this. Ask @MoodyBotAI next time."),
                ledger=book,
            )
            assert unrelated["status"] == "skipped"
            assert sent == [(POST, "Noted.")]
            summary = book.generation_summary()
            assert summary["replies_published"] == 6
            assert summary["replies_attempted"] == 6
            assert summary["budget_remaining_usd"] == 10
    finally:
        probe.validated_user_token = original_token
        publish_mod.send_reply = original_send
        reply_mod.draft_mention_reply = original_draft
        webhook_mod._confirm_parent = original_parent
        _clear()


def test_budget_stops_generation_before_a_model_call():
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_OPERATING_MODE"] = "live_test"
    os.environ["X_BOT_USER_ID"] = BOT
    os.environ["X_OPENROUTER_BUDGET_USD"] = "0.10"
    os.environ["X_OPENROUTER_CALL_RESERVE_USD"] = "0.20"
    drafted = []
    import x_integration.reply as reply_mod

    original_draft = reply_mod.draft_mention_reply
    reply_mod.draft_mention_reply = lambda *args, **kwargs: drafted.append("called")
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            result = process_mention(
                _mention(POST, "@MoodyBotAI what should I do"),
                ledger=book,
            )
            assert result == {"status": "not_sent", "reason": "budget_exhausted"}
            assert drafted == []
            assert book.publication(POST) is None
            assert book.generation_summary()["model_calls"] == 0
            assert book.generation_summary()["last_generation_error"] == "budget_exhausted"
            assert book.get("poll:" + POST) is None
    finally:
        reply_mod.draft_mention_reply = original_draft
        _clear()


def test_confirmed_cost_replaces_the_reserve_and_missing_cost_keeps_it():
    os.environ["X_OPERATING_MODE"] = "live_test"
    os.environ["X_OPENROUTER_BUDGET_USD"] = "0.50"
    os.environ["X_OPENROUTER_CALL_RESERVE_USD"] = "0.20"
    with TemporaryDirectory() as tmp:
        book = MentionLedger(Path(tmp) / "mentions.sqlite")
        first = book.reserve_generation_call(POST)
        assert first is not None
        assert book.budget_allows_call() is True
        second = book.reserve_generation_call("2120746490700386494")
        assert second is not None
        assert book.budget_allows_call() is False
        assert book.reserve_generation_call("2120746490700386495") is None
        book.settle_generation_call(
            first,
            usage={"prompt_tokens": 1000, "completion_tokens": 40, "cost": 0.01},
        )
        book.settle_generation_call(second, usage={})
        summary = book.generation_summary()
        assert summary["model_calls"] == 2
        assert summary["confirmed_usd"] == 0.01
        assert summary["input_tokens"] == 1000
        assert summary["output_tokens"] == 40
        assert summary["spend_usd"] == 0.21
        assert summary["budget_remaining_usd"] == 0.29
        missing = book.reserve_generation_call("2120746490700386496")
        assert missing is not None
        book.settle_generation_call(
            missing,
            usage={"prompt_tokens": 10, "completion_tokens": 10},
            error="openrouter_http_500",
        )
        settled = book.generation_summary()
        assert settled["last_generation_error"] == "openrouter_http_500"
        assert settled["spend_usd"] >= 0.41
    _clear()


def test_openrouter_records_provider_cost_and_requests_usage():
    os.environ["X_OPERATING_MODE"] = "live_test"
    os.environ["X_OPENROUTER_BUDGET_USD"] = "10"
    os.environ["X_OPENROUTER_CALL_RESERVE_USD"] = "0.20"
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    seen = {}
    import httpx
    import moodybot
    from x_integration.reply import generation_post, openrouter_complete

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": "Paris."}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "cost": 0.004},
            }

    class Client:
        def __init__(self, timeout=0):
            seen["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            seen["url"] = url
            seen["body"] = json
            seen["auth"] = (headers or {}).get("Authorization", "")
            return Response()

    original = httpx.Client
    original_key = moodybot.OPENROUTER_API_KEY
    httpx.Client = Client
    moodybot.OPENROUTER_API_KEY = "test-key"
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            token = generation_post.set(POST)
            try:
                text = openrouter_complete([{"role": "user", "content": "capital?"}])
            finally:
                generation_post.reset(token)
            assert text == "Paris."
            assert seen["body"]["usage"] == {"include": True}
            assert "test-key" in seen["auth"]
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            summary = book.generation_summary()
            assert summary["model_calls"] == 1
            assert summary["confirmed_usd"] == 0.004
            assert summary["spend_usd"] == 0.004
            assert summary["input_tokens"] == 12
            assert summary["output_tokens"] == 3
    finally:
        httpx.Client = original
        moodybot.OPENROUTER_API_KEY = original_key
        _clear()


if __name__ == "__main__":
    test_live_test_is_explicit_and_unknown_modes_stay_disabled()
    test_stopped_one_reply_gate_does_not_block_live_test()
    test_budget_stops_generation_before_a_model_call()
    test_confirmed_cost_replaces_the_reserve_and_missing_cost_keeps_it()
    test_openrouter_records_provider_cost_and_requests_usage()
    print("ok")
