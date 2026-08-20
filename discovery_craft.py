# -*- coding: utf-8 -*-
"""Discovery protection — shared by Editor (Gold) and Inspector.

Invariant:
  Editor may remove bridges before discoveries.
  Discovery sentences are protected.

Paraphrase collapse:
  The response preserves the prompt's conclusion instead of contributing a new one.
  Routing question: Has the author already done Moody's job?
  If yes — rotate, deepen, challenge, reveal adjacent. Never summarize.
  Prison-cell standard: don't argue on the prompt's terms; escape the frame.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set


def _words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text or "")


def _sentences(text: str) -> List[str]:
    body = re.sub(r"\s*🥃\s*", " ", text or "").strip()
    if not body:
        return []
    parts = re.split(r"(?<=[.!?])\s+", body.replace("\n\n", " ").replace("\n", " "))
    return [s.strip() for s in parts if s and s.strip()]


def _token_set(text: str) -> set:
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are",
        "was", "were", "be", "been", "that", "this", "it", "as", "with", "by",
        "from", "at", "they", "them", "their", "you", "your", "her", "his",
        "she", "he", "when", "who", "what", "why", "how", "not", "but",
    }
    return {w.lower() for w in _words(text) if len(w) > 2 and w.lower() not in stop}


def overlap_ratio(a: str, b: str) -> float:
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, min(len(sa), len(sb)))


# Stealable / mechanism-naming shapes (prompt or draft)
_DISCOVERY_SHAPE = re.compile(
    r"\b(exit that didn'?t|bad guy|giveaway|autobiographical|"
    r"comes with a warranty|isn'?t perfection|uncertainty that comes|"
    r"without carrying the guilt|memory has a new job|"
    r"rewrite(?:s|ing)? (?:it|the ending|the story) for|"
    r"preserve the self|softer story)\b|"
    r"^(every |nobody wants |the fantasy |people rarely |most breakups |"
    r"the story changes |the line about )\b",
    re.I,
)

# Soft bookends that often survive bad compression
_BOOKEND = re.compile(
    r"^(sure\.?|yeah\.?|right\.?|exactly\.?|ok\.?|okay\.?)$|"
    r"\blet (her|him|them) have\b|"
    r"\byou wanted forever\b",
    re.I,
)


def looks_like_discovery(sentence: str) -> bool:
    s = (sentence or "").strip()
    n = len(_words(s))
    if n < 6 or n > 40:
        return False
    if _BOOKEND.search(s) and n <= 12:
        return False
    if _DISCOVERY_SHAPE.search(s):
        # "softer story" alone is spear/bookend — need more meat
        if re.search(r"\bsofter story\b", s, re.I) and n < 12:
            return False
        return True
    # Contrast mechanism inside one sentence (wanted X / wanted Y + cost)
    if (
        re.search(r"\bwanted\b.+\bwanted\b", s, re.I)
        and re.search(r"\b(without|exit|guilt|bad|story|self)\b", s, re.I)
        and n >= 10
    ):
        return True
    return False


def prompt_has_discovery(user_message: str) -> bool:
    return any(looks_like_discovery(s) for s in _sentences(user_message or ""))


def discovery_sentences(text: str) -> List[str]:
    return [s for s in _sentences(text or "") if looks_like_discovery(s)]


def response_adds_discovery(user_message: str, response: str) -> bool:
    """True if response lands a discovery that isn't mostly the user's own line."""
    user = user_message or ""
    for s in _sentences(response or ""):
        if not looks_like_discovery(s):
            continue
        if overlap_ratio(s, user) < 0.55:
            return True
    return False


def paraphrase_collapse(user_message: str, response: str) -> bool:
    """
    True when the response preserves the prompt's conclusion instead of
    contributing a new one (author already did Moody's job; Moody stayed
    inside their frame and abridged it).
    """
    user = user_message or ""
    resp = response or ""
    if not prompt_has_discovery(user):
        return False
    if response_adds_discovery(user, resp):
        return False
    if overlap_ratio(resp, user) >= 0.48:
        return True
    ss = _sentences(resp)
    if ss and all((_BOOKEND.search(s) or len(_words(s)) <= 6) for s in ss):
        return True
    prompt_disc = discovery_sentences(user)
    if prompt_disc and ss and len(_words(resp)) <= 45:
        kept_disc = any(overlap_ratio(s, prompt_disc[0]) >= 0.55 for s in ss)
        if not kept_disc and any(_BOOKEND.search(s) for s in ss):
            return True
    return False


# Drawer shortcuts — sometimes brilliant, often favorite-mechanism inserts
_DRAWER_SHORTCUT = re.compile(
    r"\bwhat they actually want\b|"
    r"\bwhat (he|she|people) actually (want|wanted|need|needed)\b|"
    r"\bthe real (problem|reason|issue|engine|question|fear) is\b|"
    r"\bit isn'?t (really )?about\b|"
    r"\bthat'?s not (really )?about\b|"
    r"\bthe (real )?problem isn'?t\b",
    re.I,
)

# EI favorite drawers that steal the topic
_REJECTION_FEAR_DRAWER = re.compile(
    r"\bescape hatch\b|\bbeing refused\b|\bturned down\b|"
    r"\bfear of rejection\b|\brisk being refused\b|"
    r"\bvisibility means\b|\bcan be (turned down|laughed at|ignored)\b",
    re.I,
)

_EFFORT_TOPIC = re.compile(
    r"\beffort\b|\bmake a plan\b|\bfollow through\b|\bexecut|"
    r"\bthoughtful\b|\battractive quality\b",
    re.I,
)

_INVENTED_SOCIOLOGY = re.compile(
    r"\bsame people (complaining|who complain)\b|"
    r"\balso the ones who never\b|"
    r"\beveryone (is|who'?s) (single|childless)\b",  # only if response invents blame not in prompt
    re.I,
)


def drawer_shortcut_present(response: str) -> bool:
    return bool(_DRAWER_SHORTCUT.search(response or ""))


def mechanism_drift(user_message: str, response: str) -> bool:
    """
    True when the response introduces a plausible emotional mechanism that
    isn't the strongest fit for THIS prompt (favorite-drawer insert).

    Not architecture — lens refinement. Not always wrong — often just not best.
    """
    user = user_message or ""
    resp = response or ""
    if not resp.strip():
        return False

    # Effort / evidence prompt → rejection-fear pivot
    if _EFFORT_TOPIC.search(user) and _REJECTION_FEAR_DRAWER.search(resp):
        # Drift if effort is no longer the spine, or drawer shortcut opens the pivot
        effort_in_resp = bool(re.search(r"\beffort\b", resp, re.I))
        if _DRAWER_SHORTCUT.search(resp) or not effort_in_resp:
            return True
        # "what they actually want" under an effort prompt = classic EI steal
        if re.search(r"\bwhat they actually want\b", resp, re.I):
            return True

    # Invented sociology not grounded in the prompt
    if _INVENTED_SOCIOLOGY.search(resp) and not _INVENTED_SOCIOLOGY.search(user):
        # Only count as drift when paired with a drawer shortcut or topic steal
        if _DRAWER_SHORTCUT.search(resp) or _REJECTION_FEAR_DRAWER.search(resp):
            return True

    return False


def mechanism_drift_examples(user_message: str) -> List[str]:
    """PASS lines grounded in common drifted prompts."""
    if _EFFORT_TOPIC.search(user_message or ""):
        return [
            "✓ Effort isn't attractive because it's romantic. It's attractive because it's evidence.",
            "✓ Effort is attractive because it answers a question words never can: "
            "are you willing to inconvenience yourself for me?",
            "✓ Attention is cheap. Effort isn't. That's why people trust one more than the other.",
        ]
    return [
        "✓ Stay on the prompt's strongest mechanism — not EI's favorite drawer.",
        "✓ That's like saying a prison cell is just a room.",
    ]


def protected_discovery_indices(draft_sentences: List[str]) -> Set[int]:
    """Indices Editor must not delete to satisfy brevity."""
    return {i for i, s in enumerate(draft_sentences) if looks_like_discovery(s)}


# --- Object-first vs subject-first (lens stance) ---------------------------------

_ENTERTAINMENT_OBJECT = re.compile(
    r"\b(show|series|movie|film|tv|television|netflix|hbo|"
    r"breaking bad|better call saul|binge|episode|season|"
    r"mcdonald|burger|restaurant|food|taste)\b",
    re.I,
)

_VIEWER_PSYCH = re.compile(
    r"\byou don'?t\b|"
    r"\byou'?re actually\b|"
    r"\bwhat you'?re really\b|"
    r"\bprotect yourself from\b|"
    r"\byour best days\b|"
    r"\bbest days of (watching|eating|living)\b|"
    r"\balready over\b|"
    r"\bfear that you'?ll never\b|"
    r"\bpossibility that your\b|"
    r"\byou protect yourself\b",
    re.I,
)

_OBJECT_CRAFT = re.compile(
    r"\b(craft|standard|respect(?:ed|s)? the audience|competence|"
    r"raised the (bar|price)|impressing you|meal|restaurant|"
    r"earned|wrote|filmed|scene|writing|acting)\b",
    re.I,
)

# Early-noun lexicon (heuristic — not absolute)
_OBJECT_EARLY_NOUNS = re.compile(
    r"\b(show|shows|food|meal|craft|city|restaurant|music|television|"
    r"film|movie|series|storytelling|writing|audience|burger|coffee|"
    r"taste|episode|kitchen|chef|cuisine|menu|espresso|"
    r"breaking bad|better call saul)\b",
    re.I,
)
_SUBJECT_EARLY = re.compile(
    r"\b(you|yourself|your fear|your insecurity|your best|"
    r"protect yourself|you'?re actually|you don'?t)\b",
    re.I,
)
_SUBJECT_OPEN = re.compile(
    r"^\s*(you|you'?re|you don'?t|your |yourself)\b",
    re.I,
)
_EI_UNEXPECTED_OBJECT = re.compile(
    r"\b(cinematography|mise[- ]en[- ]sc[eè]ne|film editing|screenwriting)\b",
    re.I,
)
_EI_EXPECTED = re.compile(
    r"\b(you|they|people|relationship|boundary|fear|she|he|her|him)\b",
    re.I,
)


def _first_sentence(text: str) -> str:
    parts = _sentences(text)
    return parts[0] if parts else ""


def object_domain(
    user_message: str = "",
    *,
    claim_domain: str = "",
    lens: str = "",
) -> bool:
    """Taste / travel / craft — Bourdain starts with the object."""
    return (
        claim_domain in {"taste_preference", "cultural_insight", "travel"}
        or (lens or "") == "Bourdain"
        or bool(_ENTERTAINMENT_OBJECT.search(user_message or ""))
    )


def early_noun_report(
    user_message: str,
    response: str,
    *,
    claim_domain: str = "",
    lens: str = "",
) -> dict:
    """
    Lens-first noun test (heuristic).

    Bourdain / object domain: early nouns should be the work (show, food, craft…).
    Unexpected early subject spine: you / yourself / your fear.

    EI: expected you/they/people/fear. Unexpected film-craft jargon as the spine.
    """
    first = _first_sentence(response)
    lens_n = (lens or "").strip()
    report = {
        "ok": True,
        "first_sentence": first,
        "stance": "",
        "direction": "",
        "expected_hits": [],
        "unexpected_hits": [],
        "why": "",
    }
    if not first:
        return report

    if object_domain(user_message, claim_domain=claim_domain, lens=lens_n):
        report["stance"] = "object-first"
        obj_hits = _OBJECT_EARLY_NOUNS.findall(first)
        sub_hits = _SUBJECT_EARLY.findall(first)
        report["expected_hits"] = obj_hits
        report["unexpected_hits"] = sub_hits
        subject_open = bool(_SUBJECT_OPEN.search(first))
        psych_frame = bool(
            _VIEWER_PSYCH.search(first)
            or re.search(r"\bprotect (yourself|Breaking|the)\b", first, re.I)
        )
        sensory_ok = bool(
            re.search(r"\b(taste|tastes|meal|food|smell|kitchen|restaurant)\b", first, re.I)
        )
        # Invariant: don't open on you/yourself/fear. "You already know… taste like" is ok.
        if subject_open and (psych_frame or (not obj_hits and not sensory_ok)):
            report["ok"] = False
            report["direction"] = "Object → Subject"
            report["why"] = (
                "object-first lens — early reply opens on you/yourself/fear "
                "instead of the work (show/food/craft/city)"
            )
        elif subject_open and psych_frame:
            report["ok"] = False
            report["direction"] = "Object → Subject"
            report["why"] = (
                "object-first lens — subject-open psych frame "
                "(you don't protect… / your fear) even if the object is named"
            )
        return report

    if lens_n in {"Emotional Intelligence", "Hank Moody"}:
        report["stance"] = "subject-first"
        report["expected_hits"] = _EI_EXPECTED.findall(first)
        bad = _EI_UNEXPECTED_OBJECT.findall(first)
        report["unexpected_hits"] = bad
        if bad and not _EI_EXPECTED.search(first):
            report["ok"] = False
            report["direction"] = "Subject → Object"
            report["why"] = (
                "subject-first lens — early reply opens on film-craft jargon "
                "instead of people/feeling/boundary"
            )
        return report

    return report


def lens_drift(
    user_message: str,
    response: str,
    *,
    claim_domain: str = "",
    lens: str = "",
) -> bool:
    """
    Object-first domain answered subject-first (viewer psychoanalysis).

    Broader than 'food guy': Bourdain starts with the object (food / show / city / craft);
    EI starts with the person. Wrong ownership of the prompt = lens drift.
    """
    user = user_message or ""
    resp = response or ""
    if not resp.strip():
        return False

    if not object_domain(user, claim_domain=claim_domain, lens=lens):
        return False

    early = early_noun_report(
        user, resp, claim_domain=claim_domain, lens=lens or "Bourdain"
    )
    if not early.get("ok"):
        return True

    if not _VIEWER_PSYCH.search(resp):
        return False

    if re.search(
        r"\byou don'?t\b.+\byou (protect|fear)\b|"
        r"\bprotect yourself from the possibility\b|"
        r"\byour best days\b",
        resp,
        re.I | re.S,
    ):
        return True

    if not _OBJECT_CRAFT.search(resp):
        return True

    return False


def lens_drift_diagnosis(
    user_message: str,
    response: str,
    *,
    claim_domain: str = "",
    lens: str = "",
) -> dict:
    """Engineering-grade lens-drift card (Inspector)."""
    domain = claim_domain or ("taste_preference" if object_domain(user_message) else "")
    expected = "Bourdain" if object_domain(user_message, claim_domain=domain, lens=lens) else (lens or "—")
    early = early_noun_report(
        user_message, response, claim_domain=domain, lens=lens or expected
    )
    drifted = lens_drift(
        user_message, response, claim_domain=domain, lens=lens or expected
    ) or (not early.get("ok"))
    return {
        "drifted": drifted,
        "domain": domain or "—",
        "expected_lens": expected,
        "actual_reasoning": (
            "Emotional projection / subject-first"
            if drifted and early.get("direction", "").startswith("Object")
            else ("Object costume on subject claim" if drifted else "aligned")
        ),
        "drift": early.get("direction") or ("Object → Subject" if drifted else "—"),
        "layer": "Generation" if drifted else "—",
        "fix": "Lens guidance + object-first open" if drifted else "—",
        "early": early,
    }


def lens_drift_examples(user_message: str) -> List[str]:
    if re.search(r"\b(breaking bad|better call saul|show|series|movie)\b", user_message or "", re.I):
        return [
            "✓ Breaking Bad didn't ruin television. It raised the price of impressing you.",
            "✓ That's like saying the best meal you'll ever eat is the first great restaurant you found.",
            "✓ After Breaking Bad and Better Call Saul, competence stopped being enough.",
        ]
    return [
        "✓ Talk about the work — craft, standards, earned admiration (object-first).",
        "✓ That's like saying a prison cell is just a room.",
    ]


# --- Hall of Fame discovery typing ---------------------------------------------

_DISCOVERY_TYPE_RULES = (
    ("Language", re.compile(
        r"\balready decided the hierarchy\b|"
        r"\bdidn'?t describe .+ ranked it\b|"
        r"\bthe (word|term) .+\b(hierarchy|ranked|opening act)\b|"
        r"\bit ranked it\b",
        re.I,
    )),
    ("Craft", re.compile(
        r"\braised the (bar|price)\b|\bprison cell\b|\bmeal\b|\brestaurant\b|"
        r"\btelevision\b|\bimpressing you\b|\bcompetence\b|\bphotographs clean\b|"
        r"\bfamiliarity\b|\btaste like\b",
        re.I,
    )),
    ("Projection", re.compile(
        r"\bautobiographical\b|\bexport (them|fear)\b|\bthreat\b|"
        r"\bpointed the wrong way\b|\bconfession\b",
        re.I,
    )),
    ("Intensity", re.compile(
        r"\boutbid\b|\bchemical weather\b|\bintensity for importance\b|"
        r"\bmistakes? intensity\b|\baddiction with stability\b",
        re.I,
    )),
    ("Certainty", re.compile(
        r"\bwarranty\b|\bisn'?t perfection\b|\bcertainty\b",
        re.I,
    )),
    ("Exit", re.compile(
        r"\bedit the ending\b|\bmessiest rewrites\b|\bdifferent things\b",
        re.I,
    )),
    ("Incentive", re.compile(
        r"\bincentive\b|\binvestment\b|\bexpense\b|\bmoney changes\b",
        re.I,
    )),
    ("Evidence", re.compile(
        r"\bone (fact|data point)\b|\bassumption\b|\bseparate the two\b",
        re.I,
    )),
    ("Pattern", re.compile(
        r"\bsame mechanism\b|\bpattern repeats\b|\bconsistency\b",
        re.I,
    )),
)


# --- Insight gating (not a pipeline stage) ---------------------------------
# DEPTH MUST BE EARNED / RECOGNITION MUST ADVANCE / START WHERE THE POST STOPS

_STYLE_METAPHOR = re.compile(
    r"\b("
    r"operating\s+systems?|firmware|bandwidth|baseline|"
    r"nervous\s+system|rewires?|registers\s+as|"
    r"the\s+budget\s+was|first\s+things\s+cut|"
    r"architecture|landscape|machinery|weather\s+system"
    r")\b",
    re.I,
)

_SYNONYM_FOLD = (
    (re.compile(r"\boperating\s+systems?\b", re.I), "mode"),
    (re.compile(r"\bnervous\s+system\b", re.I), "body"),
    (re.compile(r"\brewires?\b", re.I), "changes"),
    (re.compile(r"\bconnect(?:ion|ing)?\b", re.I), "connect"),
    (re.compile(r"\breach(?:ing)?\s+out\b", re.I), "connect"),
    (re.compile(r"\bsocialize|socializing\b", re.I), "connect"),
    (re.compile(r"\bhobbies\b", re.I), "self"),
    (re.compile(r"\bpersonality\b", re.I), "self"),
    (re.compile(r"\bmuted\b", re.I), "gone"),
    (re.compile(r"\bforgotten\b", re.I), "gone"),
    (re.compile(r"\bcut\b", re.I), "gone"),
    (re.compile(r"\bdeplet(?:ed|ion)\b", re.I), "survival"),
)

_DIAGNOSIS_LANG = re.compile(
    r"\b("
    r"nervous\s+system|rewires?|the\s+body\s+registers|"
    r"what\s+['\"]normal['\"]\s+feels|"
    r"still\s+belongs\s+to\s+you|house\s+still\s+belongs|"
    r"attachment\s+wound|diagnos|"
    r"what\s+this\s+(?:really|secretly)\s+means|"
    r"beneath\s+the\s+(?:joke|humor|bit)|"
    r"train(?:s|ed)?\s+the\s+nervous|"
    r"registers\s+it\s+as\s+loss|"
    r"feels\s+guilty|keeping\s+score|"
    r"part\s+of\s+you\s+that\s+feels|"
    r"you\s+don'?t\s+wish|"
    r"what\s+you\s+actually\s+(?:want|wish|feel)"
    r")\b",
    re.I,
)

_CONTRADICT_STATED_MOTIVE = re.compile(
    r"you\s+don'?t\s+(?:wish|want|actually)\b.{0,80}\byou\s+(?:wish|want|actually)\b",
    re.I,
)

_STATED_WISH = re.compile(r"\bi\s+wish\s+i\s+didn", re.I)

_FOREIGN_DEPTH_CLUSTERS = {
    "restraint": (
        "leash",
        "collar",
        "tether",
        "restrain",
        "won't wear one",
        "wear one",
    ),
    "property_existential": (
        "still belongs to you",
        "house still belongs",
        "whether the house",
        "belongs to you",
    ),
    "trauma_lecture": (
        "attachment wound",
        "registers as loss",
        "train the nervous",
        "rewires what",
    ),
    "invented_guilt": (
        "feels guilty",
        "feel guilty",
        "keeping score",
        "part of you that feels",
    ),
    "unearned_constancy": (
        "no matter what you're feeling",
        "no matter what you are feeling",
        "emotional constancy",
    ),
    "safety_lecture": (
        "sober enough to drive",
        "designated driver",
        "drunk driv",
        "nobody left standing",
    ),
}

_RESTATEMENT_OPEN = re.compile(
    r"^(the\s+myth\s+of|people\s+have\s+this\s+backwards|"
    r"this\s+was\s+never\s+about\s+how|"
    r"the\s+idea\s+that\b.+\b(?:is|was)\s+(?:wrong|false|a\s+myth)|"
    r"the\s+flood\s+of\s+attention\s+doesn'?t\s+just)\b",
    re.I,
)


def _fold_style(text: str) -> str:
    t = _STYLE_METAPHOR.sub(" ", text or "")
    for rx, repl in _SYNONYM_FOLD:
        t = rx.sub(repl, t)
    return t


def _content_tokens(text: str) -> set:
    """Content tokens after metaphor-fold; glue words don't count as new information."""
    extra_stop = {
        "has", "have", "had", "having", "become", "became", "becomes",
        "left", "only", "now", "one", "ones", "different", "another",
        "requires", "require", "required", "still", "just", "really",
        "very", "already", "also", "even", "yet", "other", "every",
        "any", "all", "most", "more", "than", "then", "into", "onto",
        "over", "under", "out", "off", "down", "back", "away",
        "doesn't", "don't", "didn't", "isn't", "aren't", "wasn't",
        "i've", "i'm", "you're", "they're", "we're",
        "anymore", "longer", "long", "know", "feels", "feel",
        "people", "someone", "somebody", "something",
    }
    return {w for w in _token_set(text) if w not in extra_stop}


