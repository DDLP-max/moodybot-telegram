# -*- coding: utf-8 -*-
"""Regression tests for evidence vs inference / epistemic calibration."""

from pathlib import Path


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
    assert "level 1" in text
    assert "level 3" in text
    assert "never present level 3" in text or "never present" in text
    assert "action survives uncertainty" in text


def test_evidence_vs_inference_has_bad_better_best_examples():
    text = (INTEL / "capabilities" / "evidence-vs-inference.md").read_text(encoding="utf-8")
    assert "He turned it into an invitation." in text
    assert "He may have treated it as an invitation." in text
    assert "Whether he interpreted it as an invitation" in text
    assert "His motives remain uncertain." in text


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
    assert "declared motive" in text


def test_operator_heuristics_include_epistemic_trio():
    text = (INTEL / "operator-heuristics.md").read_text(encoding="utf-8")
    assert "What do we actually know?" in text
    assert "What are we inferring?" in text
    assert "What changes regardless?" in text


def test_response_order_has_motivation_attribution_check():
    text = (RESPONSE / "response-generation-order.md").read_text(encoding="utf-8")
    assert "Motivation Attribution Check" in text
    assert "Evidence Gate" in text
    assert "Action Survives Uncertainty Check" in text


def test_doorman_regression_rejects_mind_reading():
    text = (TESTING / "doorman-boundary-regression.md").read_text(encoding="utf-8")
    assert "He was trying to seduce her." in text
    assert "He decided he had access." in text
    assert "professional boundary shifted" in text.lower() or "professional boundary has shifted" in text.lower()
    assert "Thank you for the thought" in text


def test_corpus_teaches_action_survives_uncertainty():
    blob = _blob(INTEL)
    assert "action survives uncertainty" in blob
    assert "what changes regardless" in blob
    assert "epistemic calibration" in blob or "epistemic-calibration" in str(
        list((INTEL / "capabilities").glob("*.md"))
    ).lower()


if __name__ == "__main__":
    test_epistemic_calibration_file_exists()
    test_evidence_vs_inference_has_bad_better_best_examples()
    test_intent_vs_impact_impact_determines_response()
    test_relationship_pattern_uses_boundary_shift_order()
    test_operator_heuristics_include_epistemic_trio()
    test_response_order_has_motivation_attribution_check()
    test_doorman_regression_rejects_mind_reading()
    test_corpus_teaches_action_survives_uncertainty()
    print("All epistemic calibration tests passed.")
