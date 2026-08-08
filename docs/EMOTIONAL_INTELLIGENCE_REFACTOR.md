# Emotional Intelligence Refactor — Audit & Migration Record

Date: 2026-08-07

## 1. Old architecture

- Prompt section `2_personality-engine` with 86 persona modules + spectrums
- Runtime emphasis: detect mood → pick persona stack → stylize reply
- Live Telegram path: slash commands + `STRUCTURE_PROMPTS` + compiled `system_prompt.txt`
- Parallel unused selector: `dynamic_persona_engine.py` (persona labels)

## 2. New architecture

```
INPUT → Intent → Emotional State → Pattern → Power/Incentives →
Boundary/Risk → Practical Intelligence → Emotional Shift → Voice → OUTPUT
```

Sections:

1. `1_emotional-architecture`
2. `2_intelligence-engine` (capabilities, interventions, worldview, packs)
3. `3_voice-engine` (inspiration sources, style modifiers)
4–10. formatting, safety, engagement, design, modulation, response, testing

## 3. Persona → capability mapping (core)

| Legacy | Capability / Intervention / Voice |
|---|---|
| Bourdain | Sensory Realism + Human Realism |
| CIA | Interrogative Analysis + Clipped Precision |
| Noir Detective | Pattern Forensics |
| Noir Romantic | Narrative Weight |
| Sam Neill | Weathered Wisdom |
| Munger | Latticework Judgment |
| Field Operator | Operational Intelligence |
| Builder | Prototype Thinking |
| Bob Ross | Gentle Stabilization |
| Velvet | Soft Emotional Precision |
| Clinical | Detached Analysis |
| Savage | High-Friction Confrontation |
| Rollins | Anger Mobilization |
| Dale/YOLO | Crash Intervention |
| Columbo | Interrogative Analysis + Informal Wisdom |
| Bond | Social Calibration |

Full alias table: `legacy_persona_aliases.json`

## 4–6. Files moved / renamed / created

### Moved
- `2_personality-engine/personas/*` → `3_voice-engine/inspiration-sources/`
- `2_personality-engine/spectrums/*` → `2_intelligence-engine/capability-packs/`
- `worldview-engine.md` → `2_intelligence-engine/worldview.md`
- `operator-heuristics.md` → `2_intelligence-engine/operator-heuristics.md`
- `module-framework.md` → `2_intelligence-engine/capability-framework.md`
- `tone-framework.md` → `3_voice-engine/voice-framework.md`
- Sections 3–9 renumbered to 4–10

### Created
- `2_intelligence-engine/emotional-intelligence-core.md`
- `2_intelligence-engine/capabilities/*.md` (31)
- `2_intelligence-engine/interventions/*.md`
- `3_voice-engine/style-modifiers/*.md` (14)
- `9_response-engine/dynamic-intelligence-routing.md`
- `9_response-engine/capability-composition-matrix.md`
- `9_response-engine/response-generation-order.md`
- `legacy_persona_aliases.json` / `.py`
- `tests/test_ei_routing.py`
- this document

### Stubbed (compat)
- `2_personality-engine/README.md` (deprecated pointer)
- `dynamic-persona-selection.md`, `persona-compatibility-matrix.md` → stubs

## 7. Legacy aliases retained

All major slash commands preserved as user-facing strings.
Mapped internally via `legacy_persona_aliases.json` and `mode-trigger-mapping.md`.

## 8. Runtime routing changes

- `dynamic_persona_engine.py` now returns capability bundles
- Method names kept for compatibility (`DynamicPersonaEngine`, `select_optimal_personas`)
- Manual `/cia`, `/noir`, `/validate`, `/savage`, `/munger` etc. still resolve

## 9. Prompt assembly changes

`build_system_prompt.py` ORDER updated to intelligence + voice sections (1–10).
Legacy `2_personality-engine` excluded from assembly.

## 10. Test changes

Behavioral tests for:
- relationship/boundary routing (doorman scenario)
- evidence vs inference preference
- slash alias resolution
- no requirement that celebrity names drive selection

## 11. Intentionally not renamed / not deleted

- Slash command strings (`/cia`, `/validate`, …)
- `STRUCTURE_PROMPTS` keys
- Brand name MoodyBot
- Inspiration source filenames (kept for creative DNA; banner marks non-runtime)
- Web marketing can still mention influences; no “Choose Persona” UI existed to remove

## 12. Acceptance checklist

- [x] Runtime selects capabilities first
- [x] Personas retained as inspiration / aliases
- [x] Manual commands preserved
- [x] Evidence vs inference + practical next action first-class
- [x] Web/Telegram share same engine docs via compiled prompt
- [x] Docs explain new model
