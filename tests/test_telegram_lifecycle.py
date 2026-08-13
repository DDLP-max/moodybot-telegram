# -*- coding: utf-8 -*-
"""Telegram lifecycle: shutdown-first diagnostics; one updater; no lease probe."""
from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

from telegram.error import Conflict
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
    """Mirrors PTB: start_polling bootstraps delete_webhook; background getUpdates."""

    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.start_calls = 0
        self.stop_calls = 0
        self._poll_task = None
        self.get_updates_after_stop = 0

    async def start_polling(self, **kwargs):
        await self.bot.delete_webhook(drop_pending_updates=kwargs.get("drop_pending_updates"))
        self.start_calls += 1
        self.running = True

        async def _poll_loop():
            while self.running:
                try:
                    await self.bot.get_updates(timeout=0)
                except Exception:
                    pass
                await asyncio.sleep(0.01)

        self._poll_task = asyncio.create_task(_poll_loop())

    async def stop(self):
        self.running = False
        self.stop_calls += 1
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None


class FakeBot:
    def __init__(self):
        self.get_updates_calls = 0
        self.delete_webhook_calls = 0
        self.get_updates_timestamps = []
        self._stopped = False

    async def get_updates(self, **kwargs):
        self.get_updates_calls += 1
        self.get_updates_timestamps.append(time.monotonic())
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


async def _test_startup_one_poller():
    log = RecordingLog()
    app = FakeApp()
    runtime = _make_runtime(log)
    assert runtime.state == STARTING
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)

    assert app.bot.delete_webhook_calls == 1
    assert app.updater.start_calls == 1
    assert app.run_polling_calls == 0
    assert app.initialize_calls == 1
    assert app.start_calls == 1

    joined = "\n".join(log.infos)
    assert "[test-1-abc123] MoodyBot starting" in joined
    assert "instance lifetime" in joined
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


async def _test_sigterm_log_sequence():
    log = RecordingLog()
    app = FakeApp()
    runtime = _make_runtime(log)
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)
    runtime.request_shutdown(signal_name="SIGTERM")
    await task

    infos = log.infos
    # Required shutdown instrumentation order (subset)
    def idx(substr):
        for i, m in enumerate(infos):
            if substr in m:
                return i
        raise AssertionError(f"missing log: {substr!r}\n{infos}")

    i_sig = idx("SIGTERM received")
    i_stop_upd = idx("stopping Telegram updater")
    i_upd_stopped = idx("Telegram updater stopped")
    i_stop_app = idx("stopping application")
    i_app_stopped = idx("application stopped")
    i_app_shutdown = idx("application shutdown complete")
    i_done = idx("MoodyBot shutdown complete")
    assert i_sig < i_stop_upd < i_upd_stopped < i_stop_app < i_app_stopped < i_app_shutdown < i_done
    assert runtime.updater_stop_ms is not None
    assert runtime.updater_stop_ms >= 0


def test_sigterm_log_sequence():
    asyncio.run(_test_sigterm_log_sequence())


async def _test_sigterm_stops_get_updates_before_b_polls():
    """CRITICAL: instance A must not issue getUpdates after updater.stop()."""
    log_a = RecordingLog()
    app_a = FakeApp()
    runtime_a = _make_runtime(log_a, instance_id="instance-A")
    task_a = asyncio.create_task(runtime_a.run(app_a))
    await _wait_state(runtime_a, READY, task=task_a)

    # Let A issue at least one getUpdates via fake poll loop
    await asyncio.sleep(0.05)
    assert app_a.bot.get_updates_calls >= 1
    calls_before_stop = app_a.bot.get_updates_calls

    runtime_a.request_shutdown(signal_name="SIGTERM")
    await task_a

    calls_at_stop = app_a.bot.get_updates_calls
    assert app_a.updater.running is False
    assert app_a.updater.stop_calls >= 1

    # Wait — A must not keep polling
    await asyncio.sleep(0.08)
    assert app_a.bot.get_updates_calls == calls_at_stop, (
        f"A issued getUpdates after updater.stop "
        f"(before={calls_before_stop} at_stop={calls_at_stop} after={app_a.bot.get_updates_calls})"
    )

    # Instance B starts polling cleanly
    log_b = RecordingLog()
    app_b = FakeApp()
    runtime_b = _make_runtime(log_b, instance_id="instance-B")
    task_b = asyncio.create_task(runtime_b.run(app_b))
    await _wait_state(runtime_b, READY, task=task_b)
    await asyncio.sleep(0.05)
    assert app_b.updater.start_calls == 1
    assert app_b.bot.get_updates_calls >= 1
    assert app_a.bot.get_updates_calls == calls_at_stop

    runtime_b.request_shutdown()
    await task_b


