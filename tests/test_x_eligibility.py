# -*- coding: utf-8 -*-
"""Mention eligibility is the same decision for observation and publishing."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.eligibility import classify_mention
from x_integration.poll import _apply, observe_once, FetchResult
from x_integration.state import MentionLedger, operating_mode
from x_integration.webhook import process_mention
from x_integration.events import Mention


BOT = "1912252811469025282"
CONTRIBUTION = "2120100442286002548"
QUESTION = "2120100442286002549"
OLD_FAILED = "2119262820428865635"


def _clear():
    for key in (
        "X_REPLIES_ENABLED",
        "X_ONE_REPLY_GATE",
        "X_OPERATING_MODE",
        "X_BOT_USER_ID",
        "X_DAILY_MODEL_CALL_LIMIT",
        "X_USER_ACCESS_TOKEN",
        "X_STATE_DIR",
    ):
        os.environ.pop(key, None)


def _tweet(post_id, text, author="2081454353987297280", parent=""):
    return {
        "id": post_id,
        "author_id": author,
        "author_username": "buildwithpb",
        "text": text,
        "conversation_id": post_id,
        "parent_author_id": parent,
    }


def _contribution():
    return _tweet(
        CONTRIBUTION,
        "@MoodyBotAI @AskMoodyBot stay patient, focus on one small step today"
        "—progress builds momentum, even when hope feels distant.",
        parent=BOT,
    )


def _decide(tweet, **kwargs):
    return classify_mention(
        tweet,
        user_id=kwargs.get("user_id", BOT),
        floor=kwargs.get("floor", "0"),
        already_replied=kwargs.get("already_replied", False),
    )


def test_contribution_is_not_a_request_for_observation_or_publishing():
    decision = _decide(_contribution())
    assert decision["eligible"] is False
    assert decision["classification"] == "not_requested"
    assert decision["reason"] == "contribution"
    os.environ["X_BOT_USER_ID"] = BOT
    os.environ["X_USER_ACCESS_TOKEN"] = "test-user-token"
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_OPERATING_MODE"] = "limited_beta"
    sent = []
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            book = MentionLedger(path)
            assert book.claim_publication(OLD_FAILED, "old") == "claimed"
            book.finish_publication(OLD_FAILED, status="failed", http_status=403, detail="Forbidden")
            before = book.publication(OLD_FAILED)

            def fetch(user_id, token, since_id, pagination):
                return FetchResult(status="ok", tweets=[_contribution(), _tweet(QUESTION, "@MoodyBotAI what should I do")])

            observed = observe_once(ledger=book, fetch=fetch)
            queued = [item["post_id"] for item in observed["queued"]]
            reasons = {item["post_id"]: item["reason"] for item in observed["filtered"]}
            assert CONTRIBUTION not in queued
            assert reasons[CONTRIBUTION] == "not_requested"
            assert queued == [QUESTION]
            saved = book.mention_review(CONTRIBUTION)
            assert saved["classification"] == "not_requested"
            assert saved["reason"] == "contribution"
            result = _apply(book, [_contribution()])
            assert result["status"] == "ok"
            assert sent == []
            assert book.publication(CONTRIBUTION) is None
            assert book.publication(OLD_FAILED) == before
            assert book.mention_review(CONTRIBUTION)["classification"] == "not_requested"
    finally:
        _clear()


def test_requests_are_eligible_and_uncertain_intent_is_not():
    direct = _decide(_tweet("31", "@MoodyBotAI what should I do now"))
    assert direct["eligible"] is True
    assert direct["reason"] == "direct_request"
    follow = _decide(
        _tweet("32", "@MoodyBotAI say more about that first point", parent=BOT)
    )
    assert follow["eligible"] is True
    assert follow["reason"] == "follow_up"
    plain = _decide(_tweet("33", "@MoodyBotAI tell me how to start over"))
    assert "?" not in "@MoodyBotAI tell me how to start over"
    assert plain["eligible"] is True
    assert plain["reason"] == "direct_request"
    empty = _decide(_tweet("34", "@MoodyBotAI"))
    assert empty["eligible"] is False
    assert empty["classification"] == "empty"
    own = _decide(_tweet("35", "@MoodyBotAI what should I do", author=BOT))
    assert own["eligible"] is False
    assert own["classification"] == "own_post"
    duplicate = _decide(_tweet("36", "@MoodyBotAI what should I do"), already_replied=True)
    assert duplicate["eligible"] is False
    assert duplicate["reason"] == "duplicate_parent"
    uncertain = _decide(_tweet("37", "@MoodyBotAI that was a long week"))
    assert uncertain["eligible"] is False
    assert uncertain["classification"] == "uncertain"
    assert uncertain["reason"] == "review"


def test_uncertain_mention_is_not_published():
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_OPERATING_MODE"] = "limited_beta"
    os.environ["X_BOT_USER_ID"] = BOT
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "5"
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            result = _apply(book, [_tweet("41", "@MoodyBotAI that was a long week")])
            assert result["status"] == "ok"
            assert book.publication("41") is None
            assert book.mention_review("41")["classification"] == "uncertain"
    finally:
        _clear()


def test_consumed_gate_stays_consumed_and_beta_does_not_reset_it():
    os.environ["X_ONE_REPLY_GATE"] = "true"
    os.environ["X_OPERATING_MODE"] = "one_reply_test"
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_BOT_USER_ID"] = BOT
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "5"
    sent = []
    import x_integration.account_probe as probe
    import x_integration.publish_once as publish_mod
    import x_integration.reply as reply_mod
    import x_integration.webhook as webhook_mod

    original_token = probe.validated_user_token
    original_send = publish_mod.send_reply
    original_draft = reply_mod.draft_mention_reply
    original_parent = webhook_mod._confirm_parent
    probe.validated_user_token = lambda book=None: {
        "ok": True,
        "token": "cached-access",
        "http_status": 200,
        "username": "MoodyBotAI",
        "user_id": BOT,
    }
    reply_mod.draft_mention_reply = lambda text, conversation_id, complete=None: "Noted."
    webhook_mod._confirm_parent = lambda token, post_id: {
        "ok": True,
        "reason": "authorized",
        "http_status": 200,
    }

    def send(token, post_id, text):
        sent.append(post_id)
        return {"outcome": "posted", "http_status": 201, "detail": "", "x_reply_id": "reply-9"}

    publish_mod.send_reply = send
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            book = MentionLedger(path)
            book.stop_activation("posted", "2119952806698520807")
            assert book.claim_publication(OLD_FAILED, "old") == "claimed"
            book.finish_publication(OLD_FAILED, status="failed", http_status=403, detail="Forbidden")
            before = book.publication(OLD_FAILED)
            reopened = MentionLedger(path)
            assert reopened.activation_status()["mode"] == "stopped"
            assert reopened.activation_status()["remaining"] == 0
            assert reopened.activation_status()["stop_reason"] == "posted"
            assert reopened.claim_activation_attempt(QUESTION) == "exhausted"
            blocked = process_mention(
                Mention(
                    event_id=f"poll:{QUESTION}",
                    post_id=QUESTION,
                    author_id="2081454353987297280",
                    text="@MoodyBotAI what should I do",
                    conversation_id=QUESTION,
                ),
                ledger=reopened,
            )
            assert blocked["status"] == "activation_stopped"
            assert sent == []
            os.environ["X_OPERATING_MODE"] = "limited_beta"
            posted = process_mention(
                Mention(
                    event_id=f"poll:{QUESTION}",
                    post_id=QUESTION,
                    author_id="2081454353987297280",
                    text="@MoodyBotAI what should I do",
                    conversation_id=QUESTION,
                ),
                ledger=MentionLedger(path),
            )
            assert posted["status"] == "posted"
            assert sent == [QUESTION]
            again = MentionLedger(path)
            gate = again.activation_status()
            assert gate["mode"] == "stopped"
            assert gate["remaining"] == 0
            assert gate["stop_reason"] == "posted"
            assert again.publication(OLD_FAILED) == before
    finally:
        probe.validated_user_token = original_token
        publish_mod.send_reply = original_send
        reply_mod.draft_mention_reply = original_draft
        webhook_mod._confirm_parent = original_parent
        _clear()


def test_daily_cap_allows_only_one_of_two_concurrent_claims():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "mentions.sqlite"
        book = MentionLedger(path)
        for number in range(4):
            post_id = str(3000 + number)
            assert book.reserve_automatic_publication(post_id, "reply") == "claimed"
            book.finish_publication(post_id, status="posted", x_reply_id=f"r{number}", http_status=201)
        results = []

        def worker(post_id):
            worker_book = MentionLedger(path)
            results.append(worker_book.reserve_automatic_publication(post_id, "last"))

        threads = [threading.Thread(target=worker, args=(str(4000 + number),)) for number in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(results) == ["cap", "claimed"]
        assert MentionLedger(path).automatic_reply_allowance()["remaining"] == 0


def test_invalid_operating_mode_is_disabled():
    os.environ["X_OPERATING_MODE"] = "beta"
    try:
        assert operating_mode() == "disabled"
    finally:
        _clear()
    assert operating_mode() == "disabled"


def test_overlong_autonomous_reply_is_not_sent_and_two_auth_failures_halt():
    os.environ["X_REPLIES_ENABLED"] = "true"
    os.environ["X_OPERATING_MODE"] = "limited_beta"
    os.environ["X_BOT_USER_ID"] = BOT
    os.environ["X_DAILY_MODEL_CALL_LIMIT"] = "5"
    sent = []
    import x_integration.account_probe as probe
    import x_integration.publish_once as publish_mod
    import x_integration.reply as reply_mod

    original_token = probe.validated_user_token
    original_send = publish_mod.send_reply
    original_draft = reply_mod.draft_mention_reply
    probe.validated_user_token = lambda book=None: {"ok": True, "token": "cached-access", "http_status": 200}
    reply_mod.draft_mention_reply = lambda text, conversation_id, complete=None: "a" * 281
    publish_mod.send_reply = lambda token, post_id, text: sent.append(post_id)
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            book = MentionLedger(path)
            result = process_mention(
                Mention(
                    event_id="poll:51",
                    post_id="51",
                    author_id="2081454353987297280",
                    text="@MoodyBotAI what should I do",
                    conversation_id="51",
                ),
                ledger=book,
            )
            assert result["status"] == "not_sent"
            assert result["reason"] == "reply_too_long"
            assert sent == []
            assert book.note_publish_failure("authorization") == ""
            assert book.note_publish_failure("authorization") == "authorization"
            halted = process_mention(
                Mention(
                    event_id="poll:52",
                    post_id="52",
                    author_id="2081454353987297280",
                    text="@MoodyBotAI what should I do",
                    conversation_id="52",
                ),
                ledger=MentionLedger(path),
            )
            assert halted["status"] == "publish_halted"
            assert sent == []
            assert MentionLedger(path).publish_halted() is True
    finally:
        probe.validated_user_token = original_token
        publish_mod.send_reply = original_send
        reply_mod.draft_mention_reply = original_draft
        _clear()


if __name__ == "__main__":
    test_contribution_is_not_a_request_for_observation_or_publishing()
    test_requests_are_eligible_and_uncertain_intent_is_not()
    test_uncertain_mention_is_not_published()
    test_consumed_gate_stays_consumed_and_beta_does_not_reset_it()
    test_daily_cap_allows_only_one_of_two_concurrent_claims()
    test_invalid_operating_mode_is_disabled()
    test_overlong_autonomous_reply_is_not_sent_and_two_auth_failures_halt()
    print("eligibility ok")
