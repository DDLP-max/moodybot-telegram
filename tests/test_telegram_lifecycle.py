# -*- coding: utf-8 -*-
"""Telegram poller lifecycle: acquire, backoff, duplicate vs overlap, SIGTERM."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from telegram.error import Conflict
from telegram_lifecycle import (
    DUPLICATE_ERROR,
    READY,
    STARTING,
    SHUTTING_DOWN,
    WAITING_FOR_TELEGRAM_POLLER,
    PollerRuntime,
    guard_handler,
    is_poller_conflict,
    reset_poller_guard,
)

ROOT = Path(__file__).resolve().parents[1]

CONFLICT = Conflict(
    "terminated by other getUpdates request; make sure that only one bot instance is running"
)


class ZeroRng:
    def uniform(self, a, b):
        return 0.0


class FakeClock:
    def __init__(self, t=0.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += float(s)


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
    def __init__(self):
        self.running = False
        self.start_calls = 0
        self.stop_calls = 0

    async def start_polling(self, **kwargs):
        self.start_calls += 1
        self.running = True

    async def stop(self):
        self.stop_calls += 1
        self.running = False


class FakeBot:
    def __init__(self, results):
        self.results = list(results)
        self.get_updates_calls = 0
        self.delete_webhook_calls = 0

    async def get_updates(self, **kwargs):
        self.get_updates_calls += 1
        idx = min(self.get_updates_calls - 1, len(self.results) - 1)
        item = self.results[idx]
        if isinstance(item, BaseException):
            raise item
        return item

    async def delete_webhook(self, **kwargs):
        self.delete_webhook_calls += 1
        return True


class FakeApp:
    def __init__(self, bot):
        self.bot = bot
        self.updater = FakeUpdater()
        self.initialize_calls = 0
        self.start_calls = 0
        self.stop_calls = 0
        self.shutdown_calls = 0
        self.stop_saw_polling_stopped = None
        self._handler_block = None

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


def _make_runtime(clock, log, sleep, **kwargs):
    reset_poller_guard()
    kwargs.setdefault("grace_seconds", 90.0)
    kwargs.setdefault("install_signals", False)
    return PollerRuntime(
        clock=clock,
        sleep=sleep,
        rng=ZeroRng(),
        log=log,
        **kwargs,
    )


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
# TEST A — normal startup
# ---------------------------------------------------------------------------
async def _test_a():
    clock = FakeClock()
    log = RecordingLog()
    app = FakeApp(FakeBot([[]]))

    async def sleep(delay):
        clock.advance(delay)

    runtime = _make_runtime(clock, log, sleep)
    assert runtime.state == STARTING
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)
    assert runtime.acquire_attempts == 1
    assert runtime.retry_count == 0
    assert runtime.sleep_delays == []
    assert app.updater.start_calls == 1
    assert any("Telegram polling lease acquired" in m for m in log.infos)
    assert any("MoodyBot ready." in m for m in log.infos)
    assert any("MoodyBot starting with OpenRouter." in m for m in log.infos)
    assert not any("usually a Render deploy overlap" in m for m in log.warnings)
    runtime.request_shutdown()
    await task
    assert runtime.state == SHUTTING_DOWN


def test_a_normal_startup():
    asyncio.run(_test_a())


# ---------------------------------------------------------------------------
# TEST B — Render overlap (3x 409, then success)
# ---------------------------------------------------------------------------
async def _test_b():
    clock = FakeClock()
    log = RecordingLog()
    states = []
    app = FakeApp(FakeBot([CONFLICT, CONFLICT, CONFLICT, []]))

    async def sleep(delay):
        states.append(runtime.state)
        clock.advance(delay)

    runtime = _make_runtime(clock, log, sleep)
    assert runtime.state == STARTING
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)
    assert WAITING_FOR_TELEGRAM_POLLER in states
    assert runtime.conflict_count == 3
    assert runtime.acquire_attempts == 4
    assert runtime.retry_count == 0  # reset after lease acquired
    assert [round(d) for d in runtime.sleep_delays] == [2, 4, 8]
    assert app.updater.start_calls == 1
    assert any("deploy overlap" in m for m in log.warnings)
    assert not any(DUPLICATE_ERROR in m for m in log.errors)
    assert any("Telegram polling lease acquired" in m for m in log.infos)
    assert any("MoodyBot ready." in m for m in log.infos)
    runtime.request_shutdown()
    await task


def test_b_render_overlap():
    asyncio.run(_test_b())


# ---------------------------------------------------------------------------
# TEST C — persistent duplicate poller
# ---------------------------------------------------------------------------
async def _test_c():
    clock = FakeClock()
    log = RecordingLog()
    app = FakeApp(FakeBot([CONFLICT]))

    async def sleep(delay):
        clock.advance(delay)
        if runtime.duplicate_error_emitted or clock() > 200:
            runtime.request_shutdown()

    runtime = _make_runtime(clock, log, sleep, grace_seconds=90.0)
    await runtime.run(app)
    assert runtime.beyond_grace()
    assert runtime.classify_conflict() == "POLLER_ALREADY_ACTIVE_DUPLICATE"
    assert any(DUPLICATE_ERROR in m for m in log.errors)
    assert app.updater.start_calls == 0
    overlap_only = [m for m in log.warnings if "usually a Render deploy overlap" in m]
    assert overlap_only == []


def test_c_persistent_duplicate():
    asyncio.run(_test_c())


# ---------------------------------------------------------------------------
# TEST D — SIGTERM while polling
# ---------------------------------------------------------------------------
async def _test_d():
    clock = FakeClock()
    log = RecordingLog()
    app = FakeApp(FakeBot([[]]))

    async def sleep(delay):
        clock.advance(delay)

    runtime = _make_runtime(clock, log, sleep)
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
    assert runtime.state == SHUTTING_DOWN


def test_d_sigterm_stops_polling():
    asyncio.run(_test_d())


# ---------------------------------------------------------------------------
# TEST E — SIGTERM while a handler is in flight
# ---------------------------------------------------------------------------
async def _test_e():
    clock = FakeClock()
    log = RecordingLog()
    app = FakeApp(FakeBot([[]]))
    hold = asyncio.Event()
    app._handler_block = hold.wait()

    async def sleep(delay):
        clock.advance(delay)

    runtime = _make_runtime(clock, log, sleep, handler_drain_seconds=2.0)
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)

    runtime.handler_entered()
    runtime._on_shutdown_signal()
    await asyncio.sleep(0.05)
    assert runtime.accepting_updates is False
    assert app.updater.running is False
    assert app.updater.stop_calls >= 1
    assert any("Telegram polling stopped" in m for m in log.infos)
    assert runtime.in_flight == 1
    assert app.stop_saw_polling_stopped is True
    runtime.handler_exited()
    hold.set()
    await task
    assert app.shutdown_calls == 1


def test_e_shutdown_during_handler():
    asyncio.run(_test_e())


def test_guard_drops_updates_during_shutdown():
    async def _inner():
        reset_poller_guard()
        clock = FakeClock()
        log = RecordingLog()

        async def sleep(delay):
            clock.advance(delay)

        runtime = _make_runtime(clock, log, sleep)
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


def test_conflict_classifier():
    assert is_poller_conflict(CONFLICT)
    assert not is_poller_conflict(RuntimeError("boom"))


def test_single_production_polling_entrypoint():
    """moodybot.py must not start polling itself; telegram_lifecycle is the one site."""
    src = (ROOT / "moodybot.py").read_text(encoding="utf-8")
    assert "run_polling" not in src
    assert "start_polling" not in src
    assert "PollerRuntime" in src
    assert "runtime.run(" in src or ".run(app)" in src

    lifecycle = (ROOT / "telegram_lifecycle.py").read_text(encoding="utf-8")
    assert lifecycle.count("start_polling") == 1
    assert "run_polling" not in lifecycle

    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "type: worker" in render
    assert render.count("type:") == 1
    assert "TELEGRAM_POLLER_SINGLETON" in render
    assert "TELEGRAM_MODE" in render
    assert "sleep 8" not in render


def test_language_tool_is_optional_info():
    src = (ROOT / "moodybot.py").read_text(encoding="utf-8")
    assert "LanguageTool not available; continuing without optional grammar polish" in src
    assert "LanguageTool unavailable, skipping grammar polish" not in src


if __name__ == "__main__":
    test_a_normal_startup()
    print("ok A")
    test_b_render_overlap()
    print("ok B")
    test_c_persistent_duplicate()
    print("ok C")
    test_d_sigterm_stops_polling()
    print("ok D")
    test_e_shutdown_during_handler()
    print("ok E")
    test_guard_drops_updates_during_shutdown()
    test_conflict_classifier()
    test_single_production_polling_entrypoint()
    test_language_tool_is_optional_info()
    print("ok")
