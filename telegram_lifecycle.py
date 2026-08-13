# -*- coding: utf-8 -*-
"""Telegram application lifecycle — one Application, one Updater, one getUpdates loop.

No manual Bot.get_updates probes. No synthetic lease acquisition.
python-telegram-bot's Updater owns the only getUpdates consumer.

Startup (unchanged for diagnosis):
  initialize → start → updater polling start → READY

Shutdown (polling first):
  SIGTERM → updater.stop() → app.stop() → app.shutdown()

Production entry: moodybot.py main() → PollerRuntime.run(app)
TELEGRAM_MODE=polling
TELEGRAM_POLLER_SINGLETON=true  (documentation / one Render worker)
"""
from __future__ import annotations

import asyncio
import functools
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Optional

logger = logging.getLogger("moodybot")

STARTING = "STARTING"
READY = "READY"
SHUTTING_DOWN = "SHUTTING_DOWN"

HANDLER_DRAIN_SECONDS = 8.0
DEPLOY_OVERLAP_SECONDS = 60.0

_RUNTIME: Optional["PollerRuntime"] = None


def make_instance_id() -> str:
    host = socket.gethostname().split(".")[0][:24]
    short = uuid.uuid4().hex[:6]
    return f"{host}-{os.getpid()}-{short}"


def resolve_git_commit() -> str:
    env = (
        os.environ.get("RENDER_GIT_COMMIT")
        or os.environ.get("GIT_COMMIT")
        or os.environ.get("SOURCE_VERSION")
        or ""
    ).strip()
    if env:
        return env[:12]
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
            timeout=2,
        )
        return out.decode("utf-8", errors="replace").strip()[:12] or "unknown"
    except Exception:
        return "unknown"


def render_env_snapshot() -> dict:
    return {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "render_service_id": os.environ.get("RENDER_SERVICE_ID") or "",
        "render_instance_id": (
            os.environ.get("RENDER_INSTANCE_ID")
            or os.environ.get("RENDER_INSTANCE_ID".lower())
            or ""
        ),
        "render_service_name": os.environ.get("RENDER_SERVICE_NAME") or "",
        "render": os.environ.get("RENDER") or "",
        "git_commit": resolve_git_commit(),
    }


def get_runtime() -> Optional["PollerRuntime"]:
    return _RUNTIME


def bind_runtime(runtime: Optional["PollerRuntime"]) -> None:
    global _RUNTIME
    _RUNTIME = runtime


def reset_poller_guard() -> None:
    """Tests only — clear bound runtime."""
    global _RUNTIME
    _RUNTIME = None


def is_poller_conflict(exc: BaseException) -> bool:
    """True for Telegram 409 getUpdates conflicts (deploy overlap / duplicate)."""
    name = type(exc).__name__
    text = str(exc)
    if name == "Conflict":
        return True
    if "Conflict" in name or "409" in text:
        if "getUpdates" in text or "get_updates" in text or "terminated by other" in text:
            return True
    if "terminated by other getUpdates" in text:
        return True
    return False


def flush_logs() -> None:
    """Force handlers to flush so Render captures SIGTERM lines before exit."""
    for log in (logger, logging.getLogger()):
        for handler in getattr(log, "handlers", []):
            try:
                handler.flush()
            except Exception:
                pass
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass


def guard_handler(fn: Callable) -> Callable:
    """Drop new updates during shutdown; track in-flight handlers for drain."""

    @functools.wraps(fn)
    async def wrapped(update: Any, context: Any) -> Any:
        runtime = get_runtime()
        if runtime is not None and not runtime.accepting_updates:
            runtime.log.info("[%s] Dropping update — shutdown in progress", runtime.instance_id)
            flush_logs()
            return None
        if runtime is not None:
            runtime.handler_entered()
        try:
            return await fn(update, context)
        finally:
            if runtime is not None:
                runtime.handler_exited()

    return wrapped


