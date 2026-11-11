# -*- coding: utf-8 -*-
"""Mention polling: cursor, duplicates, pages, restart, auth, and rate limits."""
from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.poll import FetchResult, poll_loop, poll_once
from x_integration.state import MentionLedger
from x_integration.webhook import post_reply


def _tweet(post_id: str, author: str = "user-1", text: str = "Hey @MoodyBotAI what should I do") -> dict:
    return {
        "id": post_id,
        "author_id": author,
        "conversation_id": post_id,
        "text": text,
    }


def _book(path: Path) -> MentionLedger:
    return MentionLedger(path)


def _use_env():
    os.environ["X_USER_ACCESS_TOKEN"] = "test-user-token"
    os.environ["X_BOT_USER_ID"] = "bot-1"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "25"
    os.environ.pop("X_POLL_ENABLED", None)


def _clear_env():
    for key in (
        "X_USER_ACCESS_TOKEN",
        "X_BOT_USER_ID",
        "X_REPLIES_ENABLED",
        "X_DAILY_MODEL_CALL_LIMIT",
        "X_POLL_ENABLED",
        "X_OPERATING_MODE",
        "X_ONE_REPLY_GATE",
    ):
        os.environ.pop(key, None)


def _patch_draft():
    import x_integration.reply as reply_mod
    import x_integration.webhook as webhook_mod

    calls = []
    original_draft = reply_mod.draft_mention_reply
    original_post = webhook_mod.post_reply

    def _draft(text, conversation_id, complete=None):
        calls.append(conversation_id)
        return "Draft held."

    def _post(*_args, **_kwargs):
        raise AssertionError("post_reply ran while replies are disabled")

    reply_mod.draft_mention_reply = _draft
    webhook_mod.post_reply = _post
    return calls, original_draft, original_post


def _restore_draft(original_draft, original_post):
    import x_integration.reply as reply_mod
    import x_integration.webhook as webhook_mod

    reply_mod.draft_mention_reply = original_draft
    webhook_mod.post_reply = original_post


def test_pagination_is_oldest_first_and_cursor_survives_restart():
    calls, original_draft, original_post = _patch_draft()
    _use_env()
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            seen = []

            def fetch(user_id, token, since_id, pagination):
                seen.append((since_id, pagination))
                assert user_id == "bot-1"
                assert token == "test-user-token"
                if not pagination:
                    return FetchResult(
                        status="ok",
                        tweets=[_tweet("30"), _tweet("20")],
                        next_token="page-2",
                    )
                assert pagination == "page-2"
                return FetchResult(
                    status="ok",
                    tweets=[_tweet("12"), _tweet("11")],
                    next_token="",
                )

            first = poll_once(ledger=_book(path), fetch=fetch, max_pages=5)
            assert first["status"] == "ok"
            assert first["drafted"] == 4
            assert calls == ["11", "12", "20", "30"]
            assert first["since_id"] == "30"
            reopened = MentionLedger(path)
            assert reopened.get_since_id() == "30"

            def later(user_id, token, since_id, pagination):
                seen.append(("later", since_id, pagination))
                assert since_id == "30"
                assert pagination == ""
                return FetchResult(status="ok", tweets=[_tweet("40")], next_token="")

            second = poll_once(ledger=reopened, fetch=later, max_pages=5)
            assert second["drafted"] == 1
            assert second["since_id"] == "40"
            assert calls[-1] == "40"
            assert len(calls) == 5
    finally:
        _restore_draft(original_draft, original_post)
        _clear_env()


def test_duplicate_post_id_and_own_post_do_not_draft_twice():
    calls, original_draft, original_post = _patch_draft()
    _use_env()
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"

            def fetch(user_id, token, since_id, pagination):
                return FetchResult(
                    status="ok",
                    tweets=[
                        _tweet("11", author="bot-1", text="my own mention"),
                        _tweet("12"),
                        _tweet("12"),
                    ],
                    next_token="",
                )

            result = poll_once(ledger=_book(path), fetch=fetch)
            assert result["drafted"] == 1
            assert calls == ["12"]
            assert result["since_id"] == "12"
            again = poll_once(
                ledger=MentionLedger(path),
                fetch=lambda *_args: FetchResult(
                    status="ok",
                    tweets=[_tweet("12")],
                    next_token="",
                ),
            )
            assert again["drafted"] == 0
            assert calls == ["12"]
    finally:
        _restore_draft(original_draft, original_post)
        _clear_env()


def test_truncated_pages_do_not_move_the_cursor():
    calls, original_draft, original_post = _patch_draft()
    _use_env()
    try:
        with TemporaryDirectory() as tmp:
            fetched = []

            def fetch(user_id, token, since_id, pagination):
                fetched.append(pagination)
                token_out = "page-2" if pagination == "" else "page-3"
                return FetchResult(status="ok", tweets=[_tweet("5")], next_token=token_out)

            result = poll_once(
                ledger=_book(Path(tmp) / "mentions.sqlite"),
                fetch=fetch,
                max_pages=2,
            )
            assert result["status"] == "truncated"
            assert result["drafted"] == 0
            assert result["since_id"] == ""
            assert fetched == ["", "page-2"]
            assert calls == []
    finally:
        _restore_draft(original_draft, original_post)
        _clear_env()


