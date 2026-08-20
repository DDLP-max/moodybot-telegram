# -*- coding: utf-8 -*-
"""Cross-case regression: open vs taggable vs terminal comic bits."""
from __future__ import annotations

from capability_detection import (
    classify_comic_bit_shape,
    classify_social_mode,
    detect_comic_premise,
    inverted_comic_premise,
)
from discovery_craft import (
    inert_terminal_tag,
    insight_after_payoff,
    sidesteps_forced_choice,
    corrects_comic_premise,
)
from gold_shape import evaluate_gold_shape
from response_finalization import (
    build_response_plan,
    plan_runtime_instruction,
    is_deliverable_response,
    is_valid_terminal_response,
    normalize_terminal_response,
    finalize_response,
)

ENERGY_DRINK = """An energy drink is $2.50 a day.

That's $17.50 a week, $75 a month, and $900 a year.

If you quit drinking them for 10 years, you'll save $9,000.

That's still not enough for your dream car.

So just enjoy the energy drink."""

ENERGY_FAIL = (
    "The math works until you notice the $2.50 isn't really about the car. "
    "It's the daily bribe that keeps the version of you who still thinks the car is possible "
    "from checking out completely. 🥃"
)
ENERGY_INERT = "Fair. 🥃"
ENERGY_MICRO = "Retirement plan denied. Crack the can. 🥃"
ENERGY_MICRO_2 = "Financial literacy has gone too far. 🥃"
ENERGY_SILENCE = "🥃"

DATA_CENTER_GIRL = (
    "if your girl: \n"
    "- drinks a lot of water \n"
    "- causes drama \n"
    "- remembers everything \n"
    "that's not your girl, that's a data center"
)
DATA_CENTER_TAG = "That's a data center with better uptime than your last three relationships. 🥃"

BOWLING_ALAS = (
    "they should invent a woman who wants to go bowling and enjoy a bucket of beer but alas"
)

SANDLER = "Name an actor who immediately makes you NOT want to watch a movie"
VILLAIN = "name a villain who was 100% right"
VILLAIN_THOUGHTS = "/thoughts Name a villain who was 100% right"

SEX_GYM_MONEY = (
    "Dear Man, if you can choose any one for lifetime:\n\n"
    "Sex\n"
    "Gym\n"
    "Money\n\n"
    "Which one will you pick?"
)
SEX_GYM_FAIL = "I'd sidestep all three and choose freedom. 🥃"
SEX_GYM_PASS = "Money. 🥃"
SEX_GYM_TAG = "Money. Hard to flex loneliness. 🥃"

DROPPED_CARRY = (
    "I am so sick and tired of friends who can't handle alcohol. "
    "the other night they dropped me 3 times while carrying me to the car😭"
)
DROPPED_FAIL = (
    "Three drops and you're still blaming their tolerance instead of the fact "
    "that nobody left standing was sober enough to drive. 🥃"
)
DROPPED_PASS = "You need drinking buddies with forklift certification. 🥃"
DROPPED_PASS_2 = "Three drops is a personnel problem. 🥃"
DROPPED_PASS_3 = "Get friends with better upper-body strength. 🥃"
# Live 2026-08-20: Iggy continued the forklift world. Behavioral gold, not a generation rule.
IGGY_CONTINUE = (
    "Where will we park it, I'm sure will end up lifting people's cars when we drink"
)


def test_energy_drink_is_terminal_bit():
    assert classify_comic_bit_shape(ENERGY_DRINK) == "terminal"
    social = classify_social_mode(ENERGY_DRINK)
    assert social.mode == "comic"
    assert social.interaction_shape == "terminal_bit"
    assert social.terminal_bit is True
    assert social.depth_earned is False

    plan = build_response_plan(ENERGY_DRINK)
    assert plan.interaction_shape == "terminal_bit"
    assert plan.primary_capability == "Humor As Disruption"
    assert plan.mechanism_hint == "terminal_bit_micro_tag"
    assert plan.preferred_structure == "SNAP"
    assert plan.response_budget == "low"
    assert plan.comic_payoff_is_terminal is True
    assert plan.landing == "body_ends_response"
    assert plan.primary_capability != "Emotional State Recognition"

    guide = plan_runtime_instruction(plan).lower()
    assert "terminal bit" in guide
    assert "no new interpretation" in guide
    assert "fair. 🥃" in guide

    assert insight_after_payoff(ENERGY_DRINK, ENERGY_FAIL) is True
    assert inert_terminal_tag(ENERGY_DRINK, ENERGY_INERT) is True
    assert inert_terminal_tag(ENERGY_DRINK, ENERGY_MICRO) is False
    assert insight_after_payoff(ENERGY_DRINK, ENERGY_INERT) is False
    fails = evaluate_gold_shape(ENERGY_DRINK, ENERGY_FAIL, "SNAP")
    assert "insight_after_payoff" in fails
    inert_fails = evaluate_gold_shape(ENERGY_DRINK, ENERGY_INERT, "SNAP")
    assert "inert_terminal_tag" in inert_fails
    ok = evaluate_gold_shape(ENERGY_DRINK, ENERGY_MICRO, "SNAP")
    assert "inert_terminal_tag" not in ok
    assert "insight_after_payoff" not in ok


