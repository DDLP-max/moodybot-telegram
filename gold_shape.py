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
    r"delicious|sushi|steak|dessert|eat|dining|fries|"
    r"show|series|movie|film|tv|television|netflix|hbo|binge|"
    r"breaking bad|better call saul|episode|season)\b",
    re.I,
)

PREFERENCE_DOMAIN_MARKERS = re.compile(
    r"\b(best|worst|overrated|underrated|favorite|familiar|consistency|"
    r"convenience|nostalgia|value|brand|iphone|tesla|compare|ever)\b",
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
    routing_structure: str = ""
    generation_recommendation: str = ""
    structure_override: bool = False
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
    s = (structure or "KNIFE").strip().upper().replace("_", " ")
    if s == "STORY":
        return "REFLECTION"
    if s in {"EXTENDED KNIFE", "EXTENDEDKNIFE"}:
        return "KNIFE"
    if s not in {"SNAP", "KNIFE", "REFLECTION"}:
        return "KNIFE"
    return s


def writing_shape_label(structure: str, response_budget: str = "medium") -> str:
    """Display label: high × KNIFE → Extended KNIFE (Depth × Shape product name)."""
    s = _normalize_structure_name(structure)
    if s == "KNIFE" and (response_budget or "").lower() == "high":
        return "Extended KNIFE"
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


def paragraphs(text: str) -> List[str]:
    """Blank-line separated semantic units (not visual spacing)."""
    body = strip_whiskey(text or "").strip()
    if not body:
        return []
    return [p.strip() for p in re.split(r"\n\s*\n+", body) if p.strip()]


def paragraph_count(text: str) -> int:
    """Blank-line paragraph units; whiskey ignored."""
    return len(paragraphs(text))


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
    """Recommend SNAP / KNIFE / REFLECTION from draft cues.

    Recommendation only — routing owns the structure. Editor must not mute
    preferred_structure. Multi-paragraph drafts are normal for Extended KNIFE;
    paragraph count alone must never promote KNIFE → REFLECTION.
    """
    wc = len(words(draft))
    ss = sentences(draft)
    preferred = _normalize_structure_name(preferred) if preferred else None
    contemplative = bool(
        re.search(
            r"\b(for (example|instance)|the time|last (week|night|year)|"
            r"when I |seasons?|sneaks up|whisper|years down|chase ends|"
            r"get older|purpose|legacy|mortality)\b",
            draft,
            re.I,
        )
    )
    wants_reflection = bool(
        re.search(
            r"\b(tell me (the )?story|walk me through|what happened|"
            r"get older|in (your|their) \d|purpose|legacy|mortality|"
            r"grief|forgive|forgiveness)\b",
            user_message,
            re.I,
        )
    )
    # Soft recommendation (caller may ignore when routing locked a shape)
    if wants_reflection:
        return "REFLECTION"
    if contemplative and (wc >= 160 or len(ss) >= 7):
        return "REFLECTION"
    if preferred == "SNAP" and wc <= 70 and len(ss) <= 3:
        return "SNAP"
    if wc <= 45 and len(ss) <= 2:
        return "SNAP"
    if preferred in {"KNIFE", "REFLECTION", "SNAP"}:
        return preferred
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

    # Prompt has the insight; response only abridges it — zero new value
    try:
        from discovery_craft import (
            lens_drift,
            mechanism_drift,
            paraphrase_collapse,
            parroting,
            psychologizing,
            restates_runway,
            unsupported_depth,
            overperformance,
            rhetorical_explained,
            missed_comic_handoff,
            insight_after_payoff,
            sidesteps_forced_choice,
            reverses_premise_guard,
            uninvited_corrective_analysis,
        )
        from capability_detection import detect_comic_premise

        if paraphrase_collapse(user_message, body):
            failures.append("paraphrase_collapse")
        if mechanism_drift(user_message, body):
            failures.append("mechanism_drift")
        if lens_drift(user_message, body):
            failures.append("lens_drift")
        comic_on = bool(detect_comic_premise(user_message).active)
        if parroting(user_message, body):
            failures.append("parroting")
        if psychologizing(user_message, body, comic=comic_on):
            failures.append("psychologizing")
        if unsupported_depth(user_message, body, comic=comic_on):
            failures.append("unsupported_depth")
        if restates_runway(user_message, body):
            failures.append("runway_restatement")
        if overperformance(user_message, body):
            failures.append("overperformance")
        if rhetorical_explained(user_message, body):
            failures.append("rhetorical_explained")
        if missed_comic_handoff(user_message, body):
            failures.append("missed_handoff")
        if insight_after_payoff(user_message, body):
            failures.append("insight_after_payoff")
        if sidesteps_forced_choice(user_message, body):
            failures.append("sidestep_forced_choice")
        if reverses_premise_guard(user_message, body):
            failures.append("premise_reversal")
        if uninvited_corrective_analysis(user_message, body):
            failures.append("corrective_analysis")
    except Exception:
        pass

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

    # Progression: paragraphs that only reinforce an earlier one (not visual spacing)
    paras = paragraphs(body)
    if reflection or high:
        restaty_paras = 0
        for i in range(1, len(paras)):
            if len(words(paras[i])) < 12:
                continue
            if any(_overlap_ratio(paras[i], prev) >= 0.48 for prev in paras[:i]):
                restaty_paras += 1
        if restaty_paras >= 1:
            failures.append("paragraph_restatement")
        # Single-block over-confirm: many sentences after proof that restate early lines
        if len(ss) >= 5:
            head = " ".join(ss[:2])
            confirm = sum(
                1
                for s in ss[2:]
                if _overlap_ratio(s, head) >= 0.45 and len(words(s)) >= 8
            )
            if confirm >= 2:
                failures.append("over_confirming")

    return failures


def _strip_tail_noise(sentence: str) -> str:
    last = CTA_TAIL.sub("", sentence).strip()
    last = COSTUME_CLOSER.sub("", last).strip()
    last = re.sub(
        r"\s*(Stay (dangerous|sharp)\.?|That'?s the game\.?)\s*$",
        "",
        last,
        flags=re.I,
    ).strip()
    return last


def _drop_over_confirming_sentences(
    ss: List[str],
    *,
    protect: bool = False,
) -> List[str]:
    """Keep forward motion — delete lines that only restate earlier proof.

    Discovery sentences are protected when protect=True.
    """
    if len(ss) < 3:
        return ss
    protected: set = set()
    if protect:
        try:
            from discovery_craft import protected_discovery_indices

            protected = protected_discovery_indices(ss)
        except Exception:
            protected = set()
    kept: List[str] = [ss[0]]
    for i, s in enumerate(ss[1:], start=1):
        if i in protected:
            kept.append(s)
            continue
        if len(words(s)) >= 8 and any(_overlap_ratio(s, k) >= 0.52 for k in kept):
            if SPEAR_MARKERS.search(s) and len(words(s)) <= 18:
                kept.append(s)
            continue
        kept.append(s)
    return kept if kept else ss


def _drop_premise_echoes(ss: List[str], user_message: str) -> List[str]:
    """Drop user-echo sentences — never delete discovery lines."""
    try:
        from discovery_craft import looks_like_discovery
    except Exception:

        def looks_like_discovery(_s: str) -> bool:
            return False

    kept: List[str] = []
    for s in ss:
        if looks_like_discovery(s):
            kept.append(s)
            continue
        if _overlap_ratio(s, user_message) >= 0.65 and len(words(s)) >= 8:
            if SPEAR_MARKERS.search(s) and len(words(s)) <= 20:
                kept.append(s)
            continue
        kept.append(s)
    return kept if kept else ss


def _compress_paragraph_units(
    user_message: str,
    paras: List[str],
    failures: List[str],
) -> List[str]:
    """Editor on paragraph beats: semantic units, not visual spacing. Progression only."""
    cleaned: List[str] = []
    for p in paras:
        ss = sentences(p)
        if not ss:
            continue
        ss[-1] = _strip_tail_noise(ss[-1]) or ss[-1]
        if not ss[-1]:
            ss = ss[:-1]
        if not ss:
            continue
        # Within-paragraph sentence restatement
        compact: List[str] = [ss[0]]
        protected = set()
        try:
            from discovery_craft import protected_discovery_indices

            protected = protected_discovery_indices(ss)
        except Exception:
            protected = set()
        for i, s in enumerate(ss[1:], start=1):
            if i in protected:
                compact.append(s)
                continue
            if _overlap_ratio(s, compact[-1]) >= 0.68:
                continue
            compact.append(s)
        if "over_confirming" in failures or "paragraph_restatement" in failures:
            compact = _drop_over_confirming_sentences(compact, protect=True)
        if "premise_restatement" in failures:
            compact = _drop_premise_echoes(compact, user_message)
        para = " ".join(compact).strip()
        para = re.sub(r"[ \t]{2,}", " ", para)
        if para:
            cleaned.append(para)

    if len(cleaned) < 2:
        return cleaned

    # Drop paragraphs that only restate a previous one ("and then?" → same thing)
    out: List[str] = [cleaned[0]]
    for p in cleaned[1:]:
        if any(_overlap_ratio(p, prev) >= 0.48 for prev in out) and len(words(p)) >= 12:
            continue
        out.append(p)
    return out if out else cleaned


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
    Preserve paragraph cadence for REFLECTION / Extended KNIFE.
    """
    structure = _normalize_structure_name(structure)
    body = strip_whiskey(draft)
    high = (response_budget or "").lower() == "high"
    reflection = structure == "REFLECTION"
    keep_paragraphs = reflection or high
    paras = paragraphs(body)

    # Multi-paragraph path — cadence is part of the writing
    if keep_paragraphs and len(paras) >= 2:
        out_paras = _compress_paragraph_units(user_message, paras, failures)
        if "abstract_closer" in failures and out_paras:
            last_ss = sentences(out_paras[-1])
            if len(last_ss) >= 1 and _is_conference_talk_sentence(last_ss[-1]):
                if len(last_ss) >= 2:
                    out_paras[-1] = " ".join(last_ss[:-1]).strip()
                elif len(out_paras) >= 2 and any(
                    not _is_conference_talk_sentence(s)
                    for s in sentences(out_paras[-2])
                ):
                    out_paras = out_paras[:-1]
        text = "\n\n".join(p for p in out_paras if p)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    ss = sentences(body)
    if not ss:
        return draft

    # Strip CTA / costume verbal tails from last sentence
    ss[-1] = _strip_tail_noise(ss[-1])
    if not ss[-1]:
        ss = ss[:-1]
    if not ss:
        return body

    # Drop sentences that mostly restate the user — never delete discoveries
    if "premise_restatement" in failures or "thesis_repetition" in failures:
        ss = _drop_premise_echoes(ss, user_message)

    # Drop near-duplicate consecutive sentences (keep stronger/shorter)
    if len(ss) >= 2:
        try:
            from discovery_craft import protected_discovery_indices

            protected = protected_discovery_indices(ss)
        except Exception:
            protected = set()
        compact: List[str] = [ss[0]]
        for i, s in enumerate(ss[1:], start=1):
            if i in protected:
                compact.append(s)
                continue
            prev = compact[-1]
            if _overlap_ratio(s, prev) >= 0.68:
                if len(words(s)) < len(words(prev)) and SPEAR_MARKERS.search(s):
                    compact[-1] = s
                continue
            compact.append(s)
        ss = compact

    if "over_confirming" in failures or (keep_paragraphs and len(ss) >= 5):
        ss = _drop_over_confirming_sentences(ss, protect=True)

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

    # Post-payoff: only trim clear restatement tails — never gut REFLECTION / high-depth proofs
    spear_ok, spear, spear_i = detect_spear(ss)
    if (
        spear_ok
        and spear_i >= 0
        and "post_payoff_drift" in failures
        and structure in {"SNAP", "KNIFE"}
        and not high
        and not reflection
    ):
        trimmed = ss[: spear_i + 1]
        for s in ss[spear_i + 1 :]:
            if _overlap_ratio(s, spear) >= 0.6:
                continue
            trimmed.append(s)
            break
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
        "over_confirming",
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
            if reflection:
                for i in range(min(6, len(ss))):
                    keep_idx.add(i)
            ss = [s for i, s in enumerate(ss) if i in keep_idx]
        else:
            try:
                from discovery_craft import protected_discovery_indices

                protect_idx = protected_discovery_indices(ss)
            except Exception:
                protect_idx = set()
            keep_idx = {0} | protect_idx
            if spear_i >= 0:
                keep_idx.add(spear_i)
            if len(ss) > 1:
                keep_idx.add(min(1, len(ss) - 1))
            if spear_i >= 2:
                keep_idx.add(spear_i - 1)
            ss = [s for i, s in enumerate(ss) if i in keep_idx]

    text = " ".join(ss)

    if "abstract_closer" in failures:
        ss2 = sentences(text) if text else ss
        if len(ss2) >= 2 and _is_conference_talk_sentence(ss2[-1]):
            prior = ss2[:-1]
            if any(
                not _is_conference_talk_sentence(p) and len(words(p)) >= 6 for p in prior
            ):
                text = " ".join(prior).strip()

    # SNAP / medium KNIFE: single block OK. High / REFLECTION: never invent flatten of cadence.
    if keep_paragraphs:
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        text = re.sub(r"[ \t]+([,.!?;:])", r"\1", text)
        return text
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
    explicit = _normalize_structure_name(structure) if structure else None
    recommendation = select_structure(
        user_message, draft, preferred=preferred_structure
    )
    # Structure persistence: routing owns the shape. Recommendation is log-only.
    if preferred_norm:
        editor_structure = preferred_norm
        override = False
    elif explicit:
        editor_structure = explicit
        override = False
    else:
        editor_structure = recommendation
        override = False
    structure = editor_structure
    routing_label = writing_shape_label(preferred_norm or structure, budget)
    selected_label = writing_shape_label(structure, budget)
    recommendation_label = writing_shape_label(recommendation, budget)
    body = strip_whiskey(draft)
    report = GoldShapeReport(
        selected_structure=selected_label,
        routing_structure=routing_label,
        generation_recommendation=recommendation_label,
        structure_override=override,
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
        "paragraph_restatement",
        "over_confirming",
        "essay_diction",
        "abstract_closer",
    }
    if any(f in rewrite_triggers for f in failures):
        compressed = _compress_once(
            user_message, body, structure, failures, response_budget=budget
        )
        if strip_whiskey(compressed) and _token_set(compressed):
            # Never accept a compression that deletes the discovery / worsens paraphrase collapse
            try:
                from discovery_craft import paraphrase_collapse

                before = paraphrase_collapse(user_message, body)
                after = paraphrase_collapse(user_message, compressed)
                if after and not before:
                    compressed = body
                elif after and before:
                    # Prefer the version that still contains a discovery-shaped line
                    from discovery_craft import discovery_sentences

                    if discovery_sentences(body) and not discovery_sentences(compressed):
                        compressed = body
            except Exception:
                pass
            if strip_whiskey(compressed) != strip_whiskey(body):
                report.quality_rewrite_triggered = True
                body = strip_whiskey(compressed)
                report.quality_failures = evaluate_gold_shape(
                    user_message, body, structure, response_budget=budget
                )
                report.mechanism_mismatch = "mechanism_mismatch" in report.quality_failures
            else:
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
        "routing_structure": report.routing_structure or report.selected_structure,
        "generation_recommendation": report.generation_recommendation or "",
        "structure_override": str(report.structure_override).lower(),
        "structure_persistence": "routing_only",
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
