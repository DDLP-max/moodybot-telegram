# -*- coding: utf-8 -*-
"""Dashboard / card / filter helpers — editor telemetry, not analytics vanity."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .score import inspect_event

# Teaching examples for the sentence panel
EXAMPLE_BANK: Dict[str, List[str]] = {
    "discovery": [
        "Every threat is autobiographical.",
        "Most people don't edit the relationship. They edit the ending.",
        "The cleanest exits usually require the messiest rewrites.",
        "That's like saying a prison cell is just a room.",
    ],
    "mechanism_summary": [
        "Funny how preferences only become immoral when you're the one being measured.",
        "Every threat is autobiographical.",
        "Most people don't edit the relationship. They edit the ending.",
    ],
    "strong": [
        "Men get to grade your body like it's on display.",
        "You look at his bank account and suddenly standards are offensive.",
    ],
    "spear": [
        "That's when a warning becomes a confession.",
        "Every threat is autobiographical.",
    ],
    "bridge": [
        "Keep bridges short — they carry, they don't lecture.",
    ],
    "generic": [
        "Most people don't edit the relationship. They edit the ending.",
        "The cleanest exits usually require the messiest rewrites.",
        "Nobody wants a partner who's already finished. They want a future that already comes with a warranty.",
    ],
    "ok": [],
}


def ensure_inspection(event: Dict[str, Any]) -> Dict[str, Any]:
    insp = event.get("inspection")
    if not isinstance(insp, dict) or "scores" not in insp or "sentences" not in insp:
        insp = inspect_event(event)
        event["inspection"] = insp
    # Alias for UI
    scores = insp.setdefault("scores", {})
    if "stealability" not in scores and "memorability" in scores:
        scores["stealability"] = scores["memorability"]
    elif "memorability" not in scores and "stealability" in scores:
        scores["memorability"] = scores["stealability"]
    return insp


def source_label(source: str) -> str:
    s = (source or "").lower()
    if s in {"live", "telegram"}:
        return "live telemetry"
    if s.startswith("seed"):
        return "seeded regression example"
    if "log" in s or s in {"moodybot.log", "moodybot_log.txt", "import"}:
        return "moodybot.log"
    return source or "unknown"


def _steal(insp: Dict[str, Any]) -> float:
    sc = insp.get("scores") or {}
    return float(sc.get("stealability") if sc.get("stealability") is not None else sc.get("memorability") or 0)


def _has_discovery(insp: Dict[str, Any]) -> bool:
    if any(s.get("verdict") == "discovery" for s in insp.get("sentences") or []):
        return True
    return any(c.get("name") == "Discovery" and c.get("status") == "pass" for c in insp.get("checks") or [])


def _last_line_trap(insp: Dict[str, Any]) -> bool:
    return any(c.get("name") == "Last line" and c.get("status") == "fail" for c in insp.get("checks") or [])


def _mechanism_summary(insp: Dict[str, Any]) -> bool:
    return any(s.get("verdict") == "mechanism_summary" for s in insp.get("sentences") or [])


def _mechanism_mismatch(event: Dict[str, Any], insp: Dict[str, Any]) -> bool:
    d = event.get("diagnostics") or {}
    if str(d.get("mechanism_mismatch")).lower() in {"1", "true", "yes"}:
        return True
    return any(c.get("name") == "Mechanisms" and c.get("status") == "fail" for c in insp.get("checks") or [])


def card_summary(event: Dict[str, Any]) -> Dict[str, Any]:
    """Sidebar card: color, headline tag, stealability, teaser."""
    insp = ensure_inspection(event)
    d = event.get("diagnostics") or {}
    lens = d.get("lens") or d.get("interpretive_lens") or "—"
    steal = _steal(insp)
    opening = (insp.get("editor") or {}).get("opening") or (event.get("output") or "")[:80]

    tag = "Ok"
    tone = "green"
    if _mechanism_mismatch(event, insp):
        tag, tone = "Mechanism mismatch", "red"
    elif "lens_drift" in str((event.get("diagnostics") or {}).get("quality_failures") or ""):
        tag, tone = "Lens drift", "red"
    elif any(c.get("name") == "Lens drift" and c.get("status") == "fail" for c in insp.get("checks") or []):
        tag, tone = "Lens drift", "red"
    elif any(c.get("name") == "Mode 1 ceiling" and c.get("status") == "fail" for c in insp.get("checks") or []):
        tag, tone = "Mode 1 ceiling", "yellow"
    elif "mechanism_drift" in str((event.get("diagnostics") or {}).get("quality_failures") or ""):
        tag, tone = "Mechanism drift", "yellow"
    elif _last_line_trap(insp):
        tag, tone = "Last-line trap", "yellow"
    elif _mechanism_summary(insp) and not _has_discovery(insp):
        tag, tone = "Mechanism summary", "red"
    elif _has_discovery(insp) or steal >= 8:
        tag, tone = "Discovery", "green"
        if steal >= 9:
            tag = "Discovery"
    elif steal < 6:
        tag, tone = "Forgettable", "red"
    else:
        tag, tone = "Competent", "yellow"

    stars = "⭐⭐⭐" if steal >= 9 else "⭐⭐" if steal >= 8 else "⭐" if steal >= 7 else ""
    return {
        "id": event.get("id"),
        "lens": lens,
        "tag": tag,
        "tone": tone,
        "stealability": round(steal, 1),
        "stars": stars,
        "teaser": opening[:96],
        "ts": event.get("ts") or "",
        "source": source_label(str(event.get("source") or "")),
        "source_raw": event.get("source") or "",
    }


def filter_events(
    events: List[Dict[str, Any]],
    *,
    lens: str = "",
    fail: str = "",
    tag: str = "",
    source: str = "",
    since: str = "",
    q: str = "",
) -> List[Dict[str, Any]]:
    out = []
    lens_l = lens.lower().strip()
    fail_l = fail.lower().strip()
    tag_l = tag.lower().strip()
    source_l = source.lower().strip()
    q_l = q.lower().strip()
    for e in events:
        insp = ensure_inspection(e)
        d = e.get("diagnostics") or {}
        elens = (d.get("lens") or d.get("interpretive_lens") or "").lower()
        if lens_l and lens_l not in elens:
            continue
        if since and (e.get("ts") or "")[:10] < since[:10]:
            continue
        if source_l:
            label = source_label(str(e.get("source") or "")).lower()
            raw = str(e.get("source") or "").lower()
            if source_l not in label and source_l not in raw:
                continue
        if fail_l:
            hit = False
            for c in insp.get("checks") or []:
                if fail_l in (c.get("name") or "").lower() and c.get("status") == "fail":
                    hit = True
                    break
            if fail_l in {"last-line trap", "last line", "last-line"}:
                hit = hit or _last_line_trap(insp)
            if fail_l in {"mechanism summary", "mechanism_summary"}:
                hit = hit or _mechanism_summary(insp)
            if not hit:
                continue
        if tag_l:
            card = card_summary(e)
            if tag_l not in card["tag"].lower():
                continue
        if q_l:
            blob = f"{e.get('prompt','')} {e.get('output','')}".lower()
            if q_l not in blob:
                continue
        out.append(e)
    return out


def _pool_stats(
    pool: List[Dict[str, Any]],
    hall: List[Dict[str, Any]],
) -> Dict[str, Any]:
    discoveries = last_traps = mech_sums = hof_candidates = 0
    lens_steal: Dict[str, List[float]] = defaultdict(list)
    starred_lines = {(h.get("line") or "").strip() for h in hall if h.get("line")}

    for e in pool:
        insp = ensure_inspection(e)
        d = e.get("diagnostics") or {}
        lens = d.get("lens") or d.get("interpretive_lens") or "Unknown"
        # Interaction-log rows have no lens — bucket by source era instead of "Unknown"
        if lens in {"", "Unknown", "—"}:
            lens = "Unlensed (log)"
        steal = _steal(insp)
        lens_steal[lens].append(steal)
        if _has_discovery(insp) or steal >= 8:
            discoveries += 1
        if _last_line_trap(insp):
            last_traps += 1
        if _mechanism_summary(insp):
            mech_sums += 1
        disc = (insp.get("editor") or {}).get("discovery_line") or ""
        if steal >= 8 and disc and disc not in starred_lines:
            hof_candidates += 1

    drifting = ("—", 0.0)
    improved = ("—", 0.0)
    for lens, scores in lens_steal.items():
        if lens.startswith("Unlensed"):
            continue
        if len(scores) < 2:
            continue
        avg = sum(scores) / len(scores)
        if drifting[0] == "—" or avg < drifting[1]:
            drifting = (lens, avg)
        if improved[0] == "—" or avg > improved[1]:
            improved = (lens, avg)

    steals = [_steal(ensure_inspection(e)) for e in pool] if pool else []
    return {
        "total": len(pool),
        "discoveries": discoveries,
        "last_line_traps": last_traps,
        "mechanism_summaries": mech_sums,
        "hof_candidates": hof_candidates,
        "drifting_lens": drifting[0],
        "drifting_score": round(drifting[1], 1) if drifting[0] != "—" else None,
        "improved_lens": improved[0],
        "improved_score": round(improved[1], 1) if improved[0] != "—" else None,
        "steal_mean": round(sum(steals) / len(steals), 1) if steals else 0.0,
        "hit_rate_pct": round(100.0 * discoveries / len(pool), 1) if pool else 0.0,
    }


def dashboard_stats(
    events: List[Dict[str, Any]],
    hall: List[Dict[str, Any]],
    *,
    day: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Editor board.

    Primary numbers are always the FULL corpus (moodybot_log.txt + live).
    'Today' is a secondary strip — never the only thing you see after an import.
    """
    production = [
        e
        for e in events
        if not str(e.get("source") or "").startswith("seed")
    ]
    # Seeds stay available in the sidebar/filters but don't dilute corpus rates
    corpus_pool = production if production else list(events)
    corpus = _pool_stats(corpus_pool, hall)
    # Unique stealable lines (matches Hall notebook Candidates bucket)
    corpus["hof_candidates"] = len(collect_hall_candidates(corpus_pool, hall, limit=10_000))
    corpus["hall_starred"] = len(hall)

    if not day:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_rows = [e for e in events if (e.get("ts") or "")[:10] == day]
    # If "today" is empty or only seeds, fall back to most recent production day
    if not today_rows or all(str(e.get("source") or "").startswith("seed") for e in today_rows):
        prod_days = sorted(
            {(e.get("ts") or "")[:10] for e in production if e.get("ts")},
            reverse=True,
        )
        if prod_days:
            day = prod_days[0]
            today_rows = [e for e in production if (e.get("ts") or "")[:10] == day]

    today = _pool_stats(today_rows, hall)
    ts_vals = [(e.get("ts") or "")[:10] for e in corpus_pool if e.get("ts")]
    return {
        "day": day,
        "pool_label": "Corpus",
        # Primary = full corpus (backward-compatible keys for the template)
        **corpus,
        "corpus_total": len(corpus_pool),
        "index_total": len(events),
        "hall_total": len(hall),
        "date_from": min(ts_vals) if ts_vals else "",
        "date_to": max(ts_vals) if ts_vals else "",
        "today": {"day": day, **today},
    }


