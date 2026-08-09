#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Finalize MoodyBot Gold corpus from moodybot_log.txt.

Gold = writing quality 9/10+, NOT agreement with the user.
Method: parse all pairs → hard reject → human-criteria filters → curated set.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "moodybot_log.txt"
OUT = ROOT / "training" / "moodybot-gold"

WORD = re.compile(r"[A-Za-z']+")
SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-Z\"'“‘0-9])")
LIKE = re.compile(r"\blike a\b|\bas if\b|\bas though\b", re.I)
RHET_Q = re.compile(r"\?")
HUMOR = re.compile(
    r"\b(lol|lmao|joke|funny|absurd|ridiculous|bullshit|fuckery|stupid|"
    r"dumb|comedy|ironic|irony|chainsawing|slot machine|loyalty program|"
    r"victory lap|pretty lighting|eat before they leave)\b",
    re.I,
)
CONTRADICTION = re.compile(
    r"^(no[,.]?\s|not\s|wrong|false|that'?s not|you'?re not|"
    r"you'?re describing|stop\s|don'?t\s|never\s|nobody|"
    r"power doesn'?t|not everyone|that'?s not strategy|"
    r"you already know|snoring\.)",
    re.I,
)
AGREEMENT = re.compile(
    r"^(yes[,.]?\s|yeah[,.]?\s|yep|exactly|agreed|true[,.]?\s|"
    r"you'?re right|fair[,.]?\s|absolutely|spot on|correct)",
    re.I,
)
ADJ = {
    "beautiful", "deep", "emotional", "powerful", "profound", "raw", "real",
    "true", "authentic", "messy", "brutal", "quiet", "loud", "hard", "soft",
    "cold", "warm", "dark", "sharp", "clean", "ugly", "pretty", "lonely",
    "empty", "heavy", "fragile", "strong", "endless", "fleeting", "toxic",
    "intimate", "chaotic", "stupid", "daily", "clear",
}

# Signature memorable openings / unique fingerprints of known gold replies
# (used to recover excellent responses that filters might miss)
MUST_INCLUDE_SNIPPETS = [
    "You're describing a transaction, not a superpower",
    "Power doesn’t forgive sins. It just changes the courtroom",
    "Power doesn't forgive sins. It just changes the courtroom",
    "That’s not strategy. That’s fear dressed up as clever",
    "That's not strategy. That's fear dressed up as clever",
    "Snoring. Mouth odour and body odour are choices",
    "You want to be *seen* without being *touched*",
    "Not everyone agrees feminism destroyed society",
    "Pick the one where you can’t bullshit yourself",
    "Pick the one where you can't bullshit yourself",
    "You’re stuck because you keep choosing the version",
    "You're stuck because you keep choosing the version",
    "They’d name the exact thing you’re scared they see",
    "They'd name the exact thing you're scared they see",
    "tax on trust you loaned out too easy",
    "The ache isn't in the silence—it's in the expectation",
    "Anger just unlocked the door",
    "midwives don't get to absolve themselves",
    "treating web3 like a slot machine instead of a skill loop",
    "The premise assumes a clean villain",
    "the throne never stops collecting",
    "who still knows you when the utility stops",
]


def words(t: str) -> list[str]:
    return WORD.findall(t)


def sents(t: str) -> list[str]:
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
    n = 0
    for x in w:
        if x in ADJ:
            n += 1
        elif re.search(r"(ful|ous|ive|ical|less|ish)$", x) and len(x) > 5:
            n += 1
    return n / len(w)


