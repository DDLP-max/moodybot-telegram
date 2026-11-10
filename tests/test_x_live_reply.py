# -*- coding: utf-8 -*-
"""One live reply is sent once. A rejection is not posted again."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.live_reply import PARENT_AUTHOR_ID, POST_ID, run_live_reply
from x_integration.publish_once import execute_publish


def _boom(*_args, **_kwargs):
    raise AssertionError("should not run")


def _clear():
    for key in ("X_USER_ACCESS_TOKEN", "X_POLL_ENABLED", "X_REPLIES_ENABLED", "X_STATE_DIR"):
        os.environ.pop(key, None)
    for key in ("X_USER_ACCESS_TOKEN", "X_POLL_ENABLED", "X_REPLIES_ENABLED", "X_STATE_DIR"):
        os.environ.pop(key, None)


def _ready():
    os.environ["X_USER_ACCESS_TOKEN"] = "access-secret-value"
    os.environ["X_POLL_ENABLED"] = "false"
    os.environ["X_REPLIES_ENABLED"] = "false"


def _post():
    return {
        "status": 200,
        "author_id": PARENT_AUTHOR_ID,
        "author_username": "MattCanham805",
        "text": "MoodyBot publishing test. Reply to this post.",
        "conversation_id": POST_ID,
    }


def _verify(_token):
    return {
        "ok": True,
        "reason": "",
        "username": "MoodyBotAI",
        "user_id": "1912252811469025282",
        "write_evidence": "tweet.write",
    }


def test_rejection_is_recorded_once_and_not_retried():
    _ready()
    calls = {"send": 0}

    def send(_token, _post_id, text):
        calls["send"] += 1
        assert "http" not in text
        assert len(text) <= 200
        return {
            "outcome": "failed",
            "http_status": 403,
            "detail": "Forbidden",
            "problem": {
                "title": "Forbidden",
                "detail": "Replies are limited to summoned accounts.",
                "reason": "reply-not-permitted",
                "type": "about:blank",
                "status": 403,
            },
            "x_reply_id": "",
        }

    def publish(directory, reply):
        return execute_publish(
            post_id=POST_ID,
            draft_text=reply,
            confirm=f"POST:{POST_ID}",
            production=__import__("x_integration.state", fromlist=["MentionLedger"]).MentionLedger(
                Path(directory) / "mentions.sqlite"
            ),
            draft_db=Path(directory) / f"live-reply-{POST_ID}.sqlite",
            verify=_verify,
            send=send,
            token="access-secret-value",
        )

    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = run_live_reply(root, fetch_post=lambda *_a, **_k: _post(), generate=lambda *_a, **_k: "Noted. The test post is the whole question.", publish=publish)
            second = run_live_reply(root, fetch_post=lambda *_a, **_k: _post(), generate=lambda *_a, **_k: "Noted.", publish=publish)
    finally:
        _clear()
    assert calls["send"] == 1
    assert first["posted"] is False
    assert first["http_status"] == 403
    assert first["problem"]["reason"] == "reply-not-permitted"
    assert first["problem"]["detail"] == "Replies are limited to summoned accounts."
    assert first["checks"]["reply_id_returned"] is False
    assert second["rerun"] is False
    assert second["status"] == "failed"
    assert calls["send"] == 1


def test_a_posted_reply_is_retrieved_and_not_sent_again():
    _ready()
    calls = {"send": 0, "get": 0}

    def send(_token, _post_id, _text):
        calls["send"] += 1
        return {"outcome": "posted", "http_status": 201, "detail": "", "x_reply_id": "555"}

    def publish(directory, reply):
        return execute_publish(
            post_id=POST_ID,
            draft_text=reply,
            confirm=f"POST:{POST_ID}",
            production=__import__("x_integration.state", fromlist=["MentionLedger"]).MentionLedger(
                Path(directory) / "mentions.sqlite"
            ),
            draft_db=Path(directory) / f"live-reply-{POST_ID}.sqlite",
            verify=_verify,
            send=send,
            token="access-secret-value",
        )

    def retrieve(_token, reply_id):
        calls["get"] += 1
        assert reply_id == "555"
        return {
            "status": 200,
            "in_reply_to": POST_ID,
            "author_id": "1912252811469025282",
            "author_username": "MoodyBotAI",
        }

    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = run_live_reply(
                root,
                fetch_post=lambda *_a, **_k: _post(),
                generate=lambda *_a, **_k: "Noted. \U0001f943 https://example.com",
                publish=publish,
                retrieve=retrieve,
            )
            second = run_live_reply(
                root,
                fetch_post=_boom,
                generate=_boom,
                publish=_boom,
                retrieve=_boom,
            )
    finally:
        _clear()
    assert calls["send"] == 1
    assert calls["get"] == 1
    assert first["posted"] is True
    assert first["x_reply_id"] == "555"
    assert first["post_id"] == POST_ID
    assert first["reply_text"] == "Noted."
    assert first["weighted_length"] <= 200
    assert first["created_at"]
    assert first["updated_at"]
    assert first["checks"]["reply_parent_matches"] is True
    assert first["checks"]["reply_author_matches"] is True
    assert first["checks"]["row_reply_id"] is True
    assert first["checks"]["flags_off"] is True
    assert second["x_reply_id"] == "555"
    assert second["rerun"] is False


def test_flags_and_the_wrong_parent_do_not_post():
    os.environ["X_USER_ACCESS_TOKEN"] = "access-secret-value"
    os.environ["X_POLL_ENABLED"] = "true"
    os.environ["X_REPLIES_ENABLED"] = "false"
    try:
        with TemporaryDirectory() as tmp:
            blocked = run_live_reply(
                Path(tmp),
                fetch_post=_boom,
                publish=_boom,
            )
    finally:
        _clear()
    assert blocked["state"] == "refused"
    assert blocked["posted"] is False
    _ready()
    try:
        with TemporaryDirectory() as tmp:
            wrong = run_live_reply(
                Path(tmp),
                fetch_post=lambda *_a, **_k: {**_post(), "author_id": "1", "author_username": "someone"},
                publish=_boom,
            )
    finally:
        _clear()
    assert wrong["reason"] == "unexpected_parent"
    assert wrong["posted"] is False


def test_parent_read_uses_the_cached_access_token():
    _ready()
    seen = {}

    def fetch(_post_id, token):
        seen["token"] = token
        return {**_post(), "author_id": "1", "author_username": "someone"}

    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            from x_integration.state import MentionLedger

            MentionLedger(root / "mentions.sqlite").store_oauth_tokens("cached-token", "refresh-token")
            result = run_live_reply(root, fetch_post=fetch, publish=_boom)
    finally:
        _clear()
    assert seen["token"] == "cached-token"
    assert result["posted"] is False
    assert result["reason"] == "unexpected_parent"


if __name__ == "__main__":
    test_rejection_is_recorded_once_and_not_retried()
    test_a_posted_reply_is_retrieved_and_not_sent_again()
    test_flags_and_the_wrong_parent_do_not_post()
    test_parent_read_uses_the_cached_access_token()
    print("live reply ok")
