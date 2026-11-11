# -*- coding: utf-8 -*-
"""Telegram transport lifecycle for MoodyBot.

Production (Render): TELEGRAM_MODE=webhook
  initialize → start → setWebhook once → aiohttp POST /telegram/webhook → READY
  Updates feed Application.process_update (same handlers as polling).

Local optional: TELEGRAM_MODE=polling
  initialize → start → updater.start_polling (no lease / no 409 classifiers)

Never log bot tokens or API keys. HTTP URLs to api.telegram.org are redacted.
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Optional

from aiohttp import web
from telegram import Update

logger = logging.getLogger("moodybot")

STARTING = "STARTING"
READY = "READY"
SHUTTING_DOWN = "SHUTTING_DOWN"

HANDLER_DRAIN_SECONDS = 8.0
WEBHOOK_PATH = "/telegram/webhook"
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
# Telegram setWebhook secret_token: 1–256 chars, only A-Z a-z 0-9 _ -
_WEBHOOK_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")

# Redact Telegram Bot API URLs that embed the token after /bot
_TELEGRAM_BOT_URL = re.compile(
    r"(https?://api\.telegram\.org/bot)[^/\s\"']+",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(Bearer\s+)(\S+)", re.IGNORECASE)


def _x_poll_enabled() -> bool:
    return (os.environ.get("X_POLL_ENABLED") or "").strip().lower() == "true"

_RUNTIME: Optional["BotRuntime"] = None
_REDACTION_INSTALLED = False


class SecretRedactFilter(logging.Filter):
    """Strip credentials from every log record (httpx dumps full bot URLs)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = _TELEGRAM_BOT_URL.sub(r"\1[REDACTED]", msg)
        redacted = _BEARER.sub(r"\1[REDACTED]", redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def install_log_redaction() -> None:
    """Install once on root + common HTTP loggers."""
    global _REDACTION_INSTALLED
    if _REDACTION_INSTALLED:
        return
    filt = SecretRedactFilter()
    root = logging.getLogger()
    root.addFilter(filt)
    for name in ("httpx", "httpcore", "telegram", "aiohttp", "moodybot"):
        logging.getLogger(name).addFilter(filt)
    for handler in root.handlers:
        handler.addFilter(filt)
    _REDACTION_INSTALLED = True


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
        "render_instance_id": os.environ.get("RENDER_INSTANCE_ID") or "",
        "render_service_name": os.environ.get("RENDER_SERVICE_NAME") or "",
        "render": os.environ.get("RENDER") or "",
        "git_commit": resolve_git_commit(),
    }


def telegram_mode() -> str:
    """webhook (production) or polling (local only). Default: webhook on Render."""
    raw = (os.environ.get("TELEGRAM_MODE") or "").strip().lower()
    if raw in {"webhook", "polling"}:
        return raw
    if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
        return "webhook"
    return "polling"


def webhook_base_url() -> str:
    base = (
        os.environ.get("TELEGRAM_WEBHOOK_BASE_URL")
        or os.environ.get("RENDER_EXTERNAL_URL")
        or ""
    ).strip().rstrip("/")
    return base


def webhook_secret() -> str:
    return (os.environ.get("TELEGRAM_WEBHOOK_SECRET") or "").strip()


