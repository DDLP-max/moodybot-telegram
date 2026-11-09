# -*- coding: utf-8 -*-
"""Mention inspection is read-only against the production ledger."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.mention_inspect import inspect_recent_mentions
from x_integration.state import MentionLedger


def _clear():
    for key in ("X_USER_ACCESS_TOKEN", "X_STATE_DIR", "X_POLL_ENABLED", "X_REPLIES_ENABLED"):
        os.environ.pop(key, None)


def test_inspect_lists_mentions_without_moving_the_cursor():
    os.environ["X_USER_ACCESS_TOKEN"] = "access-secret-value"
    os.environ["X_POLL_ENABLED"] = "false"
    os.environ["X_REPLIES_ENABLED"] = "false"
    import httpx

    original = httpx.get

    def fake_get(url, headers=None, params=None, timeout=None):
        assert headers["Authorization"] == "Bearer access-secret-value"
        assert params["max_results"] == 5
        assert "since_id" not in params

        class Response:
            status_code = 200
            headers = {"x-rate-limit-limit": "300", "x-rate-limit-remaining": "298"}

            def json(self):
                return {
                    "data": [
                        {
                            "id": "55",
                            "text": "hello @MoodyBotAI access-secret-value",
                            "author_id": "7",
                            "created_at": "2026-11-09T12:00:00.000Z",
                            "conversation_id": "55",
                        }
                    ],
                    "includes": {"users": [{"id": "7", "username": "someone"}]},
                }

        return Response()

    httpx.get = fake_get
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            book.set_since_id("100")
            result = inspect_recent_mentions("1912252811469025282")
            again = MentionLedger(Path(tmp) / "mentions.sqlite")
            assert again.get_since_id() == "100"
            assert again.model_calls_today() == 0
            assert not (Path(tmp) / "dry-run.sqlite").exists()
    finally:
        httpx.get = original
        _clear()
    assert result["mentions_status"] == 200
    assert result["mentions_returned"] == 1
    assert result["mentions"][0]["author_username"] == "someone"
    assert result["mentions"][0]["post_id"] == "55"
    assert result["production_since_id"] == "100"
    assert result["poll_enabled"] is False
    assert result["replies_enabled"] is False
    rendered = json.dumps(result)
    assert "access-secret-value" not in rendered
    assert "[redacted]" in result["mentions"][0]["text"]


if __name__ == "__main__":
    test_inspect_lists_mentions_without_moving_the_cursor()
    print("mention inspect ok")
