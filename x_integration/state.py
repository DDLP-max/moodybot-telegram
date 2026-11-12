# -*- coding: utf-8 -*-
"""Durable mention ledger.

One SQLite file. A repeat delivery of the same event id does not call
the model again, including after this process exits and a new one opens
the same file. Writers take an immediate lock, so concurrent deliveries
cannot share one remaining model call. On Render, X_STATE_DIR must be a
persistent disk mount; the default path does not survive an instance restart.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


MAX_ATTEMPTS = 3
LEDGER_FILENAME = "mentions.sqlite"
AUTOMATIC_REPLY_LIMIT = 5
AUTOMATIC_REPLY_WINDOW = timedelta(hours=24)
_TERMINAL_EVENT = frozenset({
    "dry_run",
    "posted",
    "skipped",
    "dead",
    "ambiguous",
    "failed",
})

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
    problem_json TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activation_gate (
    name TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    remaining INTEGER NOT NULL,
    stop_reason TEXT NOT NULL DEFAULT '',
    post_id TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mention_reviews (
    post_id TEXT PRIMARY KEY,
    classification TEXT NOT NULL,
    reason TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS publish_safety (
    name TEXT PRIMARY KEY,
    auth_failures INTEGER NOT NULL DEFAULT 0,
    unexpected_failures INTEGER NOT NULL DEFAULT 0,
    halt_reason TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS engagement_decisions (
    post_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL DEFAULT '',
    author_id TEXT NOT NULL DEFAULT '',
    classification TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    respond INTEGER NOT NULL DEFAULT 0,
    action TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT '',
    objective TEXT NOT NULL DEFAULT '',
    safety_flags TEXT NOT NULL DEFAULT '[]',
    context_ids TEXT NOT NULL DEFAULT '[]',
    model TEXT NOT NULL DEFAULT 'rules',
    filter_classification TEXT NOT NULL DEFAULT '',
    filter_reason TEXT NOT NULL DEFAULT '',
    text_complete INTEGER NOT NULL DEFAULT 1,
    text_source TEXT NOT NULL DEFAULT '',
    publish INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    participant_ids TEXT NOT NULL DEFAULT '[]',
    post_ids TEXT NOT NULL DEFAULT '[]',
    moodybot_reply_ids TEXT NOT NULL DEFAULT '[]',
    last_classification TEXT NOT NULL DEFAULT '',
    last_decision TEXT NOT NULL DEFAULT '',
    last_outcome TEXT NOT NULL DEFAULT '',
    last_interaction_at TEXT NOT NULL DEFAULT '',
    human_request_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation_slots (
    post_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS battle_events (
    post_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL DEFAULT '',
    inviting_account TEXT NOT NULL DEFAULT '',
    question_id TEXT NOT NULL DEFAULT '',
    response_id TEXT NOT NULL DEFAULT '',
    classification TEXT NOT NULL DEFAULT '',
    decision TEXT NOT NULL DEFAULT '',
    loop_outcome TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generation_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    reserved_usd REAL NOT NULL DEFAULT 0,
    estimated_usd REAL NOT NULL DEFAULT 0,
    confirmed_usd REAL NOT NULL DEFAULT 0,
    charged_usd REAL NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generation_notes (
    name TEXT PRIMARY KEY,
    detail TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reply_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id TEXT NOT NULL,
    reply_id TEXT NOT NULL,
    result TEXT NOT NULL,
    http_status INTEGER NOT NULL DEFAULT 0,
    checked_at TEXT NOT NULL
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
            _ensure_problem_column(conn)
            _ensure_origin_column(conn)
            _ensure_engagement_columns(conn)
            _ensure_battle_columns(conn)
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
                if status in _TERMINAL_EVENT:
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
                           detail, problem_json, created_at, updated_at
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
            "problem": _load_problem(row[6]),
            "created_at": row[7],
            "updated_at": row[8],
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
                            http_status = 0, detail = '', problem_json = '', updated_at = ?
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
        problem: Optional[dict] = None,
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
                        problem_json = ?, updated_at = ?
                    WHERE post_id = ? AND status = 'pending'
                    """,
                    (
                        status,
                        x_reply_id,
                        int(http_status),
                        safe_detail,
                        _dump_problem(problem),
                        now,
                        post_id,
                    ),
                )
                if status == "posted" and x_reply_id:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO replied_posts (post_id, event_id)
                        VALUES (?, ?)
                        """,
                        (post_id, f"publish:{post_id}"),
                    )
                    conn.execute(
                        """
                        UPDATE battle_events
                        SET response_id = ?
                        WHERE post_id = ? AND response_id = ''
                        """,
                        (x_reply_id, post_id),
                    )
                _sync_conversation_slot(conn, post_id, status, x_reply_id, now)
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def automatic_reply_allowance(self) -> dict:
        """Successful automatic replies in the rolling 24 hours.

        Manual publication rows have an empty origin and are not counted.
        Pending and ambiguous automatic rows are held so two workers cannot
        both pass a cap that only looks at finished posts.
        """
        used, inflight = self._automatic_counts()
        cap = automatic_reply_limit()
        remaining = cap - used - inflight
        if remaining < 0:
            remaining = 0
        return {
            "limit": cap,
            "used": used,
            "inflight": inflight,
            "remaining": remaining,
            "window_hours": 24,
        }

    def reserve_automatic_publication(
        self,
        post_id: str,
        reply_text: str,
        conversation_id: str = "",
        *,
        ai_author: bool = False,
        question_id: str = "",
        inviting_account: str = "",
    ) -> str:
        """Hold one automatic slot. Does not rewrite an existing row.

        A failed or ambiguous automatic row stays as it is. Only a new row
        may be claimed, and only while the rolling cap and the conversation
        cap both have room. The two checks share this transaction.
        """
        now = _now()
        conversation_id = str(conversation_id or "").strip()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT status FROM publications WHERE post_id = ?",
                    (post_id,),
                ).fetchone()
                if row is not None:
                    conn.execute("COMMIT")
                    return str(row[0])
                if not self._automatic_room(conn):
                    conn.execute("COMMIT")
                    return "cap"
                if conversation_id and not _conversation_room(conn, conversation_id):
                    conn.execute("COMMIT")
                    return "conversation_cap"
                if ai_author and _battle_blocked(conn, conversation_id, question_id):
                    conn.execute("COMMIT")
                    return "ai_loop"
                conn.execute(
                    """
                    INSERT INTO publications (
                        post_id, reply_text, x_reply_id, status, http_status,
                        detail, problem_json, created_at, updated_at, origin
                    ) VALUES (?, ?, '', 'pending', 0, '', '', ?, ?, 'automatic')
                    """,
                    (post_id, reply_text, now, now),
                )
                if conversation_id:
                    conn.execute(
                        """
                        INSERT INTO conversation_slots (
                            post_id, conversation_id, status, created_at
                        ) VALUES (?, ?, 'pending', ?)
                        """,
                        (post_id, conversation_id, now),
                    )
                if ai_author:
                    conn.execute(
                        """
                        INSERT INTO battle_events (
                            post_id, conversation_id, inviting_account, question_id,
                            response_id, classification, decision, loop_outcome,
                            model, created_at
                        ) VALUES (?, ?, ?, ?, '', 'DIRECT_CHALLENGE', 'reply', 'claimed', 'rules', ?)
                        ON CONFLICT(post_id) DO UPDATE SET
                            conversation_id = excluded.conversation_id,
                            inviting_account = excluded.inviting_account,
                            question_id = excluded.question_id,
                            decision = 'reply',
                            loop_outcome = 'claimed'
                        WHERE battle_events.response_id = ''
                        """,
                        (post_id, conversation_id, inviting_account, question_id, now),
                    )
                conn.execute("COMMIT")
                return "claimed"
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def activation_status(self) -> dict:
        """One-reply gate. A missing row is armed only while the env flag is on."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT mode, remaining, stop_reason
                    FROM activation_gate WHERE name = 'one_reply'
                    """
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            if one_reply_gate_enabled():
                return {"mode": "armed", "remaining": 1, "stop_reason": ""}
            return {"mode": "off", "remaining": 1, "stop_reason": ""}
        return {
            "mode": str(row[0] or "stopped"),
            "remaining": int(row[1]),
            "stop_reason": str(row[2] or ""),
        }

    def activation_blocks_publish(self) -> bool:
        status = self.activation_status()
        return status["mode"] == "stopped" or int(status["remaining"]) <= 0

    def claim_activation_attempt(self, post_id: str) -> str:
        """Take the single automatic POST slot. The loser gets 'exhausted'."""
        if not one_reply_gate_enabled():
            return "inactive"
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT mode, remaining FROM activation_gate WHERE name = 'one_reply'
                    """
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO activation_gate (
                            name, mode, remaining, stop_reason, post_id, updated_at
                        ) VALUES ('one_reply', 'stopped', 0, 'claimed', ?, ?)
                        """,
                        (post_id, now),
                    )
                    conn.execute("COMMIT")
                    return "claimed"
                if str(row[0]) == "stopped" or int(row[1]) != 1:
                    conn.execute("COMMIT")
                    return "exhausted"
                updated = conn.execute(
                    """
                    UPDATE activation_gate
                    SET mode = 'stopped', remaining = 0, stop_reason = 'claimed',
                        post_id = ?, updated_at = ?
                    WHERE name = 'one_reply' AND remaining = 1
                    """,
                    (post_id, now),
                )
                conn.execute("COMMIT")
                return "claimed" if updated.rowcount == 1 else "exhausted"
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def stop_activation(self, reason: str, post_id: str = "") -> None:
        """Stop the gate before a write. The first reason is kept."""
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT stop_reason FROM activation_gate WHERE name = 'one_reply'
                    """
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO activation_gate (
                            name, mode, remaining, stop_reason, post_id, updated_at
                        ) VALUES ('one_reply', 'stopped', 0, ?, ?, ?)
                        """,
                        (reason, post_id, now),
                    )
                elif not str(row[0] or ""):
                    conn.execute(
                        """
                        UPDATE activation_gate
                        SET mode = 'stopped', remaining = 0, stop_reason = ?,
                            post_id = CASE WHEN ? != '' THEN ? ELSE post_id END,
                            updated_at = ?
                        WHERE name = 'one_reply'
                        """,
                        (reason, post_id, post_id, now),
                    )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def finish_activation(self, reason: str) -> None:
        """Record the write outcome. Remaining stays at zero."""
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    UPDATE activation_gate
                    SET mode = 'stopped', stop_reason = ?, updated_at = ?
                    WHERE name = 'one_reply' AND remaining = 0 AND stop_reason = 'claimed'
                    """,
                    (reason, now),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def record_classification(self, post_id: str, classification: str, reason: str) -> None:
        """Remember why a mention was or was not eligible. Does not touch publications."""
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO mention_reviews (
                        post_id, classification, reason, updated_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(post_id) DO UPDATE SET
                        classification = excluded.classification,
                        reason = excluded.reason,
                        updated_at = excluded.updated_at
                    """,
                    (post_id, classification, reason, now),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def mention_review(self, post_id: str) -> Optional[dict]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT classification, reason FROM mention_reviews WHERE post_id = ?
                    """,
                    (post_id,),
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return {"classification": row[0], "reason": row[1]}

    def engagement_decision(self, post_id: str) -> Optional[dict]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT classification, reason, respond, action
                    FROM engagement_decisions WHERE post_id = ?
                    """,
                    (post_id,),
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return {
            "classification": row[0],
            "reason": row[1],
            "respond": bool(row[2]),
            "action": row[3],
        }

    def record_engagement(
        self,
        decision: dict,
        *,
        filter_classification: str = "",
        filter_reason: str = "",
    ) -> None:
        """Store one shadow decision. Does not touch publications or the cursor."""
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO engagement_decisions (
                        post_id, conversation_id, author_id, classification,
                        confidence, reason, respond, action, mode, objective,
                        safety_flags, context_ids, model, filter_classification,
                        filter_reason, text_complete, text_source, publish, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(post_id) DO UPDATE SET
                        classification = excluded.classification,
                        confidence = excluded.confidence,
                        reason = excluded.reason,
                        respond = excluded.respond,
                        action = excluded.action,
                        mode = excluded.mode,
                        objective = excluded.objective,
                        safety_flags = excluded.safety_flags,
                        context_ids = excluded.context_ids,
                        model = excluded.model,
                        filter_classification = excluded.filter_classification,
                        filter_reason = excluded.filter_reason,
                        text_complete = excluded.text_complete,
                        text_source = excluded.text_source,
                        publish = excluded.publish,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(decision.get("post_id") or ""),
                        str(decision.get("conversation_id") or ""),
                        str(decision.get("author_id") or ""),
                        str(decision.get("classification") or ""),
                        float(decision.get("confidence") or 0),
                        str(decision.get("reason") or ""),
                        1 if decision.get("respond") else 0,
                        str(decision.get("action") or ""),
                        str(decision.get("mode") or ""),
                        str(decision.get("objective") or ""),
                        json.dumps(decision.get("safety_flags") or []),
                        json.dumps(decision.get("context_ids") or []),
                        str(decision.get("model") or "rules"),
                        filter_classification,
                        filter_reason,
                        1 if decision.get("text_complete", True) else 0,
                        str(decision.get("text_source") or ""),
                        1 if decision.get("publish") else 0,
                        now,
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def remember_conversation(
        self,
        *,
        conversation_id: str,
        author_id: str,
        post_id: str,
        classification: str,
        action: str,
        bot_id: str = "",
        author_username: str = "",
    ) -> None:
        """Ids and decisions only. Post text stays on X."""
        if not conversation_id:
            return
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT participant_ids, post_ids, moodybot_reply_ids
                    FROM conversations WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                ).fetchone()
                people = _id_list(row[0] if row else "[]")
                posts = _id_list(row[1] if row else "[]")
                replies = _id_list(row[2] if row else "[]")
                if author_id and author_id not in people:
                    people.append(author_id)
                if bot_id and bot_id not in people:
                    people.append(bot_id)
                if post_id and post_id not in posts:
                    posts.append(post_id)
                people = people[-20:]
                posts = posts[-30:]
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO conversations (
                            conversation_id, participant_ids, post_ids,
                            moodybot_reply_ids, last_classification, last_decision,
                            last_outcome, last_interaction_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, '', ?, ?)
                        """,
                        (
                            conversation_id,
                            json.dumps(people),
                            json.dumps(posts),
                            json.dumps(replies),
                            classification,
                            action,
                            now,
                            now,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE conversations
                        SET participant_ids = ?, post_ids = ?,
                            last_classification = ?, last_decision = ?,
                            last_interaction_at = ?, updated_at = ?
                        WHERE conversation_id = ?
                        """,
                        (
                            json.dumps(people),
                            json.dumps(posts),
                            classification,
                            action,
                            now,
                            now,
                            conversation_id,
                        ),
                    )
                if _human_refresh(author_id, author_username, classification):
                    conn.execute(
                        """
                        UPDATE conversations
                        SET human_request_at = ?
                        WHERE conversation_id = ?
                        """,
                        (now, conversation_id),
                    )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def conversation_state(self, conversation_id: str) -> dict:
        cutoff = (datetime.now(timezone.utc) - AUTOMATIC_REPLY_WINDOW).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT last_interaction_at, human_request_at FROM conversations
                    WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                ).fetchone()
                used = conn.execute(
                    """
                    SELECT COUNT(*) FROM conversation_slots
                    WHERE conversation_id = ?
                      AND status IN ('pending', 'posted', 'ambiguous')
                      AND created_at >= ?
                    """,
                    (conversation_id, cutoff),
                ).fetchone()[0]
                claimed = conn.execute(
                    """
                    SELECT question_id, created_at FROM battle_events
                    WHERE conversation_id = ? AND loop_outcome = 'claimed'
                    ORDER BY created_at DESC
                    """,
                    (conversation_id,),
                ).fetchall()
            finally:
                conn.close()
        latest = str(claimed[0][1] or "") if claimed else ""
        human_at = str(row[1] or "") if row else ""
        return {
            "last_interaction_at": str(row[0] or "") if row else "",
            "bot_replies_24h": int(used),
            "ai_invitation_used": bool(claimed),
            "human_after_ai": bool(latest and human_at and human_at > latest),
            "answered_question_ids": [str(item[0]) for item in claimed if item[0]],
        }

    def record_battle(self, decision: dict, *, inviting_account: str, question_id: str) -> None:
        """One battle row. Post text stays out of the ledger. A claimed slot is not downgraded."""
        if str(decision.get("classification") or "") != "DIRECT_CHALLENGE":
            return
        post_id = str(decision.get("post_id") or "").strip()
        if not post_id:
            return
        outcome = str(decision.get("loop_outcome") or "")
        if outcome == "allowed":
            outcome = "observed"
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO battle_events (
                        post_id, conversation_id, inviting_account, question_id,
                        response_id, classification, decision, loop_outcome,
                        model, created_at
                    ) VALUES (?, ?, ?, ?, '', ?, ?, ?, ?, ?)
                    ON CONFLICT(post_id) DO UPDATE SET
                        conversation_id = excluded.conversation_id,
                        inviting_account = excluded.inviting_account,
                        question_id = excluded.question_id,
                        classification = excluded.classification,
                        decision = excluded.decision,
                        loop_outcome = excluded.loop_outcome,
                        model = excluded.model
                    WHERE battle_events.loop_outcome != 'claimed'
                    """,
                    (
                        post_id,
                        str(decision.get("conversation_id") or ""),
                        str(inviting_account or ""),
                        str(question_id or ""),
                        str(decision.get("classification") or ""),
                        str(decision.get("action") or ""),
                        outcome,
                        str(decision.get("model") or "rules"),
                        now,
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def battle_summary(self) -> dict:
        """Counts only. No post text, account names, or credentials."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT loop_outcome, response_id, model FROM battle_events"
                ).fetchall()
            finally:
                conn.close()
        return {
            "detected": len(rows),
            "claimed": sum(1 for row in rows if row[0] == "claimed"),
            "blocked": sum(1 for row in rows if row[0] == "blocked"),
            "published": sum(1 for row in rows if str(row[1] or "")),
            "model_calls": sum(1 for row in rows if str(row[2] or "") not in {"", "rules"}),
        }

    def conversation_at_cap(self, conversation_id: str) -> bool:
        if not str(conversation_id or "").strip():
            return False
        return self.conversation_state(conversation_id)["bot_replies_24h"] >= conversation_reply_limit()

    def engagement_summary(self) -> dict:
        """Counts only. No post text and no credentials."""
        buckets = {
            "DIRECT_REQUEST": "direct_requests",
            "FOLLOW_UP": "follow_ups",
            "CHALLENGE": "challenges",
            "DIRECT_CHALLENGE": "direct_challenges",
            "CONTRIBUTION": "contributions",
            "AMBIENT": "ambient",
            "SPAM": "spam",
            "UNSAFE": "unsafe",
        }
        hidden_ambient = {"empty", "not_mentioned", "own_post", "historical", "invalid_id"}
        summary = {
            "shadow": True,
            "mentions": 0,
            "direct_requests": 0,
            "follow_ups": 0,
            "challenges": 0,
            "direct_challenges": 0,
            "contributions": 0,
            "ambient": 0,
            "spam": 0,
            "unsafe": 0,
            "would_reply": 0,
            "observed": 0,
            "skipped": 0,
            "duplicates": 0,
            "model_calls": 0,
            "filter_disagreements": 0,
            "last_publish_error": {"status": "", "http_status": 0},
            "recent": [],
        }
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT classification, reason, respond, action, model,
                           filter_classification
                    FROM engagement_decisions
                    """
                ).fetchall()
                error = conn.execute(
                    """
                    SELECT status, http_status FROM publications
                    WHERE status IN ('failed', 'ambiguous')
                    ORDER BY updated_at DESC LIMIT 1
                    """
                ).fetchone()
                recent_rows = conn.execute(
                    """
                    SELECT post_id, classification, confidence, reason, action,
                           publish, text_complete, text_source, filter_classification,
                           filter_reason
                    FROM engagement_decisions
                    WHERE reason NOT IN ('historical', 'invalid_id')
                    ORDER BY updated_at DESC
                    LIMIT 10
                    """
                ).fetchall()
            finally:
                conn.close()
        for classification, reason, respond, action, model, filt in rows:
            if reason in {"historical", "invalid_id"}:
                continue
            summary["mentions"] += 1
            key = buckets.get(str(classification))
            if key and not (key == "ambient" and reason in hidden_ambient):
                summary[key] += 1
            if respond:
                summary["would_reply"] += 1
            if action == "observe":
                summary["observed"] += 1
            if action == "skip":
                summary["skipped"] += 1
            if reason == "duplicate_parent":
                summary["duplicates"] += 1
            if model not in {"", "rules"}:
                summary["model_calls"] += 1
            filter_reply = filt == "eligible"
            if bool(respond) != filter_reply:
                summary["filter_disagreements"] += 1
        if error is not None:
            summary["last_publish_error"] = {
                "status": str(error[0] or ""),
                "http_status": int(error[1] or 0),
            }
        summary["recent"] = [
            {
                "post_id": row[0],
                "classification": row[1],
                "confidence": row[2],
                "reason": row[3],
                "action": row[4],
                "publish": bool(row[5]),
                "text_complete": bool(row[6]),
                "text_source": row[7] or "",
                "filter_classification": row[8] or "",
                "filter_reason": row[9] or "",
            }
            for row in recent_rows
        ]
        return summary

    def conversation_activity(self, limit: int = 20) -> list[dict]:
        """Operator view. Not mounted on the public health route."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT d.post_id, d.conversation_id, d.classification, d.reason,
                           d.action, d.objective, d.context_ids,
                           p.status, p.x_reply_id, p.reply_text
                    FROM engagement_decisions d
                    LEFT JOIN publications p ON p.post_id = d.post_id
                    ORDER BY d.updated_at DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                ).fetchall()
            finally:
                conn.close()
        activity = []
        for row in rows:
            activity.append({
                "post_id": row[0],
                "conversation_id": row[1],
                "classification": row[2],
                "reason": row[3],
                "action": row[4],
                "objective": row[5],
                "context_ids": _id_list(row[6]),
                "publication_status": row[7] or "",
                "x_reply_id": row[8] or "",
                "reply_text": row[9] or "",
            })
        return activity

    def publish_halted(self) -> bool:
        return bool(self.publish_halt_status()["halt_reason"])

    def publish_halt_status(self) -> dict:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT auth_failures, unexpected_failures, halt_reason
                    FROM publish_safety WHERE name = 'automatic'
                    """
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return {"auth_failures": 0, "unexpected_failures": 0, "halt_reason": ""}
        return {
            "auth_failures": int(row[0]),
            "unexpected_failures": int(row[1]),
            "halt_reason": str(row[2] or ""),
        }

    def note_publish_failure(self, kind: str) -> str:
        """Count a repeated authorization or unexpected failure. Two stops publishing."""
        column = "auth_failures" if kind == "authorization" else "unexpected_failures"
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT auth_failures, unexpected_failures, halt_reason
                    FROM publish_safety WHERE name = 'automatic'
                    """
                ).fetchone()
                if row is None:
                    auth, unexpected, halted = 0, 0, ""
                    conn.execute(
                        """
                        INSERT INTO publish_safety (
                            name, auth_failures, unexpected_failures, halt_reason, updated_at
                        ) VALUES ('automatic', 0, 0, '', ?)
                        """,
                        (now,),
                    )
                else:
                    auth, unexpected, halted = int(row[0]), int(row[1]), str(row[2] or "")
                if halted:
                    conn.execute("COMMIT")
                    return halted
                if column == "auth_failures":
                    auth += 1
                    halted = "authorization" if auth >= 2 else ""
                else:
                    unexpected += 1
                    halted = "unexpected" if unexpected >= 2 else ""
                conn.execute(
                    """
                    UPDATE publish_safety
                    SET auth_failures = ?, unexpected_failures = ?, halt_reason = ?, updated_at = ?
                    WHERE name = 'automatic'
                    """,
                    (auth, unexpected, halted, now),
                )
                conn.execute("COMMIT")
                return halted
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def note_publish_success(self) -> None:
        """A posted reply clears the consecutive counters. A halt stays halted."""
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT halt_reason FROM publish_safety WHERE name = 'automatic'"
                ).fetchone()
                if row is not None and not str(row[0] or ""):
                    conn.execute(
                        """
                        UPDATE publish_safety
                        SET auth_failures = 0, unexpected_failures = 0, updated_at = ?
                        WHERE name = 'automatic'
                        """,
                        (now,),
                    )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def release_pending_event(self, event_id: str) -> None:
        """Drop an event that never reached a write, so the mention stays queued."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "DELETE FROM events WHERE event_id = ? AND status = 'pending'",
                    (event_id,),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def release_automatic_reservation(self, post_id: str) -> None:
        """Drop a slot only when no write was attempted."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    DELETE FROM publications
                    WHERE post_id = ? AND origin = 'automatic' AND status = 'pending'
                    """,
                    (post_id,),
                )
                conn.execute(
                    """
                    DELETE FROM conversation_slots
                    WHERE post_id = ? AND status = 'pending'
                    """,
                    (post_id,),
                )
                conn.execute(
                    """
                    DELETE FROM battle_events
                    WHERE post_id = ? AND response_id = '' AND loop_outcome = 'claimed'
                    """,
                    (post_id,),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def charged_usd(self) -> float:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(charged_usd), 0) FROM generation_calls"
                ).fetchone()
            finally:
                conn.close()
        return float(row[0] or 0)

    def budget_allows_call(self) -> bool:
        if operating_mode() != "live_test":
            return True
        return self.charged_usd() + openrouter_call_reserve_usd() <= openrouter_budget_usd() + 1e-9

    def generation_calls_for(self, post_id: str) -> int:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM generation_calls WHERE post_id = ?",
                    (post_id,),
                ).fetchone()
            finally:
                conn.close()
        return int(row[0] or 0)

    def note_generation_error(self, detail: str) -> None:
        text = (detail or "").strip()[:120]
        if not text:
            return
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO generation_notes (name, detail, updated_at)
                    VALUES ('last', ?, ?)
                    ON CONFLICT(name) DO UPDATE SET detail = excluded.detail, updated_at = excluded.updated_at
                    """,
                    (text, now),
                )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def reserve_generation_call(self, post_id: str) -> Optional[int]:
        """Hold a conservative cost before the provider request. None means stop."""
        reserve = openrouter_call_reserve_usd()
        budget = openrouter_budget_usd()
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                charged = float(
                    conn.execute(
                        "SELECT COALESCE(SUM(charged_usd), 0) FROM generation_calls"
                    ).fetchone()[0]
                    or 0
                )
                if charged + reserve > budget + 1e-9:
                    conn.execute("COMMIT")
                    return None
                cursor = conn.execute(
                    """
                    INSERT INTO generation_calls (
                        post_id, status, input_tokens, output_tokens,
                        reserved_usd, estimated_usd, confirmed_usd, charged_usd,
                        error, created_at, updated_at
                    ) VALUES (?, 'reserved', 0, 0, ?, 0, 0, ?, '', ?, ?)
                    """,
                    (post_id or "", reserve, reserve, now, now),
                )
                conn.execute("COMMIT")
                return int(cursor.lastrowid)
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def settle_generation_call(
        self,
        call_id: int,
        *,
        usage: Optional[dict] = None,
        error: str = "",
    ) -> None:
        """Replace the in-flight hold with provider cost, or keep the hold."""
        usage = usage if isinstance(usage, dict) else {}
        prompt = _usage_tokens(usage, "prompt_tokens", "input_tokens")
        completion = _usage_tokens(usage, "completion_tokens", "output_tokens")
        confirmed = _usage_cost(usage)
        now = _now()
        reason = (error or "").strip()[:120]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT reserved_usd FROM generation_calls WHERE id = ?",
                    (int(call_id),),
                ).fetchone()
                if row is None:
                    conn.execute("COMMIT")
                    return
                reserve = float(row[0] or 0)
                if confirmed is not None and confirmed >= 0:
                    status = "confirmed"
                    estimated = 0.0
                    confirmed_usd = confirmed
                    charged = confirmed
                elif prompt or completion:
                    estimated = (
                        prompt / 1_000_000 * openrouter_input_usd_per_million()
                        + completion / 1_000_000 * openrouter_output_usd_per_million()
                    )
                    confirmed_usd = 0.0
                    charged = estimated if estimated > reserve else reserve
                    status = "estimated"
                else:
                    estimated = 0.0
                    confirmed_usd = 0.0
                    charged = reserve
                    status = "unavailable"
                conn.execute(
                    """
                    UPDATE generation_calls
                    SET status = ?, input_tokens = ?, output_tokens = ?,
                        estimated_usd = ?, confirmed_usd = ?, charged_usd = ?,
                        error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        prompt,
                        completion,
                        estimated,
                        confirmed_usd,
                        charged,
                        reason,
                        now,
                        int(call_id),
                    ),
                )
                if reason:
                    conn.execute(
                        """
                        INSERT INTO generation_notes (name, detail, updated_at)
                        VALUES ('last', ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            detail = excluded.detail, updated_at = excluded.updated_at
                        """,
                        (reason, now),
                    )
                conn.execute("COMMIT")
            except Exception:
                _rollback(conn)
                raise
            finally:
                conn.close()

    def generation_summary(self) -> dict:
        """Public counters. No prompt text and no reply text."""
        budget = openrouter_budget_usd()
        with self._lock:
            conn = self._connect()
            try:
                calls = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN status != 'blocked' THEN 1 ELSE 0 END), 0),
                        COALESCE(SUM(input_tokens), 0),
                        COALESCE(SUM(output_tokens), 0),
                        COALESCE(SUM(estimated_usd), 0),
                        COALESCE(SUM(CASE WHEN status = 'confirmed' THEN confirmed_usd ELSE 0 END), 0),
                        COALESCE(SUM(charged_usd), 0)
                    FROM generation_calls
                    """
                ).fetchone()
                replies = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN origin = 'automatic' AND status IN ('posted', 'failed', 'ambiguous') THEN 1 ELSE 0 END), 0),
                        COALESCE(SUM(CASE WHEN origin = 'automatic' AND status = 'posted' THEN 1 ELSE 0 END), 0),
                        COALESCE(SUM(CASE WHEN origin = 'automatic' AND status = 'failed' THEN 1 ELSE 0 END), 0)
                    FROM publications
                    """
                ).fetchone()
                publish_error = conn.execute(
                    """
                    SELECT status, http_status, detail FROM publications
                    WHERE status IN ('failed', 'ambiguous')
                    ORDER BY updated_at DESC LIMIT 1
                    """
                ).fetchone()
                note = conn.execute(
                    "SELECT detail FROM generation_notes WHERE name = 'last'"
                ).fetchone()
            finally:
                conn.close()
        spent = float(calls[5] or 0)
        remaining = budget - spent
        if remaining < 0:
            remaining = 0.0
        error = {"status": "", "http_status": 0, "reason": ""}
        if publish_error is not None:
            error = {
                "status": str(publish_error[0] or ""),
                "http_status": int(publish_error[1] or 0),
                "reason": _public_reason(publish_error[2]),
            }
        return {
            "model_calls": int(calls[0] or 0),
            "input_tokens": int(calls[1] or 0),
            "output_tokens": int(calls[2] or 0),
            "estimated_usd": round(float(calls[3] or 0), 6),
            "confirmed_usd": round(float(calls[4] or 0), 6),
            "spend_usd": round(spent, 6),
            "budget_usd": round(budget, 6),
            "budget_remaining_usd": round(remaining, 6),
            "replies_attempted": int(replies[0] or 0),
            "replies_published": int(replies[1] or 0),
            "replies_failed": int(replies[2] or 0),
            "last_generation_error": str(note[0] or "") if note else "",
            "last_publish_error": error,
        }

    def outcome_summary(self) -> dict:
        """Publication counts with names that say what they count.

        No reply text and no credentials. model_generations counts recorded
        provider calls. x_poll.drafted remains a dry-run counter elsewhere.
        """
        with self._lock:
            conn = self._connect()
            try:
                generations = conn.execute(
                    """
                    SELECT COUNT(*) FROM generation_calls
                    WHERE status IN ('confirmed', 'estimated', 'unavailable')
                    """
                ).fetchone()
                failures = conn.execute(
                    """
                    SELECT COUNT(*) FROM events
                    WHERE skip_reason IN (
                        'generation_failed', 'incomplete_answer',
                        'reply_too_long', 'budget_exhausted'
                    )
                    """
                ).fetchone()
                published = conn.execute(
                    """
                    SELECT COUNT(*) FROM publications
                    WHERE origin = 'automatic' AND status = 'posted'
                    """
                ).fetchone()
                failed = conn.execute(
                    """
                    SELECT COUNT(*) FROM publications
                    WHERE origin = 'automatic' AND status = 'failed'
                    """
                ).fetchone()
                battles = conn.execute(
                    """
                    SELECT COUNT(*) FROM battle_events
                    WHERE response_id != ''
                    """
                ).fetchone()
                verified = None
                present = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'reply_verifications'"
                ).fetchone()
                if present:
                    verified = conn.execute(
                        """
                        SELECT reply_id, parent_id, result
                        FROM reply_verifications
                        ORDER BY id DESC LIMIT 1
                        """
                    ).fetchone()
            finally:
                conn.close()
        return {
            "model_generations": int(generations[0] or 0),
            "generation_failures": int(failures[0] or 0),
            "x_publications_succeeded": int(published[0] or 0),
            "x_publications_failed": int(failed[0] or 0),
            "battle_publications": int(battles[0] or 0),
            "last_verified_reply_id": str(verified[0] or "") if verified else "",
            "last_verified_parent_id": str(verified[1] or "") if verified else "",
            "last_verification_result": str(verified[2] or "") if verified else "",
        }

    def _automatic_counts(self) -> tuple[int, int]:
        cutoff = (datetime.now(timezone.utc) - AUTOMATIC_REPLY_WINDOW).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                used = conn.execute(
                    """
                    SELECT COUNT(*) FROM publications
                    WHERE origin = 'automatic' AND status = 'posted' AND created_at >= ?
                    """,
                    (cutoff,),
                ).fetchone()[0]
                inflight = conn.execute(
                    """
                    SELECT COUNT(*) FROM publications
                    WHERE origin = 'automatic' AND status IN ('pending', 'ambiguous')
                    """,
                ).fetchone()[0]
            finally:
                conn.close()
        return int(used), int(inflight)

    def _automatic_room(self, conn: sqlite3.Connection) -> bool:
        cutoff = (datetime.now(timezone.utc) - AUTOMATIC_REPLY_WINDOW).isoformat()
        used = conn.execute(
            """
            SELECT COUNT(*) FROM publications
            WHERE origin = 'automatic' AND status = 'posted' AND created_at >= ?
            """,
            (cutoff,),
        ).fetchone()[0]
        inflight = conn.execute(
            """
            SELECT COUNT(*) FROM publications
            WHERE origin = 'automatic' AND status IN ('pending', 'ambiguous')
            """,
        ).fetchone()[0]
        return int(used) + int(inflight) < automatic_reply_limit()

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


