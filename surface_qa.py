# -*- coding: utf-8 -*-
"""Surface QA — typography integrity after Gold.

Not writing. Not lens. Not Gold compression.
Catches post-processing damage before Telegram (e.g. "side. and watch").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

# Accidental sentence split before a continuation conjunction (lowercase only —
# ". That fear" is a real sentence; ". and watch" is damage.)
_BAD_BOUNDARY = re.compile(
    r"\.\s+(and|or|but|because|while|which|who|that)\b"
)


@dataclass
class SurfaceIssue:
    kind: str  # sentence_boundary | lowercase_start | orphan_conjunction
    span: str
    suggested: str = ""


@dataclass
class SurfaceQAResult:
    text: str
    fixed: bool = False
    issues: List[SurfaceIssue] = field(default_factory=list)

    @property
    def failure_names(self) -> List[str]:
        return sorted({i.kind for i in self.issues})


def detect_surface_issues(text: str) -> List[SurfaceIssue]:
    """Flag typography damage. Does not mutate."""
    body = re.sub(r"\s*🥃\s*", " ", text or "").strip()
    issues: List[SurfaceIssue] = []

    for m in _BAD_BOUNDARY.finditer(body):
        start = max(0, m.start() - 28)
        end = min(len(body), m.end() + 32)
        span = body[start:end].strip()
        suggested = _BAD_BOUNDARY.sub(lambda mm: f" {mm.group(1)}", span, count=1)
        kind = "orphan_conjunction" if m.group(1).islower() else "sentence_boundary"
        # Always sentence_boundary for ". and" pattern; orphan is the same heal
        issues.append(
            SurfaceIssue(
                kind="sentence_boundary",
                span=span,
                suggested=suggested,
            )
        )

    # Lowercase sentence starts after .!? (excluding healed conjunctions / brands)
    for m in re.finditer(r"(?<=[.!?])\s+([a-z][\w'-]*)", body):
        word = m.group(1)
        if word.lower() in {
            "and",
            "or",
            "but",
            "because",
            "while",
            "which",
            "who",
            "that",
        }:
            continue  # covered above
        if word in {"iPhone", "iPad", "iOS", "eBay", "macOS"} or word.startswith("iP"):
            continue
        start = max(0, m.start() - 20)
        end = min(len(body), m.end() + 20)
        issues.append(
            SurfaceIssue(
                kind="lowercase_start",
                span=body[start:end].strip(),
                suggested="",
            )
        )

    return issues


def repair_surface_boundaries(text: str) -> Tuple[str, bool]:
    """
    Heal accidental splits: 'side. and watch' → 'side and watch'.
    Typography only — does not invent prose.
    """
    original = text or ""
    whiskey = " 🥃" if "🥃" in original else ""
    body = re.sub(r"\s*🥃\s*", " ", original).strip()
    fixed = _BAD_BOUNDARY.sub(lambda m: f" {m.group(1)}", body)
    fixed = re.sub(r"[ \t]{2,}", " ", fixed)
    fixed = re.sub(r"\n{3,}", "\n\n", fixed).strip()
    if whiskey:
        fixed = f"{fixed}{whiskey}".strip()
        fixed = re.sub(r"([^\s])(🥃)", r"\1 \2", fixed)
    return fixed, fixed != original


def run_surface_qa(text: str, *, auto_repair: bool = True) -> SurfaceQAResult:
    """Detect issues; optionally repair bad boundaries before send."""
    issues_before = detect_surface_issues(text)
    out = text or ""
    fixed = False
    if auto_repair and any(i.kind == "sentence_boundary" for i in issues_before):
        out, fixed = repair_surface_boundaries(out)
    issues = detect_surface_issues(out)
    return SurfaceQAResult(text=out, fixed=fixed, issues=issues)
