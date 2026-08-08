# -*- coding: utf-8 -*-
"""Rhetorical callback tests — signature language, not semantic reflection."""

from response_finalization import (
    build_response_plan,
    finalize_response,
    generate_recognition_callback,
    validate_recognition_callback_quality,
)
from signature_language import (
    belongs_only_to_this_conversation,
    extract_signature_language,
    transform_signature_callback,
    uses_synonym_destruction,
)


def test_stretch_fails_semantic_synonyms():
    user = "What got stretched out for you?"
    signatures = extract_signature_language(user)
    assert any(p.stem == "stretch" for p in signatures.phrases if p.protected)

    for bad in (
        "What changed for you?",
        "What shifted for you?",
        "What changed in your sense of intimacy?",
        "What part felt familiar?",
    ):
        assert belongs_only_to_this_conversation(bad, signatures) is False
        assert uses_synonym_destruction(bad, signatures) is True or "stretch" not in bad.lower()


def test_stretch_pass_rhetorical_echo():
    user = "What got stretched out for you?"
    signatures = extract_signature_language(user)
    for good in (
        "So what actually got stretched out in you reading that?",
        "So what actually got stretched out for you?",
        "What part of your definition got stretched furthest?",
    ):
        assert belongs_only_to_this_conversation(good, signatures) is True
        assert uses_synonym_destruction(good, signatures) is False


def test_generate_callback_preserves_stretch():
    user = "What got stretched out for you?"
    plan = build_response_plan(user)
    cb = generate_recognition_callback(user, plan)
    assert "stretch" in cb.lower()
    assert "what changed" not in cb.lower()
    assert "what shifted" not in cb.lower()


def test_finalize_rewrites_semantic_closer_to_rhetorical():
    user = "What got stretched out for you?"
    draft = (
        "Here is the insight about intimacy and language.\n\n"
        "What changed in your sense of the topic?"
    )
    result = finalize_response(draft, user)
    closer = result.text.strip().split("\n\n")[-1].lower().replace("🥃", "").strip()
    assert "stretch" in closer
    assert not closer.startswith("what changed")
    assert "what shifted" not in closer
    assert "seen it named" not in closer


def test_carrying_callback():
    user = "I feel like I'm carrying this."
    cb = generate_recognition_callback(user, build_response_plan(user))
    assert "carrying" in cb.lower()


def test_cracked_callback():
    user = "This cracked something."
    cb = generate_recognition_callback(user, build_response_plan(user))
    assert "crack" in cb.lower()


def test_room_callback():
    user = "The room changed."
    cb = generate_recognition_callback(user, build_response_plan(user))
    assert "room" in cb.lower()


def test_quality_gate_rejects_synonym_destruction():
    user = "What got stretched out for you?"
    plan = build_response_plan(user)
    checks = validate_recognition_callback_quality(
        "What changed in your sense of intimacy?",
        user,
        plan,
    )
    assert checks["no_synonym_destruction"] is False or checks["rhetorical"] is False
    assert checks["anchor"] is False


def test_transform_uses_construction():
    sig = extract_signature_language("What got stretched out for you?")
    cb = transform_signature_callback(sig)
    assert cb and "stretch" in cb.lower()


if __name__ == "__main__":
    test_stretch_fails_semantic_synonyms()
    test_stretch_pass_rhetorical_echo()
    test_generate_callback_preserves_stretch()
    test_finalize_rewrites_semantic_closer_to_rhetorical()
    test_carrying_callback()
    test_cracked_callback()
    test_room_callback()
    test_quality_gate_rejects_synonym_destruction()
    test_transform_uses_construction()
    print("All rhetorical callback tests passed.")
