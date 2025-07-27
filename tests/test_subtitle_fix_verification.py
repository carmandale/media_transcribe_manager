#!/usr/bin/env python3
"""
Verification tests for the subtitle translation fix (PR #70).
Ensures segment-by-segment language detection works correctly for mixed-language interviews.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator, SRTSegment
from scribe.translate import HistoricalTranslator


class TestSubtitleFixVerification(unittest.TestCase):
    """Verify the subtitle translation fix works correctly."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mock translator with OpenAI client
        self.mock_translator = Mock(spec=HistoricalTranslator)
        self.mock_translator.openai_client = MagicMock()
        self.srt_translator = SRTTranslator(translator=self.mock_translator)
        
    def test_problematic_segment_detection(self):
        """Test the specific problematic segments from issue #72."""
        # The problematic segment that was incorrectly detected as English
        segment = SRTSegment(1, "00:00:00,000", "00:00:02,000", "In die Wehrmacht gekommen?")
        
        # Mock GPT-4o-mini to return German
        self.mock_translator.openai_client.chat.completions.create.return_value = \
            Mock(choices=[Mock(message=Mock(content="German"))])
        
        # Detect language
        detected = self.srt_translator.detect_segment_language(segment)
        
        # Should be detected as German, not English
        self.assertEqual(detected, 'de', 
                        "Failed to detect 'In die Wehrmacht gekommen?' as German")
        
    def test_word_in_detection(self):
        """Test detection of the word 'in' in different contexts."""
        test_cases = [
            ("In die Wehrmacht gekommen?", 'de'),  # German context
            ("in der Stadt", 'de'),                 # German context
            ("I was born in Germany", 'en'),       # English context
            ("in", None),                           # Too short, ambiguous
        ]
        
        # Mock GPT responses
        gpt_responses = [
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
        ]
        self.mock_translator.openai_client.chat.completions.create.side_effect = gpt_responses
        
        for text, expected_lang in test_cases:
            segment = SRTSegment(1, "00:00:00,000", "00:00:02,000", text)
            detected = self.srt_translator.detect_segment_language(segment)
            
            if expected_lang:
                self.assertEqual(detected, expected_lang,
                               f"Wrong detection for '{text}': expected {expected_lang}, got {detected}")
    
    def test_mixed_language_preservation(self):
        """Test that German segments are preserved when translating to German."""
        segments = [
            SRTSegment(1, "00:00:00,000", "00:00:03,000", 
                      "Ich wurde neunzehnhundertdreißig geboren."),
            SRTSegment(2, "00:00:03,000", "00:00:05,000", 
                      "I was thirty years old."),
            SRTSegment(3, "00:00:05,000", "00:00:08,000", 
                      "In die Wehrmacht gekommen?"),
        ]
        
        # Mock language detection
        self.mock_translator.openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
            Mock(choices=[Mock(message=Mock(content="German"))]),
        ]
        
        # Test translation decisions for German target
        decisions = []
        for segment in segments:
            should_translate = self.srt_translator.should_translate_segment(segment, 'de')
            decisions.append((segment.text[:20], should_translate))
        
        # Verify German segments are NOT translated when target is German
        self.assertFalse(decisions[0][1], "German segment should not be translated to German")
        self.assertTrue(decisions[1][1], "English segment should be translated to German")
        self.assertFalse(decisions[2][1], "German segment should not be translated to German")
    
    def test_segment_boundary_preservation(self):
        """Test that segment boundaries are never violated."""
        # Create segments with exact boundaries
        segments = [
            SRTSegment(1, "00:00:00,000", "00:00:02,000", "First segment"),
            SRTSegment(2, "00:00:02,000", "00:00:04,000", "Second segment"),
            SRTSegment(3, "00:00:04,000", "00:00:06,000", "Third segment"),
        ]
        
        # Process segments (mock to avoid actual translation)
        for segment in segments:
            original_start = segment.start_time
            original_end = segment.end_time
            original_index = segment.index
            
            # Simulate processing
            _ = self.srt_translator.should_translate_segment(segment, 'de')
            
            # Verify boundaries unchanged
            self.assertEqual(segment.start_time, original_start, 
                           f"Start time changed for segment {original_index}")
            self.assertEqual(segment.end_time, original_end,
                           f"End time changed for segment {original_index}")
            self.assertEqual(segment.index, original_index,
                           f"Index changed for segment {original_index}")
    
    def test_gpt4o_mini_language_detection(self):
        """Test that GPT-4o-mini is used for language detection."""
        segment = SRTSegment(1, "00:00:00,000", "00:00:02,000", 
                           "Das ist ein Test")
        
        # Mock GPT response
        self.mock_translator.openai_client.chat.completions.create.return_value = \
            Mock(choices=[Mock(message=Mock(content="German"))])
        
        # Detect language
        detected = self.srt_translator.detect_segment_language(segment)
        
        # Verify GPT-4o-mini was called
        self.mock_translator.openai_client.chat.completions.create.assert_called_once()
        call_args = self.mock_translator.openai_client.chat.completions.create.call_args
        
        # Check model parameter
        self.assertEqual(call_args[1]['model'], 'gpt-4o-mini')
        
        # Check prompt includes the text
        prompt = call_args[1]['messages'][0]['content']
        self.assertIn("Das ist ein Test", prompt)
        self.assertIn("English, German, or Hebrew", prompt)
        
        # Verify detection result
        self.assertEqual(detected, 'de')
    
    def test_fallback_pattern_matching(self):
        """Test fallback pattern matching when GPT is not available."""
        # Create translator without OpenAI client
        translator_no_gpt = SRTTranslator()
        
        test_cases = [
            ("der Mann und die Frau", 'de'),     # Strong German indicators
            ("the man and the woman", 'en'),      # Strong English indicators
            ("מה שלומך היום", 'he'),              # Hebrew characters
        ]
        
        for text, expected_lang in test_cases:
            segment = SRTSegment(1, "00:00:00,000", "00:00:02,000", text)
            detected = translator_no_gpt.detect_segment_language(segment)
            self.assertEqual(detected, expected_lang,
                           f"Pattern matching failed for '{text}'")
    
    def test_non_verbal_preservation(self):
        """Test that non-verbal segments are always preserved."""
        non_verbal_segments = [
            "♪♪",
            "[Music]",
            "[Applause]",
            "♪",
        ]
        
        for text in non_verbal_segments:
            segment = SRTSegment(1, "00:00:00,000", "00:00:02,000", text)
            
            # Should not detect a language
            detected = self.srt_translator.detect_segment_language(segment)
            self.assertIsNone(detected, f"Non-verbal '{text}' should not have language")
            
            # Should never translate
            for target_lang in ['en', 'de', 'he']:
                should_translate = self.srt_translator.should_translate_segment(segment, target_lang)
                self.assertFalse(should_translate, 
                               f"Non-verbal '{text}' should never be translated")
    
    def test_real_interview_pattern(self):
        """Test with a realistic interview pattern from the 728 files."""
        # Simulate a typical pattern found in the interviews
        interview_segments = [
            ("Also, ich bin im Jahr", 'de'),
            ("neunzehnhundertsechsunddreißig.", 'de'),
            ("And then what happened?", 'en'),
            ("Dann kam der Krieg.", 'de'),
            ("♪♪", None),
            ("We had to leave.", 'en'),
            ("Ja, wir mussten weg.", 'de'),
        ]
        
        # Mock GPT responses (skip non-verbal)
        gpt_responses = []
        for text, expected_lang in interview_segments:
            if expected_lang:
                lang_name = {'de': 'German', 'en': 'English', 'he': 'Hebrew'}[expected_lang]
                gpt_responses.append(Mock(choices=[Mock(message=Mock(content=lang_name))]))
        
        self.mock_translator.openai_client.chat.completions.create.side_effect = gpt_responses
        
        # Process each segment
        for i, (text, expected_lang) in enumerate(interview_segments):
            segment = SRTSegment(i+1, f"00:00:{i*3:02d},000", f"00:00:{(i+1)*3:02d},000", text)
            detected = self.srt_translator.detect_segment_language(segment)
            
            self.assertEqual(detected, expected_lang,
                           f"Wrong detection for segment {i+1}: '{text}'")
            
            # Test translation decision for German target
            if expected_lang:
                should_translate = self.srt_translator.should_translate_segment(segment, 'de')
                expected_translate = (expected_lang != 'de')
                self.assertEqual(should_translate, expected_translate,
                               f"Wrong translation decision for segment {i+1}")


