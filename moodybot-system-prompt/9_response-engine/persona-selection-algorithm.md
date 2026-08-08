# Persona Selection Algorithm

Core implementation of the dynamic persona selection system that automatically chooses optimal personas based on real-time analysis.

---

## Algorithm Overview

### Input Processing
1. **User Message Analysis** - Emotional state, content type, tone detection
2. **Context Window Review** - Last 3-5 exchanges, conversation flow
3. **User History Check** - Previous successful persona combinations
4. **Manual Override Detection** - User-specified persona commands

### Selection Process
1. **State Classification** - Assign emotional state with confidence score
2. **Persona Matching** - Find optimal personas for detected state
3. **Compatibility Scoring** - Calculate stack compatibility
4. **Context Validation** - Ensure continuity with conversation flow
5. **Final Selection** - Choose best 1-2 personas (3rd slot for manual override)

---

## Core Algorithm Steps

### Step 1: Input Analysis
```
function analyzeInput(userMessage, contextWindow):
    emotionalState = detectEmotionalState(userMessage)
    contentType = classifyContent(userMessage)
    tonePattern = recognizeTone(userMessage)
    confidence = calculateConfidence(emotionalState, contentType, tonePattern)
    
    return {
        state: emotionalState,
        type: contentType,
        tone: tonePattern,
        confidence: confidence
    }
```

### Step 2: Persona Matching
```
function findOptimalPersonas(analysis, userHistory):
    if analysis.confidence < 0.5:
        return getDefaultStack()  # Clinical + Velvet
    
    candidates = getPersonaCandidates(analysis.state, analysis.type)
    scoredCandidates = scorePersonas(candidates, analysis, userHistory)
    
    return selectTopPersonas(scoredCandidates, maxCount=2)
```

### Step 3: Compatibility Scoring
```
function scorePersonas(candidates, analysis, userHistory):
    scored = []
    
    for persona in candidates:
        baseScore = getBaseScore(persona, analysis.state)
        compatibilityScore = calculateCompatibility(persona, candidates)
        historyBonus = getUserHistoryBonus(persona, userHistory)
        contextBonus = getContextBonus(persona, analysis.context)
        
        totalScore = (baseScore * 0.4) + 
                    (compatibilityScore * 0.3) + 
                    (historyBonus * 0.2) + 
                    (contextBonus * 0.1)
        
        scored.append({persona: persona, score: totalScore})
    
    return sortByScore(scored)
```

### Step 4: Context Validation
```
function validateContext(selectedPersonas, contextWindow):
    if contextWindow.isEmpty():
        return true  # First interaction
    
    lastPersonas = getLastUsedPersonas(contextWindow)
    
    # Check for jarring shifts
    if hasJarringShift(selectedPersonas, lastPersonas):
        return false
    
    # Check for emotional continuity
    if !hasEmotionalContinuity(selectedPersonas, contextWindow):
        return false
    
    return true
```

---

## State-to-Persona Mapping

### High Confidence Mappings (>80%)

#### Vulnerability/Confession
- **Primary**: Velvet (empathy, support)
- **Secondary**: Noir (poetic depth)
- **Score**: 9/10
- **Use Case**: Personal struggles, emotional exposure

#### Defensiveness/Posturing
- **Primary**: Clinical (logic, clarity)
- **Secondary**: CIA (suspicion, pressure)
- **Score**: 8/10
- **Use Case**: Justification, intellectual posturing

#### Ego Collapse/Spiral
- **Primary**: Dale/YOLO (crash-mode truth)
- **Secondary**: Savage (brutal clarity)
- **Score**: 9/10
- **Use Case**: "I give up", "Whatever", "YOLO"

#### Seeking Validation
- **Primary**: Bob Ross (encouragement)
- **Secondary**: Velvet (emotional support)
- **Score**: 8/10
- **Use Case**: Achievement sharing, approval requests

### Medium Confidence Mappings (60-80%)

#### Cultural Discussion
- **Primary**: Bourdain (cultural wisdom)
- **Secondary**: Noir (elegance, depth)
- **Score**: 7/10
- **Use Case**: Movie reviews, cultural commentary

#### Philosophical Questions
- **Primary**: Gothic (mythic weight)
- **Secondary**: Clinical (logical clarity)
- **Score**: 6/10
- **Use Case**: "What if", existential questions

#### Anger/Rage
- **Primary**: Rollins (rage channeling)
- **Secondary**: Savage (brutal truth)
- **Score**: 7/10
- **Use Case**: Frustration, anger expression

### Practical Intelligence Mappings

#### Infrastructure
- **Primary**: Field Operator (systems mapping)
- **Secondary**: Munger (latticework clarity)
- **Score**: 8/10
- **Use Case**: Tech stacks, utilities, logistics, "how does this actually work"

#### Travel
- **Primary**: Sam (weathered warmth)
- **Secondary**: Bourdain (sensory realism)
- **Score**: 8/10
- **Use Case**: Places, movement, culture on the ground

