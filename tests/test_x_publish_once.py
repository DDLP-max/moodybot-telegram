# -*- coding: utf-8 -*-
"""One-shot publishing posts only after explicit confirmation."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.publish_once import _exit_code, execute_publish, send_reply, verify_posting_credential
from x_integration.state import MentionLedger
from x_integration.webhook import post_reply

POST_ID = "2119262820428865635"
DRAFT = "A dry reply that stays unposted until confirmed. 🥃"
AUTHOR = "2082957781293035520"


def _clear():
    for key in ("X_USER_ACCESS_TOKEN", "X_STATE_DIR", "X_POLL_ENABLED", "X_REPLIES_ENABLED"):
        os.environ.pop(key, None)


def _ready(root: Path) -> tuple[MentionLedger, Path]:
    os.environ["X_POLL_ENABLED"] = "false"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_USER_ACCESS_TOKEN"] = "access-secret-value"
    production = MentionLedger(root / "mentions.sqlite")
    production.set_since_id("100")
    side = MentionLedger(root / "dry-run.sqlite")
    event_id = f"dry-run:{POST_ID}"
    side.claim(event_id, POST_ID, AUTHOR, "2119097552092250463")
    side.finish(event_id, status="dry_run", reply_text=DRAFT, post_id=POST_ID)
    return production, root / "dry-run.sqlite"


def _credential(ok=True, reason="", evidence="tweet.write"):
    def verify(_token):
        if not ok:
            return {
                "ok": False,
                "reason": reason or "tweet_write_unverified",
                "username": "SomeoneElse",
                "user_id": "1",
                "write_evidence": "",
            }
        return {
            "ok": True,
            "reason": "",
            "username": "MoodyBotAI",
            "user_id": "1912252811469025282",
            "write_evidence": evidence,
        }

    return verify


def test_preview_and_mismatch_do_not_post():
    sent = {"n": 0}

    def send(*_args, **_kwargs):
        sent["n"] += 1
        raise AssertionError("preview must not post")

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        production, draft_db = _ready(root)
        preview = execute_publish(
            post_id=POST_ID,
            draft_text=DRAFT + "\n",
            confirm="",
            production=production,
            draft_db=draft_db,
            verify=_credential(),
            send=send,
            token="access-secret-value",
        )
        mismatch = execute_publish(
            post_id=POST_ID,
            draft_text="a different reply",
            confirm=f"POST:{POST_ID}",
            production=production,
            draft_db=draft_db,
            verify=_credential(),
            send=send,
            token="access-secret-value",
        )
        assert production.get_since_id() == "100"
        assert production.model_calls_today() == 0
        assert production.publication(POST_ID) is None
    assert preview["status"] == "preview"
    assert preview["posted"] is False
    assert preview["exit_code"] == 0
    assert mismatch["reason"] == "draft_mismatch"
    assert sent["n"] == 0
    assert preview["replies_enabled"] is False
    assert preview["poll_enabled"] is False
    assert "access-secret-value" not in json.dumps(preview)


def test_rejected_credential_does_not_post():
    sent = {"n": 0}

    def send(*_args, **_kwargs):
        sent["n"] += 1
        return {"outcome": "posted", "x_reply_id": "999", "http_status": 201, "detail": ""}

    with TemporaryDirectory() as tmp:
        production, draft_db = _ready(Path(tmp))
        result = execute_publish(
            post_id=POST_ID,
            draft_text=DRAFT,
            confirm=f"POST:{POST_ID}",
            production=production,
            draft_db=draft_db,
            verify=_credential(ok=False, reason="unexpected_account"),
            send=send,
            token="access-secret-value",
        )
    assert result["reason"] == "unexpected_account"
    assert result["posted"] is False
    assert sent["n"] == 0


def test_confirmed_post_records_one_reply_and_blocks_a_repeat():
    sent = {"n": 0, "body": None}

    def send(token, post_id, text):
        sent["n"] += 1
        sent["body"] = (token, post_id, text)
        return {
            "outcome": "posted",
            "x_reply_id": "555",
            "http_status": 201,
            "detail": "",
        }

    with TemporaryDirectory() as tmp:
        production, draft_db = _ready(Path(tmp))
        first = execute_publish(
            post_id=POST_ID,
            draft_text=DRAFT,
            confirm=f"POST:{POST_ID}",
            production=production,
            draft_db=draft_db,
            verify=_credential(),
            send=send,
            token="access-secret-value",
        )
        second = execute_publish(
            post_id=POST_ID,
            draft_text=DRAFT,
            confirm=f"POST:{POST_ID}",
            production=production,
            draft_db=draft_db,
            verify=_credential(),
            send=send,
            token="access-secret-value",
        )
        saved = production.publication(POST_ID)
        assert production.get_since_id() == "100"
        assert production.model_calls_today() == 0
        assert production.already_replied(POST_ID) is True
    assert sent["n"] == 1
    assert sent["body"][1] == POST_ID
    assert sent["body"][2] == DRAFT
    assert first["posted"] is True
    assert first["x_reply_id"] == "555"
    assert first["status"] == "posted"
    assert first["model_called"] is False
    assert first["production_since_id_unchanged"] is True
    assert first["production_model_calls_unchanged"] is True
    assert saved["reply_text"] == DRAFT
    assert saved["x_reply_id"] == "555"
    assert saved["post_id"] == POST_ID
    assert saved["created_at"]
    assert saved["updated_at"]
    assert second["posted"] is False
    assert second["reason"] == "posted"
    try:
        post_reply(POST_ID, DRAFT)
        raise AssertionError("automatic post_reply ran while replies are disabled")
    except RuntimeError as exc:
        assert "disabled" in str(exc)


def test_timeout_is_ambiguous_and_is_not_retried():
    sent = {"n": 0}

    def send(*_args, **_kwargs):
        sent["n"] += 1
        return {"outcome": "ambiguous", "http_status": 0, "detail": "timeout", "x_reply_id": ""}

    with TemporaryDirectory() as tmp:
        production, draft_db = _ready(Path(tmp))
        first = execute_publish(
            post_id=POST_ID,
            draft_text=DRAFT,
            confirm=f"POST:{POST_ID}",
            production=production,
            draft_db=draft_db,
            verify=_credential(),
            send=send,
            token="access-secret-value",
        )
        second = execute_publish(
            post_id=POST_ID,
            draft_text=DRAFT,
            confirm=f"POST:{POST_ID}",
            production=production,
            draft_db=draft_db,
            verify=_credential(),
            send=send,
            token="access-secret-value",
        )
        assert production.already_replied(POST_ID) is False
        assert production.model_calls_today() == 0
    assert sent["n"] == 1
    assert first["status"] == "ambiguous"
    assert second["reason"] == "ambiguous"
    assert second["posted"] is False


def test_concurrent_claims_allow_one_sender():
    with TemporaryDirectory() as tmp:
        production, _draft_db = _ready(Path(tmp))
        results = []

        def claim():
            results.append(production.claim_publication(POST_ID, DRAFT))

        threads = [threading.Thread(target=claim) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    assert sorted(results) == ["claimed", "pending"]


def test_send_reply_posts_one_in_reply_to_and_does_not_retry_timeouts():
    import httpx

    original = httpx.post
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["auth"] = headers["Authorization"]

        class Response:
            status_code = 201

            def json(self):
                return {"data": {"id": "777", "text": "ignored echo"}}

        return Response()

    httpx.post = fake_post
    try:
        outcome = send_reply("access-secret-value", POST_ID, DRAFT)
    finally:
        httpx.post = original
    assert outcome["outcome"] == "posted"
    assert outcome["x_reply_id"] == "777"
    assert captured["url"] == "https://api.x.com/2/tweets"
    assert captured["json"] == {
        "text": DRAFT,
        "reply": {"in_reply_to_tweet_id": POST_ID},
    }
    assert captured["auth"] == "Bearer access-secret-value"

    def explode(*_args, **_kwargs):
        raise httpx.TimeoutException("timed out")

    httpx.post = explode
    try:
        ambiguous = send_reply("access-secret-value", POST_ID, DRAFT)
    finally:
        httpx.post = original
    assert ambiguous["outcome"] == "ambiguous"
    assert ambiguous["detail"] == "timeout"


def test_credential_requires_moodybotai_and_tweet_write():
    import httpx

    original = httpx.get

    def fake_get(url, headers=None, params=None, timeout=None):
        class Response:
            status_code = 200
            headers = {
                "x-access-level": "read-write",
                "x-oauth-scopes": "tweet.read users.read tweet.write offline.access",
            }

            def json(self):
                return {"data": {"username": "MoodyBotAI", "id": "1912252811469025282"}}

        return Response()

    httpx.get = fake_get
    try:
        allowed = verify_posting_credential("access-secret-value")
    finally:
        httpx.get = original
    assert allowed["ok"] is True
    assert allowed["write_evidence"] == "tweet.write"
    assert allowed["username"] == "MoodyBotAI"

    def read_only(url, headers=None, params=None, timeout=None):
        class Response:
            status_code = 200
            headers = {"x-access-level": "read"}

            def json(self):
                return {"data": {"username": "MoodyBotAI", "id": "1912252811469025282"}}

        return Response()

    httpx.get = read_only
    try:
        denied = verify_posting_credential("access-secret-value")
    finally:
        httpx.get = original
    assert denied["ok"] is False
    assert denied["reason"] == "tweet_write_unverified"

    def missing_scope(url, headers=None, params=None, timeout=None):
        class Response:
            status_code = 200
            headers = {
                "x-access-level": "read-write",
                "x-oauth-scopes": "tweet.read users.read",
            }

            def json(self):
                return {"data": {"username": "MoodyBotAI", "id": "1912252811469025282"}}

        return Response()

    httpx.get = missing_scope
    try:
        no_write = verify_posting_credential("access-secret-value")
    finally:
        httpx.get = original
    assert no_write["ok"] is False
    assert no_write["reason"] == "tweet_write_unverified"


def test_automatic_flags_block_the_one_shot():
    sent = {"n": 0}

    def send(*_args, **_kwargs):
        sent["n"] += 1
        return {"outcome": "posted", "x_reply_id": "1", "http_status": 201, "detail": ""}

    with TemporaryDirectory() as tmp:
        production, draft_db = _ready(Path(tmp))
        os.environ["X_REPLIES_ENABLED"] = "true"
        result = execute_publish(
            post_id=POST_ID,
            draft_text=DRAFT,
            confirm=f"POST:{POST_ID}",
            production=production,
            draft_db=draft_db,
            verify=_credential(),
            send=send,
            token="access-secret-value",
        )
        assert os.environ["X_REPLIES_ENABLED"] == "true"
        assert os.environ["X_POLL_ENABLED"] == "false"
    assert result["reason"] == "automatic_flags_enabled"
    assert sent["n"] == 0


def test_preview_exit_code_stays_zero():
    assert _exit_code({"exit_code": 0}) == 0
    assert _exit_code({"exit_code": 3}) == 3
    assert _exit_code({}) == 2


def test_rejection_keeps_the_sanitized_problem_and_an_old_failure_stays():
    import sqlite3

    class Response:
        status_code = 403
        headers = {"x-transaction-id": "txn-123"}

        def json(self):
            return {
                "title": "Forbidden",
                "detail": "token access-secret-value is not allowed to post",
                "type": "about:blank",
                "reason": "not-authorized",
                "required_enrollment": "",
                "status": 403,
                "errors": [{"message": "access-secret-value", "code": 403}],
            }

    import httpx

    original = httpx.post

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json["reply"]["in_reply_to_tweet_id"] == POST_ID
        return Response()

    httpx.post = fake_post
    try:
        outcome = send_reply("access-secret-value", POST_ID, DRAFT)
    finally:
        httpx.post = original
    assert outcome["detail"] == "Forbidden"
    problem = outcome["problem"]
    assert problem["title"] == "Forbidden"
    assert problem["type"] == "about:blank"
    assert problem["reason"] == "not-authorized"
    assert problem["status"] == 403
    assert problem["x_transaction_id"] == "txn-123"
    assert "access-secret-value" not in json.dumps(problem)
    assert "[redacted]" in problem["detail"]
    assert problem["errors"][0]["message"] == "[redacted]"

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "mentions.sqlite"
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE publications (
                post_id TEXT PRIMARY KEY,
                reply_text TEXT NOT NULL,
                x_reply_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                http_status INTEGER NOT NULL DEFAULT 0,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO publications VALUES (?, ?, '', 'failed', 403, 'Forbidden', 't1', 't2')",
            (POST_ID, DRAFT),
        )
        conn.commit()
        conn.close()
        book = MentionLedger(path)
        book.finish_publication(
            POST_ID,
            status="failed",
            http_status=500,
            detail="replaced",
            problem={"title": "replaced"},
        )
        saved = book.publication(POST_ID)
    assert saved["status"] == "failed"
    assert saved["detail"] == "Forbidden"
    assert saved["http_status"] == 403
    assert saved["created_at"] == "t1"
    assert saved["updated_at"] == "t2"
    assert saved["problem"] == {}


if __name__ == "__main__":
    test_preview_and_mismatch_do_not_post()
    test_rejected_credential_does_not_post()
    test_confirmed_post_records_one_reply_and_blocks_a_repeat()
    test_timeout_is_ambiguous_and_is_not_retried()
    test_concurrent_claims_allow_one_sender()
    test_send_reply_posts_one_in_reply_to_and_does_not_retry_timeouts()
    test_credential_requires_moodybotai_and_tweet_write()
    test_automatic_flags_block_the_one_shot()
    test_preview_exit_code_stays_zero()
    test_rejection_keeps_the_sanitized_problem_and_an_old_failure_stays()
    print("publish once ok")
