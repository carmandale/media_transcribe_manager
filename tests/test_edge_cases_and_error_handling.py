#!/usr/bin/env python3
"""
Edge Cases and Error Handling Tests for Subtitle Translation

This test suite covers Task 3 from spec #73:
- Malformed subtitle files and invalid formats
- API rate limiting and retry logic  
- Partial translation failures
- Character encoding issues (UTF-8, UTF-16, etc.)
- Empty segments and timing-only entries
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict
import json
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scribe.srt_translator import SRTTranslator, SRTSegment, translate_srt_file
from scribe.translate import HistoricalTranslator


class TestMalformedSubtitleFiles(unittest.TestCase):
    """Test handling of malformed and invalid subtitle file formats."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.translator = SRTTranslator()
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test files."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def create_test_file(self, filename: str, content: str, encoding: str = 'utf-8') -> Path:
        """Create test file with specific content and encoding."""
        filepath = self.test_dir / filename
        with open(filepath, 'w', encoding=encoding) as f:
            f.write(content)
        return filepath
    
    def create_binary_file(self, filename: str, content: bytes) -> Path:
        """Create binary test file."""
        filepath = self.test_dir / filename
        with open(filepath, 'wb') as f:
            f.write(content)
        return filepath
    
    def test_malformed_srt_missing_timing(self):
        """Test SRT file with missing timing lines."""
        content = """1
This is segment without timing

2
00:00:02,000 --> 00:00:04,000
This segment has timing

3
This segment also has no timing"""
        
        test_file = self.create_test_file('malformed_timing.srt', content)
        segments = self.translator.parse_srt(str(test_file))
        
        # Should only parse the valid segment
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].index, 2)
        self.assertEqual(segments[0].text, "This segment has timing")
    
    def test_malformed_srt_invalid_timing_format(self):
        """Test SRT file with invalid timing format."""
        content = """1
25:61:75,999 --> 30:70:80,100
Invalid timing format

2
00:00:02,000 -> 00:00:04,000
Wrong arrow format

3
00:00:05,000 --> 00:00:07,000
Valid timing format"""
        
        test_file = self.create_test_file('malformed_format.srt', content)
        segments = self.translator.parse_srt(str(test_file))
        
        # Should parse valid segments (1 and 3) but skip segment 2 with wrong arrow
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].index, 1)
        self.assertEqual(segments[0].text, "Invalid timing format")
        self.assertEqual(segments[1].index, 3)
        self.assertEqual(segments[1].text, "Valid timing format")
    
    def test_malformed_srt_non_numeric_index(self):
        """Test SRT file with non-numeric segment indices."""
        content = """abc
00:00:00,000 --> 00:00:02,000
Non-numeric index

2
00:00:02,000 --> 00:00:04,000
Valid segment

#3
00:00:04,000 --> 00:00:06,000
Hash prefix index"""
        
        test_file = self.create_test_file('malformed_index.srt', content)
        segments = self.translator.parse_srt(str(test_file))
        
        # Should only parse the valid segment
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].index, 2)
        self.assertEqual(segments[0].text, "Valid segment")
    
    def test_empty_srt_file(self):
        """Test completely empty SRT file."""
        test_file = self.create_test_file('empty.srt', '')
        segments = self.translator.parse_srt(str(test_file))
        
        self.assertEqual(len(segments), 0)
    
    def test_srt_file_only_whitespace(self):
        """Test SRT file containing only whitespace."""
        content = "   \n\n\t\t\n   \n\n"
        test_file = self.create_test_file('whitespace.srt', content)
        segments = self.translator.parse_srt(str(test_file))
        
        self.assertEqual(len(segments), 0)
    
    def test_nonexistent_file(self):
        """Test handling of nonexistent files."""
        segments = self.translator.parse_srt('/nonexistent/path/file.srt')
        self.assertEqual(len(segments), 0)
    
    def test_directory_instead_of_file(self):
        """Test passing directory path instead of file."""
        test_dir = self.test_dir / 'subdir'
        test_dir.mkdir()
        
        segments = self.translator.parse_srt(str(test_dir))
        self.assertEqual(len(segments), 0)