def one_reply_gate_enabled() -> bool:
    return (os.environ.get("X_ONE_REPLY_GATE") or "").strip().lower() == "true"


def operating_mode() -> str:
    """disabled, one_reply_test, limited_beta, or live_test. Anything else is disabled."""
    raw = (os.environ.get("X_OPERATING_MODE") or "").strip().lower()
    if raw in {"disabled", "one_reply_test", "limited_beta", "live_test"}:
        return raw
    return "disabled"


def automatic_reply_limit() -> int:
    """LIVE_TEST uses a configurable 24-hour cap. Other modes stay at five."""
    if operating_mode() != "live_test":
        return AUTOMATIC_REPLY_LIMIT
    raw = (os.environ.get("X_LIVE_TEST_REPLY_LIMIT") or "100").strip()
    try:
        value = int(raw)
    except ValueError:
        return 100
    return value if value > 0 else 100


def _positive_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def openrouter_budget_usd() -> float:
    return _positive_float("X_OPENROUTER_BUDGET_USD", 10.0)


def openrouter_call_reserve_usd() -> float:
    """Held before a call. Replaced by provider cost when OpenRouter returns it."""
    return _positive_float("X_OPENROUTER_CALL_RESERVE_USD", 0.20)


def openrouter_input_usd_per_million() -> float:
    """High-context Grok 4.3 rate. Used only when the provider omits cost."""
    return _positive_float("X_OPENROUTER_INPUT_USD_PER_MILLION", 2.50)


