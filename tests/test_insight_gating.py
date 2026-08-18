# -*- coding: utf-8 -*-
"""Regression: DEPTH MUST BE EARNED / RECOGNITION MUST ADVANCE / START WHERE THE POST STOPS.

Saturday 2026-08-15 batch + courtship pair (2026-08-17).

Three failures of "every input deserves an insight":
  PARROTING         — burnout: prettier restatement of the user's own model
  PSYCHOLOGIZING    — Flock / wife-stocks: joke converted to diagnosis
  UNSUPPORTED DEPTH — whore-name: profundity with no textual basis

Paired with:
  provocation PASS  — condom: unexpected human truth beneath crude
  observation pair  — courtship: restatement vs start-where-the-post-stops
"""
from __future__ import annotations

from capability_detection import classify_social_mode, detect_comic_premise
from discovery_craft import (
    parroting,
    psychologizing,
    recognition_advances,
    restates_runway,
    starts_where_user_stopped,
    unsupported_depth,
)
from gold_shape import evaluate_gold_shape
from inspector.score import inspect_event
from response_finalization import CORE_WRITE_DIRECTIVE, build_response_plan, plan_closer_instruction


# --- Fixtures ---------------------------------------------------------------

BURNOUT = (
    "I've been in survival mode for so long I don't know how to connect with people anymore. "
    "Every attempt to reach out lands flat. I've forgotten how to socialize. "
    "My hobbies are gone and my personality feels muted."
)
BURNOUT_PARROT = (
    "Survival mode has become the only operating system left. "
    "Connection requires a different one. Every attempt to reach out now lands flat. "
    "The hobbies and the self were the first things cut when the budget was survival only."
)
BURNOUT_ADVANCE = (
    "You keep reading the quiet as proof you lost the person you were. "
    "What you described is resource allocation — and some of that self only "
    "comes back through participation, not after you feel like yourself again."
)

FLOCK = (
    "I told my wife I was installing Flock cameras for security. "
    "Now she knows where I went, when I got home, what vehicle appeared, "
    "and she's probably got searchable footage."
)
FLOCK_PSYCH = (
    "It isn't about the driveway. It's about whether the house still belongs to you."
)
FLOCK_BIT = (
    "She doesn't need a warrant. She has timestamps, plates, and the clip of you "
    "saying you were at the gym."
)

WIFE_STOCKS = (
    "Checking the stocks with my wife is our love language. "
    "Red days she doesn't speak. Green days I exist. Same volatility, worse returns."
)
WIFE_STOCKS_PSYCH = (
    "You're not watching the market. You're checking whether you're still allowed "
    "to take up space — whether the house still belongs to you."
)
WIFE_STOCKS_BIT = (
    "Red days you're a pending order. Green days you clear. "
    "The spread is just whether she answers in the kitchen."
)

WHORE_NAME = (
    "They used to say your porn star name is your first pet plus the street "
    "you grew up on. Now it's just your actual fucking name."
)
WHORE_NAME_DEPTH = "You can't put a leash on something that won't wear one."
WHORE_NAME_BIT = "Identity theft has gotten incredibly lazy."

CONDOM = (
    "Condoms kill the mood. The wrapper is just a little legal notice that "
    "somebody in the room might be a problem."
)
CONDOM_PASS = (
    "Two people admit the body is a liability they can't outrun and still "
    "want the night anyway."
)

COURTSHIP = (
    "People have this backwards perception of traditional courtship in which "
    "the woman is completely passive and the man is doing all the pursuing. "
    "This was not the case in times past. Women used to hound men and drop "
    "such obvious hints that even the autists of today would catch on."
)
COURTSHIP_RESTATE = (
    "The myth of the passive woman was never about how women actually behaved. "
    "It was a polite fiction that let men believe they were the ones doing the "
    "choosing while the woman made sure the right man got the hint loud enough "
    "to act on it. Women have always pursued. They just used to do it with "
    "enough plausible deniability that the guy could still feel like the hunter "
    "instead of the hunted."
)
COURTSHIP_GOOD = (
    "Women have always pursued. They just used to do it with enough plausible "
    "deniability that the guy could still feel like the hunter instead of the hunted."
)

