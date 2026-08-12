# -*- coding: utf-8 -*-
"""Telegram poller lifecycle — one lease, graceful shutdown, truthful readiness.

Render zero-downtime deploys overlap processes. Telegram allows only one
getUpdates consumer per bot token. This module:

- acquires the polling lease with bounded backoff (does not hammer)
- distinguishes deploy-overlap 409s from a persistent duplicate poller
- releases getUpdates immediately on SIGTERM/SIGINT
- exposes STARTING / WAITING_FOR_TELEGRAM_POLLER / READY / SHUTTING_DOWN

Production polling starts from moodybot.py main() only.
TELEGRAM_MODE=polling
TELEGRAM_POLLER_SINGLETON=true
"""
from __future__ import annotations

import asyncio
import functools
import logging
import os
import random
import signal
import time
from typing import Any, Awaitable, Callable, List, Optional

logger = logging.getLogger("moodybot")

STARTING = "STARTING"
WAITING_FOR_TELEGRAM_POLLER = "WAITING_FOR_TELEGRAM_POLLER"
READY = "READY"
SHUTTING_DOWN = "SHUTTING_DOWN"

BACKOFF_SECONDS = (2.0, 4.0, 8.0, 12.0, 20.0, 30.0)
DEPLOY_GRACE_SECONDS = 90.0
HANDLER_DRAIN_SECONDS = 8.0
DUPLICATE_ERROR = (
    "Telegram polling conflict persisted beyond deploy grace period. "
    "Another MoodyBot instance may be using this bot token."
)

# Process-wide guard: exactly one poller runtime may start polling.
_POLLER_STARTED = False
_RUNTIME: Optional["PollerRuntime"] = None


def is_poller_conflict(exc: BaseException) -> bool:
    """True for Telegram 409 getUpdates 'already being used' conflicts."""
    name = type(exc).__name__
    text = str(exc)
    if name == "Conflict":
        return True
    if "Conflict" in name or "409" in text:
        if "getUpdates" in text or "get_updates" in text:
            return True
        if "terminated by other" in text:
            return True
    if "terminated by other getUpdates" in text:
        return True
    return False


def next_backoff_seconds(attempt: int, rng: Any = None) -> float:
    """Bounded exponential backoff with jitter. attempt 0 → ~2s after first 409."""
    cap = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
    jitter_src = rng if rng is not None else random
    jitter = float(jitter_src.uniform(0.0, min(1.0, cap * 0.1)))
    return cap + jitter


def get_runtime() -> Optional["PollerRuntime"]:
    return _RUNTIME


def bind_runtime(runtime: Optional["PollerRuntime"]) -> None:
    global _RUNTIME
    _RUNTIME = runtime


def reset_poller_guard() -> None:
    """Tests only — allow another runtime in this process."""
    global _POLLER_STARTED, _RUNTIME
    _POLLER_STARTED = False
    _RUNTIME = None


