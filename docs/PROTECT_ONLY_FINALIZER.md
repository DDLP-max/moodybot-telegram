# Protect-only finalizer contract (`protect-only-v1`)

## Philosophy

Generation creates.  
Finalization protects.  
Nothing else.

The finalizer is **infrastructure**, not authorship.

## The one question

Any future change to finalization must answer:

> Does this prevent a defect, or does it change the writing?

| Answer | Action |
|--------|--------|
| Prevents a defect | May belong in finalization |
| Changes the writing | Move into generation, or delete |

## Allowed (defect prevention)

1. Remove obvious hallucinated mechanics  
2. Remove generic assistant garbage  
3. Fix broken grammar/formatting  
4. Remove duplicated ideas  
5. Enforce safety  
6. **One** Gold-shape structural compression pass (`gold_shape.py`) when the draft shows:
   - premise restatement
   - thesis / mechanism repetition
   - post-payoff drift
   - stacked metaphor
   - CTA / verbal costume tail  
   Max: `draft → quality pass → one rewrite → return`. Never loop.

## Brand exception

`🥃` is intentional brand infrastructure (watermark), not a Signature Line.
It must remain the sole standard brand tail on normal replies.
No catchphrase before it.

## Forbidden (authorship)

- Creative voice rewrite, ornament, new metaphors, new examples  
- Add conclusions, callbacks, signature lines  
- Change openings for style  
- Score profoundness / quotability as a reason to rewrite  

## Ownership

The LLM owns: voice, cadence, metaphor choice, timing, humor, emotion.

Gold-shape pass only deletes / lightly compresses structural defects.
If generation is healthy, rewrite rate stays low — fix the prompt when it rises.

## Related modules

- Telegram: `response_finalization.py`, `gold_shape.py`, `recognition_landing.py`, `surface_render.py`  
- Web Dynamic: `utils/moodybotPostProcess.ts`, `utils/goldShape.ts`  
- Corpus: `training/moodybot-gold/`  
- Cursor rule: `.cursor/rules/protect-only-finalizer.mdc`  
