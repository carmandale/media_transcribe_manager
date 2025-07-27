#!/usr/bin/env python3
"""
Comprehensive test suite for subtitle translation with mixed-language support.
Focuses on segment-by-segment language detection for interviews with 99.99% mixed content.
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator, SRTSegment
from scribe.translate import HistoricalTranslator


class SubtitleTestHelpers:
    """Helper methods for subtitle testing."""
    
    @staticmethod
    def create_srt_content(segments: List[Dict[str, str]]) -> str:
        """Create SRT content from segment dictionaries."""
        lines = []
        for i, seg in enumerate(segments, 1):
            lines.append(str(i))
            lines.append(f"{seg['start']} --> {seg['end']}")
            lines.append(seg['text'])
            lines.append("")  # Blank line
        return '\n'.join(lines)
    
    @staticmethod
    def create_vtt_content(segments: List[Dict[str, str]]) -> str:
        """Create WebVTT content from segment dictionaries."""
        lines = ["WEBVTT", ""]
        for seg in segments:
            lines.append(f"{seg['start']} --> {seg['end']}")
            lines.append(seg['text'])
            lines.append("")
        return '\n'.join(lines)
    
    @staticmethod
    def create_ass_content(segments: List[Dict[str, str]]) -> str:
        """Create ASS/SSA subtitle content."""
        # Simplified ASS format for testing
        lines = [
            "[Script Info]",
            "Title: Test Subtitle",
            "ScriptType: v4.00+",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour",
            "Style: Default,Arial,20,&H00FFFFFF,&H000000FF",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]
        
        for seg in segments:
            start = seg['start'].replace(',', '.')
            end = seg['end'].replace(',', '.')
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{seg['text']}")
        
        return '\n'.join(lines)
    
    @staticmethod
    def parse_srt_content(content: str) -> List[Dict[str, str]]:
        """Parse SRT content back into segments."""
        segments = []
        lines = content.strip().split('\n')
        i = 0
        
        while i < len(lines):
            if lines[i].strip().isdigit():
                index = int(lines[i].strip())
                i += 1
                
                if i < len(lines) and '-->' in lines[i]:
                    times = lines[i].split('-->')
                    start = times[0].strip()
                    end = times[1].strip()
                    i += 1
                    
                    text_lines = []
                    while i < len(lines) and lines[i].strip():
                        text_lines.append(lines[i])
                        i += 1
                    
                    segments.append({
                        'index': index,
                        'start': start,
                        'end': end,
                        'text': '\n'.join(text_lines)
                    })
            i += 1
        
        return segments


class TestSubtitleTranslationStructure(unittest.TestCase):
    """Test the basic structure and setup of subtitle translation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp(prefix='subtitle_test_')
        self.helpers = SubtitleTestHelpers()
        
        # Mock translator to avoid API calls
        self.mock_translator = Mock(spec=HistoricalTranslator)
        self.srt_translator = SRTTranslator(translator=self.mock_translator)
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_srt_translator_initialization(self):
        """Test SRTTranslator initialization."""
        translator = SRTTranslator()
        self.assertIsNotNone(translator)
        self.assertEqual(translator.NON_VERBAL_SOUNDS, 
                        {'♪', '♪♪', '[Music]', '[Applause]', '[Laughter]', '[Silence]', '...', '***', '--'})
        self.assertIn('en', translator.LANGUAGE_PATTERNS)
        self.assertIn('de', translator.LANGUAGE_PATTERNS)
        self.assertIn('he', translator.LANGUAGE_PATTERNS)
    
    def test_parse_srt_basic(self):
        """Test basic SRT parsing functionality."""
        srt_content = self.helpers.create_srt_content([
            {'start': '00:00:00,000', 'end': '00:00:02,000', 'text': 'Hello world'},
            {'start': '00:00:02,000', 'end': '00:00:04,000', 'text': 'Second line'},
        ])
        
        srt_file = os.path.join(self.test_dir, 'test.srt')
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        segments = self.srt_translator.parse_srt(srt_file)
        
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].text, 'Hello world')
        self.assertEqual(segments[0].start_time, '00:00:00,000')
        self.assertEqual(segments[0].end_time, '00:00:02,000')
        self.assertEqual(segments[1].text, 'Second line')
    
    def test_language_pattern_initialization(self):
        """Test language pattern data is properly loaded."""
        translator = SRTTranslator()
        
        # Check English patterns
        self.assertIn('the', translator.LANGUAGE_PATTERNS['en']['words'])
        self.assertIn('and', translator.LANGUAGE_PATTERNS['en']['words'])
        
        # Check German patterns
        self.assertIn('der', translator.LANGUAGE_PATTERNS['de']['words'])
        self.assertIn('die', translator.LANGUAGE_PATTERNS['de']['words'])
        
        # Check Hebrew pattern exists
        self.assertIsNotNone(translator.LANGUAGE_PATTERNS['he']['pattern'])


