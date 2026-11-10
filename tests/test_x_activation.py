# -*- coding: utf-8 -*-
"""One automatic X POST, then the gate stays shut."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.poll import _apply
from x_integration.state import MentionLedger
from x_integration.webhook import process_mention


FIRST = "2119952806698520807"
SECOND = "2120100442286002548"
OLD_FAILED = "2119262820428865635"
OLD_POSTED = "2119950492617081251"
OLD_REPLY = "2119951617869164634"


def _clear():
    for key in (
        "X_REPLIES_ENABLED",
        "X_ONE_REPLY_GATE",
        "X_BOT_USER_ID",
        "X_DAILY_MODEL_CALL_LIMIT",
        "X_USER_ACCESS_TOKEN",
        "X_STATE_DIR",
    ):
        os.environ.pop(key, None)


def _arm():
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_ONE_REPLY_GATE"] = "true"
    os.environ["X_BOT_USER_ID"] = "1912252811469025282"
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "25"


def _tweets():
    return [
        {
            "id": FIRST,
            "author_id": "2082957781293035520",
            "text": "Hey @MoodyBotAI one piece of advice",
            "conversation_id": FIRST,
        },
        {
            "id": SECOND,
            "author_id": "2081454353987297280",
            "text": "Hey @MoodyBotAI another question",
            "conversation_id": SECOND,
        },
    ]


def _seed_history(book: MentionLedger) -> dict:
    assert book.claim_publication(OLD_FAILED, "old draft") == "claimed"
    book.finish_publication(
        OLD_FAILED,
        status="failed",
        http_status=403,
        detail="Forbidden",
        problem={"title": "Forbidden"},
    )
    assert book.claim_publication(OLD_POSTED, "Test noted.") == "claimed"
    book.finish_publication(
        OLD_POSTED,
        status="posted",
        x_reply_id=OLD_REPLY,
        http_status=201,
        detail="",
    )
    return {
        OLD_FAILED: book.publication(OLD_FAILED),
        OLD_POSTED: book.publication(OLD_POSTED),
    }


def _history_unchanged(book: MentionLedger, before: dict) -> None:
    for post_id, saved in before.items():
        current = book.publication(post_id)
        assert current == saved


def _patch(send):
    import x_integration.account_probe as probe
    import x_integration.publish_once as publish_mod
    import x_integration.reply as reply_mod

    original = (
        probe.validated_user_token,
        reply_mod.draft_mention_reply,
        publish_mod.send_reply,
    )
    probe.validated_user_token = lambda book=None: {
        "ok": True,
        "token": "cached-access",
        "http_status": 200,
        "username": "MoodyBotAI",
        "user_id": "1912252811469025282",
        "source": "cache",
        "reason": "",
    }
    reply_mod.draft_mention_reply = lambda text, conversation_id, complete=None: "Noted."
    publish_mod.send_reply = send
    return original


def _restore(original) -> None:
    import x_integration.account_probe as probe
    import x_integration.publish_once as publish_mod
    import x_integration.reply as reply_mod

    probe.validated_user_token, reply_mod.draft_mention_reply, publish_mod.send_reply = original


def test_two_mentions_allow_one_post_and_a_success_stops_the_next():
    _arm()
    posts = []

    def send(token, post_id, text):
        posts.append(post_id)
        return {"outcome": "posted", "http_status": 201, "detail": "", "x_reply_id": "reply-1"}

    original = _patch(send)
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            before = _seed_history(book)
            result = _apply(book, _tweets())
            assert posts == [FIRST]
            assert result["since_id"] == FIRST
            assert book.publication(FIRST)["status"] == "posted"
            assert book.publication(SECOND) is None
            gate = book.activation_status()
            assert gate["mode"] == "stopped"
            assert gate["remaining"] == 0
            assert gate["stop_reason"] == "posted"
            again = _apply(book, _tweets())
            assert posts == [FIRST]
            assert again["status"] == "activation_stopped"
            assert book.get_since_id() == FIRST
            assert book.publication(SECOND) is None
            _history_unchanged(book, before)
            os.environ["X_REPLIES_ENABLED"] = "true"
            blocked = process_mention(
                __import__("x_integration.events", fromlist=["Mention"]).Mention(
                    event_id=f"poll:{SECOND}",
                    post_id=SECOND,
                    author_id="2081454353987297280",
                    text="Hey @MoodyBotAI another question",
                    conversation_id=SECOND,
                ),
                ledger=book,
            )
            assert blocked["status"] == "activation_stopped"
            assert posts == [FIRST]
    finally:
        _restore(original)
        _clear()


def test_http_403_consumes_the_allowance_and_leaves_history():
    _arm()
    posts = []

    def send(token, post_id, text):
        posts.append(post_id)
        return {
            "outcome": "failed",
            "http_status": 403,
            "detail": "Forbidden",
            "problem": {"title": "Forbidden", "status": 403},
            "x_reply_id": "",
        }

    original = _patch(send)
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            book = MentionLedger(path)
            before = _seed_history(book)
            _apply(book, _tweets())
            assert posts == [FIRST]
            saved = book.publication(FIRST)
            assert saved["status"] == "failed"
            assert saved["http_status"] == 403
            assert saved["detail"] == "Forbidden"
            assert book.publication(SECOND) is None
            gate = book.activation_status()
            assert gate["remaining"] == 0
            assert gate["stop_reason"] == "rejected"
            reopened = MentionLedger(path)
            assert reopened.activation_status()["remaining"] == 0
            assert reopened.activation_status()["stop_reason"] == "rejected"
            _history_unchanged(reopened, before)
    finally:
        _restore(original)
        _clear()


def test_timeout_consumes_the_allowance_and_stays_ambiguous():
    _arm()
    posts = []

    def send(token, post_id, text):
        posts.append(post_id)
        return {"outcome": "ambiguous", "http_status": 0, "detail": "timeout", "x_reply_id": ""}

    original = _patch(send)
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            book = MentionLedger(path)
            _apply(book, _tweets())
            assert posts == [FIRST]
            saved = book.publication(FIRST)
            assert saved["status"] == "ambiguous"
            assert saved["detail"] == "timeout"
            assert book.publication(SECOND) is None
            assert book.activation_status()["stop_reason"] == "ambiguous"
            reopened = MentionLedger(path)
            assert reopened.activation_status()["remaining"] == 0
            assert reopened.publication(FIRST)["status"] == "ambiguous"
            _apply(reopened, _tweets())
            assert posts == [FIRST]
    finally:
        _restore(original)
        _clear()


def test_generation_and_authentication_failures_stop_before_the_next_mention():
    _arm()
    drafted = []
    posts = []
    import x_integration.account_probe as probe
    import x_integration.publish_once as publish_mod
    import x_integration.reply as reply_mod

    original_draft = reply_mod.draft_mention_reply
    original_send = publish_mod.send_reply
    original_token = probe.validated_user_token

    def boom(text, conversation_id, complete=None):
        drafted.append(text)
        raise RuntimeError("model down")

    reply_mod.draft_mention_reply = boom
    publish_mod.send_reply = lambda token, post_id, text: posts.append(post_id)
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            result = _apply(book, _tweets())
            assert result["status"] == "not_sent"
            assert result["since_id"] == ""
            assert posts == []
            assert len(drafted) == 1
            assert book.publication(FIRST) is None
            assert book.publication(SECOND) is None
            assert book.activation_status()["stop_reason"] == "generation_failed"
            assert book.activation_status()["remaining"] == 0
            reopened = MentionLedger(Path(tmp) / "mentions.sqlite")
            assert reopened.activation_status()["remaining"] == 0
    finally:
        reply_mod.draft_mention_reply = original_draft
        publish_mod.send_reply = original_send
        _clear()

    _arm()
    probe.validated_user_token = lambda book=None: {
        "ok": False,
        "token": "",
        "http_status": 401,
        "reason": "rejected",
    }
    reply_mod.draft_mention_reply = lambda text, conversation_id, complete=None: drafted.append(text) or "Noted."
    drafted.clear()
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            result = _apply(book, _tweets())
            assert result["status"] == "not_sent"
            assert result["since_id"] == ""
            assert posts == []
            assert len(drafted) == 1
            assert book.publication(FIRST) is None
            assert book.publication(SECOND) is None
            assert book.automatic_reply_allowance()["remaining"] == 5
            assert book.activation_status()["stop_reason"] == "authentication_failed"
            assert book.activation_status()["remaining"] == 0
    finally:
        probe.validated_user_token = original_token
        reply_mod.draft_mention_reply = original_draft
        publish_mod.send_reply = original_send
        _clear()


def test_two_workers_cannot_claim_the_same_allowance():
    os.environ["X_ONE_REPLY_GATE"] = "true"
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            MentionLedger(path)
            results = []
            errors = []

            def worker(post_id: str) -> None:
                try:
                    book = MentionLedger(path)
                    results.append(book.claim_activation_attempt(post_id))
                except Exception as exc:
                    errors.append(repr(exc))

            threads = [
                threading.Thread(target=worker, args=(FIRST,)),
                threading.Thread(target=worker, args=(SECOND,)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            assert errors == []
            assert sorted(results) == ["claimed", "exhausted"]
            reopened = MentionLedger(path)
            assert reopened.activation_status()["remaining"] == 0
            assert reopened.activation_status()["mode"] == "stopped"
    finally:
        _clear()


def test_gate_off_reports_one_attempt_and_does_not_publish():
    with TemporaryDirectory() as tmp:
        book = MentionLedger(Path(tmp) / "mentions.sqlite")
        assert book.activation_status() == {"mode": "off", "remaining": 1, "stop_reason": ""}
        assert book.claim_activation_attempt(FIRST) == "inactive"
        assert book.publication(FIRST) is None


if __name__ == "__main__":
    test_two_mentions_allow_one_post_and_a_success_stops_the_next()
    test_http_403_consumes_the_allowance_and_leaves_history()
    test_timeout_consumes_the_allowance_and_stays_ambiguous()
    test_generation_and_authentication_failures_stop_before_the_next_mention()
    test_two_workers_cannot_claim_the_same_allowance()
    test_gate_off_reports_one_attempt_and_does_not_publish()
    print("activation gate ok")
