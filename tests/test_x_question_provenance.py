# -*- coding: utf-8 -*-
"""Question provenance for a Grok invitation. The harness does not post."""
from __future__ import annotations

from x_integration.battle import GROK_USER_ID, evaluate_fixture, walk_reply_chain
from x_integration.engagement import authoritative_decision

BOT = "1912252811469025282"
HUMAN = "2082957781293035520"
QUESTION = "What is the capital of France?"
GROK_ANSWER = "Lyon is the capital of France."


def _chain():
    question = {
        "id": "7001",
        "author_id": HUMAN,
        "author_username": "matt",
        "text": QUESTION,
        "conversation_id": "7001",
    }
    answer = {
        "id": "7002",
        "author_id": GROK_USER_ID,
        "author_username": "grok",
        "text": GROK_ANSWER,
        "parent_id": "7001",
        "conversation_id": "7001",
    }
    invitation = {
        "id": "7003",
        "author_id": GROK_USER_ID,
        "author_username": "grok",
        "text": "@MoodyBotAI, your turn.",
        "parent_id": "7002",
        "conversation_id": "7001",
    }
    return question, answer, invitation


def _decide(posts, **extra):
    invitation = dict(posts[-1])
    invitation.update(extra)
    return authoritative_decision(
        invitation,
        user_id=BOT,
        floor="0",
        already_replied=False,
        context={"posts": posts[:-1]},
        conversation=extra.get("conversation"),
    )


def test_grok_invitation_recovers_the_human_question_not_the_answer():
    question, answer, invitation = _chain()
    seen = []

    def complete(messages):
        user = " ".join(
            str(item.get("content") or "")
            for item in messages
            if item.get("role") == "user"
        )
        seen.append(user)
        return "Paris is the capital of France."

    result = evaluate_fixture(
        {"posts": [question, answer, invitation]},
        user_id=BOT,
        complete=complete,
    )
    assert result["publish"] is True
    assert result["question_id"] == "7001"
    assert result["question_text"] == QUESTION
    assert result["question_author_id"] == HUMAN
    assert result["question_conversation_id"] == "7001"
    assert result["reply_parent_id"] == "7003"
    assert result["question_origin"] == "earlier"
    assert seen
    assert "Lyon" not in seen[-1]
    assert "capital of France" in seen[-1]
    assert "Paris" in result["reply"]


