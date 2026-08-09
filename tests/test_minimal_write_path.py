# -*- coding: utf-8 -*-
"""Protect-only finalizer — generation creates; finalization protects."""

from recognition_landing import (
    CREATIVE_ENDING_TOOLS_ENABLED,
    LANDING_ENGINE_VERSION,
    select_landing,
)
from response_finalization import (
    CORE_WRITE_DIRECTIVE,
    finalize_response,
    plan_closer_instruction,
    remove_duplicate_paragraphs,
)
from signature_line import body_alone_stronger_or_equal, deletion_test


def test_engine_is_protect_only():
    assert LANDING_ENGINE_VERSION == "protect-only-v1"
    assert CREATIVE_ENDING_TOOLS_ENABLED is False


def test_protect_only_contract_documented():
    """Architectural lock: finalizer contract must stay explicit."""
    from pathlib import Path

    contract = Path("docs/PROTECT_ONLY_FINALIZER.md").read_text(encoding="utf-8")
    assert "prevent a defect" in contract.lower()
    assert "change the writing" in contract.lower()
    assert "infrastructure" in contract.lower()
    import response_finalization as rf

    assert "protect-only-v1" in (rf.__doc__ or "").lower()
    assert "change the writing" in (rf.__doc__ or "").lower()


def test_default_landing_is_body_not_signature():
    d = select_landing("Why did Game of Thrones season 8 fail?", body="Anything.")
    assert d.landing == "BODY_ENDS_RESPONSE"
    assert d.allow_question is False


def test_callback_not_forced_on_default_path():
    d = select_landing("What got stretched out for you?")
    assert d.landing == "BODY_ENDS_RESPONSE"


def test_coherent_draft_ships_untouched():
    """Great Writer Test — coherent body is not rewritten for style."""
    body = (
        "Game of Thrones didn't fail because the characters ended in the wrong places. "
        "It failed because the show stopped earning the distance between cause and consequence.\n\n"
        "For seven seasons, choices created outcomes. In the final season, outcomes arrived first "
        "and character logic was bent backward to reach them.\n\n"
        "Daenerys is the cleanest proof: madness may have been a plausible destination, "
        "but the show skipped the road that would have earned it."
    )
    result = finalize_response(body, "Why did Game of Thrones season 8 fail?")
    assert result.plan.landing == "body_ends_response"
    assert result.diagnostics.get("landing_added") == "false"
    assert result.diagnostics.get("creative_touch") == "false"
    clean = result.text.replace("🥃", "").strip()
    assert "stopped earning" in clean.lower()
    assert "daenerys" in clean.lower()
    assert "enforcers must" not in clean.lower() or "must" in body.lower()
    # No manufactured closer / costume
    assert "moment gratitude" not in clean.lower()
    assert not clean.endswith("?")
    # Prose from the model survives (allow whiskey watermark only)
    assert "skipped the road that would have earned it" in clean.lower()


def test_must_language_not_rewritten_for_style():
    """Finalizer must not rewrite rhetorical 'must' — that is writing, not safety."""
    body = (
        "Once loyalty to one person threatens the narrative, "
        "the enforcers must punish the breach before the example spreads."
    )
    result = finalize_response(body, "Why pick-me?")
    assert "enforcers must punish" in result.text.lower()
    assert "pressure shifts toward punishing" not in result.text.lower()


def test_no_signature_no_cta():
    body = (
        "The 'pick me' label isn't a defense of women. "
        "It's a disciplinary tool that treats public gratitude toward a man "
        "as defection from the collective grievance script."
    )
    with_junk = body + "\n\nDo you want me to unpack this? Say the word."
    result = finalize_response(with_junk, "Why pick-me?")
    assert "do you want" not in result.text.lower()
    assert "say the word" not in result.text.lower()
    assert result.diagnostics.get("landing_added") == "false"


def test_reasonable_inference_survives():
    draft = (
        "Yeah — he's making a move. "
        "The label functions as social enforcement. "
        "The final season stopped earning character change."
    )
    result = finalize_response(draft, "Quick take?")
    lower = result.text.lower()
    assert "making a move" in lower
    assert "social enforcement" in lower
    assert "stopped earning" in lower


def test_hidden_scheme_still_calibrated():
    draft = (
        "He used the lockout kit as a pretext to obtain her number. "
        "He planned this from the beginning."
    )
    result = finalize_response(
        draft,
        "Doorman got her number for a lockout, then sent flowers.",
    )
    lower = result.text.lower()
    assert "pretext" not in lower
    assert "from the beginning" not in lower


def test_duplicate_paragraphs_removed():
    text = "Insight one.\n\nInsight one.\n\nNext point."
    out, changed = remove_duplicate_paragraphs(text)
    assert changed
    assert out.count("Insight one.") == 1
    assert "Next point" in out


def test_stronger_without_last_sentence_counts_as_success():
    body = (
        "Public gratitude toward one man threatens movements "
        "that depend on collective resentment of all men."
    )
    weak = "Public gratitude toward one man threatens movements."
    assert body_alone_stronger_or_equal(body, weak) is True
    assert deletion_test(body, weak) is False


def test_core_write_directive_is_for_generator():
    text = plan_closer_instruction(type("P", (), {
        "landing": "signature_line",
        "needs_practical_action": False,
        "intent": "explore",
    })())
    lower = text.lower()
    assert "proof" in lower
    assert "concrete before abstract" in lower
    assert "translate" in lower
    assert CORE_WRITE_DIRECTIVE


def test_practical_still_action():
    assert select_landing("What should I do about this?").landing == "ACTION"


def test_grief_still_silence():
    assert select_landing("My brother died.", grief=True).landing == "SILENCE"


if __name__ == "__main__":
    test_engine_is_protect_only()
    test_protect_only_contract_documented()
    test_default_landing_is_body_not_signature()
    test_callback_not_forced_on_default_path()
    test_coherent_draft_ships_untouched()
    test_must_language_not_rewritten_for_style()
    test_no_signature_no_cta()
    test_reasonable_inference_survives()
    test_hidden_scheme_still_calibrated()
    test_duplicate_paragraphs_removed()
    test_stronger_without_last_sentence_counts_as_success()
    test_core_write_directive_is_for_generator()
    test_practical_still_action()
    test_grief_still_silence()
    print("All protect-only tests passed.")
