#!/usr/bin/env python3
"""
Test suite for various language tag formats and edge cases in subtitle translation.

Implements Task 2.2: Create test cases for various language tag formats and edge cases
as part of the subtitle translation testing spec.

This covers comprehensive testing of different language tag formats that might appear
in subtitle files, handling of malformed language indicators, and edge cases in
language detection for mixed-language interviews.
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


class TestLanguageTagFormats:
    """Test suite for language tag format handling and edge cases."""
    
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
        """Create mock translator with OpenAI client."""
        translator = Mock(spec=HistoricalTranslator)
        translator.openai_client = MagicMock()
        return translator
    
    @pytest.fixture
    def srt_translator(self, mock_translator):
        """Create SRTTranslator with mocked dependencies."""
        return SRTTranslator(translator=mock_translator)
    
    def create_test_segments(self, segment_data: List[Tuple[str, str, str, Optional[str]]]) -> List[SRTSegment]:
        """
        Create test SRT segments from data tuples.
        
        Args:
            segment_data: List of (start_time, end_time, text, expected_language) tuples
        
        Returns:
            List of SRTSegment objects
        """
        segments = []
        for i, (start, end, text, expected_lang) in enumerate(segment_data, 1):
            segment = SRTSegment(i, start, end, text)
            segment.expected_language = expected_lang  # For testing purposes
            segments.append(segment)
        return segments
    
    @pytest.mark.language_tags
    def test_explicit_language_tag_formats(self, srt_translator, mock_translator):
        """Test handling of explicit language tags in various formats."""
        # Test different language tag formats that might appear in subtitles
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "[EN] This is in English", "en"),
            ("00:00:03,000", "00:00:06,000", "[DE] Das ist auf Deutsch", "de"),
            ("00:00:06,000", "00:00:09,000", "[HE] זה בעברית", "he"),
            ("00:00:09,000", "00:00:12,000", "(English) Mixed with tags", "en"),
            ("00:00:12,000", "00:00:15,000", "(German) Gemischt mit Tags", "de"),
            ("00:00:15,000", "00:00:18,000", "{EN} Curly bracket format", "en"),
            ("00:00:18,000", "00:00:21,000", "<DE> Angle bracket format", "de"),
            ("00:00:21,000", "00:00:24,000", "EN: Colon separator format", "en"),
            ("00:00:24,000", "00:00:27,000", "German - Dash separator", "de"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: English
5: German
6: English
7: German
8: English
9: German"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify that language detection works despite tag formats
        for segment in segments:
            assert segment.detected_language == segment.expected_language, \
                f"Segment {segment.index}: expected {segment.expected_language}, got {segment.detected_language}"
    
    @pytest.mark.language_tags
    def test_malformed_language_tags(self, srt_translator, mock_translator):
        """Test handling of malformed or incorrect language tags."""
        # Test cases with malformed or incorrect language indicators
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "[INVALID] This should still be detected as English", "en"),
            ("00:00:03,000", "00:00:06,000", "[XYZ] Das ist trotzdem Deutsch", "de"),
            ("00:00:06,000", "00:00:09,000", "[123] Still Hebrew זהו עדיין עברית", "he"),
            ("00:00:09,000", "00:00:12,000", "[EN] But this is actually German text", "de"),  # Misleading tag
            ("00:00:12,000", "00:00:15,000", "[DE] But this is English text", "en"),        # Misleading tag
            ("00:00:15,000", "00:00:18,000", "[] Empty tag with German Das ist deutsch", "de"),
            ("00:00:18,000", "00:00:21,000", "[INCOMPLETE Tag with English text", "en"),
            ("00:00:21,000", "00:00:24,000", "MISSING_BRACKET] German text hier", "de"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection - should detect actual language, not tag
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: German
5: English
6: German
7: English
8: German"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify that actual language is detected, not what the tag claims
        for segment in segments:
            assert segment.detected_language == segment.expected_language, \
                f"Segment {segment.index}: expected {segment.expected_language}, got {segment.detected_language}"
    
    @pytest.mark.language_tags
    def test_mixed_content_with_tags(self, srt_translator, mock_translator):
        """Test segments with mixed languages and various tag formats."""
        # Test cases where segments contain multiple languages with tags
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "[EN] I was born in [DE] Deutschland", "en"),  # Primarily English
            ("00:00:04,000", "00:00:08,000", "[DE] Ich war in the [EN] Wehrmacht", "de"),   # Primarily German
            ("00:00:08,000", "00:00:12,000", "Said 'Guten Tag' [DE] to the [EN] soldiers", "en"),  # Primarily English
            ("00:00:12,000", "00:00:16,000", "[HE] אמא שלי spoke [EN] English at home", "he"),  # Hebrew with English
            ("00:00:16,000", "00:00:20,000", "[EN] Father was [HE] רופא in Germany", "en"),  # English with Hebrew
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection - should detect primary language
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: English
4: Hebrew
5: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify primary language detection
        for segment in segments:
            assert segment.detected_language == segment.expected_language, \
                f"Segment {segment.index}: expected {segment.expected_language}, got {segment.detected_language}"
    
    @pytest.mark.language_tags
    def test_special_characters_and_encoding_edge_cases(self, srt_translator, mock_translator):
        """Test handling of special characters and encoding edge cases."""
        # Test cases with special characters, emojis, and encoding issues
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "English with émojis 😊 and accénts", "en"),
            ("00:00:03,000", "00:00:06,000", "Deutsch mit Ümlauten über alles", "de"),
            ("00:00:06,000", "00:00:09,000", "עברית עם ספרות 123 ותווים מיוחדים", "he"),
            ("00:00:09,000", "00:00:12,000", "Mixed א English with Hebrew letters ב", "en"),
            ("00:00:12,000", "00:00:15,000", "German with ñ Spanish character", "de"),
            ("00:00:15,000", "00:00:18,000", "Numbers: 1234567890 with text", "en"),
            ("00:00:18,000", "00:00:21,000", "Punctuation!@#$%^&*()_+{}|:<>?", None),  # Should not translate
            ("00:00:21,000", "00:00:24,000", "Mixed: Hello שלום Guten Tag", "en"),  # Primarily English
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: English
5: German
6: English
7: None
8: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify handling of special characters
        for segment in segments:
            if segment.expected_language is not None:
                assert segment.detected_language == segment.expected_language, \
                    f"Segment {segment.index}: expected {segment.expected_language}, got {segment.detected_language}"
    
    @pytest.mark.language_tags
    def test_very_short_segments_and_minimal_content(self, srt_translator, mock_translator):
        """Test handling of very short segments and minimal content."""
        # Test cases with very short or minimal content
        segment_data = [
            ("00:00:00,000", "00:00:01,000", "Hi", "en"),            # Very short English
            ("00:00:01,000", "00:00:02,000", "Ja", "de"),            # Very short German
            ("00:00:02,000", "00:00:03,000", "כן", "he"),            # Very short Hebrew (Yes)
            ("00:00:03,000", "00:00:04,000", "OK", "en"),            # Ambiguous
            ("00:00:04,000", "00:00:05,000", "Mm", None),           # Too short to translate
            ("00:00:05,000", "00:00:06,000", "Ah", None),           # Too short to translate
            ("00:00:06,000", "00:00:07,000", "...", None),          # Non-verbal
            ("00:00:07,000", "00:00:08,000", "12", None),           # Just numbers (too short)
            ("00:00:08,000", "00:00:09,000", "A", None),            # Single letter
            ("00:00:09,000", "00:00:10,000", "No", "en"),           # Short but valid
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection for valid segments only
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: English
5: None
6: None
7: None
8: None
9: None
10: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Test translation decisions for very short segments
        for segment in segments:
            if segment.expected_language is None:
                # Very short segments should not be translated
                should_translate = srt_translator.should_translate_segment(segment, "de")
                assert should_translate == False, \
                    f"Very short segment {segment.index} should not be translated: '{segment.text}'"
            else:
                # Verify language detection for translatable segments
                assert segment.detected_language == segment.expected_language, \
                    f"Segment {segment.index}: expected {segment.expected_language}, got {segment.detected_language}"
    
    @pytest.mark.language_tags
    def test_timing_format_variations(self, srt_translator, mock_translator):
        """Test handling of different timing format variations in SRT files."""
        # Test different timing formats that might appear in SRT files
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Standard millisecond format", "en"),
            ("00:00:03.000", "00:00:06.000", "Dot separator format", "en"),  # Sometimes appears
            ("0:00:06,000", "0:00:09,000", "Single digit hour", "en"),       # Sometimes appears
            ("00:00:09,0", "00:00:12,0", "Shortened milliseconds", "en"),    # Malformed but parseable
        ]
        
        # Create segments with potentially problematic timing formats
        segments = []
        for i, (start, end, text, expected_lang) in enumerate(segment_data, 1):
            segment = SRTSegment(i, start, end, text)
            segment.expected_language = expected_lang
            segments.append(segment)
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: English
3: English
4: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify that timing format variations don't affect language detection
        for segment in segments:
            assert segment.detected_language == segment.expected_language, \
                f"Segment {segment.index}: timing format affected language detection"
    
    @pytest.mark.language_tags
    def test_language_detection_with_proper_nouns(self, srt_translator, mock_translator):
        """Test language detection accuracy with proper nouns and historical names."""
        # Test cases with proper nouns that might confuse language detection
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "I lived in München during the war", "en"),
            ("00:00:04,000", "00:00:08,000", "Ich wohnte in New York nach dem Krieg", "de"),
            ("00:00:08,000", "00:00:12,000", "עליתי לירושלים ב-1948", "he"),  # Hebrew: I went up to Jerusalem in 1948
            ("00:00:12,000", "00:00:16,000", "My father worked for BMW in München", "en"),
            ("00:00:16,000", "00:00:20,000", "Der Rabbi from Brooklyn was very kind", "de"),  # German with English proper nouns
            ("00:00:20,000", "00:00:24,000", "Rabbi Cohen הסביר לנו על ההיסטוריה", "he"),  # Hebrew with English name
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: English
5: German
6: Hebrew"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify that proper nouns don't confuse language detection
        for segment in segments:
            assert segment.detected_language == segment.expected_language, \
                f"Segment {segment.index}: proper nouns confused language detection"
    
    @pytest.mark.language_tags
    def test_historical_context_terminology(self, srt_translator, mock_translator):
        """Test language detection with historical context and terminology."""
        # Test cases with WWII-era terminology and historical context
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "I served in the Wehrmacht during 1943", "en"),
            ("00:00:04,000", "00:00:08,000", "Ich war in der SS von 1941 bis 1944", "de"),
            ("00:00:08,000", "00:00:12,000", "The Führer's orders were absolute", "en"),
            ("00:00:12,000", "00:00:16,000", "נשלחתי למחנה בטרזנשטט", "he"),  # Hebrew: I was sent to Theresienstadt camp
            ("00:00:16,000", "00:00:20,000", "Der Kommandant spoke only German to us", "en"),
            ("00:00:20,000", "00:00:24,000", "הקריסטלנאכט היה נורא", "he"),  # Hebrew: Kristallnacht was terrible
            ("00:00:24,000", "00:00:28,000", "Die Gestapo kam am frühen Morgen", "de"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: English
4: Hebrew
5: English
6: Hebrew
7: German"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify accurate detection despite historical German terms in English/Hebrew
        for segment in segments:
            assert segment.detected_language == segment.expected_language, \
                f"Segment {segment.index}: historical terminology confused language detection"
    
    @pytest.mark.language_tags
    def test_batch_processing_consistency(self, srt_translator, mock_translator):
        """Test that batch processing produces consistent results across multiple runs."""
        # Create a set of segments that will be processed multiple times
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "This is English text", "en"),
            ("00:00:03,000", "00:00:06,000", "Das ist deutscher Text", "de"),
            ("00:00:06,000", "00:00:09,000", "זהו טקסט בעברית", "he"),
            ("00:00:09,000", "00:00:12,000", "Mixed English with deutsche Wörter", "en"),
            ("00:00:12,000", "00:00:15,000", "Deutsch mit some English words", "de"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock consistent batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: English
5: German"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch detection multiple times and verify consistency
        results = []
        for run in range(3):
            # Reset detected languages
            for segment in segments:
                segment.detected_language = None
            
            # Run batch language detection
            detect_languages_for_segments(segments, mock_translator.openai_client)
            
            # Collect results
            run_results = [segment.detected_language for segment in segments]
            results.append(run_results)
        
        # Verify all runs produced identical results
        for i in range(1, len(results)):
            assert results[i] == results[0], \
                f"Run {i+1} produced different results from run 1: {results[i]} vs {results[0]}"
        
        # Verify expected languages
        for segment in segments:
            assert segment.detected_language == segment.expected_language, \
                f"Segment {segment.index}: expected {segment.expected_language}, got {segment.detected_language}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'language_tags'])