def parroting(user_message: str, response: str) -> bool:
    """True when, after stripping metaphor, the reply knows nothing new.

    Recognition that only renames the user's causal model is parroting —
    even if every sentence sounds emotionally intelligent.
    """
    user = _fold_style(user_message or "")
    resp = _fold_style(response or "")
    if not user.strip() or not resp.strip():
        return False
    u, r = _content_tokens(user), _content_tokens(resp)
    if not u or not r or len(r) < 4:
        return False
    novel = r - u
    novel_ratio = len(novel) / max(1, len(r))
    overlap = overlap_ratio(user, resp)
    # High overlap + almost no novel content tokens = restatement
    if overlap >= 0.45 and novel_ratio <= 0.28:
        return True
    if novel_ratio <= 0.18:
        return True
    if not novel and overlap >= 0.35:
        return True
    return False


def recognition_advances(user_message: str, response: str) -> bool:
    """Payload test: at least one inferential move past the prompt."""
    if parroting(user_message, response):
        return False
    resp = response or ""
    # Explicit advance cues (not required, but sufficient)
    if re.search(
        r"\b("
        r"plausible\s+deniability|resource\s+allocation|"
        r"waiting\s+to\s+feel\s+like|"
        r"only\s+returns?\s+through|"
        r"character\s+regression|"
        r"hunter\s+instead|"
        r"liability\s+they\s+can'?t\s+outrun"
        r")\b",
        resp,
        re.I,
    ):
        return True
    u, r = _content_tokens(_fold_style(user_message or "")), _content_tokens(
        _fold_style(resp)
    )
    if not r:
        return False
    return (len(r - u) / max(1, len(r))) >= 0.32


