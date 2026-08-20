# -*- coding: utf-8 -*-
"""CONTRIBUTION BUDGET — permission to add material, not a new interaction shape.

Capability = what kind of intelligence. Shape = what form. Budget = how much you may add.
zero | micro | one_beat | develop

X-post fixtures (2026-08-20):
  Paula: completed comic escalation → zero; don't compete with the punchline
  KFC: low-stakes swagger → micro; no brand analysis
  Murray Hill: comic taxonomy → one beat; not a second list
  Feelings: recognition → one beat; articulation, not dissection
  Stefan: mechanism claim → develop; don't inherit the supplied causal story
  Manager/video: media owns meaning → zero
  Delivery dad: withheld resolution → zero
"""
from __future__ import annotations

from capability_detection import classify_comic_bit_shape, classify_social_mode
from discovery_craft import (
    classify_contribution_budget,
    competes_with_punchline,
    exceeds_contribution_budget,
)
from gold_shape import evaluate_gold_shape
from inspector.score import inspect_event
from response_finalization import (
    CORE_WRITE_DIRECTIVE,
    build_response_plan,
    plan_runtime_instruction,
)


PAULA = (
    'why am I still hearing "let me ask claude" in meetings\n\n'
    "invite him. send claude the google meet."
)
PAULA_FAIL = "At this point Claude deserves equity and a parking spot. 🥃"
PAULA_PASS = "Send the calendar too. 🥃"

KFC = "haters real quiet since we brought back popcorn chicken"
KFC_FAIL = (
    "Bringing back a fan favorite rebuilds goodwill and reminds the brand "
    "what consumer-behavior actually rewards. 🥃"
)
KFC_PASS = "Popcorn chicken ended the discourse. 🥃"

MURRAY = (
    "Successful couples by city:\n\n"
    "New York: finance guy / fashion girl\n"
    "LA: actor / yoga instructor\n"
    "San Francisco: white tech guy / Asian tech girl\n"
    "Miami: older guy / Instagram girl\n"
    "Austin: both in startups\n"
    "Chicago: both in consulting\n"
    "Boston: doctor / lawyer\n"
    "Seattle: both at Amazon"
)
MURRAY_FAIL = (
    "Denver: both on bikes\n"
    "Portland: both in coffee\n"
    "Nashville: both in music. 🥃"
)
MURRAY_PASS = "Atlanta: both pretending they don't live in Atlanta. 🥃"

FEELINGS = "that feeling when I see us laughing about nothing at 2am"
FEELINGS_FAIL = (
    "Shared laughter during unstructured late-night interactions creates "
    "emotional intimacy because it signals safety without a plan. 🥃"
)
FEELINGS_PASS = "That's usually the part you end up missing. 🥃"

STEFAN = (
    "Women who have children later in life have higher rates of postpartum "
    "depression because they spent years being the center of male attention "
    "and resent the baby for taking that away."
)
MANAGER = (
    "what type of manager do you have to be for your employees to fight "
    "for you like this"
)
DAD = "Dad's a delivery driver. His son didn't know. Until..."
CAMELS = (
    "This camel collapsed from heat exhaustion. Climate change is here. Debate over."
)
ENERGY_DRINK = (
    "An energy drink is $2.50 a day.\n\n"
    "That's $17.50 a week, $75 a month, and $900 a year.\n\n"
    "If you quit drinking them for 10 years, you'll save $9,000.\n\n"
    "That's still not enough for your dream car.\n\n"
    "So just enjoy the energy drink."
)
ENERGY_MICRO = "Retirement plan denied. Crack the can. 🥃"
VILLAIN = "name a villain who was 100% right"
KILLMONGER_HEAT = (
    "Killmonger. Wakanda spent centuries watching the world bleed while sitting "
    "on the means to help it, then called that restraint. He was right about the "
    "hypocrisy; he just confused justice with vengeance. The diagnosis made him "
    "dangerous. The prescription made him the villain. 🥃"
)


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
                "routing_structure": plan.routed_structure or "SNAP",
                "structure_persistence": "routing_only",
                "lens_locked": "true",
                "dominant_mechanism_count": "1",
                "premise_relocated": "true",
                "comic_premise": str(bool(plan.comic_premise)).lower(),
                "engagement_energy": str(bool(plan.engagement_energy)).lower(),
                "contribution_budget": plan.contribution_budget,
            },
        }
    )


