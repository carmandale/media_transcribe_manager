#!/usr/bin/env python3
"""
Comprehensive test suite for subtitle translation functionality.
Tests timing preservation, language detection, and translation accuracy.
"""

import os
import sys
import unittest
from pathlib import Path
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scribe.srt_translator import SRTTranslator, SRTSegment, translate_srt_file


class TestSRTTranslator(unittest.TestCase):
    """Test suite for SRT translation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.translator = SRTTranslator()
        self.test_dir = Path("test_srt_files")
        self.test_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """Clean up test files."""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def create_test_srt(self, filename: str, segments: List[Dict]) -> Path:
        """Create a test SRT file with given segments."""
        content = []
        for i, seg in enumerate(segments, 1):
            content.append(str(i))
            content.append(f"{seg['start']} --> {seg['end']}")
            content.append(seg['text'])
            content.append("")  # Blank line
        
        filepath = self.test_dir / filename
        filepath.write_text('\n'.join(content), encoding='utf-8')
        return filepath
    
    def test_language_detection_accuracy(self):
        """Test language detection for various text samples."""
        test_cases = [
            # (text, expected_language)
            ("In die Wehrmacht gekommen? In", 'de'),
            ("What is your name?", 'en'),
            ("Ich bin ein Berliner", 'de'),
            ("Hello, how are you?", 'en'),
            ("und brauchte auch nicht in den", 'de'),
            ("Das ist sehr gut", 'de'),
            ("This is a test", 'en'),
            ("מה שלומך?", 'he'),  # Hebrew: How are you?
            ("♪♪", None),  # Non-verbal
            ("...", None),  # Non-verbal
        ]
        
        for text, expected_lang in test_cases:
            segment = SRTSegment(1, "00:00:00,000", "00:00:01,000", text)
            detected = self.translator.detect_segment_language(segment)
            self.assertEqual(detected, expected_lang, 
                           f"Failed to detect {expected_lang} for: {text}")
    
    def test_should_translate_logic(self):
        """Test translation decision logic."""
        test_cases = [
            # (text, detected_lang, target_lang, should_translate)
            ("Ich bin ein Berliner", 'de', 'de', False),  # Same language
            ("Ich bin ein Berliner", 'de', 'en', True),   # Different language
            ("Hello world", 'en', 'de', True),            # Different language
            ("Hello world", 'en', 'en', False),           # Same language
            ("♪♪", None, 'de', False),                    # Non-verbal
        ]
        
        for text, detected_lang, target_lang, expected in test_cases:
            segment = SRTSegment(1, "00:00:00,000", "00:00:01,000", text)
            segment.detected_language = detected_lang
            result = self.translator.should_translate_segment(segment, target_lang)
            self.assertEqual(result, expected,
                           f"Wrong decision for {text} ({detected_lang} -> {target_lang})")
    
    def test_timing_preservation(self):
        """Test that timing is preserved exactly during translation."""
        # Create test file
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:02,500', 'text': 'Hello world'},
            {'start': '00:00:02,500', 'end': '00:00:05,000', 'text': 'This is a test'},
            {'start': '00:00:05,000', 'end': '00:00:07,500', 'text': 'Final segment'},
        ]
        
        test_file = self.create_test_srt('timing_test.srt', segments)
        output_file = self.test_dir / 'timing_test_de.srt'
        
        # Translate
        success = translate_srt_file(
            str(test_file),
            str(output_file),
            target_language='de',
            preserve_original_when_matching=True
        )
        
        self.assertTrue(success, "Translation failed")
        
        # Verify timing
        original_segments = self.translator.parse_srt(str(test_file))
        translated_segments = self.translator.parse_srt(str(output_file))
        
        self.assertEqual(len(original_segments), len(translated_segments),
                        "Segment count mismatch")
        
        for orig, trans in zip(original_segments, translated_segments):
            self.assertEqual(orig.start_time, trans.start_time,
                           f"Start time mismatch for segment {orig.index}")
            self.assertEqual(orig.end_time, trans.end_time,
                           f"End time mismatch for segment {orig.index}")
    
    def test_mixed_language_translation(self):
        """Test translation of mixed German/English content."""
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:02,000', 
             'text': 'In die Wehrmacht gekommen?'},  # German - should preserve
            {'start': '00:00:02,000', 'end': '00:00:04,000', 
             'text': 'What is your name?'},  # English - should translate
            {'start': '00:00:04,000', 'end': '00:00:06,000', 
             'text': 'Ich bin ein Berliner'},  # German - should preserve
            {'start': '00:00:06,000', 'end': '00:00:08,000', 
             'text': 'Thank you very much'},  # English - should translate
            {'start': '00:00:08,000', 'end': '00:00:10,000', 
             'text': '♪♪'},  # Non-verbal - should preserve
        ]
        
        test_file = self.create_test_srt('mixed_lang.srt', segments)
        output_file = self.test_dir / 'mixed_lang_de.srt'
        
        # Translate to German
        success = translate_srt_file(
            str(test_file),
            str(output_file),
            target_language='de',
            preserve_original_when_matching=True
        )
        
        self.assertTrue(success, "Translation failed")
        
        # Verify results
        translated_segments = self.translator.parse_srt(str(output_file))
        
        # Check that German segments were preserved
        self.assertEqual(translated_segments[0].text, 'In die Wehrmacht gekommen?')
        self.assertEqual(translated_segments[2].text, 'Ich bin ein Berliner')
        
        # Check that English segments were translated (just verify they changed)
        self.assertNotEqual(translated_segments[1].text, 'What is your name?')
        self.assertNotEqual(translated_segments[3].text, 'Thank you very much')
        
        # Check non-verbal preserved
        self.assertEqual(translated_segments[4].text, '♪♪')
    
    def test_batch_translation_efficiency(self):
        """Test that batch translation reduces API calls."""
        # Create file with repeated phrases
        segments = [
            {'start': f'00:00:{i:02d},000', 'end': f'00:00:{i+1:02d},000',
             'text': 'Hello world' if i % 2 == 0 else 'This is a test'}
            for i in range(10)
        ]
        
        test_file = self.create_test_srt('batch_test.srt', segments)
        
        # Parse and check deduplication
        parsed_segments = self.translator.parse_srt(str(test_file))
        unique_texts = set()
        
        for segment in parsed_segments:
            if self.translator.should_translate_segment(segment, 'de'):
                unique_texts.add(segment.text)
        
        # Should only have 2 unique texts to translate
        self.assertEqual(len(unique_texts), 2,
                        "Deduplication not working correctly")
    
    def test_language_preservation_flag(self):
        """Test preserve_original_when_matching flag behavior."""
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:02,000',
             'text': 'Das ist gut'},  # German text
        ]
        
        test_file = self.create_test_srt('preservation_test.srt', segments)
        
        # Test with preservation ON
        output_preserved = self.test_dir / 'preserved_en.srt'
        translate_srt_file(
            str(test_file),
            str(output_preserved),
            target_language='en',
            preserve_original_when_matching=True
        )
        
        # Test with preservation OFF
        output_translated = self.test_dir / 'translated_en.srt'
        translate_srt_file(
            str(test_file),
            str(output_translated),
            target_language='en',
            preserve_original_when_matching=False
        )
        
        # Check results
        preserved = self.translator.parse_srt(str(output_preserved))
        translated = self.translator.parse_srt(str(output_translated))
        
        # With preservation ON, German->English should translate
        self.assertNotEqual(preserved[0].text, 'Das ist gut',
                           "German text should be translated to English")
        
        # With preservation OFF, should also translate
        self.assertNotEqual(translated[0].text, 'Das ist gut',
                           "German text should be translated to English")
    
    def test_segment_boundary_preservation(self):
        """Test that segment boundaries are never modified during translation."""
        # Create test with potential boundary issues
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:02,000', 'text': 'First segment'},
            {'start': '00:00:02,000', 'end': '00:00:04,000', 'text': ''},  # Empty segment
            {'start': '00:00:04,000', 'end': '00:00:06,000', 'text': 'Third segment'},
            {'start': '00:00:06,000', 'end': '00:00:08,000', 'text': '\n\n'},  # Whitespace
            {'start': '00:00:08,000', 'end': '00:00:10,000', 'text': 'Final segment'},
        ]
        
        test_file = self.create_test_srt('boundary_test.srt', segments)
        output_file = self.test_dir / 'boundary_test_de.srt'
        
        # Translate
        success = translate_srt_file(
            str(test_file),
            str(output_file),
            target_language='de',
            preserve_original_when_matching=True
        )
        
        self.assertTrue(success, "Translation failed")
        
        # Verify segment count preserved
        original_segments = self.translator.parse_srt(str(test_file))
        translated_segments = self.translator.parse_srt(str(output_file))
        
        self.assertEqual(len(original_segments), len(translated_segments),
                        "Segment count must be preserved")
        
        # Verify each segment maintains its boundaries
        for i, (orig, trans) in enumerate(zip(original_segments, translated_segments)):
            self.assertEqual(orig.index, trans.index,
                           f"Segment {i+1} index mismatch")
            self.assertEqual(orig.start_time, trans.start_time,
                           f"Segment {i+1} start time mismatch")
            self.assertEqual(orig.end_time, trans.end_time,
                           f"Segment {i+1} end time mismatch")


def run_specific_test(test_name: str = None):
    """Run a specific test or all tests."""
    if test_name:
        suite = unittest.TestLoader().loadTestsFromName(f'__main__.TestSRTTranslator.{test_name}')
    else:
        suite = unittest.TestLoader().loadTestsFromTestCase(TestSRTTranslator)
    
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


if __name__ == '__main__':
    # Run all tests
    unittest.main()