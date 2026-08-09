# -*- coding: utf-8 -*-
"""Landing tests — earned endings, not mandatory mic-drops."""

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
from signature_line import body_already_lands


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
    ]
    for c in cases:
        ok, reason = validate_landing(c)
        assert ok is False, c


def test_landing_engine_version():
    assert LANDING_ENGINE_VERSION == "earned-ending-v1"


def test_politics_strips_broken_closer_and_may_stop():
    user = "Why do feminists hate women praising men?"
    draft = (
        "The accusation stops being analysis the moment disagreement becomes evidence.\n\n"
        "What about feminists hate woman looks different now that you've seen it named?"
    )
    result = finalize_response(draft, user)
    assert "seen it named" not in result.text.lower()
    assert result.plan.landing in {
        "body_ends_response",
        "signature_line",
        "silence",
    }


def test_stretch_still_allows_rhetorical_question():
    user = "What got stretched out for you?"
    assert select_landing(user).landing == "RECOGNITION_CALLBACK"
    q = craft_callback_question(user)
    assert q and "stretch" in q.lower()


def test_topic_nouns_are_not_signature():
    sig = extract_signature_language("Why do feminists hate women praising men?")
    assert not sig.protected
    assert craft_callback_question(
        "Why do feminists hate women praising men?"
    ) is None


def test_body_lands_selector():
    body = (
        "The charge works as social enforcement of loyalty. "
        "Public gratitude threatens movements built on resentment."
    )
    assert body_already_lands(body)
    assert select_landing("why?", body=body).landing == "BODY_ENDS_RESPONSE"


def test_technical_silence():
    assert select_landing("Why does worker die?", technical=True).landing == "SILENCE"


def test_grief_silence():
    assert select_landing("My brother died.", grief=True).landing == "SILENCE"


def test_practical_action():
    assert select_landing("What should I do?", practical=True).landing == "ACTION"


def test_apply_landing_strips_broken_closer():
    text = (
        "Healthy ideas don't require loyalty tests.\n\n"
        "What about feminists hate woman looks different now that you've seen it named?"
    )
    decision = select_landing("Why?", body="Healthy ideas don't require loyalty tests.")
    out, modified = apply_landing(text, "Why?", decision)
    assert "seen it named" not in out.lower()
    assert modified


def test_build_plan_landing_field():
    plan = build_response_plan("Why do feminists hate women praising men?")
    # Without body at plan time, discovery may be attempted
    assert plan.landing in {"signature_line", "body_ends_response", "silence"}
    assert plan.allow_question is False


if __name__ == "__main__":
    test_broken_topic_staple_fails_grammar()
    test_malformed_landing_family_rejected()
    test_landing_engine_version()
    test_politics_strips_broken_closer_and_may_stop()
    test_stretch_still_allows_rhetorical_question()
    test_topic_nouns_are_not_signature()
    test_body_lands_selector()
    test_technical_silence()
    test_grief_silence()
    test_practical_action()
    test_apply_landing_strips_broken_closer()
    test_build_plan_landing_field()
    print("All recognition landing tests passed.")
