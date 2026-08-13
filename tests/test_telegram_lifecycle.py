# -*- coding: utf-8 -*-
"""Webhook transport tests — no production getUpdates / start_polling."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from unittest.mock import AsyncMock

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from telegram_lifecycle import (
    READY,
    SECRET_HEADER,
    SHUTTING_DOWN,
    STARTING,
    WEBHOOK_PATH,
    BotRuntime,
    SecretRedactFilter,
    install_log_redaction,
    reset_runtime,
)

ROOT = Path(__file__).resolve().parents[1]


class RecordingLog:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []

    def _fmt(self, msg, args):
        try:
            return msg % args if args else str(msg)
        except TypeError:
            return str(msg)

    def info(self, msg, *a, **k):
        self.infos.append(self._fmt(msg, a))

    def warning(self, msg, *a, **k):
        self.warnings.append(self._fmt(msg, a))

    def error(self, msg, *a, **k):
        self.errors.append(self._fmt(msg, a))


class FakeBot:
    def __init__(self):
        self.set_webhook_calls = 0
        self.last_webhook = None
        self.get_updates_calls = 0

    async def set_webhook(self, **kwargs):
        self.set_webhook_calls += 1
        self.last_webhook = kwargs
        return True

    async def get_updates(self, **kwargs):
        self.get_updates_calls += 1
        return []


class FakeUpdater:
    def __init__(self):
        self.running = False
        self.start_polling_calls = 0
        self.stop_calls = 0

    async def start_polling(self, **kwargs):
        self.start_polling_calls += 1
        self.running = True

    async def stop(self):
        self.stop_calls += 1
        self.running = False


class FakeApp:
    def __init__(self):
        self.bot = FakeBot()
        self.updater = FakeUpdater()
        self.initialize_calls = 0
        self.start_calls = 0
        self.stop_calls = 0
        self.shutdown_calls = 0
        self.processed = []
        self.process_update = AsyncMock(side_effect=self._proc)

    async def _proc(self, update):
        self.processed.append(update)

    async def initialize(self):
        self.initialize_calls += 1

    async def start(self):
        self.start_calls += 1

    async def stop(self):
        self.stop_calls += 1

    async def shutdown(self):
        self.shutdown_calls += 1


def _runtime_webhook(log, **kwargs):
    reset_runtime()
    kwargs.setdefault("install_signals", False)
    kwargs.setdefault("instance_id", "wh-test-1")
    kwargs.setdefault("mode", "webhook")
    kwargs.setdefault("webhook_base", "https://example.onrender.com")
    kwargs.setdefault("webhook_secret_token", "secret-test-token")
    kwargs.setdefault("listen_port", 0)  # ephemeral — overridden by TestClient path
    return BotRuntime(log=log, **kwargs)


async def _wait_ready(runtime, task, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if task.done():
            exc = task.exception()
            if exc is not None:
                raise exc
        if runtime.state == READY:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"not ready: {runtime.state}")


# ---------------------------------------------------------------------------
# Webhook: valid update reaches Application.process_update
# ---------------------------------------------------------------------------
async def _test_valid_webhook_reaches_handler():
    log = RecordingLog()
    app = FakeApp()
    runtime = _runtime_webhook(log)
    # Don't start full HTTP bind — exercise handler directly after binding app
    runtime._ptb_app = app
    runtime.state = READY
    runtime.accepting_updates = True

    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "date": 1,
            "chat": {"id": 1, "type": "private"},
            "text": "hello",
        },
    }
    request = AsyncMock()
    request.headers = {SECRET_HEADER: "secret-test-token"}
    request.json = AsyncMock(return_value=payload)

    resp = await runtime.handle_telegram_webhook(request)
    assert resp.status == 200
    # allow background task
    await asyncio.sleep(0.05)
    assert app.bot.get_updates_calls == 0
    assert app.process_update.await_count == 1


def test_valid_webhook_reaches_handler():
    asyncio.run(_test_valid_webhook_reaches_handler())


async def _test_invalid_secret_rejected():
    log = RecordingLog()
    app = FakeApp()
    runtime = _runtime_webhook(log)
    runtime._ptb_app = app
    runtime.state = READY
    runtime.accepting_updates = True

    request = AsyncMock()
    request.headers = {SECRET_HEADER: "wrong"}
    request.json = AsyncMock(return_value={"update_id": 1})

    resp = await runtime.handle_telegram_webhook(request)
    assert resp.status == 403
    assert app.process_update.await_count == 0

    request2 = AsyncMock()
    request2.headers = {}
    request2.json = AsyncMock(return_value={"update_id": 1})
    resp2 = await runtime.handle_telegram_webhook(request2)
    assert resp2.status == 403


def test_invalid_secret_rejected():
    asyncio.run(_test_invalid_secret_rejected())


async def _test_webhook_startup_no_polling():
    log = RecordingLog()
    app = FakeApp()
    # Use a free port via aiohttp site in run()
    runtime = _runtime_webhook(log, listen_port=8765)
    task = asyncio.create_task(runtime.run(app))
    try:
        await _wait_ready(runtime, task)
        assert runtime.mode == "webhook"
        assert app.bot.set_webhook_calls == 1
        assert runtime.set_webhook_calls == 1
        assert app.updater.start_polling_calls == 0
        assert runtime.start_polling_calls == 0
        assert app.bot.get_updates_calls == 0
        assert app.bot.last_webhook["url"] == "https://example.onrender.com/telegram/webhook"
        assert app.bot.last_webhook["secret_token"] == "secret-test-token"

        joined = "\n".join(log.infos)
        assert "application initialized" in joined
        assert "application started" in joined
        assert "Telegram webhook configured" in joined
        assert "MoodyBot ready" in joined
        assert "polling started" not in joined.lower()
        assert "lease" not in joined.lower()
    finally:
        runtime.request_shutdown()
        await task


def test_webhook_startup_no_polling():
    asyncio.run(_test_webhook_startup_no_polling())


async def _test_sigterm_webhook_shutdown():
    log = RecordingLog()
    app = FakeApp()
    runtime = _runtime_webhook(log, listen_port=8766)
    task = asyncio.create_task(runtime.run(app))
    await _wait_ready(runtime, task)
    runtime.request_shutdown(signal_name="SIGTERM")
    await task
    assert runtime.state == SHUTTING_DOWN
    assert app.stop_calls == 1
    assert app.shutdown_calls == 1
    assert app.updater.start_polling_calls == 0
    infos = "\n".join(log.infos)
    assert "SIGTERM received" in infos
    assert "stopping application" in infos
    assert "MoodyBot shutdown complete" in infos


def test_sigterm_webhook_shutdown():
    asyncio.run(_test_sigterm_webhook_shutdown())


def test_production_source_never_polls():
    lifecycle = (ROOT / "telegram_lifecycle.py").read_text(encoding="utf-8")
    moody = (ROOT / "moodybot.py").read_text(encoding="utf-8")
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")

    # Production default in render.yaml is webhook
    assert "TELEGRAM_MODE" in render
    assert "webhook" in render
    assert "TELEGRAM_POLLER_SINGLETON" not in render
    assert "type: web" in render
    assert "healthCheckPath: /health" in render

    # No obsolete polling diagnostics
    assert "probable_render_deploy_overlap" not in lifecycle
    assert "TELEGRAM_POLLER_SINGLETON" not in lifecycle
    assert "acquire_polling_lease" not in lifecycle

    # get_updates / start_polling only allowed inside polling-mode helper
    assert "await updater.start_polling" in lifecycle or "start_polling(" in lifecycle
    # Ensure webhook path is primary and set_webhook exists
    assert "set_webhook" in lifecycle
    assert "process_update" in lifecycle

    # moodybot must not call start_polling / get_updates / run_polling
    assert re.search(r"\.start_polling\s*\(", moody) is None
    assert re.search(r"\.get_updates\s*\(", moody) is None
    assert re.search(r"\.run_polling\s*\(", moody) is None

    # No credential prints
    assert "Using Telegram Token" not in moody
    assert "Using OpenRouter Key" not in moody


def test_log_redaction_filters_bot_urls():
    install_log_redaction()
    filt = SecretRedactFilter()
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='HTTP Request: POST https://api.telegram.org/bot8101181461:AAH-SECRET-TOKEN/getUpdates "HTTP/1.1 409 Conflict"',
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert "[REDACTED]" in record.getMessage()
    assert "AAH-SECRET-TOKEN" not in record.getMessage()
    assert "8101181461" not in record.getMessage()


def test_webhook_path_constant():
    assert WEBHOOK_PATH == "/telegram/webhook"


if __name__ == "__main__":
    test_valid_webhook_reaches_handler()
    print("ok valid")
    test_invalid_secret_rejected()
    print("ok secret")
    test_webhook_startup_no_polling()
    print("ok startup")
    test_sigterm_webhook_shutdown()
    print("ok sigterm")
    test_production_source_never_polls()
    test_log_redaction_filters_bot_urls()
    test_webhook_path_constant()
    print("ok")