def parse_pairs(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n(?=\[\d{4}-\d{2}-\d{2})", text)
    out = []
    for i, b in enumerate(blocks):
        m = re.search(r"\[([^\]]+)\].*?User:\s*(.*?)\nMoodyBot:\s*(.*)\s*$", b, re.S)
        if not m:
            continue
        out.append(
            {
                "index": i,
                "ts": m.group(1),
                "user": m.group(2).strip(),
                "bot": m.group(3).strip(),
            }
        )
    return out


def hard_reject(bot: str) -> str | None:
    if re.search(
        r"tag @|mention @|subscribe|hold space|the truth is|"
        r"what.?s really happening|incentive structure|"
        r"identity architecture|pattern recognition engine|"
        r"narrative contract|epistemic|delve\b|tapestry|"
        r"beautiful mess|my dear|emotional roulette|"
        r"if it slapped|share the sting|hit that.?🔁|"
        r"pass it\.?\s*🔁|owe them the tremor",
        bot,
        re.I,
    ):
        return "banned"
    if re.search(
        r"\b(validate your|inner child|attachment style|healing journey|"
        r"emotional regulation|self[- ]care|hold space)\b",
        bot,
        re.I,
    ):
        return "therapy"
    if len(LIKE.findall(bot)) >= 2:
        return "multi_metaphor"
    if len(re.findall(r"\b(shadow|echo|soul|symphony|whisper|storm)\b", bot, re.I)) >= 3:
        return "costume"
    paras = [p for p in bot.split("\n") if p.strip()]
    if len(paras) >= 5:
        return "too_many_paras"
    wc = len(words(bot))
    if wc < 15 or wc > 175:
        return "length"
    if re.search(
        r"^(there are (several|many)|it'?s important to|let'?s (unpack|explore|dive))",
        bot,
        re.I,
    ):
        return "ai_opener"
    return None


def is_gold_quality(user: str, bot: str) -> bool:
    """Strict writing-quality gate approximating 9/10."""
    if hard_reject(bot):
        return False
    # Must-include overrides still pass hard_reject
    for snip in MUST_INCLUDE_SNIPPETS:
        if snip.lower() in bot.lower():
            return True

    wc = len(words(bot))
    ss = sents(bot)
    avg = wc / max(1, len(ss))
    if avg > 23:
        return False

    # Prefer reframe / contradiction / clean naming
    reframe = bool(
        re.search(
            r"you.?re (not|describing|confusing|measuring|calling|stuck)|"
            r"that.?s not|isn.?t .+—|doesn.?t (forgive|mean)|"
            r"not everyone|the (tell|premise|spell|filter|hook)|"
            r"transaction, not|fear dressed|loyalty program|"
            r"choices you make|stop waiting|you already know",
            bot,
            re.I,
        )
    )
    if not reframe:
        return False

    # Conversational
    if not re.search(r"\b\w+'(t|s|re|ll|ve|d)\b|\byou\b", bot, re.I):
        return False

    # Concrete presence
    concrete = len(
        re.findall(
            r"\b(money|sex|job|door|phone|text|bed|rent|bill|boss|wife|"
            r"husband|ex|pay|leave|trust|promise|rule|cost|receipt|"
            r"snoring|choice|map|throne|court|silence|boundary|drink|"
            r"lie|cheat|work|car|kids|city|door|machine|utility|"
            r"drinks|songs|audience)\b",
            bot,
            re.I,
        )
    )
    if concrete < 1 and wc > 40:
        return False

    # Reject soft essay / rewrite-echo
    if re.search(
        r"it'?s important to respect diverse|every relationship has its own blueprint|"
        r"authenticity is messy but magnetic|rejection is often redirection",
        bot,
        re.I,
    ):
        return False

    # Reject mental architecture jargon residue
    if re.search(r"mental architecture|emotional alchemy|velvet trap of every guru", bot, re.I):
        return False

    # Must have a short punch line
    punch = [s for s in ss if 5 <= len(words(s)) <= 18]
    if not punch:
        return False

    # User substance
    if len(words(user)) < 4:
        return False

    return True


def structure_of(bot: str) -> str:
    ss = sents(bot)
    wc = len(words(bot))
    paras = [p for p in bot.strip().split("\n") if p.strip()]
    if len(ss) <= 2 and wc <= 55:
        return "SNAP"
    if len(ss) >= 4 or (len(paras) >= 2 and wc >= 95):
        # STORY if has concrete example beat
        if re.search(
            r"\b(for (example|instance)|like when|the time|she |he |they |"
            r"hooker|roommate|paris|drinks|songs|morning|machine|city)\b",
            bot,
            re.I,
        ):
            return "STORY"
    return "KNIFE"


def category_of(user: str, bot: str) -> str:
    blob = (user + " " + bot).lower()
    rules = [
        ("relationships", r"girlfriend|boyfriend|wife|husband|ex|dating|love|sex|marriage|snoring"),
        ("power_status", r"\bpower\b|status|respect|throne|courtroom"),
        ("money_work", r"money|job|career|work|business|rent|web3|crypto|rugged"),
        ("social_critique", r"society|feminism|men|women|culture|cities"),
        ("psychology_self", r"myself|lonely|regret|stuck|connection|alone"),
        ("philosophy", r"meaning|truth|choice|regret|kierkegaard"),
        ("advice_practical", r"should i|options|how do i|assist"),
    ]
    for name, pat in rules:
        if re.search(pat, blob, re.I):
            return name
    return "general"


def memorable_of(bot: str) -> str:
    ss = sents(bot)
    scored = []
    for s in ss:
        n = len(words(s))
        if n < 4 or n > 22:
            continue
        pts = 0.0
        if 6 <= n <= 14:
            pts += 2
        if re.search(r"\b(not|never|stop|that'?s|isn'?t|don'?t|doesn'?t)\b", s, re.I):
            pts += 1.5
        if re.search(r"(transaction|courtroom|loyalty|strategy|spell|tell|utility)", s, re.I):
            pts += 2
        scored.append((pts, len(s), s.strip()))
    if scored:
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[0][2]
    return (ss[0] if ss else bot).strip()


def why_of(bot: str, structure: str) -> str:
    bits = []
    if re.search(r"you.?re (describing|not|stuck)|that.?s not|doesn.?t forgive|not everyone", bot, re.I):
        bits.append("reframes the premise instead of answering inside it")
    if structure == "SNAP":
        bits.append("one or two sentences; stops at the punch")
    elif structure == "KNIFE":
        bits.append("reframe → short proof → stop")
    else:
        bits.append("observation → concrete proof → implication → stop")
    if len(LIKE.findall(bot)) <= 1:
        bits.append("metaphor-disciplined")
    if len(words(bot)) <= 120:
        bits.append("does not overexplain")
    ml = memorable_of(bot)
    if ml:
        bits.append("memorable line carries the insight")
    return "; ".join(bits)


def build_gold(pairs: list[dict]) -> list[dict]:
    gold = []
    seen = set()
    for p in pairs:
        bot = p["bot"]
        if not is_gold_quality(p["user"], bot):
            # still allow must-include if only soft issues
            if not any(s.lower() in bot.lower() for s in MUST_INCLUDE_SNIPPETS):
                continue
            if hard_reject(bot):
                continue
        key = re.sub(r"\s+", " ", bot.lower())[:200]
        if key in seen:
            continue
        seen.add(key)
        structure = structure_of(bot)
        entry = {
            "id": f"gold-{p['index']:04d}",
            "original_user_prompt": p["user"],
            "assistant_response": bot,
            "category": category_of(p["user"], bot),
            "why_it_works": why_of(bot, structure),
            "memorable_line": memorable_of(bot),
            "structure": structure,
            "_meta": {"ts": p["ts"], "log_index": p["index"]},
        }
        gold.append(entry)

    # Prefer diversity: cap near-duplicates by memorable line
    final = []
    seen_ml = set()
    for g in gold:
        mlk = g["memorable_line"].lower()[:80]
        if mlk in seen_ml:
            continue
        seen_ml.add(mlk)
        final.append(g)
    return final


def stats(gold: list[dict]) -> dict:
    bots = [g["assistant_response"] for g in gold]
    sent_lens = []
    resp_lens = []
    meta_freq = []
    humor = 0
    rhet = []
    adj_d = []
    contra = 0
    agree = 0
    paras = []
    grades = []
    flesches = []

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

    n = len(bots) or 1
    return {
        "n": len(bots),
        "avg_sentence_length_words": round(statistics.mean(sent_lens), 2) if sent_lens else 0,
        "avg_response_length_words": round(statistics.mean(resp_lens), 2) if resp_lens else 0,
        "median_response_length_words": statistics.median(resp_lens) if resp_lens else 0,
        "metaphor_like_a_per_response": round(statistics.mean(meta_freq), 3) if meta_freq else 0,
        "pct_with_any_like_a_metaphor": round(100 * sum(1 for x in meta_freq if x) / n, 1),
        "humor_frequency_pct": round(100 * humor / n, 1),
        "avg_rhetorical_questions": round(statistics.mean(rhet), 2) if rhet else 0,
        "adjective_density": round(statistics.mean(adj_d), 4) if adj_d else 0,
        "pct_beginning_with_contradiction": round(100 * contra / n, 1),
        "pct_beginning_with_agreement": round(100 * agree / n, 1),
        "avg_paragraphs": round(statistics.mean(paras), 2) if paras else 0,
        "avg_flesch_kincaid_grade": round(statistics.mean(grades), 2) if grades else 0,
        "avg_flesch_reading_ease": round(statistics.mean(flesches), 2) if flesches else 0,
        "structure_counts": dict(Counter(g["structure"] for g in gold)),
        "category_counts": dict(Counter(g["category"] for g in gold)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = parse_pairs(LOG)
    print(f"parsed {len(pairs)}")
    gold = build_gold(pairs)
    print(f"gold {len(gold)}")

    # Strip meta for public gold file; keep sidecar
    public = []
    for g in gold:
        public.append({k: v for k, v in g.items() if not k.startswith("_")})

    (OUT / "gold.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in public) + "\n",
        encoding="utf-8",
    )
    (OUT / "gold.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    st = stats(gold)
    (OUT / "stats.json").write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(st, indent=2))

    # Print a sample for verification
    for g in public[:12]:
        print("---", g["id"], g["structure"], g["category"])
        print(g["memorable_line"])


if __name__ == "__main__":
    main()
