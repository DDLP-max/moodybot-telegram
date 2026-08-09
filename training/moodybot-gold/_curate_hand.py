#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hand-curated Gold set.

Only responses that clear a human 9/10 writing bar:
reframe, one memorable line, conversational, concrete, one insight, stops.
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

# Hand-picked fingerprints (unique substrings from moodybot_log.txt)
# Selected by reading for writing quality — not agreement.
GOLD_FINGERPRINTS = [
    # Late sharp period
    "You're describing a transaction, not a superpower",
    "Power doesn’t forgive sins. It just changes the courtroom",
    "Snoring. Mouth odour and body odour are choices you make every morning",
    "You want to be *seen* without being *touched*",
    "Not everyone agrees feminism destroyed society",
    "Pick the one where you can’t bullshit yourself for longer than a week",
    "You’re stuck because you keep choosing the version of yourself that avoids the work",
    "They’d name the exact thing you’re scared they see when the room goes quiet",
    "That’s not strategy. That’s fear dressed up as clever",
    "You didn't see the pull coming. That's not bad luck—it's the tax on trust",
    "The ache isn't in the silence—it's in the expectation",
    "Anger just unlocked the door",
    "midwives don't get to absolve themselves by pointing at the baby",
    "treating web3 like a slot machine instead of a skill loop",
    "The cities on that list are fine if you want volume",
    # Strong mid-corpus knives
    "You're not wrong. Dating's turned into a gauntlet",
    "“He grew on me” isn’t evolution; it’s erosion",
    "Ah, the classic projection grenade",
    "Yeah, that's the velvet trap of every guru's pitch",
    "You’re not wrong that faces tell stories",
    "There isn’t a single cure. Depression isn’t a lock waiting for one key",
    "You don't touch her on a first date—you earn the invitation",
    "You remember when $10k felt like lightning",
    "You poured eight years into the glow of screens",
    "You think her job's to look pretty? Fine",
    "You’re not wrong to wonder. In the old phone call days",
    "Fair point—you're calling bullshit on the relic narrative",
    # Clean early-ish punches that still hold
    "Constantly pretending to know everything while fearing the silence of an unanswered question",
    "Cut them off like a gangrenous limb",  # borderline metaphor — keep only if rest is clean; will review
    "Watching characters walk away from explosions without a scratch",
    "Alone, every single time. Solitude doesn’t mean silence",
    "Kindness without discernment is like giving away a shield",  # one metaphor ok
    "Some see shadows in the family photo, not burdens to bear",
    "That sounds like an interesting concept. The physical sensation of holding money",  # weak - skip later
    "Social media might have widened the horizon, but love isn't on the hook",
    "There it is, the velvet curtain behind the hard sell",
    "The myth of \"when I get rich\" is a seductive dream",
    "Maturing as a woman is peeling back the layers",
    "Trust isn’t a currency — it’s an investment",  # soft - may drop
    "You can't save anyone who doesn't want to be saved",
    "Everyone's swaying between the past and the future",  # costume risk
    "Layered defenses, my friend",  # CTA risk skip
]

# Explicit rejects among fingerprints if matched poorly
DROP_IF_CONTAINS = [
    "Tag @MoodyBotAI",
    "Mention @MoodyBotAI",
    "If it slapped",
    "share the sting",
    "Hit that 🔁",
    "Pass it. 🔁",
    "owe them the tremor",
]


WORD = re.compile(r"[A-Za-z']+")
SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-Z\"'“‘0-9])")
LIKE = re.compile(r"\blike a\b|\bas if\b|\bas though\b", re.I)
RHET_Q = re.compile(r"\?")
HUMOR = re.compile(
    r"\b(absurd|ridiculous|bullshit|fuckery|stupid|ironic|irony|"
    r"chainsawing|slot machine|loyalty program|victory lap|"
    r"pretty lighting|eat before they leave|projection grenade|"
    r"velvet trap|gauntlet)\b",
    re.I,
)
CONTRADICTION = re.compile(
    r"^(no[,.]?\s|not\s|wrong|false|that'?s not|you'?re not|"
    r"you'?re describing|stop\s|power doesn'?t|not everyone|"
    r"that'?s not strategy|you already know|snoring\.|"
    r"there isn'?t|you don'?t touch|alone[,.]|fair point)",
    re.I,
)
AGREEMENT = re.compile(
    r"^(yes[,.]?\s|yeah[,.]?\s|yep|exactly|agreed|true[,.]?\s|"
    r"you'?re right|absolutely|spot on)",
    re.I,
)
ADJ = {
    "beautiful", "deep", "emotional", "powerful", "profound", "raw", "real",
    "true", "authentic", "messy", "brutal", "quiet", "loud", "hard", "soft",
    "cold", "warm", "dark", "sharp", "clean", "ugly", "pretty", "lonely",
    "empty", "heavy", "fragile", "strong", "endless", "fleeting", "toxic",
    "intimate", "chaotic", "stupid", "daily", "clear", "fine", "real",
}


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


def structure_of(bot: str) -> str:
    ss = sents(bot)
    wc = len(words(bot))
    paras = [p for p in bot.strip().split("\n") if p.strip()]
    if len(ss) <= 2 and wc <= 60:
        return "SNAP"
    if wc >= 90 and (
        re.search(
            r"\b(hooker|roommate|paris|drinks|songs|morning|machine|city|"
            r"first date|eight years|\$10k|lower back|crowds)\b",
            bot,
            re.I,
        )
        or len(ss) >= 5
    ):
        return "STORY"
    return "KNIFE"


