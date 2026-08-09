# -*- coding: utf-8 -*-
"""Generator: think abstractly, speak concretely. Protect-only untouched."""

from pathlib import Path

from recognition_landing import LANDING_ENGINE_VERSION
from response_finalization import (
    CORE_WRITE_DIRECTIVE,
    finalize_response,
    infer_governing_pattern,
)


def test_protect_only_untouched():
    assert LANDING_ENGINE_VERSION == "protect-only-v1"


def test_write_directive_separates_thinking_and_writing():
    lower = CORE_WRITE_DIRECTIVE.lower()
    assert "think abstractly" in lower
    assert "speak concretely" in lower
    assert "governing pattern" in lower
    assert "translate" in lower or "ordinary language" in lower
    assert "spear" in lower
    assert "cut" in lower and "prove once" in lower



def test_trust_the_reader_in_generation_guidance():
    lower = CORE_WRITE_DIRECTIVE.lower()
    assert "trust the reader" in lower
    assert "new understanding" in lower
    assert "prove it once" in lower
    path = Path("moodybot-system-prompt/9_response-engine/trust-the-reader.md")
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    assert "saying less" in text or "say less" in text


def test_thesis_discipline_in_generation_guidance():
    lower = CORE_WRITE_DIRECTIVE.lower()
    assert "thesis discipline" in lower
    assert "one response" in lower and "one thesis" in lower
    assert "bloodlines mattered" in lower
    assert "spine" in lower
    assert "spear" in lower or "one idea" in lower
    path = Path("moodybot-system-prompt/9_response-engine/thesis-discipline.md")
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    assert "distraction test" in text or "cross-examination" in text
    assert "how does this prove the thesis" in text


def test_thinking_vs_writing_doc():
    path = Path("moodybot-system-prompt/9_response-engine/thinking-vs-writing.md")
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    assert "governing pattern" in text
    assert "think abstractly" in text
    assert "speak concretely" in text


def test_got_regression_concepts_in_guidance():
    blob = (
        CORE_WRITE_DIRECTIVE
        + Path("moodybot-system-prompt/9_response-engine/thinking-vs-writing.md").read_text(
            encoding="utf-8"
        )
        + Path("moodybot-system-prompt/9_response-engine/concrete-before-abstract.md").read_text(
            encoding="utf-8"
        )
    ).lower()
    assert "stopped playing by its own rules" in blob or "obeying its own rules" in blob
    assert "incentive structure" in blob
    assert "narrative contract" in blob
    assert "making a move" in blob
    assert "don't trust you" in blob or "people don't trust" in blob


def test_governing_pattern_prefers_opening_take_not_mid_essay():
    draft = (
        "Game of Thrones stopped playing by its own rules. "
        "For years, bad choices had a cost. "
        "Later the incentive structure and narrative contract collapsed into coherence problems."
    )
    pattern = infer_governing_pattern("Why did GoT fail?", draft)
    assert "stopped playing by its own rules" in pattern.lower()
    assert "incentive structure" not in pattern.lower()


def test_finalizer_still_does_not_rewrite_jargon():
    draft = (
        "Game of Thrones abandoned the incentive structure. "
        "The narrative contract collapsed into coherence failure."
    )
    result = finalize_response(draft, "Why did GoT end badly?")
    assert "incentive structure" in result.text.lower()
    assert result.diagnostics.get("governing_pattern") is not None
    assert result.diagnostics.get("landing_added") == "false"


def test_diagnostics_log_governing_pattern_key():
    result = finalize_response(
        "He's making a move. The professional boundary changed.",
        "Doorman sent flowers after getting my number.",
    )
    assert "governing_pattern" in result.diagnostics
    assert "making a move" in result.diagnostics["governing_pattern"].lower()


if __name__ == "__main__":
    test_protect_only_untouched()
    test_write_directive_separates_thinking_and_writing()
    test_trust_the_reader_in_generation_guidance()
    test_thesis_discipline_in_generation_guidance()
    test_thinking_vs_writing_doc()
    test_got_regression_concepts_in_guidance()
    test_governing_pattern_prefers_opening_take_not_mid_essay()
    test_finalizer_still_does_not_rewrite_jargon()
    test_diagnostics_log_governing_pattern_key()
    print("All thinking-vs-writing tests passed.")
