# -*- coding: utf-8 -*-
"""Tests for conversation anchors, epistemic cultural claims, and surface render."""

import re

from conversation_anchors import (
    callback_echoes_anchor,
    evolve_anchor_callback,
    extract_conversation_anchors,
)
from response_finalization import (
    build_response_plan,
    finalize_response,
    generate_recognition_callback,
    run_epistemic_check,
)
from surface_render import final_surface_render


def test_extract_stretch_anchor():
    anchors = extract_conversation_anchors("What got stretched out for you?")
    assert any("stretch" in a for a in anchors.all_anchors)
    cb = evolve_anchor_callback(anchors)
    assert cb and "stretch" in cb.lower()
    assert "familiar" not in cb.lower()


def test_extract_carrying_anchor():
    anchors = extract_conversation_anchors("I feel like I'm carrying this.")
    cb = evolve_anchor_callback(anchors)
    assert cb and "carrying" in cb.lower()


def test_extract_cracked_anchor():
    anchors = extract_conversation_anchors("This cracked something.")
    cb = evolve_anchor_callback(anchors)
    assert cb and "crack" in cb.lower()


def test_extract_script_anchor():
    anchors = extract_conversation_anchors("The script changed.")
    cb = evolve_anchor_callback(anchors)
    assert cb and "script" in cb.lower()


def test_dirty_talk_callback_uses_user_anchors():
    user = (
        "How has dirty talk changed between 1995 and 2026, "
        "and did pornography influence the language? What got stretched out for you?"
    )
    draft = (
        "The shift is real. The language changed because the consumption changed. "
        "The average person's sexual vocabulary has been trained by thousands of hours of porn. "
        "The camera needs degradation now.\n\n"
        "What part of that shift felt most familiar or alien to you?"
    )
    result = finalize_response(draft, user, selected_command="/thoughts")
    lower = result.text.lower()
    closer = result.text.strip().split("\n\n")[-1].lower()
    closer_q = closer.replace("🥃", "").strip()
    assert "say the word" not in lower
    assert "thousands of hours" not in lower
    assert "the average person" not in lower
    assert "the language changed because the consumption changed" not in lower
    assert result.plan.closing_strategy == "recognition_callback"
    assert closer_q.endswith("?")
    # Rhetorical: must preserve signature language (stretch), not topical synonyms
    assert "stretch" in closer
    assert "what changed in your sense" not in closer
    assert "familiar or alien" not in closer


def test_generic_reflective_closer_fails_anchor_check():
    user = "What got stretched out for you around dirty talk?"
    plan = build_response_plan(user)
    anchors = extract_conversation_anchors(user)
    generic = "What part of that shift felt most familiar or alien to you?"
    assert callback_echoes_anchor(generic, anchors) is False
    cb = generate_recognition_callback(user, plan, anchors=anchors)
    assert "stretch" in cb.lower()
    assert "what changed" not in cb.lower()


def test_broad_cultural_and_quantitative_rewrite():
    plan = build_response_plan("Did porn change dirty talk?")
    text, changed = run_epistemic_check(
        "The language changed because the consumption changed. "
        "The average person's sexual vocabulary has been trained by thousands of hours. "
        "People now expect the camera needs degradation.",
        plan,
    )
    assert changed
    lower = text.lower()
    assert "thousands of hours" not in lower
    assert "the average person" not in lower
    assert "the language changed because the consumption changed" not in lower


def test_technical_still_no_emotional_callback():
    user = "Why does this Telegram worker keep dying?"
    draft = "Duplicate getUpdates.\n\nWhat stretched in you while reading that?"
    result = finalize_response(draft, user)
    assert "stretched" not in result.text.lower() or "worker" in result.text.lower()
    # Prefer: emotional callback removed
    assert "stretched in you" not in result.text.lower()


def test_surface_render_space_before_punctuation():
    text, changed = final_surface_render("neutral .\n\nand anything gentler")
    assert changed
    assert "neutral ." not in text
    assert "neutral." in text
    assert re.search(r"\n\nAnd ", text) or "And anything" in text


def test_surface_render_double_spaces_and_paragraphs():
    text, _ = final_surface_render("One line.\n\n\n\nTwo   line .")
    assert "\n\n\n" not in text
    assert "  " not in text
    assert "line." in text


def test_surface_render_emoji_and_quotes():
    text, _ = final_surface_render('He said "hello"')
    assert '"' in text
    assert text.count("🥃") == 1
    assert text.endswith("🥃")


def test_finalize_ends_with_surface_quality():
    user = "The script changed."
    draft = "Insight  here .\n\n\nWhat part of that shift felt familiar?"
    result = finalize_response(draft, user)
    assert " ." not in result.text
    assert "\n\n\n" not in result.text
    assert "script" in result.text.lower().split("\n\n")[-1]


def test_no_hedge_soup_introduced():
    plan = build_response_plan("culture shift?")
    text, _ = run_epistemic_check("Perhaps porn changed everything.", plan)
    assert "perhaps" not in text.lower()
    assert "one might argue" not in text.lower()


if __name__ == "__main__":
    test_extract_stretch_anchor()
    test_extract_carrying_anchor()
    test_extract_cracked_anchor()
    test_extract_script_anchor()
    test_dirty_talk_callback_uses_user_anchors()
    test_generic_reflective_closer_fails_anchor_check()
    test_broad_cultural_and_quantitative_rewrite()
    test_technical_still_no_emotional_callback()
    test_surface_render_space_before_punctuation()
    test_surface_render_double_spaces_and_paragraphs()
    test_surface_render_emoji_and_quotes()
    test_finalize_ends_with_surface_quality()
    test_no_hedge_soup_introduced()
    print("All surface/anchor tests passed.")
