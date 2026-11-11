# -*- coding: utf-8 -*-
"""Shadow conversation decisions. Publishing stays on the existing filter."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.engagement import (
    CHALLENGE,
    CONTRIBUTION,
    DIRECT_REQUEST,
    FOLLOW_UP,
    SPAM,
    UNSAFE,
    decide_engagement,
)
from x_integration.events import Mention
from x_integration.poll import ACTIVATION_POST_ID, FetchResult, observe_once
from x_integration.state import MentionLedger
from x_integration.webhook import process_mention


BOT = "1912252811469025282"
BUILD = "2120100442286002548"
MATT = "2119952806698520807"
FRESH = "2120100442286002549"
OLD_FAILED = "2119262820428865635"
BUILD_TEXT = (
    "@MoodyBotAI @AskMoodyBot stay patient, focus on one small step today"
    "—progress builds momentum, even when hope feels distant."
)
MATT_TEXT = (
    "Hey @MoodyBotAI To all men who survived rock bottom, what's one piece of "
    "advice would you give a man who feels like giving up right  now?"
)
ROOT = "2119934935947747449"


def _clear():
    for key in (
        "X_REPLIES_ENABLED",
        "X_ONE_REPLY_GATE",
        "X_OPERATING_MODE",
        "X_BOT_USER_ID",
        "X_USER_ACCESS_TOKEN",
        "X_CONVERSATION_REPLY_LIMIT",
    ):
        os.environ.pop(key, None)


def _tweet(post_id, text, author="2081454353987297280", username="someone", parent="", parent_author="", conversation=""):
    return {
        "id": post_id,
        "author_id": author,
        "author_username": username,
        "text": text,
        "conversation_id": conversation or post_id,
        "parent_id": parent,
        "parent_author_id": parent_author,
        "parent_text": "Earlier claim." if parent_author else "",
    }


def _decide(tweet, **kwargs):
    return decide_engagement(
        tweet,
        user_id=kwargs.get("user_id", BOT),
        floor=kwargs.get("floor", "0"),
        already_replied=kwargs.get("already_replied", False),
        context=kwargs.get("context"),
        conversation=kwargs.get("conversation"),
        complete=kwargs.get("complete"),
    )


def test_real_contribution_is_observed():
    tweet = _tweet(
        BUILD,
        BUILD_TEXT,
        author="2081454353987297280",
        username="buildwithpb",
        parent=ROOT,
        parent_author=BOT,
        conversation=ROOT,
    )
    decision = _decide(tweet)
    assert decision["classification"] == CONTRIBUTION
    assert decision["respond"] is False
    assert decision["action"] == "observe"
    assert decision["reason"] == "generic_encouragement"


def test_direct_question_is_eligible():
    decision = _decide(_tweet(FRESH, "@MoodyBotAI what should I do about this job"))
    assert decision["classification"] == DIRECT_REQUEST
    assert decision["respond"] is True
    assert decision["action"] == "reply"


def test_challenge_and_evidence_request_are_eligible():
    challenge = _decide(
        _tweet(
            "5001",
            "@MoodyBotAI I disagree. That claim contradicts what you said.",
            parent="5000",
            parent_author=BOT,
        )
    )
    assert challenge["classification"] == CHALLENGE
    assert challenge["respond"] is True
    assert challenge["objective"] == "answer_substance"
    evidence = _decide(
        _tweet(
            "5002",
            "@MoodyBotAI what's your source for that?",
            parent="5000",
            parent_author=BOT,
        )
    )
    assert evidence["classification"] == CHALLENGE
    assert evidence["respond"] is True
    assert "evidence" in evidence["safety_flags"]
    assert evidence["objective"] == "separate_verified_from_uncertain"


def test_meaningful_contribution_can_reply_and_generic_does_not():
    meaningful = _decide(
        _tweet(
            "5003",
            "@MoodyBotAI I tried that after a layoff. The hard part was not the "
            "plan, it was telling my brother I needed the rent covered for a month.",
            parent="5000",
            parent_author=BOT,
        )
    )
    assert meaningful["classification"] == CONTRIBUTION
    assert meaningful["respond"] is True
    assert meaningful["objective"] == "add_an_idea"
    generic = _decide(_tweet("5004", "@MoodyBotAI great point, thanks for sharing"))
    assert generic["respond"] is False
    assert generic["action"] == "observe"


def test_empty_spam_own_and_answered_posts_are_skipped():
    empty = _decide(_tweet("5005", "@MoodyBotAI"))
    assert empty["reason"] == "empty"
    assert empty["respond"] is False
    spam = _decide(_tweet("5006", "@MoodyBotAI follow me for a giveaway", username="promo"))
    assert spam["classification"] == SPAM
    assert spam["respond"] is False
    own = _decide(_tweet("5007", "@MoodyBotAI what should I do", author=BOT, username="MoodyBotAI"))
    assert own["reason"] == "own_post"
    assert own["respond"] is False
    bot = _decide(_tweet("5008", "@MoodyBotAI what should I do", username="helperbot"))
    assert bot["classification"] == SPAM
    assert bot["reason"] == "bot_loop"
    answered = _decide(
        _tweet(MATT, MATT_TEXT, author="2082957781293035520", username="MattCanham805"),
        already_replied=True,
    )
    assert answered["classification"] == DIRECT_REQUEST
    assert answered["respond"] is False
    assert answered["reason"] == "duplicate_parent"


def test_request_without_a_question_mark_is_eligible():
    decision = _decide(_tweet("5009", "@MoodyBotAI tell me what you think about leaving"))
    assert decision["classification"] == DIRECT_REQUEST
    assert decision["respond"] is True


def test_follow_up_keeps_context():
    context = {
        "posts": [
            {"id": "6000", "author_id": BOT, "text": "Most people quit one day before the work gets honest."},
            {"id": "6001", "author_id": "7", "text": "@MoodyBotAI can you give an example of that?"},
        ]
    }
    decision = _decide(
        _tweet("6002", "@MoodyBotAI say more about the first ugly version", parent="6001", parent_author="7"),
        context=context,
    )
    assert decision["classification"] == FOLLOW_UP
    assert decision["respond"] is True
    assert "6000" in decision["context_ids"]
    assert "6002" in decision["context_ids"]


def test_grok_style_thread_keeps_each_intent():
    claim = {"id": "7000", "author_id": BOT, "text": "Most people quit one day before the work gets honest."}
    ask = _tweet(
        "7001",
        "@MoodyBotAI can you give an example of that?",
        parent="7000",
        parent_author=BOT,
        conversation="7000",
    )
    asked = _decide(ask, context={"posts": [claim]})
    assert asked["classification"] == FOLLOW_UP
    assert asked["respond"] is True
    elaboration = {
        "id": "7002",
        "author_id": BOT,
        "text": "They rewrite the plan a third time instead of doing the first ugly version.",
    }
    challenge = _tweet(
        "7003",
        "@MoodyBotAI what's your evidence for that? It sounds like a slogan.",
        parent="7002",
        parent_author=BOT,
        conversation="7000",
    )
    challenged = _decide(challenge, context={"posts": [claim, ask, elaboration]})
    assert challenged["classification"] == CHALLENGE
    assert challenged["respond"] is True
    assert "evidence" in challenged["safety_flags"]
    assert challenged["context_ids"][:3] == ["7000", "7001", "7002"]


def test_missing_context_does_not_speculate():
    tweet = _tweet("7100", "@MoodyBotAI and this", parent="7099", parent_author="")
    tweet["parent_text"] = ""
    decision = _decide(tweet)
    assert decision["respond"] is False
    assert decision["reason"] == "missing_context"


def test_conversation_limit_and_stale_contribution():
    blocked = _decide(
        _tweet("7200", "@MoodyBotAI what should I do"),
        conversation={"bot_replies_24h": 3},
    )
    assert blocked["classification"] == DIRECT_REQUEST
    assert blocked["respond"] is False
    assert blocked["reason"] == "conversation_limit"
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    stale = _decide(
        _tweet(
            "7201",
            "@MoodyBotAI I tried that after a layoff and the hard part was asking my brother for rent.",
            parent="7200",
            parent_author=BOT,
        ),
        conversation={"last_interaction_at": old, "bot_replies_24h": 0},
    )
    assert stale["respond"] is False
    assert stale["reason"] == "stale"
    fresh_request = _decide(
        _tweet("7202", "@MoodyBotAI what should I do now"),
        conversation={"last_interaction_at": old, "bot_replies_24h": 0},
    )
    assert fresh_request["respond"] is True


def test_crisis_uses_the_safety_hold():
    decision = _decide(_tweet("7300", "@MoodyBotAI I want to die"))
    assert decision["classification"] == UNSAFE
    assert decision["respond"] is False
    assert decision["objective"] == "safety_hold"
    assert decision["action"] == "skip"
    assert "crisis" in decision["safety_flags"]
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_BOT_USER_ID"] = BOT
    drafted = []
    import x_integration.reply as reply_mod

    original = reply_mod.draft_mention_reply
    reply_mod.draft_mention_reply = lambda *args, **kwargs: drafted.append("draft")
    try:
        with TemporaryDirectory() as tmp:
            book = MentionLedger(Path(tmp) / "mentions.sqlite")
            outcome = process_mention(
                Mention("crisis:7300", "7300", "9", "@MoodyBotAI I want to die", "7300"),
                ledger=book,
            )
            assert outcome["reason"] == "safety_hold"
            assert drafted == []
    finally:
        reply_mod.draft_mention_reply = original
        _clear()


def test_ambiguous_text_uses_the_model_and_failure_stays_quiet():
    tweet = _tweet("7400", "@MoodyBotAI the blue door thing")

    def complete(_messages):
        return json.dumps({
            "classification": "CHALLENGE",
            "confidence": 0.91,
            "reason": "disputes the claim",
            "objective": "answer_substance",
        })

    decided = _decide(tweet, complete=complete)
    assert decided["classification"] == CHALLENGE
    assert decided["respond"] is True
    assert decided["model"] == "model"

    def broken(_messages):
        raise RuntimeError("down")

    quiet = _decide(tweet, complete=broken)
    assert quiet["respond"] is False
    assert quiet["reason"] == "model_unavailable"


def test_shadow_observe_does_not_publish_or_move_the_cursor():
    os.environ["X_BOT_USER_ID"] = BOT
    os.environ["X_USER_ACCESS_TOKEN"] = "test-user-token"
    os.environ["X_REPLIES_ENABLED"] = "false"
    os.environ["X_OPERATING_MODE"] = "disabled"
    posts = []
    import x_integration.publish_once as once
    import x_integration.reply as reply_mod

    original_send = once.send_reply
    original_draft = reply_mod.draft_mention_reply
    def _no_post(*args, **kwargs):
        posts.append("post")
        return {"status": "posted"}

    def _draft(*args, **kwargs):
        posts.append("draft")
        return "No post."

    once.send_reply = _no_post
    reply_mod.draft_mention_reply = _draft
    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentions.sqlite"
            book = MentionLedger(path)
            assert book.claim_publication(OLD_FAILED, "old") == "claimed"
            book.finish_publication(OLD_FAILED, status="failed", http_status=403, detail="Forbidden")
            before = book.publication(OLD_FAILED)
            book.claim("poll:" + MATT, MATT, "2082957781293035520", MATT)
            book.finish("poll:" + MATT, status="dry_run", post_id=MATT)
            book.set_since_id(ACTIVATION_POST_ID)
            os.environ["X_ONE_REPLY_GATE"] = "true"
            assert book.claim_activation_attempt(MATT) == "claimed"
            book.finish_activation("posted")
            os.environ["X_ONE_REPLY_GATE"] = "false"

            def fetch(user_id, token, since_id, pagination):
                return FetchResult(
                    status="ok",
                    tweets=[
                        _tweet("10", "@MoodyBotAI what should I do"),
                        _tweet(
                            BUILD,
                            BUILD_TEXT,
                            username="buildwithpb",
                            parent=ROOT,
                            parent_author=BOT,
                            conversation=ROOT,
                        ),
                        _tweet(MATT, MATT_TEXT, author="2082957781293035520", username="MattCanham805"),
                        _tweet(FRESH, "@MoodyBotAI what should I do about the job"),
                    ],
                )

            result = observe_once(ledger=book, fetch=fetch)
            assert result["published"] == 0
            assert result["since_id"] == ACTIVATION_POST_ID
            assert book.get_since_id() == ACTIVATION_POST_ID
            queued = {item["post_id"] for item in result["queued"]}
            assert FRESH in queued
            assert BUILD not in queued
            assert MATT not in queued
            build = book.engagement_decision(BUILD)
            assert build["classification"] == CONTRIBUTION
            assert build["respond"] is False
            matt = book.engagement_decision(MATT)
            assert matt["classification"] == DIRECT_REQUEST
            assert matt["reason"] == "duplicate_parent"
            fresh = book.engagement_decision(FRESH)
            assert fresh["respond"] is True
            assert book.engagement_decision("10") is None
            summary = book.engagement_summary()
            assert summary["would_reply"] == 1
            assert summary["duplicates"] == 1
            assert posts == []
            outcome = process_mention(
                Mention("poll:" + FRESH, FRESH, "2081454353987297280", "@MoodyBotAI what now", FRESH),
                ledger=book,
            )
            assert outcome["status"] == "dry_run"
            assert posts == ["draft"]
            assert book.publication(OLD_FAILED) == before
            gate = MentionLedger(path).activation_status()
            assert gate["mode"] == "stopped"
            assert gate["remaining"] == 0
            assert gate["stop_reason"] == "posted"
            assert book.claim_activation_attempt("999") == "inactive"
            os.environ["X_ONE_REPLY_GATE"] = "true"
            assert book.claim_activation_attempt("999") == "exhausted"
            assert book.activation_status()["remaining"] == 0
            stored = book.conversation_activity(10)
            assert all(row["post_id"] != OLD_FAILED for row in stored)
            assert BUILD in {row["post_id"] for row in stored}
    finally:
        once.send_reply = original_send
        reply_mod.draft_mention_reply = original_draft
        _clear()


def test_conversation_cap_is_atomic_with_the_daily_cap():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "mentions.sqlite"
        book = MentionLedger(path)
        for number in range(2):
            post_id = str(8000 + number)
            assert book.reserve_automatic_publication(post_id, "reply", "thread-1") == "claimed"
            book.finish_publication(post_id, status="posted", x_reply_id=f"r{number}", http_status=201)
        results = []

        def worker(post_id):
            worker_book = MentionLedger(path)
            results.append(
                worker_book.reserve_automatic_publication(post_id, "next", "thread-1")
            )

        threads = [threading.Thread(target=worker, args=(str(8100 + number),)) for number in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(results) == ["claimed", "conversation_cap"]
        assert book.reserve_automatic_publication("8200", "other", "thread-2") == "claimed"
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "mentions.sqlite"
        book = MentionLedger(path)
        for number in range(5):
            post_id = str(8300 + number)
            assert book.reserve_automatic_publication(post_id, "daily", f"c{number}") == "claimed"
            book.finish_publication(
                post_id, status="posted", x_reply_id=f"d{number}", http_status=201
            )
        assert book.reserve_automatic_publication("8400", "over", "fresh") == "cap"
        assert book.automatic_reply_allowance()["remaining"] == 0


if __name__ == "__main__":
    test_real_contribution_is_observed()
    test_direct_question_is_eligible()
    test_challenge_and_evidence_request_are_eligible()
    test_meaningful_contribution_can_reply_and_generic_does_not()
    test_empty_spam_own_and_answered_posts_are_skipped()
    test_request_without_a_question_mark_is_eligible()
    test_follow_up_keeps_context()
    test_grok_style_thread_keeps_each_intent()
    test_missing_context_does_not_speculate()
    test_conversation_limit_and_stale_contribution()
    test_crisis_uses_the_safety_hold()
    test_ambiguous_text_uses_the_model_and_failure_stays_quiet()
    test_shadow_observe_does_not_publish_or_move_the_cursor()
    test_conversation_cap_is_atomic_with_the_daily_cap()
    print("ok")