class TestCharacterEncodingIssues(unittest.TestCase):
    """Test handling of various character encodings."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.translator = SRTTranslator()
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test files."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_utf8_with_bom(self):
        """Test UTF-8 file with Byte Order Mark (BOM)."""
        content = """1
00:00:00,000 --> 00:00:02,000
German text: Ich bin ein Berliner

2
00:00:02,000 --> 00:00:04,000
Hebrew text: מה שלומך"""
        
        # Create file with BOM
        filepath = self.test_dir / 'utf8_bom.srt'
        with open(filepath, 'wb') as f:
            f.write('\ufeff'.encode('utf-8'))  # BOM
            f.write(content.encode('utf-8'))
        
        segments = self.translator.parse_srt(str(filepath))
        
        # Should parse both segments, handling BOM correctly
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].text, "German text: Ich bin ein Berliner")
        self.assertEqual(segments[1].text, "Hebrew text: מה שלומך")
    
    def test_latin1_encoding(self):
        """Test Latin-1 encoded file (should fail gracefully)."""
        content = """1
00:00:00,000 --> 00:00:02,000
Café français"""
        
        # Create Latin-1 encoded file
        filepath = self.test_dir / 'latin1.srt'
        with open(filepath, 'w', encoding='latin-1') as f:
            f.write(content)
        
        # This should handle encoding error gracefully
        segments = self.translator.parse_srt(str(filepath))
        # Depending on implementation, might return empty list or handle gracefully
        self.assertIsInstance(segments, list)
    
    def test_binary_file(self):
        """Test attempting to parse binary file as SRT."""
        # Create fake binary file
        binary_content = b'\x00\x01\x02\x03\x04\x05' * 100
        filepath = self.test_dir / 'binary.srt'
        with open(filepath, 'wb') as f:
            f.write(binary_content)
        
        segments = self.translator.parse_srt(str(filepath))
        self.assertEqual(len(segments), 0)
    
    def test_mixed_line_endings(self):
        """Test file with mixed line endings (CR, LF, CRLF)."""
        # Create content with mixed line endings
        content_lines = [
            "1\r",  # CR
            "00:00:00,000 --> 00:00:02,000\n",  # LF
            "First segment\r\n",  # CRLF
            "\r\n",  # CRLF
            "2\r",  # CR
            "00:00:02,000 --> 00:00:04,000\n",  # LF
            "Second segment\r\n"  # CRLF
        ]
        
        filepath = self.test_dir / 'mixed_endings.srt'
        with open(filepath, 'wb') as f:
            for line in content_lines:
                f.write(line.encode('utf-8'))
        
        segments = self.translator.parse_srt(str(filepath))
        
        # Should handle mixed line endings
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].text, "First segment")
        self.assertEqual(segments[1].text, "Second segment")


class TestEmptySegmentsAndTimingEntries(unittest.TestCase):
    """Test handling of empty segments and timing-only entries."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.translator = SRTTranslator()
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test files."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def create_test_file(self, filename: str, content: str) -> Path:
        """Create test file with specific content."""
        filepath = self.test_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    
    def test_empty_text_segments(self):
        """Test segments with empty text."""
        content = """1
00:00:00,000 --> 00:00:02,000


2
00:00:02,000 --> 00:00:04,000
Valid text segment

3
00:00:04,000 --> 00:00:06,000

"""
        
        test_file = self.create_test_file('empty_segments.srt', content)
        segments = self.translator.parse_srt(str(test_file))
        
        # Should parse all segments including empty ones
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].text, "")
        self.assertEqual(segments[1].text, "Valid text segment")
        self.assertEqual(segments[2].text, "")
        
        # Test translation logic with empty segments
        self.assertFalse(self.translator.should_translate_segment(segments[0], 'de'))
        self.assertTrue(self.translator.should_translate_segment(segments[1], 'de'))
        self.assertFalse(self.translator.should_translate_segment(segments[2], 'de'))
    
    def test_whitespace_only_segments(self):
        """Test segments with only whitespace."""
        content = """1
00:00:00,000 --> 00:00:02,000
   

2
00:00:02,000 --> 00:00:04,000
	\t\n  

3
00:00:04,000 --> 00:00:06,000
Valid segment"""
        
        test_file = self.create_test_file('whitespace_segments.srt', content)
        segments = self.translator.parse_srt(str(test_file))
        
        self.assertEqual(len(segments), 3)
        
        # Test that whitespace-only segments are not translated
        self.assertFalse(self.translator.should_translate_segment(segments[0], 'de'))
        self.assertFalse(self.translator.should_translate_segment(segments[1], 'de'))
        self.assertTrue(self.translator.should_translate_segment(segments[2], 'de'))
    
    def test_very_short_segments(self):
        """Test very short segments (1-2 characters)."""
        content = """1
00:00:00,000 --> 00:00:02,000
A

2
00:00:02,000 --> 00:00:04,000
No

3
00:00:04,000 --> 00:00:06,000
?

4
00:00:06,000 --> 00:00:08,000
This is long enough"""
        
        test_file = self.create_test_file('short_segments.srt', content)
        segments = self.translator.parse_srt(str(test_file))
        
        self.assertEqual(len(segments), 4)
        
        # Test that very short segments are not translated
        self.assertFalse(self.translator.should_translate_segment(segments[0], 'de'))  # "A"
        self.assertFalse(self.translator.should_translate_segment(segments[1], 'de'))  # "No"
        self.assertFalse(self.translator.should_translate_segment(segments[2], 'de'))  # "?"
        self.assertTrue(self.translator.should_translate_segment(segments[3], 'de'))   # Long text
    
    def test_non_verbal_sounds(self):
        """Test recognition of non-verbal sounds."""
        content = """1
00:00:00,000 --> 00:00:02,000
♪♪

2
00:00:02,000 --> 00:00:04,000
[Music]

3
00:00:04,000 --> 00:00:06,000
[Applause]

4
00:00:06,000 --> 00:00:08,000
...

5
00:00:08,000 --> 00:00:10,000
Normal speech here"""
        
        test_file = self.create_test_file('non_verbal.srt', content)
        segments = self.translator.parse_srt(str(test_file))
        
        self.assertEqual(len(segments), 5)
        
        # Test that non-verbal sounds are not translated
        self.assertFalse(self.translator.should_translate_segment(segments[0], 'de'))  # ♪♪
        self.assertFalse(self.translator.should_translate_segment(segments[1], 'de'))  # [Music]
        self.assertFalse(self.translator.should_translate_segment(segments[2], 'de'))  # [Applause]
        self.assertFalse(self.translator.should_translate_segment(segments[3], 'de'))  # ...
        self.assertTrue(self.translator.should_translate_segment(segments[4], 'de'))   # Normal speech


