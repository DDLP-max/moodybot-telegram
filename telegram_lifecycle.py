# -*- coding: utf-8 -*-
"""Telegram application lifecycle — one Application, one Updater, one getUpdates loop.

No manual Bot.get_updates probes. No synthetic lease acquisition.
python-telegram-bot's Updater owns the only getUpdates consumer.

Startup (manual lifecycle; do NOT also call Application.run_polling):
  initialize → start → updater polling start → READY

Note: Updater._bootstrap always calls bot.delete_webhook for polling mode
(empty webhook_url). Do NOT call delete_webhook ourselves or startup doubles it.

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
import uuid
from typing import Any, Callable, Optional

logger = logging.getLogger("moodybot")

STARTING = "STARTING"
READY = "READY"
SHUTTING_DOWN = "SHUTTING_DOWN"

HANDLER_DRAIN_SECONDS = 8.0

_RUNTIME: Optional["PollerRuntime"] = None


def make_instance_id() -> str:
    host = socket.gethostname().split(".")[0][:24]
    short = uuid.uuid4().hex[:6]
    return f"{host}-{os.getpid()}-{short}"


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


def guard_handler(fn: Callable) -> Callable:
    """Drop new updates during shutdown; track in-flight handlers for drain."""

    @functools.wraps(fn)
    async def wrapped(update: Any, context: Any) -> Any:
        runtime = get_runtime()
        if runtime is not None and not runtime.accepting_updates:
            runtime.log.info("[%s] Dropping update — shutdown in progress", runtime.instance_id)
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
    ) -> None:
        self.log = log if log is not None else logger
        self.handler_drain_seconds = handler_drain_seconds
        self.install_signals_enabled = install_signals
        self.instance_id = instance_id or make_instance_id()

        self.state = STARTING
        self.accepting_updates = True
        self.in_flight = 0
        self._shutdown_event = asyncio.Event()
        self._signals_installed = False
        self._app_started = False
        self._polling_started = False

    @property
    def shutting_down(self) -> bool:
        return self.state == SHUTTING_DOWN or self._shutdown_event.is_set()

    def _fmt(self, msg: str) -> str:
        return f"[{self.instance_id}] {msg}"

    def handler_entered(self) -> None:
        self.in_flight += 1

    def handler_exited(self) -> None:
        self.in_flight = max(0, self.in_flight - 1)

    def request_shutdown(self) -> None:
        if self.state != SHUTTING_DOWN:
            self.log.info(self._fmt("Shutdown signal received — releasing Telegram polling lease"))
        self.state = SHUTTING_DOWN
        self.accepting_updates = False
        self._shutdown_event.set()

    def _on_shutdown_signal(self, *_args: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self.request_shutdown)
        except RuntimeError:
            self.request_shutdown()

    def install_signal_handlers(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        if self._signals_installed:
            return
        loop = loop or asyncio.get_running_loop()

        def _ask() -> None:
            self._on_shutdown_signal()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _ask)
            except (NotImplementedError, RuntimeError, AttributeError):
                try:
                    signal.signal(sig, lambda *_: _ask())
                except (ValueError, OSError):
                    pass
        self._signals_installed = True

    def _polling_error_callback(self, exc: BaseException) -> None:
        if is_poller_conflict(exc):
            self.log.warning(
                self._fmt(
                    "Telegram getUpdates conflict — another process may still be polling "
                    "this bot token (deploy overlap or duplicate worker): %s"
                ),
                exc,
            )
            return
        self.log.error(self._fmt("Telegram polling error: %s"), exc)

    async def _stop_updater(self, app: Any) -> None:
        updater = getattr(app, "updater", None)
        if updater is None:
            return
        try:
            if getattr(updater, "running", True):
                await updater.stop()
        except Exception as exc:
            self.log.warning(self._fmt("Updater stop raised: %s"), exc)

    async def _drain_and_close(self, app: Any) -> None:
        if self._app_started:
            stop = getattr(app, "stop", None)
            if callable(stop):
                try:
                    await asyncio.wait_for(stop(), timeout=self.handler_drain_seconds)
                except asyncio.TimeoutError:
                    self.log.warning(
                        self._fmt("In-flight handler drain timed out after %.1fs"),
                        self.handler_drain_seconds,
                    )
                except Exception as exc:
                    self.log.warning(self._fmt("Application stop raised: %s"), exc)
        shutdown = getattr(app, "shutdown", None)
        if callable(shutdown):
            try:
                await shutdown()
            except Exception as exc:
                self.log.warning(self._fmt("Application shutdown raised: %s"), exc)

    async def shutdown_app(self, app: Any) -> None:
        if not self._shutdown_event.is_set():
            self.request_shutdown()
        else:
            self.state = SHUTTING_DOWN
            self.accepting_updates = False

        await self._stop_updater(app)
        self.log.info(self._fmt("Telegram polling stopped"))
        await self._drain_and_close(app)
        self.log.info(self._fmt("MoodyBot shutdown complete"))

    async def run(self, app: Any) -> None:
        """Manual PTB lifecycle only — never Application.run_polling, never a bot get_updates probe."""
        bind_runtime(self)
        self.state = STARTING
        self.accepting_updates = True
        self.log.info(self._fmt("MoodyBot starting"))
        self.log.info(
            self._fmt("TELEGRAM_MODE=%s TELEGRAM_POLLER_SINGLETON=%s"),
            telegram_mode(),
            str(poller_singleton_enabled()).lower(),
        )
        initialized = False
        try:
            if self.install_signals_enabled:
                self.install_signal_handlers()

            await app.initialize()
            initialized = True
            self.log.info(self._fmt("application initialized"))

            # Do NOT call bot.delete_webhook here.
            # Updater polling bootstrap deletes the webhook exactly once.

            await app.start()
            self._app_started = True
            self.log.info(self._fmt("application started"))

            await app.updater.start_polling(
                drop_pending_updates=False,
                error_callback=self._polling_error_callback,
            )
            self._polling_started = True
            self.log.info(self._fmt("Telegram updater polling started"))

            self.state = READY
            self.log.info(self._fmt("MoodyBot ready"))
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
