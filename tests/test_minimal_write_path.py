# -*- coding: utf-8 -*-
"""Minimal write path — protective finalizer, insight-first, no forced endings."""

from recognition_landing import (
    CREATIVE_ENDING_TOOLS_ENABLED,
    LANDING_ENGINE_VERSION,
    select_landing,
)
from response_finalization import (
    CORE_WRITE_DIRECTIVE,
    finalize_response,
    looks_like_plot_inventory,
    looks_like_thesis_proof,
    plan_closer_instruction,
)
from signature_line import body_alone_stronger_or_equal, deletion_test


def test_engine_is_minimal_write():
    assert LANDING_ENGINE_VERSION == "minimal-write-v1"
    assert CREATIVE_ENDING_TOOLS_ENABLED is False


def test_default_landing_is_body_not_signature():
    d = select_landing("Why did Game of Thrones season 8 fail?", body="Anything.")
    assert d.landing == "BODY_ENDS_RESPONSE"
    assert d.allow_question is False


def test_callback_not_forced_on_default_path():
    d = select_landing("What got stretched out for you?")
    assert d.landing == "BODY_ENDS_RESPONSE"


def test_no_signature_appended_to_complete_body():
    body = (
        "Game of Thrones didn't fail because the characters ended in the wrong places. "
        "It failed because the show stopped earning the distance between cause and consequence.\n\n"
        "For seven seasons, choices created outcomes. In the final season, outcomes arrived first "
        "and character logic was bent backward to reach them.\n\n"
        "Daenerys is the cleanest example: madness may have been a plausible destination, "
        "but the show skipped the road."
    )
    result = finalize_response(body, "Why did Game of Thrones season 8 fail?")
    assert result.plan.landing == "body_ends_response"
    assert result.diagnostics.get("landing_added") == "false"
    assert "moment gratitude" not in result.text.lower()
    assert not result.text.rstrip().endswith("?")
    # Body should ship essentially intact
    assert "stopped earning" in result.text.lower()
    assert "daenerys" in result.text.lower()


def test_got_inventory_shape_is_not_required_by_finalizer():
    """Finalizer must not invent a pattern thesis for a plot inventory draft.

    Generation prompt owns insight-first; finalizer stays protective.
    """
    inventory = (
        "Game of Thrones stands as the clearest case. After seven seasons of intricate plotting, "
        "the final season compressed years of character logic into six rushed episodes.\n\n"
        "Daenerys's arc collapsed from liberator to tyrant in a single scene. "
        "Jon Snow's entire journey resolved in exile. Bran's ascension made no thematic sense."
    )
    assert looks_like_plot_inventory(inventory) is True
    result = finalize_response(inventory, "Why did season 8 fail?")
    assert result.diagnostics.get("landing_added") == "false"
    assert result.diagnostics.get("plot_inventory_risk") == "true"
    # Must not append fake profound Instagram closer
    assert "power protects itself" not in result.text.lower()
    assert "stories defend themselves" not in result.text.lower()


def test_got_thesis_proof_shape_passes():
    """Regression: thesis → proof, not plot inventory."""
    body = (
        "Game of Thrones didn't fail because the characters ended in the wrong places. "
        "It failed because the show stopped earning the distance between cause and consequence.\n\n"
        "For seven seasons, choices created outcomes. In the final season, outcomes arrived first "
        "and character logic was bent backward to reach them.\n\n"
        "Daenerys is the cleanest proof: madness may have been a plausible destination, "
        "but the show skipped the road that would have earned it."
    )
    assert looks_like_plot_inventory(body) is False
    assert looks_like_thesis_proof(body) is True
    result = finalize_response(body, "Why did Game of Thrones season 8 fail?")
    assert result.diagnostics.get("landing_added") == "false"
    assert result.diagnostics.get("thesis_proof_shape") == "true"
    assert result.diagnostics.get("plot_inventory_risk") == "false"
    assert not result.text.rstrip().endswith("?")
    # No forced closer appended
    assert result.text.replace("🥃", "").strip().endswith("earned it.") or (
        "skipped the road" in result.text.lower()
    )


def test_write_directive_requires_proof_not_recap():
    lower = CORE_WRITE_DIRECTIVE.lower()
    assert "thesis" in lower and "proof" in lower
    assert "plot summary" in lower
    assert "governing pattern" in lower or "mechanism" in lower
    assert "one excellent proof" in lower


def test_no_cta_no_question_forced():
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


def test_stronger_without_last_sentence_counts_as_success():
    body = (
        "Public gratitude toward one man threatens movements "
        "that depend on collective resentment of all men."
    )
    weak = "Public gratitude toward one man threatens movements."
    assert body_alone_stronger_or_equal(body, weak) is True
    assert deletion_test(body, weak) is False


def test_core_write_directive_is_insight_first():
    text = plan_closer_instruction(type("P", (), {
        "landing": "signature_line",
        "needs_practical_action": False,
        "intent": "explore",
    })())
    lower = text.lower()
    assert "interesting true thing" in lower
    assert "proof" in lower
    assert "signature line" in lower
    assert "plot summary" in lower


def test_practical_still_action():
    assert select_landing("What should I do about this?").landing == "ACTION"


def test_grief_still_silence():
    assert select_landing("My brother died.", grief=True).landing == "SILENCE"


if __name__ == "__main__":
    test_engine_is_minimal_write()
    test_default_landing_is_body_not_signature()
    test_callback_not_forced_on_default_path()
    test_no_signature_appended_to_complete_body()
    test_got_inventory_shape_is_not_required_by_finalizer()
    test_got_thesis_proof_shape_passes()
    test_write_directive_requires_proof_not_recap()
    test_no_cta_no_question_forced()
    test_reasonable_inference_survives()
    test_hidden_scheme_still_calibrated()
    test_stronger_without_last_sentence_counts_as_success()
    test_core_write_directive_is_insight_first()
    test_practical_still_action()
    test_grief_still_silence()
    print("All minimal-write tests passed.")
