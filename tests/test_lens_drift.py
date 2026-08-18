# -*- coding: utf-8 -*-
"""Taste/entertainment answered as viewer psychoanalysis = lens drift (Object → Subject)."""

from discovery_craft import (
    classify_discovery_type,
    early_noun_report,
    lens_drift,
    lens_drift_diagnosis,
)
from gold_shape import evaluate_gold_shape
from response_finalization import build_response_plan, classify_claim_domain

BB_PROMPT = "no show will ever compare to breaking bad and better call saul... ever."

DRIFTED = (
    "You don't protect Breaking Bad from every other show. You protect yourself "
    "from the possibility that your best days of watching are already over."
)

GROUNDED = (
    "Breaking Bad didn't ruin television. It raised the price of impressing you."
)

GROUNDED_MEAL = (
    "That's like saying the best meal you'll ever eat is the first great restaurant you found."
)

SENSORY_YOU = "You already know exactly what it's going to taste like."


def test_bb_routes_taste_bourdain():
    assert classify_claim_domain(BB_PROMPT) == "taste_preference"
    plan = build_response_plan(BB_PROMPT)
    assert plan.lens == "Bourdain"
    assert plan.claim_domain == "taste_preference"


def test_viewer_psych_is_lens_drift():
    assert lens_drift(BB_PROMPT, DRIFTED) is True
    assert lens_drift(BB_PROMPT, DRIFTED, claim_domain="taste_preference", lens="Bourdain") is True


def test_craft_about_work_is_not_drift():
    assert lens_drift(BB_PROMPT, GROUNDED) is False
    assert lens_drift(BB_PROMPT, GROUNDED_MEAL) is False
    assert lens_drift(BB_PROMPT, SENSORY_YOU, lens="Bourdain") is False


def test_early_noun_object_vs_subject():
    bad = early_noun_report(BB_PROMPT, DRIFTED, lens="Bourdain")
    assert bad["ok"] is False
    assert bad["direction"] == "Object → Subject"
    good = early_noun_report(BB_PROMPT, GROUNDED, lens="Bourdain")
    assert good["ok"] is True
    assert "Breaking Bad" in good["first_sentence"] or "television" in good["first_sentence"].lower()


def test_diagnosis_engineering_card():
    d = lens_drift_diagnosis(
        BB_PROMPT, DRIFTED, claim_domain="taste_preference", lens="Bourdain"
    )
    assert d["drifted"] is True
    assert d["expected_lens"] == "Bourdain"
    assert "Object → Subject" in d["drift"]
    assert d["layer"] == "Generation"


def test_evaluate_flags_lens_drift():
    fails = evaluate_gold_shape(BB_PROMPT, DRIFTED, "SNAP", response_budget="medium")
    assert "lens_drift" in fails
    fails_ok = evaluate_gold_shape(BB_PROMPT, GROUNDED, "SNAP", response_budget="medium")
    assert "lens_drift" not in fails_ok


def test_discovery_types():
    assert classify_discovery_type(GROUNDED, "Bourdain") == "Craft"
    assert (
        classify_discovery_type("Every threat is autobiographical.", "Emotional Intelligence")
        == "Projection"
    )


def test_inspector_lens_drift_check():
    from inspector.score import inspect_event

    event = {
        "prompt": BB_PROMPT,
        "output": DRIFTED + " 🥃",
        "diagnostics": {
            "claim_domain": "taste_preference",
            "lens": "Bourdain",
            "interpretive_lens": "Bourdain",
            "quality_failures": "lens_drift",
            "routing_structure": "SNAP",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "dominant_mechanism_count": "1",
            "premise_relocated": "true",
        },
    }
    insp = inspect_event(event)
    lens_check = next(c for c in insp["checks"] if c["name"] == "Lens drift")
    assert lens_check["status"] == "fail"
    assert "Object → Subject" in lens_check["why"]
    early = next(c for c in insp["checks"] if c["name"] == "Early nouns")
    assert early["status"] == "fail"


if __name__ == "__main__":
    test_bb_routes_taste_bourdain()
    test_viewer_psych_is_lens_drift()
    test_craft_about_work_is_not_drift()
    test_early_noun_object_vs_subject()
    test_diagnosis_engineering_card()
    test_evaluate_flags_lens_drift()
    test_discovery_types()
    test_inspector_lens_drift_check()
    print("ok")
