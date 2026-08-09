# -*- coding: utf-8 -*-
"""Gold-shape regression: delivery geometry from training/moodybot-gold/."""

from pathlib import Path

from gold_shape import (
    GOLD_SHAPE_VERSION,
    apply_gold_shape_pass,
    detect_mechanism_mismatch,
    evaluate_gold_shape,
    select_structure,
)
from response_finalization import (
    CORE_WRITE_DIRECTIVE,
    build_response_plan,
    classify_claim_domain,
    finalize_response,
    plan_closer_instruction,
)
from recognition_landing import LANDING_ENGINE_VERSION

GOLD_DIR = Path("training/moodybot-gold")


def test_protect_only_still_landing_engine():
    assert LANDING_ENGINE_VERSION == "protect-only-v1"
    assert GOLD_SHAPE_VERSION == "gold-shape-v1"


def test_core_write_has_gold_geometry():
    lower = CORE_WRITE_DIRECTIVE.lower()
    assert "cut" in lower and "prove once" in lower
    assert "premise relocation" in lower or "relocate" in lower
    assert "spear" in lower
    assert "🥃" in CORE_WRITE_DIRECTIVE
    assert "stay dangerous" in lower  # banned example
    assert "resentment economy" in lower  # avoided diction
    assert "mechanism fit" in lower
    assert "rule-shopping" in lower
    assert "claim type" in lower
    assert "interpretive lens" in lower or "whose eyes" in lower
    assert "everyday preference" in lower
    assert "bourdain" in lower
    assert "prison is just a room" in lower
    assert "gold never" in lower


def test_mcdonalds_routes_to_bourdain_not_pattern_recognition():
    """Food: Bourdain lens + Everyday Preference Analysis + SNAP — not Power analysis."""
    user = "McDonald's is easily the best place for burgers and fries."
    assert classify_claim_domain(user) == "taste_preference"
    plan = build_response_plan(user, selected_command="/thoughts")
    assert plan.claim_domain == "taste_preference"
    assert plan.lens == "Bourdain"
    assert plan.primary_capability == "Everyday Preference Analysis"
    assert plan.supporting_capability == "Sensory Realism"
    assert plan.preferred_structure == "SNAP"
    assert plan.mechanism_hint == "familiarity_vs_quality"
    assert "Power" not in (plan.primary_capability or "")
    guidance = plan_closer_instruction(plan).lower()
    assert "bourdain" in guidance
    assert "everyday preference" in guidance
    assert "prison is just a room" in guidance
    assert "rule-shopping" in guidance  # banned when unsupported
    assert "interpretive lens" in guidance or "whose eyes" in CORE_WRITE_DIRECTIVE.lower()

    bad = (
        "The pattern is rule-shopping. People reach for the standard that "
        "delivers the benefit and drop the one that demands the cost."
    )
    assert detect_mechanism_mismatch(user, bad) is True
    failures = evaluate_gold_shape(user, bad, "KNIFE")
    assert "mechanism_mismatch" in failures
    out, report = apply_gold_shape_pass(user, bad, preferred_structure="SNAP")
    assert report.mechanism_mismatch is True
    # Diagnostic only — Gold must not invent a Bourdain line
    assert "rule-shopping" in out.lower()
    result = finalize_response(bad, user)
    assert result.diagnostics.get("claim_domain") == "taste_preference"
    assert result.diagnostics.get("lens") == "Bourdain"
    assert result.diagnostics.get("interpretive_lens") == "Bourdain"
    assert result.diagnostics.get("mechanism_mismatch") == "true"
    assert result.diagnostics.get("primary_capability") == "Everyday Preference Analysis"
    assert result.diagnostics.get("preferred_structure") == "SNAP"


def test_social_prompt_allows_rule_shopping_name():
    user = (
        "Feminists want the authority of a man. The privileges of a woman. "
        "And the responsibility of a child."
    )
    draft = (
        "The pattern is rule-shopping. People reach for the standard that "
        "delivers the benefit and drop the one that demands the cost."
    )
    assert detect_mechanism_mismatch(user, draft) is False
    assert "mechanism_mismatch" not in evaluate_gold_shape(user, draft, "KNIFE")


def test_gold_docs_present():
    assert (GOLD_DIR / "gold.json").exists()
    assert (GOLD_DIR / "style-guide.md").exists()
    assert (GOLD_DIR / "pattern-analysis.md").exists()
    assert Path("moodybot-system-prompt/9_response-engine/gold-shape.md").exists()


