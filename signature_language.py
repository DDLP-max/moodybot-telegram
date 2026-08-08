# -*- coding: utf-8 -*-
"""Rhetorical signature language for MoodyBot recognition callbacks.

ChatGPT remembers the topic.
MoodyBot remembers the language.

Callbacks are RHETORICAL — they reuse distinctive authorial wording.
They are not semantic, topical, or generic reflective questions.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Set, Tuple


# Distinctive lexicon — preserve these; never reduce to synonyms.
SIGNATURE_LEXICON = {
    "stretch", "stretched", "stretching", "unfold", "unfolded", "unfolding",
    "carry", "carrying", "carried", "gravity", "weather", "room", "door",
    "map", "current", "script", "oxygen", "mirror", "shadow", "weight",
    "temperature", "signal", "anchor", "fingerprints", "fingerprint",
    "backstage", "crack", "cracked", "cracking", "bruise", "bruised",
    "haunt", "haunted", "ghost", "echo", "scar", "wound", "thread",
    "bridge", "mask", "stage", "library", "intimacy", "boundary",
}

# Generic topical/reflective language — never treat as signature.
GENERIC_LEXICON = {
    "change", "changed", "changing", "shift", "shifted", "shifting",
    "feel", "felt", "feeling", "think", "thought", "about", "what",
    "part", "sense", "aspect", "topic", "thing", "something", "really",
    "just", "like", "want", "need", "know", "mean", "means", "question",
    "answer", "explore", "discuss", "talk", "dirty", "porn", "pornography",
    "language", "culture", "relationship", "people", "between", "influence",
}

# If a signature term is protected, these substitutes DESTROY the fingerprint.
SYNONYM_DESTRUCTION = {
    "stretch": {"change", "changed", "shift", "shifted", "differ", "different"},
    "stretched": {"change", "changed", "shift", "shifted", "differ", "different"},
    "stretching": {"change", "changed", "shift", "shifted"},
    "carry": {"hold", "holding", "bear", "bearing", "deal"},
    "carrying": {"holding", "bearing", "dealing"},
    "carried": {"held", "bore"},
    "crack": {"break", "broke", "broken", "open"},
    "cracked": {"broke", "broken", "opened"},
    "gravity": {"weight", "heaviness", "importance"},
    "room": {"space", "place", "situation"},
    "script": {"story", "narrative", "pattern"},
    "mirror": {"reflection", "image"},
    "oxygen": {"air", "breath", "space"},
}

GENERIC_REFLECTIVE = [
    r"familiar or alien",
    r"felt most familiar",
    r"does that resonate",
    r"what do you make of that",
    r"how does that land",
    r"what comes up for you",
    r"what changed in your sense",
    r"what shifted in how you",
    r"what part of that (?:shift|change)",
]

SIGNATURE_THRESHOLD = 0.55

# Per-conversation memory: conversation_id -> recent signature stems used in closers
_CONVERSATION_SIGNATURE_TERMS: Dict[str, Deque[str]] = defaultdict(lambda: deque(maxlen=32))


@dataclass
class SignaturePhrase:
    phrase: str
    stem: str
    score: float
    kind: str  # verb | image | construction | metaphor
    protected: bool = False


@dataclass
class SignatureSet:
    phrases: List[SignaturePhrase] = field(default_factory=list)
    protected: List[str] = field(default_factory=list)
    raw_constructions: List[str] = field(default_factory=list)

    @property
    def primary(self) -> Optional[SignaturePhrase]:
        protected = [p for p in self.phrases if p.protected]
        pool = protected or self.phrases
        if not pool:
            return None
        return sorted(pool, key=lambda p: (-p.score, -len(p.phrase)))[0]

    @property
    def stems(self) -> List[str]:
        return [p.stem for p in self.phrases if p.protected]


def _stem(word: str) -> str:
    w = (word or "").lower()
    for suffix in ("ing", "ed", "es", "s"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            return w[: -len(suffix)] if suffix != "ing" or not w.endswith("ning") else w[:-3]
    return w


def _normalize_stem(word: str) -> str:
    w = (word or "").lower()
    # Prefer lexicon roots
    for root in (
        "stretch", "unfold", "carry", "crack", "haunt", "bruise",
        "fingerprint", "shadow", "mirror", "gravity", "oxygen", "script",
        "room", "door", "weather", "current", "weight", "bridge", "thread",
        "wound", "scar", "mask", "stage", "library", "intimacy", "boundary",
        "anchor", "signal", "temperature", "backstage", "map",
    ):
        if w.startswith(root) or root.startswith(w[: max(4, len(w) - 1)]):
            if root in w or w in root or w.startswith(root[:4]):
                if w.startswith(root) or root.startswith(w):
                    return root
    return _stem(w)


def signature_score(phrase: str, *, in_lexicon: bool, kind: str) -> float:
    """Score distinctive / authorial feel. Higher = more protected."""
    p = (phrase or "").strip().lower()
    if not p or p in GENERIC_LEXICON:
        return 0.0

    score = 0.0
    words = re.findall(r"[a-z']+", p)

    # Rarity / lexicon membership
    if in_lexicon:
        score += 0.45
    if any(w in SIGNATURE_LEXICON for w in words):
        score += 0.25

    # Imagery / metaphor feel
    if kind in {"image", "metaphor", "construction"}:
        score += 0.15

    # Multi-word construction (authorial phrasing)
    if len(words) >= 2:
        score += 0.2
    if len(words) >= 3:
        score += 0.1

    # Novelty vs generic reflective vocabulary
    if not any(w in GENERIC_LEXICON for w in words):
        score += 0.15
    else:
        # Penalize if mostly generic
        generic_ratio = sum(1 for w in words if w in GENERIC_LEXICON) / max(len(words), 1)
        score -= 0.25 * generic_ratio

    # Unexpected verbs / vivid wording
    if kind == "verb" and in_lexicon:
        score += 0.1

    return max(0.0, min(1.0, score))


def _extract_constructions(text: str) -> List[str]:
    lower = (text or "").lower()
    patterns = [
        r"got stretched out",
        r"stretched out",
        r"still carrying",
        r"carrying this",
        r"i'?m carrying",
        r"cracked something",
        r"the room changed",
        r"room changed",
        r"the script changed",
        r"script changed",
        r"gravity shifted",
        r"lost some oxygen",
        r"backstage",
        r"left fingerprints",
    ]
    found = []
    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            found.append(m.group(0))
    return found


def extract_signature_language(user_message: str) -> SignatureSet:
    """Extract distinctive authorial language — not topics, nouns-as-entities, or keywords."""
    text = re.sub(r"^/\w+\s*", "", (user_message or "").strip())
    lower = text.lower()
    constructions = _extract_constructions(lower)
    words = re.findall(r"[A-Za-z']+", lower)

    phrases: List[SignaturePhrase] = []

    for cons in constructions:
        stem = "stretch" if "stretch" in cons else _normalize_stem(cons.split()[0])
        for w in re.findall(r"[a-z']+", cons):
            if w in SIGNATURE_LEXICON or _normalize_stem(w) in SIGNATURE_LEXICON:
                stem = _normalize_stem(w)
                break
        score = signature_score(cons, in_lexicon=True, kind="construction")
        phrases.append(
            SignaturePhrase(
                phrase=cons,
                stem=stem,
                score=max(score, 0.85),
                kind="construction",
                protected=True,
            )
        )

    for w in words:
        if w in GENERIC_LEXICON and w not in SIGNATURE_LEXICON:
            continue
        in_lex = w in SIGNATURE_LEXICON
        if not in_lex and len(w) < 5:
            continue
        # Only keep non-lexicon words if they appear in vivid constructions already handled
        if not in_lex:
            continue
        stem = _normalize_stem(w)
        kind = "verb" if stem in {
            "stretch", "unfold", "carry", "crack", "haunt", "bruise"
        } else "image"
        score = signature_score(w, in_lexicon=True, kind=kind)
        phrases.append(
            SignaturePhrase(
                phrase=w,
                stem=stem,
                score=score,
                kind=kind,
                protected=score >= SIGNATURE_THRESHOLD,
            )
        )

    # Quoted fragments = authorial
    for m in re.finditer(r"[\"']([^\"']{3,40})[\"']", text):
        frag = m.group(1).strip()
        score = signature_score(frag, in_lexicon=False, kind="metaphor") + 0.2
        stem = _normalize_stem(re.findall(r"[A-Za-z']+", frag)[0]) if re.findall(r"[A-Za-z']+", frag) else frag
        phrases.append(
            SignaturePhrase(
                phrase=frag,
                stem=stem,
                score=min(1.0, score),
                kind="metaphor",
                protected=score >= SIGNATURE_THRESHOLD,
            )
        )

    # Deduplicate by stem, keep highest score / longest phrase
    best: Dict[str, SignaturePhrase] = {}
    for p in phrases:
        cur = best.get(p.stem)
        if not cur or (p.score, len(p.phrase)) > (cur.score, len(cur.phrase)):
            best[p.stem] = p

    ordered = sorted(best.values(), key=lambda p: (-p.score, -len(p.phrase)))
    protected = [p.phrase for p in ordered if p.protected]

    return SignatureSet(
        phrases=ordered,
        protected=protected,
        raw_constructions=constructions,
    )


def is_generic_reflective(question: str) -> bool:
    lower = (question or "").lower()
    return any(re.search(pat, lower) for pat in GENERIC_REFLECTIVE)


def loses_protected_language(callback: str, signatures: SignatureSet) -> bool:
    """True if a beautiful protected phrase disappeared into a synonym."""
    if not signatures.protected:
        return False
    lower = (callback or "").lower()
    # Must keep at least one protected stem literally (rhetorical echo)
    if any(p.stem in lower or p.phrase in lower for p in signatures.phrases if p.protected):
        # Also fail if synonym destruction present WITHOUT the stem
        return False
    return True


def uses_synonym_destruction(callback: str, signatures: SignatureSet) -> bool:
    """True if callback replaced signature language with a fingerprint-killing synonym."""
    lower = (callback or "").lower()
    words = set(re.findall(r"[a-z']+", lower))
    for p in signatures.phrases:
        if not p.protected:
            continue
        banned = SYNONYM_DESTRUCTION.get(p.stem, set()) | SYNONYM_DESTRUCTION.get(p.phrase, set())
        if not banned:
            continue
        # Destruction: banned synonym used AND signature stem absent
        if any(b in words for b in banned) and p.stem not in lower and p.phrase not in lower:
            return True
    return False


def belongs_only_to_this_conversation(callback: str, signatures: SignatureSet) -> bool:
    """Could this final sentence only belong to THIS conversation?"""
    if not callback:
        return False
    if is_generic_reflective(callback):
        return False
    if not signatures.protected:
        # No signature available — topical fallback is allowed but weak
        return True
    if loses_protected_language(callback, signatures):
        return False
    if uses_synonym_destruction(callback, signatures):
        return False
    lower = callback.lower()
    return any(p.stem in lower or p.phrase in lower for p in signatures.phrases if p.protected)


def remember_signature_use(conversation_id: str, callback: str, signatures: SignatureSet) -> None:
    if not conversation_id:
        return
    lower = (callback or "").lower()
    mem = _CONVERSATION_SIGNATURE_TERMS[conversation_id]
    for p in signatures.phrases:
        if p.protected and (p.stem in lower or p.phrase in lower):
            mem.append(p.stem)


def recently_used_stems(conversation_id: str) -> Set[str]:
    if not conversation_id:
        return set()
    return set(_CONVERSATION_SIGNATURE_TERMS.get(conversation_id, []))


def transform_signature_callback(
    signatures: SignatureSet,
    *,
    conversation_id: str = "",
) -> Optional[str]:
    """signature phrase → transformation → rhetorical callback. Never synonymize."""
    if not signatures.phrases:
        return None

    recent = recently_used_stems(conversation_id)

    # Prefer protected constructions / high-score phrases not mechanically overused
    candidates = [p for p in signatures.phrases if p.protected]
    if not candidates:
        candidates = list(signatures.phrases)

    # Evolve: prefer a stem not used last if alternatives exist
    ordered = sorted(
        candidates,
        key=lambda p: (
            0 if p.stem not in recent else 1,
            0 if p.kind == "construction" else 1,
            -p.score,
            -len(p.phrase),
        ),
    )
    primary = ordered[0]
    stem = primary.stem
    phrase = primary.phrase

    # Rhetorical transformations — keep the actual language
    if stem == "stretch" or "stretch" in phrase:
        variants = [
            "So what actually got stretched out in you reading that?",
            "So what actually got stretched out for you?",
            "What part of your definition got stretched furthest?",
            "What got stretched out in you while you were reading that?",
        ]
        # Evolve across the conversation — avoid mechanical identical reuse.
        mem = list(_CONVERSATION_SIGNATURE_TERMS.get(conversation_id, []))
        idx = sum(1 for m in mem if m == "stretch") % len(variants)
        return variants[idx]

    if stem == "carry" or "carry" in phrase:
        return "What are you still carrying now that you've named it?"

    if stem == "crack" or "crack" in phrase:
        return "What actually cracked?"

    if stem == "room" or "room" in phrase:
        return "What changed in the room after you saw it differently?"

    if stem == "script" or "script" in phrase:
        return "What part of the script stopped feeling inevitable?"

    if stem == "gravity" or "gravity" in phrase:
        return "What changed once the gravity shifted?"

    if stem == "mirror" or "mirror" in phrase:
        return "What did the mirror show you that the story was hiding?"

    if stem == "oxygen" or "oxygen" in phrase:
        return "What got harder to breathe around once the oxygen thinned?"

    if stem == "weather" or "weather" in phrase:
        return "What shifted in the weather of that moment once you named it?"

    if stem == "door" or "door" in phrase:
        return "What was on the other side of that door once you stopped pretending it was locked?"

    if stem == "weight" or "weight" in phrase:
        return "What part of the weight got more honest once you stopped decorating it?"

    if stem == "shadow" or "shadow" in phrase:
        return "What in the shadow stopped looking like mystery and started looking like pattern?"

    if stem == "fingerprint" or "fingerprints" in phrase:
        return "Whose fingerprints are still on this now that you can see them?"

    if stem == "backstage" or "backstage" in phrase:
        return "What did you notice backstage that the performance was hiding?"

    if stem == "current" or "current" in phrase:
        return "Where is the current actually taking you now that you feel it?"

    if stem == "anchor" or "anchor" in phrase:
        return "What are you still using as an anchor that might be a weight?"

    if stem == "unfold" or "unfold" in phrase:
        return "What unfolded that you weren't ready to name yet?"

    if stem == "map" or "map" in phrase:
        return "What part of the map no longer matches the territory?"

    if stem == "signal" or "signal" in phrase:
        return "What signal got clearer once the noise dropped?"

    if stem == "temperature" or "temperature" in phrase:
        return "What changed in the temperature of the room once the truth landed?"

    # Generic rhetorical echo — still preserve the phrase itself
    return f"What about '{phrase}' still holds now that you've heard it answered?"


def rhetorical_callback_quality(
    callback: str,
    user_message: str,
    signatures: Optional[SignatureSet] = None,
) -> Dict[str, bool]:
    signatures = signatures or extract_signature_language(user_message)
    q = (callback or "").strip()
    return {
        "is_question": q.endswith("?"),
        "not_generic_reflective": not is_generic_reflective(q),
        "preserves_signature": not loses_protected_language(q, signatures),
        "no_synonym_destruction": not uses_synonym_destruction(q, signatures),
        "conversation_specific": belongs_only_to_this_conversation(q, signatures),
        "brief": len(q.split()) <= 42,
    }
