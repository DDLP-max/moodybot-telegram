# -*- coding: utf-8 -*-
"""authored_interior is a generation reject-once, not a finalizer rewrite."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

import moodybot
from generation_gate import (
    AUTHORED_INTERIOR_RETRY,
    CONSERVATIVE_FALLBACK,
    reject_reason,
    retry_messages,
    settle_authored_interior,
)
from gold_shape import apply_gold_shape_pass
from response_finalization import finalize_response

ENDGAME = (
    "I genuinely don't get the endgame. If the plan ends with a ruined planet, "
    "collapsed economies, and no working class left to spend money... what are "
    "billionaires actually hoarding wealth for? To sit in a bunker with numbers "
    "on a screen that don't mean anything anymore? What is the actual point?"
)
ENDGAME_COMPRESSED = (
    "The confusion hits because the numbers were never supposed to survive "
    "the collapse. They just had to stay bigger than the next guy's until the "
    "lights went out. That's the only scoreboard that still registers when "
    "everything else stops making sense. 🥃"
)
ENDGAME_SCORE_PASS = (
    "Hard to call it winning when your endgame deletes the economy keeping score. 🥃"
)
TEXTS = "He texts you every night but somehow never has time to see you."
TEXTS_AUTHORED = "He likes knowing you're waiting for him. 🥃"


def test_evaluator_marks_compressed_status_hunger():
    reason = reject_reason(ENDGAME, ENDGAME_COMPRESSED, "SNAP")
    assert reason == AUTHORED_INTERIOR_RETRY
    assert reason.startswith("REJECTED: authored_interior.")
    assert "unestablished private motive" in reason
    assert "rhetorical why" in reason


def test_retry_instruction_is_surgical_not_a_law_dump():
    assert "billionaire" not in AUTHORED_INTERIOR_RETRY.lower()
    assert len(AUTHORED_INTERIOR_RETRY) < 400
    assert reject_reason(TEXTS, TEXTS_AUTHORED, "SNAP") == AUTHORED_INTERIOR_RETRY


def test_scoreboard_object_heat_is_not_rejected():
    assert reject_reason(ENDGAME, ENDGAME_SCORE_PASS, "SNAP") is None


def test_addiction_telos_is_rejected_portfolio_is_not():
    addiction = (
        "It's the same quiet addiction that never needed a finish line. You keep "
        "stacking the chips because the moment you stop counting is the moment you "
        "have to admit the game was only ever the counting. 🥃"
    )
    portfolio = (
        "Pretty impressive portfolio if the final asset is a bunker in an economy "
        "that no longer exists. 🥃"
    )
    assert reject_reason(ENDGAME, addiction, "SNAP") == AUTHORED_INTERIOR_RETRY
    assert reject_reason(ENDGAME, portfolio, "SNAP") is None
    text, source = settle_authored_interior(ENDGAME, addiction, addiction)
    assert source == "fallback"
    assert text == CONSERVATIVE_FALLBACK


def test_retry_instruction_does_not_feed_back_the_draft():
    messages = [{"role": "user", "content": ENDGAME}]
    out = retry_messages(messages, AUTHORED_INTERIOR_RETRY)
    assert out[0] == messages[0]
    assert out[-1]["role"] == "system"
    assert out[-1]["content"] == AUTHORED_INTERIOR_RETRY
    assert ENDGAME_COMPRESSED not in out[-1]["content"]


def test_settle_ships_first_when_valid():
    text, source = settle_authored_interior(ENDGAME, ENDGAME_SCORE_PASS)
    assert source == "first"
    assert text == ENDGAME_SCORE_PASS


def test_settle_ships_retry_when_first_fails():
    text, source = settle_authored_interior(
        ENDGAME, ENDGAME_COMPRESSED, ENDGAME_SCORE_PASS
    )
    assert source == "retry"
    assert "keeping score" in text.lower()


def test_settle_falls_back_when_retry_still_authored():
    text, source = settle_authored_interior(
        ENDGAME, ENDGAME_COMPRESSED, ENDGAME_COMPRESSED
    )
    assert source == "fallback"
    assert text == CONSERVATIVE_FALLBACK
    assert reject_reason(ENDGAME, text, "SNAP") is None
    assert reject_reason(TEXTS, text, "SNAP") is None


def test_settle_falls_back_when_retry_missing():
    text, source = settle_authored_interior(ENDGAME, ENDGAME_COMPRESSED, None)
    assert source == "fallback"
    assert text == CONSERVATIVE_FALLBACK


def test_finalizer_does_not_rewrite_authored_interior():
    result = finalize_response(ENDGAME_COMPRESSED, ENDGAME)
    assert "stay bigger" in result.text.lower()
    assert result.diagnostics.get("quality_rewrite_triggered") == "false"


def test_gold_does_not_compress_authored_interior():
    out, report = apply_gold_shape_pass(
        ENDGAME, ENDGAME_COMPRESSED, preferred_structure="SNAP"
    )
    assert report.quality_rewrite_triggered is False
    assert "authored_interior" in report.quality_failures
    assert "stay bigger" in out.lower()


def _openrouter_response(status: int, content: str) -> httpx.Response:
    return httpx.Response(
        status,
        json={"choices": [{"message": {"role": "assistant", "content": content}}]},
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


def _run_handler(first: str, second: str, finalized_text: str):
    async def _run():
        update = SimpleNamespace(
            update_id=99,
            message=SimpleNamespace(
                text=ENDGAME,
                message_id=1,
                reply_text=AsyncMock(),
            ),
            effective_chat=SimpleNamespace(id=42, type="private"),
            effective_user=SimpleNamespace(username="matt", id=7),
        )
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            side_effect=[
                _openrouter_response(200, first),
                _openrouter_response(200, second),
            ]
        )
        finalized = SimpleNamespace(
            text=finalized_text,
            diagnostics={"response_budget": "medium"},
        )
        with patch.object(moodybot, "OPENROUTER_API_KEY", "test-key"), patch.object(
            moodybot.httpx, "AsyncClient", return_value=mock_client
        ), patch.object(
            moodybot, "route_command", return_value="/thoughts"
        ), patch.object(
            moodybot, "process_user_input", side_effect=lambda x: x
        ), patch.object(
            moodybot, "finalize_response", return_value=finalized
        ) as finalize_mock, patch.object(
            moodybot, "process_bot_output", side_effect=lambda x: x
        ), patch.object(
            moodybot, "polish_sentences", side_effect=lambda x: x
        ), patch.object(
            moodybot, "clean_response", side_effect=lambda x: x
        ), patch.object(
            moodybot, "safe_emoji", side_effect=lambda x: x
        ), patch.object(
            moodybot, "detect_category", return_value="general"
        ), patch.object(
            moodybot, "replace_category_descriptors", side_effect=lambda t, c: t
        ), patch.object(
            moodybot, "log_interaction"
        ), patch.object(
            moodybot, "resolve_mode", return_value="dynamic"
        ), patch.object(
            moodybot, "send_message", new_callable=AsyncMock
        ) as send_mock, patch(
            "inspector.store.record_event"
        ):
            await moodybot.handle_message(update, SimpleNamespace())
            return mock_client, finalize_mock, finalized, send_mock

    return asyncio.run(_run())


def test_handler_rejects_authored_interior_once_and_ships_retry():
    client, finalize_mock, finalized, send_mock = _run_handler(
        ENDGAME_COMPRESSED, ENDGAME_SCORE_PASS, ENDGAME_SCORE_PASS
    )
    assert client.post.await_count == 2
    retry_payload = client.post.await_args_list[1].kwargs["json"]
    retry_text = " ".join(
        m["content"] for m in retry_payload["messages"] if m.get("content")
    )
    assert AUTHORED_INTERIOR_RETRY in retry_text
    assert ENDGAME_COMPRESSED not in retry_text
    shipped = finalize_mock.call_args.args[0]
    assert "keeping score" in shipped.lower()
    assert "stay bigger" not in shipped.lower()
    assert finalized.diagnostics["generation_retry"] == "true"
    assert finalized.diagnostics["generation_reject"] == "authored_interior"
    assert finalized.diagnostics["generation_settle"] == "retry"
    assert send_mock.await_count == 1


def test_handler_ships_fallback_when_retry_still_violates():
    client, finalize_mock, finalized, send_mock = _run_handler(
        ENDGAME_COMPRESSED, ENDGAME_COMPRESSED, CONSERVATIVE_FALLBACK
    )
    assert client.post.await_count == 2
    shipped = finalize_mock.call_args.args[0]
    assert shipped == CONSERVATIVE_FALLBACK
    assert "stay bigger" not in shipped.lower()
    assert finalized.diagnostics["generation_settle"] == "fallback"
    assert finalized.diagnostics["generation_reject"] == "authored_interior"
    assert send_mock.await_count == 1


if __name__ == "__main__":
    test_evaluator_marks_compressed_status_hunger()
    print("ok reject reason")
    test_retry_instruction_is_surgical_not_a_law_dump()
    print("ok surgical")
    test_scoreboard_object_heat_is_not_rejected()
    print("ok pass")
    test_addiction_telos_is_rejected_portfolio_is_not()
    print("ok addiction telos")
    test_retry_instruction_does_not_feed_back_the_draft()
    print("ok discard draft")
    test_settle_ships_first_when_valid()
    print("ok settle first")
    test_settle_ships_retry_when_first_fails()
    print("ok settle retry")
    test_settle_falls_back_when_retry_still_authored()
    print("ok settle fallback")
    test_settle_falls_back_when_retry_missing()
    print("ok settle missing")
    test_finalizer_does_not_rewrite_authored_interior()
    print("ok finalizer")
    test_gold_does_not_compress_authored_interior()
    print("ok gold")
    test_handler_rejects_authored_interior_once_and_ships_retry()
    print("ok handler retry")
    test_handler_ships_fallback_when_retry_still_violates()
    print("ok handler fallback")
    print("ok")