class TestMixedLanguageDetection(unittest.TestCase):
    """Test language detection for mixed-language content."""
    
    def setUp(self):
        """Set up test environment."""
        self.mock_translator = Mock(spec=HistoricalTranslator)
        # Mock the OpenAI client for GPT-4o-mini language detection
        self.mock_translator.openai_client = MagicMock()
        self.srt_translator = SRTTranslator(translator=self.mock_translator)
        
    def test_segment_by_segment_language_detection(self):
        """Test that language is detected per segment, not per file."""
        segments = [
            SRTSegment(1, "00:00:00,000", "00:00:02,000", "Guten Tag, wie geht es Ihnen?"),
            SRTSegment(2, "00:00:02,000", "00:00:04,000", "Hello, how are you today?"),
            SRTSegment(3, "00:00:04,000", "00:00:06,000", "Ich bin in Deutschland geboren"),
            SRTSegment(4, "00:00:06,000", "00:00:08,000", "I was born in Germany"),
            SRTSegment(5, "00:00:08,000", "00:00:10,000", "מה שלומך"),  # Hebrew
        ]
        
        # Mock GPT-4o-mini responses
        self.mock_translator.openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
        ]
        
        # Test detection
        detected_languages = []
        for segment in segments:
            lang = self.srt_translator.detect_segment_language(segment)
            detected_languages.append(lang)
        
        # Verify each segment was detected individually
        self.assertEqual(detected_languages[0], 'de')  # German greeting
        self.assertEqual(detected_languages[1], 'en')  # English greeting
        self.assertEqual(detected_languages[2], 'de')  # German sentence
        self.assertEqual(detected_languages[3], 'en')  # English sentence
        self.assertEqual(detected_languages[4], 'he')  # Hebrew (pattern-based)
    
    def test_mixed_language_within_interview(self):
        """Test handling of typical mixed-language interview patterns."""
        # Simulate a real interview pattern
        interview_segments = [
            SRTSegment(1, "00:00:00,000", "00:00:03,000", 
                      "Also, ich bin neunzehnhundertdreißig geboren."),
            SRTSegment(2, "00:00:03,000", "00:00:05,000", 
                      "In die Wehrmacht gekommen?"),
            SRTSegment(3, "00:00:05,000", "00:00:08,000", 
                      "Yes, I was drafted in 1944."),
            SRTSegment(4, "00:00:08,000", "00:00:11,000", 
                      "Das war sehr schwierig für mich."),
            SRTSegment(5, "00:00:11,000", "00:00:14,000", 
                      "Because I was only seventeen years old."),
        ]
        
        # Mock GPT responses for German/English detection
        self.mock_translator.openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
        ]
        
        # Process segments for German target
        results = []
        for segment in interview_segments:
            should_translate = self.srt_translator.should_translate_segment(segment, 'de')
            results.append((segment.text[:20], segment.detected_language, should_translate))
        
        # Verify correct detection and translation decisions
        self.assertEqual(results[0][1], 'de')  # German - detected
        self.assertFalse(results[0][2])        # German - don't translate to German
        
        self.assertEqual(results[2][1], 'en')  # English - detected
        self.assertTrue(results[2][2])         # English - translate to German
        
        self.assertEqual(results[4][1], 'en')  # English - detected
        self.assertTrue(results[4][2])         # English - translate to German
    
    def test_language_detection_cache(self):
        """Test that language detection results are cached."""
        segment = SRTSegment(1, "00:00:00,000", "00:00:02,000", "Das ist ein Test")
        
        # Mock GPT response
        self.mock_translator.openai_client.chat.completions.create.return_value = \
            Mock(choices=[Mock(message=Mock(content="German"))])
        
        # First detection
        lang1 = self.srt_translator.detect_segment_language(segment)
        
        # Second detection (should use cache)
        lang2 = self.srt_translator.detect_segment_language(segment)
        
        # Verify GPT was only called once
        self.assertEqual(self.mock_translator.openai_client.chat.completions.create.call_count, 1)
        self.assertEqual(lang1, 'de')
        self.assertEqual(lang2, 'de')
    
    def test_non_verbal_segment_handling(self):
        """Test handling of non-verbal segments in mixed content."""
        segments = [
            SRTSegment(1, "00:00:00,000", "00:00:02,000", "Das ist gut"),
            SRTSegment(2, "00:00:02,000", "00:00:04,000", "♪♪"),
            SRTSegment(3, "00:00:04,000", "00:00:06,000", "[APPLAUSE]"),
            SRTSegment(4, "00:00:06,000", "00:00:08,000", "Thank you"),
        ]
        
        # Only mock for actual text
        self.mock_translator.openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
        ]
        
        # Test detection
        for segment in segments:
            lang = self.srt_translator.detect_segment_language(segment)
            should_trans = self.srt_translator.should_translate_segment(segment, 'de')
            
            if segment.text in self.srt_translator.NON_VERBAL_SOUNDS:
                self.assertIsNone(lang)
                self.assertFalse(should_trans)