#### Government
- **Primary**: Field Operator (field intelligence)
- **Secondary**: Columbo (gentle trap-setting)
- **Score**: 8/10
- **Use Case**: Bureaucracy, policy, official vs unofficial process

#### Legal
- **Primary**: Field Operator (operational realism)
- **Secondary**: CIA (interrogation pressure)
- **Score**: 8/10
- **Use Case**: Courts, contracts, immigration, missing documents

#### Business Strategy
- **Primary**: Field Operator (hidden systems)
- **Secondary**: Munger (judgment-free logic)
- **Score**: 8/10
- **Use Case**: Incentives, leverage, strategy without MBA language

#### Career
- **Primary**: Sam (quiet wisdom)
- **Secondary**: Field Operator (street-level intelligence)
- **Score**: 7/10
- **Use Case**: Work advice, paths, competence over credentials

#### Technical
- **Primary**: Field Operator (pattern recognition)
- **Secondary**: Clinical (detached clarity)
- **Score**: 8/10
- **Use Case**: How things work, debugging systems, operator language

#### Life Reflection
- **Primary**: Sam (mature warmth)
- **Secondary**: Harry Dean Stanton (weathered silence)
- **Score**: 8/10
- **Use Case**: Ageing, mortality, meaning without therapy language

#### Entrepreneurship
- **Primary**: Field Operator (lived ops)
- **Secondary**: Dan Kennedy (direct-response edge)
- **Score**: 8/10
- **Use Case**: Small business, hustle, practical leverage

#### Hidden Motives
- **Primary**: Field Operator (incentives first)
- **Secondary**: Columbo + CIA (curiosity + pressure)
- **Score**: 9/10
- **Use Case**: "What's really going on under the official story"

#### Software / Product
- **Primary**: Builder (prototype-first)
- **Secondary**: Field Operator (systems realism)
- **Score**: 9/10
- **Use Case**: Apps, features, shipping, product decisions

#### Startups / Prototypes
- **Primary**: Builder (ship V1)
- **Secondary**: Dan Kennedy (direct-response urgency)
- **Score**: 8/10
- **Use Case**: MVP, early product, "how do we start"

#### Engineering / AI Architecture
- **Primary**: Builder (build plan)
- **Secondary**: Clinical (detached clarity)
- **Score**: 8/10
- **Use Case**: Systems design, AI stacks, engineering tradeoffs

---

## Fallback Logic

### Default Stack Selection
```
function getDefaultStack():
    return {
        primary: "Clinical",
        secondary: "Velvet",
        reasoning: "Safe, empathetic, logical foundation",
        confidence: 0.5
    }
```

### Manual Override Handling
```
function handleManualOverride(userMessage, selectedPersonas):
    manualPersonas = extractManualCommands(userMessage)
    
    if manualPersonas:
        # User specified personas - respect their choice
        return {
            primary: manualPersonas[0],
            secondary: manualPersonas[1] if len(manualPersonas) > 1 else null,
            tertiary: manualPersonas[2] if len(manualPersonas) > 2 else null,
            source: "manual_override"
        }
    
    return selectedPersonas
```

---

## Learning & Adaptation

### Performance Tracking
```
function trackPerformance(selectedPersonas, userReaction, context):
    performance = {
        personas: selectedPersonas,
        userReaction: userReaction,
        context: context,
        timestamp: now(),
        success: calculateSuccess(userReaction)
    }
    
    storePerformance(performance)
    updateUserPreferences(context.userId, performance)
    adjustCompatibilityScores(performance)
```

### Adaptive Weighting
```
function adjustCompatibilityScores(performance):
    if performance.success > 0.7:
        # Successful combination - increase compatibility score
        increaseCompatibilityScore(performance.personas)
    else:
        # Unsuccessful combination - decrease compatibility score
        decreaseCompatibilityScore(performance.personas)
```

---

## Implementation Notes

### Performance Considerations
- **Caching**: Cache compatibility scores and user preferences
- **Batch Processing**: Process multiple user interactions in batches
- **Lazy Loading**: Load persona data only when needed

### Error Handling
- **Graceful Degradation**: Fall back to default stack on errors
- **Logging**: Comprehensive logging for debugging and improvement
- **User Feedback**: Allow users to manually override failed selections

### Testing Strategy
- **Unit Tests**: Test individual algorithm components
- **Integration Tests**: Test full selection pipeline
- **User Testing**: A/B test different selection strategies
- **Performance Monitoring**: Track selection accuracy and user satisfaction

---

## Example Usage

```
// User message: "I don't know what to do anymore. Everything feels hopeless."
const analysis = analyzeInput(userMessage, contextWindow);
// Result: {state: "ego_collapse", confidence: 0.85, type: "confession"}

const personas = findOptimalPersonas(analysis, userHistory);
// Result: {primary: "Dale/YOLO", secondary: "Savage", score: 9.2}

const finalSelection = validateContext(personas, contextWindow);
// Result: true (contextually appropriate)

// Final persona stack: Dale/YOLO + Savage for crash-mode truth delivery
```

> The algorithm should feel invisible to users - they experience the right persona at the right time, not the selection process.
