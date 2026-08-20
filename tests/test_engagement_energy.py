# -*- coding: utf-8 -*-
"""ENGAGEMENT ENERGY — writing dimension after routing, not a new shape.

Killmonger fixture (2026-08-20):
  Prompt: name a villain who was 100% right
  Flat:  The diagnosis was airtight. Only the prescription turned him into the villain…
         position high / tension medium / quotability medium
  Heat:  Wakanda / hypocrisy / justice vs vengeance — all three high
  Perfume: Justice wears the mask of vengeance in the messy visceral hues of reality.
"""
from __future__ import annotations

from capability_detection import classify_social_mode
from discovery_craft import (
    engagement_energy_earned,
    engagement_energy_flat,
    engagement_perfume,
    score_engagement_energy,
)
from gold_shape import evaluate_gold_shape
from inspector.score import inspect_event
from prompt_runtime import build_runtime_prompt
from response_finalization import (
    CORE_WRITE_DIRECTIVE,
    build_response_plan,
    plan_closer_instruction,
    plan_runtime_instruction,
)


VILLAIN = "name a villain who was 100% right"
VILLAIN_THOUGHTS = "/thoughts Name a villain who was 100% right"

KILLMONGER_FLAT = (
    "The diagnosis was airtight. Only the prescription turned him into the "
    "villain the story needed. 🥃"
)
KILLMONGER_HEAT = (
    "Killmonger. Wakanda spent centuries watching the world bleed while sitting "
    "on the means to help it, then called that restraint. He was right about the "
    "hypocrisy; he just confused justice with vengeance. The diagnosis made him "
    "dangerous. The prescription made him the villain. 🥃"
)
KILLMONGER_PERFUME = (
    "Justice wears the mask of vengeance in the messy visceral hues of reality. 🥃"
)
KILLMONGER_TRIVIA = "Thanos. The numbers never lied. 🥃"
KILLMONGER_LINE = (
    "He was right about Wakanda's hypocrisy; he just confused justice with vengeance. 🥃"
)

SANDLER = "Name an actor who immediately makes you NOT want to watch a movie"
ENERGY_DRINK = (
    "An energy drink is $2.50 a day.\n\n"
    "That's $17.50 a week, $75 a month, and $900 a year.\n\n"
    "If you quit drinking them for 10 years, you'll save $9,000.\n\n"
    "That's still not enough for your dream car.\n\n"
    "So just enjoy the energy drink."
)
BURNOUT = (
    "I've been in survival mode for so long I don't know how to connect with people anymore."
)
FIBER = "How do I replace a fiber connector?"


def _checks(insp):
    return {c["name"]: c for c in insp["checks"]}


def _inspect(prompt: str, output: str):
    plan = build_response_plan(prompt, selected_command="/thoughts")
    return inspect_event(
        {
            "prompt": prompt,
            "output": output,
            "diagnostics": {
                "claim_domain": plan.claim_domain,
                "lens": plan.lens,
                "routing_structure": plan.routed_structure or "KNIFE",
                "structure_persistence": "routing_only",
                "lens_locked": "true",
                "dominant_mechanism_count": "1",
                "premise_relocated": "true",
                "comic_premise": str(bool(plan.comic_premise)).lower(),
                "engagement_energy": str(bool(plan.engagement_energy)).lower(),
            },
        }
    )


def test_villain_earns_engagement_energy():
    for msg in (VILLAIN, VILLAIN_THOUGHTS):
        social = classify_social_mode(msg)
        assert social.interaction_shape == "pick_and_defend"
        plan = build_response_plan(msg, selected_command="/thoughts")
        assert plan.engagement_energy is True
        assert engagement_energy_earned(msg, plan=plan) is True
        guide = plan_runtime_instruction(plan)
        assert "ENGAGEMENT ENERGY" in guide
        assert "TAKE A SIDE" in guide
        assert "visceral hues" in guide.lower()
        assert "diagnosis was airtight" in guide.lower()
        closer = plan_closer_instruction(plan).lower()
        assert "take a side" in closer
        rt = build_runtime_prompt(plan, social=social, selected_command="/thoughts")
        assert "engagement-energy.md" in ",".join(rt.module_paths)


