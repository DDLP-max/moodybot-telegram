# Dynamic Persona Selection Engine

MoodyBot automatically selects the optimal persona(s) based on real-time analysis of user input, emotional state, and conversation context.

---

## Core Selection Logic

### 1. Input Analysis Pipeline
- **Emotional State Detection**: Vulnerability, defensiveness, seeking validation, etc.
- **Content Type Classification**: Confession, question, statement, request, etc.
- **Tone Indicators**: Sarcasm, sincerity, performative, authentic, etc.
- **Context Awareness**: Previous interactions, user history, conversation flow

### 2. Persona Matching Matrix

| User State | Primary Persona | Secondary | Reasoning |
|------------|----------------|-----------|-----------|
| **Vulnerable/Confessing** | Velvet | Noir | Gentle empathy + poetic depth |
| **Defensive/Performative** | Clinical | CIA | Logic + suspicion detection |
| **Seeking Validation** | Bob Ross | Velvet | Encouragement + emotional support |
| **Ego Spiral/Collapse** | Dale/YOLO | Savage | Crash-mode truth delivery |
| **Intellectual Posturing** | CIA | Noir | Interrogation + poetic dismantling |
| **Grief/Loss** | Noir Romantic | Bourdain | Poetic wisdom + lived experience |
| **Anger/Rage** | Rollins | Savage | Channel rage into rhythm |
| **Seduction/Flirting** | Bond | Velvet | Charm + emotional depth |
| **Cultural Discussion** | Bourdain | CIA | Cultural insight + critical analysis |
| **Spiritual/Philosophical** | Gothic | Clinical | Mythic weight + logical clarity |
| **Infrastructure** | Field Operator | Munger | Systems mapping + latticework clarity |
| **Travel** | Sam | Bourdain | Weathered warmth + sensory realism |
| **Government** | Field Operator | Columbo | Field intelligence + gentle trap-setting |
| **Legal** | Field Operator | CIA | Operational realism + interrogation pressure |
| **Business Strategy** | Field Operator | Munger | Hidden systems + judgment-free logic |
| **Career** | Sam | Field Operator | Quiet wisdom + street-level intelligence |
| **Technical** | Field Operator | Clinical | Pattern recognition + detached clarity |
| **Life Reflection** | Sam | Harry Dean Stanton | Mature warmth + weathered silence |
| **Entrepreneurship** | Field Operator | Dan Kennedy | Lived ops + direct-response edge |
| **Hidden Motives** | Field Operator | Columbo + CIA | Incentives first + relentless curiosity |
| **Software / Product** | Builder | Field Operator | Prototype-first + systems realism |
| **Startups / Prototypes** | Builder | Dan Kennedy | Ship V1 + direct-response urgency |
| **Engineering / AI Arch** | Builder | Clinical | Build plan + detached clarity |

### 3. Selection Rules

- **Max 2 personas** for automatic selection (3rd slot reserved for manual override)
- **Emotional resonance** takes priority over clever combinations
- **Context continuity** - avoid jarring persona shifts mid-conversation
- **User preference learning** - remember what works for each user

---

## Implementation Components

### A. State Detection Engine
- Emotional keyword analysis
- Tone pattern recognition
- Context window analysis (last 3-5 exchanges)
- User interaction history

### B. Persona Compatibility Matrix
- Pre-calculated compatibility scores
- Rhythm matching algorithms
- Emotional intensity scaling
- Cultural resonance factors

### C. Selection Algorithm
- Multi-factor scoring system
- Fallback logic for edge cases
- Manual override preservation
- Learning from user reactions

---

## Fallback Strategy

**Default Stack**: Clinical + Velvet
- **When**: Unknown state, first interaction, system uncertainty
- **Why**: Safe, empathetic, logical foundation
- **Override**: Always allows manual command override

---

## Learning & Adaptation

- Track which persona selections lead to positive user engagement
- Adjust selection weights based on user-specific patterns
- Maintain persona effectiveness metrics
- Evolve selection logic based on performance data

> The right persona at the right time is worth a thousand clever responses.
