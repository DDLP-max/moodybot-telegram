# -*- coding: utf-8 -*-
"""Response Budget = Depth × Shape. Density ≠ brevity; REFLECTION for contemplative asks."""

from gold_shape import apply_gold_shape_pass, evaluate_gold_shape
from response_finalization import (
    CORE_WRITE_DIRECTIVE,
    apply_budget_to_structure,
    build_response_plan,
    classify_response_budget,
    classify_topic_mode,
    plan_closer_instruction,
)


CAT_LADY = (
    "It's amusing to me that men refuse to give up the 'cat lady' threat even though "
    "women have never been threatened by it. It's a projection of his fears, not an "
    "example of hers. The biggest fear for these men is ending up alone so they assume "
    "it's women's biggest fear too, but it's not. There's no female loneliness epidemic "
    "because women don't experience loneliness like men do. Women don't need companionship "
    "in the same way that men do. Women are okay being single because women aren't ever "
    "really 'alone' like single men are. The sooner these men realize that threatening "
    "women with singledom isn't really a threat at all, the sooner they can switch their "
    "focus to becoming a man who women actually want to be in a relationship with instead."
)

MCDONALDS = "McDonald's is easily the best place for burgers and fries."

FORTIES = (
    "People in their 40s and over, what's something that people in their 20s "
    "don't realize will impact them as they get older"
)


def test_mcdonalds_is_low_snap_compress():
    assert classify_topic_mode(MCDONALDS, "taste_preference") == "compress"
    assert classify_response_budget(MCDONALDS, "taste_preference") == "low"
    plan = build_response_plan(MCDONALDS)
    assert plan.response_budget == "low"
    assert plan.preferred_structure == "SNAP"
    assert plan.topic_mode == "compress"


def test_cat_lady_is_high_knife_not_reflection():
    """Long ideology expands length but stays KNIFE — not midnight lyric."""
    assert classify_topic_mode(CAT_LADY) == "compress"
    plan = build_response_plan(CAT_LADY)
    assert plan.response_budget == "high"
    assert plan.preferred_structure == "KNIFE"
    assert plan.preferred_structure != "REFLECTION"
    g = plan_closer_instruction(plan).lower()
    assert "extended knife" in g or "depth: high" in g
    assert "do not flip into lyrical" in g or "extended knife" in g


def test_forties_prompt_is_high_reflection():
    """Short existential ask → REFLECTION (~250–450), not a tweet."""
    assert classify_topic_mode(FORTIES) == "expand"
    assert classify_response_budget(FORTIES) == "high"
    plan = build_response_plan(FORTIES)
    assert plan.response_budget == "high"
    assert plan.preferred_structure == "REFLECTION"
    assert plan.topic_mode == "expand"
    g = plan_closer_instruction(plan).lower()
    assert "reflection" in g
    assert "250" in g or "450" in g or "midnight" in g


def test_medium_tweet_stays_knife():
    tweet = "Dating shouldn't feel like a job interview every weekend."
    budget = classify_response_budget(tweet, "relationship")
    assert budget in {"low", "medium"}
    struct = apply_budget_to_structure("KNIFE", budget, tweet, "relationship")
    assert struct in {"SNAP", "KNIFE"}


def test_core_write_has_depth_times_shape():
    lower = CORE_WRITE_DIRECTIVE.lower()
    assert "response budget" in lower
    assert "reflection" in lower
    assert "depth" in lower and "shape" in lower
    assert "density" in lower and "brevity" in lower
    assert "time sneaks up" in lower or "prison is just a room" in lower
    assert "necessary development" in lower or "expand topics" in lower
    assert "surprise the reader" in lower
    assert "reframe the reader" in lower
    assert "earn every paragraph" in lower
    assert "observation" in lower and "deepening" in lower and "acceptance" in lower


def test_reflection_guidance_names_purpose_and_diamond():
    plan = build_response_plan(FORTIES)
    g = plan_closer_instruction(plan).lower()
    assert "seeing their own life differently" in g
    assert "earn every paragraph" in g
    assert "same diamond" in g or "rotate the same diamond" in g


def test_high_budget_gold_does_not_flag_developed_knife():
    developed = (
        "People usually threaten others with the loss they'd fear most themselves. "
        "That's why arguments about relationships often reveal more about the speaker "
        "than the target. "
        "The mistake is assuming everyone organizes their lives around the same "
        "emotional needs. Some people build their world around a partner. Others build "
        "it around family, friends, work, or community. Remove one pillar and the "
        "building doesn't necessarily collapse. "
        "The moment you assume your greatest fear is universal, you've stopped "
        "describing other people and started describing yourself."
    )
    failures_high = evaluate_gold_shape(CAT_LADY, developed, "KNIFE", response_budget="high")
    assert "knife_overlong" not in failures_high
    out, report = apply_gold_shape_pass(
        CAT_LADY, developed, preferred_structure="KNIFE", response_budget="high"
    )
    assert report.response_budget == "high"
    assert report.selected_structure != "SNAP"
    assert len(out.split()) >= 60


def test_reflection_gold_preserves_contemplative_length():
    reflection = (
        "Time sneaks up on you like a ghost haunting the corners of your ambition, "
        "a currency set to inflate beyond your reach if you keep spending it like it's endless. "
        "Your body begins to whisper doubts you used to shout over. Friendships settle into "
        "quiet loyalty, and love becomes a tender ache instead of a fireworks show. "
        "Here's the kicker: purpose stops being about the chase and starts being about "
        "who you are when the chase ends. Choices etch themselves into you years later. "
        "The gap between dream and reality is an unexpected mirror. Invest youth. "
        "Don't just spend it."
    )
    failures = evaluate_gold_shape(
        FORTIES, reflection, "REFLECTION", response_budget="high"
    )
    assert "reflection_overlong" not in failures
    out, report = apply_gold_shape_pass(
        FORTIES, reflection, preferred_structure="REFLECTION", response_budget="high"
    )
    assert report.selected_structure == "REFLECTION"
    assert len(out.split()) >= 80


def test_story_alias_maps_to_reflection():
    assert apply_budget_to_structure("STORY", "high", FORTIES, "general", "expand") == "REFLECTION"


if __name__ == "__main__":
    test_mcdonalds_is_low_snap_compress()
    test_cat_lady_is_high_knife_not_reflection()
    test_forties_prompt_is_high_reflection()
    test_medium_tweet_stays_knife()
    test_core_write_has_depth_times_shape()
    test_high_budget_gold_does_not_flag_developed_knife()
    test_reflection_gold_preserves_contemplative_length()
    test_story_alias_maps_to_reflection()
    print("All response-budget tests passed.")
