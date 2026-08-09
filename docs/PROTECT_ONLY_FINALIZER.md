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

## Forbidden (authorship)

- Improve / tighten / compress / rewrite prose  
- Add conclusions, transitions, callbacks, signature lines  
- Change cadence, rhythm, openings, endings, sentence order  
- Insert or replace examples  
- Score profoundness, memorability, landing quality, quotability  

## Ownership

The LLM owns: voice, cadence, paragraphing, sentence length, metaphor, timing, humor, surprise, emotion, rhythm.

If a generated response is already coherent, insightful, and well-paced: **do not touch it.**

## Success metric

Average creative rewrites performed by finalization ≈ **0**.

If finalization rewrites most responses, the generator/prompt is wrong. Fix generation — not the output.

## Related modules

- Telegram: `response_finalization.py`, `recognition_landing.py`, `surface_render.py`  
- Web Dynamic: `utils/moodybotPostProcess.ts`, `utils/recognitionLanding.ts`  
- Cursor rule: `.cursor/rules/protect-only-finalizer.mdc`  