def test_engagement_energy_does_not_fire_on_snap_grief_or_facts():
    sandler = build_response_plan(SANDLER)
    assert sandler.interaction_shape == "pick_one"
    assert sandler.engagement_energy is False
    assert "TAKE A SIDE. CREATE FRICTION" not in plan_runtime_instruction(sandler)

    energy = build_response_plan(ENERGY_DRINK)
    assert energy.interaction_shape == "terminal_bit"
    assert energy.engagement_energy is False

    burn = build_response_plan(BURNOUT)
    assert burn.social_mode == "vulnerability"
    assert burn.engagement_energy is False

    fiber = build_response_plan(FIBER)
    assert fiber.engagement_energy is False


def test_killmonger_scores_flat_vs_heat_vs_perfume():
    plan = build_response_plan(VILLAIN, selected_command="/thoughts")
    flat = score_engagement_energy(VILLAIN, KILLMONGER_FLAT, plan=plan)
    assert flat.earned is True
    assert flat.position == "high"
    assert flat.tension == "medium"
    assert flat.quotability == "medium"
    assert flat.perfume is False
    assert flat.hits_target is False
    assert engagement_energy_flat(VILLAIN, KILLMONGER_FLAT, plan=plan) is True

    heat = score_engagement_energy(VILLAIN, KILLMONGER_HEAT, plan=plan)
    assert heat.position == "high"
    assert heat.tension == "high"
    assert heat.quotability == "high"
    assert heat.perfume is False
    assert heat.hits_target is True
    assert engagement_energy_flat(VILLAIN, KILLMONGER_HEAT, plan=plan) is False

    line = score_engagement_energy(VILLAIN, KILLMONGER_LINE, plan=plan)
    assert line.position == "high"
    assert line.tension == "high"
    assert line.quotability == "high"
    assert line.perfume is False

    perfume = score_engagement_energy(VILLAIN, KILLMONGER_PERFUME, plan=plan)
    assert perfume.perfume is True
    assert perfume.hits_target is False
    assert engagement_perfume(VILLAIN, KILLMONGER_PERFUME, plan=plan) is True

    trivia = score_engagement_energy(VILLAIN, KILLMONGER_TRIVIA, plan=plan)
    assert trivia.hits_target is False
    assert engagement_energy_flat(VILLAIN, KILLMONGER_TRIVIA, plan=plan) is True


def test_killmonger_gold_and_inspector():
    fails = evaluate_gold_shape(VILLAIN, KILLMONGER_FLAT, "KNIFE")
    assert "engagement_flat" in fails
    ok = evaluate_gold_shape(VILLAIN, KILLMONGER_HEAT, "KNIFE")
    assert "engagement_flat" not in ok
    assert "engagement_perfume" not in ok
    perfume_fails = evaluate_gold_shape(VILLAIN, KILLMONGER_PERFUME, "KNIFE")
    assert "engagement_perfume" in perfume_fails

    insp = _inspect(VILLAIN, KILLMONGER_FLAT)
    assert _checks(insp)["Engagement energy"]["status"] == "fail"
    insp_ok = _inspect(VILLAIN, KILLMONGER_HEAT)
    assert _checks(insp_ok)["Engagement energy"]["status"] == "pass"
    insp_perfume = _inspect(VILLAIN, KILLMONGER_PERFUME)
    assert _checks(insp_perfume)["Engagement energy"]["status"] == "fail"


def test_core_write_gates_engagement_energy():
    blob = CORE_WRITE_DIRECTIVE.lower()
    assert "take a side" in blob
    assert "create friction" in blob
    assert "quotable" in blob
    assert "perfume" in blob
    assert "terminal bits" in blob
    assert "visceral hues" in blob


if __name__ == "__main__":
    test_villain_earns_engagement_energy()
    print("ok earn")
    test_engagement_energy_does_not_fire_on_snap_grief_or_facts()
    print("ok gate")
    test_killmonger_scores_flat_vs_heat_vs_perfume()
    print("ok scores")
    test_killmonger_gold_and_inspector()
    print("ok gold")
    test_core_write_gates_engagement_energy()
    print("ok")