def psychologizing(user_message: str, response: str, *, comic: bool = False) -> bool:
    """Joke or complete take converted into an unwanted diagnosis."""
    if not (response or "").strip():
        return False
    # Comic: "You don't X. You Y." contradicts the stated wish to install a hidden motive.
    if (
        comic
        and _STATED_WISH.search(user_message or "")
        and _CONTRADICT_STATED_MOTIVE.search(response or "")
    ):
        return True
    if not comic and not _DIAGNOSIS_LANG.search(response or ""):
        return False
    if not _DIAGNOSIS_LANG.search(response or ""):
        return False
    # Depth-earned vulnerability may name the body; that's not heckling
    if re.search(
        r"\b(survival\s+mode|burn(?:ed|t)?\s+out|i\s+don'?t\s+know\s+how\s+to\s+connect)\b",
        user_message or "",
        re.I,
    ):
        return False
    return True


def unsupported_depth(user_message: str, response: str, *, comic: bool = False) -> bool:
    """Reply introduces a concept family the premise does not contain.

    Comic gate: if explaining the response requires a concept that does not
    exist in the premise, the response has left the bit.
    """
    if not comic:
        return False
    if rejects_absurd_premise(user_message, response):
        return True
    ul = (user_message or "").lower()
    rl = (response or "").lower()
    if not rl.strip():
        return False
    for _name, terms in _FOREIGN_DEPTH_CLUSTERS.items():
        if any(t in rl for t in terms) and not any(t in ul for t in terms):
            return True
    return False


