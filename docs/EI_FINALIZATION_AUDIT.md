# EI Finalization Audit

**Date:** 2026-08-08  
**Repo:** `DDLP-max/moodybot-telegram` (Python Telegram bot)  
**Scope:** Why epistemic calibration and recognition callbacks lose in production

---

## Root Cause

Production treats intelligence rules as **prompt suggestions**, not **runtime gates**.

The model draft goes to the user after light polish. Generic CTAs and overconfident causal claims survive because nothing authoritative rewrites them.

| Rule | Status before this work |
|------|-------------------------|
| Epistemic calibration | Prompt-only (`epistemic-calibration.md` in `system_prompt.txt`) |
| Recognition callbacks | Hybrid: strategy injected + logged; **no rewrite** |
| Generic CTA ban | Pattern detect + log warning only |
| Engagement CTA append | `message_utils.maybe_append_cta` can still append after a valid closer |
| Capability routing | `dynamic_persona_engine.py` exists but is **not wired** into `handle_message` |

---

## Production Flow (actual)

```
Telegram Update
  → moodybot.handle_message
  → route_command / select_best_command   (slash + keyword; default /thoughts)
  → messages = [
        closer_instruction(strategy),     # recognition_callbacks.py
        STRUCTURE_PROMPTS[cmd]?,          # structure_prompts.py
        load_system_prompt(),             # full system_prompt.txt
        user_input
     ]
  → OpenRouter (single pass)
  → process_bot_output                    # postprocessing.py (cosmetic)
  → legacy polish (descriptors, paragraphs, 🥃)
  → log is_generic_followup               # NO REWRITE
  → send_message → strip_known_ctas → maybe_append_cta → HTML
```

**Missing stage:** FINALIZATION PASS between polish and send.

---

## Prompt Assembly

`build_system_prompt.py` ORDER:

1. emotional-architecture  
2. intelligence-engine  
3. voice-engine  
4. formatting-structure  
5. safety-protocols  
6. engagement-conversion  
7. design-process  
8. emotional-modulation  
9. response-engine  
10. testing-quality  

Per section: alpha-sorted `.md` files, then nested dirs.  
READMEs skipped. Legacy trees (`2_personality-engine`, `8_response-engine`) are **not** in ORDER.

**Problem:** Engagement / design-process goals (“Start a thread”, “Invite confession”, “Lead to Premium CTA”) appear **before** response-engine rules. Without a late enforcement block, earlier engagement goals compete with closer discipline.

---

## CTA / Closer Overwriters

1. Model draft (may invent “If you want… say the word”)
2. Legacy polish (usually does not strip closers)
3. Whiskey emoji append
4. `strip_known_ctas` (share 🔁 lines only)
5. `maybe_append_cta` (env CTAs for flirt/social/etc.) — **can overwrite a clean closer**
6. Prompt-level mirrorback / poetic CTA instructions

---

## Conflicting Legacy Rules

| File | Conflict |
|------|----------|
| `7_design-process/output-goal-evaluator.md` | Behavioral goals: share / thread / confession / Premium CTA |
| `6_engagement-conversion/comment-bait-strategy.md` | “Want me to say it cruel or kind?” |
| `1_emotional-architecture/mirrorback-tags.md` | “Max one per reply” at end — can fight SILENCE/NONE |
| `structure_prompts.py` | Still says “poetic CTA” on some slash commands |
| `8_response-engine/response-length-tiers.md` | Legacy “one CTA” (not in ORDER, but confusing on disk) |
| `docs/EMOTIONAL_INTELLIGENCE_REFACTOR.md` | Claims runtime capability selection; production does not |

---

## Web vs Telegram

- **User-facing replies:** Telegram (`moodybot.py`)
- **Web in this repo:** Flask admin/ops (`main.py`), not the chat engine
- Finalization must live in one shared Python module so any future web Dynamic Mode can call the same function

---

## Fix Direction (implemented)

1. `response_finalization.py` — authoritative post-generation stage  
2. Generic-CTA + epistemic rewrite as deterministic gates  
3. Recognition callbacks generated/replaced when strategy requires them  
4. `send_message(..., allow_cta=False)` on intelligence replies  
5. `final-quality-gates.md` + critical modules appended last in `build_system_prompt.py`  
6. Engagement goals demoted to secondary in output-goal-evaluator / comment-bait  

Engagement is last. Truth and closing integrity win.

---

## Prompt hash (post-fix)

See `prompt_meta.json` after `python build_system_prompt.py`.

Critical tail order (expected):

- evidence-vs-inference  
- epistemic-calibration  
- practical-next-action  
- recognition-callbacks  
- response-generation-order  
- final-quality-gates (last)
