# -*- coding: utf-8 -*-
"""Mechanism-diversity regression: unrelated prompts must not collapse to one drawer.

Routing can be technically correct and still semantically stale if 30 prompts
share the same 4–5 abstractions. This suite checks that claim type → lens →
capability → mechanism_hint actually change with the subject.
"""

from response_finalization import (
    build_response_plan,
    classify_claim_domain,
    plan_closer_instruction,
)


# (prompt, expected_domain, expected_lens, expected_capability_substr, expected_mechanism_hint)
DIVERSITY_CASES = [
    (
        "McDonald's is easily the best place for burgers and fries.",
        "taste_preference",
        "Bourdain",
        "Everyday Preference",
        "familiarity_vs_quality",
    ),
    (
        "Airport hotels are the peak of travel luxury.",
        "travel",
        "Bourdain",
        "Lived Experience",
        "place_texture_honesty",
    ),
    (
        "My friend only texts when she needs a ride.",
        "relationship",
        "Hank Moody",
        "Relationship Pattern",
        "boundary_leverage",
    ),
    (
        "The promotion doubles my hours — salary tradeoff looks ugly.",
        "business",
        "Munger",
        "Business / Tradeoff",
        "incentives_second_order",
    ),
    (
        "The affidavit contradicts her earlier statement.",
        "court",
        "CIA",
        "Evidence / Contradiction",
        "evidence_vs_inference",
    ),
    (
        "Feminists hate when a woman genuinely appreciates her man.",
        "social_power",
        "Noir Detective",
        "Power / Incentive",
        "power_incentives",
    ),
    (
        "The iPhone is worth buying even at this price.",
        "consumer_preference",
        "Munger",
        "Business / Tradeoff",
        "status_lockin_hype",
    ),
    (
        "What should I do about the lockout kit flowers?",
        "practical",
        "Field Operator",
        "Practical Next Action",
        "concrete_next_step",
    ),
    (
        "Why does this TypeScript build keep failing on deploy?",
        "technical",
        "Builder",
        "Operational Intelligence",
        "cause_fix",
    ),
    (
        "Sex without affection started feeling like a transaction.",
        "relationship",
        "Hank Moody",
        "Relationship Pattern",
        "boundary_leverage",
    ),
    (
        "Everyone at work pretends busy to look important.",
        "general",  # status-ish everyday — may route general/Hank unless keywords hit
        "Hank Moody",
        None,  # capability flexible
        None,
    ),
]


def test_mcdonalds_four_layer_stack():
    user = "McDonald's is easily the best place for burgers and fries."
    plan = build_response_plan(user)
    assert plan.claim_domain == "taste_preference"
    assert plan.lens == "Bourdain"
    assert plan.primary_capability == "Everyday Preference Analysis"
    assert plan.supporting_capability == "Sensory Realism"
    assert plan.preferred_structure == "SNAP"
    assert plan.mechanism_hint == "familiarity_vs_quality"
    guidance = plan_closer_instruction(plan).lower()
    assert "interpretive lens" in guidance or "whose eyes" in guidance
    assert "everyday preference" in guidance
    assert "prison is just a room" in guidance
    assert "gold never" in guidance


def test_lens_is_not_capability():
    """Bourdain is Identity; Everyday Preference Analysis is Intelligence."""
    plan = build_response_plan(
        "McDonald's is easily the best place for burgers and fries."
    )
    assert plan.lens == "Bourdain"
    assert plan.primary_capability != "Bourdain"
    assert "Sensory" not in (plan.primary_capability or "")


def test_unrelated_prompts_diversify_mechanism_hints():
    rows = []
    for prompt, domain, lens, cap_sub, mech in DIVERSITY_CASES:
        if mech is None:
            continue
        plan = build_response_plan(prompt)
        assert classify_claim_domain(prompt) == domain, prompt
        assert plan.lens == lens, prompt
        if cap_sub:
            assert cap_sub.lower() in (plan.primary_capability or "").lower(), prompt
        assert plan.mechanism_hint == mech, prompt
        rows.append((plan.lens, plan.primary_capability, plan.mechanism_hint))

    hints = {r[2] for r in rows}
    lenses = {r[0] for r in rows}
    caps = {r[1] for r in rows}
    # Stale routing symptom: everything collapses into one drawer
    assert len(hints) >= 6, hints
    assert len(lenses) >= 4, lenses
    assert len(caps) >= 5, caps
    assert "familiarity_vs_quality" in hints
    assert "power_incentives" in hints
    assert "evidence_vs_inference" in hints
    assert "boundary_leverage" in hints


def test_food_and_power_do_not_share_mechanism_family():
    food = build_response_plan(
        "McDonald's is easily the best place for burgers and fries."
    )
    power = build_response_plan(
        "Feminists hate when a woman genuinely appreciates her man."
    )
    assert food.mechanism_hint != power.mechanism_hint
    assert food.lens != power.lens
    assert food.primary_capability != power.primary_capability


def test_gold_guidance_says_editor_not_coauthor():
    plan = build_response_plan("Coffee is better than wine.")
    g = plan_closer_instruction(plan).lower()
    assert "gold only" in g or "gold never" in g
    assert "co-author" in g or "never picks the lens" in g or "only compresses" in g


if __name__ == "__main__":
    test_mcdonalds_four_layer_stack()
    test_lens_is_not_capability()
    test_unrelated_prompts_diversify_mechanism_hints()
    test_food_and_power_do_not_share_mechanism_family()
    test_gold_guidance_says_editor_not_coauthor()
    print("All mechanism-diversity tests passed.")