def test_intermediate_replies_do_not_hide_the_question():
    question, _answer, invitation = _chain()
    posts = [
        question,
        {"id": "7011", "author_id": HUMAN, "author_username": "matt",
         "text": "Still thinking about it.", "parent_id": "7001", "conversation_id": "7001"},
        {"id": "7012", "author_id": "303", "author_username": "ada",
         "text": "Same here.", "parent_id": "7011", "conversation_id": "7001"},
        {"id": "7002", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": GROK_ANSWER, "parent_id": "7012", "conversation_id": "7001"},
        invitation,
    ]
    decision = _decide(posts)
    assert decision["question_sufficient"] is True
    assert decision["original_question_id"] == "7001"
    assert decision["question_text"] == QUESTION
    assert decision["reply_parent_id"] == "7003"


def test_question_in_the_invitation_is_used_directly():
    decision = _decide([
        {"id": "7101", "author_id": HUMAN, "text": "Unrelated earlier post."},
        {"id": "7102", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "@MoodyBotAI, your turn. What is the capital of France?",
         "conversation_id": "7102"},
    ])
    assert decision["publish"] is True
    assert decision["original_question_id"] == "7102"
    assert decision["question_origin"] == "current"
    assert "capital of France" in decision["question_text"]
    assert decision["reply_parent_id"] == "7102"


def test_missing_deleted_and_protected_parents_fail_closed():
    missing = _decide([
        {"id": "7201", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "@MoodyBotAI, your turn.", "parent_id": "7299", "conversation_id": "7201"},
    ])
    assert missing["publish"] is False
    assert missing["reason"] == "missing_parent"

    def fetch(tweet_id):
        status = {"7302": "deleted", "7303": "protected"}[tweet_id]
        return {"id": tweet_id, "status": status}

    deleted = _decide([
        {"id": "7301", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "@MoodyBotAI, your turn.", "parent_id": "7302", "conversation_id": "7301"},
    ], fetch_post=fetch)
    protected = _decide([
        {"id": "7311", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "@MoodyBotAI, your turn.", "parent_id": "7303", "conversation_id": "7311"},
    ], fetch_post=fetch)
    assert deleted["reason"] == "deleted_parent"
    assert deleted["publish"] is False
    assert protected["reason"] == "protected_parent"
    assert protected["publish"] is False


def test_long_human_question_uses_the_complete_note():
    note = "What is the tallest mountain on Earth? " + ("range " * 40)
    decision = _decide([
        {"id": "7401", "author_id": HUMAN, "author_username": "matt",
         "text": "1/", "note_tweet": {"text": note}, "conversation_id": "7401"},
        {"id": "7402", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "@MoodyBotAI, your turn.", "parent_id": "7401", "conversation_id": "7401"},
    ])
    assert decision["original_question_id"] == "7401"
    assert "tallest mountain" in decision["question_text"]
    assert decision["question_text"] != "1/"
    assert decision["publish"] is True


def test_distractors_are_not_the_human_question():
    decision = _decide([
        {"id": "7501", "author_id": HUMAN, "author_username": "matt",
         "text": QUESTION, "conversation_id": "7501"},
        {"id": "7502", "author_id": HUMAN, "author_username": "ada",
         "text": "What a night?", "parent_id": "7501", "conversation_id": "7501"},
        {"id": "7503", "author_id": HUMAN, "author_username": "bea",
         "text": 'He asked "What is the capital of Spain?" and left.',
         "parent_id": "7502", "conversation_id": "7501"},
        {"id": "7504", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "Is Lyon the capital of France?",
         "parent_id": "7503", "conversation_id": "7501"},
        {"id": "7505", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "@MoodyBotAI, your turn.",
         "parent_id": "7504", "conversation_id": "7501"},
    ])
    assert decision["original_question_id"] == "7501"
    assert decision["question_text"] == QUESTION
    assert "Spain" not in decision["question_text"]
    assert "Lyon" not in decision["question_text"]


def test_a_mention_without_an_invitation_is_not_a_request():
    decision = _decide([
        {"id": "7601", "author_id": HUMAN, "text": QUESTION, "conversation_id": "7601"},
        {"id": "7602", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "I like @MoodyBotAI.", "parent_id": "7601", "conversation_id": "7601"},
    ])
    assert decision["classification"] != "DIRECT_CHALLENGE"
    assert decision["publish"] is False


def test_repeated_invitation_and_ai_loop_do_not_answer_again():
    question, answer, invitation = _chain()
    repeated = _decide(
        [question, answer, {**invitation, "id": "7702"}],
        conversation={"ai_invitation_used": True, "answered_question_ids": ["7001"]},
    )
    assert repeated["publish"] is False
    assert repeated["reason"] == "repeated_question"
    other = {
        "id": "7703",
        "author_id": GROK_USER_ID,
        "author_username": "grok",
        "text": "@MoodyBotAI, your turn.",
        "parent_id": "7704",
        "conversation_id": "7001",
    }
    loop = _decide(
        [
            {"id": "7705", "author_id": HUMAN, "text": "What is the capital of Spain?",
             "conversation_id": "7001"},
            {"id": "7704", "author_id": GROK_USER_ID, "author_username": "grok",
             "text": "Madrid.", "parent_id": "7705", "conversation_id": "7001"},
            other,
        ],
        conversation={"ai_invitation_used": True, "answered_question_ids": ["7001"]},
    )
    assert loop["publish"] is False
    assert loop["reason"] == "ai_loop"


def test_cycle_depth_and_lookup_budget_stop():
    cycle = _decide([
        {"id": "7801", "author_id": HUMAN, "text": "ok", "parent_id": "7802"},
        {"id": "7802", "author_id": HUMAN, "text": "ok", "parent_id": "7801"},
        {"id": "7803", "author_id": GROK_USER_ID, "author_username": "grok",
         "text": "@MoodyBotAI, your turn.", "parent_id": "7802"},
    ])
    assert cycle["reason"] == "cycle"
    assert cycle["publish"] is False
    posts = []
    parent = "7907"
    for number in range(1, 7):
        posts.append({
            "id": f"790{number}",
            "author_id": HUMAN,
            "text": "ok",
            "parent_id": f"790{number + 1}",
        })
    posts.append({
        "id": "7907",
        "author_id": HUMAN,
        "text": QUESTION,
    })
    posts.append({
        "id": "7908",
        "author_id": GROK_USER_ID,
        "author_username": "grok",
        "text": "@MoodyBotAI, your turn.",
        "parent_id": "7901",
    })
    depth = _decide(posts)
    assert depth["reason"] == "depth_limit"
    assert depth["publish"] is False
    assert parent == "7907"

    def fetch(tweet_id):
        number = int(tweet_id)
        return {"id": tweet_id, "author_id": HUMAN, "text": "ok", "parent_id": str(number + 1)}

    walked = walk_reply_chain(
        {"id": "8000", "parent_id": "8001"},
        {},
        fetch,
        max_lookups=4,
    )
    assert walked["stop"] == "lookup_budget"
    assert walked["lookups"] == 4


if __name__ == "__main__":
    test_grok_invitation_recovers_the_human_question_not_the_answer()
    test_intermediate_replies_do_not_hide_the_question()
    test_question_in_the_invitation_is_used_directly()
    test_missing_deleted_and_protected_parents_fail_closed()
    test_long_human_question_uses_the_complete_note()
    test_distractors_are_not_the_human_question()
    test_a_mention_without_an_invitation_is_not_a_request()
    test_repeated_invitation_and_ai_loop_do_not_answer_again()
    test_cycle_depth_and_lookup_budget_stop()
    print("question provenance ok")
