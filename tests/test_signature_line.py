# -*- coding: utf-8 -*-
"""Earned endings — inevitable, not mandatory mic-drops."""

from recognition_landing import LANDING_ENGINE_VERSION, apply_landing, select_landing
from response_finalization import build_response_plan, finalize_response
from signature_line import (
    _RECENT_SIGNATURES,
    body_already_lands,
    body_already_said_this,
    deletion_test,
    discover_signature_line,
    score_discovery,
    validate_signature_line,
)


def _clear():
    _RECENT_SIGNATURES.clear()


def test_engine_version():
    assert LANDING_ENGINE_VERSION == "earned-ending-v1"


def test_body_already_lands_no_signature():
    """Test 1 — body already lands → no Signature Line."""
    _clear()
    body = (
        "The 'pick me' charge works as social enforcement, not protection. "
        "Public gratitude toward one man threatens movements that depend on collective resentment."
    )
    assert body_already_lands(body) is True
    d = select_landing(
        "Why do feminists hate women praising men?",
        body=body,
    )
    assert d.landing == "BODY_ENDS_RESPONSE"
    result = finalize_response(body, "Why do feminists hate women praising men?")
    assert result.plan.landing == "body_ends_response"
    # No extra manufactured paragraph
    assert result.text.replace("🥃", "").strip().count("\n\n") == 0 or (
        "moment gratitude" not in result.text.lower()
    )


def test_restatement_rejected():
    """Test 2 — signature repeats thesis → rejected."""
    body = "The 'pick me' charge works as social enforcement."
    weak = "The 'pick me' charge works as social enforcement, not protection."
    assert body_already_said_this(weak, body) is True
    assert deletion_test(body, weak) is False
    ok, reason = validate_signature_line(weak, body=body, check_novelty=False)
    assert ok is False


def test_shortening_rejected():
    """Test 3 — signature merely shortens body → rejected."""
    body = (
        "Public gratitude toward one man threatens movements "
        "that depend on collective resentment."
    )
    weak = "Public gratitude toward one man threatens movements."
    assert body_already_said_this(weak, body) is True
    assert deletion_test(body, weak) is False


def test_higher_order_insight_accepted():
    """Test 4 — higher-order insight can be accepted when body has not landed."""
    _clear()
    # Thin body — explains, does not yet land at the higher order
    body = "The accusation functions as a loyalty test inside the group."
    # This body may or may not "land" depending on signals — force discovery path
    strong = (
        "The moment gratitude becomes betrayal, "
        "the argument stopped being about equality."
    )
    assert body_already_said_this(strong, body) is False
    assert deletion_test(body, strong) is True
    disc = score_discovery(
        strong,
        body=body,
        user_message="Why do feminists hate women praising men?",
    )
    assert disc.ok, disc.reasons
    ok, _ = validate_signature_line(
        strong,
        body=body,
        user_message="Why do feminists hate women praising men?",
        allow_exceptional_length=True,
        check_novelty=False,
    )
    assert ok


def test_deletion_improves_means_body_ends():
    """Test 5 — if deleting signature improves response → BODY_ENDS_RESPONSE."""
    _clear()
    body = (
        "The 'pick me' charge works as social enforcement of loyalty. "
        "Gratitude gets reclassified as betrayal of the cause."
    )
    # Body already has the complete argument
    assert body_already_lands(body)
    line = discover_signature_line(
        build_response_plan("Why do feminists hate women praising men?"),
        body,
        user_message="Why do feminists hate women praising men?",
    )
    assert line is None  # NO_SIGNATURE_FOUND


def test_fortune_cookies_rejected():
    for bad in (
        "Power corrupts.",
        "Truth wins.",
        "Gratitude matters.",
        "Movements need enemies.",
        "Everything changes.",
        "Stories protect themselves.",
    ):
        ok, _ = validate_signature_line(bad, body="Some analysis about power.", check_novelty=False)
        assert ok is False, bad


def test_grief_silence():
    assert select_landing("My brother died.", grief=True).landing == "SILENCE"


def test_callback_still_special():
    assert select_landing("What got stretched out for you?").landing == "RECOGNITION_CALLBACK"


def test_apply_body_ends_strips_fake_closer():
    text = (
        "The charge works as social enforcement of group loyalty tests.\n\n"
        "What about feminists hate woman looks different now that you've seen it named?"
    )
    decision = select_landing(
        "Why pick me?",
        body="The charge works as social enforcement of group loyalty tests.",
    )
    # With landing body, prefer BODY_ENDS or discovery
    out, _ = apply_landing(
        text,
        "Why pick me?",
        decision if decision.landing != "SIGNATURE_LINE" else type(decision)(
            "BODY_ENDS_RESPONSE", False, "test"
        ),
    )
    assert "seen it named" not in out.lower()


if __name__ == "__main__":
    test_engine_version()
    test_body_already_lands_no_signature()
    test_restatement_rejected()
    test_shortening_rejected()
    test_higher_order_insight_accepted()
    test_deletion_improves_means_body_ends()
    test_fortune_cookies_rejected()
    test_grief_silence()
    test_callback_still_special()
    test_apply_body_ends_strips_fake_closer()
    print("All earned-ending tests passed.")
