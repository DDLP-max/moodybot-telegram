#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a cleaner review pool for hand curation."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "moodybot_log.txt"
OUT = ROOT / "training" / "moodybot-gold" / "_review_pool.json"

WORD = re.compile(r"[A-Za-z']+")
SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-Z\"'“‘0-9])")
LIKE = re.compile(r"\blike a\b|\bas if\b", re.I)
BANNED = re.compile(
    r"tag @|mention @|subscribe|hold space|the truth is|what.?s really happening|"
    r"incentive structure|identity architecture|pattern recognition|"
    r"delve|tapestry|my dear|beautiful mess|emotional roulette|whiskey|"
    r"🌹|🔥🔥|↗️",
    re.I,
)
REFRAME = re.compile(
    r"you.?re (not|describing|confusing|measuring|calling)|that.?s not|"
    r"isn.?t .+[,.] it.?s|the tell|doesn.?t forgive|transaction, not|"
    r"changes the courtroom|premise|stop romanticizing|wrong\.|"
    r"not everyone agrees|power doesn.?t|loyalty program|"
    r"doesn.?t mean|are choices you make",
    re.I,
)
CONCRETE = re.compile(
    r"\b(money|sex|job|door|phone|text|bed|rent|bill|boss|wife|husband|ex|"
    r"pay|leave|trust|promise|rule|cost|receipt|snoring|choice|map|throne|"
    r"court|silence|boundary|drink|lie|cheat|kids|work|car|attorney)\b",
    re.I,
)
COSTUME = re.compile(
    r"\b(shadow|echo|soul|symphony|whisper|storm|dance|mirror|ghost|flame)\b",
    re.I,
)


def main() -> None:
    text = LOG.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n(?=\[\d{4}-\d{2}-\d{2})", text)
    pairs = []
    for i, b in enumerate(blocks):
        m = re.search(r"\[([^\]]+)\].*?User:\s*(.*?)\nMoodyBot:\s*(.*)\s*$", b, re.S)
        if not m:
            continue
        ts, u, bot = m.group(1), m.group(2).strip(), m.group(3).strip()
        if BANNED.search(bot):
            continue
        w = WORD.findall(bot)
        if not (18 <= len(w) <= 140):
            continue
        paras = [p for p in bot.split("\n") if p.strip()]
        if len(paras) > 3:
            continue
        if len(LIKE.findall(bot)) >= 2:
            continue
        if not REFRAME.search(bot):
            continue
        if len(CONCRETE.findall(bot)) < 1:
            continue
        costume = len(COSTUME.findall(bot))
        if costume >= 3:
            continue
        ss = [s for s in SENT.split(bot) if s.strip()] or [bot]
        avg = len(w) / max(1, len(ss))
        if avg > 24:
            continue
        if not re.search(r"\b\w+'(t|s|re|ll|ve|d)\b|\byou\b", bot, re.I):
            continue
        # skip slash-mode prompt spam
        if u.strip().startswith("/") and len(WORD.findall(u)) < 8:
            continue
        pairs.append(
            {
                "i": i,
                "ts": ts,
                "u": u,
                "b": bot,
                "w": len(w),
                "costume": costume,
                "like": len(LIKE.findall(bot)),
            }
        )

    def sort_key(p: dict):
        year = int(p["ts"][:4])
        late = 1 if year >= 2026 or (year == 2025 and int(p["ts"][5:7]) >= 10) else 0
        return (-late, p["costume"], p["like"], p["w"])

    pairs.sort(key=sort_key)
    OUT.write_text(json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"pool {len(pairs)}")
    for p in pairs[:80]:
        print("====", p["ts"], "w", p["w"], "c", p["costume"])
        print("U:", p["u"][:160].replace("\n", " | "))
        print("B:", p["b"][:360].replace("\n", " | "))
        print()


if __name__ == "__main__":
    main()
