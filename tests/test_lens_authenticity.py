# -*- coding: utf-8 -*-
"""Lens authenticity regression — ways of seeing, not style themes.

For each prompt ask:
1) Is the selected lens plausible?
2) Does guidance encode that lens's distinctive first question?
3) Could this exact answer have been written by another lens? (must be no)
4) Lens persistence: finalize/Gold cannot change the routed lens

If lenses converge, answers become themes with different labels.
The goal isn't stylistic mimicry — each lens notices something others wouldn't first.
"""

from response_finalization import (
    LENS_CAPABILITY_FAMILIES,
    LENS_INTERNAL_QUESTIONS,
    LENS_PERSISTENCE_INVARIANT,
    build_response_plan,
    finalize_response,
    lens_capability_family,
    lens_internal_question,
    lens_voice_guidance,
    plan_closer_instruction,
)

# Generic phrasing any lens could write vs distinctive noticing for one lens.
# Assertion: "Could this exact answer have been written by another lens?"
DISTINCTIVE_NOTICING = {
    "Bourdain": {
        "generic": "People mistake consistency for quality.",
        "distinctive": "You already know exactly what it's going to taste like.",
    },
    "Munger": {
        "generic": "Incentives matter.",
        "distinctive": "Show me where the money changes direction.",
    },
    "CIA": {
        "generic": "You're missing information.",
        "distinctive": "You have one fact and three assumptions.",
    },
    "Hank Moody": {
        "generic": "Breakups are hard.",
        "distinctive": (
            "Sometimes the loneliest part of a relationship is having someone beside you."
        ),
    },
}

# (prompt, expected_lens, distinctive_fragment_in_guidance)
AUTHENTICITY_CASES = [
    (
        "McDonald's is easily the best place for burgers and fries.",
        "Bourdain",
        "lived this notice",
    ),
    (
        "Airport coffee is the pinnacle of espresso.",
        "Bourdain",
        "observation over diagnosis",
    ),
    (
        "Should I buy a Ferrari to impress clients?",
        "Munger",
        "what's the incentive",
    ),
    (
        "The promotion doubles my hours — salary tradeoff looks ugly.",
        "Munger",
        "opportunity cost",
    ),
    (
        "The affidavit contradicts her earlier statement.",
        "CIA",
        "what do we actually know",
    ),
    (
        "My boss suddenly became distant after the meeting.",
        "CIA",
        "evidence vs inference",
    ),
    (
        "I'm happier after my divorce.",
        "Hank Moody",
        "human truth nobody wants to admit",
    ),
    (
        "My friend only texts when she needs a ride.",
        "Hank Moody",
        "emotional contradiction",
    ),
    (
        "Feminists hate when a woman genuinely appreciates her man.",
        "Pattern Recognition",
        "what pattern repeats",
    ),
    (
        "I feel overwhelmed and my boundary keeps getting ignored.",
        "Emotional Intelligence",
        "without a sweeping group claim",
    ),
    (
        "If the girl or guy you're talking to isn't 100% obsessed with you, move on. "
        "With the right person there's no guessing games. When someone is really into you, you'll know.",
        "Emotional Intelligence",
        "without a sweeping group claim",
    ),
]


def test_core_lenses_have_unique_internal_questions():
    core = [
        "Bourdain",
        "Munger",
        "CIA",
        "Hank Moody",
        "Pattern Recognition",
        "Emotional Intelligence",
    ]
    questions = [lens_internal_question(name) for name in core]
    assert all(questions), questions
    assert len(set(questions)) == len(core), questions
    # Sanity: questions are short and specific
    for q in questions:
        assert q.endswith("?")
        assert len(q.split()) <= 12


