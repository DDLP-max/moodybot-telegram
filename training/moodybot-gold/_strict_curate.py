#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Second-pass Gold curator — writing quality, not poetic costume."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "training" / "moodybot-gold"
CAND = OUT / "_candidates.jsonl"
STRICT = OUT / "_strict_pool.jsonl"

COSTUME = re.compile(
    r"\b(dance|symphony|tapestry|whisper(s|ed|ing)?|echo(es|ed|ing)?|"
    r"shadows? play|battlefield|chess|roulette|circus wire|"
    r"ferrari|gangrenous|sunrise over|soul[,.]|"
    r"beautiful mess|volatile angel|my dear|"
    r"let that sink|sit with that|mic drop|"
    r"narrative of|emotional economy|emotional roulette)\b|"
    r"🌹|🔥|✨|💀|↗️",
    re.I,
)
LIKE_A = re.compile(r"\blike a\b|\bas if\b|\bas though\b", re.I)
WORD = re.compile(r"[A-Za-z']+")
SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-Z\"'“‘0-9])")

REFRAME = re.compile(
    r"\b(not .+—|not .+[,.] it'?s|you'?re (not|describing|confusing|calling|measuring)|"
    r"that'?s not|isn'?t .+[,.] it'?s|the (tell|premise|hook)|"
    r"stop (calling|pretending|asking|romanticizing)|"
    r"wrong\.|false\.|bullshit|"
    r"doesn'?t (forgive|mean|fix)|"
    r"is a transaction|is the tell|changes the courtroom)\b",
    re.I,
)
CONCRETE = re.compile(
    r"\b(money|sex|work|job|door|phone|text|bed|car|rent|bill|boss|"
    r"wife|husband|kid|kids|friend|ex|body|hand|pay|leave|stay|"
    r"wait|call|lie|cheat|trust|promise|rule|cost|price|risk|"
    r"move|boundary|room|silence|receipt|contract|attorney|"
    r"court|throne|map|path|choice|drink|snoring|odour|odor)\b",
    re.I,
)
AI_VOICE = re.compile(
    r"\b(delve|tapestry|landscape of|in today'?s|it'?s important to|"
    r"navigate|multifaceted|leverage your|unlock your|"
    r"at the end of the day|food for thought|"
    r"here'?s the (real )?kicker|ponder)\b",
    re.I,
)
THERAPY = re.compile(
    r"\b(hold space|validate|inner child|attachment style|"
    r"trauma dump|healing journey|self[- ]care|cope with|"
    r"emotional regulation|process your feelings)\b",
    re.I,
)
CTA = re.compile(
    r"(tag @|subscribe|follow me|comment below|link in bio|dm me|"
    r"hit (like|follow)|share this|join (my|the) )",
    re.I,
)


def words(t: str) -> list[str]:
    return WORD.findall(t)


def sents(t: str) -> list[str]:
    parts = [s.strip() for s in SENT.split(t) if s.strip()]
    return parts or ([t.strip()] if t.strip() else [])


def is_gold(user: str, bot: str) -> tuple[bool, float, list[str]]:
    reasons: list[str] = []
    w = words(bot)
    wc = len(w)
    ss = sents(bot)
    paras = [p for p in bot.split("\n") if p.strip()]

    if wc < 12 or wc > 160:
        return False, 0, ["length"]
    if len(paras) > 4:
        return False, 0, ["paragraphs"]
    if CTA.search(bot) or THERAPY.search(bot) or AI_VOICE.search(bot):
        return False, 0, ["banned_voice"]
    if re.search(r"\b(the truth is|what'?s really happening)\b", bot, re.I):
        return False, 0, ["banned_phrase"]
    if re.search(
        r"(incentive structure|identity architecture|pattern recognition engine|"
        r"narrative contract|epistemic)",
        bot,
        re.I,
    ):
        return False, 0, ["systems_jargon"]

    like_count = len(LIKE_A.findall(bot))
    costume_hits = len(COSTUME.findall(bot))
    if like_count >= 2 or costume_hits >= 2:
        return False, 0, ["metaphor_costume"]
    if like_count >= 1 and costume_hits >= 1:
        return False, 0, ["metaphor_costume"]

    # Must feel spoken: contractions or direct you/I
    spoken = bool(re.search(r"\b\w+'(t|s|re|ll|ve|d)\b", bot)) or (
        len(re.findall(r"\byou\b", bot, re.I)) >= 1
    )
    if not spoken and wc > 40:
        return False, 0, ["not_conversational"]

    avg_sent = wc / max(1, len(ss))
    if avg_sent > 26:
        return False, 0, ["essay_sentences"]

    has_reframe = bool(REFRAME.search(bot))
    concrete = len(CONCRETE.findall(bot))
    punch = [s for s in ss if 5 <= len(words(s)) <= 16]

    score = 7.0
    if has_reframe:
        score += 1.5
        reasons.append("reframe")
    if concrete >= 2:
        score += 0.8
        reasons.append("concrete")
    elif concrete == 0 and wc > 50:
        score -= 0.6
    if punch:
        score += 0.7
        reasons.append("memorable")
    if like_count == 0 and costume_hits == 0:
        score += 0.5
        reasons.append("no_costume")
    if wc <= 100:
        score += 0.4
        reasons.append("stopped")
    if len(paras) <= 2:
        score += 0.3
    if len(words(user)) < 5:
        score -= 1.2
    if re.search(r"\?\s*$", bot.strip()) and bot.count("?") >= 2:
        score -= 0.8  # ending engagement bait

    # Require the core gold signals
    if not has_reframe and not (concrete >= 3 and punch):
        return False, score, ["weak_insight"]

    if score < 9.0:
        return False, score, reasons + ["below_9"]

    return True, min(10.0, score), reasons


def main() -> None:
    rows = [json.loads(l) for l in CAND.read_text(encoding="utf-8").splitlines() if l]
    # Also re-scan all pairs from original log for strict filter (not only first-pass)
    from _extract_candidates import parse_log, LOG, classify_structure, category_guess, memorable_line

    pairs = parse_log(LOG)
    goldish = []
    for p in pairs:
        ok, score, reasons = is_gold(p.user, p.bot)
        if not ok:
            continue
        goldish.append(
            {
                "index": p.index,
                "ts": p.ts,
                "score": round(score, 2),
                "user": p.user,
                "bot": p.bot,
                "reasons": reasons,
                "structure": classify_structure(p.bot),
                "category": category_guess(p.user, p.bot),
                "memorable_line": memorable_line(p.bot),
            }
        )

    # Deduplicate near-identical bot responses
    seen = set()
    unique = []
    for g in sorted(goldish, key=lambda x: (-x["score"], len(x["bot"]))):
        key = re.sub(r"\s+", " ", g["bot"].lower())[:180]
        if key in seen:
            continue
        seen.add(key)
        unique.append(g)

    with STRICT.open("w", encoding="utf-8") as f:
        for g in unique:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    print(f"strict pool: {len(unique)}")
    for g in unique[:25]:
        print("---", g["score"], g["structure"], g["reasons"])
        print("U:", g["user"][:100].replace("\n", " "))
        print("B:", g["bot"][:200].replace("\n", " "))
        print("M:", g["memorable_line"][:120])


if __name__ == "__main__":
    main()
