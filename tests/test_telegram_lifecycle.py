# -*- coding: utf-8 -*-
"""Telegram lifecycle: one Application, one Updater, no manual get_updates lease."""
from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

from telegram_lifecycle import (
    READY,
    STARTING,
    SHUTTING_DOWN,
    PollerRuntime,
    guard_handler,
    is_poller_conflict,
    reset_poller_guard,
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


class FakeUpdater:
    """Mirrors PTB: start_polling bootstraps delete_webhook, then polls."""

    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.start_calls = 0
        self.stop_calls = 0

    async def start_polling(self, **kwargs):
        # PTB Updater._bootstrap always deletes webhook for polling mode.
        await self.bot.delete_webhook(drop_pending_updates=kwargs.get("drop_pending_updates"))
        self.start_calls += 1
        self.running = True

    async def stop(self):
        self.stop_calls += 1
        self.running = False


class FakeBot:
    def __init__(self):
        self.get_updates_calls = 0
        self.delete_webhook_calls = 0

    async def get_updates(self, **kwargs):
        self.get_updates_calls += 1
        return []

    async def delete_webhook(self, **kwargs):
        self.delete_webhook_calls += 1
        return True


class FakeApp:
    def __init__(self):
        self.bot = FakeBot()
        self.updater = FakeUpdater(self.bot)
        self.initialize_calls = 0
        self.start_calls = 0
        self.stop_calls = 0
        self.shutdown_calls = 0
        self.stop_saw_polling_stopped = None
        self._handler_block = None
        self.run_polling_calls = 0

    async def initialize(self):
        self.initialize_calls += 1

    async def start(self):
        self.start_calls += 1

    async def stop(self):
        self.stop_saw_polling_stopped = not self.updater.running
        self.stop_calls += 1
        if self._handler_block is not None:
            await self._handler_block

    async def shutdown(self):
        self.shutdown_calls += 1

    def run_polling(self, **kwargs):
        self.run_polling_calls += 1
        raise AssertionError("run_polling must not be used with manual lifecycle")


def _make_runtime(log, **kwargs):
    reset_poller_guard()
    kwargs.setdefault("install_signals", False)
    kwargs.setdefault("instance_id", "test-1-abc123")
    return PollerRuntime(log=log, **kwargs)


async def _wait_state(runtime, state, task=None, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if task is not None and task.done():
            exc = task.exception()
            if exc is not None:
                raise exc
        if runtime.state == state:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"state={runtime.state!r} wanted {state!r}")


# ---------------------------------------------------------------------------
# Startup invariants: one webhook delete, one poller, zero manual get_updates
# ---------------------------------------------------------------------------
async def _test_startup_one_poller():
    log = RecordingLog()
    app = FakeApp()
    runtime = _make_runtime(log)
    assert runtime.state == STARTING
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)

    assert app.bot.delete_webhook_calls == 1
    assert app.updater.start_calls == 1
    assert app.bot.get_updates_calls == 0  # no manual lease probe
    assert app.run_polling_calls == 0
    assert app.initialize_calls == 1
    assert app.start_calls == 1

    joined = "\n".join(log.infos)
    assert "[test-1-abc123] MoodyBot starting" in joined
    assert "[test-1-abc123] application initialized" in joined
    assert "[test-1-abc123] application started" in joined
    assert "[test-1-abc123] Telegram updater polling started" in joined
    assert "[test-1-abc123] MoodyBot ready" in joined
    assert "lease acquired" not in joined.lower()

    runtime.request_shutdown()
    await task
    assert runtime.state == SHUTTING_DOWN


def test_startup_one_poller():
    asyncio.run(_test_startup_one_poller())


# ---------------------------------------------------------------------------
# SIGTERM while polling
# ---------------------------------------------------------------------------
async def _test_sigterm():
    log = RecordingLog()
    app = FakeApp()
    runtime = _make_runtime(log)
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)
    assert app.updater.running is True
    runtime._on_shutdown_signal()
    await task
    assert app.updater.running is False
    assert app.updater.stop_calls >= 1
    assert app.shutdown_calls == 1
    assert any("releasing Telegram polling lease" in m for m in log.infos)
    assert any("Telegram polling stopped" in m for m in log.infos)
    assert any("MoodyBot shutdown complete" in m for m in log.infos)


