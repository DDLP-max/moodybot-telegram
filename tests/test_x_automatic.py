# -*- coding: utf-8 -*-
"""Automatic reply guard: one token, a five-reply cap, and no unsafe retry."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.events import Mention
from x_integration.state import MentionLedger
from x_integration.webhook import process_mention


def _clear():
    for key in (
        "X_USER_ACCESS_TOKEN",
        "X_REPLIES_ENABLED",
        "X_POLL_ENABLED",
        "X_STATE_DIR",
        "X_OAUTH2_CLIENT_ID",
        "X_OAUTH2_CLIENT_SECRET",
        "X_OAUTH2_REFRESH_TOKEN",
        "X_BOT_USER_ID",
        "X_DAILY_MODEL_CALL_LIMIT",
        "X_OPERATING_MODE",
        "X_ONE_REPLY_GATE",
    ):
        os.environ.pop(key, None)


def _mention(post_id: str) -> Mention:
    return Mention(
        event_id=f"poll:{post_id}",
        post_id=post_id,
        author_id="2082957781293035520",
        text="Hey @MoodyBotAI what is one piece of advice",
        conversation_id=post_id,
    )


def test_validated_token_uses_the_cache_and_ignores_a_stale_env_token():
    from x_integration.account_probe import validated_user_token
    import httpx

    os.environ["X_USER_ACCESS_TOKEN"] = "stale-env-token"
    original = httpx.get
    seen = []

    def fake_get(url, headers=None, params=None, timeout=None):
        token = headers["Authorization"].split(" ", 1)[1]
        seen.append(token)

        class Response:
            status_code = 200

            def json(self):
                return {"data": {"username": "MoodyBotAI", "id": "1912252811469025282"}}

        return Response()

    httpx.get = fake_get
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            book.store_oauth_tokens("cached-access", "cached-refresh")
            result = validated_user_token(book)
    finally:
        httpx.get = original
        _clear()
    assert result["ok"] is True
    assert result["source"] == "cache"
    assert result["username"] == "MoodyBotAI"
    assert seen == ["cached-access"]
    assert "token" in result
    assert result["token"] == "cached-access"


def test_rejected_cache_does_not_fall_back_to_the_env_token():
    from x_integration.account_probe import validated_user_token
    import httpx

    os.environ["X_USER_ACCESS_TOKEN"] = "stale-env-token"
    original = httpx.get
    seen = []

    def fake_get(url, headers=None, params=None, timeout=None):
        token = headers["Authorization"].split(" ", 1)[1]
        seen.append(token)

        class Response:
            status_code = 401

            def json(self):
                return {"title": "Unauthorized", "status": 401}

        return Response()

    httpx.get = fake_get
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            book.store_oauth_tokens("expired-cache", "cached-refresh")
            result = validated_user_token(book)
    finally:
        httpx.get = original
        _clear()
    assert result["ok"] is False
    assert result["token"] == ""
    assert seen == ["expired-cache"]


def test_manual_posts_do_not_spend_the_automatic_allowance():
    with TemporaryDirectory() as tmp:
        book = MentionLedger(Path(tmp) / "mentions.sqlite")
        assert book.claim_publication("manual-post", "manual reply") == "claimed"
        book.finish_publication("manual-post", status="posted", x_reply_id="manual-reply", http_status=201)
        allowance = book.automatic_reply_allowance()
        assert allowance["used"] == 0
        assert allowance["remaining"] == 5
        saved = book.publication("manual-post")
        assert saved["status"] == "posted"
        assert saved["detail"] == ""


def test_sixth_automatic_reply_is_refused_before_a_write():
    with TemporaryDirectory() as tmp:
        book = MentionLedger(Path(tmp) / "mentions.sqlite")
        for number in range(5):
            post_id = str(1000 + number)
            assert book.reserve_automatic_publication(post_id, "reply") == "claimed"
            book.finish_publication(post_id, status="posted", x_reply_id=f"r{number}", http_status=201)
        assert book.automatic_reply_allowance()["remaining"] == 0
        assert book.reserve_automatic_publication("1006", "one more") == "cap"
        assert book.publication("1006") is None


def test_ambiguous_automatic_write_is_not_retried_or_rewritten():
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_OPERATING_MODE"] = "limited_beta"
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "5"
    posted = []
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            assert book.reserve_automatic_publication("2119952806698520807", "kept") == "claimed"
            book.finish_publication(
                "2119952806698520807",
                status="ambiguous",
                http_status=0,
                detail="timeout",
                problem={"title": "timeout", "x_transaction_id": "abc"},
            )
            import x_integration.reply as reply_mod
            import x_integration.publish_once as publish_mod

            original_draft = reply_mod.draft_mention_reply
            original_send = publish_mod.send_reply
            reply_mod.draft_mention_reply = lambda text, conversation_id, complete=None: "new draft"
            publish_mod.send_reply = lambda token, post_id, text: posted.append(post_id)
            try:
                result = process_mention(_mention("2119952806698520807"), ledger=book)
            finally:
                reply_mod.draft_mention_reply = original_draft
                publish_mod.send_reply = original_send
            saved = book.publication("2119952806698520807")
            assert result["reason"] == "ambiguous"
            assert posted == []
            assert saved["status"] == "ambiguous"
            assert saved["detail"] == "timeout"
            assert saved["problem"]["x_transaction_id"] == "abc"
            again = book.claim("poll:2119952806698520807", "2119952806698520807", "2082957781293035520", "2119952806698520807")
            assert again.duplicate is True
    finally:
        _clear()


def test_invalid_token_does_not_publish_and_releases_the_slot():
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_OPERATING_MODE"] = "limited_beta"
    os.environ["X_USER_ACCESS_TOKEN"] = "stale-env-token"
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "5"
    posted = []
    import httpx
    import x_integration.reply as reply_mod
    import x_integration.publish_once as publish_mod

    original_get = httpx.get
    original_draft = reply_mod.draft_mention_reply
    original_send = publish_mod.send_reply

    def fake_get(url, headers=None, params=None, timeout=None):
        class Response:
            status_code = 401

            def json(self):
                return {"title": "Unauthorized"}

        return Response()

    httpx.get = fake_get
    reply_mod.draft_mention_reply = lambda text, conversation_id, complete=None: "draft"
    publish_mod.send_reply = lambda token, post_id, text: posted.append(token)
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            book.store_oauth_tokens("expired-cache", "refresh")
            result = process_mention(_mention("2119952806698520808"), ledger=book)
            assert result["status"] == "not_sent"
            assert result["reason"] == "token_invalid"
            assert posted == []
            assert book.publication("2119952806698520808") is None
            assert book.automatic_reply_allowance()["remaining"] == 5
    finally:
        httpx.get = original_get
        reply_mod.draft_mention_reply = original_draft
        publish_mod.send_reply = original_send
        _clear()


if __name__ == "__main__":
    test_validated_token_uses_the_cache_and_ignores_a_stale_env_token()
    test_rejected_cache_does_not_fall_back_to_the_env_token()
    test_manual_posts_do_not_spend_the_automatic_allowance()
    test_sixth_automatic_reply_is_refused_before_a_write()
    test_ambiguous_automatic_write_is_not_retried_or_rewritten()
    test_invalid_token_does_not_publish_and_releases_the_slot()
    print("automatic guard ok")
