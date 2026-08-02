# -*- coding: utf-8 -*-
"""
Unit tests for the post-processing pipeline.
Tests proper-noun preservation and spellcheck behavior.
"""

import os
import unittest
from unittest.mock import patch
from postprocessing import (
    process_bot_output, 
    process_user_input,
    is_whitelisted_token,
    preserve_whitelisted_tokens,
    restore_whitelisted_tokens,
    PROPER_NOUN_WHITELIST
)

class TestPostProcessing(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        # Ensure spellcheck is disabled by default
        os.environ['SPELLCHECK_BOT_OUTPUT'] = 'false'
        os.environ['DEBUG'] = 'bot:postprocess'
    
    def test_whitelisted_tokens_unchanged(self):
        """Test that whitelisted tokens like 'Cialdini' remain unchanged."""
        test_cases = [
            "Cialdini proved that influence works",
            "Kahneman said something profound",
            "MoodyBot is always right",
            "The work of Tversky and Kahneman",
            "Da Nang is a beautiful city"
        ]
        
        for input_text in test_cases:
            with self.subTest(input_text=input_text):
                result = process_bot_output(input_text)
                # Should be identical since no spellcheck is enabled
                self.assertEqual(result, input_text)
    
    def test_markdown_escaping_only(self):
        """Test that only MarkdownV2 special characters are escaped."""
        input_text = "This has *bold* and _italic_ text with [links](url)"
        result = process_bot_output(input_text)
        
        # Should escape special characters
        expected = "This has \\*bold\\* and \\_italic\\_ text with \\[links\\]\\(url\\)"
        self.assertEqual(result, expected)
    
    def test_spellcheck_disabled_by_default(self):
        """Test that spellcheck is disabled by default."""
        # Test with intentional misspelling
        input_text = "Cialdini proved that influance works"
        result = process_bot_output(input_text)
        
        # Should remain unchanged (no spellcheck)
        self.assertEqual(result, input_text)
    
    @patch.dict(os.environ, {'SPELLCHECK_BOT_OUTPUT': 'true'})
    def test_spellcheck_enabled_still_protects_whitelist(self):
        """Test that even when spellcheck is enabled, whitelisted words are protected."""
        input_text = "Cialdini proved that influance works"
        result = process_bot_output(input_text)
        
        # Cialdini should be preserved, but other words might be corrected
        self.assertIn("Cialdini", result)
        # The exact behavior depends on the safe_filters implementation
    
    def test_whitelist_token_detection(self):
        """Test whitelist token detection."""
        self.assertTrue(is_whitelisted_token("Cialdini"))
        self.assertTrue(is_whitelisted_token("cialdini"))  # case insensitive
        self.assertTrue(is_whitelisted_token("Kahneman"))
        self.assertFalse(is_whitelisted_token("random"))
        self.assertFalse(is_whitelisted_token("influence"))
    
    def test_preserve_restore_tokens(self):
        """Test the preserve/restore mechanism."""
        input_text = "Cialdini and Kahneman worked together"
        
        # Preserve tokens
        protected, tokens = preserve_whitelisted_tokens(input_text)
        
        # Should have placeholders
        self.assertIn("__PRESERVE_", protected)
        self.assertNotIn("Cialdini", protected)
        self.assertNotIn("Kahneman", protected)
        
        # Restore tokens
        restored = restore_whitelisted_tokens(protected, tokens)
        self.assertEqual(restored, input_text)
    
    def test_empty_input(self):
        """Test handling of empty input."""
        result = process_bot_output("")
        self.assertEqual(result, "")
    
    def test_whitespace_only_input(self):
        """Test handling of whitespace-only input."""
        result = process_bot_output("   \n\t   ")
        self.assertEqual(result, "")
    
    def test_markdown_v2_special_chars(self):
        """Test escaping of all MarkdownV2 special characters."""
        input_text = "_*[]()~`>#+=|{}.!-"
        result = process_bot_output(input_text)
        
        # All special characters should be escaped
        expected = "\\_\\*\\[\\]\\(\\)\\~\\`\\>\\#\\+\\=\\|\\{\\}\\.\\!\\-"
        self.assertEqual(result, expected)
    
    def test_mixed_content_preservation(self):
        """Test preservation of mixed content with whitelisted tokens."""
        input_text = "Cialdini's work on *influence* shows that _persuasion_ works"
        result = process_bot_output(input_text)
        
        # Cialdini should be preserved, Markdown should be escaped
        self.assertIn("Cialdini", result)
        self.assertIn("\\*influence\\*", result)
        self.assertIn("\\_persuasion\\_", result)
    
    def test_user_input_processing(self):
        """Test user input processing (should not modify input)."""
        input_text = "Tell me about Cialdini"
        result = process_user_input(input_text)
        
        # User input should not be modified
        self.assertEqual(result, input_text)
    
    def test_debug_logging(self):
        """Test that debug logging works when enabled."""
        with patch('postprocessing.logger') as mock_logger:
            process_bot_output("Test message")
            
            # Should log stages when DEBUG is enabled
            mock_logger.info.assert_called()
            calls = [call[0][0] for call in mock_logger.info.call_args_list]
            self.assertTrue(any("POST-PROCESSING STAGES" in call for call in calls))

if __name__ == '__main__':
    unittest.main()

