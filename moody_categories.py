# -*- coding: utf-8 -*-
import random
import re

CATEGORY_KEYWORDS = {
    "love": ["love", "in love", "romantic", "crush", "partner", "relationship", "together"],
    "heartbreak": ["breakup", "left me", "cheated", "ghosted", "loss", "crying", "grief"],
    "flirt": ["hot", "sexy", "attractive", "kiss", "desire", "seduce"],
    "rage": ["hate", "revenge", "anger", "violent", "burn", "get back"],
    "self": ["who am i", "lost", "confused", "direction", "purpose", "identity"],
    "ambition": ["grind", "hustle", "goal", "career", "work", "legacy", "win", "build"],
    "grief": ["grief", "loss", "funeral", "passed", "miss them", "gone", "mourning"],
    "family": ["mom", "dad", "parent", "brother", "sister", "childhood", "home"],
    "latenight": ["3am", "late", "can't sleep", "awake", "night thoughts", "dark", "moon"],
    "existential": ["why", "meaning", "exist", "point", "identity", "life", "death"]
}

MOODY_CATEGORIES = {
    "love": {
        r"\bdarling\b": [
            "my ache wrapped in velvet", "delicate disaster", "my lullaby and hurricane"
        ]
    },
    "heartbreak": {
        r"\bdarling\b": [
            "ghost in my ribs", "scar that still sings", "love’s aftertaste"
        ]
    },
    "flirt": {
        r"\bdarling\b": [
            "sin in slow motion", "eye contact in a bottle", "my next mistake"
        ]
    },
    "rage": {
        r"\bdarling\b": [
            "fuel to my fire", "target with a smile", "unfinished retribution"
        ]
    },
    "self": {
        r"\bdarling\b": [
            "quiet echo of me", "shattered compass", "unfinished sentence"
        ]
    },
    "ambition": {
        r"\bdarling\b": [
            "delayed dopamine", "checklist ghost", "fire in a suit", "success wrapped in silence"
        ]
    },
    "grief": {
        r"\bdarling\b": [
            "absence with a name", "echo I sleep beside", "unspoken goodbye", "time’s unfinished apology"
        ]
    },
    "family": {
        r"\bdarling\b": [
            "bloodline ache", "love I didn’t earn but carry", "unfinished conversation", "legacy in my bones"
        ]
    },
    "latenight": {
        r"\bdarling\b": [
            "hour where ghosts stretch", "loneliness wrapped in velvet", "truth with insomnia", "dream’s draft folder"
        ]
    },
    "existential": {
        r"\bdarling\b": [
            "soul inside a question mark", "chaos with a conscience", "hope wearing doubt’s coat", "the echo behind every answer"
        ]
    }
}

def detect_category(text: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text.lower() for kw in keywords):
            return category
    return "default"

def replace_category_descriptors(text: str, category: str) -> str:
    if category in MOODY_CATEGORIES:
        for pattern, replacements in MOODY_CATEGORIES[category].items():
            text = re.sub(pattern, lambda _: random.choice(replacements), text, flags=re.IGNORECASE)
    return text