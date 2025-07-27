#!/usr/bin/env python3
"""
Utility functions and helpers for subtitle testing.
Provides common functionality for parsing, validation, and comparison.
"""

import re
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
import difflib


@dataclass
class SubtitleSegment:
    """Generic subtitle segment for testing."""
    index: int
    start_time: str
    end_time: str
    text: str
    format: str = 'srt'  # srt, vtt, ass


class SubtitleValidator:
    """Validates subtitle files and segments."""
    
    # Timing patterns for different formats
    SRT_TIME_PATTERN = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})')
    VTT_TIME_PATTERN = re.compile(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})')
    
    @staticmethod
    def validate_srt_timing(timing: str) -> bool:
        """Validate SRT timing format."""
        match = SubtitleValidator.SRT_TIME_PATTERN.match(timing)
        if not match:
            return False
        
        hours, minutes, seconds, millis = map(int, match.groups())
        return (0 <= hours <= 99 and 
                0 <= minutes <= 59 and 
                0 <= seconds <= 59 and 
                0 <= millis <= 999)
    
    @staticmethod
    def validate_vtt_timing(timing: str) -> bool:
        """Validate WebVTT timing format."""
        match = SubtitleValidator.VTT_TIME_PATTERN.match(timing)
        if not match:
            return False
        
        hours, minutes, seconds, millis = map(int, match.groups())
        return (0 <= hours <= 99 and 
                0 <= minutes <= 59 and 
                0 <= seconds <= 59 and 
                0 <= millis <= 999)
    
    @staticmethod
    def validate_segment_boundaries(segments: List[SubtitleSegment]) -> List[str]:
        """Validate that segment boundaries don't overlap."""
        errors = []
        
        for i in range(len(segments) - 1):
            current = segments[i]
            next_seg = segments[i + 1]
            
            # Convert to milliseconds for comparison
            current_end = SubtitleValidator.time_to_ms(current.end_time, current.format)
            next_start = SubtitleValidator.time_to_ms(next_seg.start_time, next_seg.format)
            
            if current_end > next_start:
                errors.append(
                    f"Overlap between segment {current.index} and {next_seg.index}: "
                    f"{current.end_time} > {next_seg.start_time}"
                )
        
        return errors
    
    @staticmethod
    def time_to_ms(time_str: str, format: str = 'srt') -> int:
        """Convert time string to milliseconds."""
        if format == 'srt':
            pattern = SubtitleValidator.SRT_TIME_PATTERN
            sep = ','
        else:  # vtt
            pattern = SubtitleValidator.VTT_TIME_PATTERN
            sep = '.'
        
        match = pattern.match(time_str)
        if not match:
            raise ValueError(f"Invalid time format: {time_str}")
        
        h, m, s, ms = map(int, match.groups())
        return (h * 3600000) + (m * 60000) + (s * 1000) + ms
    
    @staticmethod
    def ms_to_time(ms: int, format: str = 'srt') -> str:
        """Convert milliseconds to time string."""
        hours = ms // 3600000
        ms %= 3600000
        minutes = ms // 60000
        ms %= 60000
        seconds = ms // 1000
        millis = ms % 1000
        
        if format == 'srt':
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
        else:  # vtt
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


class SubtitleComparator:
    """Compare subtitle files and segments."""
    
    @staticmethod
    def compare_segments(seg1: SubtitleSegment, seg2: SubtitleSegment, 
                        ignore_text: bool = False) -> Dict[str, bool]:
        """Compare two segments and return differences."""
        comparison = {
            'index_match': seg1.index == seg2.index,
            'start_match': seg1.start_time == seg2.start_time,
            'end_match': seg1.end_time == seg2.end_time,
            'text_match': seg1.text == seg2.text if not ignore_text else True,
            'timing_match': seg1.start_time == seg2.start_time and seg1.end_time == seg2.end_time
        }
        return comparison
    
    @staticmethod
    def compare_timing_precision(segments1: List[SubtitleSegment], 
                                segments2: List[SubtitleSegment]) -> List[Tuple[int, int]]:
        """Compare timing precision between two sets of segments.
        Returns list of (index, millisecond_difference) tuples."""
        differences = []
        
        for s1, s2 in zip(segments1, segments2):
            if s1.index != s2.index:
                continue
            
            start_diff = abs(
                SubtitleValidator.time_to_ms(s1.start_time, s1.format) -
                SubtitleValidator.time_to_ms(s2.start_time, s2.format)
            )
            end_diff = abs(
                SubtitleValidator.time_to_ms(s1.end_time, s1.format) -
                SubtitleValidator.time_to_ms(s2.end_time, s2.format)
            )
            
            max_diff = max(start_diff, end_diff)
            if max_diff > 0:
                differences.append((s1.index, max_diff))
        
        return differences
    
    @staticmethod
    def generate_diff_report(original: List[SubtitleSegment], 
                           translated: List[SubtitleSegment]) -> str:
        """Generate a detailed diff report between original and translated."""
        report = []
        report.append("=== Subtitle Translation Diff Report ===\n")
        
        # Check segment count
        if len(original) != len(translated):
            report.append(f"⚠️  Segment count mismatch: {len(original)} → {len(translated)}\n")
            return '\n'.join(report)
        
        # Compare each segment
        timing_preserved = True
        text_changes = []
        
        for orig, trans in zip(original, translated):
            comp = SubtitleComparator.compare_segments(orig, trans)
            
            if not comp['timing_match']:
                timing_preserved = False
                report.append(f"❌ Timing changed in segment {orig.index}:")
                report.append(f"   Original: {orig.start_time} --> {orig.end_time}")
                report.append(f"   Translated: {trans.start_time} --> {trans.end_time}\n")
            
            if not comp['text_match']:
                text_changes.append((orig.index, orig.text, trans.text))
        
        if timing_preserved:
            report.append("✅ All timings preserved correctly\n")
        
        # Report text changes
        if text_changes:
            report.append(f"📝 Text changes in {len(text_changes)} segments:")
            for idx, orig_text, trans_text in text_changes[:5]:  # Show first 5
                report.append(f"\n   Segment {idx}:")
                report.append(f"   Original:   {orig_text[:50]}...")
                report.append(f"   Translated: {trans_text[:50]}...")
        
        return '\n'.join(report)


