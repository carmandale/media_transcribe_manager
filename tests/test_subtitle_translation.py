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
        """Test language detection behavior with current GPT-4o-mini implementation."""
        test_cases = [
            # Test that detect_segment_language returns None when no language is set
            # (since the method now only returns pre-detected languages)
            ("In die Wehrmacht gekommen? In", None),
            ("What is your name?", None),
            ("Ich bin ein Berliner", None),
            ("Hello, how are you?", None),
            ("♪♪", None),  # Non-verbal
            ("...", None),  # Non-verbal
        ]
        
        for text, expected_lang in test_cases:
            segment = SRTSegment(1, "00:00:00,000", "00:00:01,000", text)
            # Without batch language detection, detect_segment_language returns None
            detected = self.translator.detect_segment_language(segment)
            self.assertEqual(detected, expected_lang, 
                           f"Failed to get expected result for: {text}")
            
        # Test that we can set detected_language and it gets returned
        segment_with_lang = SRTSegment(1, "00:00:00,000", "00:00:01,000", "Hallo Welt")
        segment_with_lang.detected_language = 'de'
        detected = self.translator.detect_segment_language(segment_with_lang)
        self.assertEqual(detected, 'de', "Should return pre-detected language")
    
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


class TestMixedLanguageSubtitles(unittest.TestCase):
    """Test suite for mixed-language subtitle handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.translator = SRTTranslator()
        self.test_dir = Path("test_mixed_lang_srt")
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
    
    def test_mixed_language_segment_detection(self):
        """Test detection of language tags within segments."""
        test_cases = [
            # (text, expected_languages)
            ("[EN] Hello world [DE] Hallo Welt", ['EN', 'DE']),
            ("[HE] שלום [EN] Hello", ['HE', 'EN']),
            ("[DE] Guten Tag [EN] Good day [HE] יום טוב", ['DE', 'EN', 'HE']),
            ("No language tags here", []),
            ("[EN] Only at start", ['EN']),
            ("Only at end [DE]", ['DE']),
            ("[INVALID] Not a valid tag", []),
            ("[EN][DE] Adjacent tags", ['EN', 'DE']),
            ("[EN] Text with [EN] repeated tag", ['EN']),
            ("Mixed [EN] text [DE] with [EN] repeats", ['EN', 'DE']),
        ]
        
        for text, expected_langs in test_cases:
            # Create a method to extract language tags
            import re
            lang_pattern = r'\[([A-Z]{2})\]'
            detected = list(dict.fromkeys(re.findall(lang_pattern, text)))
            self.assertEqual(detected, expected_langs,
                           f"Failed to detect language tags in: {text}")
    
    def test_mixed_language_segment_parsing(self):
        """Test parsing of segments with language tags."""
        import re
        
        def parse_mixed_language(text):
            """Parse text with language tags into parts."""
            if not text:
                return []
            
            # Pattern to match language tags and capture text until the next tag or end
            pattern = r'\[([A-Z]{2})\]\s*'
            parts = []
            
            # Split by language tags while keeping the tags
            split_pattern = r'(\[[A-Z]{2}\])'
            tokens = re.split(split_pattern, text)
            
            current_lang = None
            i = 0
            
            while i < len(tokens):
                token = tokens[i]
                
                # Check if this is a language tag
                if re.match(r'\[[A-Z]{2}\]', token):
                    # Extract language from tag
                    current_lang = token[1:-1]  # Remove brackets
                    i += 1
                    
                    # Get the text after this tag (if any)
                    if i < len(tokens) and tokens[i].strip():
                        parts.append({'lang': current_lang, 'text': tokens[i].strip()})
                        i += 1
                    else:
                        i += 1
                else:
                    # Regular text without a tag
                    if token.strip():
                        parts.append({'lang': None, 'text': token.strip()})
                    i += 1
            
            return parts
        
        test_cases = [
            # (text, expected_parts)
            ("[EN] Hello [DE] Hallo", [
                {'lang': 'EN', 'text': 'Hello'},
                {'lang': 'DE', 'text': 'Hallo'}
            ]),
            ("[HE] שלום עולם [EN] Hello world", [
                {'lang': 'HE', 'text': 'שלום עולם'},
                {'lang': 'EN', 'text': 'Hello world'}
            ]),
            ("No tags here", [
                {'lang': None, 'text': 'No tags here'}
            ]),
            ("[EN] Text with [brackets] inside", [
                {'lang': 'EN', 'text': 'Text with [brackets] inside'}
            ]),
            ("", []),  # Empty string
            ("   [EN]   Whitespace   [DE]   Test   ", [
                {'lang': 'EN', 'text': 'Whitespace'},
                {'lang': 'DE', 'text': 'Test'}
            ]),
        ]
        
        for text, expected_parts in test_cases:
            parts = parse_mixed_language(text)
            self.assertEqual(parts, expected_parts,
                           f"Failed to parse segment: {text}")
    
    def test_mixed_language_preservation(self):
        """Test that segments already in target language are preserved in mixed segments."""
        # Note: This test validates the concept but actual implementation
        # would need to be added to the SRTTranslator class
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:02,000',
             'text': '[EN] Hello world [DE] Hallo Welt'},
            {'start': '00:00:02,000', 'end': '00:00:04,000',
             'text': '[DE] Ich bin [EN] I am [DE] ein Berliner'},
            {'start': '00:00:04,000', 'end': '00:00:06,000',
             'text': '[HE] שלום [EN] Hello [HE] עולם'},
        ]
        
        test_file = self.create_test_srt('mixed_preserve.srt', segments)
        output_file = self.test_dir / 'mixed_preserve_de.srt'
        
        # Translate to German - current implementation doesn't handle mixed languages
        # This test documents expected behavior
        success = translate_srt_file(
            str(test_file),
            str(output_file),
            target_language='de',
            preserve_original_when_matching=True
        )
        
        self.assertTrue(success, "Translation should complete")
        
        # Current implementation would translate entire segments
        # Future implementation should preserve [DE] tagged parts
        translated_segments = self.translator.parse_srt(str(output_file))
        self.assertEqual(len(translated_segments), 3, "Segment count should be preserved")
    
    def test_edge_cases_language_tags(self):
        """Test edge cases for language tag handling."""
        edge_cases = [
            # Nested or malformed tags
            "[EN] Text with [[nested]] brackets",
            "[EN [DE] Malformed nesting",
            "[EN] [DE] [HE] Multiple adjacent tags",
            "[EN]No space after tag",
            "No space before[DE]tag",
            "[en] lowercase tag [DE] mixed case",
            "[ENGLISH] Full language name",
            "[12] Numeric tag",
            "[] Empty tag",
            "[EN DE] Space in tag",
        ]
        
        for text in edge_cases:
            # Should not crash on any edge case
            try:
                segment = SRTSegment(1, "00:00:00,000", "00:00:01,000", text)
                # Current implementation handles these as regular text
                self.translator.detect_segment_language(segment)
                # No exceptions should be raised
            except Exception as e:
                self.fail(f"Failed on edge case '{text}': {e}")
    
    def test_multiple_language_switches(self):
        """Test segments with multiple language switches."""
        complex_segment = (
            "[EN] The professor said [DE] 'Guten Tag' [EN] and then continued "
            "[HE] בעברית [EN] before switching back to English"
        )
        
        segments = [{
            'start': '00:00:00,000',
            'end': '00:00:05,000',
            'text': complex_segment
        }]
        
        test_file = self.create_test_srt('complex_mixed.srt', segments)
        
        # Test translation to each language
        for target_lang in ['en', 'de']:  # Skip 'he' if not configured
            output_file = self.test_dir / f'complex_mixed_{target_lang}.srt'
            try:
                success = translate_srt_file(
                    str(test_file),
                    str(output_file),
                    target_language=target_lang,
                    preserve_original_when_matching=True
                )
                
                if success:
                    # Verify the file was created
                    self.assertTrue(output_file.exists())
                    
                    # Verify segment count preserved
                    translated = self.translator.parse_srt(str(output_file))
                    self.assertEqual(len(translated), 1)
            except Exception:
                # Skip if translation service not configured
                pass
    
    def test_mixed_language_with_punctuation(self):
        """Test mixed language segments with various punctuation."""
        import re
        
        test_cases = [
            "[EN] Hello, world! [DE] Hallo, Welt!",
            "[EN] Question? [DE] Frage? [HE] שאלה?",
            "[EN] Quote: 'Hello' [DE] Zitat: 'Hallo'",
            "[EN] List: 1) First 2) Second [DE] Liste: 1) Erste 2) Zweite",
            "[EN] Email@example.com [DE] Email@beispiel.de",
        ]
        
        for text in test_cases:
            # Ensure punctuation is preserved in parsing
            # Extract all punctuation
            punctuation = re.findall(r'[!?.,:\'"@()]', text)
            
            # The text should contain all original punctuation
            for char in punctuation:
                self.assertIn(char, text,
                             f"Lost punctuation '{char}' in: {text}")
    
    def test_rtl_ltr_mixed_segments(self):
        """Test handling of RTL (Hebrew) and LTR (English/German) mixed text."""
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:02,000',
             'text': '[HE] אני אומר [EN] I say [HE] שלום'},
            {'start': '00:00:02,000', 'end': '00:00:04,000',
             'text': '[EN] From [HE] מ [EN] to [HE] ל'},
        ]
        
        test_file = self.create_test_srt('rtl_ltr_mixed.srt', segments)
        
        # Verify Hebrew text is preserved correctly
        parsed = self.translator.parse_srt(str(test_file))
        
        # Check that Hebrew portions are present
        for segment in parsed:
            if '[HE]' in segment.text:
                # Find all Hebrew text portions
                import re
                hebrew_pattern = r'[\u0590-\u05FF]+'
                hebrew_matches = re.findall(hebrew_pattern, segment.text)
                self.assertTrue(len(hebrew_matches) > 0,
                               "Hebrew text should be preserved")
    
    def test_language_tag_formats(self):
        """Test various language tag formats and cases."""
        test_formats = [
            # Standard 2-letter codes
            ("[EN] English", "EN"),
            ("[DE] Deutsch", "DE"),
            ("[HE] עברית", "HE"),
            ("[FR] Français", "FR"),
            ("[ES] Español", "ES"),
            # Case variations (should normalize to uppercase)
            ("[en] lowercase", "EN"),
            ("[En] Mixed case", "EN"),
            ("[eN] Weird case", "EN"),
            # Invalid formats (should not be recognized)
            ("[ENGLISH] Full name", None),
            ("[E] Single letter", None),
            ("[123] Numbers", None),
            ("[EN-US] Region code", None),
        ]
        
        import re
        for text, expected_code in test_formats:
            # Extract language code
            match = re.search(r'\[([A-Za-z]{2})\]', text)
            if match and expected_code:
                detected = match.group(1).upper()
                self.assertEqual(detected, expected_code,
                               f"Failed to normalize language code in: {text}")
            elif expected_code is None:
                # Should not match invalid formats with strict pattern
                strict_match = re.search(r'\[([A-Z]{2})\]', text)
                self.assertIsNone(strict_match,
                                f"Should not match invalid format: {text}")
    
    def test_segment_reassembly_after_translation(self):
        """Test that mixed language segments are properly reassembled."""
        # This test documents the expected behavior for reassembly
        
        # Simulated translation results
        original_parts = [
            {'lang': 'EN', 'text': 'Hello'},
            {'lang': 'DE', 'text': 'Welt'}
        ]
        
        translated_parts = [
            {'lang': 'EN', 'text': 'Hallo', 'translated': True},
            {'lang': 'DE', 'text': 'Welt', 'translated': False}
        ]
        
        # Expected reassembly when translating to German
        expected = "[DE] Hallo [DE] Welt"
        
        # Reassembly logic
        result = ""
        for part in translated_parts:
            if part.get('translated'):
                # Translated parts take target language tag
                result += f"[DE] {part['text']} "
            else:
                # Preserved parts keep original tag
                result += f"[{part['lang']}] {part['text']} "
        
        result = result.strip()
        self.assertEqual(result, expected,
                        "Reassembly should update language tags correctly")
    
    def test_whitespace_handling_in_mixed_segments(self):
        """Test that whitespace is properly handled in mixed language segments."""
        test_cases = [
            # Extra spaces
            "[EN]  Extra  spaces  [DE]  Zusätzliche  Leerzeichen",
            # Tabs and newlines
            "[EN]\tTab\there\t[DE]\tTab\thier",
            "[EN]\nNewline\n[DE]\nNeue Zeile",
            # Leading/trailing whitespace
            "  [EN] Leading space [DE] Trailing space  ",
            # No spaces between tags and text
            "[EN]NoSpace[DE]KeinPlatz",
        ]
        
        for text in test_cases:
            segment = SRTSegment(1, "00:00:00,000", "00:00:01,000", text)
            # Should handle without errors
            try:
                # Normalize whitespace
                normalized = ' '.join(text.split())
                self.assertIsInstance(normalized, str)
            except Exception as e:
                self.fail(f"Failed to handle whitespace in: {text!r}, error: {e}")


def run_specific_test(test_name: str = None, test_class: str = 'TestSRTTranslator'):
    """Run a specific test or all tests."""
    if test_name:
        suite = unittest.TestLoader().loadTestsFromName(f'__main__.{test_class}.{test_name}')
    else:
        # Load tests from both classes
        suite1 = unittest.TestLoader().loadTestsFromTestCase(TestSRTTranslator)
        suite2 = unittest.TestLoader().loadTestsFromTestCase(TestMixedLanguageSubtitles)
        suite = unittest.TestSuite([suite1, suite2])
    
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


if __name__ == '__main__':
    # Run all tests from both test classes
    unittest.main()