#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract Gold-tier MoodyBot responses from moodybot_log.txt for training."""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # replit/
LOG = ROOT / "moodybot_log.txt"
OUT = ROOT / "training" / "moodybot-gold"
CANDIDATES = OUT / "_candidates.jsonl"
REJECTED_SAMPLE = OUT / "_rejected_sample.jsonl"

# Hard reject substrings / patterns (case-insensitive)
HARD_REJECT = [
    r"\bthe truth is\b",
    r"\bwhat'?s really happening\b",
    r"governing incentive structure",
    r"identity architecture",
    r"pattern recognition engine",
    r"\bas an ai\b",
    r"\bi'?m an ai\b",
    r"\blet'?s dive (in|deeper)\b",
    r"\bat the end of the day\b",
    r"\bit'?s important to (remember|note|recognize)\b",
    r"\bin today'?s (world|society)\b",
    r"\bnavigate (the |their )?(complex|emotional)\b",
    r"\bhold space\b",
    r"\bvalidate (your|their) feelings\b",
    r"\btrauma response\b",
    r"\battachment style\b",
    r"\bcoping mechanism\b",
    r"\bemotional regulation\b",
    r"\bself[- ]care\b",
    r"\byour journey\b",
    r"\binner child\b",
    r"\bshadow work\b",
    r"\btoxic positivity\b",
    r"\bgaslighting\b.*\bnarcissist\b",  # stacked therapy jargon
    r"incentive structure",
    r"narrative contract",
    r"epistemic",
    r"coherence (failure|collapse|problem)",
    r"behavioral framework",
    r"systemic dynamic",
    r"\bmeta[- ]analysis\b",
    r"\bframework for\b",
    r"\bdelve\b",
    r"\btapestry\b",
    r"\blandscape of\b",
    r"\bin the realm of\b",
    r"\bmultifaceted\b",
    r"\bnuanced (approach|understanding|perspective)\b",
]

HARD_RE = [re.compile(p, re.I) for p in HARD_REJECT]

# Engagement bait / CTA
CTA_RE = re.compile(
    r"(subscribe|follow me|hit (like|follow)|drop a|comment below|link in bio|"
    r"what do you think\?$|agree\?$|tag someone|share this|"
    r"click (here|the link)|dm me|join (my|the) (channel|community|discord)|"
    r"👉|🔥🔥|💯💯)",
    re.I | re.M,
)

# Fake profundity / prompt-engineering tells
FAKE_PROFOUND = re.compile(
    r"(and that.?s the real (secret|truth|lesson)|"
    r"remember(,| this)|here'?s the (real )?kicker|"
    r"food for thought|ponder (this|on)|"
    r"sit with that|let that sink in|"
    r"mic drop|chef'?s kiss|"
    r"my (dear|darling|beautiful mess|volatile angel)|"
    r"whiskey[- ]bar|noir (detective|night))",
    re.I,
)

SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-Z\"'“‘0-9])|(?<=\n)\s*")
WORD_RE = re.compile(r"[A-Za-z']+")
METAPHOR_MARKERS = re.compile(
    r"\b(like a|as if|as though|metaphor|mirror of|symphony of|dance of|"
    r"battlefield of|chess|roulette|tango|circus|ferrari|cliff)\b",
    re.I,
)
HUMOR_MARKERS = re.compile(
    r"\b(lol|lmao|haha|joke|funny|absurd|ridiculous|bullshit|fuckery|"
    r"stupid|dumb|comedy|ironic|irony|laugh)\b|"
    r"[!]{2,}|\bshit\b|\bcrap\b",
    re.I,
)
RHETORICAL_Q = re.compile(r"\?")
ADJ_CANDIDATES = {
    "beautiful", "deep", "emotional", "powerful", "profound", "raw", "real",
    "true", "authentic", "messy", "brutal", "quiet", "loud", "hard", "soft",
    "cold", "warm", "dark", "light", "sharp", "clean", "ugly", "pretty",
    "lonely", "empty", "full", "heavy", "light", "fragile", "strong",
    "endless", "fleeting", "sacred", "toxic", "intimate", "chaotic",
}
CONTRADICTION_START = re.compile(
    r"^(no[,.]?\s|not\s|wrong[.:]|false[.:]|that'?s not|you'?re not|"
    r"stop\s|don'?t\s|never\s|nobody\s|nothing\s|bullshit|"
    r"the premise|that premise|you'?re describing|you'?re confusing|"
    r"incorrect|missed it|back up)",
    re.I,
)
AGREEMENT_START = re.compile(
    r"^(yes[,.]?\s|yeah[,.]?\s|yep|exactly|agreed|true[,.]?\s|"
    r"you'?re right|fair|absolutely|spot on|correct)",
    re.I,
)


