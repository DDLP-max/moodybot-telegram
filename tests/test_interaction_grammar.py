# -*- coding: utf-8 -*-
"""Cross-case regression: open vs taggable vs terminal comic bits."""
from __future__ import annotations

from capability_detection import classify_comic_bit_shape, classify_social_mode, detect_comic_premise
from discovery_craft import insight_after_payoff, sidesteps_forced_choice
from gold_shape import evaluate_gold_shape
from response_finalization import build_response_plan, plan_runtime_instruction, is_deliverable_response, is_valid_terminal_ack

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
ENERGY_PASS = "Fair. 🥃"
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
    assert plan.mechanism_hint == "terminal_bit_leave_payoff"
    assert plan.preferred_structure == "SNAP"
    assert plan.response_budget == "low"
    assert plan.comic_payoff_is_terminal is True
    assert plan.landing == "silence"
    assert plan.primary_capability != "Emotional State Recognition"

    guide = plan_runtime_instruction(plan).lower()
    assert "terminal bit" in guide
    assert "insight is not additive" in guide

    assert insight_after_payoff(ENERGY_DRINK, ENERGY_FAIL) is True
    assert insight_after_payoff(ENERGY_DRINK, ENERGY_PASS) is False
    assert insight_after_payoff(ENERGY_DRINK, ENERGY_SILENCE) is False
    fails = evaluate_gold_shape(ENERGY_DRINK, ENERGY_FAIL, "SNAP")
    assert "insight_after_payoff" in fails
    ok = evaluate_gold_shape(ENERGY_DRINK, ENERGY_PASS, "SNAP")
    assert "insight_after_payoff" not in ok


def test_terminal_bit_whiskey_ack_passes_delivery_gate():
    plan = build_response_plan(ENERGY_DRINK)
    assert plan.interaction_shape == "terminal_bit"
    assert plan.landing == "silence"
    assert is_valid_terminal_ack(ENERGY_SILENCE, plan) is True
    assert is_deliverable_response(ENERGY_SILENCE, plan) is True

    open_plan = build_response_plan("Why did Game of Thrones season 8 fail?")
    assert is_valid_terminal_ack(ENERGY_SILENCE, open_plan) is False
    assert is_deliverable_response(ENERGY_SILENCE, open_plan) is False
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
        guide = plan_runtime_instruction(plan)
        assert "PICK-AND-DEFEND CONTRACT" in guide
        assert "PICK-ONE CONTRACT" not in guide

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
