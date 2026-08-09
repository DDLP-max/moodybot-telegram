#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final polish: drop residual fake-profundity / manufactured closers; recompute stats."""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
GOLD = OUT / "gold.json"

DROP_IDS = {"gold-003", "gold-004", "gold-007"}  # profundity quote / bait closer / manufactured closer

WORD = re.compile(r"[A-Za-z']+")
SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-Z\"'“‘0-9])")
LIKE = re.compile(r"\blike a\b|\bas if\b|\bas though\b", re.I)
RHET_Q = re.compile(r"\?")
HUMOR = re.compile(
    r"\b(absurd|ridiculous|bullshit|fuckery|stupid|ironic|irony|"
    r"chainsawing|slot machine|loyalty program|victory lap|"
    r"pretty lighting|eat before they leave|gauntlet)\b",
    re.I,
)
CONTRADICTION = re.compile(
    r"^(no[,.]?\s|not\s|wrong|false|that'?s not|you'?re not|"
    r"you'?re describing|stop\s|power doesn'?t|not everyone|"
    r"that'?s not strategy|you already know|snoring\.|"
    r"there isn'?t|you don'?t |constantly |watching )",
    re.I,
)
AGREEMENT = re.compile(
    r"^(yes[,.]?\s|yeah[,.]?\s|yep|exactly|agreed|true[,.]?\s|"
    r"you'?re right|you'?re not wrong|absolutely)",
    re.I,
)
ADJ = {
    "beautiful", "deep", "emotional", "powerful", "profound", "raw", "real",
    "true", "authentic", "messy", "brutal", "quiet", "loud", "hard", "soft",
    "cold", "warm", "dark", "sharp", "clean", "ugly", "pretty", "lonely",
    "empty", "heavy", "fragile", "strong", "endless", "fleeting", "toxic",
    "intimate", "chaotic", "stupid", "daily", "clear", "fine",
}


def words(t: str):
    return WORD.findall(t)


def sents(t: str):
    parts = [s.strip() for s in SENT.split(t) if s and s.strip()]
    return parts or ([t.strip()] if t.strip() else [])


def syl(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups) or 1
    if word.endswith("e") and n > 1:
        n -= 1
    return n


def flesch(text: str) -> float:
    ss, w = sents(text), words(text)
    if not ss or not w:
        return 0.0
    asl = len(w) / len(ss)
    asw = sum(syl(x) for x in w) / len(w)
    return 206.835 - 1.015 * asl - 84.6 * asw


def fk_grade(text: str) -> float:
    ss, w = sents(text), words(text)
    if not ss or not w:
        return 0.0
    asl = len(w) / len(ss)
    asw = sum(syl(x) for x in w) / len(w)
    return 0.39 * asl + 11.8 * asw - 15.59


def adj_density(text: str) -> float:
    w = [x.lower() for x in words(text)]
    if not w:
        return 0.0
    n = sum(
        1
        for x in w
        if x in ADJ or (len(x) > 5 and re.search(r"(ful|ous|ive|ical|less|ish)$", x))
    )
    return n / len(w)


# Manual memorable-line overrides where auto-pick failed
ML_OVERRIDE = {
    "gold-009": "That’s fear dressed up as clever.",
    "gold-017": "That’s a very well-designed loyalty program.",
    "gold-021": "Power doesn’t forgive sins. It just changes the courtroom.",
    "gold-019": "Mouth odour and body odour are choices you make every morning.",
    "gold-012": "The spell is your comfort with delay.",
    "gold-015": "You want to be *seen* without being *touched*.",
    "gold-018": "They’d name the exact thing you’re scared they see when the room goes quiet.",
    "gold-016": "The premise assumes a clean villain.",
}

CAT_OVERRIDE = {
    "gold-001": "culture_media",
    "gold-006": "psychology_self",
    "gold-020": "money_work",
}


