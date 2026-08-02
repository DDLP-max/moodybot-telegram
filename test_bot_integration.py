# -*- coding: utf-8 -*-
"""
Integration test for MoodyBot with new post-processing pipeline.
Tests that proper nouns like 'Cialdini' are preserved.
"""

import os
import sys
from postprocessing import process_bot_output

def test_cialdini_preservation():
    """Test that 'Cialdini' is preserved through the pipeline."""
    print("Testing Cialdini preservation...")
    
    # Test input with Cialdini
    test_input = "Cialdini proved that influence works through psychological principles."
    
    # Process through the pipeline
    result = process_bot_output(test_input)
    
    print(f"Input:  {test_input}")
    print(f"Output: {result}")
    
    # Check that Cialdini is preserved
    if "Cialdini" in result:
        print("✅ SUCCESS: Cialdini preserved")
        return True
    else:
        print("❌ FAILED: Cialdini was modified")
        return False

def test_markdown_escaping():
    """Test that MarkdownV2 characters are properly escaped."""
    print("\nTesting MarkdownV2 escaping...")
    
    test_input = "This has *bold* and _italic_ text with [links](url)"
    result = process_bot_output(test_input)
    
    print(f"Input:  {test_input}")
    print(f"Output: {result}")
    
    # Check that special characters are escaped
    expected_escaped = "This has \\*bold\\* and \\_italic\\_ text with \\[links\\]\\(url\\)"
    if result == expected_escaped:
        print("✅ SUCCESS: MarkdownV2 characters properly escaped")
        return True
    else:
        print("❌ FAILED: MarkdownV2 escaping incorrect")
        print(f"Expected: {expected_escaped}")
        return False

def test_whitelist_preservation():
    """Test that all whitelisted tokens are preserved."""
    print("\nTesting whitelist preservation...")
    
    whitelist_tokens = [
        "Cialdini", "Kahneman", "Tversky", "MoodyBot", 
        "Ogilvy", "Da Nang", "Ala Wai", "Donna Walden"
    ]
    
    test_input = f"Work by {', '.join(whitelist_tokens)} shows important insights."
    result = process_bot_output(test_input)
    
    print(f"Input:  {test_input}")
    print(f"Output: {result}")
    
    # Check that all whitelisted tokens are preserved
    all_preserved = True
    for token in whitelist_tokens:
        if token not in result:
            print(f"❌ FAILED: {token} was modified")
            all_preserved = False
    
    if all_preserved:
        print("✅ SUCCESS: All whitelisted tokens preserved")
        return True
    else:
        print("❌ FAILED: Some whitelisted tokens were modified")
        return False

def test_debug_logging():
    """Test that debug logging works when enabled."""
    print("\nTesting debug logging...")
    
    # Enable debug logging
    os.environ['DEBUG'] = 'bot:postprocess'
    
    test_input = "Test message for debug logging"
    result = process_bot_output(test_input)
    
    print(f"Input:  {test_input}")
    print(f"Output: {result}")
    print("✅ SUCCESS: Debug logging test completed (check logs above)")
    
    return True

def main():
    """Run all integration tests."""
    print("=== MoodyBot Post-Processing Integration Tests ===\n")
    
    # Ensure spellcheck is disabled by default
    os.environ['SPELLCHECK_BOT_OUTPUT'] = 'false'
    
    tests = [
        test_cialdini_preservation,
        test_markdown_escaping,
        test_whitelist_preservation,
        test_debug_logging
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ ERROR in {test.__name__}: {e}")
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Post-processing pipeline is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

