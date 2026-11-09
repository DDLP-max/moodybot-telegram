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
    me_title = ""
    refresh_status = 0
    refresh_used = False
    if token:
        me_status, username, user_id, me_title = _users_me(token)
        if me_status == 401 and refresh_configured:
            refresh_status, refreshed = refresh_access_token(book)
            refresh_used = True
            if refreshed:
                token = refreshed
                me_status, username, user_id, me_title = _users_me(token)
    mentions_status = 0
    mentions_title = ""
    if me_status == 200 and user_id and token:
        mentions_status, mentions_title = _mentions(user_id, token)
    result = {
        "state": "done",
        "users_me_status": me_status,
        "users_me_title": me_title,
        "username": username,
        "user_id": user_id,
        "mentions_status": mentions_status,
        "mentions_permitted": mentions_status == 200,
        "mentions_title": mentions_title,
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
    refresh = book.cached_refresh_token() or _env("X_OAUTH2_REFRESH_TOKEN")
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


def _users_me(token: str) -> tuple[int, str, str, str]:
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
        return 0, "", "", ""
    if response.status_code != 200:
        title = _error_title(response)
        logger.info("X users/me http=%s title=%s", response.status_code, title or "-")
        return response.status_code, "", "", title
    try:
        data = (response.json() or {}).get("data") or {}
    except ValueError:
        return response.status_code, "", "", ""
    return response.status_code, str(data.get("username") or ""), str(data.get("id") or ""), ""


def _mentions(user_id: str, token: str) -> tuple[int, str]:
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
        return 0, ""
    title = ""
    if response.status_code != 200:
        title = _error_title(response)
        logger.info("X mentions http=%s title=%s", response.status_code, title or "-")
    return response.status_code, title


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
        and (ledger.cached_refresh_token() or _env("X_OAUTH2_REFRESH_TOKEN"))
    )


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _redact(result: dict, token: str) -> dict:
    if not token:
        return result
    cleaned = {}
    for key, value in result.items():
        if isinstance(value, str) and token in value:
            cleaned[key] = value.replace(token, "")
        else:
            cleaned[key] = value
    return cleaned
