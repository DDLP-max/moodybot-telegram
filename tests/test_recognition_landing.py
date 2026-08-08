# -*- coding: utf-8 -*-
"""Recognition landing tests — endings that land, not module proofs."""

from recognition_landing import (
    LANDING_ENGINE_VERSION,
    apply_landing,
    craft_callback_question,
    is_grammatical_english,
    select_landing,
    validate_landing,
    would_keep_if_nobody_could_reply,
)
from response_finalization import build_response_plan, finalize_response
from signature_language import extract_signature_language


def test_broken_topic_staple_fails_grammar():
    bad = "What about feminists hate woman looks different now that you've seen it named?"
    ok, reason = validate_landing(bad)
    assert ok is False
    assert reason.startswith("REJECTED")
    assert is_grammatical_english(bad) is False
    assert would_keep_if_nobody_could_reply(bad) is False


def test_malformed_landing_family_rejected():
    cases = [
        "What about X looks different now that you've seen it named?",
        "What about Y hate Z looks different?",
        "Something ended. Now that you've seen it named?",
        "What about feminists hate woman looks different now that you've seen it named?",
    ]
    for c in cases:
        ok, reason = validate_landing(c)
        assert ok is False, c
        assert "REJECTED" in reason


def test_landing_engine_version():
    assert LANDING_ENGINE_VERSION == "recognition-landing-v1"


def test_politics_prefers_statement_not_question():
    user = "Why do feminists hate women praising men?"
    draft = (
        "The accusation stops being analysis the moment disagreement becomes evidence.\n\n"
        "What about feminists hate woman looks different now that you've seen it named?"
    )
    result = finalize_response(draft, user)
    closer = result.text.strip().split("\n\n")[-1].replace("🥃", "").strip()
    assert "what about feminists" not in closer.lower()
    assert "seen it named" not in closer.lower()
    assert not closer.endswith("?") or "stretch" in closer.lower()
    # Prefer a statement landing
    assert result.plan.landing in {
        "recognition_statement",
        "silence",
        "recognition_observation",
    }


def test_stretch_still_allows_rhetorical_question():
    user = "What got stretched out for you?"
    assert select_landing(user).landing == "RECOGNITION_CALLBACK"
    q = craft_callback_question(user)
    assert q and "stretch" in q.lower()
    assert is_grammatical_english(q)


def test_topic_nouns_are_not_signature():
    sig = extract_signature_language("Why do feminists hate women praising men?")
    assert not sig.protected
    assert craft_callback_question(
        "Why do feminists hate women praising men?"
    ) is None


def test_relationship_not_forced_question():
    user = "My partner cancels plans and only calls late. What's going on?"
    draft = "They are treating you as low priority. Convenience over commitment.\n\nWhat about partner cancels looks different now that you've seen it named?"
    result = finalize_response(draft, user)
    closer = result.text.strip().split("\n\n")[-1].replace("🥃", "").strip()
    assert "seen it named" not in closer.lower()
    assert result.plan.landing != "recognition_callback" or "stretch" in closer.lower()


def test_technical_silence():
    user = "Why does this Telegram worker keep dying?"
    assert select_landing(user, technical=True).landing == "SILENCE"
    draft = "Duplicate getUpdates.\n\nWhat stretched in you while reading that?"
    result = finalize_response(draft, user)
    assert "stretched in you" not in result.text.lower()


def test_grief_silence():
    user = "My brother died last week and I can't stop crying."
    assert select_landing(user, grief=True).landing == "SILENCE"


def test_practical_action():
    user = "What should I do about the doorman sending flowers?"
    assert select_landing(user, practical=True).landing == "ACTION"


def test_apply_landing_strips_broken_closer():
    text = (
        "Healthy ideas don't require loyalty tests.\n\n"
        "What about feminists hate woman looks different now that you've seen it named?"
    )
    decision = select_landing("Why do feminists hate women praising men?", body=text)
    out, modified = apply_landing(text, "Why do feminists hate women praising men?", decision)
    assert "seen it named" not in out.lower()
    assert modified


def test_build_plan_landing_field():
    plan = build_response_plan("Why do feminists hate women praising men?")
    assert plan.landing in {
        "recognition_statement",
        "silence",
        "recognition_observation",
    }
    assert plan.allow_question is False


if __name__ == "__main__":
    test_broken_topic_staple_fails_grammar()
    test_malformed_landing_family_rejected()
    test_landing_engine_version()
    test_politics_prefers_statement_not_question()
    test_stretch_still_allows_rhetorical_question()
    test_topic_nouns_are_not_signature()
    test_relationship_not_forced_question()
    test_technical_silence()
    test_grief_silence()
    test_practical_action()
    test_apply_landing_strips_broken_closer()
    test_build_plan_landing_field()
    print("All recognition landing tests passed.")