def test_pick_me_amplification_compresses():
    user = (
        "Feminists hate when a woman genuinely appreciates her man. "
        "The moment you praise him, they call you a pick me. "
        "Apparently being grateful for your man is now a betrayal of womanhood."
    )
    draft = (
        "The pick me label exists to punish women who break the script. "
        "When a woman says her man improves her life, the movement loses a recruit "
        "for the resentment economy. Gratitude is treated as defection because the "
        "ideology needs every woman positioned as harmed. Praise for a specific man "
        "makes the universal claim harder to maintain. So the group labels it betrayal "
        "and moves on. The pressure isn't about her happiness. It's about keeping the "
        "story intact. Stay dangerous."
    )
    failures = evaluate_gold_shape(user, draft, "KNIFE")
    assert any(
        f in failures
        for f in (
            "thesis_repetition",
            "multi_mechanism_essay",
            "essay_diction",
            "post_payoff_drift",
            "cta_or_costume_tail",
            "knife_overlong",
        )
    )
    out, report = apply_gold_shape_pass(user, draft)
    assert report.quality_rewrite_triggered is True
    assert "stay dangerous" not in out.lower()
    result = finalize_response(draft, user)
    assert result.text.rstrip().endswith("🥃")
    assert result.diagnostics.get("gold_shape_version") == GOLD_SHAPE_VERSION
    assert "selected_structure" in result.diagnostics
    body = result.text.replace("🥃", "").strip()
    assert len(body.split()) < len(draft.split())
    assert "stay dangerous" not in body.lower()


def test_clean_knife_ships_with_whiskey_minimal_touch():
    user = "Why do people call grateful women pick-mes?"
    draft = (
        "Pick me isn't about womanhood. It's a penalty for leaving the grievance script. "
        "A woman who says her man makes her life better is one less recruit for the shared "
        "injury story. So the group calls it betrayal and moves on."
    )
    result = finalize_response(draft, user)
    assert result.text.rstrip().endswith("🥃")
    assert result.diagnostics.get("spear_detected") == "true"
    # Should not invent Signature Line paragraph
    assert result.text.count("\n\n") <= 1


def test_stacked_metaphor_flagged():
    user = "What is leadership?"
    draft = (
        "He's steering the ship, moving the chess pieces like a grandmaster, "
        "and keeping the wolves outside the gate as if the night never ends."
    )
    failures = evaluate_gold_shape(user, draft, "KNIFE")
    assert "stacked_metaphor" in failures


def test_rule_shopping_cashes_out_abstract_closer():
    """Editorial cash-out: drop conference-talk closer when spoken proof already landed."""
    user = (
        "Feminists want the authority of a man. The privileges of a woman. "
        "And the responsibility of a child."
    )
    draft = (
        "The pattern is rule-shopping. Any group grabs the standard that delivers "
        "advantage and drops the one that imposes cost. The same move appears wherever "
        "incentives reward inconsistency over fixed boundaries."
    )
    failures = evaluate_gold_shape(user, draft, "KNIFE")
    assert "abstract_closer" in failures
    out, report = apply_gold_shape_pass(user, draft)
    assert report.quality_rewrite_triggered is True
    lower = out.lower()
    assert "incentives reward inconsistency" not in lower
    assert "rule-shopping" in lower
    assert "standard" in lower and "cost" in lower
    result = finalize_response(draft, user)
    assert result.text.rstrip().endswith("🥃")
    assert "incentives reward inconsistency" not in result.text.lower()


def test_precise_mechanism_name_is_not_stripped():
    """Abstraction that IS the shortest accurate name must survive cash-out."""
    user = "Why do people excuse bad behavior after doing one good thing?"
    draft = (
        "That's moral licensing. One clean act gets treated like a voucher "
        "for the next ugly one."
    )
    failures = evaluate_gold_shape(user, draft, "KNIFE")
    assert "abstract_closer" not in failures
    out, report = apply_gold_shape_pass(user, draft)
    assert "moral licensing" in out.lower()
    assert report.quality_rewrite_triggered is False or "moral licensing" in out.lower()


def test_structure_selection_snap():
    assert select_structure("hi", "You already know the answer.") == "SNAP"


def test_gold_corpus_examples_end_clean_when_finalized():
    import json

    rows = json.loads((GOLD_DIR / "gold.json").read_text(encoding="utf-8"))
    for row in rows[:5]:
        result = finalize_response(row["assistant_response"], row["original_user_prompt"])
        assert result.text.rstrip().endswith("🥃")
        assert result.diagnostics.get("landing_added") == "false"


if __name__ == "__main__":
    test_protect_only_still_landing_engine()
    test_core_write_has_gold_geometry()
    test_mcdonalds_routes_to_bourdain_not_pattern_recognition()
    test_social_prompt_allows_rule_shopping_name()
    test_gold_docs_present()
    test_pick_me_amplification_compresses()
    test_clean_knife_ships_with_whiskey_minimal_touch()
    test_stacked_metaphor_flagged()
    test_rule_shopping_cashes_out_abstract_closer()
    test_precise_mechanism_name_is_not_stripped()
    test_structure_selection_snap()
    test_gold_corpus_examples_end_clean_when_finalized()
    print("All gold-shape tests passed.")
