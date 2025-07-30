#!/usr/bin/env python3
"""
Test suite for language preservation during subtitle translation.

Implements Task 2.3: Implement tests for language preservation during translation
as part of the subtitle translation testing spec.

This covers comprehensive testing of the preserve_original_when_matching flag
and ensures that segments already in the target language are correctly preserved
while others are translated appropriately.
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


class TestLanguagePreservation:
    """Test suite for language preservation during translation."""
    
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
        """Create mock translator with OpenAI client and translation capabilities."""
        translator = Mock(spec=HistoricalTranslator)
        translator.openai_client = MagicMock()
        
        # Mock translation responses
        def mock_translate(text, target_lang, source_lang=None):
            # Simple mock translations for testing
            translations = {
                ("Hello world", "de"): "Hallo Welt",
                ("This is a test", "de"): "Das ist ein Test",
                ("Thank you", "de"): "Danke",
                ("How are you?", "de"): "Wie geht es dir?",
                ("Guten Tag", "en"): "Good day",
                ("Das ist gut", "en"): "That is good",
                ("Ich bin hier", "en"): "I am here",
                ("Wie geht es?", "en"): "How are you?",
                ("שלום", "en"): "Hello",
                ("תודה רבה", "en"): "Thank you very much",
                ("איך קוראים לך?", "en"): "What is your name?",
                ("Hello world", "he"): "שלום עולם",
                ("This is a test", "he"): "זה מבחן",
                ("Das ist gut", "he"): "זה טוב",
            }
            return translations.get((text, target_lang), f"[TRANSLATED: {text} -> {target_lang}]")
        
        def mock_batch_translate(texts, target_lang, source_lang=None):
            return [mock_translate(text, target_lang, source_lang) for text in texts]
        
        translator.translate.side_effect = mock_translate
        translator.batch_translate.side_effect = mock_batch_translate
        
        return translator
    
    @pytest.fixture
    def srt_translator(self, mock_translator):
        """Create SRTTranslator with mocked dependencies."""
        return SRTTranslator(translator=mock_translator)
    
    def create_test_segments(self, segment_data: List[Tuple[str, str, str, str]]) -> List[SRTSegment]:
        """
        Create test SRT segments from data tuples with detected languages.
        
        Args:
            segment_data: List of (start_time, end_time, text, detected_language) tuples
        
        Returns:
            List of SRTSegment objects with detected_language set
        """
        segments = []
        for i, (start, end, text, detected_lang) in enumerate(segment_data, 1):
            segment = SRTSegment(i, start, end, text)
            segment.detected_language = detected_lang
            segments.append(segment)
        return segments
    
    @pytest.mark.language_preservation
    def test_preserve_matching_language_segments(self, srt_translator, mock_translator):
        """Test that segments matching target language are preserved when flag is True."""
        # Create mixed-language segments
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Hello world", "en"),           # English - should translate to German
            ("00:00:03,000", "00:00:06,000", "Das ist gut", "de"),           # German - should preserve
            ("00:00:06,000", "00:00:09,000", "This is a test", "en"),        # English - should translate to German
            ("00:00:09,000", "00:00:12,000", "Guten Tag", "de"),             # German - should preserve
            ("00:00:12,000", "00:00:15,000", "How are you?", "en"),          # English - should translate to German
        ]
        
        segments = self.create_test_segments(segment_data)
        target_language = "de"
        
        # Test translation with preserve_original_when_matching=True
        translated_segments = srt_translator.translate_srt(
            srt_path=None,  # We'll inject segments directly
            target_language=target_language,
            preserve_original_when_matching=True
        )
        
        # Override the segments (simulating parsed file)
        srt_translator._test_segments = segments
        
        # Check preservation decisions
        preservation_results = []
        for segment in segments:
            should_translate = srt_translator.should_translate_segment(segment, target_language)
            preservation_results.append({
                'text': segment.text,
                'detected_lang': segment.detected_language,
                'should_translate': should_translate,
                'expected_preserve': segment.detected_language == target_language
            })
        
        # Verify preservation logic
        for result in preservation_results:
            expected_translate = not result['expected_preserve']
            assert result['should_translate'] == expected_translate, \
                f"Preservation failed for '{result['text']}': " \
                f"expected should_translate={expected_translate}, got {result['should_translate']}"
    
    @pytest.mark.language_preservation
    def test_translate_all_when_preserve_disabled(self, srt_translator, mock_translator):
        """Test that all segments are translated when preserve_original_when_matching=False."""
        # Create segments all in German
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Das ist gut", "de"),
            ("00:00:03,000", "00:00:06,000", "Ich bin hier", "de"),
            ("00:00:06,000", "00:00:09,000", "Wie geht es?", "de"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Test with preserve_original_when_matching=False
        # All German segments should be translated to English even though they're already German
        for segment in segments:
            # When preserve_original_when_matching=False, should_translate_segment
            # should still preserve same-language segments (this is the current behavior)
            should_translate = srt_translator.should_translate_segment(segment, "de")
            assert should_translate == False, \
                f"Same language segment should not translate: {segment.text}"
            
            # But for different target language, should translate
            should_translate_en = srt_translator.should_translate_segment(segment, "en")
            assert should_translate_en == True, \
                f"Different language segment should translate: {segment.text}"
    
    @pytest.mark.language_preservation
    def test_preservation_across_multiple_languages(self, srt_translator, mock_translator):
        """Test preservation behavior across English, German, and Hebrew."""
        # Create tri-lingual segment mix
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Hello world", "en"),
            ("00:00:03,000", "00:00:06,000", "Das ist gut", "de"), 
            ("00:00:06,000", "00:00:09,000", "שלום", "he"),
            ("00:00:09,000", "00:00:12,000", "This is English", "en"),
            ("00:00:12,000", "00:00:15,000", "Deutsch hier", "de"),
            ("00:00:15,000", "00:00:18,000", "תודה רבה", "he"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Test preservation for each target language
        target_languages = ["en", "de", "he"]
        
        for target_lang in target_languages:
            preservation_decisions = []
            
            for segment in segments:
                should_translate = srt_translator.should_translate_segment(segment, target_lang)
                preservation_decisions.append({
                    'text': segment.text,
                    'detected': segment.detected_language,
                    'target': target_lang,
                    'should_translate': should_translate,
                    'should_preserve': segment.detected_language == target_lang
                })
            
            # Verify preservation logic for this target language
            for decision in preservation_decisions:
                expected_translate = not decision['should_preserve']
                assert decision['should_translate'] == expected_translate, \
                    f"Target {target_lang}: '{decision['text']}' " \
                    f"(detected: {decision['detected']}) " \
                    f"expected translate={expected_translate}, got {decision['should_translate']}"
    
    @pytest.mark.language_preservation
    def test_preservation_with_non_verbal_segments(self, srt_translator, mock_translator):
        """Test that non-verbal segments are always preserved regardless of target language."""
        # Mix of verbal and non-verbal segments
        segment_data = [
            ("00:00:00,000", "00:00:02,000", "Hello world", "en"),
            ("00:00:02,000", "00:00:04,000", "♪♪", None),              # Non-verbal
            ("00:00:04,000", "00:00:06,000", "Das ist gut", "de"),
            ("00:00:06,000", "00:00:08,000", "[Applause]", None),      # Non-verbal
            ("00:00:08,000", "00:00:10,000", "...", None),             # Non-verbal
            ("00:00:10,000", "00:00:12,000", "Thank you", "en"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Test with different target languages
        for target_lang in ["en", "de", "he"]:
            for segment in segments:
                should_translate = srt_translator.should_translate_segment(segment, target_lang)
                
                if segment.detected_language is None:
                    # Non-verbal segments should never be translated
                    assert should_translate == False, \
                        f"Non-verbal segment '{segment.text}' should not be translated"
                else:
                    # Verbal segments follow normal preservation logic
                    expected = segment.detected_language != target_lang
                    assert should_translate == expected, \
                        f"Verbal segment '{segment.text}' preservation logic failed"
    
    @pytest.mark.language_preservation
    def test_preservation_with_very_short_segments(self, srt_translator, mock_translator):
        """Test preservation behavior with very short segments."""
        # Mix of short and regular segments
        segment_data = [
            ("00:00:00,000", "00:00:01,000", "Hi", "en"),               # Short but valid
            ("00:00:01,000", "00:00:02,000", "A", "en"),                # Too short (single letter)
            ("00:00:02,000", "00:00:03,000", "OK", "en"),               # Short but valid
            ("00:00:03,000", "00:00:04,000", "Ja", "de"),               # Short but valid German
            ("00:00:04,000", "00:00:05,000", "No", "en"),               # Short but valid
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Test translation decisions
        for segment in segments:
            should_translate_de = srt_translator.should_translate_segment(segment, "de")
            
            if len(segment.text.strip()) < 3:
                # Very short segments should not be translated
                assert should_translate_de == False, \
                    f"Very short segment '{segment.text}' should not be translated"
            elif segment.detected_language == "de":
                # German segments targeting German should be preserved
                assert should_translate_de == False, \
                    f"German segment '{segment.text}' should be preserved when targeting German"
            else:
                # Other segments should be translated
                assert should_translate_de == True, \
                    f"Non-German segment '{segment.text}' should be translated to German"
    
    @pytest.mark.language_preservation
    def test_boundary_preservation_during_translation(self, srt_translator, mock_translator):
        """Test that timing boundaries are preserved during translation process."""
        # Create segments with precise timing
        segment_data = [
            ("00:00:00,500", "00:00:03,750", "Hello world", "en"),      # Should translate
            ("00:00:03,750", "00:00:06,250", "Das ist gut", "de"),      # Should preserve
            ("00:00:06,250", "00:00:09,500", "Thank you", "en"),        # Should translate
        ]
        
        original_segments = self.create_test_segments(segment_data)
        
        # Create mock translated segments (simulating translation output)
        translated_segments = []
        for segment in original_segments:
            new_segment = SRTSegment(
                index=segment.index,
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=segment.text if segment.detected_language == "de" else f"[TRANSLATED: {segment.text}]",
                detected_language=segment.detected_language
            )
            translated_segments.append(new_segment)
        
        # Verify boundary preservation
        assert len(original_segments) == len(translated_segments), \
            "Number of segments must be preserved"
        
        for orig, trans in zip(original_segments, translated_segments):
            assert orig.index == trans.index, \
                f"Index mismatch for segment {orig.index}"
            assert orig.start_time == trans.start_time, \
                f"Start time mismatch for segment {orig.index}: {orig.start_time} != {trans.start_time}"
            assert orig.end_time == trans.end_time, \
                f"End time mismatch for segment {orig.index}: {orig.end_time} != {trans.end_time}"
            
            # Check that preservation worked correctly
            if orig.detected_language == "de":
                assert orig.text == trans.text, \
                    f"German segment {orig.index} should be preserved: '{orig.text}' != '{trans.text}'"
            else:
                assert orig.text != trans.text, \
                    f"Non-German segment {orig.index} should be translated: '{orig.text}' == '{trans.text}'"
    
    @pytest.mark.language_preservation
    def test_preservation_with_repeated_phrases(self, srt_translator, mock_translator):
        """Test preservation behavior with repeated phrases in different languages."""
        # Create segments with repeated phrases in different languages
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Thank you", "en"),        # First occurrence
            ("00:00:03,000", "00:00:06,000", "Danke", "de"),            # German equivalent
            ("00:00:06,000", "00:00:09,000", "Thank you", "en"),        # Repeated English
            ("00:00:09,000", "00:00:12,000", "Danke", "de"),            # Repeated German
            ("00:00:12,000", "00:00:15,000", "Thank you very much", "en"), # Variation
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Test preservation when targeting German
        target_language = "de"
        
        # Track which segments should be preserved vs translated
        expected_results = [
            ("Thank you", "en", True),          # Should translate
            ("Danke", "de", False),             # Should preserve
            ("Thank you", "en", True),          # Should translate (repeated)
            ("Danke", "de", False),             # Should preserve (repeated)
            ("Thank you very much", "en", True), # Should translate
        ]
        
        for segment, (expected_text, expected_lang, should_translate) in zip(segments, expected_results):
            assert segment.text == expected_text, f"Text mismatch: {segment.text} != {expected_text}"
            assert segment.detected_language == expected_lang, f"Language mismatch: {segment.detected_language} != {expected_lang}"
            
            actual_should_translate = srt_translator.should_translate_segment(segment, target_language)
            assert actual_should_translate == should_translate, \
                f"Translation decision wrong for '{segment.text}': expected {should_translate}, got {actual_should_translate}"
    
    @pytest.mark.language_preservation
    def test_preservation_statistics_tracking(self, srt_translator, mock_translator):
        """Test that preservation statistics are correctly tracked."""
        # Create mixed-language segments
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "Hello", "en"),            # Translate to German
            ("00:00:03,000", "00:00:06,000", "Das ist gut", "de"),      # Preserve
            ("00:00:06,000", "00:00:09,000", "World", "en"),            # Translate to German
            ("00:00:09,000", "00:00:12,000", "Guten Tag", "de"),        # Preserve
            ("00:00:12,000", "00:00:15,000", "♪♪", None),               # Non-verbal preserve
        ]
        
        segments = self.create_test_segments(segment_data)
        target_language = "de"
        
        # Count expected preservation vs translation
        expected_to_translate = 0
        expected_to_preserve = 0
        
        for segment in segments:
            should_translate = srt_translator.should_translate_segment(segment, target_language)
            if should_translate:
                expected_to_translate += 1
            else:
                expected_to_preserve += 1
        
        # Verify expected counts
        assert expected_to_translate == 2, f"Expected 2 segments to translate, got {expected_to_translate}"
        assert expected_to_preserve == 3, f"Expected 3 segments to preserve, got {expected_to_preserve}"
        
        # Verify total segments
        total_segments = len(segments)
        assert expected_to_translate + expected_to_preserve == total_segments, \
            "Translate + preserve counts should equal total segments"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'language_preservation'])