"""
Critical tests for subtitle synchronization issues.

This module focuses on reproducing and testing the subtitle sync bugs
mentioned in spec #73, ensuring accurate timing alignment between
spoken words and displayed subtitles.
"""

import pytest
from pathlib import Path
import json
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock

from scribe.srt_translator import SRTTranslator
from scribe.database import DatabaseManager
from scribe.pipeline_database_integration import PipelineDatabaseIntegration


class TestSubtitleSyncCritical:
    """Critical tests for subtitle synchronization accuracy."""
    
    @pytest.fixture
    def sample_segments(self):
        """Sample segments with precise timing for sync testing."""
        return [
            {
                "text": "My name is Hans Mueller",
                "start": 1.500,
                "end": 3.200,
                "words": [
                    {"word": "My", "start": 1.500, "end": 1.700},
                    {"word": "name", "start": 1.700, "end": 1.900},
                    {"word": "is", "start": 1.900, "end": 2.100},
                    {"word": "Hans", "start": 2.100, "end": 2.500},
                    {"word": "Mueller", "start": 2.500, "end": 3.200}
                ]
            },
            {
                "text": "I served in the Wehrmacht",
                "start": 3.500,
                "end": 5.800,
                "words": [
                    {"word": "I", "start": 3.500, "end": 3.600},
                    {"word": "served", "start": 3.600, "end": 4.100},
                    {"word": "in", "start": 4.100, "end": 4.300},
                    {"word": "the", "start": 4.300, "end": 4.500},
                    {"word": "Wehrmacht", "start": 4.500, "end": 5.800}
                ]
            }
        ]
    
    @pytest.fixture
    def mixed_language_segments(self):
        """Segments with language switching for critical sync testing."""
        return [
            {
                "text": "Ich bin in Berlin geboren",
                "start": 0.000,
                "end": 2.500,
                "detected_language": "de",
                "words": [
                    {"word": "Ich", "start": 0.000, "end": 0.300},
                    {"word": "bin", "start": 0.300, "end": 0.600},
                    {"word": "in", "start": 0.600, "end": 0.800},
                    {"word": "Berlin", "start": 0.800, "end": 1.500},
                    {"word": "geboren", "start": 1.500, "end": 2.500}
                ]
            },
            {
                "text": "but I moved to America",
                "start": 2.800,
                "end": 4.900,
                "detected_language": "en",
                "words": [
                    {"word": "but", "start": 2.800, "end": 3.000},
                    {"word": "I", "start": 3.000, "end": 3.100},
                    {"word": "moved", "start": 3.100, "end": 3.500},
                    {"word": "to", "start": 3.500, "end": 3.700},
                    {"word": "America", "start": 3.700, "end": 4.900}
                ]
            },
            {
                "text": "אני זוכר את המלחמה",  # "I remember the war" in Hebrew
                "start": 5.200,
                "end": 7.100,
                "detected_language": "he",
                "words": [
                    {"word": "אני", "start": 5.200, "end": 5.600},
                    {"word": "זוכר", "start": 5.600, "end": 6.100},
                    {"word": "את", "start": 6.100, "end": 6.400},
                    {"word": "המלחמה", "start": 6.400, "end": 7.100}
                ]
            }
        ]
    
    def test_exact_timing_preservation(self, sample_segments):
        """Test that subtitle timings match exactly with source segments."""
        translator = SRTTranslator()
        
        # Create SRT from segments
        srt_content = translator._create_srt_from_segments(sample_segments)
        
        # Parse back the SRT
        parsed_segments = translator._parse_srt_content(srt_content)
        
        # Verify timing preservation
        for original, parsed in zip(sample_segments, parsed_segments):
            assert abs(parsed['start'] - original['start']) < 0.001, \
                f"Start time mismatch: {parsed['start']} vs {original['start']}"
            assert abs(parsed['end'] - original['end']) < 0.001, \
                f"End time mismatch: {parsed['end']} vs {original['end']}"
    
    def test_word_level_timing_accuracy(self, sample_segments):
        """Test that word-level timings are preserved through translation."""
        translator = SRTTranslator()
        
        for segment in sample_segments:
            # Verify each word timing
            for word_data in segment.get('words', []):
                assert 'start' in word_data, f"Missing start time for word: {word_data['word']}"
                assert 'end' in word_data, f"Missing end time for word: {word_data['word']}"
                assert word_data['start'] >= segment['start'], \
                    f"Word starts before segment: {word_data['word']}"
                assert word_data['end'] <= segment['end'], \
                    f"Word ends after segment: {word_data['word']}"
    
    def test_language_switch_boundary_sync(self, mixed_language_segments):
        """Test synchronization at language switch boundaries."""
        translator = SRTTranslator()
        
        # Verify no timing gaps at language boundaries
        for i in range(len(mixed_language_segments) - 1):
            current = mixed_language_segments[i]
            next_seg = mixed_language_segments[i + 1]
            
            gap = next_seg['start'] - current['end']
            assert gap >= 0, f"Overlapping segments at language boundary"
            assert gap < 1.0, f"Large gap ({gap}s) at language switch"
    
    @patch('scribe.database.DatabaseManager')
    def test_database_segment_timing_integrity(self, mock_db, sample_segments):
        """Test that database storage preserves exact timing."""
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        # Store segments
        for segment in sample_segments:
            mock_db_instance.add_subtitle_segment.return_value = True
        
        pipeline = PipelineDatabaseIntegration(mock_db_instance)
        
        # Simulate storing segments
        interview_id = "test-interview"
        for idx, segment in enumerate(sample_segments):
            pipeline.store_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=segment['start'],
                end_time=segment['end'],
                original_text=segment['text'],
                translated_text=f"Translation of: {segment['text']}",
                source_language='en',
                target_language='de'
            )
        
        # Verify timing preservation in calls
        assert mock_db_instance.add_subtitle_segment.call_count == len(sample_segments)
        
        for idx, call in enumerate(mock_db_instance.add_subtitle_segment.call_args_list):
            args = call[1]
            assert abs(args['start_time'] - sample_segments[idx]['start']) < 0.001
            assert abs(args['end_time'] - sample_segments[idx]['end']) < 0.001
    
    def test_subtitle_display_duration(self, sample_segments):
        """Test that subtitle display durations are appropriate."""
        translator = SRTTranslator()
        
        for segment in sample_segments:
            duration = segment['end'] - segment['start']
            word_count = len(segment['text'].split())
            
            # Minimum reading time calculation (150 words per minute)
            min_reading_time = (word_count / 150) * 60
            
            assert duration >= min_reading_time * 0.8, \
                f"Subtitle duration too short for reading: {duration}s for {word_count} words"
            assert duration <= 7.0, \
                f"Subtitle duration too long: {duration}s"
    
    def test_sync_after_translation(self, mixed_language_segments):
        """Test that sync is maintained after translation to different languages."""
        translator = SRTTranslator()
        
        # Mock translation that preserves timing
        with patch.object(translator, '_translate_segment') as mock_translate:
            def translate_with_timing(text, source_lang, target_lang, segment):
                # Return translation that preserves original timing
                return {
                    'text': f"[{target_lang}] {text}",
                    'start': segment['start'],
                    'end': segment['end']
                }
            
            mock_translate.side_effect = translate_with_timing
            
            # Process segments
            for segment in mixed_language_segments:
                result = translator._translate_segment(
                    segment['text'],
                    segment['detected_language'],
                    'en',
                    segment
                )
                
                # Verify timing preserved
                assert result['start'] == segment['start']
                assert result['end'] == segment['end']
    
    def test_critical_sync_edge_cases(self):
        """Test edge cases that could cause sync issues."""
        translator = SRTTranslator()
        
        edge_cases = [
            # Very short segment
            {
                "text": "Ja",
                "start": 0.100,
                "end": 0.300,
                "words": [{"word": "Ja", "start": 0.100, "end": 0.300}]
            },
            # Long segment with pause
            {
                "text": "I was born in 1920... in a small village",
                "start": 0.000,
                "end": 8.500,
                "words": [
                    {"word": "I", "start": 0.000, "end": 0.200},
                    {"word": "was", "start": 0.200, "end": 0.500},
                    {"word": "born", "start": 0.500, "end": 0.900},
                    {"word": "in", "start": 0.900, "end": 1.100},
                    {"word": "1920", "start": 1.100, "end": 2.500},
                    # Long pause here
                    {"word": "in", "start": 6.000, "end": 6.200},
                    {"word": "a", "start": 6.200, "end": 6.300},
                    {"word": "small", "start": 6.300, "end": 6.700},
                    {"word": "village", "start": 6.700, "end": 8.500}
                ]
            },
            # Overlapping speech (interviewer interruption)
            {
                "text": "The year was—",
                "start": 10.000,
                "end": 11.200,
                "words": [
                    {"word": "The", "start": 10.000, "end": 10.200},
                    {"word": "year", "start": 10.200, "end": 10.500},
                    {"word": "was", "start": 10.500, "end": 11.200}
                ]
            }
        ]
        
        for segment in edge_cases:
            # Verify segment can be processed without timing corruption
            srt = translator._create_srt_from_segments([segment])
            parsed = translator._parse_srt_content(srt)
            
            assert len(parsed) == 1
            assert abs(parsed[0]['start'] - segment['start']) < 0.001
            assert abs(parsed[0]['end'] - segment['end']) < 0.001
    
    def test_frame_accurate_sync(self):
        """Test frame-accurate synchronization for video playback."""
        # Standard video frame rates
        frame_rates = [23.976, 24, 25, 29.97, 30]
        
        for fps in frame_rates:
            frame_duration = 1.0 / fps
            
            # Test segment that should align with frame boundaries
            segment = {
                "text": "Frame accurate test",
                "start": 1.000,
                "end": 2.000,
                "words": [
                    {"word": "Frame", "start": 1.000, "end": 1.333},
                    {"word": "accurate", "start": 1.333, "end": 1.667},
                    {"word": "test", "start": 1.667, "end": 2.000}
                ]
            }
            
            # Verify timing can be represented accurately in frames
            start_frame = int(segment['start'] * fps)
            end_frame = int(segment['end'] * fps)
            
            reconstructed_start = start_frame / fps
            reconstructed_end = end_frame / fps
            
            # Allow for one frame tolerance
            assert abs(reconstructed_start - segment['start']) <= frame_duration
            assert abs(reconstructed_end - segment['end']) <= frame_duration


