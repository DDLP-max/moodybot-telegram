# -*- coding: utf-8 -*-
"""Approach diversity — formula detection for same-lens batches (not routing)."""

from approach_diversity import (
    classify_opening_move,
    ending_is_reveal_speaker,
    endings_too_convergent,
    openings_too_convergent,
)
from response_finalization import lens_voice_guidance


# Same projection mechanism — five different authentic doors
DIVERSE_EI = [
    "People usually threaten others with the loss they'd fear most themselves.\n\n"
    "When the fear isn't shared, the threat stops working.",
    "Funny thing about projection: it always feels like insight to the person doing it.\n\n"
    "That's why the cat lady line keeps getting repeated.",
    "A threat only works if the other person recognizes it as a danger.\n\n"
    "Singledom only scares the person holding the threat.",
    "The moment you have to keep repeating a threat, it's probably stopped being one.\n\n"
    "The volume is the tell.",
    "The \"cat lady\" line tells you far more about the speaker than the woman hearing it.\n\n"
    "That's the whole move.",
]

FORMULA_EI = [
    'The "cat lady" line isn\'t really about women. It\'s a man naming the future he\'d fear most.',
    "This isn't really about marriage. It's about loneliness dressed as advice.",
    "The jab isn't really about cats. It's about his own empty apartment.",
    "Her choice isn't really about independence. It's about his fear of being alone.",
    "The insult isn't really about her life. It's about what would break him.",
]


def test_ei_guidance_has_approach_diversity():
    g = lens_voice_guidance("Emotional Intelligence").lower()
    assert "approach diversity" in g
    assert "observation" in g and "contradiction" in g and "reversal" in g
    assert "isn't really about" in g  # allowed
    assert "not mandatory" in g or "do not always open" in g
    assert "revealing the speaker" in g  # warned as overused landing


def test_classifies_diverse_openings():
    moves = [classify_opening_move(s) for s in DIVERSE_EI]
    assert "observation" in moves
    assert "contradiction" in moves
    assert "reversal" in moves
    assert len(set(moves)) >= 4


def test_formula_batch_flagged_convergent():
    assert all(classify_opening_move(s) == "relocation" for s in FORMULA_EI)
    assert openings_too_convergent(FORMULA_EI) is True
    assert openings_too_convergent(DIVERSE_EI) is False


def test_ending_reveal_speaker_convergence():
    reveal_heavy = [
        "People project. It ends up revealing the speaker.",
        "The threat fails. Starts revealing the speaker.",
        "Projection again. Always revealing the speaker.",
        "Same move. About the speaker every time.",
        "That's revealing the speaker once more.",
    ]
    varied = [
        "People project. That's when a warning becomes a confession.",
        "The threat only worked in one person's imagination.",
        "That's what projection sounds like when it runs out of targets.",
        "People usually threaten others with the loss they'd fear most themselves.",
        "The volume is the tell.",
    ]
    assert ending_is_reveal_speaker(reveal_heavy[0])
    assert endings_too_convergent(reveal_heavy) is True
    assert endings_too_convergent(varied) is False


def test_regression_doc_exists():
    from pathlib import Path

    p = Path("moodybot-system-prompt/10_testing-quality/approach-diversity-regression.md")
    text = p.read_text(encoding="utf-8").lower()
    assert "not a routing layer" in text
    assert "approach diversity" in text or "rhetorical" in text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
