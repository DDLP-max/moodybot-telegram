# -*- coding: utf-8 -*-
"""Opt-out is stored by user id and blocks later automated replies."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.events import Mention
from x_integration.opt_out import detect_opt_out
from x_integration.poll import _classify_mention
from x_integration.publish_once import send_reply
from x_integration.state import MentionLedger
from x_integration.webhook import _publish_automatic, process_mention


USER = "424242"
POST = "2120746490700386493"


def _tweet(text: str, username: str = "alpha", post_id: str = POST) -> dict:
    return {
        "id": post_id,
        "author_id": USER,
        "author_username": username,
        "conversation_id": POST,
        "text": text,
    }


def _mention(text: str, post_id: str, username: str = "alpha") -> Mention:
    return Mention(
        event_id=f"poll:{post_id}",
        post_id=post_id,
        author_id=USER,
        text=text,
        conversation_id=POST,
        author_username=username,
    )


def test_stop_is_persistent_and_blocks_the_next_question():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "mentions.sqlite"
        book = MentionLedger(path)
        first = _classify_mention(book, _tweet("@MoodyBotAI stop"), "", "0")
        assert first["eligible"] is False
        assert first["classification"] == "opt_out"
        assert book.is_opted_out(USER) is True
        again = MentionLedger(path)
        assert again.is_opted_out(USER) is True
        question = _classify_mention(
            again,
            _tweet("@MoodyBotAI what should I do now", username="renamed", post_id="2120746490700386494"),
            "",
            "0",
        )
        assert question["eligible"] is False
        assert question["classification"] == "opt_out"
        assert again.list_opt_outs()[0]["username"] == "alpha"
        summary = again.opt_out_summary()
        assert summary["opted_out_users"] == 1
        assert summary["enforcement_active"] is True
        assert "user_id" not in summary


def test_opt_out_precedes_ambient_and_battle_classification():
    with TemporaryDirectory() as tmp:
        book = MentionLedger(Path(tmp) / "mentions.sqlite")
        ambient = process_mention(
            _mention("@MoodyBotAI leave me alone", "2120746490700386501"),
            ledger=book,
        )
        assert ambient["status"] == "skipped"
        assert ambient["reason"] == "opt_out"
        challenge = process_mention(
            _mention("@MoodyBotAI @grok prove that claim", "2120746490700386502"),
            ledger=book,
        )
        assert challenge["reason"] == "opt_out"
        assert book.model_calls_today() == 0
        assert book.publication("2120746490700386502") is None


def test_quoted_and_incidental_stop_are_not_opt_outs():
    assert detect_opt_out('@MoodyBotAI he said "stop"') == ""
    assert detect_opt_out("@MoodyBotAI if I say stop, ignore that") == ""
    assert detect_opt_out("@MoodyBotAI stop by the office on Friday") == ""
    assert detect_opt_out("@MoodyBotAI don't stop") == ""
    assert detect_opt_out("stop") == ""
    assert detect_opt_out("@MoodyBotAI please stop replying to me") == "stop_replying"
    assert detect_opt_out("@MoodyBotAI do not contact me") == "do_not_contact"


def test_publish_boundary_does_not_post_after_opt_out():
    import httpx

    calls = {"n": 0}

    def explode(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("opt-out reached the network")

    original = httpx.post
    httpx.post = explode
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            book.record_opt_out(USER, "alpha", POST, "stop")
            outcome = send_reply(
                "access-secret-value",
                POST,
                "A reply that must not post.",
                origin="automatic",
                publishing_path="webhook._publish_automatic",
                author_id=USER,
                enforce_opt_out=True,
                audit=book,
            )
    finally:
        httpx.post = original
    assert calls["n"] == 0
    assert outcome["outcome"] == "failed"
    assert outcome["detail"] == "opt_out"


def test_unreadable_registry_does_not_post():
    import httpx

    class Broken:
        def is_opted_out(self, _user_id):
            raise OSError("registry unreadable")

    calls = {"n": 0}

    def explode(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("unreadable registry reached the network")

    original = httpx.post
    httpx.post = explode
    try:
        refused = send_reply(
            "access-secret-value",
            POST,
            "A reply that must not post.",
            origin="automatic",
            publishing_path="webhook._publish_automatic",
            author_id=USER,
            enforce_opt_out=True,
            audit=Broken(),
        )
        missing = send_reply(
            "access-secret-value",
            POST,
            "A reply that must not post.",
            origin="automatic",
            publishing_path="webhook._publish_automatic",
            author_id=USER,
            enforce_opt_out=True,
            audit=None,
        )
    finally:
        httpx.post = original
    assert calls["n"] == 0
    assert refused["detail"] == "opt_out_unavailable"
    assert missing["detail"] == "opt_out_unavailable"


def test_migration_keeps_existing_rows():
    import sqlite3

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "mentions.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE events (event_id TEXT PRIMARY KEY, status TEXT NOT NULL)")
        conn.execute("INSERT INTO events (event_id, status) VALUES ('keep-me', 'posted')")
        conn.execute("CREATE TABLE publications (post_id TEXT PRIMARY KEY, reply_text TEXT NOT NULL)")
        conn.execute("INSERT INTO publications (post_id, reply_text) VALUES ('99', 'stored')")
        conn.commit()
        conn.close()
        first = MentionLedger(path)
        second = MentionLedger(path)
        conn = sqlite3.connect(path)
        kept = conn.execute("SELECT status FROM events WHERE event_id = 'keep-me'").fetchone()
        stored = conn.execute("SELECT reply_text FROM publications WHERE post_id = '99'").fetchone()
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        conn.close()
        assert kept[0] == "posted"
        assert stored[0] == "stored"
        assert "x_user_opt_outs" in tables
        assert "x_opt_out_suppressions" in tables
        assert "x_opt_out_state" in tables
        assert first.opt_out_summary()["opted_out_users"] == 0
        assert second.opt_out_summary()["opted_out_users"] == 0


def test_disabled_replies_stop_the_automatic_publisher():
    os.environ["X_REPLIES_ENABLED"] = "false"
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            result = _publish_automatic(
                book,
                _mention("@MoodyBotAI what should I do now", POST),
                "This must not post.",
            )
    finally:
        os.environ.pop("X_REPLIES_ENABLED", None)
    assert result["status"] == "not_publishing"
    assert result["reason"] == "replies_disabled"


if __name__ == "__main__":
    test_stop_is_persistent_and_blocks_the_next_question()
    test_opt_out_precedes_ambient_and_battle_classification()
    test_quoted_and_incidental_stop_are_not_opt_outs()
    test_publish_boundary_does_not_post_after_opt_out()
    test_unreadable_registry_does_not_post()
    test_migration_keeps_existing_rows()
    test_disabled_replies_stop_the_automatic_publisher()
    print("opt out ok")
