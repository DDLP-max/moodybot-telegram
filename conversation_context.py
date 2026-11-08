# -*- coding: utf-8 -*-
"""Recent turns for one chat.

This is the conversation MoodyBot is already in. It is not a user profile,
not a summary, and not another product's memory.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterable, List, Optional

MAX_MESSAGES = 8
MAX_TURN_CHARS = 800
MAX_TOTAL_CHARS = 4000

CONTINUATION_NOTE = (
    "ONGOING CONVERSATION: the turns below already happened. "
    "The latest message decides what this reply is about. "
    "Keep the people and works already named when they are still the subject. "
    "An opinion from an earlier turn is not the thesis of this one. "
    "Answer as someone who is already in the conversation. "
    "Do not restart, do not recap the transcript, "
    "and do not turn a familiar name into a lecture."
)


def bound_turns(turns: Optional[Iterable[dict]]) -> List[dict]:
    """Keep the newest user/assistant turns inside a small budget."""
    kept: List[dict] = []
    for turn in turns or []:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = turn.get("content")
        if not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        kept.append({"role": role, "content": content[:MAX_TURN_CHARS]})
    kept = kept[-MAX_MESSAGES:]
    while kept and sum(len(item["content"]) for item in kept) > MAX_TOTAL_CHARS:
        kept.pop(0)
    return kept


class ConversationLog:
    """One JSON file per chat. Lost only if that file is deleted."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._lock = threading.Lock()

    def recent(self, chat_id) -> List[dict]:
        if chat_id is None:
            return []
        with self._lock:
            return bound_turns(self._read(chat_id))

    def append_exchange(self, chat_id, user_text: str, assistant_text: str) -> None:
        if chat_id is None:
            return
        user = (user_text or "").strip()
        assistant = (assistant_text or "").strip()
        if not user or not assistant:
            return
        with self._lock:
            turns = self._read(chat_id)
            turns.append({"role": "user", "content": user})
            turns.append({"role": "assistant", "content": assistant})
            self._write(chat_id, bound_turns(turns))

    def _path(self, chat_id) -> Path:
        safe = "".join(ch for ch in str(chat_id) if ch.isalnum() or ch in {"-", "_"})
        return self.root / f"{safe or 'unknown'}.json"

    def _read(self, chat_id) -> List[dict]:
        path = self._path(chat_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        turns = data.get("turns") if isinstance(data, dict) else None
        return list(turns) if isinstance(turns, list) else []

    def _write(self, chat_id, turns: List[dict]) -> None:
        path = self._path(chat_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"turns": turns}, ensure_ascii=False)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)


conversation_log = ConversationLog(
    Path(__file__).resolve().parent / "data" / "conversations"
)