def validate_webhook_secret_format(secret: str) -> None:
    """Raise ValueError if secret is not valid for Telegram setWebhook."""
    if not secret:
        raise ValueError(
            "TELEGRAM_WEBHOOK_SECRET is required in webhook mode. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if not _WEBHOOK_SECRET_RE.fullmatch(secret):
        raise ValueError(
            "TELEGRAM_WEBHOOK_SECRET contains characters Telegram rejects. "
            "Allowed only: A-Z a-z 0-9 _ - (1–256 chars). "
            "Do not use secrets.token_urlsafe() (+ / =). "
            "Use: python -c \"import secrets; print(secrets.token_hex(32))\""
        )


def webhook_listen_port() -> int:
    try:
        return int(os.environ.get("PORT") or "8080")
    except ValueError:
        return 8080


def get_runtime() -> Optional["BotRuntime"]:
    return _RUNTIME


def bind_runtime(runtime: Optional["BotRuntime"]) -> None:
    global _RUNTIME
    _RUNTIME = runtime


def reset_runtime() -> None:
    """Tests only."""
    global _RUNTIME
    _RUNTIME = None


# Back-compat alias for older imports / tests
reset_poller_guard = reset_runtime


def flush_logs() -> None:
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
            runtime._info("Dropping update — shutdown in progress")
            return None
        if runtime is not None:
            runtime.handler_entered()
        try:
            return await fn(update, context)
        finally:
            if runtime is not None:
                runtime.handler_exited()

    return wrapped


def _activation_gate() -> dict:
    try:
        from x_integration.state import ledger_from_env

        status = ledger_from_env().activation_status()
        return {
            "mode": status.get("mode") or "off",
            "remaining": status.get("remaining"),
            "stop_reason": status.get("stop_reason") or "",
        }
    except Exception:
        return {"mode": "off", "remaining": None, "stop_reason": ""}


def _operating_mode() -> str:
    try:
        from x_integration.state import operating_mode

        return operating_mode()
    except Exception:
        return "disabled"


def _publish_halt() -> dict:
    try:
        from x_integration.state import ledger_from_env

        return ledger_from_env().publish_halt_status()
    except Exception:
        return {"auth_failures": None, "unexpected_failures": None, "halt_reason": ""}


def _reply_allowance() -> dict:
    try:
        from x_integration.state import ledger_from_env

        return ledger_from_env().automatic_reply_allowance()
    except Exception:
        return {"limit": 5, "used": None, "inflight": None, "remaining": None, "window_hours": 24}


def _health_mentions(payload: Any) -> Any:
    """Health stays public. Mention text does not."""
    if not isinstance(payload, dict):
        return payload
    cleaned = dict(payload)
    mentions = []
    for item in payload.get("mentions") or []:
        if not isinstance(item, dict):
            continue
        visible = {key: value for key, value in item.items() if key != "text"}
        visible["text_length"] = len(str(item.get("text") or ""))
        mentions.append(visible)
    if "mentions" in cleaned:
        cleaned["mentions"] = mentions
    return cleaned


def _health_dry_run(payload: Any) -> Any:
    """Health stays public. The draft and the source post do not."""
    if not isinstance(payload, dict):
        return payload
    cleaned = {key: value for key, value in payload.items() if key not in {"reply_text", "source_post"}}
    stored = payload.get("stored")
    if isinstance(stored, dict):
        cleaned["stored"] = {key: value for key, value in stored.items() if key != "reply_text"}
        cleaned["reply_stored"] = bool(stored.get("reply_text"))
    source = payload.get("source_post")
    if isinstance(source, dict):
        cleaned["source_post_id"] = source.get("post_id") or ""
        cleaned["source_author"] = source.get("author_username") or ""
    return cleaned


class BotRuntime:
    """Owns Application lifecycle + transport (webhook or local polling)."""

    def __init__(
        self,
        *,
        mode: Optional[str] = None,
        log: Any = None,
        handler_drain_seconds: float = HANDLER_DRAIN_SECONDS,
        install_signals: bool = True,
        instance_id: Optional[str] = None,
        clock: Callable[[], float] = time.monotonic,
        webhook_base: Optional[str] = None,
        webhook_secret_token: Optional[str] = None,
        listen_host: str = "0.0.0.0",
        listen_port: Optional[int] = None,
    ) -> None:
        install_log_redaction()
        self.log = log if log is not None else logger
        self.handler_drain_seconds = handler_drain_seconds
        self.install_signals_enabled = install_signals
        self.instance_id = instance_id or make_instance_id()
        self.clock = clock
        self.mode = (mode or telegram_mode()).strip().lower()
        if self.mode not in {"webhook", "polling"}:
            raise ValueError(f"Unsupported TELEGRAM_MODE={self.mode!r}")

        self.webhook_base = (webhook_base if webhook_base is not None else webhook_base_url()).rstrip("/")
        self.webhook_secret_token = (
            webhook_secret_token if webhook_secret_token is not None else webhook_secret()
        )
        self.listen_host = listen_host
        self.listen_port = webhook_listen_port() if listen_port is None else listen_port

        self.state = STARTING
        self.accepting_updates = True
        self.in_flight = 0
        self._shutdown_event = asyncio.Event()
        self._signals_installed = False
        self._app_started = False

        self.process_started_at = clock()
        self.sigterm_at: Optional[float] = None
        self.env = render_env_snapshot()
        self.x_probe = {"state": "pending"}
        self.x_mentions = {"state": "pending"}
        self.x_dry_run = {"state": "pending"}
        self.x_publish = {"state": "pending"}
        self.x_live_test = {"state": "pending"}
        self.x_poll = {"state": "pending"}

        self._http_runner: Optional[web.AppRunner] = None
        self._http_site: Optional[web.TCPSite] = None
        self.set_webhook_calls = 0
        self.start_polling_calls = 0
        self._ptb_app: Any = None

    # --- logging ---
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

    @property
    def shutting_down(self) -> bool:
        return self.state == SHUTTING_DOWN or self._shutdown_event.is_set()

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base}{WEBHOOK_PATH}"

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

    def validate_webhook_secret(self, header_value: Optional[str]) -> bool:
        expected = self.webhook_secret_token or ""
        if not expected:
            return False
        return (header_value or "") == expected

    async def handle_telegram_webhook(self, request: web.Request) -> web.Response:
        """POST /telegram/webhook — validate secret, process Update, 200 ASAP."""
        if self.shutting_down or not self.accepting_updates:
            return web.Response(status=503, text="shutting down")

        header = request.headers.get(SECRET_HEADER) or request.headers.get(
            SECRET_HEADER.lower()
        )
        if not self.validate_webhook_secret(header):
            self._warning("Rejected webhook: invalid or missing secret token")
            return web.Response(status=403, text="forbidden")

        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400, text="invalid json")

        app = self._ptb_app
        if app is None:
            return web.Response(status=503, text="not ready")

        update_id = data.get("update_id", "?")
        self._info("[update %s] webhook received", update_id)
        try:
            from moodybot_vision import summarize_raw_update
            import json as _json
            self._info(
                "[update %s] webhook shape %s",
                update_id,
                _json.dumps(summarize_raw_update(data), sort_keys=True),
            )
        except Exception:
            self.log.exception(self._fmt("[update %s] webhook shape failed"), update_id)

        raw_token = None
        try:
            from moodybot_vision import bind_raw_update, reset_raw_update
            raw_token = bind_raw_update(data)
        except Exception:
            self.log.exception(self._fmt("[update %s] raw update bind failed"), update_id)
            reset_raw_update = None

        try:
            update = Update.de_json(data, app.bot)
        except Exception:
            self.log.exception(
                self._fmt("[update %s] Update.de_json failed"), update_id
            )
            flush_logs()
            if raw_token is not None:
                reset_raw_update(raw_token)
            return web.Response(status=400, text="bad update")

        if update is None:
            self._warning("[update %s] empty update after de_json", update_id)
            if raw_token is not None:
                reset_raw_update(raw_token)
            return web.Response(status=400, text="empty update")

        update_type = "unknown"
        if update.message:
            update_type = "message"
        elif update.callback_query:
            update_type = "callback_query"
        elif update.edited_message:
            update_type = "edited_message"
        self._info("[update %s] parsed update type=%s", update_id, update_type)
        self._info("[update %s] dispatching application.process_update", update_id)

        # Schedule while the raw update is still bound. create_task copies that context.
        asyncio.create_task(self._process_update_safe(app, update, update_id))
        if raw_token is not None:
            reset_raw_update(raw_token)
        return web.Response(status=200, text="ok")

    async def _process_update_safe(
        self, app: Any, update: Update, update_id: Any = None
    ) -> None:
        uid = update_id if update_id is not None else getattr(update, "update_id", "?")
        try:
            await app.process_update(update)
            self._info("[update %s] process_update complete", uid)
        except Exception:
            self.log.exception(
                self._fmt("[update %s] application.process_update failed"), uid
            )
            flush_logs()

    def _remember_poll(self, result: dict) -> None:
        previous = self.x_poll if isinstance(self.x_poll, dict) else {}
        incoming = dict(result)
        if previous.get("polled_at") and previous.get("polled_at") != incoming.get("polled_at"):
            incoming["previous_polled_at"] = previous.get("polled_at")
            incoming["previous_cycle"] = previous.get("cycle")
        kept = {}
        for key in (
            "state",
            "status",
            "discovered",
            "queued",
            "filtered",
            "since_id",
            "replies_enabled",
            "published",
            "drafted",
            "cycle",
            "polled_at",
            "previous_polled_at",
            "previous_cycle",
            "token_source",
            "users_me_status",
            "username",
            "http_status",
        ):
            if key in incoming:
                kept[key] = incoming[key]
        self.x_poll = kept

    async def handle_health(self, request: web.Request) -> web.Response:
        body = {
            "status": "ok" if self.state == READY else self.state.lower(),
            "mode": self.mode,
            "instance_id": self.instance_id,
            "git_commit": (self.env.get("git_commit") or "unknown"),
            "x_probe": self.x_probe,
            "x_mentions": _health_mentions(self.x_mentions),
            "x_dry_run": _health_dry_run(self.x_dry_run),
            "x_publish": self.x_publish,
            "x_live_test": self.x_live_test,
            "x_poll": self.x_poll,
            "x_reply_allowance": _reply_allowance(),
            "x_activation": _activation_gate(),
            "x_operating_mode": _operating_mode(),
            "x_publish_halt": _publish_halt(),
        }
        return web.json_response(body)

    def build_http_app(self) -> web.Application:
        http_app = web.Application()
        http_app.router.add_post(WEBHOOK_PATH, self.handle_telegram_webhook)
        http_app.router.add_get("/health", self.handle_health)
        http_app.router.add_get("/", self.handle_health)
        from x_integration.webhook import X_WEBHOOK_PATH, handle_x_crc, handle_x_event

        http_app.router.add_get(X_WEBHOOK_PATH, handle_x_crc)
        http_app.router.add_post(X_WEBHOOK_PATH, handle_x_event)
        return http_app

    async def _start_http_server(self) -> None:
        http_app = self.build_http_app()
        runner = web.AppRunner(http_app)
        await runner.setup()
        site = web.TCPSite(runner, self.listen_host, self.listen_port)
        await site.start()
        self._http_runner = runner
        self._http_site = site
        self._info("HTTP server listening on %s:%s", self.listen_host, self.listen_port)

    async def _stop_http_server(self) -> None:
        if self._http_site is not None:
            try:
                await self._http_site.stop()
            except Exception as exc:
                self._warning("HTTP site stop raised: %s", exc)
            self._http_site = None
        if self._http_runner is not None:
            try:
                await self._http_runner.cleanup()
            except Exception as exc:
                self._warning("HTTP runner cleanup raised: %s", exc)
            self._http_runner = None

    async def configure_telegram_webhook(self, app: Any) -> None:
        if not self.webhook_base:
            raise RuntimeError(
                "TELEGRAM_WEBHOOK_BASE_URL (or RENDER_EXTERNAL_URL) is required in webhook mode"
            )
        validate_webhook_secret_format(self.webhook_secret_token or "")
        url = self.webhook_url
        await app.bot.set_webhook(
            url=url,
            secret_token=self.webhook_secret_token,
            drop_pending_updates=False,
        )
        self.set_webhook_calls += 1
        self._info("Telegram webhook configured")

    async def _start_polling_local(self, app: Any) -> None:
        """Local-dev only. Production must never enter this path."""
        updater = app.updater
        await updater.start_polling(drop_pending_updates=False)
        self.start_polling_calls += 1
        self._info("Telegram updater polling started (local TELEGRAM_MODE=polling)")

    async def _stop_polling_if_needed(self, app: Any) -> None:
        if self.mode != "polling":
            return
        updater = getattr(app, "updater", None)
        if updater is None:
            return
        try:
            if getattr(updater, "running", False):
                self._info("stopping Telegram updater")
                await updater.stop()
                self._info("Telegram updater stopped")
        except Exception as exc:
            self._warning("Updater stop raised: %s", exc)

    async def shutdown_app(self, app: Any) -> None:
        if not self._shutdown_event.is_set():
            self.request_shutdown(signal_name="SIGTERM")
        else:
            self.state = SHUTTING_DOWN
            self.accepting_updates = False

        await self._stop_http_server()
        await self._stop_polling_if_needed(app)

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
        self._info(
            "MoodyBot shutdown complete instance_id=%s pid=%s git_commit=%s",
            self.instance_id,
            self.env.get("pid"),
            self.env.get("git_commit") or "unknown",
        )

    async def _run_x_probe(self) -> None:
        from x_integration.account_probe import run_account_probe

        try:
            result = await asyncio.to_thread(run_account_probe)
        except Exception:
            self.log.exception("X account probe failed")
            result = {"state": "error"}
        self.x_probe = result
        user_id = str(result.get("user_id") or "")
        if result.get("users_me_status") == 200 and user_id:
            try:
                from x_integration.mention_inspect import inspect_recent_mentions

                self.x_mentions = await asyncio.to_thread(inspect_recent_mentions, user_id)
            except Exception:
                self.log.exception("X mention inspect failed")
                self.x_mentions = {"state": "error"}
        else:
            self.x_mentions = {"state": "skipped"}
        if (
            result.get("users_me_status") == 200
            and result.get("username")
            and user_id
        ):
            try:
                from x_integration.dry_run import run_controlled_dry_run

                self.x_dry_run = await asyncio.to_thread(
                    run_controlled_dry_run,
                    str(result.get("username") or ""),
                    user_id,
                )
            except Exception:
                self.log.exception("X dry run failed")
                self.x_dry_run = {"state": "error"}
        else:
            self.x_dry_run = {"state": "skipped"}
        dry = self.x_dry_run
        self._info(
            "X dry run state=%s post=%s first=%s replay=%s dedup=%s cap=%s "
            "cursor_unchanged=%s spend_unchanged=%s",
            dry.get("state"),
            dry.get("post_id") or "-",
            dry.get("first_status") or "-",
            dry.get("second_status") or "-",
            dry.get("deduplicated"),
            dry.get("cap_blocks_next"),
            dry.get("production_cursor_unchanged"),
            dry.get("production_spend_unchanged"),
        )
        self._info(
            "X account probe state=%s users_me=%s username=%s user_id=%s mentions=%s "
            "permitted=%s dir=%s mounted=%s marker_survived=%s",
            result.get("state"),
            result.get("users_me_status"),
            result.get("username") or "-",
            result.get("user_id") or "-",
            result.get("mentions_status"),
            result.get("mentions_permitted"),
            result.get("x_state_dir") or "-",
            result.get("disk_mounted"),
            result.get("marker_survived"),
        )
        try:
            from x_integration.operator_publish import run_operator_publish

            self.x_publish = await asyncio.to_thread(run_operator_publish)
        except Exception:
            self.log.exception("X one-shot publish failed")
            self.x_publish = {"state": "error", "posted": False}
        publish = self.x_publish
        self._info(
            "X publish state=%s posted=%s account=%s write=%s preview=%s publish=%s reply_id=%s",
            publish.get("state"),
            publish.get("posted"),
            publish.get("account") or "-",
            publish.get("write_evidence") or "-",
            publish.get("preview_status") or "-",
            publish.get("publish_status") or "-",
            publish.get("x_reply_id") or "-",
        )
        try:
            from x_integration.live_reply import run_live_reply

            self.x_live_test = await asyncio.to_thread(run_live_reply)
        except Exception:
            self.log.exception("X live reply failed")
            self.x_live_test = {"state": "error", "posted": False}
        live = self.x_live_test
        self._info(
            "X live reply state=%s posted=%s http=%s reply_id=%s",
            live.get("state"),
            live.get("posted"),
            live.get("http_status") or 0,
            live.get("x_reply_id") or "-",
        )
        if not _x_poll_enabled():
            self.x_poll = {"state": "disabled", "replies_enabled": False}
        survey = self.x_poll
        self._info(
            "X mention survey state=%s status=%s discovered=%s queued=%s since_id=%s",
            survey.get("state"),
            survey.get("status") or "-",
            survey.get("discovered", 0),
            len(survey.get("queued") or []),
            survey.get("since_id") or "-",
        )

    async def run(self, app: Any) -> None:
        install_log_redaction()
        bind_runtime(self)
        self._ptb_app = app
        self.state = STARTING
        self.accepting_updates = True
        self.env = render_env_snapshot()
        self.process_started_at = self.clock()

        self._info("MoodyBot starting")
        self._info(
            "instance lifetime instance_id=%s pid=%s hostname=%s "
            "RENDER_SERVICE_ID=%s git_commit=%s TELEGRAM_MODE=%s",
            self.instance_id,
            self.env.get("pid"),
            self.env.get("hostname"),
            self.env.get("render_service_id") or "unset",
            self.env.get("git_commit") or "unknown",
            self.mode,
        )
        initialized = False
        poll_task = None
        probe_task = None
        try:
            if self.install_signals_enabled:
                self.install_signal_handlers()

            await app.initialize()
            initialized = True
            self._info("application initialized")

            await app.start()
            self._app_started = True
            self._info("application started")

            if self.mode == "webhook":
                await self._start_http_server()
                await self.configure_telegram_webhook(app)
            else:
                await self._start_polling_local(app)

            self.state = READY
            self._info("MoodyBot ready")
            probe_task = asyncio.create_task(self._run_x_probe())
            if _x_poll_enabled():
                from x_integration.poll import poll_loop

                poll_task = asyncio.create_task(
                    poll_loop(self._shutdown_event, record=self._remember_poll)
                )
                self._info("X mention poll armed")
            await self._shutdown_event.wait()
        finally:
            if probe_task is not None:
                probe_task.cancel()
                try:
                    await probe_task
                except asyncio.CancelledError:
                    pass
            if poll_task is not None:
                poll_task.cancel()
                try:
                    await poll_task
                except asyncio.CancelledError:
                    pass
            if initialized:
                await self.shutdown_app(app)
            bind_runtime(None)
            self._ptb_app = None


# Back-compat name used by older moodybot imports
PollerRuntime = BotRuntime