def test_sigterm_stops_get_updates_before_b_polls():
    asyncio.run(_test_sigterm_stops_get_updates_before_b_polls())


async def _test_409_classification():
    log = RecordingLog()
    app = FakeApp()
    runtime = _make_runtime(log, deploy_overlap_seconds=60.0)
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)

    # Early 409 → deploy overlap
    runtime._polling_error_callback(
        Conflict("terminated by other getUpdates request; make sure that only one bot instance is running")
    )
    assert runtime.last_409_classification == "probable_render_deploy_overlap"
    assert any("probable_render_deploy_overlap" in w for w in log.warnings)
    assert any("seconds_since_updater_start_polling=" in w for w in log.warnings)

    # Advance clock past grace
    runtime.polling_started_at = runtime.clock() - 61.0
    runtime.process_started_at = runtime.clock() - 61.0
    runtime._polling_error_callback(
        Conflict("terminated by other getUpdates request; make sure that only one bot instance is running")
    )
    assert runtime.last_409_classification == "likely_another_live_worker_or_environment"
    assert any("likely_another_live_worker_or_environment" in w for w in log.warnings)

    runtime.request_shutdown()
    await task


def test_409_classification():
    asyncio.run(_test_409_classification())


async def _test_shutdown_during_handler():
    log = RecordingLog()
    app = FakeApp()
    hold = asyncio.Event()
    app._handler_block = hold.wait()
    runtime = _make_runtime(log, handler_drain_seconds=2.0)
    task = asyncio.create_task(runtime.run(app))
    await _wait_state(runtime, READY, task=task)

    runtime.handler_entered()
    runtime.request_shutdown(signal_name="SIGTERM")
    await asyncio.sleep(0.05)
    assert runtime.accepting_updates is False
    assert app.updater.running is False
    assert app.stop_saw_polling_stopped is True
    runtime.handler_exited()
    hold.set()
    await task


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
        bind_runtime(None)

    asyncio.run(_inner())


def test_repository_no_manual_get_updates_startup():
    lifecycle = (ROOT / "telegram_lifecycle.py").read_text(encoding="utf-8")
    moody = (ROOT / "moodybot.py").read_text(encoding="utf-8")
    assert "acquire_polling_lease" not in lifecycle
    assert "lease acquired" not in lifecycle.lower()
    assert re.search(r"\.get_updates\s*\(", lifecycle) is None
    assert re.search(r"\.get_updates\s*\(", moody) is None
    assert re.search(r"\.run_polling\s*\(", moody) is None
    assert re.search(r"\.run_polling\s*\(", lifecycle) is None
    assert len(re.findall(r"await\s+\w[\w.]*\.start_polling\s*\(", lifecycle)) == 1
    assert re.search(r"await\s+[^\n]*\.delete_webhook\s*\(", lifecycle) is None


def test_render_service_definitions():
    """Every Render-related service definition in this repo."""
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "type: worker" in render
    assert render.count("type:") == 1
    assert "TELEGRAM_POLLER_SINGLETON" in render
    assert "python moodybot.py" in render
    # No second Blueprint service / web / cron / replica config in this file
    assert "type: web" not in render
    assert "type: cron" not in render
    assert "numInstances" not in render
    assert re.search(r"(?m)^\s*replicas\s*:", render) is None
    assert re.search(r"(?m)^\s*scaling\s*:", render) is None


def test_conflict_classifier():
    assert is_poller_conflict(
        Conflict("terminated by other getUpdates request; make sure that only one bot instance is running")
    )
    assert not is_poller_conflict(RuntimeError("boom"))


if __name__ == "__main__":
    test_startup_one_poller()
    print("ok startup")
    test_sigterm_log_sequence()
    print("ok sigterm logs")
    test_sigterm_stops_get_updates_before_b_polls()
    print("ok A/B")
    test_409_classification()
    print("ok 409")
    test_shutdown_during_handler()
    print("ok drain")
    test_guard_drops_updates_during_shutdown()
    test_repository_no_manual_get_updates_startup()
    test_render_service_definitions()
    test_conflict_classifier()
    print("ok")
