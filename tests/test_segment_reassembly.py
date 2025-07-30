#!/usr/bin/env python3
"""
Test suite for proper segment reassembly after subtitle translation.

Implements Task 2.4: Add tests for proper segment reassembly after translation
as part of the subtitle translation testing spec.

This covers comprehensive testing of segment boundary preservation, proper
SRT file structure maintenance, and validation that translated segments
are correctly reassembled into valid subtitle files.
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator, SRTSegment
from scribe.translate import HistoricalTranslator
from scribe.batch_language_detection import detect_languages_for_segments


class TestSegmentReassembly:
    """Test suite for segment reassembly after translation."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        temp_dir = tempfile.mkdtemp()
        input_dir = Path(temp_dir) / "input"
        output_dir = Path(temp_dir) / "output" 
        input_dir.mkdir()
        output_dir.mkdir()
        
        yield {
            'base': Path(temp_dir),
            'input': input_dir,
            'output': output_dir
        }
        
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_translator(self):
        """Create mock translator with translation capabilities."""
        translator = Mock(spec=HistoricalTranslator)
        translator.openai_client = MagicMock()
        
        # Mock translation responses
        def mock_translate(text, target_lang, source_lang=None):
            translations = {
                ("Hello world", "de"): "Hallo Welt",
                ("This is a test", "de"): "Das ist ein Test",
                ("Thank you", "de"): "Danke schön",
                ("How are you?", "de"): "Wie geht es dir?",
                ("Good morning", "de"): "Guten Morgen",
                ("Please help me", "de"): "Bitte hilf mir",
                ("I need assistance", "de"): "Ich brauche Hilfe",
                ("The weather is nice", "de"): "Das Wetter ist schön",
            }
            return translations.get((text, target_lang), f"[TRANSLATED: {text}]")
        
        def mock_batch_translate(texts, target_lang, source_lang=None):
            return [mock_translate(text, target_lang, source_lang) for text in texts]
        
        translator.translate.side_effect = mock_translate
        translator.batch_translate.side_effect = mock_batch_translate
        
        return translator
    
    @pytest.fixture
    def srt_translator(self, mock_translator):
        """Create SRTTranslator with mocked dependencies."""
        return SRTTranslator(translator=mock_translator)
    
    def create_test_srt_file(self, temp_dirs, filename: str, segments: List[Dict]) -> Path:
        """
        Create a test SRT file with given segments.
        
        Args:
            temp_dirs: Temporary directories fixture
            filename: Name of the SRT file
            segments: List of segment dictionaries with 'start', 'end', 'text' keys
        
        Returns:
            Path to the created SRT file
        """
        content = []
        for i, segment in enumerate(segments, 1):
            content.append(str(i))
            content.append(f"{segment['start']} --> {segment['end']}")
            content.append(segment['text'])
            content.append("")  # Blank line between segments
        
        srt_path = temp_dirs['input'] / filename
        srt_path.write_text('\n'.join(content), encoding='utf-8')
        return srt_path
    
    @pytest.mark.segment_reassembly
    def test_segment_index_preservation(self, srt_translator, mock_translator, temp_dirs):
        """Test that segment indices are preserved exactly during reassembly."""
        # Create SRT with non-sequential indices (edge case)
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:03,000', 'text': 'Hello world'},
            {'start': '00:00:03,000', 'end': '00:00:06,000', 'text': 'This is a test'},
            {'start': '00:00:06,000', 'end': '00:00:09,000', 'text': 'Thank you'},
            {'start': '00:00:09,000', 'end': '00:00:12,000', 'text': 'Good morning'},
        ]
        
        input_file = self.create_test_srt_file(temp_dirs, 'index_test.srt', segments)
        output_file = temp_dirs['output'] / 'index_test_de.srt'
        
        # Parse original file
        original_segments = srt_translator.parse_srt(str(input_file))
        
        # Mock language detection - all English
        for segment in original_segments:
            segment.detected_language = "en"
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="1: English\n2: English\n3: English\n4: English"))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Translate
        translated_segments = srt_translator.translate_srt(
            str(input_file),
            target_language="de",
            preserve_original_when_matching=True
        )
        
        # Save translated file
        success = srt_translator.save_translated_srt(translated_segments, str(output_file))
        assert success, "Failed to save translated SRT file"
        
        # Parse translated file and verify indices
        reparsed_segments = srt_translator.parse_srt(str(output_file))
        
        assert len(original_segments) == len(reparsed_segments), \
            "Number of segments changed during reassembly"
        
        for orig, reparsed in zip(original_segments, reparsed_segments):
            assert orig.index == reparsed.index, \
                f"Index mismatch: original {orig.index} != reparsed {reparsed.index}"
    
    @pytest.mark.segment_reassembly
    def test_timing_boundary_preservation(self, srt_translator, mock_translator, temp_dirs):
        """Test that timing boundaries are preserved exactly during reassembly."""
        # Create segments with precise timing variations
        segments = [
            {'start': '00:00:00,123', 'end': '00:00:02,456', 'text': 'Hello world'},
            {'start': '00:00:02,456', 'end': '00:00:05,789', 'text': 'This is a test'},
            {'start': '00:00:05,789', 'end': '00:00:08,012', 'text': 'Thank you'},
            {'start': '00:00:08,012', 'end': '00:00:11,345', 'text': 'Good morning'},
        ]
        
        input_file = self.create_test_srt_file(temp_dirs, 'timing_test.srt', segments)
        output_file = temp_dirs['output'] / 'timing_test_de.srt'
        
        # Parse and translate
        original_segments = srt_translator.parse_srt(str(input_file))
        
        # Mock language detection
        for segment in original_segments:
            segment.detected_language = "en"
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="1: English\n2: English\n3: English\n4: English"))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        translated_segments = srt_translator.translate_srt(
            str(input_file),
            target_language="de",
            preserve_original_when_matching=True
        )
        
        # Save and reparse
        srt_translator.save_translated_srt(translated_segments, str(output_file))
        reparsed_segments = srt_translator.parse_srt(str(output_file))
        
        # Verify timing preservation
        for orig, reparsed in zip(original_segments, reparsed_segments):
            assert orig.start_time == reparsed.start_time, \
                f"Start time changed: {orig.start_time} != {reparsed.start_time}"
            assert orig.end_time == reparsed.end_time, \
                f"End time changed: {orig.end_time} != {reparsed.end_time}"
    
    @pytest.mark.segment_reassembly
    def test_text_content_reassembly(self, srt_translator, mock_translator, temp_dirs):
        """Test that text content is correctly reassembled after translation."""
        # Create segments with various text patterns
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:03,000', 'text': 'Hello world'},
            {'start': '00:00:03,000', 'end': '00:00:06,000', 'text': 'This is a test\nwith multiple lines'},
            {'start': '00:00:06,000', 'end': '00:00:09,000', 'text': 'Special chars: é, ñ, ü'},
            {'start': '00:00:09,000', 'end': '00:00:12,000', 'text': '   Whitespace padding   '},
        ]
        
        input_file = self.create_test_srt_file(temp_dirs, 'text_test.srt', segments)
        output_file = temp_dirs['output'] / 'text_test_de.srt'
        
        # Parse and translate
        original_segments = srt_translator.parse_srt(str(input_file))
        
        # Mock language detection
        for segment in original_segments:
            segment.detected_language = "en"
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="1: English\n2: English\n3: English\n4: English"))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        translated_segments = srt_translator.translate_srt(
            str(input_file),
            target_language="de",
            preserve_original_when_matching=True
        )
        
        # Save and reparse
        srt_translator.save_translated_srt(translated_segments, str(output_file))
        reparsed_segments = srt_translator.parse_srt(str(output_file))
        
        # Verify text content structure (not exact content since it's translated)
        for orig, reparsed in zip(original_segments, reparsed_segments):
            # Check that multi-line structure is preserved
            orig_lines = orig.text.count('\n')
            reparsed_lines = reparsed.text.count('\n')
            assert orig_lines == reparsed_lines, \
                f"Line count changed: {orig_lines} != {reparsed_lines}"
            
            # Check that non-empty content remains non-empty
            assert len(reparsed.text.strip()) > 0, \
                f"Text content became empty after reassembly"
    
    @pytest.mark.segment_reassembly
    def test_empty_and_whitespace_segment_handling(self, srt_translator, mock_translator, temp_dirs):
        """Test proper handling of empty and whitespace-only segments during reassembly."""
        # Create segments with edge cases
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:02,000', 'text': 'Hello world'},
            {'start': '00:00:02,000', 'end': '00:00:04,000', 'text': ''},               # Empty
            {'start': '00:00:04,000', 'end': '00:00:06,000', 'text': '   '},            # Whitespace only
            {'start': '00:00:06,000', 'end': '00:00:08,000', 'text': '\n\n'},          # Newlines only
            {'start': '00:00:08,000', 'end': '00:00:10,000', 'text': 'Thank you'},
        ]
        
        input_file = self.create_test_srt_file(temp_dirs, 'empty_test.srt', segments)
        output_file = temp_dirs['output'] / 'empty_test_de.srt'
        
        # Parse and translate
        original_segments = srt_translator.parse_srt(str(input_file))
        
        # Mock language detection (empty segments get None)
        for i, segment in enumerate(original_segments):
            if segment.text.strip():
                segment.detected_language = "en"
            else:
                segment.detected_language = None
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="1: English\n2: None\n3: None\n4: None\n5: English"))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        translated_segments = srt_translator.translate_srt(
            str(input_file),
            target_language="de",
            preserve_original_when_matching=True
        )
        
        # Save and reparse
        srt_translator.save_translated_srt(translated_segments, str(output_file))
        reparsed_segments = srt_translator.parse_srt(str(output_file))
        
        # Verify all segments are preserved including empty ones
        assert len(original_segments) == len(reparsed_segments), \
            "Empty segments were not preserved during reassembly"
        
        # Verify empty segments remain empty
        for orig, reparsed in zip(original_segments, reparsed_segments):
            if not orig.text.strip():
                assert reparsed.text == orig.text, \
                    f"Empty segment content changed: '{orig.text}' != '{reparsed.text}'"
    
    @pytest.mark.segment_reassembly
    def test_large_segment_count_reassembly(self, srt_translator, mock_translator, temp_dirs):
        """Test reassembly of SRT files with large number of segments."""
        # Create many segments to test scalability
        segments = []
        for i in range(100):
            start_time = f"00:{i//60:02d}:{i%60:02d},000"
            end_time = f"00:{(i+1)//60:02d}:{(i+1)%60:02d},000"
            segments.append({
                'start': start_time,
                'end': end_time,
                'text': f'Segment {i+1}: Hello world'
            })
        
        input_file = self.create_test_srt_file(temp_dirs, 'large_test.srt', segments)
        output_file = temp_dirs['output'] / 'large_test_de.srt'
        
        # Parse and translate
        original_segments = srt_translator.parse_srt(str(input_file))
        
        # Mock language detection - all English
        for segment in original_segments:
            segment.detected_language = "en"
        
        # Mock batch language detection for all segments
        detection_response = "\n".join([f"{i}: English" for i in range(1, 101)])
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=detection_response))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        translated_segments = srt_translator.translate_srt(
            str(input_file),
            target_language="de",
            preserve_original_when_matching=True
        )
        
        # Save and reparse
        srt_translator.save_translated_srt(translated_segments, str(output_file))
        reparsed_segments = srt_translator.parse_srt(str(output_file))
        
        # Verify all segments are preserved
        assert len(original_segments) == len(reparsed_segments) == 100, \
            f"Segment count mismatch: original={len(original_segments)}, reparsed={len(reparsed_segments)}"
        
        # Verify first and last segments for boundary conditions
        assert original_segments[0].index == reparsed_segments[0].index == 1, \
            "First segment index not preserved"
        assert original_segments[-1].index == reparsed_segments[-1].index == 100, \
            "Last segment index not preserved"
    
    @pytest.mark.segment_reassembly
    def test_mixed_language_preservation_in_reassembly(self, srt_translator, mock_translator, temp_dirs):
        """Test that mixed-language segments are properly preserved during reassembly."""
        # Create mixed-language content
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:03,000', 'text': 'Hello world'},      # English -> translate
            {'start': '00:00:03,000', 'end': '00:00:06,000', 'text': 'Das ist gut'},      # German -> preserve
            {'start': '00:00:06,000', 'end': '00:00:09,000', 'text': 'Thank you'},        # English -> translate
            {'start': '00:00:09,000', 'end': '00:00:12,000', 'text': 'Guten Tag'},        # German -> preserve
        ]
        
        input_file = self.create_test_srt_file(temp_dirs, 'mixed_lang_test.srt', segments)
        output_file = temp_dirs['output'] / 'mixed_lang_test_de.srt'
        
        # Parse and set languages manually
        original_segments = srt_translator.parse_srt(str(input_file))
        original_segments[0].detected_language = "en"
        original_segments[1].detected_language = "de"
        original_segments[2].detected_language = "en" 
        original_segments[3].detected_language = "de"
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="1: English\n2: German\n3: English\n4: German"))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        translated_segments = srt_translator.translate_srt(
            str(input_file),
            target_language="de",
            preserve_original_when_matching=True
        )
        
        # Save and reparse
        srt_translator.save_translated_srt(translated_segments, str(output_file))
        reparsed_segments = srt_translator.parse_srt(str(output_file))
        
        # Verify mixed language preservation
        expected_preserved = [False, True, False, True]  # Which segments should be preserved
        
        for i, (orig, reparsed, should_preserve) in enumerate(zip(original_segments, reparsed_segments, expected_preserved)):
            if should_preserve:
                assert orig.text == reparsed.text, \
                    f"German segment {i+1} should be preserved: '{orig.text}' != '{reparsed.text}'"
            else:
                assert orig.text != reparsed.text, \
                    f"English segment {i+1} should be translated: '{orig.text}' == '{reparsed.text}'"
    
    @pytest.mark.segment_reassembly
    def test_file_encoding_preservation(self, srt_translator, mock_translator, temp_dirs):
        """Test that file encoding is properly handled during reassembly."""
        # Create segments with international characters
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:03,000', 'text': 'Café München'},
            {'start': '00:00:03,000', 'end': '00:00:06,000', 'text': 'Zürich naïve résumé'},
            {'start': '00:00:06,000', 'end': '00:00:09,000', 'text': 'שלום עולם'},         # Hebrew
            {'start': '00:00:09,000', 'end': '00:00:12,000', 'text': 'Москва'},           # Cyrillic
        ]
        
        input_file = self.create_test_srt_file(temp_dirs, 'encoding_test.srt', segments)
        output_file = temp_dirs['output'] / 'encoding_test_de.srt'
        
        # Parse and translate
        original_segments = srt_translator.parse_srt(str(input_file))
        
        # Mock language detection
        for segment in original_segments:
            segment.detected_language = "en"  # Simplify for this test
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="1: English\n2: English\n3: Hebrew\n4: Russian"))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        translated_segments = srt_translator.translate_srt(
            str(input_file),
            target_language="de",
            preserve_original_when_matching=True
        )
        
        # Save and reparse
        srt_translator.save_translated_srt(translated_segments, str(output_file))
        
        # Verify file can be read with UTF-8 encoding
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) > 0, "File content is empty"
        except UnicodeDecodeError:
            pytest.fail("File encoding is not properly preserved - UTF-8 decode failed")
    
    @pytest.mark.segment_reassembly
    def test_segment_boundary_validation(self, srt_translator, mock_translator, temp_dirs):
        """Test the segment boundary validation mechanism."""
        # Create normal segments
        segments = [
            {'start': '00:00:00,000', 'end': '00:00:03,000', 'text': 'Hello world'},
            {'start': '00:00:03,000', 'end': '00:00:06,000', 'text': 'This is a test'},
        ]
        
        input_file = self.create_test_srt_file(temp_dirs, 'boundary_test.srt', segments)
        original_segments = srt_translator.parse_srt(str(input_file))
        
        # Mock language detection
        for segment in original_segments:
            segment.detected_language = "en"
        
        # Test valid boundary preservation
        translated_segments = []
        for segment in original_segments:
            new_segment = SRTSegment(
                index=segment.index,
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=f"[TRANSLATED: {segment.text}]",
                detected_language=segment.detected_language
            )
            translated_segments.append(new_segment)
        
        # This should pass validation
        is_valid = srt_translator._validate_segment_boundaries(original_segments, translated_segments)
        assert is_valid, "Valid segment boundaries failed validation"
        
        # Test invalid boundary - modify timing
        invalid_segments = []
        for segment in original_segments:
            new_segment = SRTSegment(
                index=segment.index,
                start_time="00:00:00,999",  # Changed timing - should fail
                end_time=segment.end_time,
                text=f"[TRANSLATED: {segment.text}]",
                detected_language=segment.detected_language
            )
            invalid_segments.append(new_segment)
        
        # This should fail validation
        is_invalid = srt_translator._validate_segment_boundaries(original_segments, invalid_segments)
        assert not is_invalid, "Invalid segment boundaries passed validation"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'segment_reassembly'])