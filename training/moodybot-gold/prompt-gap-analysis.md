# Prompt gap analysis — current MoodyBot prompt vs Gold corpus

**Objective:** list places where the current prompt stack encourages behavior
the Gold corpus almost never exhibits.

**Not in scope:** rewriting the prompt. Architecture unchanged.

Gold reference: `training/moodybot-gold/` (n=18 elite historical replies).
Prompt reference: `moodybot-system-prompt/` + compiled `system_prompt.txt`
+ live `CORE_WRITE_DIRECTIVE` in `response_finalization.py`.

---

## Method

For each gap:

1. What the prompt encourages
2. What Gold actually does
3. Why it matters

---

## Gaps

### 1. Signature Line / Recognition Callback machinery still exists as a taught object

**Prompt encourages**
- Entire modules: `signature-line.md`, `recognition-callbacks.md`
- `response-type-mapping.md` maps many intents to “Recognition Callback”
- Even when marked optional/off, the prompt still teaches the *shape* of a manufactured closer

**Gold almost never**
- Appends a separate quotable closer after the body lands
- Ends with ritual lines like “You’ll taste this when the room gets quiet”
- Treats ending as a product feature

**Gap**
Gold endings are simply where the thought stops. The prompt still spends
surface area teaching an ending genre Gold rejects.

---

### 2. Engagement / share / CTA systems remain in the stack

**Prompt encourages**
- `6_engagement-conversion/` (share triggers, comment bait, CTA integrity)
- Formatting README still frames “CTA integrity” as structural
- Historical log shows Tag/Mention/@MoodyBotAI tails were once common

**Gold almost never**
- Asks for tags, shares, confessions-to-the-brand
- Ends with engagement bait questions as the point of the reply

**Gap**
Gold is anti-engagement-theater. Any remaining CTA/share pedagogy pulls
generation toward behaviors absent from the best historical writing.

---

### 3. Emotional-arc / structure checklists

**Prompt encourages**
- `structure-checklist.md`: “Contains emotional arc (shift from A → B)”
- Length-tier language about “prefer one quotable”
- Response-type tables that prescribe arc + callback by category

**Gold almost never**
- Performs an emotional arc as choreography
- Builds A→B theater when a single cut would do
- Optimizes for quotability as a separate deliverable (the line emerges from the insight)

**Gap**
Checklists push performance of structure. Gold performs insight, then silence.

---

### 4. Poetic / noir / gothic permission surfaces

**Prompt encourages**
- Gothic flourish / mythic line permission modules
- Persona notes that still mention noir / poetic depth
- Mode escalation toward poetic modules

**Gold almost never**
- Stacks mythic lines
- Relies on whiskey-bar / noir costume for authority
- Uses multiple metaphors per reply (~0.11 `like a`/`as if` per Gold response)

**Gap**
Permission to ornament is enough to reintroduce costume Gold discarded.
Recent write rules say “do not require” poetry — but older modules still
offer it as craft.

---

### 5. Internal analytical vocabulary is still named extensively in-prompt

**Prompt encourages**
- Long INTERNAL ONLY lists: incentive structure, narrative contract, coherence,
  epistemic calibration, pattern forensics, governing mechanism, etc.
- “Governing pattern” as a mandatory pipeline noun

**Gold almost never**
- Speaks those labels aloud
- Sounds like pattern-forensics documentation

**Partial credit**
Current `CORE_WRITE_DIRECTIVE` correctly bans dumping these into prose.
Gold supports that ban.

**Remaining gap**
Naming the forbidden vocabulary at length still primes the model to think
in those tokens. Gold’s best lines invent ordinary nouns (loyalty program,
courtroom, stupid machine) without visiting the jargon list at all.

---

### 6. Over-specified generation procedures

**Prompt encourages**
- Multi-step mandatory order: intent → evidence → governing pattern →
  translate → write → thesis tests → distraction test → cross-examination →
  trust-the-reader → concrete diction…
- Multiple overlapping docs (`insight-first`, `thesis-discipline`,
  `trust-the-reader`, `thinking-vs-writing`, `concrete-before-abstract`)

**Gold almost never**
- Feels like compliance with a procedure
- Shows seams of “I am now translating my governing pattern”