def test_contribution_budgets_by_social_job():
    assert classify_contribution_budget(PAULA) == "zero"
    assert classify_comic_bit_shape(PAULA) == "terminal"
    assert classify_social_mode(PAULA).interaction_shape == "terminal_bit"
    assert classify_contribution_budget(KFC) == "micro"
    assert classify_contribution_budget(ENERGY_DRINK) == "micro"
    assert classify_contribution_budget(MURRAY) == "one_beat"
    assert classify_contribution_budget(FEELINGS) == "one_beat"
    assert classify_contribution_budget(STEFAN) == "develop"
    assert classify_contribution_budget(CAMELS) == "develop"
    assert classify_contribution_budget(MANAGER) == "zero"
    assert classify_contribution_budget(DAD) == "zero"
    assert classify_contribution_budget(VILLAIN) == "develop"
    assert build_response_plan(PAULA).contribution_budget == "zero"
    assert build_response_plan(KFC).contribution_budget == "micro"


def test_paula_does_not_compete_with_punchline():
    assert competes_with_punchline(PAULA, PAULA_FAIL) is True
    assert competes_with_punchline(PAULA, PAULA_PASS) is False
    assert exceeds_contribution_budget(PAULA, PAULA_FAIL) is True
    assert exceeds_contribution_budget(PAULA, PAULA_PASS) is False
    fails = evaluate_gold_shape(PAULA, PAULA_FAIL, "SNAP")
    assert "over_contribution" in fails
    ok = evaluate_gold_shape(PAULA, PAULA_PASS, "SNAP")
    assert "over_contribution" not in ok
    insp = _inspect(PAULA, PAULA_FAIL)
    assert _checks(insp)["Contribution budget"]["status"] == "fail"


def test_kfc_and_energy_drink_micro():
    assert exceeds_contribution_budget(KFC, KFC_FAIL) is True
    assert exceeds_contribution_budget(KFC, KFC_PASS) is False
    assert exceeds_contribution_budget(ENERGY_DRINK, ENERGY_MICRO) is False
    assert "over_contribution" in evaluate_gold_shape(KFC, KFC_FAIL, "SNAP")


def test_one_beat_recognition_and_taxonomy():
    assert exceeds_contribution_budget(FEELINGS, FEELINGS_FAIL) is True
    assert exceeds_contribution_budget(FEELINGS, FEELINGS_PASS) is False
    assert exceeds_contribution_budget(MURRAY, MURRAY_FAIL) is True
    assert exceeds_contribution_budget(MURRAY, MURRAY_PASS) is False


def test_develop_does_not_neuter_killmonger():
    assert classify_contribution_budget(VILLAIN) == "develop"
    assert exceeds_contribution_budget(VILLAIN, KILLMONGER_HEAT) is False
    insp = _inspect(VILLAIN, KILLMONGER_HEAT)
    assert _checks(insp)["Contribution budget"]["status"] == "pass"


def test_runtime_names_contribution_budget():
    blob = CORE_WRITE_DIRECTIVE.lower()
    assert "contribution budget" in blob
    assert "don't compete with the punchline" in blob or "do not compete with the punchline" in blob
    guide = plan_runtime_instruction(build_response_plan(PAULA)).lower()
    assert "contribution budget: zero" in guide
    kfc = plan_runtime_instruction(build_response_plan(KFC)).lower()
    assert "contribution budget: micro" in kfc


if __name__ == "__main__":
    test_contribution_budgets_by_social_job()
    print("ok classify")
    test_paula_does_not_compete_with_punchline()
    print("ok paula")
    test_kfc_and_energy_drink_micro()
    print("ok micro")
    test_one_beat_recognition_and_taxonomy()
    print("ok one beat")
    test_develop_does_not_neuter_killmonger()
    print("ok develop")
    test_runtime_names_contribution_budget()
    print("ok")