@dataclass
class Pair:
    ts: str
    user: str
    bot: str
    index: int


def parse_log(path: Path) -> list[Pair]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n(?=\[\d{4}-\d{2}-\d{2})", text)
    pairs: list[Pair] = []
    for i, block in enumerate(blocks):
        m_ts = re.match(r"\[([^\]]+)\]", block.strip())
        if not m_ts:
            continue
        um = re.search(r"User:\s*(.*?)\nMoodyBot:\s*(.*)\s*$", block, re.S)
        if not um:
            continue
        user = um.group(1).strip()
        bot = um.group(2).strip()
        if not user or not bot:
            continue
        pairs.append(Pair(ts=m_ts.group(1), user=user, bot=bot, index=i))
    return pairs


def sentences(text: str) -> list[str]:
    parts = [s.strip() for s in SENT_SPLIT.split(text) if s and s.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def count_metaphors(text: str) -> int:
    return len(METAPHOR_MARKERS.findall(text))


def hard_reject_reason(bot: str) -> str | None:
    for cre in HARD_RE:
        if cre.search(bot):
            return f"hard:{cre.pattern[:60]}"
    if CTA_RE.search(bot):
        return "engagement_bait"
    if FAKE_PROFOUND.search(bot):
        return "fake_profundity_or_costume"
    if count_metaphors(bot) >= 3:
        return "multiple_metaphors"
    # Essayistic: long + many paragraphs of abstract padding
    paras = [p for p in bot.split("\n") if p.strip()]
    if len(paras) >= 6:
        return "too_many_paragraphs"
    wc = len(words(bot))
    if wc > 220:
        return "too_long_overexplain"
    if wc < 8:
        return "too_thin"
    # Therapy/systems stacked jargon density
    therapyish = len(
        re.findall(
            r"\b(validate|process(ing)? (your|their) (feelings|emotions)|"
            r"boundaries? work|inner work|healing journey|self[- ]worth|"
            r"codependen|narcissis|projection|trigger(ed)?|"
            r"unconscious|subconscious pattern)\b",
            bot,
            re.I,
        )
    )
    if therapyish >= 2:
        return "therapy_language"
    # AI-sounding openers / structures
    if re.search(
        r"^(there are (several|many|a few) (factors|reasons|things)|"
        r"it'?s (important|crucial|essential) to|"
        r"let'?s (break|unpack|explore)|"
        r"here are \d+|first(ly)?,?\s+second(ly)?)",
        bot,
        re.I,
    ):
        return "ai_structure"
    return None


def gold_score(user: str, bot: str) -> tuple[float, dict]:
    """Heuristic 0-10 approximating writing-quality gold."""
    sents = sentences(bot)
    w = words(bot)
    wc = len(w)
    sc = len(sents)
    paras = [p for p in bot.split("\n") if p.strip()]
    feats: dict = {}

    score = 5.0

    # Concrete language: ratio of short words, concrete markers
    concrete_hits = len(
        re.findall(
            r"\b(money|sex|work|job|door|phone|text|bed|car|rent|bill|"
            r"boss|wife|husband|kid|kids|friend|ex|body|hand|eye|"
            r"kitchen|street|night|morning|coffee|drink|pay|leave|"
            r"stay|wait|call|message|lie|cheat|trust|promise|rule|"
            r"cost|price|risk|move|boundary|room|silence)\b",
            bot,
            re.I,
        )
    )
    feats["concrete_hits"] = concrete_hits
    if concrete_hits >= 2:
        score += 1.0
    elif concrete_hits == 0 and wc > 40:
        score -= 0.8

    # One clean insight / reframe signals
    reframe = bool(
        re.search(
            r"\b(not .+[,.] it'?s|you'?re (not|describing|confusing|calling)|"
            r"the (real|actual) (problem|issue|tell|move)|"
            r"that'?s not|wrong premise|premise |"
            r"isn'?t .+[,.] it'?s|stop (calling|pretending|asking))\b",
            bot,
            re.I,
        )
    )
    feats["reframe"] = reframe
    if reframe:
        score += 1.2

    # Memorable line: short punchy sentence present
    punch = [s for s in sents if 4 <= len(words(s)) <= 16]
    feats["punch_lines"] = len(punch)
    if punch:
        score += 0.8
    # Very long average sentence = essayistic
    avg_sent = (wc / sc) if sc else wc
    feats["avg_sent_len"] = round(avg_sent, 1)
    if avg_sent > 28:
        score -= 1.0
    elif 8 <= avg_sent <= 18:
        score += 0.6

    # Conversational: contractions, second person, short paras
    contractions = len(re.findall(r"\b\w+'(t|s|re|ll|ve|d)\b", bot, re.I))
    you = len(re.findall(r"\byou\b", bot, re.I))
    feats["contractions"] = contractions
    feats["you_count"] = you
    if contractions >= 1 and you >= 1:
        score += 0.7
    if len(paras) <= 3:
        score += 0.4
    if len(paras) == 1 and 20 <= wc <= 90:
        score += 0.5

    # Stops before overexplaining
    if 25 <= wc <= 110:
        score += 0.8
    elif 111 <= wc <= 160:
        score += 0.2
    elif wc > 180:
        score -= 0.8

    # Metaphor discipline
    meta = count_metaphors(bot)
    feats["metaphors"] = meta
    if meta == 0:
        score += 0.3
    elif meta == 1:
        score += 0.5
    else:
        score -= 0.5 * (meta - 1)

    # Avoid essay transitions
    if re.search(r"\b(furthermore|moreover|additionally|in conclusion|overall)\b", bot, re.I):
        score -= 1.5

    # Bold markdown / emoji spam
    if bot.count("**") >= 4 or len(re.findall(r"[🌹🔥💀✨🎯]", bot)) >= 2:
        score -= 0.8

    # Prefer responses that don't open with throat-clearing
    if re.match(r"^(well[,.]?\s|so[,.]?\s|look[,.]?\s|listen[,.]?\s)", bot, re.I):
        score -= 0.3

    # Slight boost if opens with contradiction / reframe
    first = sents[0] if sents else bot
    if CONTRADICTION_START.search(first.strip()):
        score += 0.6
        feats["opens_contradiction"] = True
    elif AGREEMENT_START.search(first.strip()):
        feats["opens_agreement"] = True
        score -= 0.2  # gold often reframes rather than agrees

    # Penalize stacked questions (engagement)
    q = len(RHETORICAL_Q.findall(bot))
    feats["questions"] = q
    if q >= 3:
        score -= 1.0
    elif q == 1:
        score += 0.1

    # User prompt substance — prefer real prompts over greetings
    uw = len(words(user))
    if uw < 4:
        score -= 1.5
    elif uw >= 12:
        score += 0.3

    score = max(0.0, min(10.0, score))
    return score, feats


def classify_structure(bot: str) -> str:
    sents = sentences(bot)
    paras = [p for p in bot.split("\n") if p.strip()]
    wc = len(words(bot))
    if len(sents) <= 2 and wc <= 55:
        return "SNAP"
    # STORY: observation + example + implication (3+ beats / longer)
    has_example = bool(
        re.search(
            r"\b(for (example|instance)|like when|the time|remember when|"
            r"she |he |they |last (week|night|year))\b",
            bot,
            re.I,
        )
    )
    if (len(sents) >= 4 or len(paras) >= 3) and (has_example or wc >= 90):
        return "STORY"
    return "KNIFE"


def category_guess(user: str, bot: str) -> str:
    blob = (user + " " + bot).lower()
    rules = [
        ("relationships", r"\b(girlfriend|boyfriend|wife|husband|ex|dating|relationship|love|sex|marriage)\b"),
        ("power_status", r"\b(power|status|respect|alpha|dominance|hierarchy|boss)\b"),
        ("money_work", r"\b(money|job|career|work|business|rent|bill|salary|startup|web3)\b"),
        ("culture_media", r"\b(movie|show|tv|song|book|game of thrones|rotten|celebrity)\b"),
        ("psychology_self", r"\b(myself|identity|confidence|anxiety|depression|lonely|regret)\b"),
        ("social_critique", r"\b(society|feminism|men|women|culture|politics|woke)\b"),
        ("advice_practical", r"\b(should i|what (do|are) my options|how do i|help me)\b"),
        ("philosophy", r"\b(meaning|existential|kierkegaard|regret|truth|free will)\b"),
    ]
    for name, pat in rules:
        if re.search(pat, blob, re.I):
            return name
    return "general"


def memorable_line(bot: str) -> str:
    sents = sentences(bot)
    if not sents:
        return bot.strip()[:140]
    # Prefer mid-length punch with concrete/reframe energy
    scored = []
    for s in sents:
        sw = words(s)
        n = len(sw)
        if n < 4 or n > 22:
            continue
        pts = 0
        if 6 <= n <= 14:
            pts += 2
        if re.search(r"\b(not|never|stop|that'?s|isn'?t|don'?t)\b", s, re.I):
            pts += 1
        if re.search(r"[.!]$", s.strip()):
            pts += 0.5
        scored.append((pts, s.strip()))
    if scored:
        scored.sort(key=lambda x: (-x[0], len(x[1])))
        return scored[0][1]
    return sents[0].strip()


def why_it_works(bot: str, feats: dict, structure: str) -> str:
    bits = []
    if feats.get("reframe"):
        bits.append("reframes the premise instead of answering inside it")
    if feats.get("opens_contradiction"):
        bits.append("opens by cutting against the user's framing")
    if feats.get("punch_lines", 0) >= 1:
        bits.append("lands a short memorable line")
    if feats.get("metaphors", 0) <= 1:
        bits.append("keeps metaphor discipline")
    if feats.get("concrete_hits", 0) >= 2:
        bits.append("stays in concrete nouns")
    if structure == "SNAP":
        bits.append("stops at the punch")
    elif structure == "KNIFE":
        bits.append("reframe → short proof → stop")
    else:
        bits.append("observation → concrete beat → implication → stop")
    wc = len(words(bot))
    if wc <= 110:
        bits.append("does not overexplain")
    return "; ".join(bits) if bits else "clean insight with conversational delivery"


def flesch_reading_ease(text: str) -> float:
    sents = sentences(text)
    w = words(text)
    if not sents or not w:
        return 0.0
    # syllable approx
    def syl(word: str) -> int:
        word = word.lower()
        groups = re.findall(r"[aeiouy]+", word)
        n = len(groups) or 1
        if word.endswith("e") and n > 1:
            n -= 1
        return n

    syllables = sum(syl(x) for x in w)
    asl = len(w) / len(sents)
    asw = syllables / len(w)
    return 206.835 - 1.015 * asl - 84.6 * asw


def flesch_kincaid_grade(text: str) -> float:
    sents = sentences(text)
    w = words(text)
    if not sents or not w:
        return 0.0

    def syl(word: str) -> int:
        word = word.lower()
        groups = re.findall(r"[aeiouy]+", word)
        n = len(groups) or 1
        if word.endswith("e") and n > 1:
            n -= 1
        return n

    syllables = sum(syl(x) for x in w)
    asl = len(w) / len(sents)
    asw = syllables / len(w)
    return 0.39 * asl + 11.8 * asw - 15.59


def adj_density(text: str) -> float:
    w = [x.lower() for x in words(text)]
    if not w:
        return 0.0
    # crude: known adj set + -ful/-ous/-ive/-al endings excluding common nouns
    count = 0
    for x in w:
        if x in ADJ_CANDIDATES:
            count += 1
        elif re.search(r"(ful|ous|ive|ical|less|ish)$", x) and len(x) > 5:
            count += 1
    return count / len(w)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = parse_log(LOG)
    print(f"parsed {len(pairs)} pairs")

    candidates = []
    rejected = []
    for p in pairs:
        reason = hard_reject_reason(p.bot)
        if reason:
            if len(rejected) < 200:
                rejected.append({"index": p.index, "reason": reason, "bot": p.bot[:240]})
            continue
        score, feats = gold_score(p.user, p.bot)
        if score >= 7.8:
            structure = classify_structure(p.bot)
            candidates.append(
                {
                    "index": p.index,
                    "ts": p.ts,
                    "score": round(score, 2),
                    "user": p.user,
                    "bot": p.bot,
                    "feats": feats,
                    "structure": structure,
                    "category": category_guess(p.user, p.bot),
                    "memorable_line": memorable_line(p.bot),
                    "why_it_works": why_it_works(p.bot, feats, structure),
                }
            )

    candidates.sort(key=lambda x: (-x["score"], len(x["bot"])))
    with CANDIDATES.open("w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with REJECTED_SAMPLE.open("w", encoding="utf-8") as f:
        for r in rejected:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"candidates >=7.8: {len(candidates)}")
    if candidates:
        print("top scores:", [c["score"] for c in candidates[:15]])
        print("top memorable:", candidates[0]["memorable_line"][:100])


if __name__ == "__main__":
    main()
