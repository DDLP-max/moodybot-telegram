# -*- coding: utf-8 -*-
"""OBJECT BEFORE AUTHOR — heat the established object; don't author unobserved interior.

Live fixture (2026-08-20):
  Matt: Bitches will call you crazy for assuming shit that ends up being true
  FAIL: They don't call you crazy because the read was off. They call you crazy
        because now they have to live with the fact that you saw straight through them.
        High engagement. Invented guilt. Miniature conspiracy.
  PASS: Everybody hates assumptions right up until the receipts arrive.
  PASS: The worst part about being called paranoid is how rarely anyone apologizes
        when the evidence finally shows up.

Contract that survives the energy layer:
  Make the established truth hotter. Don't manufacture a hidden truth just because
  it hits harder.
"""
from __future__ import annotations

from discovery_craft import authors_unobserved_interior
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
KILLMONGER_HEAT = (
    "Killmonger. Wakanda spent centuries watching the world bleed while sitting "
    "on the means to help it, then called that restraint. He was right about the "
    "hypocrisy; he just confused justice with vengeance. The diagnosis made him "
    "dangerous. The prescription made him the villain. 🥃"
)


MATT = "Bitches will call you crazy for assuming shit that ends up being true"

INVENTED_GUILT = (
    "They don't call you crazy because the read was off. They call you crazy "
    "because now they have to live with the fact that you saw straight through them. 🥃"
)
RECEIPTS = "Everybody hates assumptions right up until the receipts arrive. 🥃"
PARANOID = (
    "The worst part about being called paranoid is how rarely anyone apologizes "
    "when the evidence finally shows up. 🥃"
)
OBJECT_HEAT = (
    "They call you crazy because being right too early looks like paranoia. 🥃"
)
TEXTS = "He texts you every night but somehow never has time to see you."
TEXTS_INFERENCE = "Funny how interest always finds time until time requires effort. 🥃"
TEXTS_AUTHORED = "He likes knowing you're waiting for him. 🥃"
USER_SUPPLIED = "She knew I was onto her and still called me crazy."
USER_SUPPLIED_REPLY = (
    "They call you crazy because now they have to live with the fact that you "
    "saw straight through them. 🥃"
)
ENERGY_DRINK = (
    "An energy drink is $2.50 a day.\n\n"
    "That's $17.50 a week, $75 a month, and $900 a year.\n\n"
    "If you quit drinking them for 10 years, you'll save $9,000.\n\n"
    "That's still not enough for your dream car.\n\n"
    "So just enjoy the energy drink."
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
            },
        }
    )


def test_matt_authors_unobserved_interior():
    assert authors_unobserved_interior(MATT, INVENTED_GUILT) is True
    assert authors_unobserved_interior(MATT, RECEIPTS) is False
    assert authors_unobserved_interior(MATT, PARANOID) is False
    assert authors_unobserved_interior(MATT, OBJECT_HEAT) is False


def test_inference_is_not_authored_interior():
    """Characterize the pattern. Don't invent the actor's private explanation."""
    assert authors_unobserved_interior(TEXTS, TEXTS_INFERENCE) is False
    assert authors_unobserved_interior(TEXTS, TEXTS_AUTHORED) is True
    inference_fails = evaluate_gold_shape(TEXTS, TEXTS_INFERENCE, "SNAP")
    assert "authored_interior" not in inference_fails
    authored_fails = evaluate_gold_shape(TEXTS, TEXTS_AUTHORED, "SNAP")
    assert "authored_interior" in authored_fails
    insp = _inspect(TEXTS, TEXTS_INFERENCE)
    assert _checks(insp)["Object before author"]["status"] == "pass"
    insp_fail = _inspect(TEXTS, TEXTS_AUTHORED)
    assert _checks(insp_fail)["Object before author"]["status"] == "fail"


def test_skips_when_user_supplied_or_invited_interior():
    assert authors_unobserved_interior(USER_SUPPLIED, USER_SUPPLIED_REPLY) is False
    invited = "Why did they call me crazy after I turned out to be right?"
    assert authors_unobserved_interior(invited, INVENTED_GUILT) is False


def test_skips_comic_and_pick_and_defend():
    comic_reply = "They couldn't admit the $2.50 was never about the car. 🥃"
    assert authors_unobserved_interior(ENERGY_DRINK, comic_reply) is False
    assert authors_unobserved_interior(VILLAIN, KILLMONGER_HEAT) is False


def test_matt_gold_and_inspector():
    fails = evaluate_gold_shape(MATT, INVENTED_GUILT, "SNAP")
    assert "authored_interior" in fails

    receipts = evaluate_gold_shape(MATT, RECEIPTS, "SNAP")
    assert "authored_interior" not in receipts
    paranoid = evaluate_gold_shape(MATT, PARANOID, "SNAP")
    assert "authored_interior" not in paranoid

    insp_fail = _inspect(MATT, INVENTED_GUILT)
    assert _checks(insp_fail)["Object before author"]["status"] == "fail"
    insp_ok = _inspect(MATT, RECEIPTS)
    assert _checks(insp_ok)["Object before author"]["status"] == "pass"


def test_killmonger_heat_does_not_false_positive():
    ok = evaluate_gold_shape(VILLAIN, KILLMONGER_HEAT, "KNIFE")
    assert "authored_interior" not in ok
    insp = _inspect(VILLAIN, KILLMONGER_HEAT)
    assert _checks(insp)["Object before author"]["status"] == "pass"


def test_core_write_and_energy_name_the_contract():
    blob = CORE_WRITE_DIRECTIVE.lower()
    assert "object before author" in blob
    assert "established truth hotter" in blob
    assert "receipts arrive" in blob
    assert "saw straight through them" in blob
    assert "interest always finds time" in blob
    assert "waiting for him" in blob
    assert "contribution budget" in blob

    closer = plan_closer_instruction(build_response_plan(MATT)).lower()
    assert "object before author" in closer

    villain = build_response_plan(VILLAIN, selected_command="/thoughts")
    guide = plan_runtime_instruction(villain).lower()
    assert "object before author" in guide
    rt = build_runtime_prompt(villain, selected_command="/thoughts")
    joined = ",".join(rt.module_paths)
    assert "engagement-energy.md" in joined


if __name__ == "__main__":
    test_matt_authors_unobserved_interior()
    print("ok detector")
    test_inference_is_not_authored_interior()
    print("ok inference")
    test_skips_when_user_supplied_or_invited_interior()
    print("ok skip supplied")
    test_skips_comic_and_pick_and_defend()
    print("ok skip shapes")
    test_matt_gold_and_inspector()
    print("ok gold")
    test_killmonger_heat_does_not_false_positive()
    print("ok killmonger")
    test_core_write_and_energy_name_the_contract()
    print("ok")
