# -*- coding: utf-8 -*-
"""The reply audit reads the ledger and does not treat a cursor as a post."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.reply_audit import (
    BOT_USER_ID,
    TARGET_POST_ID,
    assemble_audit,
    audit_authorized,
    body_match,
    read_post_records,
    verify_retrieved,
)
from x_integration.state import MentionLedger


def _db(path: Path, *, reply_id: str, text: str, status: str, http_status: int) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE publications (
            post_id TEXT PRIMARY KEY,
            reply_text TEXT,
            x_reply_id TEXT,
            status TEXT,
            http_status INTEGER,
            detail TEXT,
            problem_json TEXT,
            created_at TEXT,
            updated_at TEXT,
            origin TEXT
        );
        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            status TEXT,
            attempts INTEGER,
            post_id TEXT,
            author_id TEXT,
            conversation_id TEXT,
            reply_text TEXT,
            skip_reason TEXT,
            updated_at TEXT
        );
        CREATE TABLE replied_posts (
            post_id TEXT PRIMARY KEY,
            event_id TEXT
        );
        CREATE TABLE oauth_cache (
            name TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT
        );
        CREATE TABLE poll_state (
            name TEXT PRIMARY KEY,
            since_id TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO publications VALUES (?, ?, ?, ?, ?, '', '{}', 't1', 't2', 'automatic')
        """,
        (TARGET_POST_ID, text, reply_id, status, http_status),
    )
    conn.execute(
        """
        INSERT INTO events VALUES ('poll:' || ?, ?, 1, ?, '2082957781293035520', ?, ?, '', 't2')
        """,
        (TARGET_POST_ID, status, TARGET_POST_ID, TARGET_POST_ID, text),
    )
    conn.execute(
        "INSERT INTO replied_posts VALUES (?, ?)",
        (TARGET_POST_ID, "poll:" + TARGET_POST_ID),
    )
    conn.execute("INSERT INTO oauth_cache VALUES ('user', 'secret-token', 'refresh')")
    conn.execute("INSERT INTO poll_state VALUES ('mentions', ?)", (TARGET_POST_ID,))
    conn.commit()
    conn.close()


def test_authorization_rejects_a_missing_or_wrong_token():
    assert audit_authorized("", secret="webhook-secret") is False
    assert audit_authorized("nope", secret="webhook-secret") is False
    assert audit_authorized("webhook-secret", secret="webhook-secret") is True
    assert audit_authorized("webhook-secret", secret="") is False


def test_posted_row_is_not_confirmed_when_x_cannot_return_it():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "mentions.sqlite"
        _db(path, reply_id="2120990000000000001", text="The stored line.", status="posted", http_status=201)
        records = read_post_records(path)
        assert records["access_token"] == "secret-token"
        records.pop("access_token")
        result = assemble_audit(
            records,
            {"http_status": 404, "availability": "unavailable", "error": {"title": "Not Found Error"}},
            [],
        )
        assert result["publication_id"] == "2120990000000000001"
        assert result["stored_status"] == "posted"
        assert result["stored_http_status"] == 201
        assert result["parent_post_id"] == TARGET_POST_ID
        assert result["verification_status"] == "unavailable"
        assert "stored_reply_text" not in result
        assert "access_token" not in result
        again = sqlite3.connect(path)
        assert again.execute("SELECT since_id FROM poll_state").fetchone()[0] == TARGET_POST_ID
        again.close()


def test_matching_retrieval_confirms_author_parent_and_text():
    retrieved = {
        "http_status": 200,
        "availability": "accessible",
        "author_id": BOT_USER_ID,
        "author_username": "MoodyBotAI",
        "text": "The stored line.",
        "note_text": "",
        "in_reply_to_tweet_id": TARGET_POST_ID,
        "error": {},
    }
    check = verify_retrieved("The stored line.", "2120990000000000001", retrieved)
    assert check["author_matches"] is True
    assert check["parent_matches"] is True
    assert check["body_match"] == "exact"
    assert check["verification_status"] == "confirmed"
    prefixed = dict(retrieved)
    prefixed["text"] = "@MattCanham805 The stored line."
    prefixed_check = verify_retrieved("The stored line.", "2120990000000000001", prefixed)
    assert body_match("The stored line.", prefixed["text"]) == "mention_prefix"
    assert prefixed_check["verification_status"] == "confirmed"


def test_another_accounts_reply_is_not_called_moodybot():
    records = {
        "post_id": TARGET_POST_ID,
        "publications": [],
        "events": [],
        "replied_posts": [],
    }
    result = assemble_audit(
        records,
        {"http_status": 0, "availability": "token_unavailable"},
        [{
            "id": "2120990000000000002",
            "author_id": "2082957781293035520",
            "author_username": "MattCanham805",
            "in_reply_to_tweet_id": TARGET_POST_ID,
            "text": "not the bot",
        }],
    )
    assert result["publication_id"] == ""
    assert result["verification_status"] == "no_reply_id"
    reply = result["visibility"]["direct_replies"][0]
    assert reply["is_moodybot"] is False
    assert "text" not in reply


def test_outcome_names_count_posts_rather_than_dry_runs():
    with TemporaryDirectory() as tmp:
        book = MentionLedger(Path(tmp) / "mentions.sqlite")
        assert book.reserve_automatic_publication(TARGET_POST_ID, "body") == "claimed"
        book.finish_publication(TARGET_POST_ID, status="posted", x_reply_id="2120747058424586436", http_status=201)
        failed_id = "2120990000000000099"
        assert book.claim("poll:" + failed_id, failed_id, "2082957781293035520", failed_id).proceed
        book.finish(
            "poll:" + failed_id,
            status="skipped",
            skip_reason="generation_failed",
            post_id=failed_id,
        )
        summary = book.outcome_summary()
        assert summary["x_publications_succeeded"] == 1
        assert summary["x_publications_failed"] == 0
        assert summary["generation_failures"] == 1
        assert summary["model_generations"] == 0
        assert summary["battle_publications"] == 0
        assert summary["last_verification_result"] == ""


if __name__ == "__main__":
    test_authorization_rejects_a_missing_or_wrong_token()
    test_posted_row_is_not_confirmed_when_x_cannot_return_it()
    test_matching_retrieval_confirms_author_parent_and_text()
    test_another_accounts_reply_is_not_called_moodybot()
    test_outcome_names_count_posts_rather_than_dry_runs()
    print("reply audit ok")
