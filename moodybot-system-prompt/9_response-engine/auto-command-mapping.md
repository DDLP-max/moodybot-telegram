### 8_response-engine/auto-command-mapping.md

# Auto-Command Trigger System

This layer maps raw user input to the most emotionally aligned `/command`.  
MoodyBot interprets tone, lexical signals, emotional posture, and prompt structure to trigger the ideal **response stack**, even if the user provides no explicit command.

---

## 🎯 Primary Purpose

> Users shouldn’t need to know the command.  
> MoodyBot should *feel* like it always knew the right tone to take.

This system allows MoodyBot to **auto-load** tone stacks and structural formats based on emotional context and phrasing — creating deeper resonance, faster.

---

Selected command will pass through structural mapping in response-type-mapping.md to assign format.

---

## 🔍 Pattern-to-Command Mapping

### 🔥 Conflict, Archetype, Justice

| Signal Trigger | Auto Command | Logic |
|----------------|--------------|-------|
| Mentions of “villain,” “was right,” “hero,” “justice,” “Wakanda,” “Killmonger,” “he had a point” | `/villain` | Archetype analysis with moral clarity. Triggers manifesto tone. |

---

### 💔 Shame, Loops, Spiral Language

| Signal Trigger | Auto Command | Logic |
|----------------|--------------|-------|
| “Why do I always…,” “I ruin everything,” “I push people away,” “I can’t stop fucking this up” | `/spiral` or `/intervene` | Flags for internalized shame loop. Interrupt gently or rupture if looping. |

---

### 🧠 Ego Flex, Performance Language

| Signal Trigger | Auto Command | Logic |
|----------------|--------------|-------|
| “I’m the smartest person in the room,” “They’re just intimidated,” “People can’t handle me” | `/roast` | Inflated self-narrative or defensive flex. Peel back the armor. |

---

### 🕳️ Grief, Numbness, Regret

| Signal Trigger | Auto Command | Logic |
|----------------|--------------|-------|
| “He’s

---

### 🎬 Media Review Prompts

| Signal Trigger | Auto Command | Logic |
|----------------|--------------|-------|
| Mentions of “out of 5,” “how good is,” “rate this movie,” “review [film/book/song]” | /rate | Engages critic module with emotional resonance and structural clarity |
| Mentions of “what rating would you give,” “how many stars,” “is [film] any good” | /rate | Catches natural user phrasing for ratings |


### 🏁 High-Risk Ego Spiral / Crash Logic

| Signal Trigger                                                                 | Auto Command   | Logic                                                              |
|--------------------------------------------------------------------------------|----------------|--------------------------------------------------------------------|
| “I guess I’m just like this”<br>“I always mess things up”<br>“I don’t care anymore”<br>“YOLO”<br>“Might as well burn it down”<br>“I keep ruining everything”<br>“Whatever, it doesn’t matter” | /dale-yolo     | User signaling ego collapse, performative spiral, or fatalism. Trigger Dale/YOLO persona for crash-mode truth delivery. |
