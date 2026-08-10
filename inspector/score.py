# -*- coding: utf-8 -*-
"""Turn diagnostics + prose into an Inspector card (heuristics, not truth)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from approach_diversity import (
    classify_opening_move,
    ending_is_reveal_speaker,
    first_sentence,
    last_substantive_sentence,
)
from gold_shape import paragraph_count


_SYSTEMS = re.compile(
    r"\b(leverage|boundary|calibration|incentive structure|framework|paradigm|"
    r"narrative contract|systemic)\b",
    re.I,
)
_DISCOVERYISH = re.compile(
    r"^(every |people don'?t |threats |peace |consistency |the mirror |"
    r"the fastest |a threat |funny how )\b|"
    r"\bis autobiographical\b|\bexport (them|fear)\b|"
    r"\bonly become immoral\b|\bwhen you'?re the one being measured\b",
    re.I,
)
# Competent analysis that summarizes the mechanism instead of landing a discovery
_MECHANISM_SUMMARY = re.compile(
    r"\bisn'?t (really )?about\b.+\bit'?s about\b|"
    r"\bthe (rule|point|issue|problem|move) isn'?t about\b|"
    r"\bwhichever side\b|"
    r"\bprotecting whichever\b|"
    r"\bfeel(?:s|ing)? exposed by\b|"
    r"\bthe other'?s standards\b|"
    r"\bit'?s about protecting\b",
    re.I,
)
_CONCRETE_SHARP = re.compile(
    r"\b(breasts?|butt|legs?|waist|wallet|bank account|gold digger|"
    r"on display|shallow|grade|measured|immoral)\b",
    re.I,
)


def _sentences(text: str) -> List[str]:
    body = re.sub(r"\s*🥃\s*", " ", text or "").strip()
    if not body:
        return []
    parts = re.split(r"(?<=[.!?])\s+", body.replace("\n\n", " ").replace("\n", " "))
    return [s.strip() for s in parts if s and s.strip()]


def _verdict_sentence(s: str, *, is_last: bool) -> Dict[str, str]:
    if _MECHANISM_SUMMARY.search(s):
        return {
            "text": s,
            "verdict": "mechanism_summary",
            "note": "explains the analysis — generic cash-out, not a discovery",
        }
    if _DISCOVERYISH.search(s) or (is_last and re.search(r"^funny how\b", s, re.I)):
        return {
            "text": s,
            "verdict": "discovery",
            "note": "stealable / memorable",
        }
    if _CONCRETE_SHARP.search(s) and len(s.split()) <= 28:
        return {
            "text": s,
            "verdict": "strong",
            "note": "concrete, spoken, sharpens the premise",
        }
    if is_last and _MECHANISM_SUMMARY.search(s):
        return {
            "text": s,
            "verdict": "mechanism_summary",
            "note": "last line summarizes instead of discovering",
        }
    return {"text": s, "verdict": "ok", "note": ""}


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).lower() in {"1", "true", "yes"}


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def inspect_event(event: Dict[str, Any]) -> Dict[str, Any]:
    d = event.get("diagnostics") or {}
    out = event.get("output") or ""
    prompt = event.get("prompt") or ""

    paras = paragraph_count(out)
    words = len(re.findall(r"[A-Za-z']+", out))
    opening = first_sentence(out)
    opening_move = classify_opening_move(out)
    ending = last_substantive_sentence(out)
    sent_rows = [
        _verdict_sentence(s, is_last=(i == len(_sentences(out)) - 1))
        for i, s in enumerate(_sentences(out))
    ]
    discovery_line = next(
        (r["text"] for r in sent_rows if r["verdict"] == "discovery"),
        opening if _DISCOVERYISH.search(opening) else "",
    )
    last_is_summary = bool(sent_rows) and sent_rows[-1]["verdict"] == "mechanism_summary"
    strong_n = sum(1 for r in sent_rows if r["verdict"] in {"strong", "discovery"})

    checks: List[Dict[str, Any]] = []

    def add(name: str, status: str, why: str = "", examples: List[str] | None = None):
        checks.append(
            {
                "name": name,
                "status": status,  # pass | fail | weak | info
                "why": why,
                "examples": examples or [],
            }
        )

    # Architecture / pipeline from diagnostics
    structure = d.get("routing_structure") or d.get("selected_structure") or d.get("preferred_structure") or ""
    lens = d.get("lens") or d.get("interpretive_lens") or ""
    budget = d.get("response_budget") or ""
    gold_rewrite = _truthy(d.get("quality_rewrite_triggered"))
    mechanisms = _int(d.get("dominant_mechanism_count"), 1)
    premise = _truthy(d.get("premise_relocated"))
    spear = _truthy(d.get("spear_detected"))
    override = _truthy(d.get("structure_override"))
    failures = [f for f in str(d.get("quality_failures") or "none").split(",") if f and f != "none"]

    if structure and not override and d.get("structure_persistence") == "routing_only":
        add("Structure persistence", "pass", f"{structure} held")
    elif override:
        add("Structure persistence", "fail", "structure_override=true")
    else:
        add("Structure persistence", "info", structure or "unknown")

    if _truthy(d.get("lens_locked")) or d.get("lens_persistence") == "routing_only":
        add("Lens persistence", "pass", lens or "locked")
    else:
        add("Lens persistence", "weak", "lens_locked missing")

    expected_paras = {
        "SNAP": (1, 1),
        "KNIFE": (1, 2),
        "Extended KNIFE": (2, 4),
        "REFLECTION": (3, 6),
    }.get(structure, (1, 6))
    if expected_paras[0] <= paras <= expected_paras[1]:
        add("Paragraphs", "pass", f"{paras} (expected {expected_paras[0]}–{expected_paras[1]})")
    else:
        add(
            "Paragraphs",
            "fail",
            f"{paras} paragraphs; {structure or 'shape'} expects {expected_paras[0]}–{expected_paras[1]}",
        )

    if mechanisms <= 1:
        add("Mechanisms", "pass", "1")
    else:
        add("Mechanisms", "fail", f"{mechanisms} competing mechanisms")

    if premise:
        add("Premise relocated", "pass")
    else:
        add("Premise relocated", "weak", "did not relocate the user's premise")

    if spear:
        add("Spear", "pass", (d.get("spear_line") or "")[:160])
    else:
        add("Spear", "weak", "no spear detected")

    if gold_rewrite:
        add("Gold", "info", "rewrite triggered")
    else:
        add("Gold", "pass", "no rewrite — generation stood alone")

    if "over_confirming" in failures or "paragraph_restatement" in failures:
        add(
            "Over-confirming",
            "fail",
            "quality_failures: " + ", ".join(failures),
        )
    else:
        add("Over-confirming", "pass")

    # Trust reader / spokenness / discovery (craft heuristics)
    if _SYSTEMS.search(out):
        hits = sorted({m.group(0).lower() for m in _SYSTEMS.finditer(out)})
        add(
            "Spokenness",
            "fail",
            "systems jargon on the surface",
            examples=[f"leak: {h}" for h in hits[:4]],
        )
    else:
        add("Spokenness", "pass", "would someone say this aloud? — no systems leaks caught")

    if last_is_summary:
        add(
            "Last line",
            "fail",
            "mechanism summary / generic cash-out — routing can be right while distinctiveness fails",
            examples=[
                "✓ Funny how preferences only become immoral when you're the one being measured.",
                f"✗ {ending[:160]}",
            ],
        )
    elif discovery_line and ending == discovery_line:
        add("Last line", "pass", "closes on a discovery", examples=[ending[:160]])
    elif discovery_line:
        add("Last line", "pass", "discovery elsewhere in the reply", examples=[discovery_line[:160]])
    else:
        add("Last line", "weak", "no discovery line — competent but forgettable", examples=[ending[:160]])

    if opening_move == "relocation" and not discovery_line:
        add(
            "Discovery",
            "weak",
            "opening explains/relocates instead of surprising",
            examples=[
                "✓ Every threat is autobiographical.",
                f"✗ {opening[:120]}",
            ],
        )
    elif discovery_line:
        add("Discovery", "pass", "stealable line present", examples=[discovery_line])
    elif strong_n >= 1 and not last_is_summary:
        add("Discovery", "weak", "strong concrete lines, but no discovery close")
    else:
        add("Discovery", "weak", "no clear discovery line detected", examples=[opening[:160]])

    if ending_is_reveal_speaker(out) and opening_move in {"relocation", "reversal"}:
        add(
            "Ending variety",
            "weak",
            "lands on 'revealing the speaker' — allowed, becoming formula",
            examples=[ending[:160]],
        )
    elif not last_is_summary:
        add("Ending variety", "pass", ending[:120])

    # Scores 0–10
    architecture = 10
    if override:
        architecture -= 3
    if not (expected_paras[0] <= paras <= expected_paras[1]):
        architecture -= 2
    if gold_rewrite:
        architecture -= 0  # not a failure
    architecture = max(0, min(10, architecture))

    lens_fidelity = 9 if lens else 5
    if _truthy(d.get("mechanism_mismatch")):
        lens_fidelity -= 3
    if "Emotional" in lens and opening_move == "relocation":
        lens_fidelity -= 0
    lens_fidelity = max(0, min(10, lens_fidelity))

    writing = 8
    if _SYSTEMS.search(out):
        writing -= 2
    if "over_confirming" in failures:
        writing -= 2
    if last_is_summary:
        writing -= 1
    if strong_n >= 1:
        writing += 1
    if words > 0 and words < 25 and structure == "Extended KNIFE":
        writing -= 1
    writing = max(0, min(10, writing))

    memorability = 6
    if discovery_line:
        memorability = 9
    elif strong_n >= 2 and not last_is_summary:
        memorability = 8
    elif opening_move in {"contradiction", "irony", "reversal", "image"}:
        memorability = 7
    elif opening_move == "relocation":
        memorability = 5
    if last_is_summary:
        memorability -= 2
    if ending_is_reveal_speaker(out) and opening_move == "relocation":
        memorability -= 1
    memorability = max(0, min(10, memorability))

    pipeline = [
        {"label": "Claim Type", "value": d.get("claim_domain") or "—", "ok": bool(d.get("claim_domain"))},
        {"label": "Lens", "value": lens or "—", "ok": bool(lens)},
        {"label": "Lens Question", "value": (d.get("lens_question") or "—")[:120], "ok": bool(d.get("lens_question"))},
        {"label": "Capability", "value": d.get("primary_capability") or "—", "ok": bool(d.get("primary_capability"))},
        {"label": "Mechanism hint", "value": d.get("mechanism_hint") or "—", "ok": True},
        {"label": "Budget", "value": (budget or "—").title(), "ok": bool(budget)},
        {"label": "Structure", "value": structure or "—", "ok": bool(structure)},
        {
            "label": "Gold",
            "value": "Rewrite" if gold_rewrite else "No rewrite",
            "ok": not gold_rewrite,
        },
    ]

    return {
        "pipeline": pipeline,
        "editor": {
            "paragraphs": paras,
            "words": words,
            "mechanisms": mechanisms,
            "opening_move": opening_move,
            "opening": opening,
            "ending": ending,
            "discovery_line": discovery_line,
            "spear_line": d.get("spear_line") or "",
            "quality_failures": failures,
            "last_is_mechanism_summary": last_is_summary,
        },
        "sentences": sent_rows,
        "checks": checks,
        "scores": {
            "architecture": architecture,
            "lens_fidelity": lens_fidelity,
            "writing": writing,
            "memorability": memorability,
        },
    }


def diff_events(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two inspections — what changed between yesterday and today."""
    ia = a.get("inspection") or inspect_event(a)
    ib = b.get("inspection") or inspect_event(b)
    ea, eb = ia.get("editor") or {}, ib.get("editor") or {}
    return {
        "opening_changed": (ea.get("opening") or "") != (eb.get("opening") or ""),
        "opening_a": ea.get("opening"),
        "opening_b": eb.get("opening"),
        "opening_move_a": ea.get("opening_move"),
        "opening_move_b": eb.get("opening_move"),
        "structure_a": (a.get("diagnostics") or {}).get("routing_structure"),
        "structure_b": (b.get("diagnostics") or {}).get("routing_structure"),
        "structure_changed": (a.get("diagnostics") or {}).get("routing_structure")
        != (b.get("diagnostics") or {}).get("routing_structure"),
        "memorability_a": (ia.get("scores") or {}).get("memorability"),
        "memorability_b": (ib.get("scores") or {}).get("memorability"),
        "gold_a": (a.get("diagnostics") or {}).get("quality_rewrite_triggered"),
        "gold_b": (b.get("diagnostics") or {}).get("quality_rewrite_triggered"),
    }


