# -*- coding: utf-8 -*-
"""Persist inspector events + Hall of Fame discoveries as JSONL."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]


def _data_dir() -> Path:
    return Path(os.environ.get("MOODYBOT_INSPECTOR_DIR", str(ROOT / "data" / "inspector")))


def _events_path() -> Path:
    return _data_dir() / "events.jsonl"


def _hall_path() -> Path:
    return _data_dir() / "hall_of_fame.jsonl"


def _ensure() -> None:
    _data_dir().mkdir(parents=True, exist_ok=True)


def record_event(
    prompt: str,
    output: str,
    diagnostics: Optional[Dict[str, Any]] = None,
    *,
    channel: str = "telegram",
    source: str = "live",
) -> Dict[str, Any]:
    """Append one evaluated response. Returns the stored event."""
    from .score import inspect_event

    _ensure()
    event: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "ts": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "source": source,
        "prompt": (prompt or "").strip(),
        "output": (output or "").strip(),
        "diagnostics": dict(diagnostics or {}),
    }
    event["inspection"] = inspect_event(event)
    with _events_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def load_events(limit: int = 200) -> List[Dict[str, Any]]:
    _ensure()
    path = _events_path()
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:][::-1]  # newest first


def get_event(event_id: str) -> Optional[Dict[str, Any]]:
    for e in load_events(limit=5000):
        if e.get("id") == event_id:
            return e
    return None


def star_discovery(
    line: str,
    *,
    event_id: str = "",
    lens: str = "",
    note: str = "",
) -> Dict[str, Any]:
    """Hall of Fame — stealable sentences Matt starred."""
    _ensure()
    row = {
        "id": uuid.uuid4().hex[:10],
        "ts": datetime.now(timezone.utc).isoformat(),
        "line": (line or "").strip(),
        "event_id": event_id,
        "lens": lens,
        "note": note,
    }
    with _hall_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_hall_of_fame(limit: int = 200) -> List[Dict[str, Any]]:
    _ensure()
    path = _hall_path()
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:][::-1]
