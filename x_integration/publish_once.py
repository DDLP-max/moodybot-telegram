# -*- coding: utf-8 -*-
"""Publish one approved reply. Automatic replies and polling stay off.

The command posts only when the operator passes the original post id,
the exact stored draft, and --confirm POST:<post id>. It does not call
the model. A timeout or a dropped connection is recorded as ambiguous
and is not retried.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from x_integration.dry_run import CONFIRMED_USER_ID, CONFIRMED_USERNAME, DRY_RUN_FILENAME
from x_integration.state import MentionLedger, ledger_from_env, state_dir

TWEETS_URL = "https://api.x.com/2/tweets"
USERS_ME_URL = "https://api.x.com/2/users/me"
WRITE_LEVELS = {"read-write", "read-write-directmessages"}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Post one approved X reply. Omit --confirm to preview only."
    )
    parser.add_argument("--post-id", required=True)
    parser.add_argument("--draft-file", required=True)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    try:
        draft = Path(args.draft_file).read_text(encoding="utf-8")
    except OSError:
        print("status: refused")
        print("reason: draft_file_unreadable")
        return 2
    result = execute_publish(
        post_id=str(args.post_id).strip(),
        draft_text=draft,
        confirm=str(args.confirm or ""),
    )
    _print_result(result)
    return _exit_code(result)


def _exit_code(result: dict) -> int:
    code = result.get("exit_code")
    if code is None:
        return 2
    return int(code)


def execute_publish(
    *,
    post_id: str,
    draft_text: str,
    confirm: str,
    production: Optional[MentionLedger] = None,
    draft_db: Optional[Path] = None,
    verify=None,
    send=None,
    token: Optional[str] = None,
) -> dict:
    """Return the publish result. Network helpers are replaceable in tests."""
    replies_before = os.environ.get("X_REPLIES_ENABLED")
    poll_before = os.environ.get("X_POLL_ENABLED")
    book = production or ledger_from_env()
    since_before = book.get_since_id()
    calls_before = book.model_calls_today()
    result = {
        "post_id": post_id,
        "posted": False,
        "status": "refused",
        "reason": "",
        "exit_code": 2,
        "x_reply_id": "",
        "model_called": False,
    }
    if _flag_on("X_POLL_ENABLED") or _flag_on("X_REPLIES_ENABLED"):
        result["reason"] = "automatic_flags_enabled"
        return _finish_flags(result, book, since_before, calls_before, replies_before, poll_before)
    if not post_id.isdigit():
        result["reason"] = "invalid_post_id"
        return _finish_flags(result, book, since_before, calls_before, replies_before, poll_before)
    stored = stored_draft(draft_db or (state_dir()[0] / DRY_RUN_FILENAME), post_id)
    supplied = normalize_draft(draft_text)
    if not stored or supplied != stored:
        result["reason"] = "draft_mismatch"
        return _finish_flags(result, book, since_before, calls_before, replies_before, poll_before)
    result["draft_sha256"] = hashlib.sha256(stored.encode("utf-8")).hexdigest()
    access = token if token is not None else (os.environ.get("X_USER_ACCESS_TOKEN") or "")
    access = access.strip()
    if not access:
        result["reason"] = "token_missing"
        return _finish_flags(result, book, since_before, calls_before, replies_before, poll_before)
    credential = (verify or verify_posting_credential)(access)
    result["username"] = credential.get("username") or ""
    result["user_id"] = credential.get("user_id") or ""
    result["write_evidence"] = credential.get("write_evidence") or ""
    if not credential.get("ok"):
        result["reason"] = credential.get("reason") or "credential_rejected"
        return _redact(
            _finish_flags(result, book, since_before, calls_before, replies_before, poll_before),
            access,
        )
    if confirm != f"POST:{post_id}":
        result["status"] = "preview"
        result["reason"] = "confirmation_required"
        result["exit_code"] = 0
        result["reply_text"] = stored
        return _redact(
            _finish_flags(result, book, since_before, calls_before, replies_before, poll_before),
            access,
        )
    claim = book.claim_publication(post_id, stored)
    if claim != "claimed":
        result["status"] = "blocked"
        result["reason"] = claim
        result["exit_code"] = 4 if claim == "posted" else 3
        return _redact(
            _finish_flags(result, book, since_before, calls_before, replies_before, poll_before),
            access,
        )
    try:
        outcome = (send or send_reply)(access, post_id, stored)
    except Exception:
        book.finish_publication(post_id, status="ambiguous", detail="send_error")
        outcome = {"outcome": "ambiguous", "http_status": 0, "detail": "send_error", "x_reply_id": ""}
    status = str(outcome.get("outcome") or "ambiguous")
    if status not in {"posted", "failed", "ambiguous"}:
        status = "ambiguous"
    reply_id = str(outcome.get("x_reply_id") or "")
    if status == "posted" and not reply_id:
        status = "ambiguous"
    book.finish_publication(
        post_id,
        status=status,
        x_reply_id=reply_id if status == "posted" else "",
        http_status=int(outcome.get("http_status") or 0),
        detail=str(outcome.get("detail") or ""),
        problem=outcome.get("problem") if isinstance(outcome.get("problem"), dict) else None,
    )
    saved = book.publication(post_id) or {}
    result.update(
        {
            "posted": status == "posted",
            "status": status,
            "reason": "" if status == "posted" else status,
            "exit_code": {"posted": 0, "failed": 5, "ambiguous": 3}.get(status, 3),
            "x_reply_id": saved.get("x_reply_id") or "",
            "http_status": saved.get("http_status") or 0,
            "detail": saved.get("detail") or "",
            "problem": saved.get("problem") or {},
            "created_at": saved.get("created_at") or "",
            "updated_at": saved.get("updated_at") or "",
            "reply_text": saved.get("reply_text") or "",
        }
    )
    return _redact(
        _finish_flags(result, book, since_before, calls_before, replies_before, poll_before),
        access,
    )


def stored_draft(path: Path, post_id: str) -> str:
    """Read the dry-run reply. Does not create the file or call the model."""
    database = Path(path)
    if not database.is_file():
        return ""
    conn = sqlite3.connect(database)
    try:
        row = conn.execute(
            "SELECT reply_text, status FROM events WHERE event_id = ?",
            (f"dry-run:{post_id}",),
        ).fetchone()
    except sqlite3.Error:
        return ""
    finally:
        conn.close()
    if row is None or row[1] != "dry_run":
        return ""
    return str(row[0] or "")


def normalize_draft(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    return normalized


def verify_posting_credential(token: str) -> dict:
    """Confirm the bearer is @MoodyBotAI and carries write evidence.

    X does not offer token introspection for an opaque bearer. Write
    evidence is tweet.write on a scope header when X sends one, otherwise
    a write x-access-level. Neither is treated as a successful post.
    """
    import httpx

    try:
        response = httpx.get(
            USERS_ME_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"user.fields": "username,id"},
            timeout=20,
        )
    except httpx.HTTPError:
        return {"ok": False, "reason": "users_me_failed", "username": "", "user_id": "", "write_evidence": ""}
    username = ""
    user_id = ""
    if response.status_code == 200:
        try:
            data = (response.json() or {}).get("data") or {}
        except ValueError:
            data = {}
        username = str(data.get("username") or "")
        user_id = str(data.get("id") or "")
    account_ok = (
        response.status_code == 200
        and username == CONFIRMED_USERNAME
        and user_id == CONFIRMED_USER_ID
    )
    scopes = _scopes(response.headers)
    level = str(response.headers.get("x-access-level") or "").strip().lower()
    if scopes:
        write_ok = "tweet.write" in scopes
        evidence = "tweet.write" if write_ok else ""
    else:
        write_ok = level in WRITE_LEVELS
        evidence = "x-access-level" if write_ok else ""
    if not account_ok:
        reason = "unexpected_account" if response.status_code == 200 else "users_me_failed"
    elif not write_ok:
        reason = "tweet_write_unverified"
    else:
        reason = ""
    return {
        "ok": account_ok and write_ok,
        "reason": reason,
        "username": username,
        "user_id": user_id,
        "write_evidence": evidence,
    }


def send_reply(token: str, post_id: str, text: str) -> dict:
    """POST one reply. Transport failures stay ambiguous and are not retried."""
    import httpx

    try:
        response = httpx.post(
            TWEETS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"text": text, "reply": {"in_reply_to_tweet_id": post_id}},
            timeout=20,
        )
    except httpx.TimeoutException:
        return {"outcome": "ambiguous", "http_status": 0, "detail": "timeout", "x_reply_id": ""}
    except httpx.TransportError:
        return {"outcome": "ambiguous", "http_status": 0, "detail": "transport", "x_reply_id": ""}
    if response.status_code in {200, 201}:
        try:
            body = response.json()
        except ValueError:
            return {
                "outcome": "ambiguous",
                "http_status": response.status_code,
                "detail": "unreadable_body",
                "x_reply_id": "",
            }
        data = body.get("data") if isinstance(body, dict) else None
        reply_id = str((data or {}).get("id") or "") if isinstance(data, dict) else ""
        if not reply_id:
            return {
                "outcome": "ambiguous",
                "http_status": response.status_code,
                "detail": "missing_reply_id",
                "x_reply_id": "",
            }
        return {
            "outcome": "posted",
            "http_status": response.status_code,
            "detail": "",
            "x_reply_id": reply_id,
        }
    return {
        "outcome": "failed",
        "http_status": response.status_code,
        "detail": _problem_title(response, token),
        "problem": problem_record(response, token),
        "x_reply_id": "",
    }


def problem_record(response, token: str) -> dict:
    """Keep the X error fields and a request id. Drop the bearer if it appears."""
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    kept = {}
    for key in ("type", "title", "detail", "reason", "errors", "required_enrollment", "status"):
        if key not in payload or payload[key] in (None, ""):
            continue
        kept[key] = _sanitize_problem(payload[key], token)
    headers = getattr(response, "headers", None)
    transaction = ""
    if headers is not None and hasattr(headers, "get"):
        transaction = str(headers.get("x-transaction-id") or "")
    if transaction:
        kept["x_transaction_id"] = _sanitize_problem(transaction, token)
    return kept


def _problem_title(response, token: str) -> str:
    record = problem_record(response, token)
    return str(record.get("title") or record.get("detail") or "")[:240]


def _scopes(headers) -> set:
    if headers is None or not hasattr(headers, "get"):
        return set()
    raw = ""
    for name in ("x-oauth-scopes", "x-accepted-oauth-scopes"):
        value = headers.get(name)
        if value:
            raw = str(value)
            break
    parts = raw.replace(",", " ").split()
    return {part.strip() for part in parts if part.strip()}


def _sanitize_problem(value, token: str, depth: int = 0):
    if depth > 4:
        return ""
    if isinstance(value, str):
        text = " ".join(value.split())[:500]
        if token and token in text:
            text = text.replace(token, "[redacted]")
        return text
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return [_sanitize_problem(item, token, depth + 1) for item in value[:10]]
    if isinstance(value, dict):
        kept = {}
        for key, item in list(value.items())[:20]:
            kept[str(key)[:80]] = _sanitize_problem(item, token, depth + 1)
        return kept
    return ""


def _problem(response, token: str) -> str:
    return _problem_title(response, token)


def _flag_on(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() == "true"


def _finish_flags(result, book, since_before, calls_before, replies_before, poll_before) -> dict:
    del replies_before, poll_before
    result["production_since_id_unchanged"] = book.get_since_id() == since_before
    result["production_model_calls_unchanged"] = book.model_calls_today() == calls_before
    result["replies_enabled"] = _flag_on("X_REPLIES_ENABLED")
    result["poll_enabled"] = _flag_on("X_POLL_ENABLED")
    return result


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


def _print_result(result: dict) -> None:
    print(f"status: {result.get('status')}")
    print(f"posted: {str(bool(result.get('posted'))).lower()}")
    if result.get("reason"):
        print(f"reason: {result['reason']}")
    if result.get("username"):
        print(f"account: @{result['username']}")
    if result.get("user_id"):
        print(f"user_id: {result['user_id']}")
    if result.get("write_evidence"):
        print(f"write_evidence: {result['write_evidence']}")
    print(f"post_id: {result.get('post_id')}")
    if result.get("draft_sha256"):
        print(f"draft_sha256: {result['draft_sha256']}")
    if result.get("x_reply_id"):
        print(f"x_reply_id: {result['x_reply_id']}")
    if result.get("created_at"):
        print(f"created_at: {result['created_at']}")
    if result.get("updated_at"):
        print(f"updated_at: {result['updated_at']}")
    if result.get("status") == "preview" and result.get("reply_text"):
        print("reply_text:")
        print(result["reply_text"])


if __name__ == "__main__":
    sys.exit(main())