def main() -> None:
    rows = json.loads(GOLD.read_text(encoding="utf-8"))
    kept = [r for r in rows if r["id"] not in DROP_IDS]
    # renumber
    final = []
    for i, r in enumerate(kept, 1):
        old = r["id"]
        r = dict(r)
        r["id"] = f"gold-{i:03d}"
        if old in ML_OVERRIDE:
            r["memorable_line"] = ML_OVERRIDE[old]
        if old in CAT_OVERRIDE:
            r["category"] = CAT_OVERRIDE[old]
        # also map by content for overrides keyed to old ids after renumber — apply content heuristics
        final.append(r)

    # content-based memorable fixes
    for r in final:
        bot = r["assistant_response"]
        if "loyalty program" in bot and "transaction" in bot:
            r["memorable_line"] = "That’s a very well-designed loyalty program."
            r["category"] = "psychology_self"
        elif "changes the courtroom" in bot:
            r["memorable_line"] = "Power doesn’t forgive sins. It just changes the courtroom."
            r["category"] = "power_status"
        elif "fear dressed up as clever" in bot:
            r["memorable_line"] = "That’s fear dressed up as clever."
        elif "comfort with delay" in bot:
            r["memorable_line"] = "The spell is your comfort with delay."
        elif "seen* without being *touched" in bot or "seen* without being *touched*" in bot:
            r["memorable_line"] = "You want to be *seen* without being *touched*."
            r["category"] = "psychology_self"
        elif "clean villain" in bot:
            r["memorable_line"] = "The premise assumes a clean villain."
            r["category"] = "social_critique"
        elif "room goes quiet" in bot and "scared they see" in bot:
            r["memorable_line"] = (
                "They’d name the exact thing you’re scared they see when the room goes quiet."
            )
        elif "choices you make every morning" in bot:
            r["memorable_line"] = "Mouth odour and body odour are choices you make every morning."
        elif "explosions" in bot:
            r["category"] = "culture_media"
        elif "slot machine" in bot and "web3" in bot.lower():
            r["memorable_line"] = "You’re just treating web3 like a slot machine instead of a skill loop."
            r["category"] = "money_work"
        elif "cement ignorance" in bot:
            r["category"] = "psychology_self"

    # stats
    bots = [g["assistant_response"] for g in final]
    sent_lens, resp_lens, meta_freq, rhet, adj_d, paras, grades, flesches = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    humor = contra = agree = physical = memorable = 0
    n = len(bots)
    for b in bots:
        ss = sents(b)
        w = words(b)
        resp_lens.append(len(w))
        sent_lens.extend(len(words(s)) for s in ss)
        meta_freq.append(len(LIKE.findall(b)))
        if HUMOR.search(b):
            humor += 1
        rhet.append(len(RHET_Q.findall(b)))
        adj_d.append(adj_density(b))
        first = (ss[0] if ss else b).strip()
        if CONTRADICTION.search(first):
            contra += 1
        if AGREEMENT.search(first):
            agree += 1
        paras.append(len([p for p in b.split("\n") if p.strip()]))
        grades.append(fk_grade(b))
        flesches.append(flesch(b))
        if re.search(
            r"\b(door|hand|back|eyes?|machine|throne|courtroom|drinks?|songs?|"
            r"screens?|lightning|chainsawing|slot machine|explosion)\b",
            b,
            re.I,
        ):
            physical += 1
        if any(5 <= len(words(s)) <= 16 for s in ss):
            memorable += 1

    st = {
        "n": n,
        "source_pairs_scanned": 4909,
        "avg_sentence_length_words": round(statistics.mean(sent_lens), 2),
        "avg_response_length_words": round(statistics.mean(resp_lens), 2),
        "median_response_length_words": statistics.median(resp_lens),
        "metaphor_like_a_per_response": round(statistics.mean(meta_freq), 3),
        "pct_with_any_like_a_metaphor": round(100 * sum(1 for x in meta_freq if x) / n, 1),
        "humor_frequency_pct": round(100 * humor / n, 1),
        "avg_rhetorical_questions": round(statistics.mean(rhet), 2),
        "adjective_density": round(statistics.mean(adj_d), 4),
        "pct_beginning_with_contradiction": round(100 * contra / n, 1),
        "pct_beginning_with_agreement": round(100 * agree / n, 1),
        "avg_paragraphs": round(statistics.mean(paras), 2),
        "avg_flesch_kincaid_grade": round(statistics.mean(grades), 2),
        "avg_flesch_reading_ease": round(statistics.mean(flesches), 2),
        "pct_with_physical_image": round(100 * physical / n, 1),
        "pct_with_short_memorable_sentence": round(100 * memorable / n, 1),
        "structure_counts": dict(Counter(g["structure"] for g in final)),
        "category_counts": dict(Counter(g["category"] for g in final)),
    }

    (OUT / "gold.json").write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "gold.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in final) + "\n", encoding="utf-8"
    )
    (OUT / "stats.json").write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    print(f"final gold: {n}")
    print(json.dumps(st, indent=2))


if __name__ == "__main__":
    main()
