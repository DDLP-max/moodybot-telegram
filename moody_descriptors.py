# -*- coding: utf-8 -*-
import random
import re

# Define Moody-style replacements for clichéd emotional descriptors
MOODY_REPLACEMENTS = {
    r"\bbeautiful mess\b": [
        "poetic ruin", "shrapnel with grace", "storm dressed in softness",
        "half-healed wildfire", "midnight entropy", "chaos in eyeliner"
    ],
    r"\bdarling\b": [
        "cracked muse", "love-wrapped detour", "velvet complication",
        "whiskey-laced reverie", "soft disaster", "walking contradiction"
    ],
    r"\bsweetheart\b": [
        "soft-spoken ache", "bittersweet revenant", "ember-laced shadow",
        "quiet undoing", "soul in silk", "love's unfinished stanza"
    ],
    r"\bhoney\b": [
        "sun-warm ghost", "sugarcoated ache", "slow-burning mirror",
        "dripping sincerity", "glazed forgiveness", "wound with a smile"
    ]
}

def replace_moody_descriptors(text: str) -> str:
    for pattern, options in MOODY_REPLACEMENTS.items():
        text = re.sub(pattern, lambda _: random.choice(options), text, flags=re.IGNORECASE)
    return text