**Gap**
The *content* of recent rules (one thesis, stop, concrete speech) matches Gold.
The *quantity* of procedural instruction does not. Gold reads like judgment,
not like a completed checklist.

---

### 7. Length / completeness pressure from older modules

**Prompt encourages**
- Cultural analysis paths: Observation → Drivers → Nuance → Consequence
- Business paths: System → Incentive → Leverage
- Implicit completeness across response-type mapping

**Gold profile**
- Median ~66 words, ~1.1 paragraphs
- KNIFE dominates (reframe → short proof → stop)
- Does not walk four-stage analytical ladders unless every rung is necessary

**Gap**
Older type-mapping still asks for more stages than Gold uses.

---

### 8. “Quotable line” as a goal vs. quotable line as a byproduct

**Prompt encourages**
- Quotable-lines modules / share frameworks / “prefer one quotable”
- Signature Line doctrine (even disabled) that treats the last sentence as craft object

**Gold**
- 100% contain a short memorable sentence
- But it is usually the thesis or the proof spike, not an appended mic-drop

**Gap**
Optimizing for quotability produces tacked-on endings.
Gold’s quotability is a side effect of a clean cut.

---

### 9. Agreement / validation openings

**Prompt residue**
- Softer witness / confession paths can lean mirror-first
- Engagement-era habits in the historical log: “You’re not alone…” essays

**Gold**
- ~56% begin with contradiction / premise relocation
- ~6% begin with agreement
- Validation is not the product; rearrangement is

**Gap**
Any prompt path that rewards soothing agreement first fights the Gold open.

---

### 10. Rhetorical questions as engagement device

**Prompt / history**
- Comment-bait and older closers use questions to continue the thread
- Some Gold replies still contain a question, but sparsely (0.44 avg)

**Gold**
- Questions are rare and usually structural (“is it?”) or diagnostic
- Not “What do you think?” / “Agree?” / confession prompts

**Gap**
Prompt material that treats questions as engagement tools diverges from Gold.

---

### 11. Systems-explanation pride

**Prompt**
- “MoodyBot sees systems” appears as brand identity (useful)
- Risk: models perform systems-seeing by *talking about systems*

**Gold**
- Sees systems; speaks human
- “Loyalty program,” “courtroom,” “filter,” “scenery” — never “incentive architecture”

**Gap**
Identity line is right; surrounding analytical celebration still risks essay diction.
Gold never congratulates itself for sophistication.

---

### 12. Multi-insight generosity

**Prompt tension**
- Trust-the-reader / thesis-discipline now fight this (aligned with Gold)
- Older modules still reward “nuance,” “possible drivers,” extra layers

**Gold**
- One idea. Spear, not handful.
- Bonus insights are treated as defects

**Gap**
The stack is inconsistent: new rules say one thesis; old mapping still
invites extra drivers/nuance stages.

---

## Where the current prompt already matches Gold

Do not “fix” these away — they are converging on the corpus:

- Concrete before abstract / speak concretely
- Insight first / stop when body lands
- Trust the reader / no triple restatement
- Thesis discipline / one spine
- Protect-only finalizer (does not rewrite into costume)
- Explicit bans on Signature Line / CTA as mandatory

These are the parts of the present stack that look like reverse-engineering
Gold rather than inventing costume.

---

## Summary table

| Prompt pressure | Frequency in Gold |
|-----------------|-------------------|
| Manufactured closer / Signature Line | ~0 |
| CTA / tag / share tail | ~0 |
| Multi-metaphor costume | ~0 (≤1 image, rare) |
| Emotional-arc choreography | ~0 |
| Therapy language | ~0 |
| Engine jargon in prose | ~0 |
| Four-stage analytical ladders | rare |
| Premise rejection / relocation open | common (~56%) |
| One memorable load-bearing line | always |
| Stop after payoff | always |
| Short spoken sentences | always |

---

## Conclusion

The Gold corpus says MoodyBot’s best historical writing was already:

**cut → name → prove once → stop.**

The current prompt is partially catching up (especially recent generation
directives), but still carries older machinery that teaches:

**arc → ornament → quotable → callback → engage.**

That older machinery is the gap.

Do not invent a new style to close it.
Remove or silence the pressures Gold never obeyed —
when you are ready to change the prompt.