def aggregate_lens_stats(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-lens bars for the dashboard."""
    buckets: Dict[str, Dict[str, Any]] = {}
    for e in events:
        d = e.get("diagnostics") or {}
        lens = d.get("lens") or "Unknown"
        insp = e.get("inspection") or inspect_event(e)
        scores = insp.get("scores") or {}
        b = buckets.setdefault(
            lens,
            {
                "lens": lens,
                "n": 0,
                "memorability": 0.0,
                "writing": 0.0,
                "architecture": 0.0,
                "relocation": 0,
            },
        )
        b["n"] += 1
        b["memorability"] += float(scores.get("memorability") or 0)
        b["writing"] += float(scores.get("writing") or 0)
        b["architecture"] += float(scores.get("architecture") or 0)
        if (insp.get("editor") or {}).get("opening_move") == "relocation":
            b["relocation"] += 1
    out = []
    for b in buckets.values():
        n = max(1, b["n"])
        out.append(
            {
                "lens": b["lens"],
                "n": b["n"],
                "memorability": round(b["memorability"] / n, 1),
                "writing": round(b["writing"] / n, 1),
                "architecture": round(b["architecture"] / n, 1),
                "relocation_share": round(b["relocation"] / n, 2),
            }
        )
    out.sort(key=lambda x: -x["n"])
    return out