class TestAPIRateLimitingAndRetryLogic(unittest.TestCase):
    """Test API rate limiting and retry logic handling."""
    
    def setUp(self):
        """Set up test fixtures with mocked translator."""
        self.mock_translator = Mock(spec=HistoricalTranslator)
        self.srt_translator = SRTTranslator(translator=self.mock_translator)
    
    def test_batch_translate_fallback_on_failure(self):
        """Test that batch translate falls back to individual translation on failure."""
        texts = ["Hello world", "This is a test", "Another segment"]
        
        # Mock batch_translate to fail
        self.mock_translator.batch_translate.side_effect = Exception("API Error")
        
        # Mock individual translate to succeed
        self.mock_translator.translate.side_effect = [
            "Hallo Welt",
            "Das ist ein Test", 
            "Ein weiteres Segment"
        ]
        
        result = self.srt_translator.batch_translate(texts, 'de')
        
        # Should fall back to individual translations
        self.assertEqual(result, ["Hallo Welt", "Das ist ein Test", "Ein weiteres Segment"])
        
        # Verify batch_translate was attempted first
        self.mock_translator.batch_translate.assert_called_once_with(texts, 'de', None)
        
        # Verify individual translations were called as fallback
        self.assertEqual(self.mock_translator.translate.call_count, 3)
    
    def test_individual_translate_failures(self):
        """Test handling of individual translation failures."""
        texts = ["Hello world", "This is a test", "Another segment"]
        
        # Mock batch_translate to fail
        self.mock_translator.batch_translate.side_effect = Exception("API Error")
        
        # Mock individual translate with some failures
        self.mock_translator.translate.side_effect = [
            "Hallo Welt",      # Success
            None,              # Failure - returns None
            "Ein weiteres Segment"  # Success
        ]
        
        result = self.srt_translator.batch_translate(texts, 'de')
        
        # Should return empty string for failed translations
        self.assertEqual(result, ["Hallo Welt", "", "Ein weiteres Segment"])
    
    def test_single_text_batch_translate(self):
        """Test batch translate with single text (uses direct translate)."""
        texts = ["Hello world"]
        
        self.mock_translator.translate.return_value = "Hallo Welt"
        
        result = self.srt_translator.batch_translate(texts, 'de')
        
        self.assertEqual(result, ["Hallo Welt"])
        self.mock_translator.translate.assert_called_once_with("Hello world", 'de', None)
        # batch_translate should not be called for single text
        self.mock_translator.batch_translate.assert_not_called()
    
    def test_empty_texts_list(self):
        """Test batch translate with empty texts list."""
        result = self.srt_translator.batch_translate([], 'de')
        
        self.assertEqual(result, [])
        self.mock_translator.translate.assert_not_called()
        self.mock_translator.batch_translate.assert_not_called()


