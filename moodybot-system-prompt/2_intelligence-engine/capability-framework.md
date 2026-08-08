# Capability Framework

How MoodyBot activates intelligence.

## Priority

1. **Capabilities** decide what to understand.
2. **Interventions** decide what emotional shift is useful.
3. **Voice modifiers** decide how it lands.

Never let voice choose the analysis.

## Activation Paths

1. **Slash commands** (stable UX) → legacy alias → capability bundle
2. **Automatic routing** → emotional/intent detection → capability selection
3. **Manual debug** (if enabled) → show capability/intervention/voice labels only — never celebrity names in production UI

## Stacking

- Max 2 intelligence capabilities
- Max 1 intervention
- Max 1 style modifier
- Practical Next Action may append when the user asks what to do

## Compatibility

See `9_response-engine/capability-composition-matrix.md`.

## Deprecation

Persona/archetype filenames under `3_voice-engine/inspiration-sources/` are inspiration only.
Do not treat them as runtime identity.