AXEL = (
    "Hot single girls have been getting their dopamine fried harder than any "
    "subset of human being ever. Be wary to this. In her lifetime, probably "
    "hundreds of thousands of story replies, DMs, and social opportunities. "
    "Guess what happens when you start dating? That dies out."
)
AXEL_PSYCH = (
    "The flood of attention doesn't just feel good. It rewires what 'normal' "
    "feels like. Hundreds of thousands of story replies, DMs, and small hits "
    "train the nervous system to treat that volume as baseline. When a "
    "relationship cuts the supply, the body registers it as loss."
)

HATE_PEOPLE = (
    "I hate people. Not in a cute misanthrope way. In a I-need-a-nap-from-existing way."
)


def _checks(insp):
    return {c["name"]: c for c in insp["checks"]}


def _inspect(prompt: str, output: str, **extra):
    plan = build_response_plan(prompt)
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
                **extra,
            },
        }
    )


# --- Social mode routing ----------------------------------------------------

def test_burnout_is_vulnerability_not_comic():
    comic = detect_comic_premise(BURNOUT)
    assert comic.active is False
    social = classify_social_mode(BURNOUT)
    assert social.mode == "vulnerability"
    plan = build_response_plan(BURNOUT)
    assert plan.social_mode == "vulnerability"
    assert plan.comic_premise is False
    assert plan.primary_capability != "Humor As Disruption"


def test_flock_and_stocks_are_comic_bits():
    for src in (FLOCK, WIFE_STOCKS, WHORE_NAME, HATE_PEOPLE):
        comic = detect_comic_premise(src)
        social = classify_social_mode(src)
        plan = build_response_plan(src)
        assert comic.active, src[:60]
        assert social.mode == "comic", src[:60]
        assert plan.comic_premise is True
        assert plan.never_cure_premise is True
        assert plan.primary_capability == "Humor As Disruption"
        assert plan.social_mode == "comic"


def test_condom_is_provocation_not_never_cure():
    social = classify_social_mode(CONDOM)
    assert social.mode == "provocation"
    plan = build_response_plan(CONDOM)
    assert plan.social_mode == "provocation"
    assert plan.comic_premise is False
    assert plan.primary_capability != "Humor As Disruption"


def test_courtship_is_observation():
    social = classify_social_mode(COURTSHIP)
    assert social.mode == "observation"
    plan = build_response_plan(COURTSHIP)
    assert plan.social_mode == "observation"
    assert plan.comic_premise is False


def test_fiber_still_question():
    social = classify_social_mode("How do I replace a fiber connector?")
    assert social.mode == "question"


# --- Parroting / recognition must advance ----------------------------------

def test_burnout_parrot_detected():
    assert parroting(BURNOUT, BURNOUT_PARROT) is True
    assert recognition_advances(BURNOUT, BURNOUT_PARROT) is False
    assert parroting(BURNOUT, BURNOUT_ADVANCE) is False
    assert recognition_advances(BURNOUT, BURNOUT_ADVANCE) is True


def test_burnout_evaluate_and_inspector():
    fails = evaluate_gold_shape(BURNOUT, BURNOUT_PARROT, "KNIFE")
    assert "parroting" in fails
    insp = _inspect(BURNOUT, BURNOUT_PARROT)
    assert _checks(insp)["Recognition must advance"]["status"] == "fail"
    ok = _inspect(BURNOUT, BURNOUT_ADVANCE)
    assert _checks(ok)["Recognition must advance"]["status"] == "pass"


# --- Psychologizing --------------------------------------------------------

def test_flock_psychologizing():
    assert psychologizing(FLOCK, FLOCK_PSYCH, comic=True) is True
    assert unsupported_depth(FLOCK, FLOCK_PSYCH, comic=True) is True
    assert psychologizing(FLOCK, FLOCK_BIT, comic=True) is False
    assert unsupported_depth(FLOCK, FLOCK_BIT, comic=True) is False


def test_wife_stocks_same_failure():
    assert psychologizing(WIFE_STOCKS, WIFE_STOCKS_PSYCH, comic=True) is True
    assert psychologizing(WIFE_STOCKS, WIFE_STOCKS_BIT, comic=True) is False
    fails = evaluate_gold_shape(WIFE_STOCKS, WIFE_STOCKS_PSYCH, "SNAP")
    assert "psychologizing" in fails


