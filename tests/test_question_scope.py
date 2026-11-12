# -*- coding: utf-8 -*-
"""Question extraction and answer completeness. No X posts."""
from __future__ import annotations

from question_scope import assess_answer, extract_questions, settle_reply
from x_integration.post_length import AUTONOMOUS_LIMIT, weighted_length

COMPOUND = (
    "What's the difference between intelligence and wisdom, and why do so many "
    "intelligent people make spectacularly stupid decisions?"
)
BOTH = (
    "Intelligence is a bright knife. Wisdom is knowing when to put it down. "
    "Stupid decisions happen because the shine feels like certainty."
)
ONE_SIDE = "Intelligence is a lighthouse. Wisdom is the dark around the light."
OMIT = "Intelligence collects. Wisdom edits. The difference is patience."


def _texts(result):
    return [item["text"].lower() for item in result["questions"]]


def test_one_direct_question():
    found = extract_questions("What is the capital of France?")
    assert found["count"] == 1
    assert "capital of france" in found["questions"][0]["text"].lower()
    assert found["questions"][0]["self_contained"] is True
    assert found["needs_context"] is False


def test_compound_question_keeps_both_parts():
    found = extract_questions(COMPOUND)
    assert found["count"] == 2
    texts = _texts(found)
    assert "difference between intelligence and wisdom" in texts[0]
    assert "stupid decisions" in texts[1]
    addressed = extract_questions("@MoodyBotAI " + COMPOUND, channel="x")
    assert addressed["count"] == 2
    assert "difference between intelligence and wisdom" in _texts(addressed)[0]
    assert texts[0] != texts[1]
    assert found["questions"][0]["span"][1] > found["questions"][0]["span"][0]


def test_questions_across_paragraphs():
    found = extract_questions(
        "What is wisdom?\n\nWhy do intelligent people repeat a spectacular mistake?"
    )
    assert found["count"] == 2
    assert "wisdom" in _texts(found)[0]
    assert "mistake" in _texts(found)[1]


def test_implicit_request_without_a_question_mark():
    found = extract_questions(
        "Explain the difference between intelligence and wisdom"
    )
    assert found["count"] == 1
    assert found["questions"][0]["kind"] == "implicit"
    assert "intelligence" in found["questions"][0]["text"].lower()


def test_quoted_and_third_party_questions_are_not_requests():
    quoted = extract_questions(
        '@MoodyBotAI same question. "What\'s the difference between intelligence '
        'and wisdom, and why do so many intelligent people make spectacularly '
        'stupid decisions?"',
        channel="x",
    )
    assert quoted["questions"] == []
    assert quoted["needs_context"] is True
    other = extract_questions(
        "@grok What's the difference between intelligence and wisdom, and why "
        "do so many intelligent people make spectacularly stupid decisions? "
        "@MoodyBotAI",
        channel="x",
    )
    assert other["addressed_to_moody"] is False
    assert other["questions"] == []


def test_pointer_uses_parent_and_missing_parent_does_not_invent():
    parent = [{"id": "42", "text": "What is the capital of France?"}]
    found = extract_questions(
        "@MoodyBotAI, same question. Your turn.",
        context_posts=parent,
        channel="x",
        source_post_id="99",
    )
    assert found["count"] == 1
    assert found["questions"][0]["source_post_id"] == "42"
    assert found["questions"][0]["origin"] == "earlier"
    assert found["needs_context"] is False
    missing = extract_questions(
        "@MoodyBotAI, same question. Your turn.",
        channel="x",
    )
    assert missing["questions"] == []
    assert missing["needs_context"] is True


def test_note_text_is_the_question_source():
    note = "What is the tallest mountain on Earth? " + ("range " * 40)
    found = extract_questions("1/", note_text=note, source_post_id="7")
    assert found["count"] == 1
    assert "tallest mountain" in found["questions"][0]["text"].lower()
    assert found["source_post_id"] == "7"


def test_completeness_accepts_one_metaphor_and_rejects_a_partial():
    found = extract_questions(COMPOUND)
    both = assess_answer(found, BOTH)
    assert [item["verdict"] for item in both] == ["answered", "answered"]
    one = assess_answer(found, ONE_SIDE)
    assert one[0]["verdict"] == "answered"
    assert one[1]["verdict"] != "answered"
    omitted = assess_answer(found, OMIT)
    assert omitted[1]["verdict"] != "answered"
    unknown = assess_answer(found, "I don't know.")
    assert unknown[0]["verdict"] == "cannot_answer"


def test_overlong_reply_is_labeled_partial_instead_of_cut():
    found = extract_questions(COMPOUND)
    long_answer = BOTH + " " + ("Again. " * 80)
    settled = settle_reply(
        found,
        long_answer,
        limit=AUTONOMOUS_LIMIT,
        shorten=lambda _instruction: long_answer,
    )
    assert settled["publish"] is True
    assert settled["strategy"] == "partial"
    assert settled["fits"] is True
    assert weighted_length(settled["text"]) <= AUTONOMOUS_LIMIT
    assert "ask for the rest" in settled["text"].lower()
    assert "Again." not in settled["text"]


if __name__ == "__main__":
    test_one_direct_question()
    test_compound_question_keeps_both_parts()
    test_questions_across_paragraphs()
    test_implicit_request_without_a_question_mark()
    test_quoted_and_third_party_questions_are_not_requests()
    test_pointer_uses_parent_and_missing_parent_does_not_invent()
    test_note_text_is_the_question_source()
    test_completeness_accepts_one_metaphor_and_rejects_a_partial()
    test_overlong_reply_is_labeled_partial_instead_of_cut()
    print("question scope ok")
