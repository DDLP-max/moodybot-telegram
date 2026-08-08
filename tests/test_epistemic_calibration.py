# -*- coding: utf-8 -*-
"""Regression tests for evidence vs inference / epistemic calibration."""

from pathlib import Path

from response_finalization import (
    classify_inference_distance,
    finalize_response,
    run_epistemic_check,
    should_rewrite_claim,
)
from response_finalization import build_response_plan


INTEL = Path("moodybot-system-prompt/2_intelligence-engine")
RESPONSE = Path("moodybot-system-prompt/9_response-engine")
TESTING = Path("moodybot-system-prompt/10_testing-quality")


def _blob(root: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in root.rglob("*.md")
    ).lower()


def test_epistemic_calibration_file_exists():
    path = INTEL / "capabilities" / "epistemic-calibration.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    assert "ordinary human inference" in text
    assert "inference distance" in text
    assert "invented hidden scheme" in text
    assert "protect against fabrication" in text
    assert "action survives uncertainty" in text


def test_evidence_vs_inference_allows_ordinary_inference():
    text = (INTEL / "capabilities" / "evidence-vs-inference.md").read_text(encoding="utf-8")
    assert "He's making a move." in text
    assert "Do not convert **remote or consequential** inference into fact." in text
    assert "He planned this from the beginning." in text


def test_intent_vs_impact_impact_determines_response():
    text = (INTEL / "capabilities" / "intent-vs-impact.md").read_text(encoding="utf-8").lower()
    assert "impact determines response" in text
    assert "does not change" in text
    assert "boundary" in text


def test_relationship_pattern_uses_boundary_shift_order():
    text = (
        INTEL / "capabilities" / "relationship-pattern-recognition.md"
    ).read_text(encoding="utf-8").lower()
    assert "observed behavior" in text
    assert "boundary shift" in text
    assert "possible interpretations" in text
    assert "recommended response" in text


def test_operator_heuristics_include_epistemic_trio():
    text = (INTEL / "operator-heuristics.md").read_text(encoding="utf-8")
    assert "What do we actually know?" in text
    assert "What are we inferring?" in text
    assert "What changes regardless?" in text


def test_response_order_has_remote_motive_check():
    text = (RESPONSE / "response-generation-order.md").read_text(encoding="utf-8")
    assert "Remote Motive Check" in text
    assert "Evidence Check" in text
    assert "Action Survives Uncertainty Check" in text


def test_doorman_regression_allows_move_blocks_scheme():
    text = (TESTING / "doorman-boundary-regression.md").read_text(encoding="utf-8")
    assert "He's making a move." in text
    assert "He used the lockout kit as a pretext" in text
    assert "ALLOWED" in text
    assert "invented hidden scheme" in text.lower() or "HIDDEN" in text or "scheme" in text.lower()


def test_corpus_teaches_action_survives_uncertainty():
    blob = _blob(INTEL)
    assert "action survives uncertainty" in blob
    assert "what changes regardless" in blob


def test_inference_distance_classes():
    assert classify_inference_distance("He sent flowers.")[0] == 0
    assert classify_inference_distance("He's making a move.")[0] == 1
    assert classify_inference_distance("The language became more performative.")[0] == 2
    assert classify_inference_distance("He wanted control.")[0] == 3
    assert classify_inference_distance(
        "He used the lockout kit as a pretext to obtain her number."
    )[0] == 4


def test_flowers_allows_ordinary_inference():
    user = (
        "A woman gave the doorman her number for lockout reasons. "
        "He later sent flowers and wine. What should she do?"
    )
    draft = (
        "Yeah — he's making a move. He is probably romantically or sexually interested.\n\n"
        "Keep the boundary clean."
    )
    result = finalize_response(draft, user)
    lower = result.text.lower()
    assert "making a move" in lower
    assert "romantically or sexually interested" in lower
    assert "may possibly" not in lower


def test_flowers_blocks_hidden_scheme():
    user = (
        "A woman gave the doorman her number for lockout reasons. "
        "He later sent flowers and wine. What should she do?"
    )
    draft = (
        "He used the lockout kit as a pretext to obtain her number. "
        "He planned this from the beginning."
    )
    text, changed = run_epistemic_check(draft, build_response_plan(user))
    assert changed
    lower = text.lower()
    assert "pretext" not in lower
    assert "from the beginning" not in lower


def test_cultural_thesis_allowed_numbers_blocked():
    user = "How did dirty talk change from 1995 to 2026?"
    draft = (
        "The language became more performative. "
        "Porn helped mainstream more extreme scripts. "
        "The average person consumed 3,000 hours of porn."
    )
    text, changed = run_epistemic_check(draft, build_response_plan(user))
    lower = text.lower()
    assert "performative" in lower
    assert "mainstream" in lower or "porn helped" in lower
    assert "3,000 hours" not in lower
    assert changed


def test_relationship_ordinary_vs_scheme():
    assert should_rewrite_claim("They are treating you as low priority.") is False
    assert should_rewrite_claim("They secretly have another partner.") is True


def test_workplace_ordinary_vs_scheme():
    assert should_rewrite_claim("They are protecting their position.") is False
    assert should_rewrite_claim("They planned your termination months ago.") is True


if __name__ == "__main__":
    test_epistemic_calibration_file_exists()
    test_evidence_vs_inference_allows_ordinary_inference()
    test_intent_vs_impact_impact_determines_response()
    test_relationship_pattern_uses_boundary_shift_order()
    test_operator_heuristics_include_epistemic_trio()
    test_response_order_has_remote_motive_check()
    test_doorman_regression_allows_move_blocks_scheme()
    test_corpus_teaches_action_survives_uncertainty()
    test_inference_distance_classes()
    test_flowers_allows_ordinary_inference()
    test_flowers_blocks_hidden_scheme()
    test_cultural_thesis_allowed_numbers_blocked()
    test_relationship_ordinary_vs_scheme()
    test_workplace_ordinary_vs_scheme()
    print("All epistemic calibration tests passed.")