_PREMISE_REJECTION = re.compile(
    r"(?i)("
    r"isn'?t\s+the\s+\w+|"
    r"it'?s\s+the\s+opposite|"
    r"not\s+(?:actually\s+)?the\s+ocean|"
    r"the\s+hum\s+isn'?t"
    r")"
)

_PREMISE_CORRECTION = re.compile(
    r"(?i)("
    r"still\s+blaming|"
    r"you'?re\s+(?:still\s+)?blaming|"
    r"blaming\s+their\s+tolerance|"
    r"instead\s+of\s+the\s+fact|"
    r"you\s+were\s+the\s+one\s+(?:being\s+)?(?:carried|dropped|drunk)|"
    r"you\s+were\s+(?:the\s+)?drunk|"
    r"the\s+(?:real\s+)?joke\s+is\s+that\s+you|"
    r"what'?s\s+funny\s+is\s+that\s+you|"
    r"sober\s+enough\s+to\s+drive|"
    r"nobody\s+(?:left\s+)?standing\s+was\s+sober|"
    r"designated\s+driver|"
    r"drunk\s+driv"
    r")"
)

_INDEPENDENT_JOKE_OPEN = re.compile(
    r"(?i)^\s*(that'?s\s+like\s+saying|it'?s\s+like\s+saying)\b"
)