def category_of(user: str, bot: str) -> str:
    blob = (user + " " + bot).lower()
    rules = [
        ("relationships", r"girlfriend|boyfriend|wife|husband|ex|dating|love|sex|marriage|snoring|touch"),
        ("power_status", r"\bpower\b|status|respect|throne|courtroom"),
        ("money_work", r"money|job|career|work|business|rent|web3|crypto|rugged|\$"),
        ("social_critique", r"society|feminism|men|women|culture|cities|physiognomy|onlyfans"),
        ("psychology_self", r"stuck|connection|alone|depression|lonely|seen"),
        ("philosophy", r"truth|choice|regret|meaning"),
        ("culture_media", r"movie|explosion|wes anderson"),
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
        if n < 4 or n > 24:
            continue
        pts = 0.0
        if 5 <= n <= 16:
            pts += 2
        if re.search(
            r"\b(not|never|stop|that'?s|isn'?t|don'?t|doesn'?t|transaction|"
            r"courtroom|loyalty|strategy|spell|tell|utility|erosion|fear)\b",
            s,
            re.I,
        ):
            pts += 2
        scored.append((pts, len(s), s.strip()))
    if scored:
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[0][2]
    return (ss[0] if ss else bot).strip()


def why_of(bot: str, structure: str) -> str:
    bits = []
    if re.search(
        r"you.?re (describing|not|stuck)|that.?s not|doesn.?t forgive|not everyone|"
        r"fear dressed|transaction, not|isn.?t evolution|earn the invitation",
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


# Extra hand drops after fingerprint match (writing failed on re-read)
MANUAL_DROP_SNIPPETS = [
    "Cut them off like a gangrenous limb",  # forced metaphor + CTA variants
    "That sounds like an interesting concept",  # soft / essay
    "Trust isn’t a currency — it’s an investment",  # motivational residue
    "Everyone's swaying between the past and the future",  # costume
    "Layered defenses, my friend",  # CTA
    "Maturing as a woman is peeling back the layers",  # essayistic
    "Social media might have widened the horizon",  # soft
    "Fair point—you're calling bullshit on the relic narrative",  # meandering
    "Some see shadows in the family photo",  # costume-ish
    "Kindness without discernment is like giving away a shield",  # therapy-adjacent
    "Not to be forgiven—just to finally hear the truth",  # engagement closer
    "Mention ",
    "Tag ",
    "your sanity isn’t meant to be a playground",
    "Yeah, that's the velvet trap of every guru's pitch",  # ends in bait
    "Ah, the classic projection grenade",  # slightly costume / showy
    "There it is, the velvet curtain behind the hard sell",  # showy
    "The myth of \"when I get rich\" is a seductive dream",  # dilutes
    "You’re not wrong to wonder. In the old phone call days",  # long soft middle
    "You poured eight years into the glow of screens",  # overwrites with costume
    "You remember when $10k felt like lightning",  # meandering
    "You’re not wrong that faces tell stories",  # long
    "You think her job's to look pretty? Fine",  # escaped punctuation / soft end
]


def collect_gold(pairs: list[dict]) -> list[dict]:
    found = []
    seen = set()
    for p in pairs:
        bot = p["bot"]
        if any(d.lower() in bot.lower() for d in DROP_IF_CONTAINS):
            continue
        if any(d.lower() in bot.lower() for d in MANUAL_DROP_SNIPPETS):
            continue
        matched = None
        for fp in GOLD_FINGERPRINTS:
            if fp.lower() in bot.lower():
                matched = fp
                break
        if not matched:
            continue
        key = re.sub(r"\s+", " ", bot.lower())[:220]
        if key in seen:
            continue
        seen.add(key)
        # length sanity
        if not (20 <= len(words(bot)) <= 175):
            continue
        if len(LIKE.findall(bot)) >= 2:
            continue
        structure = structure_of(bot)
        found.append(
            {
                "id": f"gold-{len(found)+1:03d}",
                "original_user_prompt": p["user"],
                "assistant_response": bot,
                "category": category_of(p["user"], bot),
                "why_it_works": why_of(bot, structure),
                "memorable_line": memorable_of(bot),
                "structure": structure,
                "_log_index": p["index"],
                "_ts": p["ts"],
                "_matched": matched,
            }
        )
    return found


def stats(gold: list[dict]) -> dict:
    bots = [g["assistant_response"] for g in gold]
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
        paras.append(len([p for p in b.split("\n") if p.strip()]))
        grades.append(fk_grade(b))
        flesches.append(flesch(b))
        if re.search(
            r"\b(door|hand|back|eyes?|machine|throne|courtroom|drinks?|"
            r"songs?|screens?|lightning|chainsawing|slot machine)\b",
            b,
            re.I,
        ):
            physical_image += 1
        if any(5 <= len(words(s)) <= 16 for s in ss):
            memorable_present += 1
    n = len(bots) or 1
    return {
        "n": len(bots),
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
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = parse_pairs(LOG)
    gold = collect_gold(pairs)
    print(f"hand-curated gold: {len(gold)}")
    for g in gold:
        print(g["id"], g["structure"], g["_matched"][:50], "->", g["memorable_line"][:70])

    public = [{k: v for k, v in g.items() if not k.startswith("_")} for g in gold]
    (OUT / "gold.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in public) + "\n", encoding="utf-8"
    )
    (OUT / "gold.json").write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    st = stats(gold)
    (OUT / "stats.json").write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    (OUT / "_gold_meta.json").write_text(
        json.dumps([{k: g[k] for k in g} for g in gold], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(st, indent=2))


if __name__ == "__main__":
    main()
