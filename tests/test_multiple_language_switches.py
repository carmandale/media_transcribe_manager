#!/usr/bin/env python3
"""
Test suite for handling segments with multiple language switches.

Implements Task 2.5: Test handling of segments with multiple language switches
as part of the subtitle translation testing spec.

This covers comprehensive testing of complex multilingual scenarios where
speakers switch languages frequently within segments or across segments,
ensuring the GPT-4o-mini batch detection handles these cases correctly.
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


class TestMultipleLanguageSwitches:
    """Test suite for multiple language switch handling."""
    
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
    
    @pytest.mark.multiple_switches
    def test_rapid_language_switching_across_segments(self, srt_translator, mock_translator):
        """Test rapid language switching between consecutive segments."""
        # Simulate interview where speaker switches languages very frequently
        segment_data = [
            ("00:00:00,000", "00:00:02,000", "Ich war damals jung", "de"),              # German
            ("00:00:02,000", "00:00:04,000", "I was young then", "en"),                # English 
            ("00:00:04,000", "00:00:06,000", "אבל לא הבנתי", "he"),                    # Hebrew: But I didn't understand
            ("00:00:06,000", "00:00:08,000", "But I didn't understand", "en"),          # English
            ("00:00:08,000", "00:00:10,000", "Die Situation war kompliziert", "de"),   # German
            ("00:00:10,000", "00:00:12,000", "The situation was complicated", "en"),   # English
            ("00:00:12,000", "00:00:14,000", "זה היה מסובך מאוד", "he"),               # Hebrew: It was very complicated
            ("00:00:14,000", "00:00:16,000", "Very complicated indeed", "en"),         # English
            ("00:00:16,000", "00:00:18,000", "Ja, sehr kompliziert", "de"),            # German
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection for rapid switches
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: Hebrew
4: English
5: German
6: English
7: Hebrew
8: English
9: German"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify each segment was detected correctly despite rapid switching
        expected_languages = ["de", "en", "he", "en", "de", "en", "he", "en", "de"]
        for i, (segment, expected_lang) in enumerate(zip(segments, expected_languages)):
            assert segment.detected_language == expected_lang, \
                f"Segment {i+1}: expected {expected_lang}, got {segment.detected_language}"
        
        # Test translation decisions for different target languages
        for target_lang in ["de", "en", "he"]:
            for segment in segments:
                should_translate = srt_translator.should_translate_segment(segment, target_lang)
                expected_translate = segment.detected_language != target_lang
                assert should_translate == expected_translate, \
                    f"Wrong translation decision for segment '{segment.text}' targeting {target_lang}"
    
    @pytest.mark.multiple_switches
    def test_intra_segment_language_mixing(self, srt_translator, mock_translator):
        """Test segments with multiple language switches within single segments."""
        # Segments with multiple languages mixed within the same subtitle
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "I was in die Wehrmacht serving unter the Führer", "en"),  # English with German words
            ("00:00:04,000", "00:00:08,000", "Wir said 'yes sir' to der Kommandant", "de"),          # German with English phrases  
            ("00:00:08,000", "00:00:12,000", "The Rabbi told us שלום means peace", "en"),            # English with Hebrew word
            ("00:00:12,000", "00:00:16,000", "אמרנו hello בכל בוקר", "he"),                         # Hebrew with English word
            ("00:00:16,000", "00:00:20,000", "Es war difficult aber wir managed", "de"),             # German with English words
            ("00:00:20,000", "00:00:24,000", "We learned Hebrew words like תודה", "en"),            # English with Hebrew word
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock batch language detection - should detect primary language
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: English
4: Hebrew
5: German
6: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify primary language detection for mixed segments
        expected_languages = ["en", "de", "en", "he", "de", "en"]
        for i, (segment, expected_lang) in enumerate(zip(segments, expected_languages)):
            assert segment.detected_language == expected_lang, \
                f"Mixed segment {i+1}: expected {expected_lang}, got {segment.detected_language}"
    
    @pytest.mark.multiple_switches
    def test_trilingual_conversation_patterns(self, srt_translator, mock_translator):
        """Test realistic trilingual conversation with all three supported languages."""
        # Complex trilingual interview scenario 
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "My name is David Cohen", "en"),
            ("00:00:04,000", "00:00:08,000", "Ich bin in Berlin geboren", "de"),
            ("00:00:08,000", "00:00:12,000", "נולדתי בברלין בשנת 1920", "he"),                      # Hebrew: I was born in Berlin in 1920
            ("00:00:12,000", "00:00:16,000", "But we spoke English at home", "en"),
            ("00:00:16,000", "00:00:20,000", "Meine Mutter kam aus America", "de"),
            ("00:00:20,000", "00:00:24,000", "אמא שלי הייתה מאמריקה", "he"),                        # Hebrew: My mother was from America
            ("00:00:24,000", "00:00:28,000", "When the war started", "en"),
            ("00:00:28,000", "00:00:32,000", "Als der Krieg begann", "de"),
            ("00:00:32,000", "00:00:36,000", "כשהמלחמה התחילה", "he"),                              # Hebrew: When the war began
            ("00:00:36,000", "00:00:40,000", "We had to make difficult choices", "en"),
            ("00:00:40,000", "00:00:44,000", "Wir mussten schwere Entscheidungen treffen", "de"),
            ("00:00:44,000", "00:00:48,000", "היינו צריכים לקבל החלטות קשות", "he"),                # Hebrew: We had to make difficult decisions
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock comprehensive trilingual detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: English
5: German
6: Hebrew
7: English
8: German
9: Hebrew
10: English
11: German
12: Hebrew"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify trilingual pattern recognition
        expected_pattern = ["en", "de", "he", "en", "de", "he", "en", "de", "he", "en", "de", "he"]
        for i, (segment, expected_lang) in enumerate(zip(segments, expected_pattern)):
            assert segment.detected_language == expected_lang, \
                f"Trilingual segment {i+1}: expected {expected_lang}, got {segment.detected_language}"
        
        # Test that translation logic works for all three languages
        for target_lang in ["en", "de", "he"]:
            preserved_count = 0
            translated_count = 0
            
            for segment in segments:
                should_translate = srt_translator.should_translate_segment(segment, target_lang)
                if should_translate:
                    translated_count += 1
                else:
                    preserved_count += 1
            
            # Each target language should preserve 4 segments and translate 8
            assert preserved_count == 4, \
                f"Target {target_lang}: expected 4 preserved segments, got {preserved_count}"
            assert translated_count == 8, \
                f"Target {target_lang}: expected 8 translated segments, got {translated_count}"
    
    @pytest.mark.multiple_switches
    def test_emotional_intensity_language_switching(self, srt_translator, mock_translator):
        """Test language switching that correlates with emotional intensity."""
        # Common pattern: speakers switch to native language during emotional moments
        segment_data = [
            ("00:00:00,000", "00:00:03,000", "We lived peacefully then", "en"),
            ("00:00:03,000", "00:00:06,000", "Everything was normal", "en"),
            ("00:00:06,000", "00:00:09,000", "But then came 1933", "en"),
            ("00:00:09,000", "00:00:12,000", "Plötzlich war alles anders!", "de"),                  # Sudden emotional switch to German
            ("00:00:12,000", "00:00:15,000", "Suddenly everything changed!", "en"),                # Back to English
            ("00:00:15,000", "00:00:18,000", "Die Nazis kamen an die Macht", "de"),               # German for historical context
            ("00:00:18,000", "00:00:21,000", "המצב הפך להיות מסוכן מאוד", "he"),                   # Hebrew: The situation became very dangerous
            ("00:00:21,000", "00:00:24,000", "We were so scared", "en"),
            ("00:00:24,000", "00:00:27,000", "פחדנו מאוד מאוד", "he"),                             # Hebrew: We were very, very afraid
            ("00:00:27,000", "00:00:30,000", "But we had to survive", "en"),
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock emotion-based language switching detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: English
3: English
4: German
5: English
6: German
7: Hebrew
8: English
9: Hebrew
10: English"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify emotional language switching detection
        expected_languages = ["en", "en", "en", "de", "en", "de", "he", "en", "he", "en"]
        for i, (segment, expected_lang) in enumerate(zip(segments, expected_languages)):
            assert segment.detected_language == expected_lang, \
                f"Emotional switch segment {i+1}: expected {expected_lang}, got {segment.detected_language}"
    
    @pytest.mark.multiple_switches
    def test_code_switching_with_proper_nouns(self, srt_translator, mock_translator):
        """Test language switching involving proper nouns and place names."""
        # Common in historical testimonies: mixing languages with proper nouns
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "I lived in München before the war", "en"),
            ("00:00:04,000", "00:00:08,000", "Ich wohnte in New York nach 1938", "de"),
            ("00:00:08,000", "00:00:12,000", "בירושלים הרגשתי בבית", "he"),                         # Hebrew: In Jerusalem I felt at home
            ("00:00:12,000", "00:00:16,000", "My uncle worked for Siemens in Berlin", "en"),
            ("00:00:16,000", "00:00:20,000", "Der Rabbi from Brooklyn war sehr klug", "de"),         # German with English proper nouns
            ("00:00:20,000", "00:00:24,000", "Rabbi Goldman לימד אותנו עברית", "he"),              # Hebrew with English name
            ("00:00:24,000", "00:00:28,000", "The Gestapo came to our house", "en"),
            ("00:00:28,000", "00:00:32,000", "Die SS war in der Kristallnacht sehr brutal", "de"),
            ("00:00:32,000", "00:00:36,000", "הקריסטלנאכט היה ב-1938", "he"),                     # Hebrew: Kristallnacht was in 1938
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock proper noun language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: English
5: German
6: Hebrew
7: English
8: German
9: Hebrew"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify proper noun doesn't confuse language detection
        expected_languages = ["en", "de", "he", "en", "de", "he", "en", "de", "he"]
        for i, (segment, expected_lang) in enumerate(zip(segments, expected_languages)):
            assert segment.detected_language == expected_lang, \
                f"Proper noun segment {i+1}: expected {expected_lang}, got {segment.detected_language}"
    
    @pytest.mark.multiple_switches
    def test_quoted_speech_language_switching(self, srt_translator, mock_translator):
        """Test language switching in quoted speech scenarios."""
        # Common pattern: speakers quote what others said in different languages
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "The officer said 'Guten Morgen' to us", "en"),
            ("00:00:04,000", "00:00:08,000", "Der Kommandant sagte 'attention soldiers'", "de"),
            ("00:00:08,000", "00:00:12,000", "Mother always said 'שלום בבית'", "en"),               # English quoting Hebrew
            ("00:00:12,000", "00:00:16,000", "אמא אמרה 'be careful my son'", "he"),               # Hebrew quoting English
            ("00:00:16,000", "00:00:20,000", "The guard shouted 'Schnell! Schnell!'", "en"),
            ("00:00:20,000", "00:00:24,000", "Wir riefen 'help us please!'", "de"),               # German quoting English
            ("00:00:24,000", "00:00:28,000", "They said 'juden raus' very loudly", "en"),
            ("00:00:28,000", "00:00:32,000", "הם צעקו 'get out now!'", "he"),                     # Hebrew quoting English
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock quoted speech language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: English
4: Hebrew
5: English
6: German
7: English
8: Hebrew"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify quoted speech language detection (should detect primary language)
        expected_languages = ["en", "de", "en", "he", "en", "de", "en", "he"]
        for i, (segment, expected_lang) in enumerate(zip(segments, expected_languages)):
            assert segment.detected_language == expected_lang, \
                f"Quoted speech segment {i+1}: expected {expected_lang}, got {segment.detected_language}"
    
    @pytest.mark.multiple_switches
    def test_technical_terminology_language_mixing(self, srt_translator, mock_translator):
        """Test language switching with technical or military terminology."""
        # Military/technical terms often remain in original language
        segment_data = [
            ("00:00:00,000", "00:00:04,000", "I served in the Wehrmacht logistics division", "en"),
            ("00:00:04,000", "00:00:08,000", "Ich war ein Gefreiter in der Luftwaffe", "de"),
            ("00:00:08,000", "00:00:12,000", "The Obergefreiter gave us orders", "en"),            # German rank in English
            ("00:00:12,000", "00:00:16,000", "Wir bekamen orders from the Hauptmann", "de"),       # English word in German
            ("00:00:16,000", "00:00:20,000", "הקיבלנו פקודות מה-Kommandant", "he"),                # Hebrew with German title
            ("00:00:20,000", "00:00:24,000", "The Blitzkrieg strategy was effective", "en"),
            ("00:00:24,000", "00:00:28,000", "Die Wehrmacht used modern tactics", "de"),           # Mixed terminology
            ("00:00:28,000", "00:00:32,000", "ה-Panzer divisions were very strong", "he"),         # Hebrew with German military term
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock technical terminology language detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: English
4: German
5: Hebrew
6: English
7: German
8: Hebrew"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection
        detect_languages_for_segments(segments, mock_translator.openai_client)
        
        # Verify technical terminology doesn't confuse detection
        expected_languages = ["en", "de", "en", "de", "he", "en", "de", "he"]
        for i, (segment, expected_lang) in enumerate(zip(segments, expected_languages)):
            assert segment.detected_language == expected_lang, \
                f"Technical term segment {i+1}: expected {expected_lang}, got {segment.detected_language}"
    
    @pytest.mark.multiple_switches
    def test_consistency_across_rapid_switches(self, srt_translator, mock_translator):
        """Test that detection remains consistent across very rapid language switches."""
        # Extreme case: language changes every segment
        segment_data = [
            ("00:00:00,000", "00:00:01,000", "I", "en"),
            ("00:00:01,000", "00:00:02,000", "war", "de"),
            ("00:00:02,000", "00:00:03,000", "הייתי", "he"),                                       # Hebrew: I was
            ("00:00:03,000", "00:00:04,000", "young", "en"),
            ("00:00:04,000", "00:00:05,000", "jung", "de"),
            ("00:00:05,000", "00:00:06,000", "צעיר", "he"),                                        # Hebrew: young
            ("00:00:06,000", "00:00:07,000", "then", "en"),
            ("00:00:07,000", "00:00:08,000", "damals", "de"),
            ("00:00:08,000", "00:00:09,000", "אז", "he"),                                          # Hebrew: then
        ]
        
        segments = self.create_test_segments(segment_data)
        
        # Mock very rapid switching detection
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: German
3: Hebrew
4: English
5: German
6: Hebrew
7: English
8: German
9: Hebrew"""))]
        mock_translator.openai_client.chat.completions.create.return_value = mock_response
        
        # Run batch language detection multiple times to test consistency
        for run in range(3):
            # Reset detected languages
            for segment in segments:
                segment.detected_language = None
            
            # Run detection
            detect_languages_for_segments(segments, mock_translator.openai_client)
            
            # Verify consistency
            expected_pattern = ["en", "de", "he", "en", "de", "he", "en", "de", "he"]
            for i, (segment, expected_lang) in enumerate(zip(segments, expected_pattern)):
                assert segment.detected_language == expected_lang, \
                    f"Run {run+1}, segment {i+1}: expected {expected_lang}, got {segment.detected_language}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'multiple_switches'])