def hit_rate_by_month(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Share of responses that accidentally create something worth stealing."""
    buckets: Dict[str, List[bool]] = defaultdict(list)
    for e in events:
        ts = e.get("ts") or ""
        month = ts[:7] if len(ts) >= 7 else "unknown"
        insp = ensure_inspection(e)
        hit = _has_discovery(insp) or _steal(insp) >= 8
        buckets[month].append(hit)
    rows = []
    for month in sorted(buckets.keys()):
        vals = buckets[month]
        n = len(vals)
        hits = sum(1 for v in vals if v)
        rows.append(
            {
                "month": month,
                "n": n,
                "hits": hits,
                "rate": round(100.0 * hits / n, 1) if n else 0.0,
            }
        )
    return rows[-12:]


def collect_hall_candidates(
    events: List[Dict[str, Any]],
    hall: List[Dict[str, Any]],
    *,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    Stealable lines from the corpus that aren't starred yet.
    This is the 257 — not the 3 manual stars.
    """
    from discovery_craft import classify_discovery_type

    starred = {(h.get("line") or "").strip().lower() for h in hall if h.get("line")}
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for e in events:
        if str(e.get("source") or "").startswith("seed"):
            continue
        insp = ensure_inspection(e)
        steal = _steal(insp)
        if steal < 8 and not _has_discovery(insp):
            continue
        ed = insp.get("editor") or {}
        line = (ed.get("discovery_line") or ed.get("opening") or "").strip()
        if not line:
            continue
        key = line.lower()
        if key in starred or key in seen:
            continue
        seen.add(key)
        d = e.get("diagnostics") or {}
        lens = d.get("lens") or d.get("interpretive_lens") or ""
        dtype = classify_discovery_type(line, lens)
        out.append(
            {
                "id": f"cand-{(e.get('id') or '')[:12]}",
                "ts": e.get("ts") or "",
                "line": line,
                "event_id": e.get("id") or "",
                "lens": lens,
                "discovery_type": dtype,
                "type": dtype,
                "note": "candidate — not starred yet",
                "stars": 4 if steal >= 9 else 3,
                "stealability": round(steal, 1),
                "candidate": True,
            }
        )
    out.sort(key=lambda x: (-float(x.get("stealability") or 0), x.get("ts") or ""), reverse=False)
    # sort: highest stealability first
    out.sort(key=lambda x: -float(x.get("stealability") or 0))
    return out[:limit]


def hall_notebook(hall: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Writer's notebook: candidates (auto) + starred (manual) + spears + by lens/type."""
    from discovery_craft import classify_discovery_type

    by_lens: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    spears: List[Dict[str, Any]] = []
    starred = list(hall)
    candidates = collect_hall_candidates(events, hall, limit=500)

    spear_lines = set()
    for e in events:
        d = e.get("diagnostics") or {}
        sl = (d.get("spear_line") or "").strip()
        if sl:
            spear_lines.add(sl.lower())

    def _enrich(h: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(h)
        lens = row.get("lens") or "Unlabeled"
        dtype = (
            row.get("discovery_type")
            or row.get("type")
            or classify_discovery_type(row.get("line") or "", lens)
        )
        row["discovery_type"] = dtype
        row["type"] = dtype
        return row

    for h in hall:
        row = _enrich(h)
        lens = row.get("lens") or "Unlabeled"
        by_lens[lens].append(row)
        by_type[row.get("discovery_type") or "General"].append(row)
        line = (row.get("line") or "").strip().lower()
        if line in spear_lines or (row.get("note") or "").lower().find("spear") >= 0:
            spears.append(row)

    candidates = [_enrich(c) for c in candidates]
    starred = [_enrich(h) for h in starred]

    return {
        "candidates": candidates,
        "starred": starred,
        "discoveries": starred,  # back-compat alias
        "spears": spears,
        "by_lens": dict(sorted(by_lens.items(), key=lambda kv: -len(kv[1]))),
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -len(kv[1]))),
        "counts": {
            "candidates": len(candidates),
            "starred": len(starred),
            "discoveries": len(starred),
            "spears": len(spears),
            **{k: len(v) for k, v in by_lens.items()},
            **{f"type:{k}": len(v) for k, v in by_type.items()},
        },
    }


def sentence_teach(verdict: str, text: str, note: str = "") -> Dict[str, Any]:
    v = (verdict or "ok").lower()
    why = note or {
        "discovery": "Stealable. Someone would quote this without the rest of the reply.",
        "mechanism_summary": "Restates the mechanism. Doesn't deepen it.",
        "strong": "Concrete and spoken — sharpens the premise.",
        "spear": "The line that lands the cut.",
        "generic": "Labels the mechanism — not an of-course discovery.",
        "bridge": "Carries the reader between beats. Fine if short.",
        "ok": "Functional. Not yet a discovery.",
    }.get(v, "")
    return {
        "text": text,
        "verdict": v,
        "why": why,
        "examples": EXAMPLE_BANK.get(v, [])[:3],
    }
