# -*- coding: utf-8 -*-
"""Body-can-be-the-landing — preferred ending is stop writing."""

from recognition_landing import LANDING_ENGINE_VERSION, apply_landing, select_landing
from response_finalization import (
    build_response_plan,
    finalize_response,
    run_epistemic_check,
)
from signature_line import (
    _RECENT_SIGNATURES,
    body_already_lands,
    body_already_said_this,
    body_alone_stronger_or_equal,
    deletion_test,
    discover_signature_line,
    has_terminal_rhythm,
    is_semantically_redundant,
    is_shorter_paraphrase,
    score_discovery,
    validate_signature_line,
)

PICK_ME_BODY = (
    "The 'pick me' label isn't a defense of women. "
    "It's a disciplinary tool that treats any public gratitude toward a man "
    "as defection from the collective grievance script. "
    "Once loyalty to one person threatens the narrative that all men are net subtractive, "
    "the enforcers must punish the breach before the example spreads."
)


def _clear():
    _RECENT_SIGNATURES.clear()


def test_engine_version():
    assert LANDING_ENGINE_VERSION == "minimal-write-v1"


def test_body_can_end_response():
    """Acceptance — strong body ships untouched as BODY_ENDS_RESPONSE."""
    _clear()
    assert has_terminal_rhythm(
        "the enforcers must punish the breach before the example spreads."
    )
    assert body_already_lands(PICK_ME_BODY) is True
    d = select_landing(
        "Why do feminists hate women praising men?",
        body=PICK_ME_BODY,
    )
    assert d.landing == "BODY_ENDS_RESPONSE"
    result = finalize_response(PICK_ME_BODY, "Why do feminists hate women praising men?")
    assert result.plan.landing == "body_ends_response"
    # No Signature Line / second insight paragraph appended
    clean = result.text.replace("🥃", "").strip()
    assert "moment gratitude becomes betrayal" not in clean.lower()
    assert "argument stopped being about equality" not in clean.lower()
    # Terminal cadence survives (possibly after coordinated-must calibration)
    assert "before the example spreads" in clean.lower()
    # Body landing is the final sentence
    last = [s.strip() for s in clean.replace("\n", " ").split(".") if s.strip()][-1]
    assert "spreads" in last.lower() or "example" in last.lower()


def test_signature_rejected_when_shorter_paraphrase():
    body = (
        "Public gratitude toward one man threatens movements "
        "that depend on collective resentment of all men."
    )
    weak = "Public gratitude toward one man threatens movements."
    assert is_shorter_paraphrase(weak, body) is True
    assert body_already_said_this(weak, body) is True
    assert deletion_test(body, weak) is False
    assert body_alone_stronger_or_equal(body, weak) is True


def test_signature_rejected_when_semantically_redundant():
    body = (
        "The 'pick me' charge works as social enforcement, not protection. "
        "Public gratitude toward one man threatens movements that depend on "
        "collective resentment."
    )
    weak = "Public gratitude toward one man threatens movements."
    assert is_semantically_redundant(weak, body) is True
    assert deletion_test(body, weak) is False


def test_signature_accepted_when_new_insight():
    """Thin body + new abstraction layer may pass deletion (still rare)."""
    _clear()
    body = "The accusation works as social enforcement."
    strong = (
        "The moment gratitude becomes betrayal, "
        "the argument stopped being about equality."
    )
    assert body_already_lands(body) is False
    assert body_already_said_this(strong, body) is False
    assert is_semantically_redundant(strong, body) is False
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


def test_no_question_after_strong_body():
    _clear()
    result = finalize_response(PICK_ME_BODY, "Why do feminists hate women praising men?")
    assert result.plan.landing == "body_ends_response"
    assert not result.plan.allow_question
    # No trailing question paragraph
    paras = [p.strip() for p in result.text.replace("🥃", "").strip().split("\n\n") if p.strip()]
    assert not any(p.endswith("?") for p in paras)
    assert "what about" not in result.text.lower()
    assert "seen it named" not in result.text.lower()


