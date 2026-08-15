# -*- coding: utf-8 -*-
"""Regression: comic premise / never-cure-the-premise gate.

Matt fixture (2026-08-15):
  Input: Only 3 more years of bulking and cutting and I can begin phase one
         of looking women in the eyes
  Fail:  The body isn't the gatekeeper. The story is.
  Why:   general → Emotional State Recognition + SNAP cured the bit.
"""
from __future__ import annotations

from capability_detection import (
    detect_comic_premise,
    looks_like_premise_cure,
)
from response_finalization import (
    build_response_plan,
    classify_claim_domain,
    plan_closer_instruction,
)


MATT = (
    "Only 3 more years of bulking and cutting and I can begin phase one "
    "of looking women in the eyes"
)

BAD_CURE = "The body isn't the gatekeeper. The story is."
GOOD_TAG = "Don't rush it. Eye contact is an advanced compound movement."
GOOD_TAG_2 = (
    "Phase two is saying hello without checking your body-fat percentage first."
)


def test_matt_classified_general_not_emotional():
    """Historical miss was not EI-domain — it was general→Emotional State Recognition."""
    assert classify_claim_domain(MATT) == "general"


def test_matt_comic_premise_detected():
    comic = detect_comic_premise(MATT)
    assert comic.active
    assert comic.confidence >= 0.55
    assert comic.never_cure
    assert "fitness_to_social_absurdism" in comic.signals or (
        "optimization_frame" in comic.signals and "basic_social_unlock" in comic.signals
    )


def test_matt_routes_away_from_emotional_state_recognition():
    plan = build_response_plan(MATT, channel="telegram", mode="dynamic")
    assert plan.comic_premise is True
    assert plan.never_cure_premise is True
    assert plan.primary_capability != "Emotional State Recognition"
    assert plan.primary_capability == "Humor As Disruption"
    assert plan.supporting_capability == "Bit Continuation"
    assert plan.mechanism_hint == "comic_premise_continuation"


def test_never_cure_guidance_injected():
    plan = build_response_plan(MATT)
    instr = plan_closer_instruction(plan)
    assert "NEVER CURE THE PREMISE" in instr
    assert "gatekeeper" in instr.lower()  # documents the FAIL example


def test_known_cure_detected_as_failure_mode():
    assert looks_like_premise_cure(BAD_CURE) is True
    assert looks_like_premise_cure(GOOD_TAG) is False
    assert looks_like_premise_cure(GOOD_TAG_2) is False


def test_genuine_anxiety_not_comic_bit():
    sincere = (
        "I've been struggling with anxiety for three years and still can't "
        "look people in the eyes."
    )
    comic = detect_comic_premise(sincere)
    assert comic.active is False
    plan = build_response_plan(sincere)
    assert plan.comic_premise is False


def test_fiber_still_not_comic():
    comic = detect_comic_premise("How do I replace a fiber connector?")
    assert comic.active is False


if __name__ == "__main__":
    test_matt_classified_general_not_emotional()
    print("ok domain")
    test_matt_comic_premise_detected()
    print("ok detect")
    test_matt_routes_away_from_emotional_state_recognition()
    print("ok route")
    test_never_cure_guidance_injected()
    print("ok guidance")
    test_known_cure_detected_as_failure_mode()
    print("ok cure detector")
    test_genuine_anxiety_not_comic_bit()
    print("ok negative anxiety")
    test_fiber_still_not_comic()
    print("ok")