def test_terminal_bit_micro_tag_contract():
    plan = build_response_plan(ENERGY_DRINK)
    assert plan.interaction_shape == "terminal_bit"

    for micro in (ENERGY_MICRO, ENERGY_MICRO_2, "Ten years of discipline and still no Porsche. Drink up. 🥃"):
        assert is_valid_terminal_response(micro, plan) is True, micro
        assert is_deliverable_response(micro, plan) is True, micro
        assert inert_terminal_tag(ENERGY_DRINK, micro) is False, micro

    for inert in (ENERGY_INERT, "Exactly. 🥃", "Agreed. 🥃"):
        assert inert_terminal_tag(ENERGY_DRINK, inert) is True, inert
        normalized, collapsed = normalize_terminal_response(inert, plan, ENERGY_DRINK)
        assert collapsed is True
        assert normalized == "🥃"

    long_insight = (
        "Actually, the energy drink represents your inability to surrender hope. 🥃"
    )
    assert is_valid_terminal_response(long_insight, plan) is False
    normalized, collapsed = normalize_terminal_response(long_insight, plan, ENERGY_DRINK)
    assert collapsed is True
    assert normalized == "🥃"

    result = finalize_response(long_insight, ENERGY_DRINK, plan=plan)
    assert result.text.strip() == "🥃"
    assert is_deliverable_response(result.text, plan) is True

    result_good = finalize_response(ENERGY_MICRO, ENERGY_DRINK, plan=plan)
    assert ENERGY_MICRO.split("🥃")[0].strip() in result_good.text

    open_plan = build_response_plan("Why did Game of Thrones season 8 fail?")
    assert is_deliverable_response(ENERGY_INERT, open_plan) is False
    assert is_deliverable_response("k", open_plan) is False


def test_data_center_girl_is_taggable_not_terminal():
    assert classify_comic_bit_shape(DATA_CENTER_GIRL) == "taggable"
    social = classify_social_mode(DATA_CENTER_GIRL)
    assert social.interaction_shape == "taggable_bit"
    assert social.interaction_shape != "terminal_bit"

    plan = build_response_plan(DATA_CENTER_GIRL)
    assert plan.interaction_shape == "taggable_bit"
    assert plan.mechanism_hint == "taggable_bit_one_tag"
    assert plan.comic_payoff_is_terminal is False


def test_bowling_alas_stays_open_handoff():
    assert classify_comic_bit_shape(BOWLING_ALAS) == "open"
    social = classify_social_mode(BOWLING_ALAS)
    assert social.interaction_shape == "comic_handoff"
    assert social.interaction_shape != "terminal_bit"
    plan = build_response_plan(BOWLING_ALAS)
    assert plan.mechanism_hint == "comic_handoff_complete"


def test_sandler_stays_pick_one_snap():
    social = classify_social_mode(SANDLER)
    assert social.interaction_shape == "pick_one"
    assert social.participation is True
    assert social.pick_and_defend is False

    plan = build_response_plan(SANDLER, selected_command="/cinema")
    assert plan.interaction_shape == "pick_one"
    assert plan.intent == "answer"
    assert plan.preferred_structure == "SNAP"
    assert plan.response_budget == "low"
    assert plan.primary_capability in (None, "", "none")
    assert "PICK-ONE CONTRACT" in plan_runtime_instruction(plan)


def test_villain_routes_pick_and_defend():
    for msg in (VILLAIN, VILLAIN_THOUGHTS):
        social = classify_social_mode(msg)
        assert social.interaction_shape == "pick_and_defend", msg
        assert social.pick_and_defend is True
        assert social.participation is False
        assert "provocative_nomination" in social.signals

        plan = build_response_plan(msg, selected_command="/thoughts")
        assert plan.interaction_shape == "pick_and_defend"
        assert plan.preferred_structure == "KNIFE"
        assert plan.response_budget == "medium"
        assert plan.mechanism_hint == "pick_and_defend"
        assert plan.primary_capability == "Evidence / Contradiction Analysis"
        assert plan.engagement_energy is True
        guide = plan_runtime_instruction(plan)
        assert "PICK-AND-DEFEND CONTRACT" in guide
        assert "PICK-ONE CONTRACT" not in guide
        assert "ENGAGEMENT ENERGY" in guide

    assert classify_social_mode(SANDLER).interaction_shape == "pick_one"


