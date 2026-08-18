# Moody Inspector

Writer telemetry for MoodyBot. **Debugger, not another brain.**

Unit of work: improving sentences — not scrolling logs.

## Philosophy

Great editors don't start with trends. They start with today's pages, mark the unforgettable lines, circle the weak ones, and move on.

### Asymmetric regression protection

Most teams protect against bugs.
Moody also protects against losing great writing.

That is an **Inspector principle**, not a pipeline layer.

| | Hall of Fame | Canonical |
|---|---|---|
| Size | Growing (thousands) | Small (≈30–50) |
| Role | Training signal | Identity regression suite |
| Question | Steal this sentence? | If Moody couldn't write these, has identity broken? |

See [`CANONICAL.md`](CANONICAL.md).

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
python -m inspector canonical            # identity quality floor after craft changes
```

## What you see

1. **Today's board** — totals, discoveries, last-line traps, mechanism summaries, drifting/improved lens
2. **Visual response list** — green / yellow / red cards with stealability
3. **Response page** — click a sentence → teach panel (verdict, why, examples)
4. **Killer filter** — e.g. every Emotional Intelligence reply that failed Last-line trap
5. **Hall of Fame notebook** — discoveries / spears / by lens / by type (growing)
6. **Hit-rate graph** — % of replies that accidentally create something worth stealing
7. **Canonical Suite** — hand-picked never-regress floor (separate from Hall)

## Metric

**Stealability** (not “memorability”): would someone steal this sentence?

## Canonical (protect successes)

After significant craft changes, run:

```bash
python -m inspector canonical
```

Seed floor:

```
✓ Foreplay
✓ Prison
✓ McDonald's
✓ Cat Lady
✓ Breaking Bad
✓ Different Things
```

Not identical wording — quality floor. Details: [`CANONICAL.md`](CANONICAL.md).

## Future metric (not built yet): Forced Frame Shift

When a reply cannot attack Moody’s mechanism and must change the subject to answer, that is a frame shift.

Example: Moody reframes *foreplay* as hierarchy-in-language → rebuttal pivots to biology/reproduction.

Interesting later: reply-type mix (direct agreement / disagreement / frame shift / personal attack) — evidence the observation changed the terrain. Not likes. Not yet.