def test_no_cta_after_strong_body():
    _clear()
    with_cta = (
        PICK_ME_BODY
        + "\n\nDo you want me to break this down further? Say the word."
    )
    result = finalize_response(with_cta, "Why do feminists hate women praising men?")
    assert result.plan.landing == "body_ends_response"
    lower = result.text.lower()
    assert "do you want" not in lower
    assert "say the word" not in lower
    assert "before the example spreads" in lower


def test_reasonable_inference_survives_finalization():
    draft = (
        "Yeah — he's making a move. "
        "The label functions as social enforcement. "
        "That behavior is protecting the narrative."
    )
    result = finalize_response(
        draft,
        "A woman praised her husband publicly and got called a pick-me. Why?",
    )
    lower = result.text.lower()
    assert "making a move" in lower
    assert "social enforcement" in lower
    assert "protecting the narrative" in lower
    assert "may possibly" not in lower
    assert "one might argue" not in lower


def test_remote_hidden_motive_still_calibrated():
    draft = (
        "He used the lockout kit as a pretext to obtain her number. "
        "He planned this from the beginning."
    )
    text, changed = run_epistemic_check(
        draft,
        build_response_plan(
            "A woman gave the doorman her number for lockout reasons. "
            "He later sent flowers."
        ),
    )
    assert changed
    lower = text.lower()
    assert "pretext" not in lower
    assert "from the beginning" not in lower


def test_coordinated_must_calibrated_without_killing_landing():
    """'must punish' coordinated necessity softens; body still ends response."""
    _clear()
    result = finalize_response(PICK_ME_BODY, "Why pick-me?")
    assert result.plan.landing == "body_ends_response"
    lower = result.text.lower()
    assert "before the example spreads" in lower
    # Coordinated necessity rewrite should fire
    assert "enforcers must punish" not in lower
    assert "pressure shifts toward punishing" in lower or "punish" in lower


def test_body_already_lands_no_signature():
    _clear()
    body = (
        "The 'pick me' charge works as social enforcement, not protection. "
        "Public gratitude toward one man threatens movements that depend on collective resentment."
    )
    assert body_already_lands(body) is True
    assert select_landing("Why?", body=body).landing == "BODY_ENDS_RESPONSE"
    line = discover_signature_line(build_response_plan("Why?"), body, user_message="Why?")
    assert line is None


def test_fortune_cookies_rejected():
    for bad in (
        "Power corrupts.",
        "Truth wins.",
        "Gratitude matters.",
        "Movements need enemies.",
    ):
        ok, _ = validate_signature_line(bad, body="Some analysis about power.", check_novelty=False)
        assert ok is False, bad


def test_grief_silence():
    assert select_landing("My brother died.", grief=True).landing == "SILENCE"


def test_callback_not_forced_by_default():
    # Creative ending tools are OFF — distinctive language does not force a callback
    assert select_landing("What got stretched out for you?").landing == "BODY_ENDS_RESPONSE"


def test_apply_body_ends_strips_fake_closer():
    text = (
        "The charge works as social enforcement of group loyalty tests.\n\n"
        "What about feminists hate woman looks different now that you've seen it named?"
    )
    decision = select_landing(
        "Why pick me?",
        body="The charge works as social enforcement of group loyalty tests.",
    )
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
    test_body_can_end_response()
    test_signature_rejected_when_shorter_paraphrase()
    test_signature_rejected_when_semantically_redundant()
    test_signature_accepted_when_new_insight()
    test_no_question_after_strong_body()
    test_no_cta_after_strong_body()
    test_reasonable_inference_survives_finalization()
    test_remote_hidden_motive_still_calibrated()
    test_coordinated_must_calibrated_without_killing_landing()
    test_body_already_lands_no_signature()
    test_fortune_cookies_rejected()
    test_grief_silence()
    test_callback_not_forced_by_default()
    test_apply_body_ends_strips_fake_closer()
    print("All body-landing tests passed.")