def openrouter_output_usd_per_million() -> float:
    return _positive_float("X_OPENROUTER_OUTPUT_USD_PER_MILLION", 5.0)


def _usage_tokens(usage: dict, *names: str) -> int:
    for name in names:
        raw = usage.get(name)
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 0


def _usage_cost(usage: dict) -> Optional[float]:
    if "cost" not in usage or usage.get("cost") is None:
        return None
    try:
        return float(usage["cost"])
    except (TypeError, ValueError):
        return None


def _public_reason(detail: object) -> str:
    text = str(detail or "").strip().replace("\n", " ")
    lowered = text.lower()
    if "bearer" in lowered or "sk-" in lowered or "api_key" in lowered or "api-key" in lowered:
        return "redacted"
    return text[:120]


def conversation_reply_limit() -> int:
    raw = (os.environ.get("X_CONVERSATION_REPLY_LIMIT") or "3").strip()
    try:
        value = int(raw)
    except ValueError:
        return 3
    return value if 1 <= value <= 20 else 3


def bot_user_id() -> str:
    return (os.environ.get("X_BOT_USER_ID") or "").strip()


def _ensure_problem_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(publications)").fetchall()
    if rows and "problem_json" not in {row[1] for row in rows}:
        conn.execute(
            "ALTER TABLE publications ADD COLUMN problem_json TEXT NOT NULL DEFAULT ''"
        )


