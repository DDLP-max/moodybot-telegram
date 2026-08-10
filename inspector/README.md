# Moody Inspector

Writer telemetry for MoodyBot. **Debugger, not another brain.**

Unit of work: improving sentences — not scrolling logs.

## Philosophy

Great editors don't start with trends. They start with today's pages, mark the unforgettable lines, circle the weak ones, and move on.

## Two ingestion paths

| Source | Role |
|--------|------|
| `moodybot.log` / `moodybot_log.txt` | Historical corpus (production truth) |
| `data/inspector/events.jsonl` | Clean live telemetry from finalize |

Same normalized event schema. Deduped by fingerprint (`prompt + output + prompt_hash + git_commit`).

Provenance labels in the UI:

- `moodybot.log`
- `live telemetry`
- `seeded regression example`

## Commands

```bash
python -m inspector seed
python -m inspector import-log moodybot_log.txt
python -m inspector import-log moodybot.log --since 2026-08-01
python -m inspector rebuild              # wipe index; keep Hall of Fame stars
python -m inspector rebuild --keep-seeds
python -m inspector watch moodybot_log.txt
python -m inspector serve 5055           # http://127.0.0.1:5055/inspector
```

## What you see

1. **Today's board** — totals, discoveries, last-line traps, mechanism summaries, drifting/improved lens
2. **Visual response list** — green / yellow / red cards with stealability
3. **Response page** — click a sentence → teach panel (verdict, why, examples)
4. **Killer filter** — e.g. every Emotional Intelligence reply that failed Last-line trap
5. **Hall of Fame notebook** — discoveries / spears / by lens
6. **Hit-rate graph** — % of replies that accidentally create something worth stealing

## Metric

**Stealability** (not “memorability”): would someone steal this sentence?
