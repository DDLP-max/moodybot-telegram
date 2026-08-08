# -*- coding: utf-8 -*-
"""Tests for recognition callback closing strategy."""

from pathlib import Path

from recognition_callbacks import (
    closer_instruction,
    diagnose_closing,
    is_generic_followup,
    select_closing_strategy,
    validate_recognition_callback,
)


ENGINE = Path("moodybot-system-prompt/9_response-engine")


def test_recognition_callbacks_module_exists():
    path = ENGINE / "recognition-callbacks.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Recognition Landing" in text or "Recognition Landings" in text
    assert "Question Is the Exception" in text or "exception" in text.lower()
    assert "stretched" in text.lower()
    assert "seen it named" not in text.lower() or "Bad question" in text


def test_cultural_analysis_prefers_recognition_callback():
    from recognition_landing import select_landing

    decision = select_landing(
        "How has dirty talk changed between 1995 and 2026, "
        "and did pornography influence that?"
    )
    # Cultural criticism should land as statement/silence, not forced quiz
    assert decision.landing in {
        "RECOGNITION_STATEMENT",
        "SILENCE",
        "RECOGNITION_OBSERVATION",
    }


def test_practical_action_prefers_action_line():
    strategy = select_closing_strategy(
        user_message="What should I do about the doorman sending flowers?",
        practical_request=True,
    )
    assert strategy == "ACTION_LINE"


def test_grief_prefers_silence():
    strategy = select_closing_strategy(
        user_message="My brother died last week and I can't stop crying.",
        grief_or_trauma=True,
    )
    assert strategy == "SILENCE"


def test_technical_without_reframe_prefers_none():
    strategy = select_closing_strategy(
        user_message="Where does session state live in this architecture?",
        technical_only=True,
        created_reframe=False,
    )
    assert strategy == "NONE"


def test_relationship_pattern_can_use_callback():
    from recognition_landing import select_landing

    decision = select_landing(
        "Why does this relationship keep repeating the same pattern?"
    )
    assert decision.landing in {
        "RECOGNITION_STATEMENT",
        "SILENCE",
        "RECOGNITION_OBSERVATION",
        "RECOGNITION_CALLBACK",
    }


def test_generic_followups_are_detected():
    bad = [
        "So yeah.\n\nWhat are you actually asking about here?",
        "Does that make sense?",
        "Would you like me to explain more?",
        "Do you want to explore that further?",
        "Which aspect are you interested in?",
    ]
    for text in bad:
        assert is_generic_followup(text), text


def test_recognition_callback_quality_gate():
    good = "So what stretched in you while you were reading that cultural shift?"
    result = validate_recognition_callback(good, subject_tokens=["cultural", "shift"])
    assert result["is_question"]
    assert result["not_generic"]
    assert result["has_subject_callback"]
    assert result["brief"]

    bad = "Would you like to explore another topic?"
    bad_result = validate_recognition_callback(bad, subject_tokens=["cultural"])
    assert bad_result["not_generic"] is False


def test_clarification_is_not_forced_as_recognition_callback():
    strategy = select_closing_strategy(
        user_message="Should I take it?",
        missing_required_info=True,
    )
    assert strategy == "NONE"


def test_response_docs_include_generic_followup_check():
    text = (ENGINE / "response-generation-order.md").read_text(encoding="utf-8")
    assert "Generic Follow-Up Check" in text
    assert "Recognition Callback Check" in text


def test_diagnose_closing_telemetry_shape():
    diag = diagnose_closing(
        "How did dating culture change?",
        "Insight here.\n\nSo what shifted once the pattern was visible?",
        created_reframe=True,
    )
    assert "closing_strategy" in diag
    assert diag["generic_followup_detected"] in {"true", "false"}


def test_closer_instructions_exist_for_all_strategies():
    for strategy in (
        "RECOGNITION_CALLBACK",
        "RITUAL_LINE",
        "ACTION_LINE",
        "SILENCE",
        "NONE",
    ):
        text = closer_instruction(strategy)
        assert strategy in text or strategy.split("_")[0] in text
        assert "generic" in text.lower() or "follow-up" in text.lower() or "question" in text.lower()


def test_default_without_insight_signals_is_none():
    strategy = select_closing_strategy(
        user_message="thanks",
        created_reframe=False,
    )
    assert strategy == "NONE"


if __name__ == "__main__":
    test_recognition_callbacks_module_exists()
    test_cultural_analysis_prefers_recognition_callback()
    test_practical_action_prefers_action_line()
    test_grief_prefers_silence()
    test_technical_without_reframe_prefers_none()
    test_relationship_pattern_can_use_callback()
    test_generic_followups_are_detected()
    test_recognition_callback_quality_gate()
    test_clarification_is_not_forced_as_recognition_callback()
    test_response_docs_include_generic_followup_check()
    test_diagnose_closing_telemetry_shape()
    test_closer_instructions_exist_for_all_strategies()
    test_default_without_insight_signals_is_none()
    print("All recognition callback tests passed.")