def test_authorization_failure_stops_and_does_not_poll_again():
    calls, original_draft, original_post = _patch_draft()
    _use_env()
    try:
        with TemporaryDirectory() as tmp:
            hits = {"n": 0}

            def fetch(user_id, token, since_id, pagination):
                hits["n"] += 1
                return FetchResult(status="unauthorized", http_status=403)

            book = _book(Path(tmp) / "mentions.sqlite")
            book.set_since_id("9")
            result = poll_once(ledger=book, fetch=fetch, max_pages=5)
            assert result["status"] == "unauthorized"
            assert result["http_status"] == 403
            assert hits["n"] == 1
            assert book.get_since_id() == "9"
            assert calls == []

            async def _loop():
                import x_integration.poll as poll_mod

                original = poll_mod.poll_once
                seen = {"n": 0}

                def once():
                    seen["n"] += 1
                    return {"status": "insufficient_credits", "drafted": 0}

                poll_mod.poll_once = once
                os.environ["X_REPLIES_ENABLED"] = "true"
                os.environ["X_OPERATING_MODE"] = "limited_beta"
                try:
                    await poll_loop(asyncio.Event())
                finally:
                    poll_mod.poll_once = original
                return seen["n"]

            assert asyncio.run(_loop()) == 1
    finally:
        _restore_draft(original_draft, original_post)
        _clear_env()


def test_rate_limit_stops_before_the_next_page():
    calls, original_draft, original_post = _patch_draft()
    _use_env()
    try:
        with TemporaryDirectory() as tmp:
            hits = {"n": 0}

            def fetch(user_id, token, since_id, pagination):
                hits["n"] += 1
                if hits["n"] == 1:
                    return FetchResult(status="ok", tweets=[_tweet("15")], next_token="next")
                return FetchResult(status="rate_limited", http_status=429)

            result = poll_once(
                ledger=_book(Path(tmp) / "mentions.sqlite"),
                fetch=fetch,
                max_pages=5,
            )
            assert result["status"] == "rate_limited"
            assert result["drafted"] == 0
            assert result["since_id"] == ""
            assert hits["n"] == 2
            assert calls == []

            async def _loop():
                import x_integration.poll as poll_mod

                original = poll_mod.poll_once
                seen = {"n": 0}

                def once():
                    seen["n"] += 1
                    return {"status": "rate_limited", "drafted": 0}

                poll_mod.poll_once = once
                os.environ["X_REPLIES_ENABLED"] = "true"
                os.environ["X_OPERATING_MODE"] = "limited_beta"
                try:
                    await poll_loop(asyncio.Event())
                finally:
                    poll_mod.poll_once = original
                return seen["n"]

            assert asyncio.run(_loop()) == 1
    finally:
        _restore_draft(original_draft, original_post)
        _clear_env()


def test_spend_cap_stops_without_consuming_the_next_mention():
    calls, original_draft, original_post = _patch_draft()
    _use_env()
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "1"
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"

            def fetch(user_id, token, since_id, pagination):
                return FetchResult(
                    status="ok",
                    tweets=[_tweet("11"), _tweet("12")],
                    next_token="",
                )

            result = poll_once(ledger=_book(path), fetch=fetch)
            assert result["status"] == "spend_limit"
            assert result["drafted"] == 1
            assert result["since_id"] == "11"
            assert calls == ["11"]
            reopened = MentionLedger(path)
            assert reopened.get("poll:12") is None
            with sqlite3.connect(path) as conn:
                spent = conn.execute("SELECT model_calls FROM spend").fetchone()
            conn.close()
            assert spent[0] == 1
    finally:
        _restore_draft(original_draft, original_post)
        _clear_env()


def test_reply_publish_shape_is_not_sent_while_disabled():
    os.environ["X_REPLIES_ENABLED"] = "false"
    try:
        post_reply("123", "no")
        raise AssertionError("disabled post_reply returned")
    except RuntimeError as exc:
        assert "disabled" in str(exc)
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_USER_ACCESS_TOKEN"] = "test-user-token"
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["authorization"] = (headers or {}).get("Authorization")
        captured["timeout"] = timeout

        class Response:
            status_code = 201
            headers = {}

            def json(self):
                return {"data": {"id": "reply-1"}}

            def raise_for_status(self):
                return None

        return Response()

    import httpx

    original = httpx.post
    httpx.post = fake_post
    try:
        post_reply("998877", "held", token="test-user-token")
    finally:
        httpx.post = original
        _clear_env()
    assert captured["url"] == "https://api.x.com/2/tweets"
    assert captured["json"] == {
        "text": "held",
        "reply": {"in_reply_to_tweet_id": "998877"},
    }
    assert captured["authorization"] == "Bearer test-user-token"
    assert captured["timeout"] == 20


