# -*- coding: utf-8 -*-
"""Read-only account probe and OAuth refresh. Tokens stay out of the result."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.account_probe import refresh_access_token, run_account_probe
from x_integration.state import MentionLedger


def _clear():
    for key in (
        "X_USER_ACCESS_TOKEN",
        "X_OAUTH2_CLIENT_ID",
        "X_OAUTH2_CLIENT_SECRET",
        "X_OAUTH2_REFRESH_TOKEN",
        "X_USER_REFRESH_TOKEN",
        "X_REPLIES_ENABLED",
        "X_POLL_ENABLED",
        "X_STATE_DIR",
    ):
        os.environ.pop(key, None)


def test_users_me_and_mentions_hide_the_token():
    os.environ["X_USER_ACCESS_TOKEN"] = "access-secret-value"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_POLL_ENABLED"] = "false"
    os.environ.pop("X_OAUTH2_REFRESH_TOKEN", None)
    import httpx

    original = httpx.get

    def fake_get(url, headers=None, params=None, timeout=None):
        assert headers["Authorization"] == "Bearer access-secret-value"
        assert "access-secret-value" not in url

        class Response:
            def __init__(self, status, payload):
                self.status_code = status
                self._payload = payload

            def json(self):
                return self._payload

        if url.endswith("/users/me"):
            return Response(200, {"data": {"username": "AskMoodyBot", "id": "42"}})
        assert url.endswith("/users/42/mentions")
        assert params["max_results"] == 5
        response = Response(
            200,
            {"data": [{"id": "9", "text": "secret mention text"}]},
        )
        response.headers = {
            "x-rate-limit-limit": "450",
            "x-rate-limit-remaining": "449",
            "x-rate-limit-reset": "1700000000",
        }
        return response

    httpx.get = fake_get
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            result = run_account_probe()
    finally:
        httpx.get = original
        _clear()
    assert result["users_me_status"] == 200
    assert result["username"] == "AskMoodyBot"
    assert result["user_id"] == "42"
    assert result["mentions_status"] == 200
    assert result["mentions_permitted"] is True
    assert result["mentions_returned"] == 1
    assert result["mentions_rate_limit"] == {
        "limit": 450,
        "remaining": 449,
        "reset": 1700000000,
    }
    assert result["replies_enabled"] is False
    assert result["poll_enabled"] is False
    assert result["refresh_used"] is False
    rendered = json.dumps(result)
    assert "access-secret-value" not in rendered
    assert "secret mention text" not in rendered


def test_forbidden_mentions_are_not_permitted():
    os.environ["X_USER_ACCESS_TOKEN"] = "access-secret-value"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_POLL_ENABLED"] = "false"
    import httpx

    original = httpx.get

    def fake_get(url, headers=None, params=None, timeout=None):
        class Response:
            status_code = 200

            def json(self):
                if str(url).endswith("/users/me"):
                    return {"data": {"username": "AskMoodyBot", "id": "42"}}
                self.status_code = 403
                return {"title": "Client Forbidden", "reason": "client-not-enrolled"}

        response = Response()
        if not str(url).endswith("/users/me"):
            response.status_code = 403
        return response

    httpx.get = fake_get
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            result = run_account_probe()
    finally:
        httpx.get = original
        _clear()
    assert result["users_me_status"] == 200
    assert result["mentions_status"] == 403
    assert result["mentions_permitted"] is False
    assert result["mentions_title"] == "Client Forbidden"
    assert result["mentions_returned"] is None
    assert result["mentions_problem"]["reason"] == "client-not-enrolled"


def test_refresh_retries_users_me_and_stores_the_new_token():
    os.environ["X_USER_ACCESS_TOKEN"] = "expired-access"
    os.environ["X_OAUTH2_CLIENT_ID"] = "client-id"
    os.environ["X_OAUTH2_CLIENT_SECRET"] = "client-secret"
    os.environ["X_OAUTH2_REFRESH_TOKEN"] = "refresh-secret"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_POLL_ENABLED"] = "false"
    import httpx

    original_get = httpx.get
    original_post = httpx.post
    me_tokens = []

    def fake_get(url, headers=None, params=None, timeout=None):
        token = headers["Authorization"].split(" ", 1)[1]
        me_tokens.append((url, token))

        class Response:
            def __init__(self, status, payload):
                self.status_code = status
                self._payload = payload

            def json(self):
                return self._payload

        if url.endswith("/users/me") and token == "expired-access":
            return Response(401, {})
        if url.endswith("/users/me"):
            return Response(200, {"data": {"username": "AskMoodyBot", "id": "77"}})
        assert token == "new-access"
        return Response(200, {"data": []})

    def fake_post(url, data=None, auth=None, timeout=None):
        assert url.endswith("/oauth2/token")
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == "refresh-secret"
        assert auth == ("client-id", "client-secret")

        class Response:
            status_code = 200

            def json(self):
                return {"access_token": "new-access", "refresh_token": "new-refresh"}

        return Response()

    httpx.get = fake_get
    httpx.post = fake_post
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            result = run_account_probe()
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            assert book.cached_access_token() == "new-access"
            assert book.cached_refresh_token() == "new-refresh"
            again = run_account_probe(ledger=book)
    finally:
        httpx.get = original_get
        httpx.post = original_post
        _clear()
    assert result["users_me_status"] == 200
    assert result["username"] == "AskMoodyBot"
    assert result["user_id"] == "77"
    assert result["mentions_permitted"] is True
    assert result["refresh_used"] is True
    assert result["refresh_status"] == 200
    assert result["marker_survived"] is False
    assert again["marker_survived"] is True
    assert again["marker"] == result["marker"]
    assert me_tokens[0][1] == "expired-access"
    rendered = json.dumps(result) + json.dumps(again)
    for secret in ("expired-access", "new-access", "new-refresh", "refresh-secret", "client-secret"):
        assert secret not in rendered


def test_refresh_without_credentials_does_not_call_x():
    os.environ["X_USER_ACCESS_TOKEN"] = "expired-access"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_POLL_ENABLED"] = "false"
    import httpx

    original_get = httpx.get
    original_post = httpx.post
    posts = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        class Response:
            status_code = 401

            def json(self):
                return {}

        return Response()

    def fake_post(*_args, **_kwargs):
        posts["n"] += 1
        raise AssertionError("refresh was called")

    httpx.get = fake_get
    httpx.post = fake_post
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            status, token = refresh_access_token(book)
            result = run_account_probe(ledger=book)
    finally:
        httpx.get = original_get
        httpx.post = original_post
        _clear()
    assert status == 0
    assert token == ""
    assert posts["n"] == 0
    assert result["users_me_status"] == 401
    assert result["mentions_status"] == 0
    assert result["refresh_configured"] is False
    assert result["username"] == ""
    assert result["token_present"] is True
    assert result["token_shape"] == "opaque"


def test_client_forbidden_problem_is_sanitized():
    os.environ["X_USER_ACCESS_TOKEN"] = "AAAA-secret-token-value"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_POLL_ENABLED"] = "false"
    import httpx

    original = httpx.get

    def fake_get(url, headers=None, params=None, timeout=None):
        class Response:
            status_code = 403

            def json(self):
                return {
                    "client_id": "31339193",
                    "title": "Client Forbidden",
                    "detail": "Attached app is not enrolled. token=AAAA-secret-token-value",
                    "reason": "client-not-enrolled",
                    "required_enrollment": "Appropriate Level of API Access",
                    "type": "https://api.x.com/2/problems/client-forbidden",
                    "status": 403,
                }

        return Response()

    httpx.get = fake_get
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            result = run_account_probe()
    finally:
        httpx.get = original
        _clear()
    problem = result["users_me_problem"]
    assert problem["reason"] == "client-not-enrolled"
    assert problem["title"] == "Client Forbidden"
    assert problem["client_id"] == "31339193"
    assert result["token_shape"] == "app_bearer_prefix"
    rendered = json.dumps(result)
    assert "AAAA-secret-token-value" not in rendered
    assert "[redacted]" in problem["detail"]


def test_user_refresh_token_alias_is_configured_without_calling_x():
    os.environ["X_OAUTH2_CLIENT_ID"] = "client-id"
    os.environ["X_OAUTH2_CLIENT_SECRET"] = "client-secret"
    os.environ["X_USER_REFRESH_TOKEN"] = "refresh-secret"
    os.environ.pop("X_OAUTH2_REFRESH_TOKEN", None)
    os.environ.pop("X_USER_ACCESS_TOKEN", None)
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_POLL_ENABLED"] = "false"
    try:
        with TemporaryDirectory() as tmp:
            os.environ["X_STATE_DIR"] = tmp
            result = run_account_probe()
    finally:
        _clear()
    assert result["refresh_configured"] is True
    assert result["refresh_used"] is False
    assert result["users_me_status"] == 0


if __name__ == "__main__":
    test_users_me_and_mentions_hide_the_token()
    test_forbidden_mentions_are_not_permitted()
    test_refresh_retries_users_me_and_stores_the_new_token()
    test_refresh_without_credentials_does_not_call_x()
    test_client_forbidden_problem_is_sanitized()
    test_user_refresh_token_alias_is_configured_without_calling_x()
    print("account probe ok")
