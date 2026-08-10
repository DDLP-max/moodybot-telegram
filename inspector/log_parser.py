# -*- coding: utf-8 -*-
"""Parse moodybot.log / moodybot_log.txt into normalized Inspector events."""

from __future__ import annotations

import ast
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Interaction log: [ts]\nUser: ...\nMoodyBot: ...
_INTERACTION_SPLIT = re.compile(r"\n(?=\[\d{4}-\d{2}-\d{2})")
_INTERACTION_HEAD = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s*\nUser:\s*(?P<user>.*?)\nMoodyBot:\s*(?P<bot>.*)\s*$",
    re.S,
)

# Structured logger lines (Render / StreamHandler)
_LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?)"
    r"(?:\s*-\s*(?:INFO|WARNING|ERROR|DEBUG)\s*-\s*|\s+)"
    r"(?P<msg>.*)$"
)
_MSG_RECEIVED = re.compile(r"^Message received:\s*(.*)$", re.S)
_SELECTED_TONE = re.compile(r"^Selected tone:\s*(\S+)")
_RESPONSE_PLAN = re.compile(
    r"Response plan:\s*strategy=(?P<strategy>\S+)\s+intent=(?P<intent>\S+)\s+"
    r"capability=(?P<capability>.+?)\s+prompt_hash=(?P<phash>\S+)"
)
_RAW_CONTENT = re.compile(r"^Raw content from API:\s*(.*)$", re.S)
_FINALIZATION_DIAG = re.compile(
    r"^(?:Finalization diagnostics:|finalization)\s+(\{.*\})\s*$"
)
_PARA_FINAL = re.compile(
    r"PARA_TRACE_FINAL\s+structure=(?P<structure>\S+)\s+budget=(?P<budget>\S+)\s+"
    r"draft=(?P<draft>\S+)\s+post_editor=(?P<post_editor>\S+)\s+"
    r"post_finalizer=(?P<post_finalizer>\S+)"
)


def fingerprint(
    prompt: str,
    output: str,
    *,
    prompt_hash: str = "",
    git_commit: str = "",
) -> str:
    h = hashlib.sha256()
    h.update((prompt or "").strip().encode("utf-8", "replace"))
    h.update(b"\0")
    h.update((output or "").strip().encode("utf-8", "replace"))
    h.update(b"\0")
    h.update((prompt_hash or "").encode("utf-8", "replace"))
    h.update(b"\0")
    h.update((git_commit or "").encode("utf-8", "replace"))
    return h.hexdigest()[:16]


def _parse_ts(raw: str) -> str:
    s = (raw or "").strip().replace(",", ".")
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s[:26], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return datetime.now(timezone.utc).isoformat()


