# MoodyBot Gold

Reverse-engineered from historical MoodyBot outputs in `moodybot_log.txt`
(~4,909 User/MoodyBot pairs).

## Goal

Discover the style MoodyBot was already capable of at its best —
not invent a new style, and not change architecture.

## What “Gold” means

Scored on **writing quality**, never on agreement with the user.

A response is Gold only if it:

- reframes the premise
- contains one memorable line
- feels conversational, not essayistic
- uses concrete language
- has one clean insight
- stops before overexplaining
- sounds like an intelligent human, not a textbook

Rejected for: stacked metaphors, prompt-engineering tells, “the truth is…”,
engagement bait, fake profundity, therapy language, abstract systems jargon,
AI-sounding sentences, unnecessary paragraphs.

## Files

| File | Purpose |
|------|---------|
| `gold.json` / `gold.jsonl` | Gold examples with schema fields |
| `stats.json` | Corpus statistics |
| `pattern-analysis.md` | Recurring patterns + numbers |
| `style-guide.md` | Descriptive style of best outputs (not a prompt) |
| `prompt-gap-analysis.md` | Where current prompt diverges from Gold behavior |
| `_curate_hand.py` | Curation script (reproducible fingerprints) |

## Schema

```json
{
  "id": "gold-001",
  "original_user_prompt": "...",
  "assistant_response": "...",
  "category": "...",
  "why_it_works": "...",
  "memorable_line": "...",
  "structure": "SNAP | KNIFE | STORY"
}
```

### Structures

- **SNAP** — 1–2 sentence punchline
- **KNIFE** — Reframe → short explanation → stop
- **STORY** — Observation → concrete example → deeper implication → stop

## Method

1. Parse all pairs from `moodybot_log.txt` (the production conversation corpus;
   the tiny `moodybot.log` file is only a process stub).
2. Hard-reject banned phrases, CTA spam, multi-metaphor costume, therapy/systems jargon.
3. Hand-curate fingerprints of responses that clear a true **9/10** writing bar.
4. Drop residual manufactured closers / fake profundity on re-read.
5. Compute statistics only on the final Gold set.

**Final Gold count: 18** (from 4,909 pairs).

This is intentionally strict. The log contains many 7/10 and 8/10 replies;
Gold keeps only responses that still feel inevitable after the costume era,
engagement era, and systems-jargon era are stripped away.