def test_sigterm_stops_polling():
    asyncio.run(_test_sigterm())


# ---------------------------------------------------------------------------
# SIGTERM during in-flight handler
# ---------------------------------------------------------------------------
async def _test_shutdown_during_handler():
    log = RecordingLog()
    app = FakeApp()
    hold = asyncio.Event()
    app._handler_block = hold.wait()
    runtime = _make_runtime(log, handler_drain_seconds=2.0)
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)

    runtime.handler_entered()
    runtime._on_shutdown_signal()
    await asyncio.sleep(0.05)
    assert runtime.accepting_updates is False
    assert app.updater.running is False
    assert app.updater.stop_calls >= 1
    assert runtime.in_flight == 1
    assert app.stop_saw_polling_stopped is True
    runtime.handler_exited()
    hold.set()
    await task
    assert app.shutdown_calls == 1


def test_shutdown_during_handler():
    asyncio.run(_test_shutdown_during_handler())


def test_guard_drops_updates_during_shutdown():
    async def _inner():
        reset_poller_guard()
        log = RecordingLog()
        runtime = _make_runtime(log)
        from telegram_lifecycle import bind_runtime

        bind_runtime(runtime)
        runtime.accepting_updates = False
        called = []

        @guard_handler
        async def handler(update, context):
            called.append(1)

        await handler(None, None)
        assert called == []
        runtime.accepting_updates = True
        await handler(None, None)
        assert called == [1]
        bind_runtime(None)

    asyncio.run(_inner())


def test_repository_no_manual_get_updates_startup():
    """Production code must not call Bot.get_updates outside PTB's updater."""
    lifecycle = (ROOT / "telegram_lifecycle.py").read_text(encoding="utf-8")
    moody = (ROOT / "moodybot.py").read_text(encoding="utf-8")

    # No acquire_polling_lease / lease probe language in lifecycle
    assert "acquire_polling_lease" not in lifecycle
    assert "lease acquired" not in lifecycle.lower()
    assert "WAITING_FOR_TELEGRAM_POLLER" not in lifecycle

    # No bot.get_updates / .get_updates( call expressions in production modules
    assert re.search(r"\.get_updates\s*\(", lifecycle) is None
    assert re.search(r"\.get_updates\s*\(", moody) is None
    assert re.search(r"\.run_polling\s*\(", moody) is None
    assert re.search(r"\.run_polling\s*\(", lifecycle) is None

    # Exactly one await start_polling call site in production lifecycle
    assert len(re.findall(r"await\s+\w[\w.]*\.start_polling\s*\(", lifecycle)) == 1

    # Explicit delete_webhook must not appear as an awaited call (PTB bootstrap owns it)
    assert re.search(r"await\s+[^\n]*\.delete_webhook\s*\(", lifecycle) is None
    assert re.search(r"await\s+[^\n]*\.delete_webhook\s*\(", moody) is None


def test_render_single_worker():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "type: worker" in render
    assert render.count("type:") == 1
    assert "TELEGRAM_POLLER_SINGLETON" in render
    assert "TELEGRAM_MODE" in render


def test_language_tool_is_optional_info():
    src = (ROOT / "moodybot.py").read_text(encoding="utf-8")
    assert "LanguageTool not available; continuing without optional grammar polish" in src


def test_conflict_classifier():
    from telegram.error import Conflict

    assert is_poller_conflict(
        Conflict("terminated by other getUpdates request; make sure that only one bot instance is running")
    )
    assert not is_poller_conflict(RuntimeError("boom"))


if __name__ == "__main__":
    test_startup_one_poller()
    print("ok startup")
    test_sigterm_stops_polling()
    print("ok sigterm")
    test_shutdown_during_handler()
    print("ok drain")
    test_guard_drops_updates_during_shutdown()
    test_repository_no_manual_get_updates_startup()
    test_render_single_worker()
    test_language_tool_is_optional_info()
    test_conflict_classifier()
    print("ok")
