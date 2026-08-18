# -*- coding: utf-8 -*-
"""Canonical suite — identity regression floor (not Hall of Fame).

Hall of Fame = growing training signal (thousands of starred sentences).
Canonical     = small hand-picked set (≈30–50). Never regress.

Regression protection is asymmetric:
  Most teams protect against bugs.
  Moody also protects against losing great writing.

Not identical wording — quality floor.
If Moody couldn't write these anymore, something fundamental has broken.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Hand-picked. Grow slowly. Prefer identity over volume.
CANONICAL: List[Dict[str, Any]] = [
    {
        "id": "foreplay",
        "label": "Foreplay",
        "lens": "Pattern Recognition",
        "discovery_type": "Language",
        "prompt": (
            "'Foreplay' is a misleading term that makes women's pleasure sound optional "
            "while treating men's pleasure mandatory."
        ),
        "reference": (
            'The word "foreplay" already decided the hierarchy. It calls everything before '
            "penetration the opening act, which only works if penetration is the main event. "
            "The term didn't describe desire. It ranked it. 🥃"
        ),
        "must_contain": ["hierarchy", "ranked"],
        "expected_lens": "Pattern Recognition",
        "min_stealability": 8,
        "require_discovery": True,
    },
    {
        "id": "prison",
        "label": "Prison",
        "lens": "Bourdain",
        "discovery_type": "Craft",
        "prompt": "McDonald's is easily the best place for burgers and fries.",
        "reference": "That's like saying a prison cell is just a room. 🥃",
        "must_contain": ["prison cell"],
        "expected_lens": "Bourdain",
        "min_stealability": 8,
        "require_discovery": True,
    },
    {
        "id": "mcdonalds-safest",
        "label": "McDonald's",
        "lens": "Bourdain",
        "discovery_type": "Craft",
        "prompt": "McDonald's is easily the best place for burgers and fries.",
        "reference": (
            "McDonald's doesn't make the best burger. It makes the safest one. 🥃"
        ),
        "must_contain": ["safest"],
        "expected_lens": "Bourdain",
        "min_stealability": 7,
        "require_discovery": False,  # short craft line; floor via must_contain + no drift
        "note": "Alternate Bourdain taste floor — either Prison or Safest may be preferred.",
    },
    {
        "id": "breaking-bad",
        "label": "Breaking Bad",
        "lens": "Bourdain",
        "discovery_type": "Craft",
        "prompt": "no show will ever compare to breaking bad and better call saul... ever.",
        "reference": (
            "Breaking Bad didn't ruin television. It raised the price of impressing you. 🥃"
        ),
        "must_contain": ["raised the price", "television"],
        "expected_lens": "Bourdain",
        "min_stealability": 8,
        "require_discovery": True,
        "forbid_subject_open": True,
    },
    {
        "id": "threat-autobiographical",
        "label": "Cat Lady",
        "lens": "Emotional Intelligence",
        "discovery_type": "Projection",
        "prompt": (
            "If you keep acting like that you'll end up a cat lady. "
            "You'll die alone with your cats."
        ),
        "reference": (
            "Every threat is autobiographical. "
            "People don't invent fears. They export them. 🥃"
        ),
        "must_contain": ["autobiographical"],
        "expected_lens": "Emotional Intelligence",
        "min_stealability": 8,
        "require_discovery": True,
    },
    {
        "id": "different-things",
        "label": "Different Things",
        "lens": "Emotional Intelligence",
        "discovery_type": "Exit",
        "prompt": (
            "We want different things. She wanted forever. I wanted space. "
            "She wanted an exit that didn't make her the bad guy."
        ),
        "reference": (
            "Most people don't edit the relationship. They edit the ending. 🥃"
        ),
        "must_contain": ["edit the ending"],
        "expected_lens": "Emotional Intelligence",
        "min_stealability": 8,
        "require_discovery": True,
    },
]


def check_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Quality-floor check for one canonical reference (not live regeneration)."""
    from inspector.score import inspect_event
    from response_finalization import build_response_plan

    failures: List[str] = []
    prompt = entry["prompt"]
    reference = entry["reference"]
    eid = entry["id"]

    for needle in entry.get("must_contain") or []:
        if needle.lower() not in reference.lower():
            failures.append(f"missing must_contain: {needle!r}")

    plan = build_response_plan(prompt)
    expected = entry.get("expected_lens") or entry.get("lens")
    # Hard routing floor only where lens ownership is identity-critical (object-first taste).
    # Elsewhere Canonical protects the *writing floor*, not exact router labels.
    if expected == "Bourdain" and plan.lens != "Bourdain":
        failures.append(f"routing lens={plan.lens!r} expected=Bourdain (taste/object-first)")
    elif entry.get("require_routing") and expected and plan.lens != expected:
        failures.append(f"routing lens={plan.lens!r} expected={expected!r}")
    if entry.get("forbid_subject_open"):
        from discovery_craft import early_noun_report

        early = early_noun_report(
            prompt, reference, claim_domain=plan.claim_domain, lens=expected or plan.lens
        )
        if not early.get("ok"):
            failures.append(f"early nouns: {early.get('why') or 'Object→Subject'}")

    event = {
        "prompt": prompt,
        "output": reference,
        "diagnostics": {
            "claim_domain": plan.claim_domain,
            "lens": expected or plan.lens,
            "interpretive_lens": expected or plan.lens,
            "routing_structure": plan.routed_structure or plan.preferred_structure or "SNAP",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "dominant_mechanism_count": "1",
            "premise_relocated": "true",
            "quality_failures": "none",
        },
    }
    insp = inspect_event(event)
    steal = float((insp.get("scores") or {}).get("stealability") or 0)
    min_s = float(entry.get("min_stealability") or 8)
    if steal < min_s:
        failures.append(f"stealability {steal} < floor {min_s}")

    if entry.get("require_discovery"):
        disc = (insp.get("editor") or {}).get("discovery_line") or ""
        has = bool(disc) or any(
            (r.get("verdict") == "discovery") for r in (insp.get("sentences") or [])
        )
        if not has:
            failures.append("no discovery line detected on reference")

    # Canonical references must never fail their own lens-drift / Mode-1-ceiling checks
    for c in insp.get("checks") or []:
        if c.get("name") in {"Lens drift", "Early nouns"} and c.get("status") == "fail":
            failures.append(f"check fail: {c.get('name')} — {c.get('why', '')[:80]}")

    return {
        "id": eid,
        "label": entry.get("label") or eid,
        "lens": entry.get("lens"),
        "discovery_type": entry.get("discovery_type"),
        "ok": not failures,
        "failures": failures,
        "stealability": steal,
        "routed_lens": plan.lens,
    }


def run_canonical_suite(
    *,
    only: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the full Canonical Suite. Returns summary + per-entry results."""
    selected = CANONICAL
    if only:
        want = {x.lower() for x in only}
        selected = [
            e
            for e in CANONICAL
            if e["id"].lower() in want or (e.get("label") or "").lower() in want
        ]
    results = [check_entry(e) for e in selected]
    passed = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(failed),
        "ok": len(failed) == 0,
        "results": results,
    }


def format_suite_report(summary: Dict[str, Any]) -> str:
    lines = [
        "Canonical Suite",
        "===============",
        f"{'PASS' if summary['ok'] else 'FAIL'}  "
        f"{summary['passed']}/{summary['total']} quality floor held",
        "",
    ]
    for r in summary.get("results") or []:
        mark = "✓" if r["ok"] else "✗"
        lines.append(
            f"{mark} {r['label']:<16}  lens={r.get('lens')}  "
            f"type={r.get('discovery_type')}  steal={r.get('stealability')}"
        )
        for f in r.get("failures") or []:
            lines.append(f"    · {f}")
    lines.append("")
    lines.append(
        "Hall of Fame = growing training signal.  "
        "Canonical = small identity regression suite."
    )
    return "\n".join(lines)
