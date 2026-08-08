# -*- coding: utf-8 -*-
"""Extract conversational anchors from the user's original language.

Anchors are not generic keywords. They are the user's verbs, images, metaphors,
and framings that a Recognition Callback should echo and evolve.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


SIGNAL_VERBS = {
    "stretched", "stretch", "carrying", "carried", "carry", "collapsed", "collapse",
    "broke", "broken", "break", "opened", "open", "froze", "frozen", "freeze",
    "cracked", "crack", "cracking", "shifted", "shift", "changed", "change",
    "haunted", "haunt", "stuck", "dragging", "drag", "holding", "held",
    "sinking", "sank", "burning", "burned", "split", "splitting", "unraveled",
    "unravel", "tightened", "tighten", "loosened", "loosen", "named", "naming",
    "influence", "influenced", "trained", "scripted",
}

SIGNAL_IMAGES = {
    "door", "bridge", "script", "mirror", "room", "weather", "current", "gravity",
    "weight", "thread", "wound", "scar", "mask", "stage", "camera", "library",
    "bedroom", "bedrooms", "vocabulary", "language", "intimacy", "boundary",
    "pattern", "culture", "porn", "pornography",
}

# Weak words that often appear in generic reflective closers — not enough alone.
WEAK_ALONE = {"shift", "shifted", "change", "changed", "that", "this", "feel", "felt"}

STOP = {
    "the", "and", "for", "that", "this", "with", "from", "about", "have", "what",
    "when", "where", "which", "your", "you", "how", "did", "does", "are", "was",
    "were", "been", "into", "than", "then", "just", "like", "they", "them",
    "their", "would", "could", "should", "there", "here", "really", "something",
    "someone", "because", "between", "after", "before", "while", "reading",
    "moodybot", "please", "thanks", "hello",
}

GENERIC_REFLECTIVE = [
    r"familiar or alien",
    r"felt most familiar",
    r"does that resonate",
    r"what do you make of that",
    r"how does that land",
    r"what comes up for you",
]


@dataclass
class ConversationAnchors:
    verbs: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    metaphors: List[str] = field(default_factory=list)
    framings: List[str] = field(default_factory=list)
    user_anchors: List[str] = field(default_factory=list)
    draft_anchors: List[str] = field(default_factory=list)
    all_anchors: List[str] = field(default_factory=list)

    @property
    def primary(self) -> Optional[str]:
        for group in (self.metaphors, self.verbs, self.images, self.framings, self.user_anchors):
            if group:
                # Prefer non-weak alone anchors
                for item in group:
                    if item.lower() not in WEAK_ALONE:
                        return item
                return group[0]
        return None

    def contains_in(self, text: str, *, user_only: bool = False) -> bool:
        lower = (text or "").lower()
        pool = self.user_anchors if user_only else self.all_anchors
        strong = [a for a in pool if a.lower() not in WEAK_ALONE and len(a) > 2]
        if strong:
            return any(a.lower() in lower for a in strong)
        return any(a.lower() in lower for a in pool if len(a) > 2)


def _unique(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def _extract_quoted_or_emphatic(text: str) -> List[str]:
    found = []
    for m in re.finditer(r"[\"“]([^\"”]{3,40})[\"”]", text or ""):
        found.append(m.group(1).strip())
    for m in re.finditer(r"\b(?:got|get|feel like i'm|i'm|i am)\s+([a-z']{4,20})\b", (text or "").lower()):
        found.append(m.group(1))
    return found


def is_generic_reflective(question: str) -> bool:
    lower = (question or "").lower()
    return any(re.search(pat, lower) for pat in GENERIC_REFLECTIVE)


def extract_conversation_anchors(user_message: str, draft: str = "") -> ConversationAnchors:
    """Pull high-signal anchors from the user message (draft only as weak secondary)."""
    text = re.sub(r"^/\w+\s*", "", (user_message or "").strip())
    lower = text.lower()
    words = re.findall(r"[A-Za-z']+", lower)

    verbs = [w for w in words if w in SIGNAL_VERBS]
    images = [w for w in words if w in SIGNAL_IMAGES]

    framings: List[str] = []
    framing_patterns = [
        r"dirty talk",
        r"room changed",
        r"script changed",
        r"got stretched(?: out)?",
        r"still carrying",
        r"carrying this",
        r"cracked something",
        r"reference library",
        r"sexual vocabulary",
        r"between \d{4} and \d{4}",
    ]
    for pat in framing_patterns:
        m = re.search(pat, lower)
        if m:
            framings.append(m.group(0))

    metaphors = _extract_quoted_or_emphatic(text)
    for pat in (
        r"got stretched out",
        r"stretched out",
        r"carrying this",
        r"cracked something",
        r"the room changed",
        r"the script changed",
    ):
        m = re.search(pat, lower)
        if m:
            metaphors.append(m.group(0))

    subjectish = [
        w for w in words
        if len(w) > 4 and w not in STOP and w not in SIGNAL_VERBS
    ][:6]

    draft_anchors: List[str] = []
    if draft and (images or framings or any(t in lower for t in ("porn", "dirty", "culture", "script", "stretch"))):
        for w in re.findall(r"[A-Za-z']+", draft.lower()):
            if w in {"script", "library", "vocabulary", "intimacy"} and w not in images:
                draft_anchors.append(w)

    verbs = _unique(verbs)
    images = _unique(images)
    metaphors = _unique(metaphors)
    framings = _unique(framings + subjectish[:3])
    draft_anchors = _unique(draft_anchors)

    user_anchors = _unique(metaphors + verbs + images + framings)
    all_anchors = _unique(user_anchors + draft_anchors)

    return ConversationAnchors(
        verbs=verbs,
        images=images,
        metaphors=metaphors,
        framings=framings,
        user_anchors=user_anchors,
        draft_anchors=draft_anchors,
        all_anchors=all_anchors,
    )


def callback_echoes_anchor(
    callback: str,
    anchors: ConversationAnchors,
    *,
    user_only: bool = True,
) -> bool:
    if not (anchors.user_anchors if user_only else anchors.all_anchors):
        return True  # no anchors → fall back allowed
    if is_generic_reflective(callback):
        return False
    return anchors.contains_in(callback, user_only=user_only)


def evolve_anchor_callback(
    anchors: ConversationAnchors,
    *,
    subject: str = "",
    insight_hint: str = "",
) -> Optional[str]:
    """Build a recognition callback that evolves the user's anchor (not parrot)."""
    if not anchors.user_anchors and not anchors.all_anchors:
        return None

    primary = anchors.primary or (anchors.user_anchors[0] if anchors.user_anchors else anchors.all_anchors[0])
    p = primary.lower()
    subject = (subject or "").strip()
    insight_hint = (insight_hint or "").strip()
    blob = " ".join(anchors.user_anchors).lower()

    # Prefer stretch when present even if not primary
    if any("stretch" in a for a in anchors.user_anchors):
        if "intimacy" in (insight_hint + " " + subject + " " + blob).lower() or "dirty" in blob:
            return "So what got stretched out in your definition of intimacy after reading that?"
        return "So what actually got stretched out in you while you were reading that?"

    if any("carry" in a for a in anchors.user_anchors):
        return "What are you still carrying now that you've named it?"

    if any("crack" in a for a in anchors.user_anchors):
        return "What actually cracked once you stopped protecting the old story?"

    if "mirror" in blob:
        return "What did the mirror show you that the story was hiding?"

    if "room" in blob and "changed" in blob:
        return "What changed in the room once you stopped pretending it was still the same size?"

    if "script" in blob:
        return "What part of the script stopped feeling inevitable?"

    if "stuck" in blob:
        return "Where are you still stuck now that the pattern has a name?"

    if "dirty talk" in blob or ("dirty" in blob and "talk" in blob):
        if "script" in blob or "script" in insight_hint.lower() or any(
            a == "script" for a in anchors.draft_anchors
        ):
            return (
                "So what got clearer for you reading that - "
                "your definition of dirty talk, or how much the script itself changed?"
            )
        return "What changed in your sense of what now counts as ordinary dirty talk?"

    if "porn" in p or "pornography" in p or "porn" in blob:
        return "What part of the porn influence story stopped looking like the whole cause?"

    if "influence" in blob:
        return "Which influence suddenly looks louder once you stop hunting for a single cause?"

    if "language" in blob or "vocabulary" in blob:
        return "What in that language shift stopped sounding like edge and started sounding ordinary?"

    if "intimacy" in blob:
        return "What got wider in your definition of intimacy after reading that?"

    if "boundary" in blob:
        return "What boundary got sharper once the pattern had words around it?"

    if "pattern" in blob:
        return "Where have you seen this pattern before without naming it?"

    if "changed" in p or "change" in p or "shift" in p:
        other = next(
            (
                a for a in anchors.user_anchors
                if a.lower() not in WEAK_ALONE
            ),
            None,
        )
        if other:
            return f"What part of {other} stopped looking fixed once the change was visible?"
        return "What part of that change stopped feeling abstract and started feeling personal?"

    if subject and primary.lower() not in subject.lower():
        return f"What shifted in how you hold {primary} once {subject} came into focus?"
    return f"What about {primary} looks different now that you've seen it named?"
