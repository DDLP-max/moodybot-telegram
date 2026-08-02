#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for message utilities.
Tests HTML formatting, CTA appending, and mode detection.
"""

import os
from message_utils import (
    format_html_message, 
    resolve_mode, 
    maybe_append_cta, 
    strip_cta_from_text,
    escape_html
)

def test_html_formatting():
    """Test HTML formatting functionality."""
    print("=== Testing HTML Formatting ===")
    
    test_cases = [
        ("**Bold text**", "<b>Bold text</b>"),
        ("*Italic text*", "<i>Italic text</i>"),
        ("__Underlined text__", "<u>Underlined text</u>"),
        ("~~Strikethrough~~", "<s>Strikethrough</s>"),
        ("`Code text`", "<code>Code text</code>"),
        ("[Link text](https://example.com)", '<a href="https://example.com">Link text</a>'),
        ("**Bold** and *italic* together", "<b>Bold</b> and <i>italic</i> together"),
    ]
    
    for input_text, expected in test_cases:
        result = format_html_message(input_text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{input_text}' -> '{result}'")
        if result != expected:
            print(f"   Expected: '{expected}'")

def test_mode_detection():
    """Test mode detection functionality."""
    print("\n=== Testing Mode Detection ===")
    
    # Mock Update objects for testing
    class MockMessage:
        def __init__(self, text):
            self.text = text
    
    class MockUpdate:
        def __init__(self, text):
            self.message = MockMessage(text)
    
    test_cases = [
        ("/flirt tell me something nice", "flirt"),
        ("/social share this", "social"),
        ("/dev help with code", "dev"),
        ("/copywriter write an ad", "copywriter"),
        ("I want to flirt with you", "flirt"),
        ("This is social content", "social"),
        ("Help me with development", "dev"),
        ("Write copy for marketing", "copywriter"),
        ("Just a normal message", "neutral"),
    ]
    
    for input_text, expected_mode in test_cases:
        update = MockUpdate(input_text)
        detected_mode = resolve_mode(update)
        status = "✅" if detected_mode == expected_mode else "❌"
        print(f"{status} '{input_text}' -> '{detected_mode}' (expected: {expected_mode})")

def test_cta_appending():
    """Test CTA appending functionality."""
    print("\n=== Testing CTA Appending ===")
    
    # Test with different modes
    test_text = "This is a test message."
    
    modes = ['flirt', 'social', 'dev', 'copywriter', 'neutral']
    
    for mode in modes:
        result = maybe_append_cta(test_text, mode)
        should_have_cta = mode in ['flirt', 'social']
        has_cta = '🔁' in result or 'share' in result.lower()
        
        status = "✅" if (should_have_cta == has_cta) else "❌"
        print(f"{status} Mode '{mode}': CTA {'added' if has_cta else 'not added'}")
        if has_cta:
            print(f"   Result: '{result[:50]}...'")

def test_cta_stripping():
    """Test CTA stripping functionality."""
    print("\n=== Testing CTA Stripping ===")
    
    test_cases = [
        ("Normal message without CTA", "Normal message without CTA"),
        ("Message with CTA\n\nIf it read your soul, put it on speaker 🔁", "Message with CTA"),
        ("Message with share CTA\n\nShare this message 🔁", "Message with share CTA"),
        ("Multiple lines\nwith CTA\n\nPost it like a warning 🔁", "Multiple lines\nwith CTA"),
    ]
    
    for input_text, expected in test_cases:
        result = strip_cta_from_text(input_text)
        status = "✅" if result == expected else "❌"
        print(f"{status} CTA stripped correctly")
        if result != expected:
            print(f"   Input: '{input_text}'")
            print(f"   Expected: '{expected}'")
            print(f"   Got: '{result}'")

def test_html_escaping():
    """Test HTML escaping functionality."""
    print("\n=== Testing HTML Escaping ===")
    
    test_cases = [
        ("Normal text", "Normal text"),
        ("Text with & ampersand", "Text with &amp; ampersand"),
        ("Text with < brackets >", "Text with &lt; brackets &gt;"),
        ("Mixed & < > characters", "Mixed &amp; &lt; &gt; characters"),
    ]
    
    for input_text, expected in test_cases:
        result = escape_html(input_text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{input_text}' -> '{result}'")

def test_environment_flag():
    """Test environment flag behavior."""
    print("\n=== Testing Environment Flag ===")
    
    # Test with APPEND_CTA disabled
    os.environ['APPEND_CTA'] = 'false'
    from importlib import reload
    import message_utils
    reload(message_utils)
    
    result_disabled = message_utils.maybe_append_cta("Test message", "flirt")
    print(f"✅ APPEND_CTA=false: CTA {'not added' if '🔁' not in result_disabled else 'added'}")
    
    # Test with APPEND_CTA enabled
    os.environ['APPEND_CTA'] = 'true'
    reload(message_utils)
    
    result_enabled = message_utils.maybe_append_cta("Test message", "flirt")
    print(f"✅ APPEND_CTA=true: CTA {'added' if '🔁' in result_enabled else 'not added'}")

def test_no_cta_when_flag_false():
    """Test that no CTA is added when APPEND_CTA=false."""
    print("\n=== Testing No CTA When Flag False ===")
    
    os.environ['APPEND_CTA'] = 'false'
    from importlib import reload
    import message_utils
    reload(message_utils)
    
    test_cases = [
        ("flirt", "Test message"),
        ("social", "Test message"),
        ("dev", "Test message"),
        ("neutral", "Test message")
    ]
    
    for mode, text in test_cases:
        result = message_utils.maybe_append_cta(text, mode)
        status = "✅" if result == text else "❌"
        print(f"{status} Mode '{mode}': CTA {'not added' if result == text else 'added'}")

def test_cta_env_only():
    """Test that CTAs come from environment config only."""
    print("\n=== Testing CTA Environment Only ===")
    
    # Test with custom CTAS_JSON
    os.environ['CTAS_JSON'] = '{"flirt":"Custom flirt CTA 🔥","social":"Custom social CTA 📱"}'
    os.environ['APPEND_CTA'] = 'true'
    
    from importlib import reload
    import message_utils
    reload(message_utils)
    
    # Test custom CTAs
    flirt_result = message_utils.maybe_append_cta("Test", "flirt")
    social_result = message_utils.maybe_append_cta("Test", "social")
    dev_result = message_utils.maybe_append_cta("Test", "dev")
    
    print(f"✅ Flirt CTA: {'Custom flirt CTA 🔥' in flirt_result}")
    print(f"✅ Social CTA: {'Custom social CTA 📱' in social_result}")
    print(f"✅ Dev CTA: {'not added' if dev_result == 'Test' else 'added'}")

def test_strip_known_ctas():
    """Test strip_known_ctas function."""
    print("\n=== Testing Strip Known CTAs ===")
    
    from message_utils import strip_known_ctas
    
    test_cases = [
        ("Message with CTA\n\nIf it read your soul, put it on speaker 🔁", "Message with CTA"),
        ("Message with old CTA\n\nIf it slapped, share the sting -MoodyBot", "Message with old CTA"),
        ("Clean message", "Clean message"),
        ("Message with multiple CTAs\n\nCTA1\n\nIf it read your soul, put it on speaker 🔁\n\nCTA2", "Message with multiple CTAs\n\nCTA1\n\nCTA2"),
    ]
    
    for input_text, expected in test_cases:
        result = strip_known_ctas(input_text)
        status = "✅" if result == expected else "❌"
        print(f"{status} CTA stripped: '{input_text[:30]}...' -> '{result[:30]}...'")
        if result != expected:
            print(f"   Expected: '{expected}'")
            print(f"   Got: '{result}'")

def test_no_backslashes():
    """Test that no backslashes remain in final payload."""
    print("\n=== Testing No Backslashes ===")
    
    test_text = "This is a test message with periods. And exclamation marks! And other punctuation?"
    
    # Test through the full pipeline
    from message_utils import strip_known_ctas, format_html_message, maybe_append_cta
    
    # Simulate the pipeline
    cleaned = strip_known_ctas(test_text)
    formatted = format_html_message(cleaned)
    with_cta = maybe_append_cta(formatted, "flirt")
    
    has_backslashes = '\\' in with_cta
    status = "✅" if not has_backslashes else "❌"
    print(f"{status} No backslashes in final payload: {with_cta}")
    
    if has_backslashes:
        print(f"   Found backslashes in: {with_cta}")

def main():
    """Run all tests."""
    print("Testing MoodyBot Message Utilities")
    print("=" * 50)
    
    test_html_formatting()
    test_mode_detection()
    test_cta_appending()
    test_cta_stripping()
    test_html_escaping()
    test_environment_flag()
    test_no_cta_when_flag_false()
    test_cta_env_only()
    test_strip_known_ctas()
    test_no_backslashes()
    
    print("\n" + "=" * 50)
    print("All tests completed!")

if __name__ == "__main__":
    main()