class TestPartialTranslationFailures(unittest.TestCase):
    """Test handling of partial translation failures during SRT processing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test files."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def create_test_srt(self, filename: str, segments: List[Dict]) -> Path:
        """Create test SRT file."""
        content = []
        for i, seg in enumerate(segments, 1):
            content.append(str(i))
            content.append(f"{seg['start']} --> {seg['end']}")
            content.append(seg['text'])
            content.append("")
        
        filepath = self.test_dir / filename
        filepath.write_text('\n'.join(content), encoding='utf-8')
        return filepath
    
    @patch('scribe.srt_translator.translate_srt_file')
    def test_translation_function_failure(self, mock_translate_srt_file):
        """Test handling when translate_srt_file function fails."""
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:02,000', 'text': 'Hello world'},
            {'start': '00:00:02,000', 'end': '00:00:04,000', 'text': 'This is a test'}
        ]
        
        test_file = self.create_test_srt('test.srt', segments)
        output_file = self.test_dir / 'output.srt'
        
        # Mock translate_srt_file to return False (failure)
        mock_translate_srt_file.return_value = False
        
        # The function should handle failure gracefully
        result = translate_srt_file(str(test_file), str(output_file), 'de')
        
        self.assertFalse(result)
    
    def test_boundary_validation_failure(self):
        """Test that boundary validation catches segment mismatches."""
        translator = SRTTranslator()
        
        original = [
            SRTSegment(1, "00:00:00,000", "00:00:02,000", "First"),
            SRTSegment(2, "00:00:02,000", "00:00:04,000", "Second")
        ]
        
        # Create translated segments with different count (should fail)
        translated_wrong_count = [
            SRTSegment(1, "00:00:00,000", "00:00:02,000", "Erste")
        ]
        
        self.assertFalse(translator._validate_segment_boundaries(original, translated_wrong_count))
        
        # Create translated segments with wrong timing (should fail)
        translated_wrong_timing = [
            SRTSegment(1, "00:00:00,000", "00:00:03,000", "Erste"),  # Wrong end time
            SRTSegment(2, "00:00:02,000", "00:00:04,000", "Zweite")
        ]
        
        self.assertFalse(translator._validate_segment_boundaries(original, translated_wrong_timing))
        
        # Create correctly translated segments (should pass)
        translated_correct = [
            SRTSegment(1, "00:00:00,000", "00:00:02,000", "Erste"),
            SRTSegment(2, "00:00:02,000", "00:00:04,000", "Zweite")
        ]
        
        self.assertTrue(translator._validate_segment_boundaries(original, translated_correct))


class TestIntegrationWithExistingFixtures(unittest.TestCase):
    """Test edge cases using existing test fixtures."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.translator = SRTTranslator()
        
        # Find the fixtures directory
        current_dir = Path(__file__).parent
        self.fixtures_dir = current_dir / 'fixtures' / 'subtitles'
        
        if not self.fixtures_dir.exists():
            self.skipTest("Test fixtures directory not found")
    
    def test_edge_cases_fixture(self):
        """Test processing of edge_cases.srt fixture."""
        edge_cases_file = self.fixtures_dir / 'edge_cases.srt'
        
        if not edge_cases_file.exists():
            self.skipTest("edge_cases.srt fixture not found")
        
        segments = self.translator.parse_srt(str(edge_cases_file))
        
        # Should successfully parse all segments from the fixture
        self.assertGreater(len(segments), 0)
        
        # Test that each segment has proper structure
        for segment in segments:
            self.assertIsInstance(segment.index, int)
            self.assertIsInstance(segment.start_time, str)
            self.assertIsInstance(segment.end_time, str)
            self.assertIsInstance(segment.text, str)
            
            # Verify timing format
            self.assertRegex(segment.start_time, r'\d{2}:\d{2}:\d{2},\d{3}')
            self.assertRegex(segment.end_time, r'\d{2}:\d{2}:\d{2},\d{3}')
        
        # Test translation decision logic on edge cases
        for segment in segments:
            decision = self.translator.should_translate_segment(segment, 'de')
            self.assertIsInstance(decision, bool)