class LanguageDetectionHelper:
    """Helper for testing language detection."""
    
    # Common test phrases by language
    TEST_PHRASES = {
        'de': [
            "Ich bin in Deutschland geboren",
            "Das war sehr schwierig",
            "In die Wehrmacht gekommen?",
            "Mein Vater war Offizier",
            "Wir mussten nach Amerika gehen",
        ],
        'en': [
            "I was born in Germany",
            "That was very difficult",
            "My father was an officer",
            "We had to go to America",
            "Thank you very much",
        ],
        'he': [
            "מה שלומך",
            "תודה רבה",
            "שלום עליכם",
            "ברוך הבא",
            "להתראות",
        ],
        'mixed': [
            "Ich war I was siebzehn seventeen",
            "Das ist the best solution",
            "In die Wehrmacht, yes?",
            "Danke, thank you",
        ]
    }
    
    @staticmethod
    def create_test_segments(language: str, count: int = 5) -> List[SubtitleSegment]:
        """Create test segments in specified language."""
        phrases = LanguageDetectionHelper.TEST_PHRASES.get(language, [])
        segments = []
        
        for i in range(min(count, len(phrases))):
            segments.append(SubtitleSegment(
                index=i + 1,
                start_time=f"00:00:{i*3:02d},000",
                end_time=f"00:00:{(i+1)*3:02d},000",
                text=phrases[i]
            ))
        
        return segments
    
    @staticmethod
    def analyze_language_distribution(segments: List[SubtitleSegment], 
                                    detector_func) -> Dict[str, int]:
        """Analyze language distribution in segments using provided detector."""
        distribution = {'de': 0, 'en': 0, 'he': 0, 'unknown': 0}
        
        for segment in segments:
            lang = detector_func(segment)
            if lang in distribution:
                distribution[lang] += 1
            else:
                distribution['unknown'] += 1
        
        return distribution


class MockTranslationHelper:
    """Helper for creating mock translations."""
    
    # Simple translation mappings for testing
    TRANSLATIONS = {
        ('en', 'de'): {
            "Hello": "Hallo",
            "Thank you": "Danke",
            "Good morning": "Guten Morgen",
            "I was born": "Ich wurde geboren",
            "Yes": "Ja",
            "No": "Nein",
        },
        ('de', 'en'): {
            "Hallo": "Hello",
            "Danke": "Thank you",
            "Guten Morgen": "Good morning",
            "Ich wurde geboren": "I was born",
            "Ja": "Yes",
            "Nein": "No",
        }
    }
    
    @staticmethod
    def mock_translate(text: str, source_lang: str, target_lang: str) -> str:
        """Provide mock translation for testing."""
        translations = MockTranslationHelper.TRANSLATIONS.get((source_lang, target_lang), {})
        
        # Try exact match first
        if text in translations:
            return translations[text]
        
        # Try case-insensitive match
        for orig, trans in translations.items():
            if orig.lower() == text.lower():
                return trans
        
        # Default: return marked translation
        return f"[{target_lang.upper()}] {text}"
    
    @staticmethod
    def create_mock_translator(target_responses: Dict[str, str] = None):
        """Create a mock translator with predefined responses."""
        responses = target_responses or {}
        
        def translate_func(text, target_lang, source_lang=None):
            if text in responses:
                return responses[text]
            return MockTranslationHelper.mock_translate(
                text, source_lang or 'auto', target_lang
            )
        
        return translate_func


def assert_timing_preserved(original_segments: List, translated_segments: List):
    """Assert that all timings are preserved exactly."""
    assert len(original_segments) == len(translated_segments), \
        f"Segment count changed: {len(original_segments)} → {len(translated_segments)}"
    
    for orig, trans in zip(original_segments, translated_segments):
        assert orig.start_time == trans.start_time, \
            f"Start time changed in segment {orig.index}: {orig.start_time} → {trans.start_time}"
        assert orig.end_time == trans.end_time, \
            f"End time changed in segment {orig.index}: {orig.end_time} → {trans.end_time}"
        assert orig.index == trans.index, \
            f"Index changed: {orig.index} → {trans.index}"


def assert_language_detection_accurate(segment_text: str, expected_lang: str, 
                                     detected_lang: str):
    """Assert language detection is accurate."""
    assert detected_lang == expected_lang, \
        f"Language detection failed for '{segment_text[:30]}...': " \
        f"expected {expected_lang}, got {detected_lang}"


def create_mixed_language_test_file(output_path: Path, segments_per_language: int = 5):
    """Create a test file with mixed German/English content."""
    segments = []
    index = 1
    
    # Alternate between German and English
    for i in range(segments_per_language):
        # German segment
        segments.append(f"{index}\n")
        segments.append(f"00:00:{index*3-3:02d},000 --> 00:00:{index*3:02d},000\n")
        segments.append(f"{LanguageDetectionHelper.TEST_PHRASES['de'][i % 5]}\n\n")
        index += 1
        
        # English segment
        segments.append(f"{index}\n")
        segments.append(f"00:00:{index*3-3:02d},000 --> 00:00:{index*3:02d},000\n")
        segments.append(f"{LanguageDetectionHelper.TEST_PHRASES['en'][i % 5]}\n\n")
        index += 1
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(segments)
    
    return output_path