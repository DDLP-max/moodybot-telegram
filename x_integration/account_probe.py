# -*- coding: utf-8 -*-
"""One read-only check of the Render user token and the ledger disk.

The token stays in the process. Callers receive status, username, and id.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from x_integration.state import MentionLedger, ledger_from_env, replies_enabled

logger = logging.getLogger("moodybot")

USERS_ME_URL = "https://api.x.com/2/users/me"
MENTIONS_URL = "https://api.x.com/2/users/{user_id}/mentions"
TOKEN_URL = "https://api.x.com/2/oauth2/token"


def validated_user_token(ledger: Optional[MentionLedger] = None) -> dict:
    """Select one user token, check it with users/me, and refresh only on 401.

    The cache wins when it exists. The environment token is used only when
    the cache is empty. A rejected cache token is not replaced by the
    environment token. The returned token must not be logged or put on /health.
    """
    book = ledger or ledger_from_env()
    cached = book.cached_access_token()
    token = cached or _env("X_USER_ACCESS_TOKEN")
    source = "cache" if cached else ("environment" if token else "")
    if not token:
        return {"ok": False, "token": "", "source": "", "http_status": 0, "username": "", "user_id": "", "reason": "missing"}
    status, username, user_id, _problem = _users_me(token)
    if status == 401 and _refresh_configured(book):
        _refresh_status, refreshed = refresh_access_token(book)
        if not refreshed:
            return {
                "ok": False,
                "token": "",
                "source": source,
                "http_status": status,
                "username": "",
                "user_id": "",
                "reason": "refresh_failed",
            }
        token = refreshed
        source = "refresh"
        status, username, user_id, _problem = _users_me(token)
    from x_integration.dry_run import CONFIRMED_USER_ID, CONFIRMED_USERNAME

    if status != 200 or username != CONFIRMED_USERNAME or user_id != CONFIRMED_USER_ID:
        return {
            "ok": False,
            "token": "",
            "source": source,
            "http_status": status,
            "username": username,
            "user_id": user_id,
            "reason": "rejected",
        }
    return {
        "ok": True,
        "token": token,
        "source": source,
        "http_status": 200,
        "username": username,
        "user_id": user_id,
        "reason": "",
    }


def run_account_probe(ledger: Optional[MentionLedger] = None) -> dict:
    from x_integration.diagnose import report as disk_report

    book = ledger or ledger_from_env()
    survived, marker = book.remember_restart_marker()
    disk = disk_report()
    token = book.cached_access_token() or _env("X_USER_ACCESS_TOKEN")
    refresh_configured = _refresh_configured(book)
    me_status = 0
    username = ""
    user_id = ""
    me_problem: dict = {}
    refresh_status = 0
    refresh_used = False
    if token:
        me_status, username, user_id, me_problem = _users_me(token)
        if me_status == 401 and refresh_configured:
            refresh_status, refreshed = refresh_access_token(book)
            refresh_used = True
            if refreshed:
                token = refreshed
                me_status, username, user_id, me_problem = _users_me(token)
    mentions_status = 0
    mentions_title = ""
    mentions_problem: dict = {}
    mentions_returned = None
    mentions_rate_limit: dict = {}
    if me_status == 200 and user_id and token:
        (
            mentions_status,
            mentions_title,
            mentions_problem,
            mentions_returned,
            mentions_rate_limit,
        ) = _mentions(user_id, token)
    result = {
        "state": "done",
        "users_me_status": me_status,
        "users_me_title": me_problem.get("title", ""),
        "users_me_problem": me_problem,
        "token_present": bool(token),
        "token_shape": _token_shape(token),
        "token_length": len(token),
        "username": username,
        "user_id": user_id,
        "mentions_status": mentions_status,
        "mentions_permitted": mentions_status == 200,
        "mentions_title": mentions_title,
        "mentions_problem": mentions_problem,
        "mentions_returned": mentions_returned,
        "mentions_rate_limit": mentions_rate_limit,
        "refresh_configured": refresh_configured,
        "refresh_used": refresh_used,
        "refresh_status": refresh_status,
        "x_state_dir": disk.get("x_state_dir", ""),
        "x_state_dir_source": disk.get("x_state_dir_source", ""),
        "database_path": disk.get("database_path", ""),
        "disk_mounted": bool(disk.get("disk_mounted")),
        "disk_mount_path": disk.get("disk_mount_path", ""),
        "database_on_mounted_disk": bool(disk.get("database_on_mounted_disk")),
        "sqlite_accessible": bool(disk.get("database_accessible")),
        "marker": marker,
        "marker_survived": survived,
        "replies_enabled": replies_enabled(),
        "poll_enabled": _env("X_POLL_ENABLED").lower() == "true",
    }
    return _redact(result, token)


def refresh_access_token(ledger: Optional[MentionLedger] = None) -> tuple[int, str]:
    """Rotate the user token once. Returns (http status, new access token).

    Status 0 means refresh is not configured. The new token is not logged.
    """
    book = ledger or ledger_from_env()
    client_id = _env("X_OAUTH2_CLIENT_ID")
    client_secret = _env("X_OAUTH2_CLIENT_SECRET")
    refresh = _refresh_token(book)
    if not client_id or not client_secret or not refresh:
        return 0, ""
    import httpx

    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
            },
            auth=(client_id, client_secret),
            timeout=20,
        )
    except httpx.HTTPError:
        logger.warning("X token refresh failed before a response")
        return 0, ""
    if response.status_code != 200:
        logger.warning("X token refresh http=%s", response.status_code)
        return response.status_code, ""
    try:
        body = response.json()
    except ValueError:
        return response.status_code, ""
    access = str(body.get("access_token") or "").strip()
    rotated = str(body.get("refresh_token") or "").strip() or refresh
    if not access:
        return response.status_code, ""
    book.store_oauth_tokens(access, rotated)
    return response.status_code, access


def _users_me(token: str) -> tuple[int, str, str, dict]:
    import httpx

    try:
        response = httpx.get(
            USERS_ME_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"user.fields": "username,id"},
            timeout=20,
        )
    except httpx.HTTPError:
        logger.warning("X users/me failed before a response")
        return 0, "", "", {}
    if response.status_code != 200:
        problem = _problem(response, token)
        logger.info(
            "X users/me http=%s reason=%s",
            response.status_code,
            problem.get("reason") or problem.get("title") or "-",
        )
        return response.status_code, "", "", problem
    try:
        data = (response.json() or {}).get("data") or {}
    except ValueError:
        return response.status_code, "", "", {}
    return response.status_code, str(data.get("username") or ""), str(data.get("id") or ""), {}


def _mentions(user_id: str, token: str) -> tuple[int, str, dict, object, dict]:
    import httpx

    try:
        response = httpx.get(
            MENTIONS_URL.format(user_id=user_id),
            headers={"Authorization": f"Bearer {token}"},
            params={"max_results": 5, "tweet.fields": "author_id"},
            timeout=20,
        )
    except httpx.HTTPError:
        logger.warning("X mentions read failed before a response")
        return 0, "", {}, None, {}
    rate_limit = _rate_limit(response)
    if response.status_code != 200:
        problem = _problem(response, token)
        title = problem.get("title") or _error_title(response)
        logger.info(
            "X mentions http=%s reason=%s",
            response.status_code,
            problem.get("reason") or title or "-",
        )
        return response.status_code, title, problem, None, rate_limit
    try:
        payload = response.json() or {}
    except ValueError:
        return response.status_code, "", {}, None, rate_limit
    data = payload.get("data") if isinstance(payload, dict) else None
    returned = len(data) if isinstance(data, list) else 0
    return response.status_code, "", {}, returned, rate_limit


def _problem(response, token: str) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    kept = {}
    for key in ("title", "detail", "type", "reason", "required_enrollment", "status"):
        if key not in payload or payload[key] in (None, ""):
            continue
        text = " ".join(str(payload[key]).split())[:240]
        if token and token in text:
            text = "[redacted]"
        kept[key] = text
    client_id = payload.get("client_id")
    if isinstance(client_id, (int, str)) and str(client_id).isdigit():
        kept["client_id"] = str(client_id)
    return kept


def _rate_limit(response) -> dict:
    headers = getattr(response, "headers", None)
    if headers is None:
        return {}
    kept = {}
    names = {
        "x-rate-limit-limit": "limit",
        "x-rate-limit-remaining": "remaining",
        "x-rate-limit-reset": "reset",
    }
    for source, name in names.items():
        raw = headers.get(source) if hasattr(headers, "get") else None
        if raw in (None, ""):
            continue
        text = str(raw).strip()
        if text.isdigit():
            kept[name] = int(text)
    return kept


def _token_shape(token: str) -> str:
    if not token:
        return "missing"
    parts = token.split(".")
    if len(parts) == 3 and all(parts):
        return "jwt"
    if token.startswith("AAAA"):
        return "app_bearer_prefix"
    return "opaque"


def _error_title(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    title = str(payload.get("title") or payload.get("reason") or "")
    title = " ".join(title.split())[:80]
    lowered = title.lower()
    if "bearer" in lowered or "token" in lowered:
        return ""
    return title


def _refresh_configured(ledger: MentionLedger) -> bool:
    return bool(
        _env("X_OAUTH2_CLIENT_ID")
        and _env("X_OAUTH2_CLIENT_SECRET")
        and _refresh_token(ledger)
    )


def _refresh_token(ledger: MentionLedger) -> str:
    """The dashboard key is X_OAUTH2_REFRESH_TOKEN. Honor the user-token alias too."""
    return (
        ledger.cached_refresh_token()
        or _env("X_OAUTH2_REFRESH_TOKEN")
        or _env("X_USER_REFRESH_TOKEN")
    )


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _redact(result: dict, token: str) -> dict:
    if not token:
        return result

    def walk(value):
        if isinstance(value, str):
            return value.replace(token, "[redacted]") if token in value else value
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    return walk(result)