def test_observation_queues_the_new_mention_and_does_not_draft():
    from x_integration.poll import ACTIVATION_POST_ID, observe_once

    _use_env()
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            book = _book(path)
            older = str(int(ACTIVATION_POST_ID) - 10)
            newer = str(int(ACTIVATION_POST_ID) + 5)

            def fetch(user_id, token, since_id, pagination):
                assert since_id == ""
                return FetchResult(
                    status="ok",
                    tweets=[
                        _tweet(older, text="old @MoodyBotAI question about the week"),
                        _tweet(
                            str(int(ACTIVATION_POST_ID) + 1),
                            author="bot-1",
                            text="@MoodyBotAI this is mine",
                        ),
                        _tweet(
                            ACTIVATION_POST_ID,
                            author="2082957781293035520",
                            text="Hey @MoodyBotAI what is one piece of advice",
                        ),
                        _tweet(
                            newer,
                            author="999",
                            text="@MoodyBotAI",
                        ),
                        _tweet(
                            str(int(ACTIVATION_POST_ID) + 9),
                            author="888",
                            text="no handle here at all",
                        ),
                    ],
                )

            result = observe_once(ledger=book, fetch=fetch)
            assert result["status"] == "ok"
            assert result["discovered"] == 5
            assert result["queued"] == [
                {"post_id": ACTIVATION_POST_ID, "author_id": "2082957781293035520"}
            ]
            reasons = {item["post_id"]: item["reason"] for item in result["filtered"]}
            assert reasons[older] == "historical"
            assert reasons[str(int(ACTIVATION_POST_ID) + 1)] == "own_post"
            assert reasons[newer] == "empty"
            assert reasons[str(int(ACTIVATION_POST_ID) + 9)] == "not_mentioned"
            assert book.get_since_id() == str(int(ACTIVATION_POST_ID) - 1)
            assert book.get(f"poll:{ACTIVATION_POST_ID}") is None
            book.set_since_id(str(int(ACTIVATION_POST_ID) + 50))
            again = observe_once(ledger=book, fetch=fetch)
            assert again["since_id"] == str(int(ACTIVATION_POST_ID) + 50)
    finally:
        _clear_env()


def test_observation_reports_overlap_without_a_second_pass():
    from x_integration.poll import _POLL_LOCK, observe_once

    _use_env()
    held = _POLL_LOCK.acquire(blocking=False)
    try:
        result = observe_once()
        assert result["status"] == "overlap"
        assert result["queued"] == []
    finally:
        if held:
            _POLL_LOCK.release()
        _clear_env()


def test_observation_loop_runs_twice_without_publishing():
    calls, original_draft, original_post = _patch_draft()
    _use_env()
    os.environ["X_POLL_INTERVAL_SECONDS"] = "60"
    try:
        async def _loop():
            import x_integration.poll as poll_mod

            original_once = poll_mod.poll_once
            original_observe = poll_mod.observe_once
            original_interval = poll_mod.poll_interval_seconds
            seen = {"poll": 0, "observe": 0}
            stop = asyncio.Event()

            def once(*_args, **_kwargs):
                seen["poll"] += 1
                return {"status": "ok", "drafted": 1}

            def observe(*_args, **_kwargs):
                seen["observe"] += 1
                if seen["observe"] >= 2:
                    stop.set()
                return {
                    "status": "ok",
                    "discovered": 1,
                    "queued": [{"post_id": "2119952806698520807", "author_id": "2082957781293035520"}],
                    "filtered": [],
                    "since_id": "2119952806698520806",
                    "published": 0,
                    "replies_enabled": False,
                }

            poll_mod.poll_once = once
            poll_mod.observe_once = observe
            poll_mod.poll_interval_seconds = lambda: 0.01
            recorded = []
            try:
                await poll_loop(stop, record=recorded.append)
            finally:
                poll_mod.poll_once = original_once
                poll_mod.observe_once = original_observe
                poll_mod.poll_interval_seconds = original_interval
            return seen, recorded

        seen, recorded = asyncio.run(_loop())
        assert seen == {"poll": 0, "observe": 2}
        assert calls == []
        assert [item["cycle"] for item in recorded] == [1, 2]
        assert recorded[0]["polled_at"] != recorded[1]["polled_at"]
        assert recorded[1]["published"] == 0
        assert recorded[1]["since_id"] == "2119952806698520806"
    finally:
        os.environ.pop("X_POLL_INTERVAL_SECONDS", None)
        _restore_draft(original_draft, original_post)
        _clear_env()


if __name__ == "__main__":
    test_pagination_is_oldest_first_and_cursor_survives_restart()
    test_duplicate_post_id_and_own_post_do_not_draft_twice()
    test_truncated_pages_do_not_move_the_cursor()
    test_authorization_failure_stops_and_does_not_poll_again()
    test_rate_limit_stops_before_the_next_page()
    test_spend_cap_stops_without_consuming_the_next_mention()
    test_reply_publish_shape_is_not_sent_while_disabled()
    test_observation_queues_the_new_mention_and_does_not_draft()
    test_observation_reports_overlap_without_a_second_pass()
    test_observation_loop_runs_twice_without_publishing()
    print("mention poll ok")
