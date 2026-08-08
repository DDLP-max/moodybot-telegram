# -*- coding: utf-8 -*-
"""Integration: same finalization handler Telegram Dynamic uses after generation."""

from recognition_landing import LANDING_ENGINE_VERSION, validate_landing
from response_finalization import finalize_response


BAD = "What about feminists hate woman looks different now that you've seen it named?"
USER = "Why do feminists hate women praising men?"


def test_validate_landing_rejects_exact_failure():
    ok, reason = validate_landing(BAD)
    assert ok is False
    assert reason.startswith("REJECTED")


def test_telegram_dynamic_handler_strips_malformed_closer():
    draft = (
        "The accusation stops being analysis the moment disagreement becomes evidence.\n\n"
        + BAD
    )
    result = finalize_response(
        draft,
        USER,
        selected_command="/thoughts",
        channel="telegram",
        mode="dynamic",
        prompt_hash="test",
        git_commit="local",
    )
    assert result.diagnostics.get("landing_engine_version") == LANDING_ENGINE_VERSION
    assert "seen it named" not in result.text.lower()
    assert "looks different now that you've seen it named" not in result.text.lower()
    closer = result.text.strip().split("\n\n")[-1].replace("🥃", "").strip()
    assert not closer.endswith("?") or "stretch" in closer.lower()


if __name__ == "__main__":
    test_validate_landing_rejects_exact_failure()
    test_telegram_dynamic_handler_strips_malformed_closer()
    print("Dynamic handler path tests passed.")