class TestBatchProcessingIntegration(unittest.TestCase):
    """Test integration with batch processing scripts."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_fixtures = Path(__file__).parent / "fixtures" / "subtitles"
        
    def test_fixture_files_exist(self):
        """Verify test fixture files were created."""
        expected_files = [
            "mixed_language_interview.srt",
            "german_dominant_interview.srt",
            "edge_cases.srt",
            "simple_test.vtt",
            "timing_precision.srt",
            "simple_test.ass",
        ]
        
        for filename in expected_files:
            filepath = self.test_fixtures / filename
            self.assertTrue(filepath.exists(), f"Fixture file missing: {filename}")
    
    def test_mixed_language_fixture_parsing(self):
        """Test parsing of mixed language fixture."""
        fixture_path = self.test_fixtures / "mixed_language_interview.srt"
        if not fixture_path.exists():
            self.skipTest("Fixture file not found")
        
        translator = SRTTranslator()
        segments = translator.parse_srt(str(fixture_path))
        
        # Verify we have the expected number of segments
        self.assertEqual(len(segments), 20)
        
        # Verify first few segments
        self.assertEqual(segments[0].text, "Also, ich wurde in Berlin geboren.")
        self.assertEqual(segments[2].text, "My father was a businessman.")
        self.assertEqual(segments[5].text, "♪♪")
        
        # Verify timing preservation
        self.assertEqual(segments[0].start_time, "00:00:00,500")
        self.assertEqual(segments[0].end_time, "00:00:04,000")


def run_verification_tests():
    """Run all verification tests."""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSubtitleFixVerification))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestBatchProcessingIntegration))
    
    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_verification_tests()
    sys.exit(0 if success else 1)