def test_axel_psychologizing_complete_take():
    assert psychologizing(AXEL, AXEL_PSYCH, comic=False) is True
    insp = _inspect(AXEL, AXEL_PSYCH)
    assert _checks(insp)["Psychologizing"]["status"] == "fail"


# --- Unsupported depth -----------------------------------------------------

def test_whore_name_unsupported_depth():
    assert detect_comic_premise(WHORE_NAME).active
    assert unsupported_depth(WHORE_NAME, WHORE_NAME_DEPTH, comic=True) is True
    assert unsupported_depth(WHORE_NAME, WHORE_NAME_BIT, comic=True) is False
    fails = evaluate_gold_shape(WHORE_NAME, WHORE_NAME_DEPTH, "SNAP")
    assert "unsupported_depth" in fails
    insp = _inspect(WHORE_NAME, WHORE_NAME_DEPTH)
    assert _checks(insp)["Unsupported depth"]["status"] == "fail"
    ok = _inspect(WHORE_NAME, WHORE_NAME_BIT)
    assert _checks(ok)["Unsupported depth"]["status"] == "pass"


# --- Start where the post stops --------------------------------------------

def test_courtship_pair():
    assert restates_runway(COURTSHIP, COURTSHIP_RESTATE) is True
    assert starts_where_user_stopped(COURTSHIP, COURTSHIP_RESTATE) is False
    assert restates_runway(COURTSHIP, COURTSHIP_GOOD) is False
    assert starts_where_user_stopped(COURTSHIP, COURTSHIP_GOOD) is True
    assert recognition_advances(COURTSHIP, COURTSHIP_GOOD) is True
    insp_bad = _inspect(COURTSHIP, COURTSHIP_RESTATE)
    assert _checks(insp_bad)["Start where the post stops"]["status"] == "fail"
    insp_good = _inspect(COURTSHIP, COURTSHIP_GOOD)
    assert _checks(insp_good)["Start where the post stops"]["status"] == "pass"


# --- Provocation may earn depth --------------------------------------------

def test_condom_transformation_not_flagged():
    assert parroting(CONDOM, CONDOM_PASS) is False
    assert unsupported_depth(CONDOM, CONDOM_PASS, comic=False) is False
    assert psychologizing(CONDOM, CONDOM_PASS, comic=False) is False
    assert recognition_advances(CONDOM, CONDOM_PASS) is True
    fails = evaluate_gold_shape(CONDOM, CONDOM_PASS, "SNAP")
    assert "parroting" not in fails
    assert "unsupported_depth" not in fails
    assert "psychologizing" not in fails


# --- Guidance injected -----------------------------------------------------

def test_guidance_names_the_gates():
    blob = CORE_WRITE_DIRECTIVE.lower()
    assert "depth must be earned" in blob
    assert "recognition must advance" in blob
    assert "start where the user stopped" in blob
    assert "parroting" in blob
    assert "unsupported depth" in blob

    burn = plan_closer_instruction(build_response_plan(BURNOUT)).lower()
    assert "recognition must advance" in burn
    assert "operating system" in burn

    flock = plan_closer_instruction(build_response_plan(FLOCK)).lower()
    assert "never cure the premise" in flock
    assert "left the bit" in flock or "house still belongs" in flock

    court = plan_closer_instruction(build_response_plan(COURTSHIP)).lower()
    assert "start where the post stops" in court
    assert "plausible deniability" in court


def test_matt_comic_still_routes():
    matt = (
        "Only 3 more years of bulking and cutting and I can begin phase one "
        "of looking women in the eyes"
    )
    plan = build_response_plan(matt)
    assert plan.comic_premise is True
    assert plan.social_mode == "comic"
    assert plan.primary_capability == "Humor As Disruption"


if __name__ == "__main__":
    test_burnout_is_vulnerability_not_comic()
    test_flock_and_stocks_are_comic_bits()
    test_condom_is_provocation_not_never_cure()
    test_courtship_is_observation()
    test_fiber_still_question()
    test_burnout_parrot_detected()
    test_burnout_evaluate_and_inspector()
    test_flock_psychologizing()
    test_wife_stocks_same_failure()
    test_axel_psychologizing_complete_take()
    test_whore_name_unsupported_depth()
    test_courtship_pair()
    test_condom_transformation_not_flagged()
    test_guidance_names_the_gates()
    test_matt_comic_still_routes()
    print("ok")
