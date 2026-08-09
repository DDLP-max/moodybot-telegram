# -*- coding: utf-8 -*-
"""Signature Line — writer last-sentence regression suite."""

from recognition_landing import LANDING_ENGINE_VERSION, select_landing
from response_finalization import build_response_plan, finalize_response
from signature_line import (
    _RECENT_SIGNATURES,
    adds_deeper_layer,
    body_already_said_this,
    generate_signature_line,
    score_signature_line,
    validate_signature_line,
    word_count,
)


def _clear_recent():
    _RECENT_SIGNATURES.clear()


def test_engine_version():
    assert LANDING_ENGINE_VERSION.startswith("signature-line-")


def test_examples_pass_quality():
    examples = [
        "The moment gratitude becomes betrayal, the argument stopped being about equality.",
        "Boundaries rarely end relationships — they reveal them.",
        "The story started defending itself long before it started defending women.",
        "The backstage explains the stage.",
        "The paper trail is where the performance runs out.",
        "The script usually survives by making disagreement feel like betrayal.",
        "The moment gratitude needs permission, the argument changed.",
    ]
    # Canon lines are judged as reveals against a shallower thesis body
    thesis = "The charge works as ordinary social enforcement inside the group."
    ctx = "feminist gratitude betrayal equality argument pick me boundaries stage paper"
    for ex in examples:
        ok, reason = validate_signature_line(
            ex,
            user_message=ctx,
            body=thesis,
            allow_exceptional_length=True,
            check_novelty=False,
        )
        assert ok, f"{ex} -> {reason}"
        assert word_count(ex) <= 22
        assert body_already_said_this(ex, thesis) is False


def test_rejects_fortune_cookies():
    for bad in (
        "Everything happens for a reason.",
        "Life is complicated.",
        "Truth always wins.",
        "Power corrupts.",
        "In a world where loyalty matters, be careful.",
    ):
        ok, reason = validate_signature_line(bad, check_novelty=False)
        assert ok is False, bad
        assert "REJECTED" in reason


def test_political_analysis_expects_signature_line():
    _clear_recent()
    user = "Why do feminists hate women praising men?"
    assert select_landing(user).landing == "SIGNATURE_LINE"
    draft = (
        "The 'pick me' accusation functions as social enforcement. "
        "Gratitude gets reclassified as betrayal of the cause.\n\n"
        "What about feminists hate woman looks different now that you've seen it named?"
    )
    result = finalize_response(draft, user, mode="dynamic")
    assert result.plan.landing == "signature_line"
    assert "seen it named" not in result.text.lower()
    closer = result.text.strip().split("\n\n")[-1].replace("🥃", "").strip()
    assert not closer.endswith("?")
    body_only = (
        "The 'pick me' accusation functions as social enforcement. "
        "Gratitude gets reclassified as betrayal of the cause."
    )
    assert body_already_said_this(closer, body_only) is False, closer
    assert adds_deeper_layer(closer, body_only) is True, closer
    ok, _ = validate_signature_line(
        closer,
        user_message=user,
        body=body_only,
        allow_exceptional_length=True,
        check_novelty=False,
    )
    assert ok, closer


def test_relationship_analysis_signature_or_action():
    user = "My partner cancels plans and only calls late. What's going on?"
    landing = select_landing(user).landing
    assert landing in {"SIGNATURE_LINE", "ACTION"}
    result = finalize_response(
        "They are treating you as low priority. Convenience over commitment.",
        user,
    )
    assert result.plan.landing in {"signature_line", "action"}


def test_cultural_criticism_expects_signature_line():
    _clear_recent()
    user = "How did porn change the cultural script around dirty talk?"
    assert select_landing(user).landing == "SIGNATURE_LINE"
    plan = build_response_plan(user)
    body = "The language shifted because the reference library exploded. Scripts got louder."
    line = generate_signature_line(plan, body, user_message=user)
    assert line, "expected a deeper Signature Line beyond the thesis body"
    assert body_already_said_this(line, body) is False
    assert adds_deeper_layer(line, body) is True
    q = score_signature_line(line, body=body, user_message=user)
    assert q.ok, q.reasons