def test_sex_gym_money_is_forced_choice():
    from capability_detection import classify_participation_shape, detect_forced_choice

    assert detect_forced_choice(SEX_GYM_MONEY) is True
    assert classify_participation_shape(SEX_GYM_MONEY) == "forced_choice"
    social = classify_social_mode(SEX_GYM_MONEY)
    assert social.interaction_shape == "forced_choice"
    assert social.participation is True
    assert social.forced_choice is True
    assert "play_the_game" in social.signals

    plan = build_response_plan(SEX_GYM_MONEY)
    assert plan.interaction_shape == "forced_choice"
    assert plan.intent == "answer"
    assert plan.preferred_structure == "SNAP"
    assert plan.response_budget == "low"
    assert plan.mechanism_hint == "forced_choice_play_game"
    guide = plan_runtime_instruction(plan)
    assert "PLAY THE GAME CONTRACT" in guide
    assert "PICK-ONE CONTRACT" not in guide

    assert sidesteps_forced_choice(SEX_GYM_MONEY, SEX_GYM_FAIL) is True
    assert sidesteps_forced_choice(SEX_GYM_MONEY, SEX_GYM_PASS) is False
    assert sidesteps_forced_choice(SEX_GYM_MONEY, SEX_GYM_TAG) is False
    fails = evaluate_gold_shape(SEX_GYM_MONEY, SEX_GYM_FAIL, "SNAP")
    assert "sidestep_forced_choice" in fails
    ok = evaluate_gold_shape(SEX_GYM_MONEY, SEX_GYM_PASS, "SNAP")
    assert "sidestep_forced_choice" not in ok


def test_dropped_three_times_inherits_comic_premise():
    """Blame inversion is a finished bit. Inherit it; don't lecture driving."""
    assert inverted_comic_premise(DROPPED_CARRY) is True
    assert inverted_comic_premise(
        "I am so sick and tired of friends who can't handle alcohol."
    ) is False
    assert classify_comic_bit_shape(DROPPED_CARRY) == "terminal"
    comic = detect_comic_premise(DROPPED_CARRY)
    assert comic.active
    assert comic.never_cure
    assert "inverted_premise" in comic.signals

    social = classify_social_mode(DROPPED_CARRY)
    assert social.mode == "comic"
    assert social.interaction_shape == "terminal_bit"
    assert social.terminal_bit is True
    assert social.depth_earned is False

    plan = build_response_plan(DROPPED_CARRY)
    assert plan.comic_premise is True
    assert plan.never_cure_premise is True
    assert plan.interaction_shape == "terminal_bit"
    assert plan.primary_capability == "Humor As Disruption"
    assert plan.mechanism_hint == "terminal_bit_micro_tag"
    assert plan.preferred_structure == "SNAP"
    assert plan.response_budget == "low"
    assert plan.comic_payoff_is_terminal is True
    assert plan.landing == "body_ends_response"

    guide = plan_runtime_instruction(plan).lower()
    assert "comic premise must be inherited" in guide
    assert "forklift" in guide
    assert "blaming their tolerance" in guide

    assert corrects_comic_premise(DROPPED_CARRY, DROPPED_FAIL) is True
    assert insight_after_payoff(DROPPED_CARRY, DROPPED_FAIL) is True
    for tag in (DROPPED_PASS, DROPPED_PASS_2, DROPPED_PASS_3):
        assert corrects_comic_premise(DROPPED_CARRY, tag) is False, tag
        assert insight_after_payoff(DROPPED_CARRY, tag) is False, tag
        assert inert_terminal_tag(DROPPED_CARRY, tag) is False, tag
        assert is_valid_terminal_response(tag, plan) is True, tag

    fails = evaluate_gold_shape(DROPPED_CARRY, DROPPED_FAIL, "SNAP")
    assert "premise_correction" in fails
    ok = evaluate_gold_shape(DROPPED_CARRY, DROPPED_PASS, "SNAP")
    assert "premise_correction" not in ok
    assert "insight_after_payoff" not in ok
    assert "inert_terminal_tag" not in ok

    result = finalize_response(DROPPED_FAIL, DROPPED_CARRY, plan=plan)
    assert result.text.strip() == "🥃"
    result_good = finalize_response(DROPPED_PASS, DROPPED_CARRY, plan=plan)
    assert "forklift" in result_good.text.lower()


def test_iggy_forklift_author_continued_the_world():
    """Live 2026-08-20 behavioral gold.

    Affordance is evidence the architecture worked — inherit, one beat, exit.
    Not a generation mandate to ask a question or manufacture a hook.
    """
    plan = build_response_plan(DROPPED_CARRY)
    assert plan.contribution_budget == "micro"
    assert "?" not in DROPPED_PASS
    assert corrects_comic_premise(DROPPED_CARRY, DROPPED_PASS) is False
    # Author stayed inside the inherited world, not a defense of the drop.
    assert "park" in IGGY_CONTINUE.lower()
    assert "car" in IGGY_CONTINUE.lower()
    assert "sober" not in IGGY_CONTINUE.lower()
    assert "tolerance" not in IGGY_CONTINUE.lower()
    assert "forklift" in DROPPED_PASS.lower()