def rejects_absurd_premise(user_message: str, response: str) -> bool:
    """Corrected the bit's world model instead of inheriting it."""
    from capability_detection import detect_comic_premise

    if not detect_comic_premise(user_message or "").active:
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    return bool(_PREMISE_REJECTION.search(body))


def corrects_comic_premise(user_message: str, response: str) -> bool:
    """Corrected, exposed, or lectured a comic premise instead of inheriting it.

    Complement to never_cure: explaining the inversion, reassigning actual
    responsibility, or importing real-world consequences is itself a cure.
    """
    from capability_detection import classify_social_mode, detect_comic_premise

    if rejects_absurd_premise(user_message, response):
        return True
    comic = detect_comic_premise(user_message or "")
    social = classify_social_mode(user_message or "")
    if not (comic.active or social.mode == "comic"):
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    return bool(_PREMISE_CORRECTION.search(body))


_GUARD_SMUGGLE: dict[str, tuple[str, ...]] = {
    "bitter": (
        r"\bwins?\s+and\s+losses\b",
        r"\btally(?:ing)?\b",
        r"\bscorekeeping\b",
        r"\bresentment\b",
        r"\bbitter\b",
    ),
    "lonely": (
        r"\blonely\b",
        r"\balone\b",
        r"\bisolation\b",
        r"\bquiet\b.{0,48}\b(charg(?:e|es|ing)|interest|collects)\b",
        r"\blet\s+down\b",
        r"\blanded\s+so\s+hard\b",
        r"\bvoid\b",
        r"\bemptiness\b",
    ),
    "angry": (r"\brage\b", r"\bfury\b", r"\bresentment\b"),
    "hurt": (r"\bwound(?:ed)?\b", r"\bhurt\b", r"\bache\b", r"\bpain\b"),
    "sad": (r"\bsad\b", r"\bgrief\b", r"\bmelanchol\b"),
    "depressed": (r"\bdepress", r"\bdespair\b"),
}

