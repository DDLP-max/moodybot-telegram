# -*- coding: utf-8 -*-
"""Behavioral tests for Emotional Intelligence routing."""

from dynamic_persona_engine import DynamicPersonaEngine
from legacy_persona_aliases import bundle_for_command, resolve_alias


def test_doorman_scenario_routes_to_relationship_and_boundary():
    engine = DynamicPersonaEngine()
    msg = (
        "A woman thought a doorman's phone number was related to a lockout kit. "
        "He later sent flowers and wine. What is happening and what should she do?"
    )
    result = engine.process_user_input(msg, {})
    caps = result["capabilities"]
    assert caps["primary"] == "Relationship Pattern Recognition"
    assert caps["secondary"] == "Boundary Analysis"
    assert caps["intervention"] == "Grounded Recalibration"


def test_practical_action_request():
    engine = DynamicPersonaEngine()
    result = engine.process_user_input("What should I do next?", {})
    assert result["capabilities"]["primary"] == "Practical Next Action"


def test_cia_alias_maps_to_interrogative_analysis():
    bundle = bundle_for_command("/cia")
    assert "interrogative_analysis" in bundle["capabilities"]
    assert "clipped_precision" in bundle["voice"]


def test_validate_alias_maps_to_validation_bundle():
    bundle = bundle_for_command("validate")
    assert "emotional_validation" in bundle["capabilities"]
    assert "gentle_stabilization" in bundle["intervention"]


def test_legacy_persona_names_are_deprecated_aliases():
    for key in ("bourdain", "noir", "munger", "field-operator", "sam-neill"):
        alias = resolve_alias(key)
        assert alias is not None
        assert alias.get("deprecated") is True


def test_manual_slash_still_accepted_by_engine():
    engine = DynamicPersonaEngine()
    result = engine.process_user_input("/savage tell me the truth", {})
    assert result["source"] == "manual_override"
    assert result["deprecated_alias"] is True


def test_expected_doorman_intelligence_concepts():
    """Regression concepts for the doorman/flowers case (not exact wording)."""
    required_concepts = {
        "boundary",
        "inference",
        "intent",
        "impact",
        "action",
        "professional",
    }
    # Prompt corpus must teach these concepts
    from pathlib import Path
    root = Path("moodybot-system-prompt/2_intelligence-engine")
    blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in root.rglob("*.md"))
    blob_l = blob.lower()
    for concept in required_concepts:
        assert concept in blob_l, f"missing concept in EI corpus: {concept}"


if __name__ == "__main__":
    test_doorman_scenario_routes_to_relationship_and_boundary()
    test_practical_action_request()
    test_cia_alias_maps_to_interrogative_analysis()
    test_validate_alias_maps_to_validation_bundle()
    test_legacy_persona_names_are_deprecated_aliases()
    test_manual_slash_still_accepted_by_engine()
    test_expected_doorman_intelligence_concepts()
    print("All EI routing tests passed.")