def test_technical_no_signature_line():
    user = "Why does this Telegram worker keep dying?"
    assert select_landing(user, technical=True).landing == "SILENCE"
    result = finalize_response(
        "Duplicate getUpdates conflict. Stop the other poller.",
        user,
    )
    # Technical path should not force a literary fingerprint question
    assert "seen it named" not in result.text.lower()
    assert result.plan.landing in {"silence", "signature_line", "action"}
    if result.plan.intent == "technical" or select_landing(user, technical=True).landing == "SILENCE":
        # When technical flag is applied via plan
        plan = build_response_plan(user)
        # build may not mark technical — force via select
        assert select_landing(user, technical=True).landing == "SILENCE"


def test_grief_expects_silence():
    user = "My brother died last week and I can't stop crying."
    assert select_landing(user, grief=True).landing == "SILENCE"


def test_beautiful_metaphor_allows_recognition_callback():
    user = "What got stretched out for you around intimacy?"
    assert select_landing(user).landing == "RECOGNITION_CALLBACK"
    user2 = "I'm still carrying this and it cracked something."
    assert select_landing(user2).landing == "RECOGNITION_CALLBACK"


def test_generate_reacts_to_body_not_slogan():
    user = "Why do feminists treat praise as betrayal?"
    plan = build_response_plan(user)
    plan.central_insight = "gratitude reclassified as defection"
    body = (
        "The pick-me accusation functions as social enforcement. "
        "Once gratitude becomes betrayal, equality is no longer the subject."
    )
    line = generate_signature_line(plan, body, user_message=user)
    assert line
    # Must not be a disconnected fortune cookie
    assert "everything happens" not in line.lower()
    assert "life is complicated" not in line.lower()


def test_quality_specificity_fails_generic():
    q = score_signature_line("Truth always wins.")
    assert q.specificity is False


def test_restating_thesis_fails():
    body = 'The "pick me" charge works as social enforcement.'
    weak = 'The "pick me" charge works as social enforcement.'
    assert body_already_said_this(weak, body) is True
    ok, reason = validate_signature_line(
        weak, body=body, user_message="Why pick me?", check_novelty=False
    )
    assert ok is False
    assert "restates_thesis" in reason or "compression" in reason


def test_deeper_reveal_beats_restatement():
    _clear_recent()
    body = 'The "pick me" charge works as social enforcement of loyalty tests.'
    strong = (
        "The moment gratitude becomes betrayal, "
        "the argument stopped being about equality."
    )
    assert body_already_said_this(strong, body) is False
    assert adds_deeper_layer(strong, body) is True
    plan = build_response_plan("Why do feminists hate women praising men?")
    line = generate_signature_line(
        plan, body, user_message="Why do feminists hate women praising men?"
    )
    # Must not echo the thesis sentence
    assert line
    assert body_already_said_this(line, body) is False
    assert adds_deeper_layer(line, body) is True
    result = finalize_response(
        body + "\n\nWhat about feminists hate woman looks different now that you've seen it named?",
        "Why do feminists hate women praising men?",
        mode="dynamic",
    )
    closer = result.text.strip().split("\n\n")[-1].replace("🥃", "").strip()
    assert closer != body
    assert body_already_said_this(closer, body) is False


def test_boundaries_weak_vs_strong():
    body = "Boundaries reveal relationships."
    weak = "Boundaries matter."
    strong = (
        "Boundaries don't end relationships — "
        "they reveal the ones that were already ending."
    )
    assert validate_signature_line(weak, body=body, check_novelty=False)[0] is False
    ok, _ = validate_signature_line(
        strong,
        body=body,
        user_message="boundaries in relationships",
        allow_exceptional_length=True,
        check_novelty=False,
    )
    assert ok


if __name__ == "__main__":
    test_engine_version()
    test_examples_pass_quality()
    test_rejects_fortune_cookies()
    test_political_analysis_expects_signature_line()
    test_relationship_analysis_signature_or_action()
    test_cultural_criticism_expects_signature_line()
    test_technical_no_signature_line()
    test_grief_expects_silence()
    test_beautiful_metaphor_allows_recognition_callback()
    test_generate_reacts_to_body_not_slogan()
    test_quality_specificity_fails_generic()
    test_restating_thesis_fails()
    test_deeper_reveal_beats_restatement()
    test_boundaries_weak_vs_strong()
    print("All signature line writer tests passed.")
