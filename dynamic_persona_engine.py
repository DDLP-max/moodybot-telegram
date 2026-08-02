#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic Persona Selection Engine for MoodyBot
Automatically selects optimal personas based on user input analysis
"""

import re
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EmotionalState:
    """Represents detected emotional state with confidence"""
    state: str
    confidence: float
    indicators: List[str]
    content_type: str
    tone_pattern: str

@dataclass
class PersonaSelection:
    """Represents selected persona stack"""
    primary: str
    secondary: Optional[str]
    reasoning: str
    score: float
    source: str  # 'automatic' or 'manual_override'

class DynamicPersonaEngine:
    """Main engine for dynamic persona selection"""
    
    def __init__(self):
        self.emotional_keywords = self._load_emotional_keywords()
        self.persona_compatibility = self._load_persona_compatibility()
        self.state_to_persona_mapping = self._load_state_mapping()
        self.user_preferences = {}  # Will be loaded from storage
        
    def _load_emotional_keywords(self) -> Dict[str, List[str]]:
        """Load emotional state detection keywords"""
        return {
            'vulnerability': [
                'i feel', 'i\'m struggling', 'i don\'t know', 'i need help',
                'i\'m lost', 'i can\'t', 'i don\'t think', 'maybe i\'m just',
                'i guess i', 'i don\'t understand', 'i\'m confused'
            ],
            'defensiveness': [
                'but i had to', 'you don\'t understand', 'it\'s not my fault',
                'what about you', 'everyone else does', 'that\'s not the point',
                'actually', 'obviously', 'anyone can see', 'it\'s simple really'
            ],
            'validation_seeking': [
                'am i right', 'does this make sense', 'what do you think',
                'i finally', 'look what i did', 'i\'m proud of', 'is this normal',
                'do other people', 'am i the only one'
            ],
            'ego_collapse': [
                'i give up', 'whatever', 'i don\'t care anymore', 'yolo',
                'might as well burn it down', 'i keep ruining everything',
                'nothing ever works', 'i always mess up', 'i\'m just like this'
            ],
            'intellectual_posturing': [
                'philosophically speaking', 'from a theoretical perspective',
                'if we examine this', 'the fundamental issue is', 'one might argue',
                'it\'s a matter of', 'the underlying principle'
            ],
            'infrastructure': [
                'infrastructure', 'telecom', 'telecommunications', 'network',
                'construction', 'logistics', 'supply chain', 'how does this work',
                'under the hood', 'behind the scenes', 'the real process'
            ],
            'travel': [
                'travel', 'airport', 'flight', 'visiting', 'australia', 'new zealand',
                'abroad', 'road trip', 'hotel', 'passport'
            ],
            'government': [
                'government', 'bureaucracy', 'immigration', 'visa', 'policy',
                'agency', 'department', 'official process', 'red tape'
            ],
            'legal': [
                'court', 'lawyer', 'legal', 'contract', 'lawsuit', 'immigration case',
                'hearing', 'judge', 'documents'
            ],
            'business_strategy': [
                'business strategy', 'incentives', 'leverage', 'competitive',
                'market', 'pricing', 'margin', 'what\'s really going on'
            ],
            'career': [
                'career', 'job advice', 'should i quit', 'promotion', 'resume',
                'what should i do with my life', 'career path'
            ],
            'technical': [
                'technical', 'debug', 'system', 'api', 'architecture',
                'how it actually works', 'implementation'
            ],
            'life_reflection': [
                'getting older', 'ageing', 'aging', 'mortality', 'looking back',
                'what does it all mean', 'life reflection', 'getting old'
            ],
            'entrepreneurship': [
                'startup', 'small business', 'entrepreneur', 'side hustle',
                'i want to start', 'business idea', 'founders'
            ],
            'hidden_motives': [
                'hidden agenda', 'what\'s really happening', 'ulterior motive',
                'official explanation', 'beneath the surface', 'who benefits',
                'follow the money', 'unofficial'
            ],
            'software_product': [
                'software', 'app', 'product', 'feature', 'ship it', 'mvp',
                'version 1', 'prototype', 'codebase', 'deploy'
            ],
            'startups_prototypes': [
                'startup', 'prototype', 'mvp', 'build version', 'let\'s build',
                'how do we ship', 'minimum viable'
            ],
            'engineering_ai': [
                'engineering', 'ai architecture', 'system design', 'architecture',
                'stack', 'build this', 'how do we implement', 'technical design'
            ]
        }
    
    def _load_persona_compatibility(self) -> Dict[str, Dict[str, float]]:
        """Load persona compatibility scores"""
        return {
            'Savage': {
                'CIA': 0.9, 'Noir': 0.7, 'Clinical': 0.6, 'Velvet': 0.3, 'Bob Ross': 0.2
            },
            'CIA': {
                'Savage': 0.9, 'Noir': 0.8, 'Clinical': 0.9, 'Velvet': 0.4, 'Gothic': 0.7
            },
            'Noir': {
                'Savage': 0.7, 'CIA': 0.8, 'Velvet': 0.9, 'Bourdain': 0.8, 'Gothic': 0.7
            },
            'Velvet': {
                'Noir': 0.9, 'Bob Ross': 0.8, 'Clinical': 0.7, 'Bond': 0.6, 'Savage': 0.3
            },
            'Clinical': {
                'CIA': 0.9, 'Velvet': 0.7, 'Gothic': 0.6, 'Savage': 0.6, 'Bob Ross': 0.5,
                'Field Operator': 0.9, 'Builder': 0.85
            },
            'Field Operator': {
                'Munger': 0.9, 'Columbo': 0.9, 'CIA': 0.85, 'Clinical': 0.9,
                'Sam': 0.8, 'Dan Kennedy': 0.85, 'Bourdain': 0.7, 'Builder': 0.9
            },
            'Builder': {
                'Field Operator': 0.9, 'Clinical': 0.85, 'Dan Kennedy': 0.8,
                'Munger': 0.75, 'Sam': 0.5
            },
            'Sam': {
                'Bourdain': 0.9, 'Field Operator': 0.8, 'Harry Dean Stanton': 0.9,
                'Velvet': 0.7, 'Noir': 0.6
            },
            'Munger': {
                'Field Operator': 0.9, 'Clinical': 0.85, 'CIA': 0.7, 'Dan Kennedy': 0.7,
                'Builder': 0.75
            },
            'Columbo': {
                'Field Operator': 0.9, 'CIA': 0.85, 'Clinical': 0.7
            }
        }
    
    def _load_state_mapping(self) -> Dict[str, Dict]:
        """Load emotional state to persona mapping"""
        return {
            'vulnerability': {
                'primary': 'Velvet',
                'secondary': 'Noir',
                'reasoning': 'Gentle empathy + poetic depth',
                'score': 0.9
            },
            'defensiveness': {
                'primary': 'Clinical',
                'secondary': 'CIA',
                'reasoning': 'Logic + suspicion detection',
                'score': 0.8
            },
            'ego_collapse': {
                'primary': 'Dale/YOLO',
                'secondary': 'Savage',
                'reasoning': 'Crash-mode truth delivery',
                'score': 0.9
            },
            'validation_seeking': {
                'primary': 'Bob Ross',
                'secondary': 'Velvet',
                'reasoning': 'Encouragement + emotional support',
                'score': 0.8
            },
            'intellectual_posturing': {
                'primary': 'CIA',
                'secondary': 'Noir',
                'reasoning': 'Interrogation + poetic dismantling',
                'score': 0.8
            },
            'infrastructure': {
                'primary': 'Field Operator',
                'secondary': 'Munger',
                'reasoning': 'Systems mapping + latticework clarity',
                'score': 0.8
            },
            'travel': {
                'primary': 'Sam',
                'secondary': 'Bourdain',
                'reasoning': 'Weathered warmth + sensory realism',
                'score': 0.8
            },
            'government': {
                'primary': 'Field Operator',
                'secondary': 'Columbo',
                'reasoning': 'Field intelligence + gentle trap-setting',
                'score': 0.8
            },
            'legal': {
                'primary': 'Field Operator',
                'secondary': 'CIA',
                'reasoning': 'Operational realism + interrogation pressure',
                'score': 0.8
            },
            'business_strategy': {
                'primary': 'Field Operator',
                'secondary': 'Munger',
                'reasoning': 'Hidden systems + judgment-free logic',
                'score': 0.8
            },
            'career': {
                'primary': 'Sam',
                'secondary': 'Field Operator',
                'reasoning': 'Quiet wisdom + street-level intelligence',
                'score': 0.7
            },
            'technical': {
                'primary': 'Field Operator',
                'secondary': 'Clinical',
                'reasoning': 'Pattern recognition + detached clarity',
                'score': 0.8
            },
            'life_reflection': {
                'primary': 'Sam',
                'secondary': 'Harry Dean Stanton',
                'reasoning': 'Mature warmth + weathered silence',
                'score': 0.8
            },
            'entrepreneurship': {
                'primary': 'Field Operator',
                'secondary': 'Dan Kennedy',
                'reasoning': 'Lived ops + direct-response edge',
                'score': 0.8
            },
            'hidden_motives': {
                'primary': 'Field Operator',
                'secondary': 'Columbo',
                'reasoning': 'Incentives first + relentless curiosity (CIA tertiary when stacked)',
                'score': 0.9
            },
            'software_product': {
                'primary': 'Builder',
                'secondary': 'Field Operator',
                'reasoning': 'Prototype-first + systems realism',
                'score': 0.9
            },
            'startups_prototypes': {
                'primary': 'Builder',
                'secondary': 'Dan Kennedy',
                'reasoning': 'Ship V1 + direct-response urgency',
                'score': 0.8
            },
            'engineering_ai': {
                'primary': 'Builder',
                'secondary': 'Clinical',
                'reasoning': 'Build plan + detached clarity',
                'score': 0.8
            }
        }
    
    def detect_emotional_state(self, message: str) -> EmotionalState:
        """Analyze message for emotional state indicators"""
        message_lower = message.lower()
        detected_states = {}
        
        # Check each emotional category
        for state, keywords in self.emotional_keywords.items():
            matches = [kw for kw in keywords if kw in message_lower]
            if matches:
                # Calculate confidence based on number and strength of matches
                confidence = min(0.9, 0.5 + (len(matches) * 0.1))
                detected_states[state] = {
                    'confidence': confidence,
                    'indicators': matches
                }
        
        # Determine primary state
        if not detected_states:
            return EmotionalState(
                state='neutral',
                confidence=0.3,
                indicators=[],
                content_type='statement',
                tone_pattern='neutral'
            )
        
        # Select highest confidence state
        primary_state = max(detected_states.items(), key=lambda x: x[1]['confidence'])
        
        # Classify content type
        content_type = self._classify_content(message)
        
        # Detect tone pattern
        tone_pattern = self._recognize_tone(message)
        
        return EmotionalState(
            state=primary_state[0],
            confidence=primary_state[1]['confidence'],
            indicators=primary_state[1]['indicators'],
            content_type=content_type,
            tone_pattern=tone_pattern
        )
    
    def _classify_content(self, message: str) -> str:
        """Classify message content type"""
        message_lower = message.lower()
        
        if any(phrase in message_lower for phrase in ['i feel', 'i\'m', 'i don\'t', 'i need']):
            return 'confession'
        elif any(phrase in message_lower for phrase in ['what if', 'how do', 'can you', 'should i']):
            return 'question'
        elif any(phrase in message_lower for phrase in ['i think', 'obviously', 'clearly', 'the thing is']):
            return 'statement'
        elif any(phrase in message_lower for phrase in ['help me', 'tell me', 'show me', 'give me']):
            return 'request'
        else:
            return 'statement'
    
    def _recognize_tone(self, message: str) -> str:
        """Detect tone patterns in message"""
        message_lower = message.lower()
        
        # Check for sarcasm
        if any(phrase in message_lower for phrase in ['oh great', 'sure because', 'obviously', 'clearly']):
            return 'sarcastic'
        
        # Check for performative language
        if re.search(r'[A-Z]{3,}', message) or '...' in message or '!' * 3 in message:
            return 'performative'
        
        # Check for intellectual language
        if any(word in message_lower for word in ['philosophically', 'theoretically', 'fundamentally', 'principle']):
            return 'intellectual'
        
        return 'neutral'
    
    def select_optimal_personas(self, analysis: EmotionalState, context: Dict) -> PersonaSelection:
        """Select optimal personas based on emotional analysis"""
        
        # Check if we have a high-confidence mapping
        if analysis.confidence >= 0.7 and analysis.state in self.state_to_persona_mapping:
            mapping = self.state_to_persona_mapping[analysis.state]
            
            return PersonaSelection(
                primary=mapping['primary'],
                secondary=mapping['secondary'],
                reasoning=mapping['reasoning'],
                score=mapping['score'],
                source='automatic'
            )
        
        # Fallback to default stack for low confidence
        if analysis.confidence < 0.5:
            return PersonaSelection(
                primary='Clinical',
                secondary='Velvet',
                reasoning='Safe, empathetic, logical foundation',
                score=0.5,
                source='automatic_fallback'
            )
        
        # Try to find best match from available personas
        best_match = self._find_best_match(analysis)
        if best_match:
            return best_match
        
        # Ultimate fallback
        return PersonaSelection(
            primary='Clinical',
            secondary='Velvet',
            reasoning='Default safe stack',
            score=0.5,
            source='automatic_fallback'
        )
    
    def _find_best_match(self, analysis: EmotionalState) -> Optional[PersonaSelection]:
        """Find best persona match for detected state"""
        # This is a simplified matching algorithm
        # In production, this would use more sophisticated NLP and ML techniques
        
        if analysis.state == 'vulnerability':
            return PersonaSelection(
                primary='Velvet',
                secondary='Noir',
                reasoning='Empathy + poetic depth for vulnerability',
                score=0.8,
                source='automatic'
            )
        elif analysis.state == 'defensiveness':
            return PersonaSelection(
                primary='Clinical',
                secondary='CIA',
                reasoning='Logic + pressure for defensiveness',
                score=0.8,
                source='automatic'
            )
        
        return None
    
    def process_user_input(self, message: str, context: Dict) -> Dict:
        """Main entry point for processing user input"""
        
        # Check for manual commands first
        manual_personas = self._extract_manual_commands(message)
        if manual_personas:
            return {
                'personas': {
                    'primary': manual_personas[0],
                    'secondary': manual_personas[1] if len(manual_personas) > 1 else None,
                    'tertiary': manual_personas[2] if len(manual_personas) > 2 else None
                },
                'source': 'manual_override',
                'reasoning': 'User specified personas'
            }
        
        # Analyze input for automatic selection
        analysis = self.detect_emotional_state(message)
        selected_personas = self.select_optimal_personas(analysis, context)
        
        return {
            'personas': {
                'primary': selected_personas.primary,
                'secondary': selected_personas.secondary
            },
            'source': selected_personas.source,
            'analysis': {
                'state': analysis.state,
                'confidence': analysis.confidence,
                'content_type': analysis.content_type,
                'tone_pattern': analysis.tone_pattern,
                'indicators': analysis.indicators
            },
            'reasoning': selected_personas.reasoning,
            'score': selected_personas.score
        }
    
    def _extract_manual_commands(self, message: str) -> List[str]:
        """Extract manual persona commands from message"""
        # Look for /command patterns
        commands = re.findall(r'/(\w+)', message.lower())
        
        # Map command aliases to full persona names
        command_mapping = {
            'savage': 'Savage',
            'cia': 'CIA',
            'noir': 'Noir',
            'velvet': 'Velvet',
            'clinical': 'Clinical',
            'bond': 'Bond',
            'bourdain': 'Bourdain',
            'gothic': 'Gothic',
            'rollins': 'Rollins',
            'dale': 'Dale/YOLO',
            'yolo': 'Dale/YOLO',
            'bob': 'Bob Ross',
            'ross': 'Bob Ross',
            'matt': 'Field Operator',
            'field': 'Field Operator',
            'operator': 'Field Operator',
            'sam': 'Sam',
            'munger': 'Munger',
            'columbo': 'Columbo',
            'kennedy': 'Dan Kennedy',
            'builder': 'Builder',
            'build': 'Builder'
        }
        
        return [command_mapping.get(cmd, cmd.title()) for cmd in commands if cmd in command_mapping]
    
    def calculate_compatibility(self, persona1: str, persona2: str) -> float:
        """Calculate compatibility score between two personas"""
        if persona1 not in self.persona_compatibility:
            return 0.5  # Default compatibility for unknown personas
        
        return self.persona_compatibility[persona1].get(persona2, 0.5)
    
    def validate_context(self, personas: Dict, context: Dict) -> bool:
        """Validate that selected personas work with conversation context"""
        # Simple context validation - in production this would be more sophisticated
        if not context.get('conversation_history'):
            return True  # First interaction
        
        # Check for jarring shifts (simplified)
        last_personas = context.get('last_personas', [])
        if last_personas:
            # Avoid switching from high-intensity to low-intensity personas abruptly
            high_intensity = ['Savage', 'CIA', 'Rollins', 'Dale/YOLO']
            low_intensity = ['Velvet', 'Bob Ross', 'Clinical']
            
            current_high = any(p in high_intensity for p in personas.values() if p)
            current_low = any(p in low_intensity for p in personas.values() if p)
            last_high = any(p in high_intensity for p in last_personas)
            last_low = any(p in low_intensity for p in last_personas)
            
            if (current_high and last_low) or (current_low and last_high):
                return False  # Jarring shift
        
        return True

# Example usage and testing
if __name__ == "__main__":
    engine = DynamicPersonaEngine()
    
    # Test cases
    test_cases = [
        "I feel so lost right now. I don't know what to do anymore.",
        "Whatever, I don't care anymore. YOLO.",
        "Actually, you're wrong. It's not my fault.",
        "Am I right? Does this make sense?",
        "Philosophically speaking, the fundamental issue is..."
    ]
    
    for i, test_message in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Input: {test_message}")
        
        context = {'user_id': 'test_user', 'conversation_history': []}
        result = engine.process_user_input(test_message, context)
        
        print(f"Detected State: {result['analysis']['state']} (confidence: {result['analysis']['confidence']:.2f})")
        print(f"Selected Personas: {result['personas']['primary']} + {result['personas']['secondary']}")
        print(f"Reasoning: {result['reasoning']}")
        print(f"Source: {result['source']}")