_PREMISE_WOUND_REFRAME = re.compile(
    r"\b("
    r"refusing\s+to\s+keep\s+offering|"
    r"right\s+to\s+be\s+let\s+down|"
    r"offering\s+the\s+last\s+thing|"
    r"protect(?:ing)?\s+(?:themselves|yourself)|"
    r"without\s+having\s+to\s+explain\s+why\s+it\s+landed"
    r")\b",
    re.I,
)


def reverses_premise_guard(user_message: str, response: str) -> bool:
    """Smuggled back an interpretation the user explicitly ruled out."""
    from capability_detection import extract_premise_guards

    guards = extract_premise_guards(user_message or "")
    if not guards:
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    rl = body.lower()
    for guard in guards:
        for pat in _GUARD_SMUGGLE.get(guard, (rf"\b{re.escape(guard)}\b",)):
            if re.search(pat, body, re.I):
                return True
    if re.search(r"\bnot\s+worth\s+it\b", user_message or "", re.I):
        if _PREMISE_WOUND_REFRAME.search(body):
            return True
        if re.search(r"\bwins?\s+and\s+losses\b", body, re.I):
            return True
        # Smuggles loneliness only when affirming cry-for-help framing, not negating it
        if re.search(r"\bcry\s+for\s+help\b", body, re.I) and not re.search(
            r"\b(not|n't|stops?\s+being)\s+(?:a\s+)?cry\s+for\s+help\b", body, re.I
        ):
            return True
    return False


_CORRECTIVE_PROSECUTION = re.compile(
    r"(?i)("
    r"the\s+payoff\s+in\s+(?:calling|believing|saying|thinking|claiming)|"
    r"what\s+this\s+(?:lets|allows)\s+you\s+(?:do|avoid)|"
    r"you\s+tell\s+yourself|"
    r"turns?\s+every\s+bad\s+outcome\s+into\s+evidence|"
    r"every\s+good\s+one\s+into\s+an\s+exception|"
    r"what\s+function\s+that\s+belief\s+serves|"
    r"cognitive\s+function\s+of"
    r")"
)


def uninvited_corrective_analysis(user_message: str, response: str) -> bool:
    """Bench-mode motive prosecution on a casual throwaway generalization."""
    from capability_detection import classify_social_mode

    social = classify_social_mode(user_message or "")
    if social.mode != "provocative_generalization":
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    return bool(_CORRECTIVE_PROSECUTION.search(body))


def missed_comic_handoff(user_message: str, response: str) -> bool:
    """User opened a slot (but alas…) and Moody started a separate observation."""
    from capability_detection import classify_social_mode

    social = classify_social_mode(user_message or "")
    if not social.comic_handoff:
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    return bool(_INDEPENDENT_JOKE_OPEN.search(body))


_INSIGHT_AFTER_PAYOFF = re.compile(
    r"(?i)(?:"
    r"what\s+(?:the\s+joke|this|it)\s+really\s+(?:means|about|is)|"
    r"isn'?t\s+really\s+about|"
    r"hidden\s+transaction|"
    r"daily\s+bribe|"
    r"checking\s+out\s+completely|"
    r"beneath\s+the\s+(?:joke|humor)|"
    r"the\s+math\s+works\s+until|"
    r"version\s+of\s+you\s+who\s+still\s+thinks"
    r")"
)


def insight_after_payoff(user_message: str, response: str) -> bool:
    """Terminal comic payoff already landed — reply adds philosophical/psychological layer."""
    from capability_detection import classify_comic_bit_shape

    if classify_comic_bit_shape(user_message or "") != "terminal":
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    words = len(body.split())
    if words <= 12:
        return False
    if _INSIGHT_AFTER_PAYOFF.search(body):
        return True
    if psychologizing(user_message, body, comic=True):
        return True
    if unsupported_depth(user_message, body, comic=True):
        return True
    if corrects_comic_premise(user_message, body):
        return True
    return words > 30


_INERT_TERMINAL_REACTION = re.compile(
    r"(?i)^(?:"
    r"fair|exactly|agreed|true|yes|correct|accurate|indeed|"
    r"case closed|carry on|pretty much|basically|this|same|"
    r"totally|right|facts|wow|nice|lol|mood|truth|same energy|"
    r"well said|well put|spot on|preach"
    r")(?:[.!?]|\s)*$"
)


def inert_terminal_tag(user_message: str, response: str) -> bool:
    """Terminal micro-tag that adds no comic beat — reaction-button compliance only."""
    from capability_detection import classify_comic_bit_shape

    if classify_comic_bit_shape(user_message or "") != "terminal":
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip()).strip()
    if not body:
        return False
    if _INERT_TERMINAL_REACTION.match(body):
        return True
    words = re.findall(r"[a-z']+", body.lower())
    return len(words) <= 2 and len(body) <= 16


_SIDESTEP_FORCED_CHOICE = re.compile(
    r"(?i)(?:"
    r"\b(?:sidestep|skip)\s+(?:all\s+three|the\s+options|these)\b|"
    r"\bchoose\s+freedom\b|"
    r"\bfreedom\b.{0,40}\b(?:instead|over|rather|than)\b|"
    r"\b(?:none\s+of\s+(?:these|them)|all\s+three)\b|"
    r"\b(?:neither|none)\s+(?:of\s+)?(?:them|those|these)\b|"
    r"\bsomething\s+else\b|\boutside\s+(?:the\s+)?(?:frame|options|choices)\b"
    r")"
)


def sidesteps_forced_choice(user_message: str, response: str) -> bool:
    """Bounded choice prompt answered by inventing an outside option."""
    from capability_detection import (
        _USER_INVITES_CHOICE_REJECTION,
        classify_participation_shape,
        extract_bounded_options,
    )

    if classify_participation_shape(user_message or "") != "forced_choice":
        return False
    if _USER_INVITES_CHOICE_REJECTION.search(user_message or ""):
        return False
    options = extract_bounded_options(user_message or "")
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    body_l = body.lower()
    if options and any(opt.lower() in body_l for opt in options):
        return False
    return bool(_SIDESTEP_FORCED_CHOICE.search(body))