def guard_handler(fn: Callable) -> Callable:
    """Drop new updates during shutdown; track in-flight handlers for drain."""

    @functools.wraps(fn)
    async def wrapped(update: Any, context: Any) -> Any:
        runtime = get_runtime()
        if runtime is not None and not runtime.accepting_updates:
            logger.info("Dropping update — shutdown in progress")
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
    """Controls Telegram polling acquisition, readiness, and graceful stop."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: Any = None,
        log: Any = None,
        grace_seconds: float = DEPLOY_GRACE_SECONDS,
        handler_drain_seconds: float = HANDLER_DRAIN_SECONDS,
        enforce_singleton: bool = True,
        install_signals: bool = True,
    ) -> None:
        self.clock = clock
        self.sleep = sleep
        self.rng = rng if rng is not None else random.Random()
        self.log = log if log is not None else logger
        self.grace_seconds = grace_seconds
        self.handler_drain_seconds = handler_drain_seconds
        self.enforce_singleton = enforce_singleton
        self.install_signals_enabled = install_signals

        self.state = STARTING
        self.process_started_at = clock()
        self.first_409_at: Optional[float] = None
        self.last_409_at: Optional[float] = None
        self.conflict_count = 0
        self.duplicate_error_emitted = False
        self.acquire_attempts = 0
        self.retry_count = 0
        self.lease_acquired = False
        self.accepting_updates = True
        self.in_flight = 0
        self._shutdown_event = asyncio.Event()
        self._signals_installed = False
        self._app_started = False
        self.sleep_delays: List[float] = []

    @property
    def shutting_down(self) -> bool:
        return self.state == SHUTTING_DOWN or self._shutdown_event.is_set()

    def handler_entered(self) -> None:
        self.in_flight += 1

    def handler_exited(self) -> None:
        self.in_flight = max(0, self.in_flight - 1)

    def request_shutdown(self) -> None:
        if self.state != SHUTTING_DOWN:
            self.log.info("Shutdown signal received — releasing Telegram polling lease")
        self.state = SHUTTING_DOWN
        self.accepting_updates = False
        self._shutdown_event.set()

    def _on_shutdown_signal(self, *_args: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self.request_shutdown)
        except RuntimeError:
            self.request_shutdown()

    def record_conflict(self, now: Optional[float] = None) -> str:
        """Record a 409. Returns 'overlap' during grace, else 'duplicate'."""
        now = self.clock() if now is None else now
        self.conflict_count += 1
        self.last_409_at = now
        if self.first_409_at is None:
            self.first_409_at = now
        if self.beyond_grace(now):
            return "duplicate"
        return "overlap"

    def beyond_grace(self, now: Optional[float] = None) -> bool:
        now = self.clock() if now is None else now
        started = self.process_started_at
        return (now - started) >= self.grace_seconds and self.conflict_count > 0

    def classify_conflict(self, now: Optional[float] = None) -> str:
        if self.beyond_grace(now):
            return "POLLER_ALREADY_ACTIVE_DUPLICATE"
        return "POLLER_ALREADY_ACTIVE"

    def _claim_singleton(self) -> None:
        global _POLLER_STARTED
        if not self.enforce_singleton:
            return
        if _POLLER_STARTED:
            raise RuntimeError(
                "Telegram polling already started in this process "
                "(TELEGRAM_POLLER_SINGLETON=true)"
            )
        _POLLER_STARTED = True

    async def acquire_polling_lease(self, get_updates: Callable) -> bool:
        """Probe getUpdates until the lease is free or shutdown is requested.

        First attempt is immediate. 409s back off 2s → 4s → 8s → 12s → 20s → 30s max.
        """
        self.state = STARTING
        while not self._shutdown_event.is_set():
            self.acquire_attempts += 1
            try:
                await get_updates(offset=-1, timeout=0, limit=1)
                self.lease_acquired = True
                self.retry_count = 0
                self.log.info("Telegram polling lease acquired.")
                return True
            except Exception as exc:
                if not is_poller_conflict(exc):
                    self.log.error("Telegram lease probe failed: %s", exc)
                    raise
                kind = self.record_conflict()
                if self.state != SHUTTING_DOWN:
                    self.state = WAITING_FOR_TELEGRAM_POLLER
                delay = next_backoff_seconds(self.retry_count, self.rng)
                self.retry_count += 1
                self.sleep_delays.append(delay)
                if kind == "duplicate":
                    if not self.duplicate_error_emitted:
                        self.log.error(DUPLICATE_ERROR)
                        self.duplicate_error_emitted = True
                    else:
                        self.log.error(
                            "Telegram polling conflict still active "
                            "(probable duplicate instance). Retrying in %.1fs.",
                            delay,
                        )
                else:
                    self.log.warning(
                        "Telegram poller already active (deploy overlap). "
                        "Retrying in %.1fs (attempt %s).",
                        delay,
                        self.retry_count,
                    )
                await self.sleep(delay)
        return False

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

    async def _stop_updater(self, app: Any) -> None:
        updater = getattr(app, "updater", None)
        if updater is None:
            return
        try:
            running = getattr(updater, "running", True)
            if running:
                await updater.stop()
        except Exception as exc:
            self.log.warning("Updater stop raised: %s", exc)

    async def _drain_and_close(self, app: Any) -> None:
        if self._app_started:
            stop = getattr(app, "stop", None)
            if callable(stop):
                try:
                    await asyncio.wait_for(stop(), timeout=self.handler_drain_seconds)
                except asyncio.TimeoutError:
                    self.log.warning(
                        "In-flight handler drain timed out after %.1fs",
                        self.handler_drain_seconds,
                    )
                except Exception as exc:
                    self.log.warning("Application stop raised: %s", exc)
        shutdown = getattr(app, "shutdown", None)
        if callable(shutdown):
            try:
                await shutdown()
            except Exception as exc:
                self.log.warning("Application shutdown raised: %s", exc)

    async def shutdown_app(self, app: Any) -> None:
        """Stop polling first, then drain handlers, then close the Telegram client."""
        if not self._shutdown_event.is_set():
            self.request_shutdown()
        else:
            self.state = SHUTTING_DOWN
            self.accepting_updates = False

        await self._stop_updater(app)
        self.log.info("Telegram polling stopped")
        await self._drain_and_close(app)
        self.log.info("MoodyBot shutdown complete")

    def _polling_error_callback(self, exc: BaseException) -> None:
        if is_poller_conflict(exc):
            kind = self.record_conflict()
            if kind == "duplicate":
                if not self.duplicate_error_emitted:
                    self.log.error(DUPLICATE_ERROR)
                    self.duplicate_error_emitted = True
                else:
                    self.log.error(
                        "Telegram polling conflict still active "
                        "(probable duplicate instance)."
                    )
            elif self.state == READY:
                self.log.warning(
                    "Telegram getUpdates conflict after lease was acquired "
                    "(another instance may be starting)."
                )
            else:
                self.log.warning(
                    "Telegram poller already active (deploy overlap): %s",
                    exc,
                )
            return
        self.log.error("Telegram polling error: %s", exc)

    async def run(self, app: Any) -> None:
        """Production entry: acquire lease, poll, stop cleanly on signal."""
        self._claim_singleton()
        bind_runtime(self)
        self.state = STARTING
        self.accepting_updates = True
        self.log.info("MoodyBot starting with OpenRouter.")
        self.log.info(
            "TELEGRAM_MODE=%s TELEGRAM_POLLER_SINGLETON=%s",
            telegram_mode(),
            str(poller_singleton_enabled()).lower(),
        )
        initialized = False
        try:
            if self.install_signals_enabled:
                self.install_signal_handlers()
            await app.initialize()
            initialized = True
            delete_webhook = getattr(getattr(app, "bot", None), "delete_webhook", None)
            if callable(delete_webhook):
                await delete_webhook(drop_pending_updates=True)
            get_updates = getattr(app.bot, "get_updates")
            acquired = await self.acquire_polling_lease(get_updates)
            if not acquired:
                return
            await app.start()
            self._app_started = True
            updater = app.updater
            await updater.start_polling(
                drop_pending_updates=True,
                error_callback=self._polling_error_callback,
            )
            self.state = READY
            self.log.info("MoodyBot ready.")
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