def test_lens_guidance_is_not_interchangeable():
    """If you can swap two lens guides and not notice, they've converged."""
    guides = {
        name: lens_voice_guidance(name).lower()
        for name in (
            "Bourdain",
            "Munger",
            "CIA",
            "Hank Moody",
            "Pattern Recognition",
            "Emotional Intelligence",
        )
    }
    # Pairwise: each guide must contain its own question and not another's primary tell
    tells = {
        "Bourdain": ("lived this notice", "taste like"),
        "Munger": ("what's the incentive", "money changes direction"),
        "CIA": ("what do we actually know", "one fact and three assumptions"),
        "Hank Moody": ("human truth nobody wants to admit", "loneliest"),
        "Pattern Recognition": ("what pattern repeats", "same mechanism every time"),
        "Emotional Intelligence": (
            "without a sweeping group claim",
            "people only use threats they believe would work on themselves",
        ),
    }
    for name, (must_a, must_b) in tells.items():
        g = guides[name]
        assert must_a in g, name
        assert must_b in g, name
        for other, other_g in guides.items():
            if other == name:
                continue
            # Own primary question should not appear as the ask-first line of another
            own_q = lens_internal_question(name).lower()
            # Other guides may mention failures of this lens rarely — require question uniqueness
            assert own_q not in other_g or name == other


def test_authenticity_cases_select_plausible_lens():
    for prompt, expected_lens, fragment in AUTHENTICITY_CASES:
        plan = build_response_plan(prompt)
        assert plan.lens == expected_lens, (prompt, plan.lens, expected_lens)
        guidance = plan_closer_instruction(plan).lower()
        assert fragment in guidance, (prompt, fragment)
        q = lens_internal_question(expected_lens).lower()
        assert q in guidance, (prompt, q)


def test_munger_ferrari_not_status_psychology():
    plan = build_response_plan("Should I buy a Ferrari to impress clients?")
    assert plan.lens == "Munger"
    g = plan_closer_instruction(plan).lower()
    assert "incentive" in g
    assert "status signalling often reflects insecurity" in g  # as FAIL example
    assert "investment" in g and "expense" in g


def test_cia_boss_distant_respects_uncertainty():
    plan = build_response_plan("My boss suddenly became distant after the meeting.")
    # May route CIA via court keywords absent — boss distant is general/Hank unless we add cue.
    # Force authenticity of CIA guidance itself; routing for workplace mystery → prefer CIA when
    # evidence/uncertainty language is the job. If routed elsewhere, still check CIA guide.
    cia = lens_voice_guidance("CIA").lower()
    assert "planning to fire you" in cia
    assert "one data point" in cia
    assert "uncertainty" in cia or "what do we actually know" in cia


def test_hank_divorce_not_profanity_costume():
    plan = build_response_plan("I'm happier after my divorce.")
    assert plan.lens == "Hank Moody"
    g = plan_closer_instruction(plan).lower()
    assert "human truth" in g
    assert "swearing" in g or "profane" in g
    assert "loneliest" in g


def test_food_never_gets_pattern_recognition_lens():
    plan = build_response_plan(
        "McDonald's is easily the best place for burgers and fries."
    )
    assert plan.lens == "Bourdain"
    assert plan.lens != "Pattern Recognition"


def test_lens_question_table_covers_core_six():
    for name in (
        "Bourdain",
        "Munger",
        "CIA",
        "Hank Moody",
        "Pattern Recognition",
        "Emotional Intelligence",
    ):
        assert name in LENS_INTERNAL_QUESTIONS


def test_question_opens_many_capabilities_not_lens_aliases():
    """Capability must not be a 1:1 alias for the lens."""
    for lens in ("Bourdain", "Munger", "CIA"):
        family = lens_capability_family(lens)
        assert len(family) >= 4, lens
        # Primary routed capability should be one tool among many, not the lens name
        assert lens not in family
    assert "Sensory Realism" in LENS_CAPABILITY_FAMILIES["Bourdain"]
    assert "Opportunity cost" in LENS_CAPABILITY_FAMILIES["Munger"]
    assert "Missing information" in LENS_CAPABILITY_FAMILIES["CIA"]


