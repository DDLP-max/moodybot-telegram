# -*- coding: utf-8 -*-
"""Runtime finalization regressions for epistemic + recognition callbacks."""

from pathlib import Path
import json
import re

from response_finalization import (
    build_response_plan,
    detect_generic_cta,
    finalize_response,
    generate_recognition_callback,
    run_epistemic_check,
    strip_generic_cta,
)


PROMPT = Path("system_prompt.txt")
META = Path("prompt_meta.json")


def test_prompt_contains_critical_modules():
    text = PROMPT.read_text(encoding="utf-8")
    for needle in (
        "Final Quality Gates",
        "Recognition Callbacks",
        "Epistemic Calibration",
        "Generic Follow-Up Check",
        "Engagement is last",
    ):
        assert needle in text or needle.lower() in text.lower(), needle


def test_prompt_meta_critical_order():
    assert META.exists(), "Run build_system_prompt.py first"
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert meta["section_count"] > 100
    positions = meta["critical_module_positions"]
    for key in (
        "epistemic-calibration",
        "recognition-callbacks",
        "final-quality-gates",
    ):
        assert positions[key] != "MISSING", key
        # Must be late in the prompt
        cur, total = positions[key].split("/")
        assert int(cur) / int(total) > 0.7, positions[key]
    # final-quality-gates should be the last or near-last critical
    assert "final-quality-gates" in meta["final_20_sections"][-1] or any(
        "final-quality-gates" in s for s in meta["final_20_sections"]
    )


def test_no_mandatory_cta_rule_in_assembled_prompt():
    text = PROMPT.read_text(encoding="utf-8")
    # Old contradiction should not survive as an active requirement in length tiers
    assert "one quotable**, **one CTA**, **one shift" not in text
    assert "CTA is NOT mandatory" in text or "CTA is **not** required" in text


def test_dirty_talk_regression_strips_generic_cta_and_calibrates():
    user = (
        "How has dirty talk changed between 1995 and 2026, "
        "and did pornography influence the language?"
    )
    draft = (
        "The shift is real. Internet porn turned dirty talk into a full script. "
        "What used to be edge is now mainstream in a lot of bedrooms.\n\n"
        "If you want examples in either style or a specific scene, say the word."
    )
    result = finalize_response(draft, user, selected_command="/thoughts")
    lower = result.text.lower()
    closer = result.text.strip().split("\n\n")[-1].lower()
    closer_q = closer.replace("🥃", "").strip()
    assert "say the word" not in lower
    assert "if you want examples" not in lower
    assert result.generic_cta_removed or not detect_generic_cta(result.text)
    assert result.text.rstrip().endswith("🥃")
    # Invented precision still blocked; interpretive body may stay bold
    assert "thousands of hours" not in lower
    # No broken topic-staple question
    assert "seen it named" not in closer
    assert "what about" not in closer
    assert " ." not in result.text
    # Landing should not force a quiz; statement/silence/action OK
    assert result.plan.landing in {
        "recognition_statement",
        "silence",
        "recognition_observation",
        "recognition_callback",
        "action",
    }


def test_doorman_prefers_action_and_calibrates_motive():
    user = (
        "A woman gave the doorman her number for lockout reasons. "
        "He later sent flowers and wine. What should she do?"
    )
    draft = (
        "He's making a move. He wanted control.\n\n"
        "Would you like me to draft a reply?"
    )
    result = finalize_response(draft, user)
    assert result.plan.closing_strategy == "action_line"
    lower = result.text.lower()
    assert "would you like" not in lower
    assert "making a move" in lower  # ordinary inference kept
    assert "he wanted control" not in lower  # consequential overreach calibrated
    assert not result.text.rstrip().endswith("?") or "should" in lower


def test_technical_no_emotional_callback():
    user = "Why does this Telegram worker keep dying on Render?"
    draft = (
        "The worker is likely crashing on an unhandled exception or duplicate getUpdates polling.\n\n"
        "What stretched in you while reading that?"
    )
    plan = build_response_plan(user)
    assert plan.landing in {"silence", "action"}
    result = finalize_response(draft, user, plan)
    assert "stretched in you" not in result.text.lower()


def test_grief_no_forced_question():
    user = "My brother died last week and I can't stop crying."
    draft = "I'm here with that weight.\n\nWant to unpack why it still hurts?"
    result = finalize_response(draft, user)
    assert result.plan.closing_strategy == "silence"
    assert "want to unpack" not in result.text.lower()
    assert not result.text.rstrip().endswith("?")


def test_clarification_allowed():
    user = "Should I send it?"
    plan = build_response_plan(user)
    assert plan.missing_required_info
    draft = "What are you thinking of sending?"
    result = finalize_response(draft, user, plan)
    assert "what are you thinking of sending" in result.text.lower()


def test_business_no_service_cta():
    user = "Competitors are running ads while we grow through referrals. What does that mean?"
    draft = (
        "Ads rent attention. Referrals compound trust.\n\n"
        "Want me to build a strategy?"
    )
    result = finalize_response(draft, user)
    assert "want me to build" not in result.text.lower()


def test_recognition_callback_is_specific():
    user = "How did dating culture change since the 90s?"
    plan = build_response_plan(user, selected_command="/thoughts")
    cb = generate_recognition_callback(user, plan, draft="The reference library exploded.")
    # No authorial signature → statement or empty, never broken topic staple
    assert "seen it named" not in (cb or "").lower()
    assert "what about" not in (cb or "").lower()
    if cb:
        assert detect_generic_cta(cb) is False
        assert len(cb.split()) <= 40


def test_epistemic_check_population_claims():
    plan = build_response_plan("Did porn change culture?")
    text, changed = run_epistemic_check(
        "The language became more performative. "
        "The average person consumed thousands of hours of porn.",
        plan,
    )
    assert changed
    assert "performative" in text.lower()
    assert "thousands of hours" not in text.lower()


def test_strip_generic_cta_patterns():
    text, removed = strip_generic_cta(
        "Insight here.\n\nIf you'd like, I can also give you examples."
    )
    assert removed
    assert "if you'd like" not in text.lower()


def test_structure_checklist_no_mandatory_cta():
    checklist = Path("moodybot-system-prompt/10_testing-quality/structure-checklist.md").read_text(
        encoding="utf-8"
    )
    lower = checklist.lower()
    assert "cta present" not in lower or "cta is not mandatory" in lower
    assert "closing beat" in lower or "closer strategy" in lower


if __name__ == "__main__":
    test_prompt_contains_critical_modules()
    test_prompt_meta_critical_order()
    test_no_mandatory_cta_rule_in_assembled_prompt()
    test_dirty_talk_regression_strips_generic_cta_and_calibrates()
    test_doorman_prefers_action_and_calibrates_motive()
    test_technical_no_emotional_callback()
    test_grief_no_forced_question()
    test_clarification_allowed()
    test_business_no_service_cta()
    test_recognition_callback_is_specific()
    test_epistemic_check_population_claims()
    test_strip_generic_cta_patterns()
    test_structure_checklist_no_mandatory_cta()
    print("All finalization tests passed.")
