# Prompt gap analysis — current MoodyBot prompt vs Gold corpus

**Objective:** list places where the current prompt stack encourages behavior
the Gold corpus almost never exhibits.

**Not in scope:** rewriting the prompt. Architecture unchanged.

Gold reference: `training/moodybot-gold/` (n=19 elite replies — historical log + canonical craft).
Prompt reference: `moodybot-system-prompt/` + compiled `system_prompt.txt`
+ live directives in `response_finalization.py`.

---

## Method

For each gap:

1. What the prompt encourages
2. What Gold actually does
3. Why it matters

---

## Gaps that remain

### 1. Signature Line / Recognition Callback machinery still exists as a taught object

**Prompt encourages**
- Entire modules: `signature-line.md`, `recognition-callbacks.md`
- `response-type-mapping.md` and `response-generation-order.md` still teach the shape
- Even when marked optional/off, the prompt still spends tokens on manufactured closers

**Gold almost never**
- Appends a separate quotable closer after the body lands
- Ends with ritual lines like “You’ll taste this when the room gets quiet”
- Treats ending as a product feature

**Gap**
Gold endings are simply where the thought stops. The prompt still teaches an ending genre Gold rejects.

---

### 2. Engagement / share / CTA systems remain in the stack

**Prompt encourages**
- `6_engagement-conversion/` (share triggers, comment bait, CTA library, CTA structure)
- Ogilvy/Draper copy cores with “One Clear CTA”
- Brand CTA lines that invite tags, confessions, and public performance

**Gold almost never**
- Asks for tags, shares, confessions-to-the-brand
- Ends with engagement bait as the point of the reply

**Gap**
Gold is anti-engagement-theater. Remaining CTA/share pedagogy pulls generation toward behaviors absent from the best historical writing.

---

### 3. Length-tier and “quotable” pedagogy can inflate replies past the Gold stop

**Prompt encourages**
- Historical length-tier language and quotable-line modules
- Some personas still perform “atmospheric” extension

**Gold almost never**
- Continues after the payoff
- Adds a second insight “for completeness”
- Averages ~48 words; median ~34

**Gap**
Anything that rewards development-for-its-own-sake fights Gold’s primary craft move: stop.

---

### 4. Systems language still exists in capability / worldview modules

**Prompt encourages**
- Capability packs and operator language that name incentives, architectures, engines
- Internal vocabulary that can leak to the surface if translation fails

**Gold almost never**
- Says “governing incentive structure,” “identity architecture,” “pattern recognition engine”
- Sounds like a systems diagram narrating itself

**Gap**
Gold thinks abstractly and speaks concretely. Prompt surface area that models jargon increases leak risk even when `concrete-before-abstract` exists.

---

### 5. Therapy-adjacent and validation personas still live in the stack

**Prompt encourages**
- Soft emotional precision / validation capabilities
- Inspiration sources that comfort without always cutting

**Gold almost never**
- Opens with validation theater
- Sounds like a psychology textbook
- Narrates the reader’s inner movie to completion

**Gap**
Gold names the mechanism and trusts the reader. Soft-validation pathways compete with that instinct.

---

### 6. Persona costume and “voice flavor” menus exceed Gold’s actual range

**Prompt encourages**
- Large inspiration-source and style-modifier catalogs (noir, velvet, savage, etc.)
- Mode escalation that layers flavor when the quote is flat

**Gold almost never**
- Needs a costume to land
- Stacks atmospheric modifiers
- Sounds like a different celebrity each turn

**Gap**
Gold’s identity is mechanism + spoken English. Flavor menus invite imitation that Gold does not require.

---

### 7. “Always / mandatory” instructional density

**Prompt encourages**
- Many hard rules across modules (always translate, always rhythm, always…)
- High instructional volume in the assembled `system_prompt.txt` (~200+ sections)

**Gold almost never**
- Reads like compliance with a checklist
- Needs dozens of constraints to sound human

**Gap**
Volume of instruction can produce checklist prose — the opposite of Gold’s casual inevitability.

---

## Gaps that have narrowed (keep protecting)

These used to be larger failures; craft work moved toward Gold. Do not regress:

| Gold behavior | Craft that protects it |
|---------------|------------------------|
| Object-first on taste/entertainment | Lens drift + early-noun checks; Law 5c |
| Stealable discovery over explanation | Mode 1 ceiling; unforgettable-lines; EI Mode 2 |
| Escape the author’s frame | Paraphrase collapse; prison-cell standard |
| Short stop after payoff | Gold/Editor compression; Canonical Suite |
| No viewer psych on Breaking Bad-class prompts | Bourdain routing + object-first invariant |

Canonical Suite (`python -m inspector canonical`) is the regression floor for these wins.

---

## Highest-leverage prompt mismatches (if prioritized later)

1. **CTA / engagement / Signature Line surface area** — Gold has ~0% of this; prompt still teaches it.
2. **Instructional volume** — Gold is short; the compiled prompt is enormous.
3. **Costume/persona menus** — Gold is one voice noticing differently; not a wardrobe.
4. **Systems jargon residences** — Gold never says the machinery aloud.

Do not rewrite yet.
Discover first. Preserve what already worked.
Then remove prompt pressure that fights the Gold floor.

---

## Bottom line

The Gold corpus shows MoodyBot was already capable of:

- premise relocation
- one memorable line
- concrete speech
- early stop

The current prompt still spends significant weight on behaviors Gold almost never exhibits (engagement theater, manufactured closers, costume, systems talk).

Architecture stays frozen.
The style was found in history — not invented in instructions.
