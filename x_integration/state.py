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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


MAX_ATTEMPTS = 3

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


def ledger_from_env() -> MentionLedger:
    root = (os.environ.get("X_STATE_DIR") or "").strip()
    if not root:
        root = str(Path(__file__).resolve().parents[1] / "data" / "x")
    return MentionLedger(Path(root) / "mentions.sqlite")


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
