# Emotional State Detection Engine

Real-time analysis of user input to detect emotional states, content types, and tone indicators for optimal persona selection.

---

## Detection Categories

### 1. Emotional State Detection

#### Vulnerability Indicators
- **Direct Confession**: "I feel...", "I'm struggling with...", "I don't know how to..."
- **Self-Doubt**: "Maybe I'm just...", "I guess I always...", "I don't think I can..."
- **Seeking Help**: "Can you help me...", "What should I do...", "I need advice..."
- **Emotional Exposure**: Crying emojis, raw honesty, personal revelations

#### Defensiveness Patterns
- **Justification**: "But I had to...", "You don't understand...", "It's not my fault..."
- **Deflection**: "What about you...", "Everyone else does...", "That's not the point..."
- **Intellectual Posturing**: Complex vocabulary, philosophical tangents, "Actually..."
- **Performance**: Overly dramatic language, attention-seeking behavior

#### Validation Seeking
- **Approval Requests**: "Am I right?", "Does this make sense?", "What do you think?"
- **Achievement Sharing**: "I finally...", "Look what I did...", "I'm proud of..."
- **Comparison Seeking**: "Is this normal?", "Do other people...", "Am I the only one..."

#### Ego States
- **Collapse**: "I give up", "Whatever", "I don't care anymore", "YOLO"
- **Spiral**: "I always mess up", "I'm just like this", "Nothing ever works"
- **Superiority**: "Obviously...", "Anyone can see...", "It's simple really..."

### 2. Content Type Classification

#### Confession/Revelation
- Personal stories, secrets, admissions
- Emotional breakthroughs, realizations
- Past trauma, current struggles

#### Question/Inquiry
- Seeking advice, information, perspective
- Philosophical questions, "what if" scenarios
- Practical help requests

#### Statement/Declaration
- Opinions, beliefs, observations
- Life updates, current situations
- Cultural commentary, reviews

#### Request/Demand
- Specific help, validation, attention
- Roleplay requests, persona demands
- Emotional support needs

### 3. Tone Pattern Recognition

#### Sarcasm/Irony
- "Oh great...", "Sure, because...", "Obviously..."
- Contextual mismatch between words and situation
- Overly dramatic or exaggerated language

#### Sincerity/Authenticity
- Raw, unfiltered expression
- Consistent emotional language
- Personal vulnerability without performance

#### Performative/Attention-Seeking
- Overly dramatic language
- Inconsistent emotional states
- Language that seems designed for effect

#### Intellectual/Philosophical
- Complex vocabulary, abstract concepts
- "Deep" questions, existential themes
- Academic or theoretical language

---

## Detection Algorithm

### Step 1: Keyword Analysis
- Scan for emotional keywords and phrases
- Identify content type markers
- Detect tone indicators

### Step 2: Pattern Recognition
- Analyze sentence structure and rhythm
- Identify emotional escalation patterns
- Detect context shifts

### Step 3: Context Window Analysis
- Review last 3-5 exchanges
- Track emotional progression
- Identify conversation themes

### Step 4: State Classification
- Assign primary emotional state
- Determine content type
- Classify tone pattern
- Calculate confidence score

---

## Confidence Scoring

- **High (90%+)**: Clear emotional indicators, consistent patterns
- **Medium (70-89%)**: Mixed signals, some uncertainty
- **Low (50-69%)**: Unclear state, multiple possibilities
- **Unknown (<50%)**: Default to safe fallback

---

## Fallback Logic

When detection confidence is low:
1. **Default State**: Neutral/Seeking Validation
2. **Default Persona**: Clinical + Velvet
3. **Allow Manual Override**: User can force specific personas
4. **Learn from Response**: Adjust detection weights based on user reaction

---

## Learning & Adaptation

- Track detection accuracy vs. user satisfaction
- Adjust keyword weights based on performance
- Learn user-specific emotional patterns
- Evolve detection algorithms over time

> Emotional detection is not mind reading — it's pattern recognition with empathy.
