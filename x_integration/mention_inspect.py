# -*- coding: utf-8 -*-
"""Read the latest mentions without moving the production cursor.

The production ledger is opened only to report its cursor and today's
model-call count. This module does not claim events or set since_id.
"""
from __future__ import annotations

import os
from typing import Optional

from x_integration.state import ledger_from_env

MENTIONS_URL = "https://api.x.com/2/users/{user_id}/mentions"


def inspect_recent_mentions(user_id: str, *, token: Optional[str] = None) -> dict:
    book = ledger_from_env()
    snapshot = {
        "production_database": str(book.path),
        "production_since_id": book.get_since_id(),
        "production_model_calls_today": book.model_calls_today(),
    }
    access = (token if token is not None else os.environ.get("X_USER_ACCESS_TOKEN") or "").strip()
    if not access or not str(user_id).strip():
        return {
            "state": "not_configured",
            "mentions_status": 0,
            "mentions": [],
            **snapshot,
        }
    status, mentions, problem, rate_limit = _fetch(str(user_id).strip(), access)
    result = {
        "state": "done",
        "mentions_status": status,
        "mentions_returned": len(mentions) if status == 200 else None,
        "mentions_problem": problem,
        "mentions_rate_limit": rate_limit,
        "mentions": mentions,
        "poll_enabled": (os.environ.get("X_POLL_ENABLED") or "").strip().lower() == "true",
        "replies_enabled": (os.environ.get("X_REPLIES_ENABLED") or "").strip().lower() == "true",
        **snapshot,
    }
    return _redact(result, access)


def _fetch(user_id: str, token: str) -> tuple[int, list, dict, dict]:
    import httpx

    try:
        response = httpx.get(
            MENTIONS_URL.format(user_id=user_id),
            headers={"Authorization": f"Bearer {token}"},
            params={
                "max_results": 5,
                "tweet.fields": "author_id,created_at,conversation_id,text",
                "expansions": "author_id",
                "user.fields": "username",
            },
            timeout=20,
        )
    except httpx.HTTPError:
        return 0, [], {}, {}
    rate_limit = _rate_limit(response)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200:
        return response.status_code, [], _problem(payload, token), rate_limit
    if not isinstance(payload, dict):
        return response.status_code, [], {}, rate_limit
    names = {}
    includes = payload.get("includes") if isinstance(payload.get("includes"), dict) else {}
    for user in includes.get("users") or []:
        if isinstance(user, dict) and user.get("id"):
            names[str(user.get("id"))] = str(user.get("username") or "")
    mentions = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        author_id = str(item.get("author_id") or "")
        text = item.get("text") if isinstance(item.get("text"), str) else ""
        mentions.append(
            {
                "post_id": str(item.get("id") or ""),
                "created_at": str(item.get("created_at") or ""),
                "author_id": author_id,
                "author_username": names.get(author_id, ""),
                "conversation_id": str(item.get("conversation_id") or item.get("id") or ""),
                "text": " ".join(text.split())[:1000],
            }
        )
    return response.status_code, mentions, {}, rate_limit


def _problem(payload, token: str) -> dict:
    if not isinstance(payload, dict):
        return {}
    kept = {}
    for key in ("title", "detail", "type", "reason", "required_enrollment", "status"):
        if payload.get(key) in (None, ""):
            continue
        text = " ".join(str(payload[key]).split())[:240]
        if token and token in text:
            text = "[redacted]"
        kept[key] = text
    return kept


def _rate_limit(response) -> dict:
    headers = getattr(response, "headers", None)
    if headers is None or not hasattr(headers, "get"):
        return {}
    kept = {}
    for source, name in (
        ("x-rate-limit-limit", "limit"),
        ("x-rate-limit-remaining", "remaining"),
        ("x-rate-limit-reset", "reset"),
    ):
        raw = headers.get(source)
        if raw not in (None, "") and str(raw).strip().isdigit():
            kept[name] = int(str(raw).strip())
    return kept


def _redact(value, token: str):
    if not token:
        return value
    if isinstance(value, str):
        return value.replace(token, "[redacted]")
    if isinstance(value, dict):
        return {key: _redact(item, token) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, token) for item in value]
    return value
