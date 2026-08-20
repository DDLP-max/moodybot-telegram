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
LAUNCHPAD = (
    "The crazy label is just what people reach for when they need time to "
    "rewrite the story so they were never wrong. 🥃"
)
CRAZY_EVIDENCE = "Everybody loves calling it crazy before it turns into evidence. 🥃"
SHELF_LIFE = "Crazy has a remarkably short shelf life once the receipts show up. 🥃"
ENDGAME = (
    "I genuinely don't get the endgame. If the plan ends with a ruined planet, "
    "collapsed economies, and no working class left to spend money... what are "
    "billionaires actually hoarding wealth for? To sit in a bunker with numbers "
    "on a screen that don't mean anything anymore? What is the actual point?"
)
ENDGAME_FAIL = (
    "The numbers on the screen aren't a future currency. They're the permanent "
    "receipt that someone else is still below them, even after the air turns "
    "toxic and the markets stop moving. The bunker is just the final scoreboard. 🥃"
)
ENDGAME_PASS = (
    "Turns out infinite money still requires a functioning planet to spend it on. 🥃"
)
ENDGAME_PASS_2 = (
    "That's the part nobody can put on the balance sheet: wealth only works "
    "while there's still a world willing to honor it. 🥃"
)
ENDGAME_LITERARY = (
    "The confusion isn't really about their spreadsheets. It's the quieter dread "
    "that the whole point was always just keeping the numbers bigger than the "
    "other guy's, even after the room stops existing. Like saving up all your "
    "chips while the casino burns down around you, because at least the pile "
    "still proves you didn't walk away empty-handed. 🥃"
)
ENDGAME_CASINO_PASS = (
    "You can own every chip in the casino. It still doesn't help when there's "
    "no casino left. 🥃"
)
ENDGAME_CUSTOMERS_PASS = (
    "Hard to win capitalism if your endgame is deleting all the customers. 🥃"
)
ENDGAME_COMPRESSED = (
    "The confusion hits because the numbers were never supposed to survive "
    "the collapse. They just had to stay bigger than the next guy's until the "
    "lights went out. That's the only scoreboard that still registers when "
    "everything else stops making sense. 🥃"
)
ENDGAME_SCORE_PASS = (
    "Hard to call it winning when your endgame deletes the economy keeping score. 🥃"
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
    assert authors_unobserved_interior(MATT, LAUNCHPAD) is True
    assert authors_unobserved_interior(MATT, CRAZY_EVIDENCE) is False
    assert authors_unobserved_interior(MATT, SHELF_LIFE) is False


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


def test_skips_when_user_supplied_interior():
    assert authors_unobserved_interior(USER_SUPPLIED, USER_SUPPLIED_REPLY) is False


def test_question_does_not_license_interior():
    """A why-question is not permission to state an unknowable motive as fact."""
    invited = "Why did they call me crazy after I turned out to be right?"
    assert authors_unobserved_interior(invited, INVENTED_GUILT) is True


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
    launch = evaluate_gold_shape(MATT, LAUNCHPAD, "SNAP")
    assert "authored_interior" in launch
    assert "authored_interior" not in evaluate_gold_shape(MATT, CRAZY_EVIDENCE, "SNAP")
    assert "authored_interior" not in evaluate_gold_shape(MATT, SHELF_LIFE, "SNAP")

    insp_fail = _inspect(MATT, INVENTED_GUILT)
    assert _checks(insp_fail)["Object before author"]["status"] == "fail"
    insp_launch = _inspect(MATT, LAUNCHPAD)
    assert _checks(insp_launch)["Object before author"]["status"] == "fail"
    insp_ok = _inspect(MATT, RECEIPTS)
    assert _checks(insp_ok)["Object before author"]["status"] == "pass"
    insp_shelf = _inspect(MATT, SHELF_LIFE)
    assert _checks(insp_shelf)["Object before author"]["status"] == "pass"


def test_literary_wrap_and_user_override_are_still_authored():
    """Changing the metaphor does not change the proposition.

    Isolated user-interior override fails even without status-hunger payload.
    Naming dread in the prompt skips that family, not the status-hunger family.
    """
    override_only = (
        "The confusion isn't really about their spreadsheets. It's the quieter "
        "dread that the room is already gone. 🥃"
    )
    assert authors_unobserved_interior(ENDGAME, override_only) is True
    named = (
        "I genuinely don't get the endgame. The dread is that the numbers stop "
        "meaning anything. What is the actual point?"
    )
    assert authors_unobserved_interior(named, override_only) is False
    assert authors_unobserved_interior(named, ENDGAME_LITERARY) is True


def test_endgame_does_not_author_status_hunger():
    """Rhetorical what's-the-point is the contradiction, not a license to mind-read."""
    assert authors_unobserved_interior(ENDGAME, ENDGAME_FAIL) is True
    assert authors_unobserved_interior(ENDGAME, ENDGAME_PASS) is False
    assert authors_unobserved_interior(ENDGAME, ENDGAME_PASS_2) is False
    assert authors_unobserved_interior(ENDGAME, ENDGAME_LITERARY) is True
    assert authors_unobserved_interior(ENDGAME, ENDGAME_CASINO_PASS) is False
    assert authors_unobserved_interior(ENDGAME, ENDGAME_CUSTOMERS_PASS) is False
    assert authors_unobserved_interior(ENDGAME, ENDGAME_COMPRESSED) is True
    assert authors_unobserved_interior(ENDGAME, ENDGAME_SCORE_PASS) is False
    assert "authored_interior" in evaluate_gold_shape(ENDGAME, ENDGAME_FAIL, "SNAP")
    assert "authored_interior" in evaluate_gold_shape(ENDGAME, ENDGAME_LITERARY, "SNAP")
    assert "authored_interior" not in evaluate_gold_shape(ENDGAME, ENDGAME_PASS, "SNAP")
    assert "authored_interior" not in evaluate_gold_shape(ENDGAME, ENDGAME_PASS_2, "SNAP")
    assert "authored_interior" not in evaluate_gold_shape(
        ENDGAME, ENDGAME_CASINO_PASS, "SNAP"
    )
    assert "authored_interior" not in evaluate_gold_shape(
        ENDGAME, ENDGAME_CUSTOMERS_PASS, "SNAP"
    )
    assert "authored_interior" in evaluate_gold_shape(ENDGAME, ENDGAME_COMPRESSED, "SNAP")
    assert "authored_interior" not in evaluate_gold_shape(
        ENDGAME, ENDGAME_SCORE_PASS, "SNAP"
    )
    insp_fail = _inspect(ENDGAME, ENDGAME_FAIL)
    assert _checks(insp_fail)["Object before author"]["status"] == "fail"
    insp_wrap = _inspect(ENDGAME, ENDGAME_LITERARY)
    assert _checks(insp_wrap)["Object before author"]["status"] == "fail"
    insp_ok = _inspect(ENDGAME, ENDGAME_PASS)
    assert _checks(insp_ok)["Object before author"]["status"] == "pass"
    insp_casino = _inspect(ENDGAME, ENDGAME_CASINO_PASS)
    assert _checks(insp_casino)["Object before author"]["status"] == "pass"
    insp_customers = _inspect(ENDGAME, ENDGAME_CUSTOMERS_PASS)
    assert _checks(insp_customers)["Object before author"]["status"] == "pass"
    insp_compressed = _inspect(ENDGAME, ENDGAME_COMPRESSED)
    assert _checks(insp_compressed)["Object before author"]["status"] == "fail"
    insp_score = _inspect(ENDGAME, ENDGAME_SCORE_PASS)
    assert _checks(insp_score)["Object before author"]["status"] == "pass"
    guide = plan_runtime_instruction(build_response_plan(ENDGAME)).lower()
    assert "licensed interior" in guide
    assert "permanent receipt" in guide
    assert "metaphor inherits" in guide
    assert "quieter dread" in guide
    assert "no casino left" in guide


def test_killmonger_heat_does_not_false_positive():
    ok = evaluate_gold_shape(VILLAIN, KILLMONGER_HEAT, "KNIFE")
    assert "authored_interior" not in ok
    insp = _inspect(VILLAIN, KILLMONGER_HEAT)
    assert _checks(insp)["Object before author"]["status"] == "pass"


def test_authored_interior_family_is_one_violation():
    """Different surface language, same latent violation."""
    override = (
        "The confusion isn't really about their spreadsheets. It's the quieter "
        "dread that the room is already gone. 🥃"
    )
    family = (
        (MATT, LAUNCHPAD),
        (TEXTS, TEXTS_AUTHORED),
        (ENDGAME, ENDGAME_FAIL),
        (ENDGAME, ENDGAME_LITERARY),
        (ENDGAME, ENDGAME_COMPRESSED),
        (ENDGAME, override),
    )
    for prompt, reply in family:
        assert authors_unobserved_interior(prompt, reply) is True
        assert "authored_interior" in evaluate_gold_shape(prompt, reply, "SNAP")


def test_core_write_and_energy_name_the_contract():
    """Durable concepts — not historical FAIL phrases pinned verbatim."""
    blob = CORE_WRITE_DIRECTIVE.lower()
    assert "object before author" in blob
    assert "established truth hotter" in blob
    assert "licensed interior" in blob
    assert "metaphor inherits" in blob
    assert "does not change the proposition" in blob
    assert "literary wrapping" in blob
    assert "heat the contradiction" in blob
    assert "really feeling" in blob
    assert "contribution budget" in blob

    closer = plan_closer_instruction(build_response_plan(MATT)).lower()
    assert "object before author" in closer
    turn = plan_runtime_instruction(build_response_plan(MATT)).lower()
    assert "object before author" in turn
    assert "licensed interior" in turn
    assert "metaphor inherits" in turn
    assert "literary" in turn
    assert "really feeling" in turn
    assert "heat the contradiction" in turn

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
    test_skips_when_user_supplied_interior()
    print("ok skip supplied")
    test_question_does_not_license_interior()
    print("ok question not license")
    test_literary_wrap_and_user_override_are_still_authored()
    print("ok literary wrap")
    test_endgame_does_not_author_status_hunger()
    print("ok endgame")
    test_skips_comic_and_pick_and_defend()
    print("ok skip shapes")
    test_matt_gold_and_inspector()
    print("ok gold")
    test_killmonger_heat_does_not_false_positive()
    print("ok killmonger")
    test_authored_interior_family_is_one_violation()
    print("ok family")
    test_core_write_and_energy_name_the_contract()
    print("ok")
