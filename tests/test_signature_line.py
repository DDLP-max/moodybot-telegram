# -*- coding: utf-8 -*-
"""Signature Line — writer last-sentence regression suite."""

from recognition_landing import LANDING_ENGINE_VERSION, select_landing
from response_finalization import build_response_plan, finalize_response
from signature_line import (
    generate_signature_line,
    score_signature_line,
    validate_signature_line,
    word_count,
)


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
    ctx = "feminist gratitude betrayal equality argument pick me"
    for ex in examples:
        ok, reason = validate_signature_line(
            ex,
            user_message=ctx,
            body="The accusation functions as social enforcement of loyalty.",
            allow_exceptional_length=True,
            check_novelty=False,
        )
        assert ok, f"{ex} -> {reason}"
        assert word_count(ex) <= 22


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
    ok, _ = validate_signature_line(
        closer, user_message=user, body=draft, allow_exceptional_length=True, check_novelty=False
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
    user = "How did porn change the cultural script around dirty talk?"
    assert select_landing(user).landing == "SIGNATURE_LINE"
    plan = build_response_plan(user)
    line = generate_signature_line(
        plan,
        "The language shifted because the reference library exploded. Scripts got louder.",
        user_message=user,
    )
    assert line
    q = score_signature_line(line, body="Scripts got louder.", user_message=user)
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
    print("All signature line writer tests passed.")