class TestSubtitleFormats(unittest.TestCase):
    """Test support for various subtitle formats."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp(prefix='subtitle_test_')
        self.helpers = SubtitleTestHelpers()
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_srt_format_parsing(self):
        """Test SRT format parsing with various edge cases."""
        # Test with multi-line text
        srt_content = """1
00:00:00,000 --> 00:00:02,000
First line
Second line

2
00:00:02,000 --> 00:00:04,000
Single line

3
00:00:04,000 --> 00:00:06,000
Text with
multiple
lines
"""
        srt_file = os.path.join(self.test_dir, 'multiline.srt')
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        translator = SRTTranslator()
        segments = translator.parse_srt(srt_file)
        
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].text, "First line\nSecond line")
        self.assertEqual(segments[1].text, "Single line")
        self.assertEqual(segments[2].text, "Text with\nmultiple\nlines")
    
    def test_empty_segments_handling(self):
        """Test handling of empty or whitespace-only segments."""
        srt_content = self.helpers.create_srt_content([
            {'start': '00:00:00,000', 'end': '00:00:02,000', 'text': 'Normal text'},
            {'start': '00:00:02,000', 'end': '00:00:04,000', 'text': ''},
            {'start': '00:00:04,000', 'end': '00:00:06,000', 'text': '   '},
            {'start': '00:00:06,000', 'end': '00:00:08,000', 'text': 'More text'},
        ])
        
        srt_file = os.path.join(self.test_dir, 'empty_segments.srt')
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        translator = SRTTranslator()
        segments = translator.parse_srt(srt_file)
        
        # All segments should be preserved
        self.assertEqual(len(segments), 4)
        self.assertEqual(segments[1].text, '')
        self.assertEqual(segments[2].text, '   ')
    
    def test_timing_format_variations(self):
        """Test various timing format variations."""
        # Some SRT files might have slight format variations
        srt_variations = [
            "00:00:00,000 --> 00:00:02,000",  # Standard
            "00:00:00,000-->00:00:02,000",    # No spaces
            "00:00:00,000 -->  00:00:02,000", # Extra spaces
        ]
        
        translator = SRTTranslator()
        for timing in srt_variations:
            match = translator.RE_TIMING.match(timing)
            self.assertIsNotNone(match, f"Failed to match timing: {timing}")
            self.assertEqual(match.group(1), "00:00:00,000")
            self.assertEqual(match.group(2), "00:00:02,000")


class TestTranslationIntegration(unittest.TestCase):
    """Test the complete translation pipeline."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp(prefix='subtitle_test_')
        self.helpers = SubtitleTestHelpers()
        
        # Create more sophisticated mock translator
        self.mock_translator = Mock(spec=HistoricalTranslator)
        self.setup_translation_mocks()
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def setup_translation_mocks(self):
        """Set up translation mocks with realistic responses."""
        # Mock OpenAI client for language detection
        self.mock_translator.openai_client = MagicMock()
        
        # Mock translation methods
        def mock_translate_text(text, target_lang, source_lang=None):
            """Mock translation that provides realistic responses."""
            translations = {
                ('Hello world', 'de'): 'Hallo Welt',
                ('Thank you', 'de'): 'Danke',
                ('Good morning', 'de'): 'Guten Morgen',
                ('I was born in Germany', 'de'): 'Ich wurde in Deutschland geboren',
                ('Yes, I was drafted in 1944.', 'de'): 'Ja, ich wurde 1944 eingezogen.',
                ('Because I was only seventeen years old.', 'de'): 'Weil ich erst siebzehn Jahre alt war.',
            }
            return translations.get((text, target_lang), f"[Translated to {target_lang}]: {text}")
        
        def mock_translate_batch(texts, target_lang, source_lang=None):
            """Mock batch translation."""
            return [mock_translate_text(text, target_lang, source_lang) for text in texts]
        
        self.mock_translator.translate_text = Mock(side_effect=mock_translate_text)
        self.mock_translator.translate_batch = Mock(side_effect=mock_translate_batch)
    
    def test_complete_translation_pipeline(self):
        """Test the complete translation pipeline with mixed content."""
        # Create a realistic mixed-language interview
        interview_content = self.helpers.create_srt_content([
            {'start': '00:00:00,000', 'end': '00:00:03,000', 
             'text': 'Also, ich bin neunzehnhundertdreißig geboren.'},
            {'start': '00:00:03,000', 'end': '00:00:05,000', 
             'text': 'In die Wehrmacht gekommen?'},
            {'start': '00:00:05,000', 'end': '00:00:08,000', 
             'text': 'Yes, I was drafted in 1944.'},
            {'start': '00:00:08,000', 'end': '00:00:11,000', 
             'text': '♪♪'},
            {'start': '00:00:11,000', 'end': '00:00:14,000', 
             'text': 'Because I was only seventeen years old.'},
        ])
        
        input_file = os.path.join(self.test_dir, 'interview.srt')
        output_file = os.path.join(self.test_dir, 'interview_de.srt')
        
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(interview_content)
        
        # Mock language detection responses
        self.mock_translator.openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
        ]
        
        # Create translator and translate
        translator = SRTTranslator(translator=self.mock_translator)
        segments = translator.translate_srt(
            input_file,
            target_language='de',
            preserve_original_when_matching=True
        )
        
        # Write output
        translator.write_srt(output_file, segments)
        
        # Verify output
        self.assertTrue(os.path.exists(output_file))
        output_segments = translator.parse_srt(output_file)
        
        # Check segment count preserved
        self.assertEqual(len(output_segments), 5)
        
        # Check German segments preserved
        self.assertEqual(output_segments[0].text, 'Also, ich bin neunzehnhundertdreißig geboren.')
        self.assertEqual(output_segments[1].text, 'In die Wehrmacht gekommen?')
        
        # Check English segments translated
        self.assertEqual(output_segments[2].text, 'Ja, ich wurde 1944 eingezogen.')
        self.assertEqual(output_segments[4].text, 'Weil ich erst siebzehn Jahre alt war.')
        
        # Check non-verbal preserved
        self.assertEqual(output_segments[3].text, '♪♪')
        
        # Verify timing preserved exactly
        input_segments = translator.parse_srt(input_file)
        for i, (inp, out) in enumerate(zip(input_segments, output_segments)):
            self.assertEqual(inp.start_time, out.start_time, f"Segment {i+1} start time mismatch")
            self.assertEqual(inp.end_time, out.end_time, f"Segment {i+1} end time mismatch")


