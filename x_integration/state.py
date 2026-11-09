# -*- coding: utf-8 -*-
"""Durable mention ledger.

One SQLite file. A repeat delivery of the same event id does not call
the model again, including after this process exits and a new one opens
the same file. Writers take an immediate lock, so concurrent deliveries
cannot share one remaining model call. On Render, X_STATE_DIR must be a
persistent disk mount; the default path does not survive an instance restart.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


MAX_ATTEMPTS = 3
LEDGER_FILENAME = "mentions.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    post_id TEXT NOT NULL DEFAULT '',
    author_id TEXT NOT NULL DEFAULT '',
    conversation_id TEXT NOT NULL DEFAULT '',
    reply_text TEXT NOT NULL DEFAULT '',
    skip_reason TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS spend (
    day TEXT PRIMARY KEY,
    model_calls INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS replied_posts (
    post_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poll_state (
    name TEXT PRIMARY KEY,
    since_id TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS probe_marker (
    name TEXT PRIMARY KEY,
    marker TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_cache (
    name TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS publications (
    post_id TEXT PRIMARY KEY,
    reply_text TEXT NOT NULL,
    x_reply_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    http_status INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Claim:
    proceed: bool
    duplicate: bool
    dead: bool
    attempts: int


class MentionLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def claim(self, event_id: str, post_id: str, author_id: str, conversation_id: str) -> Claim:
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT status, attempts FROM events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO events (
                            event_id, status, attempts, post_id, author_id,
                            conversation_id, updated_at
                        ) VALUES (?, 'pending', 1, ?, ?, ?, ?)
                        """,
                        (event_id, post_id, author_id, conversation_id, now),
                    )
                    conn.execute("COMMIT")
                    return Claim(proceed=True, duplicate=False, dead=False, attempts=1)
                status, attempts = row
                if status in {"dry_run", "posted", "skipped", "dead"}:
                    conn.execute("COMMIT")
                    return Claim(
                        proceed=False, duplicate=True, dead=status == "dead", attempts=attempts
                    )
                if attempts >= MAX_ATTEMPTS:
                    conn.execute(
                        "UPDATE events SET status = 'dead', updated_at = ? WHERE event_id = ?",
                        (now, event_id),
                    )
                    conn.execute("COMMIT")
                    return Claim(proceed=False, duplicate=False, dead=True, attempts=attempts)
                attempts += 1
                conn.execute(
                    """
                    UPDATE events
                    SET status = 'pending', attempts = ?, updated_at = ?
                    WHERE event_id = ?
                    """,
                    (attempts, now, event_id),
                )
                conn.execute("COMMIT")
                return Claim(proceed=True, duplicate=False, dead=False, attempts=attempts)
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def finish(
        self,
        event_id: str,
        *,
        status: str,
        reply_text: str = "",
        skip_reason: str = "",
        post_id: str = "",
    ) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    UPDATE events
                    SET status = ?, reply_text = ?, skip_reason = ?, updated_at = ?
                    WHERE event_id = ?
                    """,
                    (status, reply_text, skip_reason, _now(), event_id),
                )
                if status in {"dry_run", "posted"} and post_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO replied_posts (post_id, event_id) VALUES (?, ?)",
                        (post_id, event_id),
                    )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def publication(self, post_id: str) -> Optional[dict]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT post_id, reply_text, x_reply_id, status, http_status,
                           detail, created_at, updated_at
                    FROM publications WHERE post_id = ?
                    """,
                    (post_id,),
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return {
            "post_id": row[0],
            "reply_text": row[1],
            "x_reply_id": row[2],
            "status": row[3],
            "http_status": row[4],
            "detail": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    def claim_publication(self, post_id: str, reply_text: str) -> str:
        """Reserve one publish attempt. Only 'claimed' may call X.

        posted, ambiguous, and pending block another attempt. A previous
        definite failure can be claimed again by a new explicit command.
        """
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT status FROM publications WHERE post_id = ?",
                    (post_id,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO publications (
                            post_id, reply_text, x_reply_id, status, http_status,
                            detail, created_at, updated_at
                        ) VALUES (?, ?, '', 'pending', 0, '', ?, ?)
                        """,
                        (post_id, reply_text, now, now),
                    )
                    conn.execute("COMMIT")
                    return "claimed"
                status = str(row[0])
                if status == "failed":
                    conn.execute(
                        """
                        UPDATE publications
                        SET reply_text = ?, x_reply_id = '', status = 'pending',
                            http_status = 0, detail = '', updated_at = ?
                        WHERE post_id = ? AND status = 'failed'
                        """,
                        (reply_text, now, post_id),
                    )
                    conn.execute("COMMIT")
                    return "claimed"
                conn.execute("COMMIT")
                return status
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def finish_publication(
        self,
        post_id: str,
        *,
        status: str,
        x_reply_id: str = "",
        http_status: int = 0,
        detail: str = "",
    ) -> None:
        if status not in {"posted", "failed", "ambiguous"}:
            raise ValueError("publication status must be posted, failed, or ambiguous")
        now = _now()
        safe_detail = " ".join(str(detail).split())[:240]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                current = conn.execute(
                    "SELECT status FROM publications WHERE post_id = ?",
                    (post_id,),
                ).fetchone()
                if current is None or current[0] != "pending":
                    conn.execute("COMMIT")
                    return
                conn.execute(
                    """
                    UPDATE publications
                    SET status = ?, x_reply_id = ?, http_status = ?, detail = ?,
                        updated_at = ?
                    WHERE post_id = ? AND status = 'pending'
                    """,
                    (status, x_reply_id, int(http_status), safe_detail, now, post_id),
                )
                if status == "posted" and x_reply_id:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO replied_posts (post_id, event_id)
                        VALUES (?, ?)
                        """,
                        (post_id, f"publish:{post_id}"),
                    )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def already_replied(self, post_id: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT 1 FROM replied_posts WHERE post_id = ?",
                    (post_id,),
                ).fetchone()
            finally:
                conn.close()
        return row is not None

    def get_since_id(self) -> str:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT since_id FROM poll_state WHERE name = 'mentions'"
                ).fetchone()
            finally:
                conn.close()
        return str(row[0]) if row and row[0] else ""

    def remember_restart_marker(self) -> tuple[bool, str]:
        """Return whether a marker was already on disk, and the marker itself."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT marker FROM probe_marker WHERE name = 'restart'"
                ).fetchone()
                if row and row[0]:
                    conn.execute("COMMIT")
                    return True, str(row[0])
                marker = uuid.uuid4().hex[:12]
                conn.execute(
                    """
                    INSERT INTO probe_marker (name, marker, updated_at)
                    VALUES ('restart', ?, ?)
                    """,
                    (marker, _now()),
                )
                conn.execute("COMMIT")
                return False, marker
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def cached_access_token(self) -> str:
        return self._cached_oauth("access_token")

    def cached_refresh_token(self) -> str:
        return self._cached_oauth("refresh_token")

    def store_oauth_tokens(self, access_token: str, refresh_token: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO oauth_cache (name, access_token, refresh_token, updated_at)
                    VALUES ('user', ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        access_token = excluded.access_token,
                        refresh_token = excluded.refresh_token,
                        updated_at = excluded.updated_at
                    """,
                    (access_token, refresh_token, _now()),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def _cached_oauth(self, column: str) -> str:
        if column not in {"access_token", "refresh_token"}:
            return ""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    f"SELECT {column} FROM oauth_cache WHERE name = 'user'"
                ).fetchone()
            finally:
                conn.close()
        return str(row[0]) if row and row[0] else ""

    def set_since_id(self, since_id: str) -> None:
        current = self.get_since_id()
        if current and int(since_id) <= int(current):
            return
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO poll_state (name, since_id, updated_at)
                    VALUES ('mentions', ?, ?)
                    ON CONFLICT(name) DO UPDATE
                    SET since_id = excluded.since_id, updated_at = excluded.updated_at
                    """,
                    (since_id, _now()),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def model_calls_today(self) -> int:
        day = datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT model_calls FROM spend WHERE day = ?",
                    (day,),
                ).fetchone()
            finally:
                conn.close()
        return int(row[0]) if row else 0

    def reserve_model_call(self, limit: int) -> bool:
        """Count one model attempt. False when today's budget is spent."""
        day = datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT model_calls FROM spend WHERE day = ?",
                    (day,),
                ).fetchone()
                used = int(row[0]) if row else 0
                if used >= limit:
                    conn.execute("COMMIT")
                    return False
                if row is None:
                    conn.execute(
                        "INSERT INTO spend (day, model_calls) VALUES (?, 1)",
                        (day,),
                    )
                else:
                    conn.execute(
                        "UPDATE spend SET model_calls = ? WHERE day = ?",
                        (used + 1, day),
                    )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()
        return True

    def get(self, event_id: str) -> Optional[sqlite3.Row]:
        with self._lock:
            conn = self._connect()
            try:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                return row
            finally:
                conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn


def state_dir() -> tuple[Path, str]:
    """Return the ledger directory and whether X_STATE_DIR set it."""
    raw = (os.environ.get("X_STATE_DIR") or "").strip()
    if raw:
        return Path(raw), "environment"
    return Path(__file__).resolve().parents[1] / "data" / "x", "default"


def ledger_path() -> Path:
    root, _source = state_dir()
    return root / LEDGER_FILENAME


def ledger_from_env() -> MentionLedger:
    return MentionLedger(ledger_path())


def daily_model_limit() -> int:
    raw = (os.environ.get("X_DAILY_MODEL_CALL_LIMIT") or "25").strip()
    try:
        value = int(raw)
    except ValueError:
        return 25
    return value if value > 0 else 25


def replies_enabled() -> bool:
    return (os.environ.get("X_REPLIES_ENABLED") or "").strip().lower() == "true"


def bot_user_id() -> str:
    return (os.environ.get("X_BOT_USER_ID") or "").strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rollback(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        return