def test_pipeline_includes_question_step():
    plan = build_response_plan(
        "McDonald's is easily the best place for burgers and fries."
    )
    assert plan.lens == "Bourdain"
    assert plan.lens_question == lens_internal_question("Bourdain")
    assert plan.lens_locked is True
    g = plan_closer_instruction(plan).lower()
    assert "question (invisible step" in g or "ask before capability" in g
    assert "lens persistence" in g
    assert "capability ≠ lens" in g or "capability != lens" in g or "not an alias" in g


def test_distinctive_noticing_not_generic():
    """Could this exact answer have been written by another lens? → no for distinctive."""
    for lens, pair in DISTINCTIVE_NOTICING.items():
        g = lens_voice_guidance(lens).lower()
        assert pair["generic"].lower() in g, lens  # taught as GENERIC failure
        assert pair["distinctive"].lower() in g, lens
        # Distinctive line for this lens must not appear in another core lens guide
        for other in DISTINCTIVE_NOTICING:
            if other == lens:
                continue
            other_g = lens_voice_guidance(other).lower()
            assert pair["distinctive"].lower() not in other_g, (lens, other)


def test_lens_persistence_finalize_cannot_re_lens():
    user = "McDonald's is easily the best place for burgers and fries."
    plan = build_response_plan(user)
    assert plan.lens == "Bourdain"
    # Attacker/editor attempt: mutate lens mid-flight — finalize must restore
    plan.lens = "Munger"
    draft = "You already know exactly what it's going to taste like."
    result = finalize_response(draft, user, plan=plan)
    assert result.plan.lens == "Bourdain"
    assert result.diagnostics.get("lens") == "Bourdain"
    assert result.diagnostics.get("lens_persistence") == "routing_only"
    assert result.diagnostics.get("lens_locked") == "true"
    assert "lived this notice" in (result.plan.lens_question or "").lower() or (
        result.diagnostics.get("lens_question") or ""
    )


def test_persistence_invariant_documented():
    assert "only routing can" in LENS_PERSISTENCE_INVARIANT.lower()
    assert "gold cannot change it" in LENS_PERSISTENCE_INVARIANT.lower()


def test_eat_substring_does_not_route_threatened_to_bourdain():
    """Regression: 'eat' inside 'threatened' must not select taste/Bourdain."""
    p = (
        "It's amusing that men refuse to give up the 'cat lady' threat even though "
        "women have never been threatened by it. It's a projection of his fears."
    )
    from response_finalization import classify_claim_domain

    assert classify_claim_domain(p) == "emotional"
    plan = build_response_plan(p)
    assert plan.lens == "Emotional Intelligence"
    assert plan.lens != "Bourdain"


def test_ei_prefers_people_not_group_claims():
    g = lens_voice_guidance("Emotional Intelligence").lower()
    assert "without a sweeping claim" in g or "sweeping claim" in g
    assert "people, not groups" in g or "begin with people" in g
    assert "people only use threats they believe would work on themselves" in g
    assert "women built lives with friends" in g  # FAIL example
    assert "approach diversity" in g or "discovery density" in g
    assert "discovery density" in g
    assert "every threat is autobiographical" in g


if __name__ == "__main__":
    test_core_lenses_have_unique_internal_questions()
    test_lens_guidance_is_not_interchangeable()
    test_authenticity_cases_select_plausible_lens()
    test_munger_ferrari_not_status_psychology()
    test_cia_boss_distant_respects_uncertainty()
    test_hank_divorce_not_profanity_costume()
    test_food_never_gets_pattern_recognition_lens()
    test_lens_question_table_covers_core_six()
    test_question_opens_many_capabilities_not_lens_aliases()
    test_pipeline_includes_question_step()
    test_distinctive_noticing_not_generic()
    test_lens_persistence_finalize_cannot_re_lens()
    test_persistence_invariant_documented()
    test_eat_substring_does_not_route_threatened_to_bourdain()
    test_ei_prefers_people_not_group_claims()
    print("All lens-authenticity tests passed.")