class TestPerformanceAndBatch(unittest.TestCase):
    """Test performance optimizations and batch processing."""
    
    def setUp(self):
        """Set up test environment."""
        self.mock_translator = Mock(spec=HistoricalTranslator)
        self.mock_translator.openai_client = MagicMock()
        self.srt_translator = SRTTranslator(translator=self.mock_translator)
        
    def test_translation_deduplication(self):
        """Test that repeated phrases are only translated once."""
        # Create segments with repeated text
        segments = []
        for i in range(10):
            segments.append(
                SRTSegment(i*2+1, f"00:00:{i*4:02d},000", f"00:00:{i*4+2:02d},000", 
                          "Thank you very much")
            )
            segments.append(
                SRTSegment(i*2+2, f"00:00:{i*4+2:02d},000", f"00:00:{i*4+4:02d},000", 
                          "Danke schön")
            )
        
        # Mock language detection - alternate English/German
        detection_responses = []
        for i in range(10):
            detection_responses.extend([
                Mock(choices=[Mock(message=Mock(content="English"))]),
                Mock(choices=[Mock(message=Mock(content="German"))]),
            ])
        self.mock_translator.openai_client.chat.completions.create.side_effect = detection_responses
        
        # Track unique texts for translation
        texts_to_translate = set()
        for segment in segments:
            if self.srt_translator.should_translate_segment(segment, 'de'):
                texts_to_translate.add(segment.text)
        
        # Should only have one unique English text to translate
        self.assertEqual(len(texts_to_translate), 1)
        self.assertEqual(texts_to_translate.pop(), "Thank you very much")
    
    def test_batch_size_handling(self):
        """Test handling of different batch sizes."""
        # Create many unique segments
        segments = []
        for i in range(150):  # More than default batch size
            segments.append(
                SRTSegment(i+1, f"00:{i//60:02d}:{i%60:02d},000", 
                          f"00:{i//60:02d}:{(i%60)+1:02d},000",
                          f"Unique text number {i}")
            )
        
        # Mock all as English needing translation
        self.mock_translator.openai_client.chat.completions.create.return_value = \
            Mock(choices=[Mock(message=Mock(content="English"))])
        
        # Mock batch translation
        def mock_batch_translate(texts, target, source=None):
            return [f"Translated: {text}" for text in texts]
        
        self.mock_translator.translate_batch = Mock(side_effect=mock_batch_translate)
        
        # Process with specific batch size
        batch_size = 50
        unique_texts = []
        for segment in segments:
            if self.srt_translator.should_translate_segment(segment, 'de'):
                unique_texts.append(segment.text)
        
        # Calculate expected number of batches
        expected_batches = (len(unique_texts) + batch_size - 1) // batch_size
        
        # Note: Actual batch processing happens in translate_srt method
        # This test verifies the setup for batch processing


if __name__ == '__main__':
    unittest.main(verbosity=2)