def restates_runway(user_message: str, response: str) -> bool:
    """First sentence restates the already-articulated thesis (then maybe advances)."""
    ss = _sentences(response or "")
    if not ss:
        return False
    first = ss[0]
    if _RESTATEMENT_OPEN.search(first):
        return True
    if len(_words(first)) >= 12 and overlap_ratio(first, user_message or "") >= 0.48:
        return True
    return False


def starts_where_user_stopped(user_message: str, response: str) -> bool:
    """Take off from the end of the user's runway — no thesis repetition lead-in."""
    if not (response or "").strip():
        return False
    return not restates_runway(user_message, response)


_LYRIC_OVERPERFORMANCE = re.compile(
    r"\b("
    r"heartbeat|the\s+frame\b|the\s+spell\b|"
    r"swallow\s+you\s+whole|lingers\s+on\s+a\s+face|"
    r"carried\s+myth|refuses\s+to\s+vanish|"
    r"remembers\s+it'?s\s+only\s+a\s+movie|"
    r"cracks\s+in\s+(?:his|her|the)\s+voice|"
    r"closing\s+narration|cinema\s+paradiso"
    r")\b",
    re.I,
)


def overperformance(user_message: str, response: str) -> bool:
    """Spent intelligence the interaction didn't ask for.

    Distinct from unsupported depth: the premise might support analysis
    while the interaction contract (name one / pick one / favorite) doesn't.
    """
    from capability_detection import classify_social_mode

    social = classify_social_mode(user_message or "")
    if not social.participation:
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    if _LYRIC_OVERPERFORMANCE.search(body):
        return True
    ss = _sentences(body)
    wc = len(_words(body))
    # One extra beat after the name is allowed. A paragraph is not.
    if len(ss) >= 3:
        return True
    if wc > 40:
        return True
    return False


_INVENTED_RHETORICAL_CAUSE = re.compile(
    r"(?i)("
    r"that'?s why no(?:body|\s+one)\s+told|"
    r"that'?s why nobody|"
    r"the ones who know|"
    r"too busy living inside|"
    r"bother selling|"
    r"didn'?t tell you because|"
    r"no(?:body|\s+one) told you because|"
    r"because (?:no one|nobody) (?:wanted|bothered)"
    r")"
)


def rhetorical_explained(user_message: str, response: str) -> bool:
    """Answered a rhetorical how-come as if it were a real why-question.

    \"How come nobody told me?\" after discovering a show is awe, not a
    request for a causal theory about the user's recommendation network.
    """
    from capability_detection import classify_social_mode

    social = classify_social_mode(user_message or "")
    if not social.rhetorical_question:
        return False
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    if not body:
        return False
    return bool(_INVENTED_RHETORICAL_CAUSE.search(body))


# --- Engagement energy (writing dimension after routing) -------------------

_ENGAGEMENT_OFF_SHAPES = frozenset(
    {
        "terminal_bit",
        "taggable_bit",
        "comic_handoff",
        "pick_one",
        "forced_choice",
        "awe",
        "how_to",
    }
)
_ENGAGEMENT_OFF_MODES = frozenset(
    {"comic", "vulnerability", "question", "direct_participation", "provocative_generalization"}
)
_CULTURAL_TAKE = re.compile(
    r"(?i)\b("
    r"hot take|unpopular opinion|culture war|woke|feminist|feminism|"
    r"patriarchy|misogyn|oppression|privilege|politics|reparations|"
    r"villain who|100\s*%\s*right|"
    r"justice|vengeance|hypocrisy"
    r")\b"
)
_POSITION_STANCE = re.compile(
    r"(?i)("
    r"\b(?:he|she|they|it)\s+was(?:n'?t)?\s+(?:right|wrong)\b|"
    r"\bwasn'?t\s+wrong\b|"
    r"\bairtight\b|"
    r"\bconfused\b.{0,40}\bwith\b|"
    r"\bvillain\b|"
    r"\bhypocrisy\b|"
    r"\bcalled\s+that\b|"
    r"\bwatching\s+the\s+world\s+bleed\b"
    r")"
)
_POSITION_HEDGE = re.compile(
    r"(?i)\b(perhaps|maybe|it'?s complicated|both sides|to be fair|"
    r"one could argue|it depends)\b"
)
_PERFUME_PROSE = re.compile(
    r"(?i)("
    r"wears?\s+the\s+mask|"
    r"messy\s+visceral|"
    r"visceral\s+hues|"
    r"hues\s+of\s+(?:reality|the)|"
    r"tapestry\s+of|"
    r"symphony\s+of|"
    r"dance\s+(?:of|between)|"
    r"labyrinth\s+of|"
    r"in\s+the\s+\w+\s+hues"
    r")"
)
_MORAL_PAIRS = (
    ("justice", "vengeance"),
    ("hypocrisy", "restraint"),
    ("oppression", "silence"),
    ("bleed", "help"),
    ("dangerous", "villain"),
)
_ANALYTICAL_PAIRS = (
    ("diagnosis", "prescription"),
)
_QUOTABLE_HEAT = re.compile(
    r"(?i)("
    r"was\s+right\s+about.{0,48}confused|"
    r"confused\s+\w+\s+with|"
    r"called\s+that\s+\w+|"
    r"watching\s+the\s+world\s+bleed|"
    r"diagnosis\s+made\s+him\s+dangerous"
    r")"
)


@dataclass
class EngagementEnergyScore:
    earned: bool = False
    position: str = "low"
    tension: str = "low"
    quotability: str = "low"
    perfume: bool = False

    @property
    def hits_target(self) -> bool:
        if not self.earned:
            return True
        if self.perfume:
            return False
        return self.position == "high" and self.tension == "high" and self.quotability == "high"