class PollerRuntime:
    """One process → one Application → one Updater → one getUpdates loop."""

    def __init__(
        self,
        *,
        log: Any = None,
        handler_drain_seconds: float = HANDLER_DRAIN_SECONDS,
        install_signals: bool = True,
        instance_id: Optional[str] = None,
        clock: Callable[[], float] = time.monotonic,
        deploy_overlap_seconds: float = DEPLOY_OVERLAP_SECONDS,
    ) -> None:
        self.log = log if log is not None else logger
        self.handler_drain_seconds = handler_drain_seconds
        self.install_signals_enabled = install_signals
        self.instance_id = instance_id or make_instance_id()
        self.clock = clock
        self.deploy_overlap_seconds = deploy_overlap_seconds

        self.state = STARTING
        self.accepting_updates = True
        self.in_flight = 0
        self._shutdown_event = asyncio.Event()
        self._signals_installed = False
        self._app_started = False
        self._polling_started = False

        self.process_started_at = clock()
        self.polling_started_at: Optional[float] = None
        self.sigterm_at: Optional[float] = None
        self.updater_stop_completed_at: Optional[float] = None
        self.updater_stop_ms: Optional[float] = None
        self.env = render_env_snapshot()
        self.first_409_at: Optional[float] = None
        self.conflict_count = 0
        self.last_409_classification: Optional[str] = None

    @property
    def shutting_down(self) -> bool:
        return self.state == SHUTTING_DOWN or self._shutdown_event.is_set()

    def _fmt(self, msg: str) -> str:
        return f"[{self.instance_id}] {msg}"

    def _info(self, msg: str, *args: Any) -> None:
        self.log.info(self._fmt(msg), *args)
        flush_logs()

    def _warning(self, msg: str, *args: Any) -> None:
        self.log.warning(self._fmt(msg), *args)
        flush_logs()

    def _error(self, msg: str, *args: Any) -> None:
        self.log.error(self._fmt(msg), *args)
        flush_logs()

    def uptime_seconds(self, now: Optional[float] = None) -> float:
        now = self.clock() if now is None else now
        return max(0.0, now - self.process_started_at)

    def seconds_since_polling_started(self, now: Optional[float] = None) -> Optional[float]:
        if self.polling_started_at is None:
            return None
        now = self.clock() if now is None else now
        return max(0.0, now - self.polling_started_at)

    def handler_entered(self) -> None:
        self.in_flight += 1

    def handler_exited(self) -> None:
        self.in_flight = max(0, self.in_flight - 1)

    def request_shutdown(self, *, signal_name: str = "SIGTERM") -> None:
        if self.state == SHUTTING_DOWN:
            return
        self.sigterm_at = self.clock()
        self.state = SHUTTING_DOWN
        self.accepting_updates = False
        self._info("%s received", signal_name)
        self._shutdown_event.set()

    def _on_shutdown_signal(self, signum: Optional[int] = None, *_args: Any) -> None:
        name = "SIGTERM"
        if signum == getattr(signal, "SIGINT", None):
            name = "SIGINT"
        elif signum == getattr(signal, "SIGTERM", None):
            name = "SIGTERM"

        def _ask() -> None:
            self.request_shutdown(signal_name=name)

        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(_ask)
        except RuntimeError:
            _ask()

    def install_signal_handlers(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        if self._signals_installed:
            return
        loop = loop or asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: self._on_shutdown_signal(s))
            except (NotImplementedError, RuntimeError, AttributeError):
                try:
                    signal.signal(sig, lambda s, f, sig=sig: self._on_shutdown_signal(sig))
                except (ValueError, OSError):
                    pass
        self._signals_installed = True

    def classify_conflict(self, now: Optional[float] = None) -> str:
        """Classify 409 as deploy overlap vs persistent competing poller."""
        now = self.clock() if now is None else now
        since_poll = self.seconds_since_polling_started(now)
        uptime = self.uptime_seconds(now)
        age = since_poll if since_poll is not None else uptime
        if age < self.deploy_overlap_seconds:
            return "probable_render_deploy_overlap"
        return "likely_another_live_worker_or_environment"

    def _polling_error_callback(self, exc: BaseException) -> None:
        if is_poller_conflict(exc):
            now = self.clock()
            self.conflict_count += 1
            if self.first_409_at is None:
                self.first_409_at = now
            kind = self.classify_conflict(now)
            self.last_409_classification = kind
            since_poll = self.seconds_since_polling_started(now)
            since_poll_s = f"{since_poll:.1f}" if since_poll is not None else "n/a"
            self._warning(
                "Telegram getUpdates 409 Conflict "
                "classification=%s instance_id=%s pid=%s uptime_s=%.1f "
                "seconds_since_updater_start_polling=%s "
                "RENDER_SERVICE_ID=%s RENDER_INSTANCE_ID=%s "
                "RENDER_SERVICE_NAME=%s git_commit=%s conflict_count=%s err=%s",
                kind,
                self.instance_id,
                self.env.get("pid"),
                self.uptime_seconds(now),
                since_poll_s,
                self.env.get("render_service_id") or "unset",
                self.env.get("render_instance_id") or "unset",
                self.env.get("render_service_name") or "unset",
                self.env.get("git_commit") or "unknown",
                self.conflict_count,
                exc,
            )
            return
        self._error("Telegram polling error: %s", exc)

    async def _stop_updater(self, app: Any) -> None:
        updater = getattr(app, "updater", None)
        if updater is None:
            return
        self._info("stopping Telegram updater")
        t0 = self.clock()
        try:
            if getattr(updater, "running", True):
                await updater.stop()
        except Exception as exc:
            self._warning("Updater stop raised: %s", exc)
        self.updater_stop_completed_at = self.clock()
        if self.sigterm_at is not None:
            self.updater_stop_ms = (self.updater_stop_completed_at - self.sigterm_at) * 1000.0
        else:
            self.updater_stop_ms = (self.updater_stop_completed_at - t0) * 1000.0
        self._info(
            "Telegram updater stopped (updater.stop completed in %.0f ms since SIGTERM)",
            self.updater_stop_ms,
        )

    async def _drain_and_close(self, app: Any) -> None:
        if self._app_started:
            self._info("stopping application")
            stop = getattr(app, "stop", None)
            if callable(stop):
                try:
                    await asyncio.wait_for(stop(), timeout=self.handler_drain_seconds)
                except asyncio.TimeoutError:
                    self._warning(
                        "In-flight handler drain timed out after %.1fs",
                        self.handler_drain_seconds,
                    )
                except Exception as exc:
                    self._warning("Application stop raised: %s", exc)
            self._info("application stopped")

        shutdown = getattr(app, "shutdown", None)
        if callable(shutdown):
            try:
                await shutdown()
            except Exception as exc:
                self._warning("Application shutdown raised: %s", exc)
        self._info("application shutdown complete")

    async def shutdown_app(self, app: Any) -> None:
        """Stop polling FIRST, then drain handlers, then close the Telegram client."""
        if not self._shutdown_event.is_set():
            self.request_shutdown(signal_name="SIGTERM")
        else:
            self.state = SHUTTING_DOWN
            self.accepting_updates = False

        # Critical: cancel getUpdates before any other cleanup.
        await self._stop_updater(app)
        await self._drain_and_close(app)
        self._info(
            "MoodyBot shutdown complete instance_id=%s pid=%s "
            "RENDER_SERVICE_ID=%s git_commit=%s updater_stop_ms=%s",
            self.instance_id,
            self.env.get("pid"),
            self.env.get("render_service_id") or "unset",
            self.env.get("git_commit") or "unknown",
            f"{self.updater_stop_ms:.0f}" if self.updater_stop_ms is not None else "n/a",
        )

    async def run(self, app: Any) -> None:
        """Manual PTB lifecycle only — never Application.run_polling, never a bot get_updates probe."""
        bind_runtime(self)
        self.state = STARTING
        self.accepting_updates = True
        self.env = render_env_snapshot()
        self.process_started_at = self.clock()

        self._info("MoodyBot starting")
        self._info(
            "instance lifetime instance_id=%s pid=%s hostname=%s "
            "RENDER_SERVICE_ID=%s RENDER_INSTANCE_ID=%s RENDER_SERVICE_NAME=%s "
            "git_commit=%s TELEGRAM_MODE=%s TELEGRAM_POLLER_SINGLETON=%s",
            self.instance_id,
            self.env.get("pid"),
            self.env.get("hostname"),
            self.env.get("render_service_id") or "unset",
            self.env.get("render_instance_id") or "unset",
            self.env.get("render_service_name") or "unset",
            self.env.get("git_commit") or "unknown",
            telegram_mode(),
            str(poller_singleton_enabled()).lower(),
        )
        initialized = False
        try:
            if self.install_signals_enabled:
                self.install_signal_handlers()

            await app.initialize()
            initialized = True
            self._info("application initialized")

            # Do NOT call bot.delete_webhook here.
            # Updater polling bootstrap deletes the webhook exactly once.

            await app.start()
            self._app_started = True
            self._info("application started")

            await app.updater.start_polling(
                drop_pending_updates=False,
                error_callback=self._polling_error_callback,
            )
            self._polling_started = True
            self.polling_started_at = self.clock()
            self._info("Telegram updater polling started")

            self.state = READY
            self._info("MoodyBot ready")
            await self._shutdown_event.wait()
        finally:
            if initialized:
                await self.shutdown_app(app)
            bind_runtime(None)


def telegram_mode() -> str:
    return (os.environ.get("TELEGRAM_MODE") or "polling").strip().lower()


def poller_singleton_enabled() -> bool:
    raw = (os.environ.get("TELEGRAM_POLLER_SINGLETON") or "true").strip().lower()
    return raw not in {"0", "false", "no"}