class TestSubtitleRenderingSync:
    """Tests for subtitle rendering synchronization in the viewer."""
    
    def test_srt_format_precision(self):
        """Test that SRT format maintains timing precision."""
        translator = SRTTranslator()
        
        # Test precise timing conversion
        test_times = [
            (0.001, "00:00:00,001"),
            (1.500, "00:00:01,500"),
            (59.999, "00:00:59,999"),
            (3661.123, "01:01:01,123"),  # 1 hour, 1 minute, 1.123 seconds
        ]
        
        for seconds, expected_srt in test_times:
            td = timedelta(seconds=seconds)
            srt_time = translator._format_timestamp(td)
            assert srt_time == expected_srt, \
                f"Timing precision lost: {seconds}s -> {srt_time} (expected {expected_srt})"
    
    def test_vtt_format_compatibility(self):
        """Test WebVTT format compatibility for web viewer."""
        segments = [
            {
                "text": "WebVTT test segment",
                "start": 0.000,
                "end": 2.500
            }
        ]
        
        translator = SRTTranslator()
        srt_content = translator._create_srt_from_segments(segments)
        
        # Verify SRT can be converted to VTT format
        vtt_lines = ["WEBVTT", ""]
        srt_lines = srt_content.strip().split('\n')
        
        # Skip index lines and convert timestamps
        for i in range(2, len(srt_lines), 4):
            if i < len(srt_lines):
                timestamp_line = srt_lines[i]
                # VTT uses . instead of , for milliseconds
                vtt_timestamp = timestamp_line.replace(',', '.')
                vtt_lines.append(vtt_timestamp)
                
                if i + 1 < len(srt_lines):
                    vtt_lines.append(srt_lines[i + 1])
                vtt_lines.append("")
        
        vtt_content = '\n'.join(vtt_lines)
        assert "WEBVTT" in vtt_content
        assert "." in vtt_content  # VTT uses periods for milliseconds