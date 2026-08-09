# Moody Inspector

Debugger for live MoodyBot replies. Not another routing layer.

Raw logs feed the tool — your eyes read cards.

## What it shows

- Prompt / Output
- Pipeline (claim → lens → budget → structure → Gold)
- Editor metrics (paragraphs, mechanisms, spear)
- Clickable craft checks (discovery, spokenness, over-confirming)
- Scores: Architecture / Lens fidelity / Writing / Memorability
- Diff vs a prior reply
- Hall of Fame (starred stealable lines)

## Run locally

```bash
python -m inspector seed          # sample cat-lady iterations
python -m inspector serve 5055    # http://127.0.0.1:5055/inspector
```

Or start the Flask app (`main.py`) and open `/inspector`.

## Live capture

Telegram `finalize_response` appends each reply to `data/inspector/events.jsonl`
(override with `MOODYBOT_INSPECTOR_DIR`).

On Render, mount a disk at that path if you want events to survive deploys.

## Hall of Fame

Star a discovery from any card. Lines land in `hall_of_fame.jsonl` —
better training signal than whole outputs for discovery density.