def _ensure_engagement_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(engagement_decisions)").fetchall()
    if not rows:
        return
    names = {row[1] for row in rows}
    for name, ddl in (
        ("text_complete", "ALTER TABLE engagement_decisions ADD COLUMN text_complete INTEGER NOT NULL DEFAULT 1"),
        ("text_source", "ALTER TABLE engagement_decisions ADD COLUMN text_source TEXT NOT NULL DEFAULT ''"),
        ("publish", "ALTER TABLE engagement_decisions ADD COLUMN publish INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in names:
            conn.execute(ddl)


def _ensure_battle_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(conversations)").fetchall()
    if rows and "human_request_at" not in {row[1] for row in rows}:
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN human_request_at TEXT NOT NULL DEFAULT ''"
        )


def _battle_blocked(conn: sqlite3.Connection, conversation_id: str, question_id: str) -> bool:
    """A second AI invitation needs a newer human request. The same question stays closed."""
    if not str(conversation_id or "").strip():
        return True
    if question_id:
        same = conn.execute(
            """
            SELECT 1 FROM battle_events
            WHERE conversation_id = ? AND question_id = ? AND loop_outcome = 'claimed'
            """,
            (conversation_id, question_id),
        ).fetchone()
        if same is not None:
            return True
    latest = conn.execute(
        """
        SELECT created_at FROM battle_events
        WHERE conversation_id = ? AND loop_outcome = 'claimed'
        ORDER BY created_at DESC LIMIT 1
        """,
        (conversation_id,),
    ).fetchone()
    if latest is None:
        return False
    human = conn.execute(
        "SELECT human_request_at FROM conversations WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()
    human_at = str(human[0] or "") if human else ""
    if human_at and human_at > str(latest[0] or ""):
        return False
    return True


def _human_refresh(author_id: str, username: str, classification: str) -> bool:
    if classification not in {"DIRECT_REQUEST", "FOLLOW_UP", "CHALLENGE", "DIRECT_CHALLENGE"}:
        return False
    from x_integration.battle import author_is_ai

    if author_is_ai(author_id, username) or str(username or "").lower().endswith("bot"):
        return False
    return True


def _ensure_origin_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(publications)").fetchall()
    if rows and "origin" not in {row[1] for row in rows}:
        conn.execute(
            "ALTER TABLE publications ADD COLUMN origin TEXT NOT NULL DEFAULT ''"
        )


def _dump_problem(problem: Optional[dict]) -> str:
    if not problem:
        return ""
    return json.dumps(problem, ensure_ascii=False, separators=(",", ":"))


def _load_problem(raw: str) -> dict:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _conversation_room(conn: sqlite3.Connection, conversation_id: str) -> bool:
    cutoff = (datetime.now(timezone.utc) - AUTOMATIC_REPLY_WINDOW).isoformat()
    used = conn.execute(
        """
        SELECT COUNT(*) FROM conversation_slots
        WHERE conversation_id = ?
          AND status IN ('pending', 'posted', 'ambiguous')
          AND created_at >= ?
        """,
        (conversation_id, cutoff),
    ).fetchone()[0]
    return int(used) < conversation_reply_limit()


def _sync_conversation_slot(
    conn: sqlite3.Connection,
    post_id: str,
    status: str,
    x_reply_id: str,
    now: str,
) -> None:
    """Follow a pending publication. A failed write releases the conversation slot."""
    if status in {"posted", "ambiguous"}:
        conn.execute(
            """
            UPDATE conversation_slots
            SET status = ?
            WHERE post_id = ? AND status = 'pending'
            """,
            (status, post_id),
        )
        if status == "posted" and x_reply_id:
            row = conn.execute(
                """
                SELECT conversation_id FROM conversation_slots WHERE post_id = ?
                """,
                (post_id,),
            ).fetchone()
            if row is not None:
                current = conn.execute(
                    """
                    SELECT moodybot_reply_ids FROM conversations WHERE conversation_id = ?
                    """,
                    (row[0],),
                ).fetchone()
                if current is not None:
                    replies = _id_list(current[0])
                    replies.append(x_reply_id)
                    conn.execute(
                        """
                        UPDATE conversations
                        SET moodybot_reply_ids = ?, last_outcome = 'posted', updated_at = ?
                        WHERE conversation_id = ?
                        """,
                        (json.dumps(replies[-20:]), now, row[0]),
                    )
        return
    if status == "failed":
        conn.execute(
            "DELETE FROM conversation_slots WHERE post_id = ? AND status = 'pending'",
            (post_id,),
        )


def _id_list(raw: str) -> list[str]:
    try:
        loaded = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    seen = []
    for item in loaded:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rollback(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        return
