# -*- coding: utf-8 -*-
"""
Unit tests for prefab phrase filtering.
Tests removal of unwanted filler phrases from bot outputs.
"""

import os
import unittest
from unittest.mock import patch
from postprocessing import strip_prefab_phrases, process_bot_output

class TestPrefabFiltering(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        # Enable prefab filtering by default
        os.environ['FILTER_PREFABS'] = 'true'
        os.environ['DEBUG'] = 'bot:postprocess'
    
    def test_ah_removal(self):
        """Test removal of leading 'ah, ...' patterns."""
        test_cases = [
            ("ah, reckless mess, you did it again.", "you did it again."),
            ("ah, you beautiful mess, here's the truth.", "here's the truth."),
            ("ah you did it again.", "you did it again."),
            ("Ah, this is important.", "this is important."),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_prefab_phrases(input_text)
                self.assertEqual(result, expected)
    
    def test_oh_reckless_mess_removal(self):
        """Test removal of 'oh, reckless mess' patterns."""
        test_cases = [
            ("oh, reckless mess, you did it again.", "you did it again."),
            ("Oh, reckless mess you did it again.", "you did it again."),
            ("oh, reckless mess,", ""),
            ("Oh, reckless mess", ""),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_prefab_phrases(input_text)
                self.assertEqual(result, expected)
    
    def test_validation_phrase_removal(self):
        """Test removal of validation phrases when used as filler."""
        test_cases = [
            ("you beautiful mess, here's the truth.", "here's the truth."),
            ("you lovable disaster, this is important.", "this is important."),
            ("you storm in eyeliner, listen up.", "listen up."),
            ("you slow burn in a matchstick world, here's what happened.", "here's what happened."),
            ("you chaos with a conscience, this is the deal.", "this is the deal."),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_prefab_phrases(input_text)
                self.assertEqual(result, expected)
    
    def test_preserve_legitimate_usage(self):
        """Test that legitimate usage of phrases is preserved."""
        test_cases = [
            "Cialdini nailed it.",
            "In Gothic mode, rain on rusted swingsets",
            "The beautiful mess of life continues.",
            "You are a beautiful mess, but that's okay.",
            "This is not a prefab phrase.",
        ]
        
        for input_text in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_prefab_phrases(input_text)
                self.assertEqual(result, input_text)
    
    def test_whitespace_cleanup(self):
        """Test that whitespace is properly cleaned up after removal."""
        test_cases = [
            ("ah,   you did it again.", "you did it again."),
            ("oh, reckless mess,   here's the truth.", "here's the truth."),
            ("you beautiful mess,    this is important.", "this is important."),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_prefab_phrases(input_text)
                self.assertEqual(result, expected)
    
    def test_case_insensitive_removal(self):
        """Test that removal works case-insensitively."""
        test_cases = [
            ("AH, you did it again.", "you did it again."),
            ("Oh, Reckless Mess, here's the truth.", "here's the truth."),
            ("YOU BEAUTIFUL MESS, this is important.", "this is important."),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_prefab_phrases(input_text)
                self.assertEqual(result, expected)
    
    def test_empty_string_handling(self):
        """Test handling of empty strings."""
        result = strip_prefab_phrases("")
        self.assertEqual(result, "")
    
    def test_whitespace_only_handling(self):
        """Test handling of whitespace-only strings."""
        result = strip_prefab_phrases("   \n\t   ")
        self.assertEqual(result, "")
    
    def test_multiple_prefabs_removal(self):
        """Test removal of multiple prefab phrases."""
        # This should remove the first one and leave the rest
        input_text = "ah, you beautiful mess, oh, reckless mess, here's the truth."
        result = strip_prefab_phrases(input_text)
        # Should remove "ah, you beautiful mess, " and leave the rest
        expected = "oh, reckless mess, here's the truth."
        self.assertEqual(result, expected)
    
    def test_process_bot_output_with_prefab_filtering(self):
        """Test that process_bot_output includes prefab filtering."""
        # Enable prefab filtering
        os.environ['FILTER_PREFABS'] = 'true'
        
        input_text = "ah, reckless mess, you did it again."
        result = process_bot_output(input_text)
        
        # Should have prefab phrases stripped
        self.assertNotIn("ah, reckless mess", result)
        self.assertIn("you did it again", result)
    
    def test_process_bot_output_without_prefab_filtering(self):
        """Test that process_bot_output can disable prefab filtering."""
        # Disable prefab filtering
        os.environ['FILTER_PREFABS'] = 'false'
        
        input_text = "ah, reckless mess, you did it again."
        result = process_bot_output(input_text)
        
        # Should preserve prefab phrases
        self.assertIn("ah, reckless mess", result)
    
    @patch('postprocessing.logger')
    def test_debug_logging(self, mock_logger):
        """Test that debug logging works when prefab phrases are stripped."""
        input_text = "ah, reckless mess, you did it again."
        result = strip_prefab_phrases(input_text)
        
        # Should log the stripping
        mock_logger.info.assert_called()
        calls = [call[0][0] for call in mock_logger.info.call_args_list]
        self.assertTrue(any("STRIPPED PREFAB" in call for call in calls))
    
    def test_gothic_flourish_preservation(self):
        """Test that Gothic Flourish phrases are preserved."""
        gothic_phrases = [
            "It tasted like rain on rusted swingsets — childhood you could still taste, but not touch.",
            "He smiled the way burned bridges light up a winter night.",
            "The silence pressed against the walls like a rising tide of all the things unsaid.",
        ]
        
        for phrase in gothic_phrases:
            with self.subTest(phrase=phrase):
                result = strip_prefab_phrases(phrase)
                self.assertEqual(result, phrase)

if __name__ == '__main__':
    unittest.main()

