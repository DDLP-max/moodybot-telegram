# -*- coding: utf-8 -*-
"""Authorial signature language for MoodyBot landings.

Preserve AUTHORIAL LANGUAGE — beautiful verbs, metaphors, unexpected phrasing.

Do NOT preserve topic nouns:
feminism, women, men, dirty talk, porn, politics, people, culture...

Those are subjects. Subjects are not fingerprints.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set  # noqa: F401


# Distinctive authorial lexicon only.
SIGNATURE_LEXICON = {
    "stretch", "stretched", "stretching", "unfold", "unfolded", "unfolding",
    "carry", "carrying", "carried", "gravity", "weather", "room", "door",
    "map", "current", "script", "oxygen", "mirror", "shadow", "weight",
    "temperature", "signal", "anchor", "fingerprints", "fingerprint",
    "backstage", "crack", "cracked", "cracking", "bruise", "bruised",
    "haunt", "haunted", "echo", "scar", "wound", "thread", "bridge",
    "mask", "stage",
}

# Topic / entity / ordinary language — never signature.
TOPIC_BLACKLIST = {
    "feminist", "feminists", "feminism", "woman", "women", "man", "men",
    "male", "female", "girl", "boy", "porn", "pornography", "dirty", "talk",
    "sex", "sexual", "politics", "political", "culture", "cultural", "society",
    "people", "person", "relationship", "dating", "language", "vocabulary",
    "influence", "between", "about", "praise", "praising", "hate", "hating",
    "loyalty", "equality", "gender", "doorman", "flowers", "wine", "number",
    "manager", "boss", "workplace", "partner", "boyfriend", "girlfriend",
}

GENERIC_LEXICON = TOPIC_BLACKLIST | {
    "change", "changed", "changing", "shift", "shifted", "shifting",
    "feel", "felt", "feeling", "think", "thought", "what", "part", "sense",
    "aspect", "topic", "thing", "something", "really", "just", "like",
    "want", "need", "know", "mean", "means", "question", "answer",
    "explore", "discuss", "why", "how", "does", "did", "are", "the",
}

SYNONYM_DESTRUCTION = {
    "stretch": {"change", "changed", "shift", "shifted", "differ", "different"},
    "stretched": {"change", "changed", "shift", "shifted", "differ", "different"},
    "carry": {"hold", "holding", "bear", "bearing", "deal"},
    "carrying": {"holding", "bearing", "dealing"},
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
    r"^what about\b",
]

SIGNATURE_THRESHOLD = 0.62

_CONVERSATION_SIGNATURE_TERMS: Dict[str, Deque[str]] = defaultdict(lambda: deque(maxlen=32))


@dataclass
class SignaturePhrase:
    phrase: str
    stem: str
    score: float
    kind: str
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


def _normalize_stem(word: str) -> str:
    w = (word or "").lower()
    for root in (
        "stretch", "unfold", "carry", "crack", "haunt", "bruise",
        "fingerprint", "shadow", "mirror", "gravity", "oxygen", "script",
        "room", "door", "weather", "current", "weight", "bridge", "thread",
        "wound", "scar", "mask", "stage", "anchor", "signal", "temperature",
        "backstage", "map", "echo",
    ):
        if w.startswith(root) or root.startswith(w[: max(4, min(len(w), len(root)))]):
            if w.startswith(root) or root.startswith(w):
                return root
    return w


def signature_score(phrase: str, *, in_lexicon: bool, kind: str) -> float:
    p = (phrase or "").strip().lower()
    if not p:
        return 0.0
    words = re.findall(r"[a-z']+", p)
    if any(w in TOPIC_BLACKLIST for w in words):
        return 0.0
    if p in GENERIC_LEXICON:
        return 0.0

    score = 0.0
    if in_lexicon:
        score += 0.5
    if any(w in SIGNATURE_LEXICON for w in words):
        score += 0.25
    if kind in {"image", "metaphor", "construction"}:
        score += 0.15
    if len(words) >= 2:
        score += 0.2
    if len(words) >= 3:
        score += 0.1
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
    text = re.sub(r"^/\w+\s*", "", (user_message or "").strip())
    lower = text.lower()
    constructions = _extract_constructions(lower)
    words = re.findall(r"[A-Za-z']+", lower)
    phrases: List[SignaturePhrase] = []

    for cons in constructions:
        # Skip constructions polluted by topic nouns
        cons_words = re.findall(r"[a-z']+", cons)
        if any(w in TOPIC_BLACKLIST for w in cons_words):
            continue
        stem = "stretch" if "stretch" in cons else _normalize_stem(cons_words[0])
        for w in cons_words:
            if w in SIGNATURE_LEXICON:
                stem = _normalize_stem(w)
                break
        score = signature_score(cons, in_lexicon=True, kind="construction")
        phrases.append(
            SignaturePhrase(cons, stem, max(score, 0.9), "construction", True)
        )

    for w in words:
        if w in TOPIC_BLACKLIST or w in GENERIC_LEXICON:
            continue
        if w not in SIGNATURE_LEXICON:
            continue
        stem = _normalize_stem(w)
        kind = "verb" if stem in {
            "stretch", "unfold", "carry", "crack", "haunt", "bruise"
        } else "image"
        score = signature_score(w, in_lexicon=True, kind=kind)
        phrases.append(
            SignaturePhrase(w, stem, score, kind, score >= SIGNATURE_THRESHOLD)
        )

    for m in re.finditer(r"[\"']([^\"']{3,40})[\"']", text):
        frag = m.group(1).strip()
        frag_words = re.findall(r"[A-Za-z']+", frag.lower())
        if any(w in TOPIC_BLACKLIST for w in frag_words):
            continue
        score = signature_score(frag, in_lexicon=False, kind="metaphor") + 0.2
        stem = _normalize_stem(frag_words[0]) if frag_words else frag
        phrases.append(
            SignaturePhrase(frag, stem, min(1.0, score), "metaphor", score >= SIGNATURE_THRESHOLD)
        )

    best: Dict[str, SignaturePhrase] = {}
    for p in phrases:
        cur = best.get(p.stem)
        if not cur or (p.score, len(p.phrase)) > (cur.score, len(cur.phrase)):
            best[p.stem] = p

    ordered = sorted(best.values(), key=lambda p: (-p.score, -len(p.phrase)))
    protected = [p.phrase for p in ordered if p.protected]
    return SignatureSet(ordered, protected, constructions)


def is_generic_reflective(question: str) -> bool:
    lower = (question or "").lower()
    return any(re.search(pat, lower) for pat in GENERIC_REFLECTIVE)


def loses_protected_language(callback: str, signatures: SignatureSet) -> bool:
    if not signatures.protected:
        return False
    lower = (callback or "").lower()
    return not any(
        p.stem in lower or p.phrase in lower for p in signatures.phrases if p.protected
    )


def uses_synonym_destruction(callback: str, signatures: SignatureSet) -> bool:
    lower = (callback or "").lower()
    words = set(re.findall(r"[a-z']+", lower))
    for p in signatures.phrases:
        if not p.protected:
            continue
        banned = SYNONYM_DESTRUCTION.get(p.stem, set())
        if any(b in words for b in banned) and p.stem not in lower and p.phrase not in lower:
            return True
    return False


def belongs_only_to_this_conversation(callback: str, signatures: SignatureSet) -> bool:
    if not callback or is_generic_reflective(callback):
        return False
    if not signatures.protected:
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
    candidates = [p for p in signatures.phrases if p.protected] or list(signatures.phrases)
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

    if stem == "stretch" or "stretch" in phrase:
        variants = [
            "So what actually got stretched out in you reading that?",
            "So what actually got stretched out for you?",
            "What part of your definition got stretched furthest?",
            "What got stretched out in you while you were reading that?",
        ]
        mem = list(_CONVERSATION_SIGNATURE_TERMS.get(conversation_id, []))
        idx = sum(1 for m in mem if m == "stretch") % len(variants)
        return variants[idx]

    table = {
        "carry": "What are you still carrying now that you've named it?",
        "crack": "What actually cracked?",
        "room": "What changed in the room after you saw it differently?",
        "script": "What part of the script stopped feeling inevitable?",
        "gravity": "What changed once the gravity shifted?",
        "mirror": "What did the mirror show you that the story was hiding?",
        "oxygen": "What got harder to breathe around once the oxygen thinned?",
        "weather": "What shifted in the weather of that moment once you named it?",
        "door": "What was on the other side of that door once you stopped pretending it was locked?",
        "weight": "What part of the weight got more honest once you stopped decorating it?",
        "shadow": "What in the shadow stopped looking like mystery and started looking like pattern?",
        "fingerprint": "Whose fingerprints are still on this now that you can see them?",
        "backstage": "What did you notice backstage that the performance was hiding?",
        "current": "Where is the current actually taking you now that you feel it?",
        "anchor": "What are you still using as an anchor that might be a weight?",
        "unfold": "What unfolded that you weren't ready to name yet?",
        "map": "What part of the map no longer matches the territory?",
        "signal": "What signal got clearer once the noise dropped?",
        "temperature": "What changed in the temperature of the room once the truth landed?",
        "echo": "What echo stayed after the performance ended?",
        "bridge": "What collapsed on the bridge once you stopped calling it solid?",
        "thread": "Which thread were you pretending wasn't already frayed?",
        "haunt": "What still haunts the room after you named it?",
        "bruise": "Where is the bruise more honest than the story?",
        "mask": "What was the mask protecting that the face can't?",
        "stage": "What dies when the stage lights go down?",
        "wound": "What does the wound know that the explanation doesn't?",
        "scar": "What did the scar keep after the story moved on?",
    }
    if stem in table:
        return table[stem]
    # Never fall back to topic-noun stapling
    return None


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
