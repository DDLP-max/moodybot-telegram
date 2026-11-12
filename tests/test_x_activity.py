# -*- coding: utf-8 -*-
"""Activity rows come from the ledger and from X, not from the cursor."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.activity import assemble_activity, read_activity_ledger
from x_integration.reply_audit import BOT_USER_ID, audit_authorized

PARENT = "2120716575195971928"
REPLY = "2120723000219869687"
GROK = "1720665183188922368"
RELATIONSHIP = "2120746490700386493"


def _ledger(**extra) -> dict:
    base = {
        "since_id": RELATIONSHIP,
        "publications": [],
        "events": [],
        "engagement": [],
        "reviews": [],
        "battles": [],
        "generations": [],
    }
    base.update(extra)
    return base


def _reply(text: str, parent: str = PARENT) -> dict:
    return {
        "id": REPLY,
        "author_id": BOT_USER_ID,
        "author_username": "MoodyBotAI",
        "text": text,
        "note_text": "",
        "in_reply_to_tweet_id": parent,
        "http_status": 200,
        "availability": "accessible",
    }


def test_missing_secret_is_rejected():
    assert audit_authorized("", secret="webhook-secret") is False
    assert audit_authorized("webhook-secret", secret="webhook-secret") is True


def test_cursor_does_not_make_a_visible_reply_a_publication():
    text = "@grok @MattCanham805 Because they get so good at explaining their disasters that the disasters start looking like choices."
    result = assemble_activity(
        _ledger(
            engagement=[{
                "post_id": PARENT,
                "author_id": GROK,
                "classification": "AMBIENT",
                "reason": "not_mentioned",
            }],
            battles=[{
                "post_id": PARENT,
                "response_id": "",
                "classification": "DIRECT_CHALLENGE",
            }],
        ),
        [_reply(text)],
        {
            PARENT: {
                "author_id": GROK,
                "author_username": "grok",
                "text": "Why do highly intelligent people so often ruin their own lives?",
                "note_text": "",
                "http_status": 200,
                "availability": "accessible",
            }
        },
    )
    assert result["since_id"] == RELATIONSHIP
    assert result["lanes"]["automatic_replies"] == []
    assert result["lanes"]["battle_replies"] == []
    row = result["lanes"]["visible_without_ledger_publication"][0]
    assert row["mention_id"] == PARENT
    assert row["author_id"] == GROK
    assert row["classification"] == "AMBIENT"
    assert row["classification_reason"] == "not_mentioned"
    assert row["extracted_question"] == ""
    assert row["extracted_question_source"] == "not_stored"
    assert "ruin their own lives" in row["incoming_text"]
    assert row["x_reply_id"] == REPLY
    assert row["verified_parent_id"] == PARENT
    assert row["published_text"] == text
    assert row["x_verification"] == "accessible_not_in_ledger"
    assert row["application_published"] is False
    assert row["model_generation_status"] == "not_recorded"
    assert row["model_cost_usd"] is None
    assert row["battle_response_id"] == ""


def test_direct_challenge_without_a_battle_response_stays_automatic():
    stored = "The stored line."
    result = assemble_activity(
        _ledger(
            publications=[{
                "post_id": PARENT,
                "reply_text": stored,
                "x_reply_id": REPLY,
                "status": "posted",
                "origin": "automatic",
                "http_status": 201,
            }],
            engagement=[{
                "post_id": PARENT,
                "author_id": GROK,
                "classification": "DIRECT_CHALLENGE",
                "reason": "direct_challenge",
            }],
            generations=[{
                "id": 1,
                "post_id": PARENT,
                "status": "confirmed",
                "charged_usd": 0.01,
            }],
        ),
        [_reply("@grok " + stored)],
        {},
    )
    row = result["lanes"]["automatic_replies"][0]
    assert result["lanes"]["battle_replies"] == []
    assert row["classification"] == "DIRECT_CHALLENGE"
    assert row["x_verification"] == "confirmed"
    assert row["body_match"] == "mention_prefix"
    assert row["application_published"] is True
    assert row["model_generation_status"] == "confirmed"
    assert row["model_cost_usd"] == 0.01
    assert row["verified_parent_id"] == PARENT


def test_a_stored_battle_response_is_a_battle_reply():
    result = assemble_activity(
        _ledger(
            publications=[{
                "post_id": PARENT,
                "reply_text": "Battle line.",
                "x_reply_id": REPLY,
                "status": "posted",
                "origin": "automatic",
            }],
            battles=[{"post_id": PARENT, "response_id": REPLY, "classification": "DIRECT_CHALLENGE"}],
        ),
        [_reply("Battle line.")],
        {},
    )
    assert result["lanes"]["automatic_replies"] == []
    assert result["lanes"]["battle_replies"][0]["application_published"] is True
    assert result["lanes"]["battle_replies"][0]["x_verification"] == "confirmed"


def test_dry_runs_and_manual_posts_stay_in_their_own_lanes():
    result = assemble_activity(
        _ledger(
            publications=[{
                "post_id": "2119950492617081251",
                "reply_text": "Test noted.",
                "x_reply_id": "2119951617869164634",
                "status": "posted",
                "origin": "",
            }],
            events=[{
                "event_id": "poll:dry",
                "post_id": "2120000000000000001",
                "author_id": "2082957781293035520",
                "status": "dry_run",
                "reply_text": "draft only",
            }],
        ),
        [],
        {},
    )
    assert result["lanes"]["historical_publications"][0]["mention_id"] == "2119950492617081251"
    assert result["lanes"]["historical_publications"][0]["publishing_origin"] == ""
    dry = result["lanes"]["dry_runs"][0]
    assert dry["published_text"] == ""
    assert dry["application_published"] is False
    assert dry["x_reply_id"] == ""
    assert "access_token" not in result


def test_reading_the_ledger_does_not_move_the_cursor():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "mentions.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE poll_state (name TEXT PRIMARY KEY, since_id TEXT)")
        conn.execute("INSERT INTO poll_state VALUES ('mentions', ?)", (RELATIONSHIP,))
        conn.execute(
            "CREATE TABLE oauth_cache (name TEXT PRIMARY KEY, access_token TEXT, refresh_token TEXT)"
        )
        conn.execute("INSERT INTO oauth_cache VALUES ('user', 'secret-token', 'refresh-token')")
        conn.commit()
        conn.close()
        ledger = read_activity_ledger(path)
        assert ledger["since_id"] == RELATIONSHIP
        assert ledger["access_token"] == "secret-token"
        again = sqlite3.connect(path)
        assert again.execute("SELECT since_id FROM poll_state").fetchone()[0] == RELATIONSHIP
        again.close()


if __name__ == "__main__":
    test_missing_secret_is_rejected()
    test_cursor_does_not_make_a_visible_reply_a_publication()
    test_direct_challenge_without_a_battle_response_stays_automatic()
    test_a_stored_battle_response_is_a_battle_reply()
    test_dry_runs_and_manual_posts_stay_in_their_own_lanes()
    test_reading_the_ledger_does_not_move_the_cursor()
    print("activity ok")
