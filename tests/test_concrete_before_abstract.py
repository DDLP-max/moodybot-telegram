# -*- coding: utf-8 -*-
"""Generator guidance: concrete before abstract. Not a finalizer rewrite layer."""

from pathlib import Path

from recognition_landing import LANDING_ENGINE_VERSION
from response_finalization import CORE_WRITE_DIRECTIVE, finalize_response


PROMPT_DIR = Path("moodybot-system-prompt/9_response-engine")


def test_protect_only_still_intact():
    assert LANDING_ENGINE_VERSION == "protect-only-v1"


def test_concrete_before_abstract_doc_exists():
    path = PROMPT_DIR / "concrete-before-abstract.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    assert "concrete before abstract" in text
    assert "barstool" in text
    assert "incentive structure" in text
    assert "narrative contract" in text
    assert "ordinary human language" in text or "ordinary language" in text


def test_write_directive_requires_translation_step():
    lower = CORE_WRITE_DIRECTIVE.lower()
    assert "concrete before abstract" in lower
    assert "ordinary human language" in lower or "ordinary language" in lower
    assert "translate" in lower
    assert "barstool" in lower or "say this aloud" in lower
    assert "incentive structure" in lower  # named as avoid
    assert "narrative contract" in lower
    # Prefer human words
    assert "rules" in lower and "promises" in lower and "trust" in lower


def test_got_guidance_prefers_rules_over_jargon():
    """Regression concepts for GoT — in generation guidance, not output mutation."""
    lower = CORE_WRITE_DIRECTIVE.lower()
    blob = (PROMPT_DIR / "concrete-before-abstract.md").read_text(encoding="utf-8").lower()
    combined = lower + "\n" + blob
    for prefer in ("rules", "promises", "choices", "consequences"):
        assert prefer in combined
    for avoid in ("incentive structure", "narrative contract", "coherence"):
        assert avoid in combined  # present as things to avoid


def test_relationship_guidance_prefers_move_boundary():
    blob = (PROMPT_DIR / "concrete-before-abstract.md").read_text(encoding="utf-8").lower()
    assert "making a move" in blob
    assert "asymmetric relational dynamic" in blob  # as BAD example


def test_business_guidance_prefers_trust_cost():
    blob = (PROMPT_DIR / "concrete-before-abstract.md").read_text(encoding="utf-8").lower()
    assert "paying for attention" in blob or "trust" in blob
    assert "incentive alignment" in blob  # as BAD example


def test_finalizer_does_not_rewrite_abstract_diction():
    """protect-only must NOT mutate consultant diction after generation."""
    draft = (
        "Game of Thrones abandoned the incentive structure the show itself had trained "
        "viewers to expect. The narrative contract collapsed."
    )
    result = finalize_response(draft, "Why did Game of Thrones end so badly?")
    lower = result.text.lower()
    # Finalizer leaves diction alone (may only add whiskey watermark)
    assert "incentive structure" in lower
    assert "narrative contract" in lower
    assert result.diagnostics.get("landing_added") == "false"
    assert result.diagnostics.get("creative_touch") == "false"


def test_system_prompt_includes_concrete_section():
    text = Path("system_prompt.txt").read_text(encoding="utf-8").lower()
    assert "concrete before abstract" in text
    assert "barstool" in text or "ordinary human language" in text


if __name__ == "__main__":
    test_protect_only_still_intact()
    test_concrete_before_abstract_doc_exists()
    test_write_directive_requires_translation_step()
    test_got_guidance_prefers_rules_over_jargon()
    test_relationship_guidance_prefers_move_boundary()
    test_business_guidance_prefers_trust_cost()
    test_finalizer_does_not_rewrite_abstract_diction()
    test_system_prompt_includes_concrete_section()
    print("All concrete-before-abstract generator tests passed.")