def _safe_literal_dict(text: str) -> Dict[str, Any]:
    try:
        obj = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _normalize(
    *,
    prompt: str,
    output: str,
    ts: str,
    source: str,
    diagnostics: Optional[Dict[str, Any]] = None,
    raw_output: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    d = dict(diagnostics or {})
    # Prefer lens alias consistency
    if d.get("interpretive_lens") and not d.get("lens"):
        d["lens"] = d["interpretive_lens"]
    if d.get("lens") and not d.get("interpretive_lens"):
        d["interpretive_lens"] = d["lens"]
    fp = fingerprint(
        prompt,
        output,
        prompt_hash=str(d.get("prompt_hash") or ""),
        git_commit=str(d.get("git_commit") or ""),
    )
    m = dict(meta or {})
    m["fingerprint"] = fp
    return {
        "id": fp,
        "ts": ts,
        "channel": m.get("channel") or "telegram",
        "source": source,
        "prompt": (prompt or "").strip(),
        "output": (output or "").strip(),
        "raw_output": (raw_output or "").strip(),
        "diagnostics": d,
        "meta": m,
    }


def parse_interaction_log(text: str, *, source: str = "moodybot.log") -> List[Dict[str, Any]]:
    """Parse moodybot_log.txt style blocks."""
    text = (text or "").strip()
    if not text:
        return []
    chunks = _INTERACTION_SPLIT.split(text if text.startswith("[") else "\n" + text)
    out: List[Dict[str, Any]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        m = _INTERACTION_HEAD.match(chunk)
        if not m:
            continue
        out.append(
            _normalize(
                prompt=m.group("user"),
                output=m.group("bot"),
                ts=_parse_ts(m.group("ts")),
                source=source,
                diagnostics={},
                meta={"format": "interaction"},
            )
        )
    return out


def parse_structured_log(text: str, *, source: str = "moodybot.log") -> List[Dict[str, Any]]:
    """Group Message received → raw → Finalization diagnostics into events."""
    events: List[Dict[str, Any]] = []
    cur: Dict[str, Any] = {}
    capturing_raw = False

    def flush():
        nonlocal cur, capturing_raw
        prompt = (cur.get("prompt") or "").strip()
        output = (cur.get("output") or cur.get("raw_output") or "").strip()
        if prompt and output:
            events.append(
                _normalize(
                    prompt=prompt,
                    output=output,
                    ts=cur.get("ts") or datetime.now(timezone.utc).isoformat(),
                    source=source,
                    diagnostics=cur.get("diagnostics") or {},
                    raw_output=cur.get("raw_output") or "",
                    meta={
                        "format": "structured",
                        "selected_tone": cur.get("selected_tone") or "",
                        "intent": cur.get("intent") or "",
                        "capability": cur.get("capability") or "",
                    },
                )
            )
        cur = {}
        capturing_raw = False

    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip("\n")
        lm = _LOG_LINE.match(line)
        if lm:
            ts = _parse_ts(lm.group("ts"))
            msg = lm.group("msg")
            # A new stamped log line ends raw continuation
            if capturing_raw and not _RAW_CONTENT.match(msg):
                capturing_raw = False
        else:
            # continuation / bare line (multiline model output)
            if capturing_raw and cur is not None:
                cur["raw_output"] = (cur.get("raw_output") or "") + "\n" + line
                continue
            ts = cur.get("ts") or ""
            msg = line

        m = _MSG_RECEIVED.match(msg)
        if m:
            if cur.get("prompt") and (cur.get("output") or cur.get("diagnostics") or cur.get("raw_output")):
                flush()
            cur = {"ts": ts, "prompt": m.group(1).strip()}
            capturing_raw = False
            continue

        if not cur:
            continue

        if ts:
            cur["ts"] = ts

        tm = _SELECTED_TONE.match(msg)
        if tm:
            cur["selected_tone"] = tm.group(1)
            capturing_raw = False
            continue

        pm = _RESPONSE_PLAN.match(msg)
        if pm:
            cur["intent"] = pm.group("intent")
            cur["capability"] = pm.group("capability").strip()
            cur.setdefault("diagnostics", {})
            cur["diagnostics"]["prompt_hash"] = pm.group("phash")
            cur["diagnostics"]["primary_capability"] = pm.group("capability").strip()
            capturing_raw = False
            continue

        rm = _RAW_CONTENT.match(msg)
        if rm:
            body = rm.group(1)
            if body.endswith("..."):
                body = body[:-3].rstrip()
            cur["raw_output"] = body
            capturing_raw = True
            continue

        pf = _PARA_FINAL.match(msg)
        if pf:
            cur.setdefault("diagnostics", {})
            cur["diagnostics"].setdefault("selected_structure", pf.group("structure"))
            cur["diagnostics"].setdefault("routing_structure", pf.group("structure"))
            cur["diagnostics"].setdefault("response_budget", pf.group("budget"))
            cur["diagnostics"]["draft_paragraph_count"] = pf.group("draft")
            cur["diagnostics"]["post_editor_paragraph_count"] = pf.group("post_editor")
            cur["diagnostics"]["post_finalizer_paragraph_count"] = pf.group("post_finalizer")
            capturing_raw = False
            continue

        dm = _FINALIZATION_DIAG.match(msg)
        if dm:
            diag = _safe_literal_dict(dm.group(1))
            cur.setdefault("diagnostics", {}).update({str(k): v for k, v in diag.items()})
            if not cur.get("output") and cur.get("raw_output"):
                cur["output"] = cur["raw_output"]
            flush()
            continue

        if capturing_raw:
            cur["raw_output"] = (cur.get("raw_output") or "") + "\n" + msg

    if cur.get("prompt") and (cur.get("output") or cur.get("raw_output")):
        if not cur.get("output"):
            cur["output"] = cur.get("raw_output")
        flush()
    return events


def parse_log_text(text: str, *, source: str = "moodybot.log") -> List[Dict[str, Any]]:
    """Auto-detect interaction vs structured logger format."""
    if re.search(r"(?m)^User:\s*", text or "") and re.search(r"(?m)^MoodyBot:\s*", text or ""):
        return parse_interaction_log(text, source=source)
    return parse_structured_log(text, source=source)


def parse_log_file(
    path: str | Path,
    *,
    since: Optional[str] = None,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    p = Path(path)
    label = source or "moodybot.log"
    text = p.read_text(encoding="utf-8", errors="replace")
    events = parse_log_text(text, source=label)
    if since:
        # compare date prefix YYYY-MM-DD
        events = [e for e in events if (e.get("ts") or "")[:10] >= since[:10]]
    return events


def merge_events(
    primary: Iterable[Dict[str, Any]],
    secondary: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Dedupe by fingerprint; keep the row with richer diagnostics."""
    by_fp: Dict[str, Dict[str, Any]] = {}

    def richness(e: Dict[str, Any]) -> Tuple[int, int]:
        d = e.get("diagnostics") or {}
        return (len(d), len(e.get("output") or ""))

    for e in list(primary) + list(secondary):
        fp = (e.get("meta") or {}).get("fingerprint") or fingerprint(
            e.get("prompt") or "",
            e.get("output") or "",
            prompt_hash=str((e.get("diagnostics") or {}).get("prompt_hash") or ""),
            git_commit=str((e.get("diagnostics") or {}).get("git_commit") or ""),
        )
        (e.setdefault("meta", {}))["fingerprint"] = fp
        e["id"] = e.get("id") or fp
        prev = by_fp.get(fp)
        if prev is None or richness(e) > richness(prev):
            # preserve earlier ts if newer row lacks it
            if prev and (not e.get("ts") or e.get("ts") > prev.get("ts", "")):
                pass
            by_fp[fp] = e
        elif prev is not None:
            # merge missing diagnostic keys
            pd, nd = prev.setdefault("diagnostics", {}), e.get("diagnostics") or {}
            for k, v in nd.items():
                if k not in pd or pd[k] in ("", None, "none"):
                    pd[k] = v
    rows = list(by_fp.values())
    rows.sort(key=lambda e: e.get("ts") or "", reverse=True)
    return rows
