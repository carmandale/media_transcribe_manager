#!/usr/bin/env python3
"""
Test suite for mixed-language segment detection and preservation.

Implements Task 2.1: Write tests for identifying mixed-language segments 
(e.g., [EN] text [ES] texto) as part of the subtitle translation testing spec.

This covers comprehensive testing of the language detection and preservation
logic for mixed-language interviews where speakers switch between languages
within segments or across segments.
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator, SRTSegment
from scribe.translate import HistoricalTranslator
from scribe.batch_language_detection import detect_languages_for_segments


class TestMixedLanguageDetection:
    """Test suite for mixed-language segment detection and identification."""
    
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
    
    def create_test_segments(self, segment_data: List[Tuple[str, str, str, str]]) -> List[SRTSegment]:
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
    
    @pytest.mark.mixed_language
    def test_single_language_segments(self, srt_translator, mock_translator):
        """Test detection of segments containing only one language."""
        # Create test segments with single languages
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Das ist ein deutscher Satz.", "de"),
            ("00:00:03,000", "00:00:06,000", "This is an English sentence.", "en"),
            ("00:00:06,000", "00:00:09,000", "זהו משפט בעברית.", "he"),
            ("00:00:09,000", "00:00:12,000", "Noch ein deutscher Satz hier.", "de"),
            ("00:00:12,000", "00:00:15,000", "Another English sentence here.", "en"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: Hebrew
4: German
5: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify each segment was assigned correct language
        for segment in segments:
            assert segment.detected_language == segment.expected_language, \
                f"Segment {segment.index}: expected {segment.expected_language}, got {segment.detected_language}"
    
    @pytest.mark.mixed_language
    def test_mixed_language_within_single_segment(self, srt_translator, mock_translator):
        """Test detection when multiple languages appear within a single segment."""
        # Test segments with multiple languages in one segment
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "Ich war in the Wehrmacht gekommen.", "de"),  # German with English phrase
            ("00:00:04,000", "00:00:08,000", "We called it der Führer back then.", "en"),  # English with German phrase
            ("00:00:08,000", "00:00:12,000", "Es war very difficult for us.", "de"),      # German with English words
            ("00:00:12,000", "00:00:16,000", "The soldiers said 'Guten Tag' to us.", "en"),  # English with German greeting
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection - should detect primary language
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: German
4: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify primary language detection
        expected_languages = ["de", "en", "de", "en"]
        for i, segment in enumerate(segments):
            assert segment.detected_language == expected_languages[i], \
                f"Segment {segment.index}: expected {expected_languages[i]}, got {segment.detected_language}"
    
    @pytest.mark.mixed_language
    def test_language_switching_across_segments(self, srt_translator, mock_translator):
        """Test detection when speakers switch languages between segments."""
        # Simulate interview where speaker switches languages frequently
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Ich bin in Deutschland geboren.", "de"),
            ("00:00:03,000", "00:00:06,000", "But then we moved to America.", "en"),
            ("00:00:06,000", "00:00:09,000", "Meine Familie war sehr arm.", "de"),
            ("00:00:09,000", "00:00:12,000", "We had to work very hard.", "en"),
            ("00:00:12,000", "00:00:15,000", "Der Krieg hat alles verändert.", "de"),
            ("00:00:15,000", "00:00:18,000", "The war changed everything.", "en"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: German
4: English
5: German
6: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify language switching detection
        expected_pattern = ["de", "en", "de", "en", "de", "en"]
        for i, segment in enumerate(segments):
            assert segment.detected_language == expected_pattern[i], \
                f"Segment {segment.index}: expected {expected_pattern[i]}, got {segment.detected_language}"
    
    @pytest.mark.mixed_language
    def test_translation_decision_for_mixed_segments(self, srt_translator, mock_translator):
        """Test should_translate_segment decisions for mixed-language content."""
        # Test segments with various language combinations
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Das ist deutsch.", "de"),           # German
            ("00:00:03,000", "00:00:06,000", "This is English.", "en"),          # English  
            ("00:00:06,000", "00:00:09,000", "זה בעברית.", "he"),                # Hebrew
            ("00:00:09,000", "00:00:12,000", "Mixed German and English.", "en"),  # Mixed but primary English
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Set detected languages
        for i, segment in enumerate(segments):
            segment.detected_language = segment.expected_language
        
        # Test translation decisions for German target
        target_language = "de"
        translation_decisions = []
        for segment in segments:
            should_translate = srt_translator.should_translate_segment(segment, target_language)
            translation_decisions.append(should_translate)
        
        # Expected: [False, True, True, True] - preserve German, translate others
        expected_decisions = [False, True, True, True]
        assert translation_decisions == expected_decisions, \
            f"Translation decisions don't match. Expected {expected_decisions}, got {translation_decisions}"
    
    @pytest.mark.mixed_language
    def test_edge_cases_in_mixed_language_detection(self, srt_translator, mock_translator):
        """Test edge cases in mixed-language segment detection."""
        # Edge cases that should be handled correctly
        segment_data = [
            ("00:00:00,000", "00:00:02,000", "Ja.", "de"),                    # Very short segment
            ("00:00:02,000", "00:00:04,000", "No.", "en"),                    # Very short English
            ("00:00:04,000", "00:00:06,000", "123 Hauptstraße.", "de"),       # Numbers with German
            ("00:00:06,000", "00:00:08,000", "Street 123.", "en"),            # Numbers with English
            ("00:00:08,000", "00:00:10,000", "[PAUSE]", None),               # Non-verbal sound
            ("00:00:10,000", "00:00:12,000", "(coughing)", None),            # Non-verbal action
            ("00:00:12,000", "00:00:14,000", "Mm-hmm.", None),               # Minimal response
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection (skipping non-verbal segments)
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: German
4: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify edge case handling
        for i, segment in enumerate(segments):
            if segment.expected_language is None:
                # Non-verbal segments should not be translated
                # The batch detection doesn't set language for these, so they remain None
                should_translate = srt_translator.should_translate_segment(segment, "en")
                assert should_translate == False, \
                    f"Non-verbal segment {segment.index} should not be translated"
            else:
                # Language detection should work for valid segments (first 4 only)
                if i < 4:  # Only first 4 segments have valid languages
                    assert segment.detected_language == segment.expected_language, \
                        f"Segment {segment.index}: expected {segment.expected_language}, got {segment.detected_language}"
    
    @pytest.mark.mixed_language
    def test_preservation_logic_with_mixed_languages(self, srt_translator, mock_translator):
        """Test preservation logic maintains correct segments in mixed-language scenarios."""
        # Create mixed-language interview scenario
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "Ich war damals zwanzig Jahre alt.", "de"),
            ("00:00:04,000", "00:00:08,000", "I was twenty years old then.", "en"),      # Same meaning, different language
            ("00:00:08,000", "00:00:12,000", "Der Krieg war schrecklich.", "de"),
            ("00:00:12,000", "00:00:16,000", "The war was terrible.", "en"),            # Same meaning, different language
            ("00:00:16,000", "00:00:20,000", "Wir hatten nicht genug zu essen.", "de"),
            ("00:00:20,000", "00:00:24,000", "We didn't have enough to eat.", "en"),    # Same meaning, different language
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Set detected languages
        for segment in segments:
            segment.detected_language = segment.expected_language
        
        # Test preservation for German target (should preserve German, translate English)
        german_decisions = []
        for segment in segments:
            should_translate = srt_translator.should_translate_segment(segment, "de")
            german_decisions.append(should_translate)
        
        # Expected: [False, True, False, True, False, True] - preserve German, translate English
        expected_german = [False, True, False, True, False, True]
        assert german_decisions == expected_german, \
            f"German preservation failed. Expected {expected_german}, got {german_decisions}"
        
        # Test preservation for English target (should preserve English, translate German)
        english_decisions = []
        for segment in segments:
            should_translate = srt_translator.should_translate_segment(segment, "en")
            english_decisions.append(should_translate)
        
        # Expected: [True, False, True, False, True, False] - translate German, preserve English
        expected_english = [True, False, True, False, True, False]
        assert english_decisions == expected_english, \
            f"English preservation failed. Expected {expected_english}, got {english_decisions}"
    
    @pytest.mark.mixed_language
    def test_batch_language_detection_api_calls(self, srt_translator, mock_translator):
        """Test that batch language detection makes appropriate API calls."""
        # Create segments that will trigger batch detection
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Dies ist der erste Satz.", "de"),
            ("00:00:03,000", "00:00:06,000", "This is the second sentence.", "en"),
            ("00:00:06,000", "00:00:09,000", "זהו המשפט השלישי.", "he"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: Hebrew"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client, batch_size=50)
        
        # Verify API was called correctly
        mock_translator.openai_client.chat.completions.create.assert_called_once()
        call_args = mock_translator.openai_client.chat.completions.create.call_args
        
        # Verify correct model and parameters
        assert call_args[1]['model'] == 'gpt-4o-mini'
        assert 'messages' in call_args[1]
        
        # Verify messages structure contains language detection instructions
        messages = call_args[1]['messages']
        assert len(messages) > 0, "No messages sent to OpenAI API"
        
        # Check that we have a user message with the expected language detection prompt
        user_message = next((msg for msg in messages if msg['role'] == 'user'), None)
        assert user_message is not None, "No user message found in API call"
        
        # Verify the user message contains language detection instructions
        content = user_message['content'].lower()
        assert 'language' in content, "Language detection not mentioned in prompt"
        assert 'english' in content or 'german' in content or 'hebrew' in content, "Target languages not specified"
    
    @pytest.mark.mixed_language
    def test_complex_multilingual_interview_scenario(self, srt_translator, mock_translator):
        """Test a realistic complex multilingual interview scenario."""
        # Simulate real historical interview with multiple language switches
        segment_data = [
            ("00:00:00,000", "00:00:05,000", "Mein Name ist Hans Mueller.", "de"),
            ("00:00:05,000", "00:00:10,000", "I was born in Hamburg in 1920.", "en"),
            ("00:00:10,000", "00:00:15,000", "Meine Familie war jüdisch.", "de"),
            ("00:00:15,000", "00:00:20,000", "We had to leave Germany.", "en"),
            ("00:00:20,000", "00:00:25,000", "אבא שלי היה רופא.", "he"),  # Hebrew: My father was a doctor
            ("00:00:25,000", "00:00:30,000", "But in America he could not practice.", "en"),
            ("00:00:30,000", "00:00:35,000", "Es war sehr schwer für uns.", "de"),
            ("00:00:35,000", "00:00:40,000", "The children learned English quickly.", "en"),
            ("00:00:40,000", "00:00:45,000", "אבל אמא תמיד דיברה עברית בבית.", "he"),  # Hebrew: But mother always spoke Hebrew at home
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock comprehensive language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: German
4: English
5: Hebrew
6: English
7: German
8: English
9: Hebrew"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify all segments were detected correctly
        expected_languages = ["de", "en", "de", "en", "he", "en", "de", "en", "he"]
        for i, segment in enumerate(segments):
            assert segment.detected_language == expected_languages[i], \
                f"Segment {segment.index}: expected {expected_languages[i]}, got {segment.detected_language}"
        
        # Test translation decisions for all three target languages
        for target_lang in ["de", "en", "he"]:
            translation_decisions = []
            for segment in segments:
                should_translate = srt_translator.should_translate_segment(segment, target_lang)
                translation_decisions.append(should_translate)
            
            # Verify only segments not in target language are marked for translation
            for i, should_translate in enumerate(translation_decisions):
                expected = (segments[i].detected_language != target_lang)
                assert should_translate == expected, \
                    f"Target {target_lang}, Segment {i+1}: expected {expected}, got {should_translate}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'mixed_language'])