class TestPerformanceAndMemoryHandling(unittest.TestCase):
    """Test performance under edge conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.translator = SRTTranslator()
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test files."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_large_segment_count(self):
        """Test handling of file with very large number of segments."""
        # Create file with 1000 segments
        segments = []
        for i in range(1000):
            start_ms = i * 2000  # 2 seconds each
            end_ms = (i + 1) * 2000
            
            start_time = f"00:{start_ms//60000:02d}:{(start_ms//1000)%60:02d},{start_ms%1000:03d}"
            end_time = f"00:{end_ms//60000:02d}:{(end_ms//1000)%60:02d},{end_ms%1000:03d}"
            
            segments.append(f"{i+1}\n{start_time} --> {end_time}\nSegment {i+1} text\n")
        
        content = '\n'.join(segments)
        test_file = self.test_dir / 'large_file.srt'
        test_file.write_text(content, encoding='utf-8')
        
        # Should handle large files without crashing
        parsed_segments = self.translator.parse_srt(str(test_file))
        
        self.assertEqual(len(parsed_segments), 1000)
        self.assertEqual(parsed_segments[0].text, "Segment 1 text")
        self.assertEqual(parsed_segments[999].text, "Segment 1000 text")
    
    def test_very_long_text_segments(self):
        """Test handling of segments with very long text."""
        # Create segment with very long text (10KB)
        long_text = "This is a very long text segment. " * 300  # ~10KB
        
        content = f"""1
00:00:00,000 --> 00:01:00,000
{long_text}

2
00:01:00,000 --> 00:01:02,000
Normal segment"""
        
        test_file = self.test_dir / 'long_text.srt'
        test_file.write_text(content, encoding='utf-8')
        
        segments = self.translator.parse_srt(str(test_file))
        
        self.assertEqual(len(segments), 2)
        self.assertEqual(len(segments[0].text), len(long_text))
        self.assertEqual(segments[1].text, "Normal segment")


if __name__ == '__main__':
    # Run specific test classes or all tests
    unittest.main(verbosity=2)