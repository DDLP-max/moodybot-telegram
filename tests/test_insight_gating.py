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

from capability_detection import classify_social_mode, detect_comic_premise, extract_premise_guards
from discovery_craft import (
    parroting,
    psychologizing,
    recognition_advances,
    restates_runway,
    starts_where_user_stopped,
    unsupported_depth,
    overperformance,
    rhetorical_explained,
    missed_comic_handoff,
    rejects_absurd_premise,
    reverses_premise_guard,
    uninvited_corrective_analysis,
    corrects_comic_premise,
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

NAME_ONE_ACTOR = (
    "Name an actor who immediately makes you NOT want to watch a movie"
)
NAME_ONE_FAIL = (
    "The moment Adam Sandler appears, the frame forgets its own heartbeat. "
    "Light that once carried myth now lingers on a face that refuses to vanish, "
    "turning every scene into a reminder that someone is still watching from the outside. "
    "What was meant to swallow you whole suddenly remembers it's only a movie, "
    "and the spell leaks out through the cracks in his voice."
)
NAME_ONE_PASS = "Adam Sandler."
NAME_ONE_PASS_BEAT = (
    "Adam Sandler. I see his face and already know how the next two hours smell."
)

SOPRANOS = (
    "i started watching the sopranos and wow how come no one ever told me to watch this"
)
SOPRANOS_PASS = (
    "The Sopranos doesn't announce itself. It just sits there like a loaded gun "
    "on the kitchen table until you finally pick it up."
)
SOPRANOS_FAIL = (
    SOPRANOS_PASS
    + " That's why nobody told you, the ones who know are too busy living inside it "
    "to bother selling it."
)

HAND_DEALT = (
    "I wish I didn't like smoking and drinking as much as I obviously do. "
    "Alas, we play the hand we're dealt."
)
HAND_FAIL = (
    "You don't wish you liked it less. You wish the part of you that feels "
    "guilty would stop keeping score."
)
HAND_PASS = "Somehow the hand keeps getting dealt at the liquor store."
HAND_PASS_BEAT = "Brutal hand. Weird how you have to keep buying it."

HVAC_OCEAN = "The industrial HVAC hum in the data center is the ocean."
HVAC_FAIL = (
    "The hum isn't the ocean. It's the opposite. "
    "The data center just keeps running, no matter what you're feeling."
)
HVAC_PASS = "Oceanfront living for people who think the ocean needs better uptime."

DROPPED_CARRY = (
    "I am so sick and tired of friends who can't handle alcohol. "
    "the other night they dropped me 3 times while carrying me to the car😭"
)
DROPPED_FAIL = (
    "Three drops and you're still blaming their tolerance instead of the fact "
    "that nobody left standing was sober enough to drive. 🥃"
)
DROPPED_PASS = "You need drinking buddies with forklift certification. 🥃"

BOWLING_ALAS = (
    "they should invent a woman who wants to go bowling and enjoy a bucket of beer but alas"
)
BOWLING_FAIL = (
    "That's like saying the ideal woman is the one who still thinks Friday night "
    "doesn't need a second act."
)
BOWLING_PASS = "...we apparently spent all the R&D money on AI girlfriends."
BOWLING_PASS_BEAT = "They mapped the human genome before solving this."


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
    for src in (FLOCK, WIFE_STOCKS, WHORE_NAME, HATE_PEOPLE, HAND_DEALT, HVAC_OCEAN, BOWLING_ALAS):
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
    assert social.participation is False
    assert social.resolution == "reason"


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


def test_hand_dealt_is_comic_not_guilt_diagnosis():
    """Vice vocabulary is not addiction intake. The joke is fake fate."""
    comic = detect_comic_premise(HAND_DEALT)
    assert comic.active is True
    assert "vice_as_fate" in comic.signals
    social = classify_social_mode(HAND_DEALT)
    assert social.mode == "comic"
    plan = build_response_plan(HAND_DEALT)
    assert plan.social_mode == "comic"
    assert plan.comic_premise is True
    assert plan.primary_capability == "Humor As Disruption"
    assert plan.never_cure_premise is True

    # Completed "Alas, we play…" is a punchline, not an open handoff slot
    assert classify_social_mode(HAND_DEALT).interaction_shape != "comic_handoff"

    # Without the fate punchline, a bare wish is not automatically a bit
    bare = "I wish I didn't like smoking as much as I obviously do."
    assert detect_comic_premise(bare).active is False

    assert psychologizing(HAND_DEALT, HAND_FAIL, comic=True) is True
    assert unsupported_depth(HAND_DEALT, HAND_FAIL, comic=True) is True
    assert psychologizing(HAND_DEALT, HAND_PASS, comic=True) is False
    assert psychologizing(HAND_DEALT, HAND_PASS_BEAT, comic=True) is False
    assert unsupported_depth(HAND_DEALT, HAND_PASS, comic=True) is False

    fails = evaluate_gold_shape(HAND_DEALT, HAND_FAIL, "SNAP")
    assert "psychologizing" in fails
    ok = evaluate_gold_shape(HAND_DEALT, HAND_PASS, "SNAP")
    assert "psychologizing" not in ok

    insp = _inspect(HAND_DEALT, HAND_FAIL)
    assert _checks(insp)["Psychologizing"]["status"] == "fail"
    insp_ok = _inspect(HAND_DEALT, HAND_PASS)
    assert _checks(insp_ok)["Psychologizing"]["status"] == "pass"

    guide = plan_closer_instruction(plan).lower()
    assert "hand we're dealt" in guide or "liquor store" in guide
    assert "guilty" in guide


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
    assert "overperformance" in blob
    assert "natural resolution" in blob
    assert "interaction shape" in blob
    assert "what they're doing wins" in blob
    assert "rhetorical" in blob
    assert "inherit" in blob
    assert "comic premise must be inherited" in blob
    assert "take a side" in blob
    assert "comic handoff" in blob
    assert "object before author" in blob
    assert "receipts arrive" in blob
    assert "contribution budget" in blob
    assert "interest always finds time" in blob
    assert "rewrite the story" in blob

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


def test_name_one_actor_does_not_become_film_criticism():
    """Participation question: name one. Not Cinema Paradiso.

    Trace assertions — output tests can pass while the router is still wrong.
    """
    from capability_detection import select_tone_command
    from structure_prompts import STRUCTURE_PROMPTS

    social = classify_social_mode(NAME_ONE_ACTOR)
    assert social.mode == "direct_participation"
    assert social.participation is True
    assert social.interaction_shape == "pick_one"
    assert social.resolution == "name"
    assert social.depth_earned is False
    assert social.blocks_topical_auto_route is True
    assert social.confidence >= 0.9

    # Smoking gun: actor + movie would have auto-routed /cinema
    assert "actor" in NAME_ONE_ACTOR.lower() and "movie" in NAME_ONE_ACTOR.lower()
    cmd, source = select_tone_command(
        NAME_ONE_ACTOR, topical_auto_command="/cinema"
    )
    assert cmd != "/cinema"
    assert cmd == "/thoughts"
    assert source == "social-first"
    assert "/cinema" in STRUCTURE_PROMPTS

    plan = build_response_plan(NAME_ONE_ACTOR, selected_command="/cinema")
    assert plan.social_mode == "direct_participation"
    assert plan.interaction_shape == "pick_one"
    assert plan.intent == "answer"
    assert plan.primary_capability in (None, "", "none")
    assert plan.primary_capability != "Everyday Preference Analysis"
    assert plan.preferred_structure == "SNAP"
    assert plan.response_budget == "low"
    assert (plan.routed_structure or "").upper().startswith("SNAP") or plan.preferred_structure == "SNAP"
    assert plan.selected_command != "/cinema"
    assert plan.selected_command == "/thoughts"
    assert plan.tone_source == "social-first"
    assert plan.landing == "body_ends_response"
    assert plan.claim_domain != "taste_preference"

    # Even if handle_message mistakenly passed /cinema, do not explore
    assert plan.intent != "explore"

    assert overperformance(NAME_ONE_ACTOR, NAME_ONE_FAIL) is True
    assert overperformance(NAME_ONE_ACTOR, NAME_ONE_PASS) is False
    assert overperformance(NAME_ONE_ACTOR, NAME_ONE_PASS_BEAT) is False

    fails = evaluate_gold_shape(NAME_ONE_ACTOR, NAME_ONE_FAIL, "SNAP")
    assert "overperformance" in fails
    ok_fails = evaluate_gold_shape(NAME_ONE_ACTOR, NAME_ONE_PASS, "SNAP")
    assert "overperformance" not in ok_fails
    beat_fails = evaluate_gold_shape(NAME_ONE_ACTOR, NAME_ONE_PASS_BEAT, "SNAP")
    assert "overperformance" not in beat_fails

    insp = _inspect(NAME_ONE_ACTOR, NAME_ONE_FAIL)
    assert _checks(insp)["Overperformance"]["status"] == "fail"
    insp_ok = _inspect(NAME_ONE_ACTOR, NAME_ONE_PASS)
    assert _checks(insp_ok)["Overperformance"]["status"] == "pass"
    insp_beat = _inspect(NAME_ONE_ACTOR, NAME_ONE_PASS_BEAT)
    assert _checks(insp_beat)["Overperformance"]["status"] == "pass"

    guide = plan_closer_instruction(plan)
    guide_l = guide.lower()
    assert "pick-one" in guide_l or "direct participation" in guide_l
    assert "overperformance" in guide_l
    assert "adam sandler" in guide_l
    assert "Capability (Intelligence): none" in guide
    assert "Capability (Intelligence): Everyday Preference Analysis" not in guide
    assert "CAPABILITY: Everyday Preference Analysis" not in guide
    assert "Question (invisible step" not in guide
    assert "frame forgets" in guide_l or "cinema paradiso" in guide_l


def test_greatest_role_may_still_be_cinema():
    """Negative control: cinema is the object, not a costume. /cinema may participate."""
    from capability_detection import select_tone_command

    q = "What is De Niro's greatest role?"
    social = classify_social_mode(q)
    assert social.blocks_topical_auto_route is False
    cmd, source = select_tone_command(q, topical_auto_command="/cinema")
    assert cmd == "/cinema"
    assert source == "auto-route"


def test_sopranos_awe_allows_cinema_but_not_invented_causality():
    """Cinema is the object — /cinema may participate. Rhetorical how-come is not a why.

    Trace: interaction_shape=awe, SNAP, not explore. Structure prompt must not be
    the four-beat cinema essay.
    """
    from capability_detection import select_tone_command
    from structure_prompts import CINEMA_SNAP_PROMPT, STRUCTURE_PROMPTS, structure_prompt_for

    social = classify_social_mode(SOPRANOS)
    assert social.interaction_shape == "awe"
    assert social.rhetorical_question is True
    assert social.participation is False
    assert social.blocks_topical_auto_route is False
    assert social.resolution != "explain"
    assert social.depth_earned is False

    cmd, source = select_tone_command(SOPRANOS, topical_auto_command="/cinema")
    assert cmd == "/cinema"
    assert source == "auto-route"

    cinema_prompt = structure_prompt_for("/cinema", social=social)
    assert cinema_prompt == CINEMA_SNAP_PROMPT
    assert "Final poetic rupture" not in (cinema_prompt or "")
    assert "Final poetic rupture" in STRUCTURE_PROMPTS["/cinema"]

    plan = build_response_plan(SOPRANOS, selected_command="/cinema")
    assert plan.interaction_shape == "awe"
    assert plan.intent != "explore"
    assert plan.preferred_structure == "SNAP"
    assert plan.response_budget == "low"
    assert plan.selected_command == "/cinema"
    assert plan.primary_capability in (None, "", "none")
    assert plan.intent != "explore"

    assert rhetorical_explained(SOPRANOS, SOPRANOS_FAIL) is True
    assert rhetorical_explained(SOPRANOS, SOPRANOS_PASS) is False
    fails = evaluate_gold_shape(SOPRANOS, SOPRANOS_FAIL, "SNAP")
    assert "rhetorical_explained" in fails
    ok_fails = evaluate_gold_shape(SOPRANOS, SOPRANOS_PASS, "SNAP")
    assert "rhetorical_explained" not in ok_fails

    insp = _inspect(SOPRANOS, SOPRANOS_FAIL)
    assert _checks(insp)["Rhetorical obligation"]["status"] == "fail"
    insp_ok = _inspect(SOPRANOS, SOPRANOS_PASS)
    assert _checks(insp_ok)["Rhetorical obligation"]["status"] == "pass"

    guide = plan_closer_instruction(plan).lower()
    assert "rhetorical" in guide
    assert "loaded gun" in guide
    assert "how come" in guide
    assert "question (invisible step" not in guide


def test_got_season_8_is_a_real_why_not_awe():
    q = "Why did Game of Thrones season 8 fail?"
    social = classify_social_mode(q)
    assert social.interaction_shape != "awe"
    assert social.rhetorical_question is False
    from structure_prompts import STRUCTURE_PROMPTS, structure_prompt_for

    assert structure_prompt_for("/cinema", social=social) == STRUCTURE_PROMPTS["/cinema"]


def test_hvac_ocean_inherits_the_absurd_premise():
    """Don't correct HVAC = ocean. Inherit it. Rejection → unsupported depth."""
    comic = detect_comic_premise(HVAC_OCEAN)
    assert comic.active is True
    assert "absurd_equivalence" in comic.signals
    social = classify_social_mode(HVAC_OCEAN)
    assert social.mode == "comic"
    assert social.interaction_shape != "comic_handoff"
    plan = build_response_plan(HVAC_OCEAN)
    assert plan.primary_capability == "Humor As Disruption"

    assert rejects_absurd_premise(HVAC_OCEAN, HVAC_FAIL) is True
    assert rejects_absurd_premise(HVAC_OCEAN, HVAC_PASS) is False
    assert unsupported_depth(HVAC_OCEAN, HVAC_FAIL, comic=True) is True
    assert unsupported_depth(HVAC_OCEAN, HVAC_PASS, comic=True) is False
    fails = evaluate_gold_shape(HVAC_OCEAN, HVAC_FAIL, "SNAP")
    assert "unsupported_depth" in fails
    assert "premise_correction" in fails
    ok = evaluate_gold_shape(HVAC_OCEAN, HVAC_PASS, "SNAP")
    assert "unsupported_depth" not in ok
    insp = _inspect(HVAC_OCEAN, HVAC_FAIL)
    assert _checks(insp)["Unsupported depth"]["status"] == "fail"
    insp_ok = _inspect(HVAC_OCEAN, HVAC_PASS)
    assert _checks(insp_ok)["Unsupported depth"]["status"] == "pass"

    guide = plan_closer_instruction(plan).lower()
    assert "inherit" in guide
    assert "uptime" in guide or "isn't the ocean" in guide
    assert corrects_comic_premise(HVAC_OCEAN, HVAC_FAIL) is True
    assert corrects_comic_premise(HVAC_OCEAN, HVAC_PASS) is False


def test_dropped_carry_inherits_inverted_premise():
    """Friends can't handle alcohol because they dropped the drunk speaker. Inherit it."""
    comic = detect_comic_premise(DROPPED_CARRY)
    assert comic.active is True
    assert "inverted_premise" in comic.signals
    social = classify_social_mode(DROPPED_CARRY)
    assert social.mode == "comic"
    assert social.interaction_shape == "terminal_bit"
    plan = build_response_plan(DROPPED_CARRY)
    assert plan.never_cure_premise is True
    assert plan.mechanism_hint == "terminal_bit_micro_tag"

    assert corrects_comic_premise(DROPPED_CARRY, DROPPED_FAIL) is True
    assert corrects_comic_premise(DROPPED_CARRY, DROPPED_PASS) is False
    assert rejects_absurd_premise(DROPPED_CARRY, DROPPED_FAIL) is False
    fails = evaluate_gold_shape(DROPPED_CARRY, DROPPED_FAIL, "SNAP")
    assert "premise_correction" in fails
    ok = evaluate_gold_shape(DROPPED_CARRY, DROPPED_PASS, "SNAP")
    assert "premise_correction" not in ok

    insp = _inspect(DROPPED_CARRY, DROPPED_FAIL)
    assert _checks(insp)["Comic premise inherited"]["status"] == "fail"
    insp_ok = _inspect(DROPPED_CARRY, DROPPED_PASS)
    assert _checks(insp_ok)["Comic premise inherited"]["status"] == "pass"

    guide = plan_closer_instruction(plan).lower()
    assert "comic premise must be inherited" in guide
    assert "forklift" in guide
    assert "blaming their tolerance" in guide


def test_bowling_alas_is_comic_handoff():
    """but alas… is an unfinished slot. Complete the bit. Don't start a new observation."""
    comic = detect_comic_premise(BOWLING_ALAS)
    assert comic.active is True
    social = classify_social_mode(BOWLING_ALAS)
    assert social.mode == "comic"
    assert social.interaction_shape == "comic_handoff"
    assert social.comic_handoff is True
    plan = build_response_plan(BOWLING_ALAS)
    assert plan.interaction_shape == "comic_handoff"
    assert plan.primary_capability == "Humor As Disruption"
    assert plan.mechanism_hint == "comic_handoff_complete"
    assert plan.preferred_structure == "SNAP"

    assert missed_comic_handoff(BOWLING_ALAS, BOWLING_FAIL) is True
    assert missed_comic_handoff(BOWLING_ALAS, BOWLING_PASS) is False
    assert missed_comic_handoff(BOWLING_ALAS, BOWLING_PASS_BEAT) is False
    fails = evaluate_gold_shape(BOWLING_ALAS, BOWLING_FAIL, "SNAP")
    assert "missed_handoff" in fails
    ok = evaluate_gold_shape(BOWLING_ALAS, BOWLING_PASS, "SNAP")
    assert "missed_handoff" not in ok

    insp = _inspect(BOWLING_ALAS, BOWLING_FAIL)
    assert _checks(insp)["Comic handoff"]["status"] == "fail"
    insp_ok = _inspect(BOWLING_ALAS, BOWLING_PASS)
    assert _checks(insp_ok)["Comic handoff"]["status"] == "pass"

    guide = plan_closer_instruction(plan).lower()
    assert "handoff" in guide
    assert "alas" in guide
    assert "that's like saying" in guide


DATING_MEN = (
    "The number of MEN done with dating right now is insane.\n\n"
    "Not bitter. Not lonely.\n\n"
    "They just realized.. it's not worth it."
)
DATING_FAIL = (
    "The men stepping away aren't tallying wins and losses. They're just refusing to keep "
    "offering the last thing that still feels like theirs, the right to be let down without "
    "having to explain why it landed so hard. It starts as a clean break from the whole game. "
    "Then the quiet starts charging interest. 🥃"
)
DATING_PASS = (
    "Maybe that's the part people keep missing. You don't have to hate the restaurant to decide "
    "the menu isn't worth the prices anymore. At some point opting out stops being a cry for "
    "help and becomes consumer behavior. 🥃"
)


def test_dating_men_respects_premise_guards():
    """Not bitter. Not lonely. → don't smuggle wound/loneliness back in."""
    guards = extract_premise_guards(DATING_MEN)
    assert "bitter" in guards
    assert "lonely" in guards
    social = classify_social_mode(DATING_MEN)
    assert social.premise_guards
    assert "premise_guards" in social.signals
    assert social.mode == "observation"
    plan = build_response_plan(DATING_MEN)
    assert plan.premise_guards
    assert plan.mechanism_hint == "premise_guard_inherit"

    assert reverses_premise_guard(DATING_MEN, DATING_FAIL) is True
    assert reverses_premise_guard(DATING_MEN, DATING_PASS) is False
    fails = evaluate_gold_shape(DATING_MEN, DATING_FAIL, "SNAP")
    assert "premise_reversal" in fails
    ok = evaluate_gold_shape(DATING_MEN, DATING_PASS, "SNAP")
    assert "premise_reversal" not in ok

    insp = _inspect(DATING_MEN, DATING_FAIL)
    assert _checks(insp)["Premise guard"]["status"] == "fail"
    insp_ok = _inspect(DATING_MEN, DATING_PASS)
    assert _checks(insp_ok)["Premise guard"]["status"] == "pass"

    guide = plan_closer_instruction(plan).lower()
    assert "premise guard" in guide or "don't secretly reverse" in guide
    assert "bitter" in guide or "lonely" in guide


BATSHIT_GENERALIZATION = (
    "I've come to the conclusion that most women are batshit crazy."
)
BATSHIT_FAIL = (
    "The payoff in calling most women batshit crazy is that it turns every bad outcome "
    "into evidence and every good one into an exception you don't have to explain. 🥃"
)
BATSHIT_PASS_OVERTIME = (
    "Most is doing enough work in that sentence to qualify for overtime. 🥃"
)
BATSHIT_PASS_STUDY = (
    "I like that you're presenting this as the sober conclusion of a longitudinal study. 🥃"
)


def test_batshit_generalization_social_before_correction():
    """Provocative throwaway → tease framing, not Bench-mode motive prosecution."""
    social = classify_social_mode(BATSHIT_GENERALIZATION)
    assert social.mode == "provocative_generalization"
    assert "provocative_generalization" in social.signals
    plan = build_response_plan(BATSHIT_GENERALIZATION)
    assert plan.social_mode == "provocative_generalization"
    assert plan.primary_capability == "Humor As Disruption"
    assert plan.mechanism_hint == "social_banter_not_bench"
    assert plan.preferred_structure == "SNAP"

    assert uninvited_corrective_analysis(BATSHIT_GENERALIZATION, BATSHIT_FAIL) is True
    assert uninvited_corrective_analysis(BATSHIT_GENERALIZATION, BATSHIT_PASS_OVERTIME) is False
    assert uninvited_corrective_analysis(BATSHIT_GENERALIZATION, BATSHIT_PASS_STUDY) is False
    fails = evaluate_gold_shape(BATSHIT_GENERALIZATION, BATSHIT_FAIL, "SNAP")
    assert "corrective_analysis" in fails
    ok = evaluate_gold_shape(BATSHIT_GENERALIZATION, BATSHIT_PASS_STUDY, "SNAP")
    assert "corrective_analysis" not in ok

    insp = _inspect(BATSHIT_GENERALIZATION, BATSHIT_FAIL)
    assert _checks(insp)["Social before correction"]["status"] == "fail"
    insp_ok = _inspect(BATSHIT_GENERALIZATION, BATSHIT_PASS_OVERTIME)
    assert _checks(insp_ok)["Social before correction"]["status"] == "pass"

    guide = plan_closer_instruction(plan).lower()
    assert "social handling" in guide or "epistemic correction" in guide
    assert "payoff in calling" in guide


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
    test_hand_dealt_is_comic_not_guilt_diagnosis()
    test_axel_psychologizing_complete_take()
    test_whore_name_unsupported_depth()
    test_courtship_pair()
    test_condom_transformation_not_flagged()
    test_guidance_names_the_gates()
    test_matt_comic_still_routes()
    test_name_one_actor_does_not_become_film_criticism()
    test_greatest_role_may_still_be_cinema()
    test_sopranos_awe_allows_cinema_but_not_invented_causality()
    test_got_season_8_is_a_real_why_not_awe()
    test_hvac_ocean_inherits_the_absurd_premise()
    test_dropped_carry_inherits_inverted_premise()
    test_bowling_alas_is_comic_handoff()
    test_dating_men_respects_premise_guards()
    test_batshit_generalization_social_before_correction()
    print("ok")
