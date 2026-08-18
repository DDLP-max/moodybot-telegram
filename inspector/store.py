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
    ts: Optional[str] = None,
    raw_output: str = "",
    meta: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append one evaluated response. Returns the stored event."""
    from .log_parser import fingerprint
    from .score import inspect_event

    _ensure()
    d = dict(diagnostics or {})
    fp = fingerprint(
        prompt or "",
        output or "",
        prompt_hash=str(d.get("prompt_hash") or ""),
        git_commit=str(d.get("git_commit") or ""),
    )
    # Dedupe live vs log: skip append if fingerprint already present
    existing = get_event_by_fingerprint(fp)
    if existing is not None:
        # Enrich diagnostics if the new row is richer
        if len(d) > len(existing.get("diagnostics") or {}):
            existing["diagnostics"] = {**(existing.get("diagnostics") or {}), **d}
            existing["inspection"] = inspect_event(existing)
            _rewrite_event(existing)
        return existing

    m = dict(meta or {})
    m["fingerprint"] = fp
    event: Dict[str, Any] = {
        "id": event_id or fp,
        "ts": ts or datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "source": source,
        "prompt": (prompt or "").strip(),
        "output": (output or "").strip(),
        "raw_output": (raw_output or "").strip(),
        "diagnostics": d,
        "meta": m,
    }
    event["inspection"] = inspect_event(event)
    with _events_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def write_events(events: List[Dict[str, Any]]) -> int:
    """Replace events.jsonl with a scored, deduped list. Preserves Hall of Fame."""
    from .score import inspect_event

    _ensure()
    path = _events_path()
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            e = dict(e)
            e["inspection"] = inspect_event(e)
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            n += 1
    return n


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


def load_all_events() -> List[Dict[str, Any]]:
    return load_events(limit=100_000)


def get_event(event_id: str) -> Optional[Dict[str, Any]]:
    for e in load_all_events():
        if e.get("id") == event_id:
            return e
    return None


def get_event_by_fingerprint(fp: str) -> Optional[Dict[str, Any]]:
    if not fp:
        return None
    # Recent window is enough for live/log dedupe of brand-new replies
    for e in load_events(limit=800):
        meta_fp = (e.get("meta") or {}).get("fingerprint")
        if meta_fp == fp or e.get("id") == fp:
            return e
    return None


def _rewrite_event(updated: Dict[str, Any]) -> None:
    rows = load_all_events()  # newest-first
    fp = (updated.get("meta") or {}).get("fingerprint")
    uid = updated.get("id")
    out = []
    for e in rows:
        if e.get("id") == uid or (e.get("meta") or {}).get("fingerprint") == fp:
            out.append(updated)
        else:
            out.append(e)
    chrono = sorted(out, key=lambda e: e.get("ts") or "")
    write_events(chrono)


def star_discovery(
    line: str,
    *,
    event_id: str = "",
    lens: str = "",
    discovery_type: str = "",
    note: str = "",
    stars: int = 5,
) -> Dict[str, Any]:
    """Hall of Fame — stealable sentences Matt starred (lens + type tags)."""
    _ensure()
    try:
        from discovery_craft import classify_discovery_type

        dtype = (discovery_type or "").strip() or classify_discovery_type(line, lens)
    except Exception:
        dtype = (discovery_type or "").strip() or "General"
    row = {
        "id": uuid.uuid4().hex[:10],
        "ts": datetime.now(timezone.utc).isoformat(),
        "line": (line or "").strip(),
        "event_id": event_id,
        "lens": lens,
        "discovery_type": dtype,
        "type": dtype,  # alias for templates
        "note": note,
        "stars": max(1, min(5, int(stars or 5))),
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


def import_log(
    path: str | Path,
    *,
    since: Optional[str] = None,
    merge_live: bool = True,
) -> Dict[str, int]:
    """Ingest moodybot.log / moodybot_log.txt into events.jsonl (deduped)."""
    from .log_parser import merge_events, parse_log_file

    imported = parse_log_file(path, since=since, source="moodybot.log")
    existing = load_all_events() if merge_live else []
    merged = merge_events(existing, imported)
    chrono = sorted(merged, key=lambda e: e.get("ts") or "")
    n = write_events(chrono)
    return {"imported": len(imported), "total": n, "merged_from_existing": len(existing)}


def rebuild(
    log_path: Optional[str | Path] = None,
    *,
    keep_seeds: bool = False,
) -> Dict[str, int]:
    """
    Wipe derived Inspector index and reconstruct from log (+ optional live residue).
    Preserves manually starred Hall of Fame lines.
    """
    from .log_parser import merge_events, parse_log_file

    hall_n = len(load_hall_of_fame(limit=50_000))
    prior = load_all_events()
    live = [e for e in prior if str(e.get("source") or "") in {"live", "telegram"}]
    seeds = [e for e in prior if str(e.get("source") or "").startswith("seed")] if keep_seeds else []

    log_events: List[Dict[str, Any]] = []
    candidates = []
    if log_path:
        candidates = [Path(log_path)]
    else:
        candidates = [
            ROOT / "moodybot.log",
            ROOT / "moodybot_log.txt",
        ]
    for p in candidates:
        if p and Path(p).exists():
            log_events = parse_log_file(p, source="moodybot.log")
            break

    merged = merge_events(log_events, live + seeds)
    chrono = sorted(merged, key=lambda e: e.get("ts") or "")
    n = write_events(chrono)
    return {
        "from_log": len(log_events),
        "from_live": len(live),
        "from_seed": len(seeds),
        "total": n,
        "hall_preserved": hall_n,
    }