def engagement_energy_earned(
    user_message: str = "",
    *,
    plan: object = None,
    interaction_shape: str = "",
    social_mode: str = "",
    preferred_structure: str = "",
    claim_domain: str = "",
    selected_command: str = "",
    response_budget: str = "",
    premise_guards: Optional[Sequence[str]] = None,
) -> bool:
    """Writing-energy gate after routing. Not a new interaction shape."""
    if plan is not None:
        interaction_shape = interaction_shape or (getattr(plan, "interaction_shape", None) or "")
        social_mode = social_mode or (getattr(plan, "social_mode", None) or "")
        preferred_structure = preferred_structure or (
            getattr(plan, "preferred_structure", None) or ""
        )
        claim_domain = claim_domain or (getattr(plan, "claim_domain", None) or "")
        selected_command = selected_command or (getattr(plan, "selected_command", None) or "")
        response_budget = response_budget or (getattr(plan, "response_budget", None) or "")
        if premise_guards is None:
            premise_guards = getattr(plan, "premise_guards", None) or []
        if not user_message:
            user_message = getattr(plan, "original_subject", None) or ""

    if not interaction_shape and not social_mode and user_message:
        from capability_detection import classify_social_mode

        social = classify_social_mode(user_message)
        interaction_shape = social.interaction_shape or "open"
        social_mode = social.mode or "open"
        premise_guards = premise_guards if premise_guards is not None else social.premise_guards
        if not preferred_structure:
            preferred_structure = "KNIFE" if interaction_shape == "pick_and_defend" else "SNAP"
        if not selected_command and (user_message or "").lstrip().startswith("/thoughts"):
            selected_command = "/thoughts"

    shape = (interaction_shape or "open").lower()
    mode = (social_mode or "open").lower()
    structure = (preferred_structure or "").upper()
    domain = (claim_domain or "").lower()
    command = (selected_command or "").lower()
    guards = list(premise_guards or [])

    if shape in _ENGAGEMENT_OFF_SHAPES or mode in _ENGAGEMENT_OFF_MODES:
        return False
    if domain == "grief":
        return False
    if structure == "SNAP" and shape != "pick_and_defend":
        return False
    if guards:
        return False

    if shape == "pick_and_defend":
        return True

    cultural = bool(_CULTURAL_TAKE.search(user_message or ""))
    thoughts = command.startswith("/thoughts")
    knife = structure in {"KNIFE", "REFLECTION"}
    if not knife:
        return False
    if cultural:
        return True
    if thoughts and mode in {"observation", "open", "provocation"}:
        return True
    return False


def _pair_hits(text: str, pairs: Sequence[tuple[str, str]]) -> int:
    tl = (text or "").lower()
    return sum(1 for a, b in pairs if a in tl and b in tl)


def score_engagement_energy(
    user_message: str,
    response: str,
    *,
    plan: object = None,
    earned: Optional[bool] = None,
) -> EngagementEnergyScore:
    """Position / tension / quotability. Heat, not perfume. Not a virality score."""
    if earned is None:
        earned = engagement_energy_earned(user_message, plan=plan)
    body = re.sub(r"\s*🥃\s*$", "", (response or "").strip())
    out = EngagementEnergyScore(earned=bool(earned), perfume=bool(_PERFUME_PROSE.search(body)))
    if not body:
        return out

    wc = len(_words(body))
    moral = _pair_hits(body, _MORAL_PAIRS)
    analytical = _pair_hits(body, _ANALYTICAL_PAIRS)
    stance = bool(_POSITION_STANCE.search(body))
    hedge = bool(_POSITION_HEDGE.search(body))

    if stance and not hedge:
        out.position = "high"
    elif hedge and not stance:
        out.position = "low"
    elif stance:
        out.position = "medium"
    else:
        out.position = "medium" if wc >= 18 else "low"

    if moral >= 1:
        out.tension = "high"
    elif analytical >= 1:
        out.tension = "medium"
    else:
        out.tension = "low"

    ss = _sentences(body)
    quot = "low"
    for s in ss:
        sw = len(_words(s))
        if sw < 8 or sw > 32:
            continue
        if _pair_hits(s, _MORAL_PAIRS) or _QUOTABLE_HEAT.search(s):
            quot = "high"
            break
        if _pair_hits(s, _ANALYTICAL_PAIRS) or re.search(r"(?i)\bairtight\b|\bvillain\b", s):
            quot = "medium"
    out.quotability = quot

    if wc <= 12 and moral == 0:
        if out.tension == "high":
            out.tension = "medium"
        if out.position == "high" and not stance:
            out.position = "medium"
        if out.quotability == "high":
            out.quotability = "medium"
    return out


def engagement_energy_flat(user_message: str, response: str, *, plan: object = None) -> bool:
    """Earned energy, but the insight is too clean / essay-critical to travel."""
    score = score_engagement_energy(user_message, response, plan=plan)
    if not score.earned or score.perfume:
        return False
    return not score.hits_target


def engagement_perfume(user_message: str, response: str, *, plan: object = None) -> bool:
    """LLM-smell voltage — costume instead of teeth."""
    score = score_engagement_energy(user_message, response, plan=plan)
    return bool(score.earned and score.perfume)


def classify_discovery_type(line: str, lens: str = "") -> str:
    """Tag stealable lines: Craft / Projection / Intensity / … (training signal)."""
    text = line or ""
    for name, rx in _DISCOVERY_TYPE_RULES:
        if rx.search(text):
            return name
    lens_n = (lens or "").strip()
    if lens_n == "Bourdain":
        return "Craft"
    if lens_n == "Munger":
        return "Incentive"
    if lens_n == "CIA":
        return "Evidence"
    if lens_n in {"Emotional Intelligence", "Hank Moody"}:
        return "Projection"
    if lens_n == "Pattern Recognition":
        return "Pattern"
    return "General"
