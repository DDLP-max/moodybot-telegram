# -*- coding: utf-8 -*-
"""
Dynamic Intelligence Routing Engine for MoodyBot
Selects capabilities / interventions first; legacy persona names are aliases only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from legacy_persona_aliases import bundle_for_command, resolve_alias


@dataclass
class EmotionalState:
    state: str
    confidence: float
    indicators: List[str]
    content_type: str
    tone_pattern: str


@dataclass
class IntelligenceSelection:
    primary: str
    secondary: Optional[str]
    intervention: Optional[str]
    voice: Optional[str]
    reasoning: str
    score: float
    source: str


class DynamicPersonaEngine:
    """Backwards-compatible name; routes intelligence capabilities."""

    def __init__(self):
        self.emotional_keywords = self._load_emotional_keywords()
        self.state_to_capability_mapping = self._load_state_mapping()

    def _load_emotional_keywords(self) -> Dict[str, List[str]]:
        return {
            "vulnerability": [
                "i feel", "i'm struggling", "i don't know", "i need help",
                "i'm lost", "i can't", "i'm confused",
            ],
            "defensiveness": [
                "but i had to", "you don't understand", "it's not my fault",
                "actually", "obviously",
            ],
            "validation_seeking": [
                "am i right", "does this make sense", "what do you think",
                "is this normal",
            ],
            "ego_collapse": [
                "i give up", "whatever", "i don't care anymore", "yolo",
                "nothing ever works",
            ],
            "relationship_ambiguity": [
                "mixed signals", "phone number", "sent flowers", "doorman",
                "what does it mean", "leading me on", "boundary",
            ],
            "practical_action": [
                "what should i do", "should i reply", "what do i say",
                "what now", "how should i handle",
            ],
            "infrastructure": [
                "infrastructure", "telecom", "how does this work", "under the hood",
            ],
            "hidden_motives": [
                "hidden agenda", "what's really happening", "who benefits",
                "ulterior motive",
            ],
        }

    def _load_state_mapping(self) -> Dict[str, Dict]:
        return {
            "vulnerability": {
                "primary": "Emotional Validation",
                "secondary": "Narrative Weight",
                "intervention": "Soft Emotional Precision",
                "voice": "Human Realism",
                "reasoning": "Name the feeling, then hold it with precision",
                "score": 0.9,
            },
            "defensiveness": {
                "primary": "Interrogative Analysis",
                "secondary": "Evidence vs Inference",
                "intervention": "Detached Analysis",
                "voice": "Clipped Precision",
                "reasoning": "Pressure-test claims without theatricality",
                "score": 0.85,
            },
            "validation_seeking": {
                "primary": "Emotional Validation",
                "secondary": "Gentle Stabilization",
                "intervention": "Soft Emotional Precision",
                "voice": "Dry Warmth",
                "reasoning": "Stabilize without empty flattery",
                "score": 0.8,
            },
            "ego_collapse": {
                "primary": "Crash Intervention",
                "secondary": "Emotional Reframe",
                "intervention": "Grounded Recalibration",
                "voice": None,
                "reasoning": "Interrupt freefall, restore proportion",
                "score": 0.9,
            },
            "relationship_ambiguity": {
                "primary": "Relationship Pattern Recognition",
                "secondary": "Boundary Analysis",
                "intervention": "Grounded Recalibration",
                "voice": "Human Realism",
                "reasoning": "Pattern + boundary + no false certainty about motives",
                "score": 0.92,
            },
            "practical_action": {
                "primary": "Practical Next Action",
                "secondary": "Evidence vs Inference",
                "intervention": "Grounded Recalibration",
                "voice": None,
                "reasoning": "Action without inventing facts",
                "score": 0.9,
            },
            "infrastructure": {
                "primary": "Operational Intelligence",
                "secondary": "Latticework Judgment",
                "intervention": None,
                "voice": "Dry Economy",
                "reasoning": "Systems and incentives over vibe",
                "score": 0.85,
            },
            "hidden_motives": {
                "primary": "Hidden Incentive Analysis",
                "secondary": "Pattern Forensics",
                "intervention": "Interrogative Analysis",
                "voice": "Hardboiled Observation",
                "reasoning": "Incentives and evidence before motive stories",
                "score": 0.9,
            },
        }

    def detect_emotional_state(self, message: str) -> EmotionalState:
        message_lower = message.lower()
        detected = {}
        for state, keywords in self.emotional_keywords.items():
            matches = [kw for kw in keywords if kw in message_lower]
            if matches:
                detected[state] = {
                    "confidence": min(0.9, 0.5 + len(matches) * 0.1),
                    "indicators": matches,
                }
        if not detected:
            return EmotionalState("neutral", 0.3, [], "statement", "neutral")
        primary = max(detected.items(), key=lambda x: x[1]["confidence"])
        return EmotionalState(
            state=primary[0],
            confidence=primary[1]["confidence"],
            indicators=primary[1]["indicators"],
            content_type=self._classify_content(message),
            tone_pattern=self._recognize_tone(message),
        )

    def _classify_content(self, message: str) -> str:
        m = message.lower()
        if any(p in m for p in ["what should i", "should i", "what do i say", "what now"]):
            return "request"
        if any(p in m for p in ["i feel", "i'm", "i don't"]):
            return "confession"
        if "?" in message:
            return "question"
        return "statement"

    def _recognize_tone(self, message: str) -> str:
        m = message.lower()
        if any(p in m for p in ["oh great", "sure because", "obviously"]):
            return "sarcastic"
        if any(w in m for w in ["philosophically", "theoretically", "fundamentally"]):
            return "intellectual"
        return "neutral"

    def select_optimal_personas(self, analysis: EmotionalState, context: Dict) -> IntelligenceSelection:
        # Action requests should prefer Practical Next Action even at medium confidence
        if analysis.content_type == "request" and analysis.state in {
            "practical_action", "neutral"
        }:
            m = self.state_to_capability_mapping.get("practical_action")
            if m:
                return IntelligenceSelection(
                    primary=m["primary"],
                    secondary=m.get("secondary"),
                    intervention=m.get("intervention"),
                    voice=m.get("voice"),
                    reasoning=m["reasoning"],
                    score=max(analysis.confidence, 0.75),
                    source="automatic",
                )

        if analysis.confidence >= 0.6 and analysis.state in self.state_to_capability_mapping:
            m = self.state_to_capability_mapping[analysis.state]
            return IntelligenceSelection(
                primary=m["primary"],
                secondary=m.get("secondary"),
                intervention=m.get("intervention"),
                voice=m.get("voice"),
                reasoning=m["reasoning"],
                score=m["score"],
                source="automatic",
            )
        return IntelligenceSelection(
            primary="Emotional State Recognition",
            secondary="Evidence vs Inference",
            intervention="Soft Emotional Precision",
            voice=None,
            reasoning="Safe intelligence-first fallback",
            score=0.5,
            source="automatic_fallback",
        )

    def process_user_input(self, message: str, context: Dict) -> Dict:
        manual = self._extract_manual_commands(message)
        if manual:
            bundle = bundle_for_command(manual[0])
            return {
                "capabilities": {
                    "primary": (
                        bundle["capabilities"][0].replace("_", " ").title()
                        if bundle["capabilities"] else manual[0]
                    ),
                    "secondary": (
                        bundle["capabilities"][1].replace("_", " ").title()
                        if len(bundle["capabilities"]) > 1 else None
                    ),
                    "intervention": (
                        bundle["intervention"][0].replace("_", " ").title()
                        if bundle["intervention"] else None
                    ),
                    "voice": (
                        bundle["voice"][0].replace("_", " ").title()
                        if bundle["voice"] else None
                    ),
                },
                "personas": {
                    "primary": manual[0],
                    "secondary": manual[1] if len(manual) > 1 else None,
                },
                "source": "manual_override",
                "reasoning": "Legacy slash command mapped to capability bundle",
                "deprecated_alias": True,
            }

        analysis = self.detect_emotional_state(message)
        selected = self.select_optimal_personas(analysis, context)
        return {
            "capabilities": {
                "primary": selected.primary,
                "secondary": selected.secondary,
                "intervention": selected.intervention,
                "voice": selected.voice,
            },
            "personas": {
                "primary": selected.primary,
                "secondary": selected.secondary,
            },
            "source": selected.source,
            "analysis": {
                "state": analysis.state,
                "confidence": analysis.confidence,
                "content_type": analysis.content_type,
                "tone_pattern": analysis.tone_pattern,
                "indicators": analysis.indicators,
            },
            "reasoning": selected.reasoning,
            "score": selected.score,
        }

    def _extract_manual_commands(self, message: str) -> List[str]:
        commands = re.findall(r"/(\w+)", message.lower())
        out = []
        for cmd in commands:
            if resolve_alias(cmd) or cmd in {
                "savage", "cia", "noir", "velvet", "clinical", "validate",
                "munger", "roast", "cut", "bomb", "float", "rollins",
            }:
                out.append(cmd)
        return out

    def calculate_compatibility(self, a: str, b: str) -> float:
        poor = {
            frozenset({"Emotional Validation", "High-Friction Confrontation"}),
            frozenset({"Quiet Presence", "High-Friction Confrontation"}),
            frozenset({"Savage", "Bob Ross"}),
            frozenset({"Velvet", "Savage"}),
        }
        if frozenset({a, b}) in poor:
            return 0.2
        return 0.7


PersonaSelection = IntelligenceSelection
