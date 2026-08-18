#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild MoodyBot Gold — writing quality only (9/10+), never agreement.

Sources:
  1) Hand-kept historical pairs from moodybot_log.txt
  2) Modern canonical wins (live / craft) that meet the same bar

Rejects therapy, systems jargon, engagement bait, stacked metaphor, AI essay.
"""

from __future__ import annotations

import json
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
    r"\b(absurd|ridiculous|bullshit|fuckery|stupid|ironic|irony|"
    r"chainsawing|slot machine|loyalty program|victory lap|"
    r"pretty lighting|eat before they leave|fear dressed|"
    r"opening act|ranked it|safest one)\b",
    re.I,
)
CONTRADICTION = re.compile(
    r"^(no[,.]?\s|not\s|wrong|false|that'?s not|you'?re not|"
    r"you'?re describing|stop\s|power doesn'?t|not everyone|"
    r"that'?s not strategy|you already know|snoring\.|"
    r"there isn'?t|you don'?t touch|alone[,.]|fair point|"
    r"the word |breaking bad didn'?t|mcdonald'?s doesn'?t|"
    r"that'?s like saying|every threat|most people don'?t|"
    r"the cities|it'?s called|the right person)",
    re.I,
)
AGREEMENT = re.compile(
    r"^(yes[,.]?\s|yeah[,.]?\s|yep|exactly|agreed|true[,.]?\s|"
    r"you'?re right|absolutely|spot on|you'?re not wrong)",
    re.I,
)
ADJ = {
    "beautiful", "deep", "emotional", "powerful", "profound", "raw", "real",
    "true", "authentic", "messy", "brutal", "quiet", "loud", "hard", "soft",
    "cold", "warm", "dark", "sharp", "clean", "ugly", "pretty", "lonely",
    "empty", "heavy", "fragile", "strong", "endless", "fleeting", "toxic",
    "intimate", "chaotic", "stupid", "daily", "clear", "fine",
}

# Fingerprints that must exist in moodybot_log.txt (historical Gold)
LOG_KEEP = [
    "That's not strategy. That's fear dressed up as clever",
    "You're describing a transaction, not a superpower",
    "Power doesn't forgive sins. It just changes the courtroom",
    "Snoring. Mouth odour and body odour are choices you make every morning",
    "You want to be *seen* without being *touched*",
    "Not everyone agrees feminism destroyed society",
    "Pick the one where you can't bullshit yourself for longer than a week",
    "You're stuck because you keep choosing the version of yourself that avoids the work",
    "You can't save anyone who doesn't want to be saved",
    "Constantly pretending to know everything while fearing the silence of an unanswered question",
    "You're not wrong. Dating's turned into a gauntlet",
    "You didn't see the pull coming. That's not bad luck",
    "The right person doesn't make you guess",
    "Everything else is your history trying to sell you a harder story",
]

# Modern / craft Gold not necessarily in the old log (still 9/10 writing)
MODERN_GOLD = [
    {
        "original_user_prompt": (
            "'Foreplay' is a misleading term that makes women's pleasure sound optional "
            "while treating men's pleasure mandatory."
        ),
        "assistant_response": (
            'The word "foreplay" already decided the hierarchy. It calls everything before '
            "penetration the opening act, which only works if penetration is the main event. "
            "The term didn't describe desire. It ranked it."
        ),
        "category": "language_culture",
        "why_it_works": (
            "reframes the premise inside the word itself; one clean mechanism; "
            "three sentences then stop; memorable open + close; conversational"
        ),
        "memorable_line": 'The word "foreplay" already decided the hierarchy.',
        "structure": "KNIFE",
        "source": "canonical-live",
    },
    {
        "original_user_prompt": "McDonald's is easily the best place for burgers and fries.",
        "assistant_response": "That's like saying a prison cell is just a room.",
        "category": "taste_preference",
        "why_it_works": (
            "escapes the author's frame instead of arguing burgers; "
            "one physical analogy; SNAP; stops"
        ),
        "memorable_line": "That's like saying a prison cell is just a room.",
        "structure": "SNAP",
        "source": "canonical-craft",
    },
    {
        "original_user_prompt": "McDonald's is easily the best place for burgers and fries.",
        "assistant_response": (
            "McDonald's doesn't make the best burger. It makes the safest one."
        ),
        "category": "taste_preference",
        "why_it_works": (
            "object-first taste; relocates 'best' to 'safest'; "
            "two sentences; concrete; stops"
        ),
        "memorable_line": "It makes the safest one.",
        "structure": "SNAP",
        "source": "canonical-craft",
    },
    {
        "original_user_prompt": (
            "no show will ever compare to breaking bad and better call saul... ever."
        ),
        "assistant_response": (
            "Breaking Bad didn't ruin television. It raised the price of impressing you."
        ),
        "category": "taste_preference",
        "why_it_works": (
            "object-first; talks about the work not the viewer's fear; "
            "one memorable reframe; SNAP"
        ),
        "memorable_line": "It raised the price of impressing you.",
        "structure": "SNAP",
        "source": "canonical-craft",
    },
    {
        "original_user_prompt": (
            "If you keep acting like that you'll end up a cat lady. "
            "You'll die alone with your cats."
        ),
        "assistant_response": (
            "Every threat is autobiographical. People don't invent fears. They export them."
        ),
        "category": "psychology_self",
        "why_it_works": (
            "Mode 2 discovery; names the projection mechanism without therapy; "
            "short; stealable; stops"
        ),
        "memorable_line": "Every threat is autobiographical.",
        "structure": "SNAP",
        "source": "canonical-craft",
    },
    {
        "original_user_prompt": (
            "We want different things. She wanted forever. I wanted space. "
            "She wanted an exit that didn't make her the bad guy."
        ),
        "assistant_response": (
            "Most people don't edit the relationship. They edit the ending."
        ),
        "category": "relationships",
        "why_it_works": (
            "does not paraphrase the author's discovery; rotates it; "
            "one line; Mode 2; stops"
        ),
        "memorable_line": "Most people don't edit the relationship. They edit the ending.",
        "structure": "SNAP",
        "source": "canonical-craft",
    },
    {
        "original_user_prompt": (
            "If the girl or guy you're talking to isn't 100% obsessed with you, move on. "
            "With the right person there's no guessing games. When someone is really into you, you'll know."
        ),
        "assistant_response": (
            "The right person doesn't make you guess. They show up without a strategy. "
            "Everything else is your history trying to sell you a harder story "
            "so the easy one doesn't feel like a trick."
        ),
        "category": "relationships",
        "why_it_works": (
            "relocates dating advice to the hidden dynamic — distrust of healthy ease; "
            "one mechanism; memorable close; stops"
        ),
        "memorable_line": "Everything else is your history trying to sell you a harder story.",
        "structure": "KNIFE",
        "source": "canonical-craft",
    },
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
    n = sum(
        1
        for x in w
        if x in ADJ or (len(x) > 5 and re.search(r"(ful|ous|ive|ical|less|ish)$", x))
    )
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
            {"index": i, "ts": m.group(1), "user": m.group(2).strip(), "bot": m.group(3).strip()}
        )
    return out


def strip_whiskey(t: str) -> str:
    return re.sub(r"\s*🥃\s*", " ", t or "").strip()


def norm(t: str) -> str:
    return (
        (t or "")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .replace("–", "-")
        .lower()
    )


def strip_cta_tails(t: str) -> str:
    t = strip_whiskey(t)
    # Drop known engagement / signature tails if present in log copy
    for pat in (
        r"\s*Tag @MoodyBotAI.*$",
        r"\s*Mention @MoodyBotAI.*$",
        r"\s*You'?ll (flinch|hear|taste) this.*$",
        r"\s*Hit that.*$",
        r"\s*Pass it\..*$",
    ):
        t = re.sub(pat, "", t, flags=re.I | re.S).strip()
    return t


def structure_of(bot: str) -> str:
    ss = sents(bot)
    wc = len(words(bot))
    if len(ss) <= 2 and wc <= 55:
        return "SNAP"
    if wc >= 95 and len(ss) >= 5:
        return "STORY"
    if wc >= 90 and re.search(
        r"\b(hooker|roommate|paris|drinks|songs|morning|machine|city|"
        r"first date|utility|audience)\b",
        bot,
        re.I,
    ):
        return "STORY"
    return "KNIFE"


def category_of(user: str, bot: str) -> str:
    blob = (user + " " + bot).lower()
    rules = [
        ("relationships", r"girlfriend|boyfriend|dating|love|sex|marriage|snoring|touch|obsessed"),
        ("power_status", r"\bpower\b|status|respect|throne|courtroom"),
        ("money_work", r"money|job|career|work|business|rent|web3|crypto|rugged|\$"),
        ("social_critique", r"society|feminism|culture|cities"),
        ("taste_preference", r"mcdonald|burger|show|television|breaking bad|foreplay|meal"),
        ("language_culture", r"foreplay|word |term |hierarchy|language"),
        ("psychology_self", r"stuck|connection|alone|depression|lonely|seen|threat|fear"),
        ("philosophy", r"truth|choice|regret|meaning|save anyone"),
        ("culture_media", r"movie|explosion"),
    ]
    for name, pat in rules:
        if re.search(pat, blob, re.I):
            return name
    return "general"


def memorable_of(bot: str, preferred: str = "") -> str:
    if preferred:
        return preferred
    ss = sents(bot)
    scored = []
    for s in ss:
        n = len(words(s))
        if n < 4 or n > 28:
            continue
        pts = 0.0
        if 5 <= n <= 16:
            pts += 2
        if re.search(
            r"\b(not|never|stop|that'?s|isn'?t|don'?t|doesn'?t|transaction|"
            r"courtroom|loyalty|strategy|spell|tell|utility|fear|hierarchy|"
            r"ranked|autobiographical|edit the ending|safest|prison cell|"
            r"raised the price)\b",
            s,
            re.I,
        ):
            pts += 2
        scored.append((pts, len(s), s.strip()))
    if scored:
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[0][2]
    return (ss[0] if ss else bot).strip()


def why_of(bot: str, structure: str, custom: str = "") -> str:
    if custom:
        return custom
    bits = []
    if re.search(
        r"you.?re (describing|not|stuck)|that.?s not|doesn.?t forgive|not everyone|"
        r"fear dressed|transaction, not|already decided|raised the price|"
        r"edit the ending|autobiographical|prison cell|safest one|"
        r"history trying to sell",
        bot,
        re.I,
    ):
        bits.append("reframes the user's premise")
    bits.append(
        {
            "SNAP": "lands in 1–2 sentences and stops",
            "KNIFE": "reframe → short explanation → stop",
            "STORY": "observation → concrete example → implication → stop",
        }[structure]
    )
    if len(LIKE.findall(bot)) <= 1:
        bits.append("at most one metaphor")
    if len(words(bot)) <= 130:
        bits.append("stops before overexplaining")
    bits.append("sounds spoken, not essayistic")
    return "; ".join(bits)


def collect_from_log(pairs: list[dict]) -> list[dict]:
    found = []
    seen = set()
    for p in pairs:
        bot = strip_cta_tails(p["bot"])
        matched = None
        bot_n = norm(bot)
        for fp in LOG_KEEP:
            if norm(fp) in bot_n:
                matched = fp
                break
        if not matched:
            continue
        key = re.sub(r"\s+", " ", bot_n)[:200]
        if key in seen:
            continue
        seen.add(key)
        if not (12 <= len(words(bot)) <= 160):
            continue
        if len(LIKE.findall(bot)) >= 2:
            continue
        # Reject systems / therapy / bait leftovers
        if re.search(
            r"governing incentive|identity architecture|pattern recognition engine|"
            r"the truth is|what'?s really happening|trauma dump|validate your feelings|"
            r"hit that|tag @|mention @",
            bot,
            re.I,
        ):
            continue
        # Drop trailing soft engagement questions on otherwise-gold knives
        bot = re.sub(r"\s+What'?s the story\?\s*$", "", bot, flags=re.I).strip()
        structure = structure_of(bot)
        found.append(
            {
                "original_user_prompt": p["user"],
                "assistant_response": bot,
                "category": category_of(p["user"], bot),
                "why_it_works": why_of(bot, structure),
                "memorable_line": memorable_of(bot),
                "structure": structure,
                "source": "moodybot_log",
                "_matched": matched,
            }
        )
    return found


def compute_stats(gold: list[dict]) -> dict:
    bots = [g["assistant_response"] for g in gold]
    sent_lens, resp_lens, meta_freq, rhet, adj_d, paras, grades, flesches = (
        [], [], [], [], [], [], [], [],
    )
    humor = contra = agree = 0
    physical_image = 0
    memorable_present = 0
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
        paras.append(max(1, len([p for p in b.split("\n") if p.strip()])))
        grades.append(fk_grade(b))
        flesches.append(flesch(b))
        if re.search(
            r"\b(door|hand|back|eyes?|machine|throne|courtroom|drinks?|"
            r"songs?|screens?|chainsawing|slot machine|prison cell|"
            r"burger|television|opening act|morning)\b",
            b,
            re.I,
        ):
            physical_image += 1
        if any(5 <= len(words(s)) <= 18 for s in ss):
            memorable_present += 1
    n = len(bots) or 1
    return {
        "n": len(bots),
        "corpus_pairs_scanned": None,  # filled in main
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
        "pct_with_physical_image": round(100 * physical_image / n, 1),
        "pct_with_short_memorable_sentence": round(100 * memorable_present / n, 1),
        "structure_counts": dict(Counter(g["structure"] for g in gold)),
        "category_counts": dict(Counter(g["category"] for g in gold)),
        "source_counts": dict(Counter(g.get("source", "?") for g in gold)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = parse_pairs(LOG) if LOG.exists() else []
    historical = collect_from_log(pairs)
    print(f"log pairs: {len(pairs)}")
    print(f"historical gold kept: {len(historical)}")

    # Merge modern — skip duplicates by memorable / response stem
    stems = {re.sub(r"\s+", " ", g["assistant_response"].lower())[:120] for g in historical}
    merged = list(historical)
    for m in MODERN_GOLD:
        stem = re.sub(r"\s+", " ", m["assistant_response"].lower())[:120]
        if stem in stems:
            continue
        stems.add(stem)
        structure = m.get("structure") or structure_of(m["assistant_response"])
        merged.append(
            {
                "original_user_prompt": m["original_user_prompt"],
                "assistant_response": m["assistant_response"],
                "category": m["category"],
                "why_it_works": m["why_it_works"],
                "memorable_line": m["memorable_line"],
                "structure": structure,
                "source": m["source"],
            }
        )

    # Stable ids
    gold = []
    for i, g in enumerate(merged, 1):
        row = {
            "id": f"gold-{i:03d}",
            "original_user_prompt": g["original_user_prompt"],
            "assistant_response": g["assistant_response"],
            "category": g["category"],
            "why_it_works": g["why_it_works"],
            "memorable_line": g["memorable_line"],
            "structure": g["structure"],
        }
        gold.append(row)
        print(row["id"], row["structure"], row["memorable_line"][:70])

    st = compute_stats([{**g, "source": merged[i].get("source", "?")} for i, g in enumerate(gold)])
    # fix source attachment
    for i, g in enumerate(gold):
        g["_source"] = merged[i].get("source", "?")
    st = compute_stats(
        [
            {
                **{k: v for k, v in g.items() if k != "_source"},
                "source": g.get("_source", "?"),
                "assistant_response": g["assistant_response"],
                "structure": g["structure"],
                "category": g["category"],
            }
            for g in gold
        ]
    )
    st["corpus_pairs_scanned"] = len(pairs)

    public = [{k: v for k, v in g.items() if not k.startswith("_")} for g in gold]
    (OUT / "gold.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "gold.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in public) + "\n", encoding="utf-8"
    )
    (OUT / "stats.json").write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(st, indent=2))
    print(f"FINAL GOLD: {len(public)}")


if __name__ == "__main__":
    main()
