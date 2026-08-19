# -*- coding: utf-8 -*-
"""Token-budget regression — full corpus must never ship to Grok in production."""
from __future__ import annotations

from capability_detection import classify_social_mode
from prompt_runtime import (
    ANALYTICAL_CEILING_TOKENS,
    ANALYTICAL_TARGET_TOKENS,
    FULL_CORPUS_COMPILED,
    SNAP_SOCIAL_CEILING_TOKENS,
    SNAP_SOCIAL_TARGET_TOKENS,
    build_openrouter_messages,
    build_runtime_prompt,
    full_corpus_char_count,
    is_snap_social_plan,
    load_runtime_core,
)
from response_finalization import build_response_plan

BOWLING = (
    "they should invent a woman who wants to go bowling and enjoy a bucket of beer but alas"
)
SANDLER = "Name an actor who immediately makes you NOT want to watch a movie"
SOPRANOS = (
    "i started watching the sopranos and wow how come no one ever told me to watch this"
)
HVAC = "The industrial HVAC hum in the data center is the ocean."
BURNOUT = (
    "I've been in survival mode for so long I don't know how to connect with people anymore. "
    "Every attempt to reach out lands flat. I've forgotten how to socialize. "
    "My hobbies are gone and my personality feels muted."
)


def _runtime_for(msg: str, command: str = "/thoughts"):
    social = classify_social_mode(msg)
    plan = build_response_plan(msg, selected_command=command, tone_source="test")
    return build_runtime_prompt(plan, social=social, selected_command=command), plan


def test_runtime_core_is_stable_and_smaller_than_full_corpus():
    core_a = load_runtime_core()
    core_b = load_runtime_core()
    assert core_a == core_b
    assert len(core_a) < full_corpus_char_count() * 0.2
    assert len(core_a) < 50_000


def test_full_compiled_corpus_never_used_in_runtime_payload():
    corpus_size = full_corpus_char_count()
    assert corpus_size > 200_000, "fixture expects compiled corpus to exist for comparison"
    for msg in (BOWLING, SANDLER, SOPRANOS, HVAC, BURNOUT):
        runtime, _ = _runtime_for(msg)
        assert runtime.total_payload_chars < corpus_size * 0.25
        assert runtime.core_chars < corpus_size * 0.15


def test_message_order_static_core_first():
    runtime, _ = _runtime_for(BOWLING)
    messages = build_openrouter_messages(runtime, BOWLING)
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == runtime.core
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == BOWLING
    # Dynamic guidance must not precede the static core.
    assert not messages[0]["content"].startswith("RUNTIME TURN")


def test_snap_social_token_budget():
    fixtures = [
        ("sandler", SANDLER),
        ("sopranos", SOPRANOS),
        ("bowling", BOWLING),
        ("hvac", HVAC),
    ]
    for name, msg in fixtures:
        runtime, plan = _runtime_for(msg)
        tokens = runtime.estimated_input_tokens(msg)
        assert is_snap_social_plan(plan), f"{name} should classify as snap/social"
        assert tokens <= SNAP_SOCIAL_CEILING_TOKENS, (
            f"{name}: ~{tokens} tokens exceeds ceiling {SNAP_SOCIAL_CEILING_TOKENS}"
        )
        assert tokens <= SNAP_SOCIAL_TARGET_TOKENS * 1.5, (
            f"{name}: ~{tokens} tokens well above target {SNAP_SOCIAL_TARGET_TOKENS}"
        )


def test_analytical_token_budget():
    runtime, plan = _runtime_for(BURNOUT)
    tokens = runtime.estimated_input_tokens(BURNOUT)
    assert not is_snap_social_plan(plan)
    assert tokens <= ANALYTICAL_CEILING_TOKENS, (
        f"burnout: ~{tokens} tokens exceeds ceiling {ANALYTICAL_CEILING_TOKENS}"
    )
    assert tokens <= ANALYTICAL_TARGET_TOKENS * 1.5, (
        f"burnout: ~{tokens} tokens well above target {ANALYTICAL_TARGET_TOKENS}"
    )


def test_plan_runtime_instruction_slimmer_than_legacy_closer():
    from response_finalization import plan_closer_instruction, plan_runtime_instruction

    _, plan = _runtime_for(BOWLING)
    runtime_len = len(plan_runtime_instruction(plan))
    legacy_len = len(plan_closer_instruction(plan))
    assert runtime_len < legacy_len * 0.5
    assert runtime_len < 8_000


if __name__ == "__main__":
    test_runtime_core_is_stable_and_smaller_than_full_corpus()
    test_full_compiled_corpus_never_used_in_runtime_payload()
    test_message_order_static_core_first()
    test_snap_social_token_budget()
    test_analytical_token_budget()
    test_plan_runtime_instruction_slimmer_than_legacy_closer()
    print("ok prompt runtime budget")
