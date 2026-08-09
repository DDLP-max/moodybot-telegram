# -*- coding: utf-8 -*-
"""Editor (Gold) delivery: cut → name → prove once → stop → 🥃

Responsibility: Editor / Final Cut. Origin: Gold corpus rules.
Controls SURFACE delivery. Does not replace deep reasoning upstream.
Max one structural compression pass. Never thinks, never re-lenses, never invents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

GOLD_SHAPE_VERSION = "gold-shape-v1"

WHISKEY = "🥃"

SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-Z\"'“‘0-9*]|$)")
WORD_RE = re.compile(r"[A-Za-z']+")
LIKE_A = re.compile(r"\blike a\b|\bas if\b|\bas though\b", re.I)

# Abstract/conference-talk signals for last-line cash-out detection only.
# Not a replacement dictionary — quality pass drops or leaves; generation translates.
CONFERENCE_SIGNALS = re.compile(
    r"\b(ideology|universal claim|defection|dialectic|paradigm|"
    r"systemic(?:\s+mechanism)?|resentment economy|grievance economy|"
    r"collective grievance|epistemic|incentive structure|incentives?|"
    r"narrative contract|framework|meta-analysis|inconsistency|"
    r"fixed boundaries|asymmetric incentives|social validation|"
    r"status signalling|status signaling|resource extraction|"
    r"boundary violation|wherever .+ reward)\b",
    re.I,
)

STOCK_SOCIAL_MECHANISMS = re.compile(
    r"\b(rule[- ]shopping|grievance script|resentment economy|"
    r"loyalty program|collective (grievance|injury)|pick[- ]me enforcement|"
    r"shared injury story|defection from the)\b",
    re.I,
)

TASTE_DOMAIN_MARKERS = re.compile(
    r"\b(mcdonald|burger|fries|pizza|coffee|food|taste|restaurant|"
    r"delicious|sushi|steak|dessert|eat|dining|fries)\b",
    re.I,
)

PREFERENCE_DOMAIN_MARKERS = re.compile(
    r"\b(best|worst|overrated|underrated|favorite|familiar|consistency|"
    r"convenience|nostalgia|value|brand|iphone|tesla)\b",
    re.I,
)

ESSAY_NOUNS = CONFERENCE_SIGNALS  # shared detector; no hardcoded spoken swaps

CTA_TAIL = re.compile(
    r"(want me to|let me know if|say the word|tag @|mention @|"
    r"what do you think\??\s*$|agree\??\s*$|hit that|share the sting|"
    r"if you want examples|does that make sense)",
    re.I,
)

COSTUME_CLOSER = re.compile(
    r"(stay (dangerous|sharp|dangerous)|that'?s the (game|lesson|truth)|"
    r"the real lesson is|and that'?s why|let that sink in|"
    r"you'?ll (taste|hear) this (again )?when the room|"
    r"mic drop|chef'?s kiss)\s*[.!]?\s*$",
    re.I,
)

SPEAR_MARKERS = re.compile(
    r"\b(not .+[,.—-] it'?s|isn'?t .+[,.—-] it'?s|that'?s not|"
    r"doesn'?t .+[,.—-]|you'?re (describing|not)|"
    r"the (pressure|deal|point|tell|spell|filter) |"
    r"keeping the story|loyalty program|fear dressed|"
    r"changes the courtroom)\b",
    re.I,
)


@dataclass
class GoldShapeReport:
    selected_structure: str = "KNIFE"
    premise_relocated: bool = False
    dominant_mechanism_count: int = 1
    draft_word_count: int = 0
    final_word_count: int = 0
    quality_rewrite_triggered: bool = False
    quality_failures: List[str] = field(default_factory=list)
    spear_detected: bool = False
    whiskey_tail_present: bool = False
    spear_line: str = ""
    mechanism_mismatch: bool = False
    response_budget: str = "medium"


def _normalize_structure_name(structure: str) -> str:
    s = (structure or "KNIFE").upper()
    if s == "STORY":
        return "REFLECTION"
    if s not in {"SNAP", "KNIFE", "REFLECTION"}:
        return "KNIFE"
    return s


def _budget_soft_caps(budget: str) -> dict:
    """Soft length caps by depth. Density within room — not universal brevity."""
    b = (budget or "medium").lower()
    if b == "high":
        return {
            "SNAP": 90,
            "KNIFE": 260,
            "REFLECTION": 480,
            "knife_sentences": 10,
            "reflection_sentences": 18,
        }
    if b == "low":
        return {
            "SNAP": 70,
            "KNIFE": 110,
            "REFLECTION": 200,
            "knife_sentences": 5,
            "reflection_sentences": 8,
        }
    return {
        "SNAP": 70,
        "KNIFE": 140,
        "REFLECTION": 320,
        "knife_sentences": 7,
        "reflection_sentences": 12,
    }


SOCIAL_PROMPT_MARKERS = re.compile(
    r"\b(feminist|feminism|patriarchy|pick[- ]me|misogyn|ideology|woke|"
    r"privilege|oppression|gender|politics|culture war|grievance)\b",
    re.I,
)


def detect_mechanism_mismatch(user_message: str, draft: str) -> bool:
    """True when a stock social mechanism is applied to a non-social prompt.

    Log / diagnose only — editorial pass must not invent a better mechanism.
    """
    body = strip_whiskey(draft)
    if not STOCK_SOCIAL_MECHANISMS.search(body):
        return False
    um = user_message or ""
    if SOCIAL_PROMPT_MARKERS.search(um):
        return False
    if TASTE_DOMAIN_MARKERS.search(um) or PREFERENCE_DOMAIN_MARKERS.search(um):
        return True
    return False


def words(text: str) -> List[str]:
    return WORD_RE.findall(text or "")


def sentences(text: str) -> List[str]:
    body = strip_whiskey(text).strip()
    if not body:
        return []
    parts = [s.strip() for s in SENT_SPLIT.split(body) if s and s.strip()]
    return parts or [body]


def strip_whiskey(text: str) -> str:
    return re.sub(r"\s*🥃\s*", " ", text or "").strip()


def ensure_whiskey(text: str) -> str:
    body = strip_whiskey(text).rstrip()
    if not body:
        return WHISKEY
    return f"{body} {WHISKEY}"


def _is_conference_talk_sentence(sentence: str) -> bool:
    """True if a sentence sounds more like a white paper than a conversation.

    Short precise mechanism names (e.g. "Moral licensing.") are NOT conference talk —
    they are often the spear. Cash out packaging, not the cleanest name.
    """
    s = (sentence or "").strip()
    if not s:
        return False
    w = words(s)
    # Shortest accurate name for the mechanism — keep
    if len(w) <= 4 and not re.search(
        r"\b(wherever|insofar|whereby|incentives?|inconsistency|framework)\b",
        s,
        re.I,
    ):
        return False
    hits = len(CONFERENCE_SIGNALS.findall(s))
    if hits >= 2:
        return True
    if hits >= 1 and re.search(
        r"\b(wherever|insofar|whereby|hence|thus|respectively)\b",
        s,
        re.I,
    ):
        return True
    if len(w) >= 10:
        concrete = len(
            re.findall(
                r"\b(people|person|man|woman|cost|benefit|standard|rule|"
                r"pay|drop|grab|ignore|line|drink|door|story)\b",
                s,
                re.I,
            )
        )
        if hits >= 1 and concrete == 0:
            return True
    return False


def select_structure(
    user_message: str,
    draft: str,
    preferred: Optional[str] = None,
) -> str:
    """SNAP / KNIFE / REFLECTION — soft selection from length + contemplative cues.

    preferred comes from the Writing layer (plan.preferred_structure) — a hint,
    not a hard force. Short taste/SNAP-biased drafts stay SNAP.
    STORY is accepted as a legacy alias for REFLECTION.
    """
    wc = len(words(draft))
    ss = sentences(draft)
    paras = [p for p in (draft or "").split("\n") if p.strip()]
    preferred = _normalize_structure_name(preferred) if preferred else None
    contemplative = bool(
        re.search(
            r"\b(for (example|instance)|the time|last (week|night|year)|"
            r"she |he |they |when I |seasons?|years?|daenerys|proof|"
            r"sneaks up|whisper|years down|chase ends)\b",
            draft,
            re.I,
        )
    )
    wants_reflection = bool(
        re.search(
            r"\b(tell me (the )?story|walk me through|what happened|"
            r"get older|in (your|their) \d|purpose|legacy|mortality)\b",
            user_message,
            re.I,
        )
    )
    if preferred == "REFLECTION":
        return "REFLECTION"
    if wants_reflection or len(paras) >= 3 or (contemplative and (wc >= 120 or len(ss) >= 5)):
        return "REFLECTION"
    if preferred == "SNAP" and wc <= 70 and len(ss) <= 3:
        return "SNAP"
    if wc <= 45 and len(ss) <= 2:
        return "SNAP"
    if preferred == "KNIFE":
        return "KNIFE"
    if preferred == "SNAP" and wc <= 90:
        return "SNAP"
    return "KNIFE"


def _token_set(text: str) -> set:
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are",
        "was", "were", "be", "been", "that", "this", "it", "as", "with", "by",
        "from", "at", "they", "them", "their", "you", "your", "her", "his",
        "she", "he", "when", "who", "what", "why", "how", "not", "but",
    }
    return {w.lower() for w in words(text) if len(w) > 2 and w.lower() not in stop}


def _overlap_ratio(a: str, b: str) -> float:
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, min(len(sa), len(sb)))


def detect_spear(ss: List[str]) -> Tuple[bool, str, int]:
    """Return (found, line, index). Prefer punchy contrast; break ties toward later lines."""
    best_i, best_score, best = -1, -1.0, ""
    for i, s in enumerate(ss):
        n = len(words(s))
        if n < 4 or n > 28:
            continue
        score = 0.0
        if 6 <= n <= 18:
            score += 2
        if SPEAR_MARKERS.search(s):
            score += 3
        if re.search(r"\b(not|never|isn'?t|doesn'?t|that'?s|failed because|proof)\b", s, re.I):
            score += 1
        # Prefer payoff placement over throat-clearing openers
        score += i * 0.15
        if score > best_score:
            best_score, best_i, best = score, i, s
    if best_i >= 0 and best_score >= 2:
        return True, best, best_i
    if ss:
        for i in range(len(ss) - 1, -1, -1):
            if 5 <= len(words(ss[i])) <= 22:
                return True, ss[i], i
        return True, ss[-1], len(ss) - 1
    return False, "", -1


def premise_relocated(user: str, draft: str) -> bool:
    ss = sentences(draft)
    if not ss:
        return False
    first = ss[0]
    if re.search(
        r"^(that'?s not|you'?re (not|describing|confusing)|not everyone|"
        r"stop |the .+ isn'?t|pick me.? isn'?t|power doesn'?t|"
        r"you already know|there isn'?t)",
        first.strip(),
        re.I,
    ):
        return True
    # Low overlap between first sentence and user = relocation
    return _overlap_ratio(first, user) < 0.45


def count_like_metaphors(text: str) -> int:
    return len(LIKE_A.findall(text))


def evaluate_gold_shape(
    user_message: str,
    draft: str,
    structure: str,
    response_budget: str = "medium",
) -> List[str]:
    """Return list of quality failure codes.

    Length soft-caps scale with response_budget. High-budget development
    is not treated as overlong merely for exceeding Telegram-hot-take norms.
    """
    failures: List[str] = []
    body = strip_whiskey(draft)
    ss = sentences(body)
    wc = len(words(body))
    structure = _normalize_structure_name(structure)
    caps = _budget_soft_caps(response_budget)
    high = (response_budget or "").lower() == "high"
    reflection = structure == "REFLECTION"

    if not ss:
        failures.append("empty")
        return failures

    # Restatement: high overlap with user across early sentences
    restated = 0
    for s in ss[:4]:
        if _overlap_ratio(s, user_message) >= 0.62 and len(words(s)) >= 8:
            restated += 1
    if restated >= 2 or (
        restated >= 1 and len(ss) >= 4 and _overlap_ratio(body, user_message) >= 0.55
    ):
        failures.append("premise_restatement")

    # Multi-mechanism: many essay nouns OR many near-duplicate sentences
    essay_hits = len(ESSAY_NOUNS.findall(body))
    if essay_hits >= 3:
        failures.append("essay_diction")
    # High / REFLECTION may develop with more abstract nouns; require 3+
    essay_threshold = 3 if high or reflection else 2
    if essay_hits >= essay_threshold and structure in {"SNAP", "KNIFE"}:
        failures.append("multi_mechanism_essay")

    # Near-duplicate consecutive sentences
    dup_pairs = 0
    for i in range(len(ss) - 1):
        if _overlap_ratio(ss[i], ss[i + 1]) >= 0.7:
            dup_pairs += 1
    if dup_pairs >= 2 or (dup_pairs >= 1 and len(ss) >= 5):
        failures.append("thesis_repetition")

    spear_ok, spear, spear_i = detect_spear(ss)
    if not spear_ok:
        failures.append("no_spear")
    elif spear_i >= 0 and spear_i < len(ss) - 1:
        after = ss[spear_i + 1 :]
        # Early thesis + following proofs is normal KNIFE/REFLECTION — not drift.
        # Drift = trailing lines that mostly restate the spear without new content.
        if reflection or high:
            trailing = after[-2:] if len(after) > 3 else []
            if trailing and all(_overlap_ratio(a, spear) >= 0.55 for a in trailing):
                failures.append("post_payoff_drift")
        elif spear_i <= 1:
            restaty = sum(1 for a in after if _overlap_ratio(a, spear) >= 0.6)
            if restaty >= 2:
                failures.append("post_payoff_drift")
        elif len(after) >= 2:
            rest = sum(1 for a in after if _overlap_ratio(a, spear) >= 0.5)
            if rest >= 2:
                failures.append("post_payoff_drift")

    # REFLECTION: still kill metaphor perfume (old Moody failure mode)
    metaphor_limit = 3 if reflection or high else 2
    if count_like_metaphors(body) >= metaphor_limit:
        failures.append("stacked_metaphor")

    if CTA_TAIL.search(body) or COSTUME_CLOSER.search(body):
        failures.append("cta_or_costume_tail")

    # Abstract closer: last sentence is conference-talk (cash-out failure)
    if _is_conference_talk_sentence(ss[-1]):
        failures.append("abstract_closer")

    # Favorite-drawer social mechanism on a taste/preference prompt (route failure)
    if detect_mechanism_mismatch(user_message, body):
        failures.append("mechanism_mismatch")

    # Soft length by shape × depth (not rigid; not "always ~60 words")
    if structure == "SNAP" and wc > caps["SNAP"]:
        failures.append("snap_overlong")
    if structure == "KNIFE" and wc > caps["KNIFE"]:
        failures.append("knife_overlong")
    if structure == "KNIFE" and len(ss) > caps["knife_sentences"]:
        failures.append("knife_too_many_sentences")
    if structure == "REFLECTION" and wc > caps["REFLECTION"]:
        failures.append("reflection_overlong")
    if structure == "REFLECTION" and len(ss) > caps["reflection_sentences"]:
        failures.append("reflection_too_many_sentences")

    return failures


def _compress_once(
    user_message: str,
    draft: str,
    structure: str,
    failures: List[str],
    response_budget: str = "medium",
) -> str:
    """One structural compression rewrite. Keeps meaning; deletes drift.

    Compress within the allocated response_budget. Do not gut high-budget
    development — especially REFLECTION — down to a SNAP one-liner.
    """
    structure = _normalize_structure_name(structure)
    body = strip_whiskey(draft)
    ss = sentences(body)
    if not ss:
        return draft

    # Strip CTA / costume verbal tails from last sentence
    if ss:
        last = ss[-1]
        last = CTA_TAIL.sub("", last).strip()
        last = COSTUME_CLOSER.sub("", last).strip()
        # strip catchphrase before whiskey style endings
        last = re.sub(
            r"\s*(Stay (dangerous|sharp)\.?|That'?s the game\.?)\s*$",
            "",
            last,
            flags=re.I,
        ).strip()
        if last:
            ss[-1] = last
        else:
            ss = ss[:-1]

    if not ss:
        return body

    # Drop sentences that mostly restate the user
    if "premise_restatement" in failures or "thesis_repetition" in failures:
        kept: List[str] = []
        for s in ss:
            if _overlap_ratio(s, user_message) >= 0.65 and len(words(s)) >= 8:
                # keep if it's a sharp reframe despite overlap tokens
                if SPEAR_MARKERS.search(s) and len(words(s)) <= 20:
                    kept.append(s)
                continue
            kept.append(s)
        if kept:
            ss = kept

    # Drop near-duplicate consecutive sentences (keep stronger/shorter)
    if len(ss) >= 2:
        compact: List[str] = [ss[0]]
        for s in ss[1:]:
            prev = compact[-1]
            if _overlap_ratio(s, prev) >= 0.68:
                # keep the punchier one
                if len(words(s)) < len(words(prev)) and SPEAR_MARKERS.search(s):
                    compact[-1] = s
                continue
            compact.append(s)
        ss = compact

    # Stacked metaphor: if 2+ like-a, try to drop later metaphor sentences
    if count_like_metaphors(" ".join(ss)) >= 2:
        seen_meta = 0
        filtered = []
        for s in ss:
            m = count_like_metaphors(s)
            if m and seen_meta >= 1:
                continue
            if m:
                seen_meta += 1
            filtered.append(s)
        if filtered:
            ss = filtered

    structure = _normalize_structure_name(structure)
    # Post-payoff: only trim clear restatement tails — never gut REFLECTION / high-depth proofs
    spear_ok, spear, spear_i = detect_spear(ss)
    high = (response_budget or "").lower() == "high"
    reflection = structure == "REFLECTION"
    if (
        spear_ok
        and spear_i >= 0
        and "post_payoff_drift" in failures
        and structure in {"SNAP", "KNIFE"}
        and not high
        and not reflection
    ):
        # Keep through spear; drop only trailing restaty lines after last proof
        trimmed = ss[: spear_i + 1]
        for s in ss[spear_i + 1 :]:
            if _overlap_ratio(s, spear) >= 0.6:
                continue
            trimmed.append(s)
            break  # at most one non-restating proof after spear
        if trimmed:
            ss = trimmed

    # Soft caps only when overlong failure present — scaled by depth; never tweet-gut REFLECTION
    caps = _budget_soft_caps(response_budget)
    soft_cap = {
        "SNAP": max(40, caps["SNAP"] - 15),
        "KNIFE": max(80, caps["KNIFE"] - 20),
        "REFLECTION": caps["REFLECTION"],
    }.get(structure, caps["KNIFE"])
    wc = len(words(" ".join(ss)))
    min_sentences_before_gut = 12 if reflection else (7 if high else 4)
    overlong_flags = (
        "knife_overlong",
        "snap_overlong",
        "reflection_overlong",
        "thesis_repetition",
    )
    if (
        structure in {"SNAP", "KNIFE", "REFLECTION"}
        and wc > soft_cap
        and len(ss) > min_sentences_before_gut
        and any(f in failures for f in overlong_flags)
    ):
        spear_ok, spear, spear_i = detect_spear(ss)
        if reflection or high:
            keep_idx = {0, 1, 2, 3}
            if spear_i >= 0:
                keep_idx.add(spear_i)
                if spear_i > 0:
                    keep_idx.add(spear_i - 1)
                if spear_i + 1 < len(ss):
                    keep_idx.add(spear_i + 1)
            # Keep early contemplative beats for REFLECTION
            if reflection:
                for i in range(min(6, len(ss))):
                    keep_idx.add(i)
            ss = [s for i, s in enumerate(ss) if i in keep_idx]
        else:
            keep_idx = {0}
            if spear_i >= 0:
                keep_idx.add(spear_i)
            if len(ss) > 1:
                keep_idx.add(min(1, len(ss) - 1))
            if spear_i >= 2:
                keep_idx.add(spear_i - 1)
            ss = [s for i, s in enumerate(ss) if i in keep_idx]

    # Essay diction: light signal only — no growing replacement dictionary.
    # Generation owns Abstract→Spoken translation; pass deletes conference closers.
    text = " ".join(ss)

    # Cash out the last line (editorial): if the closer is conference-talk and
    # an earlier spoken sentence already carries the insight, drop the closer.
    # Principle: do not invent a spoken paraphrase here — only remove white-paper tails.
    if "abstract_closer" in failures:
        ss2 = sentences(text) if text else ss
        if len(ss2) >= 2 and _is_conference_talk_sentence(ss2[-1]):
            prior = ss2[:-1]
            # Keep if prior already has concrete / spear content
            if any(
                not _is_conference_talk_sentence(p) and len(words(p)) >= 6 for p in prior
            ):
                text = " ".join(prior).strip()

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text


def apply_gold_shape_pass(
    user_message: str,
    draft: str,
    *,
    structure: Optional[str] = None,
    preferred_structure: Optional[str] = None,
    response_budget: Optional[str] = None,
) -> Tuple[str, GoldShapeReport]:
    """
    draft → evaluate → at most one compression → ensure whiskey later in surface.
    Returns body WITHOUT requiring whiskey (surface_render adds it).
    Editing layer only — never invents a lens or mechanism.
    Lens persistence: must not select or change the interpretive lens.
    Compresses within response_budget — density, not universal brevity.
    """
    budget = (response_budget or "medium").lower()
    preferred_norm = (
        _normalize_structure_name(preferred_structure) if preferred_structure else None
    )
    structure = _normalize_structure_name(
        structure
        or select_structure(user_message, draft, preferred=preferred_structure)
    )
    # Honor routed shape; do not tweet-collapse high-depth or REFLECTION drafts
    if preferred_norm == "REFLECTION":
        structure = "REFLECTION"
    elif budget == "high" and structure == "SNAP" and preferred_norm != "SNAP":
        structure = preferred_norm if preferred_norm in {"KNIFE", "REFLECTION"} else "KNIFE"
    body = strip_whiskey(draft)
    report = GoldShapeReport(
        selected_structure=structure,
        draft_word_count=len(words(body)),
        premise_relocated=premise_relocated(user_message, body),
        response_budget=budget,
    )

    failures = evaluate_gold_shape(user_message, body, structure, response_budget=budget)
    report.quality_failures = list(failures)
    report.mechanism_mismatch = "mechanism_mismatch" in failures

    # Failures that warrant rewrite
    # mechanism_mismatch is diagnostic only — do not invent a better insight here.
    rewrite_triggers = {
        "premise_restatement",
        "thesis_repetition",
        "post_payoff_drift",
        "cta_or_costume_tail",
        "stacked_metaphor",
        "multi_mechanism_essay",
        "knife_overlong",
        "snap_overlong",
        "knife_too_many_sentences",
        "reflection_overlong",
        "reflection_too_many_sentences",
        "essay_diction",
        "abstract_closer",
    }
    if any(f in rewrite_triggers for f in failures):
        compressed = _compress_once(
            user_message, body, structure, failures, response_budget=budget
        )
        if strip_whiskey(compressed) and _token_set(compressed):
            report.quality_rewrite_triggered = True
            body = strip_whiskey(compressed)
            # re-evaluate lightly (no second rewrite)
            report.quality_failures = evaluate_gold_shape(
                user_message, body, structure, response_budget=budget
            )
            report.mechanism_mismatch = "mechanism_mismatch" in report.quality_failures

    spear_ok, spear, _ = detect_spear(sentences(body))
    report.spear_detected = spear_ok
    report.spear_line = spear[:240]
    report.dominant_mechanism_count = 1 if len(ESSAY_NOUNS.findall(body)) <= 1 else min(
        3, len(set(m.lower() for m in ESSAY_NOUNS.findall(body)))
    )
    report.final_word_count = len(words(body))
    report.premise_relocated = premise_relocated(user_message, body)
    return body, report


def gold_shape_diagnostics(report: GoldShapeReport) -> dict:
    return {
        "gold_shape_version": GOLD_SHAPE_VERSION,
        "selected_structure": report.selected_structure,
        "premise_relocated": str(report.premise_relocated).lower(),
        "dominant_mechanism_count": str(report.dominant_mechanism_count),
        "draft_word_count": str(report.draft_word_count),
        "final_word_count": str(report.final_word_count),
        "quality_rewrite_triggered": str(report.quality_rewrite_triggered).lower(),
        "quality_failures": ",".join(report.quality_failures) if report.quality_failures else "none",
        "spear_detected": str(report.spear_detected).lower(),
        "spear_line": (report.spear_line or "")[:240],
        "whiskey_tail_present": str(report.whiskey_tail_present).lower(),
        "mechanism_mismatch": str(report.mechanism_mismatch).lower(),
        "response_budget": report.response_budget or "medium",
    }
