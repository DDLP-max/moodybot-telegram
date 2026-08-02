#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo script for Dynamic Persona Selection System
Shows various user inputs and how the system responds
"""

from dynamic_persona_engine import DynamicPersonaEngine

def demo_dynamic_persona():
    """Demonstrate the dynamic persona selection system"""
    
    print("🎭 Dynamic Persona Selection System Demo")
    print("=" * 50)
    
    engine = DynamicPersonaEngine()
    
    # Demo scenarios
    scenarios = [
        {
            "name": "Vulnerable Confession",
            "input": "I feel so lost right now. I don't know what to do anymore.",
            "expected_state": "vulnerability"
        },
        {
            "name": "Ego Collapse",
            "input": "Whatever, I don't care anymore. YOLO.",
            "expected_state": "ego_collapse"
        },
        {
            "name": "Defensive Posturing",
            "input": "Actually, you're wrong. It's not my fault.",
            "expected_state": "defensiveness"
        },
        {
            "name": "Seeking Validation",
            "input": "Am I right? Does this make sense?",
            "expected_state": "validation_seeking"
        },
        {
            "name": "Intellectual Posturing",
            "input": "Philosophically speaking, the fundamental issue is...",
            "expected_state": "intellectual_posturing"
        },
        {
            "name": "Manual Override",
            "input": "Tell me something /savage about my situation",
            "expected_state": "manual_override"
        },
        {
            "name": "Neutral Statement",
            "input": "The weather is nice today.",
            "expected_state": "neutral"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n--- Scenario {i}: {scenario['name']} ---")
        print(f"Input: {scenario['input']}")
        
        context = {'user_id': 'demo_user', 'conversation_history': []}
        result = engine.process_user_input(scenario['input'], context)
        
        if result['source'] == 'manual_override':
            print(f"Detected State: Manual Override")
            print(f"Confidence: N/A")
            print(f"Content Type: N/A")
            print(f"Tone Pattern: N/A")
            print(f"Selected Personas: {result['personas']['primary']} + {result['personas'].get('secondary', 'None')}")
            print(f"Reasoning: {result['reasoning']}")
            print(f"Source: {result['source']}")
        else:
            print(f"Detected State: {result['analysis']['state']}")
            print(f"Confidence: {result['analysis']['confidence']:.2f}")
            print(f"Content Type: {result['analysis']['content_type']}")
            print(f"Tone Pattern: {result['analysis']['tone_pattern']}")
            print(f"Selected Personas: {result['personas']['primary']} + {result['personas']['secondary']}")
            print(f"Reasoning: {result['reasoning']}")
            print(f"Source: {result['source']}")
        
        # Validate expectations
        if scenario['expected_state'] == 'manual_override':
            expected = result['source'] == 'manual_override'
        else:
            expected = result['analysis']['state'] == scenario['expected_state']
        
        status = "✅ PASS" if expected else "❌ FAIL"
        print(f"Status: {status}")
    
    print("\n" + "=" * 50)
    print("🎉 Demo Complete!")
    print("\nKey Benefits:")
    print("• Automatic emotional state detection")
    print("• Optimal persona selection")
    print("• Manual override support")
    print("• Context-aware responses")
    print("• Fallback safety mechanisms")

if __name__ == "__main__":
    demo_dynamic_persona()
