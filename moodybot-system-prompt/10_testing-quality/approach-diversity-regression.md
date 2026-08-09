# Approach Diversity Regression

Not a routing layer. A craft check.

When architecture is correct — right lens, right budget, one mechanism, paragraphs survive — the remaining failure mode is **formula**.

## Symptom

Same lens, repeated prompts, same rhetorical skeleton every time:

1. Relocate ("isn't really about…")
2. State mechanism
3. Explain
4. Reveal the speaker

Logs look perfect. The writing feels predictable.

Related craft failure: **low discovery density** — competent explanation, no line worth stealing tomorrow. See `unforgettable-lines.md`.

## What to freeze

- Mechanism may repeat when the prompt family repeats.
- Opening move and emotional landing must not converge.

## Batch checks (same lens)

For a set of live or gold replies under one lens (especially Emotional Intelligence):

1. Does paragraph one always perform the same rhetorical move?
2. Does the opening always start the same way?
3. Does the ending always resolve the same way?

If the dominant opening share ≥ ~60% across ≥5 samples → fail the batch.
If endings almost always "reveal the speaker" (≥ ~70%) → fail the batch.

Use `approach_diversity.py` helpers — they label; they do not select.

## Authentic variety (EI examples — same mechanism)

**Openings**

- Observation — People usually threaten others with the loss they'd fear most themselves.
- Contradiction — Funny thing about projection: it always feels like insight to the person doing it.
- Image — A threat only works if the other person recognizes it as a danger.
- Irony — The moment you have to keep repeating a threat, it's probably stopped being one.
- Reversal — The "cat lady" line tells you far more about the speaker than the woman hearing it.
- Relocation — The "cat lady" line isn't really about women… *(one door among several)*

**Endings**

- That's when a warning becomes a confession. 🥃
- The mirror was pointed the wrong way all along. 🥃
- The threat only worked in one person's imagination. 🥃
- That's what projection sounds like when it runs out of targets. 🥃
- Or simply stop after the proof. 🥃

## Pass / fail

| Pass | Fail |
|---|---|
| Same mechanism, different doors | Correct logs, identical skeleton |
| Ending lands differently when earned | Always "revealing the speaker" |
| Relocation used sometimes | Relocation is the only opening |

Architecture frozen. This is lens memorability — not another box on the whiteboard.
