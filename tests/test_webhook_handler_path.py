# -*- coding: utf-8 -*-
"""Webhook message path: OpenRouter no-choices → scrambled fallback."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

import moodybot


class FakeMessage:
    def __init__(self, text="hello"):
        self.text = text
        self.message_id = 10
        self.reply_text = AsyncMock()


class FakeChat:
    def __init__(self):
        self.id = 42
        self.type = "private"


class FakeUser:
    username = "tester"
    id = 7


class FakeUpdate:
    def __init__(self, text="hello"):
        self.update_id = 123456
        self.message = FakeMessage(text)
        self.effective_chat = FakeChat()
        self.effective_user = FakeUser()


def _openrouter_response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status,
        json=body,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


async def _run_handler_with_openrouter(body: dict, status: int = 401):
    update = FakeUpdate()
    context = SimpleNamespace()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=_openrouter_response(status, body))

    with patch.object(moodybot, "OPENROUTER_API_KEY", "test-key"), patch.object(
        moodybot.httpx, "AsyncClient", return_value=mock_client
    ), patch.object(
        moodybot, "load_system_prompt", return_value="sys"
    ), patch.object(
        moodybot, "build_response_plan"
    ) as plan_mock, patch.object(
        moodybot, "plan_closer_instruction", return_value="closer"
    ), patch.object(
        moodybot, "prompt_content_hash", return_value="abc"
    ), patch.object(
        moodybot, "route_command", return_value="/thoughts"
    ), patch.object(
        moodybot, "process_user_input", side_effect=lambda x: x
    ):
        plan = SimpleNamespace(
            closing_strategy="silence",
            intent="x",
            primary_capability="y",
            mode="dynamic",
            preferred_structure="",
            response_budget="medium",
        )
        plan_mock.return_value = plan
        await moodybot.handle_message(update, context)

    return update, mock_client


def test_openrouter_error_sends_scrambled_and_logs_status():
    """Stage C: OpenRouter returns no choices → scrambled message (not exception)."""

    async def _run():
        update, client = await _run_handler_with_openrouter(
            {"error": {"code": 401, "message": "User not found."}},
            status=401,
        )
        assert client.post.await_count == 1
        # Friendly fallback once
        assert update.message.reply_text.await_count == 1
        sent = update.message.reply_text.await_args.args[0]
        assert "signal got scrambled" in sent
        # Telegram AI reply path not used (only simple fallback)
        return True

    assert asyncio.run(_run()) is True


def test_openrouter_success_reaches_telegram_send():
    async def _run():
        body = {
            "choices": [
                {"message": {"role": "assistant", "content": "A real Moody line about the work."}}
            ]
        }
        update = FakeUpdate()
        context = SimpleNamespace()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=_openrouter_response(200, body))

        finalized = SimpleNamespace(
            text="A real Moody line about the work. 🥃",
            diagnostics={"response_budget": "medium"},
        )

        with patch.object(moodybot, "OPENROUTER_API_KEY", "test-key"), patch.object(
            moodybot.httpx, "AsyncClient", return_value=mock_client
        ), patch.object(
            moodybot, "load_system_prompt", return_value="sys"
        ), patch.object(
            moodybot, "build_response_plan"
        ) as plan_mock, patch.object(
            moodybot, "plan_closer_instruction", return_value="closer"
        ), patch.object(
            moodybot, "prompt_content_hash", return_value="abc"
        ), patch.object(
            moodybot, "route_command", return_value="/thoughts"
        ), patch.object(
            moodybot, "process_user_input", side_effect=lambda x: x
        ), patch.object(
            moodybot, "finalize_response", return_value=finalized
        ), patch.object(
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
        ) as send_mock:
            plan = SimpleNamespace(
                closing_strategy="silence",
                intent="x",
                primary_capability="y",
                mode="dynamic",
                preferred_structure="",
                response_budget="medium",
            )
            plan_mock.return_value = plan
            await moodybot.handle_message(update, context)
            assert mock_client.post.await_count == 1
            assert send_mock.await_count == 1
            # scrambled fallback NOT used
            assert update.message.reply_text.await_count == 0

    asyncio.run(_run())


def test_sanitize_openrouter_keeps_error():
    out = moodybot._sanitize_openrouter_payload(
        {"error": {"code": 401, "message": "User not found.", "metadata": {"x": 1}}}
    )
    assert out["error"]["code"] == 401
    assert out["error"]["message"] == "User not found."
    assert "metadata" not in out["error"]
    fields = moodybot._openrouter_error_fields(
        {"error": {"code": 401, "message": "User not found."}, "id": "gen-abc"}
    )
    assert fields["error_code"] == 401
    assert fields["request_id"] == "gen-abc"


def test_payload_diagnostics_static_corpus():
    diag = moodybot._payload_diagnostics(
        core="A" * 1000,
        modules="B" * 200,
        guidance="C" * 50,
        structure_prompt="D" * 25,
        user_input="hello",
    )
    assert diag["core_chars"] == 1000
    assert diag["modules_chars"] == 200
    assert diag["guidance_chars"] == 50
    assert diag["structure_chars"] == 25
    assert diag["current_message_chars"] == 5
    assert diag["number_of_history_messages"] == 0
    assert diag["number_of_system_messages"] == 4
    assert diag["total_payload_chars"] == 1280


def test_openrouter_usage_fields():
    usage = moodybot._openrouter_usage_fields(
        {
            "usage": {
                "prompt_tokens": 72000,
                "completion_tokens": 120,
                "total_tokens": 72120,
                "prompt_tokens_details": {"cached_tokens": 5000},
            }
        }
    )
    assert usage["input_tokens"] == 72000
    assert usage["cached_tokens"] == 5000
    assert usage["output_tokens"] == 120
    assert usage["total_tokens"] == 72120


if __name__ == "__main__":
    test_openrouter_error_sends_scrambled_and_logs_status()
    print("ok scramble")
    test_openrouter_success_reaches_telegram_send()
    print("ok success")
    test_sanitize_openrouter_keeps_error()
    print("ok")
