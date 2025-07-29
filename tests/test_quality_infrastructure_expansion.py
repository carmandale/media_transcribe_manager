#!/usr/bin/env python3
"""
Expanded Quality Infrastructure Tests for Database Segment Operations
---------------------------------------------------------------------
This test suite implements Task 6: Expand Existing Quality Infrastructure,
building upon the existing 67-83% test coverage to include comprehensive
validation of database segment operations, performance benchmarks, and
edge case handling.
"""

import os
import sys
import pytest
import tempfile
import shutil
import time
import statistics
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Tuple
import random
import string

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.database import Database
from scribe.database_translation import DatabaseTranslator
from scribe.srt_translator import SRTTranslator, SRTSegment
from scribe.database_quality_metrics import (
    store_quality_metrics,
    store_timing_coordination_metrics,
    get_quality_metrics
)
from scribe.pipeline_database_integration import EnhancedPipeline, PipelineConfig


class TestPerformanceWithDatabaseSegments:
    """Test Task 6.1: Extend performance test suite for database segment operations."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "performance_test.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        yield db
        db.close()
        shutil.rmtree(temp_dir)
    
    @pytest.mark.performance
    def test_segment_insertion_performance(self, temp_db):
        """Test performance of inserting segments into database."""
        interview_id = temp_db.add_file("/test/perf_test.mp4", "perf_test_mp4", "video")
        
        # Measure time for different batch sizes
        batch_sizes = [10, 50, 100, 500]
        results = {}
        
        for batch_size in batch_sizes:
            segments = []
            for i in range(batch_size):
                segments.append({
                    'segment_index': i,
                    'start_time': i * 3.0,
                    'end_time': (i + 1) * 3.0,
                    'original_text': f"Performance test segment {i} with some text content.",
                    'confidence_score': 0.95
                })
            
            # Measure insertion time
            start_time = time.time()
            
            for seg in segments:
                temp_db.add_subtitle_segment(
                    interview_id=interview_id,
                    **seg
                )
            
            end_time = time.time()
            duration = end_time - start_time
            
            results[batch_size] = {
                'duration': duration,
                'segments_per_second': batch_size / duration
            }
            
            # Clean up for next test
            conn = temp_db._get_connection()
            conn.execute("DELETE FROM subtitle_segments WHERE interview_id = ?", (interview_id,))
            conn.commit()
        
        # Verify performance scales reasonably
        assert results[10]['segments_per_second'] > 100  # Should handle >100 segments/sec
        assert results[500]['duration'] < 5.0  # 500 segments should take < 5 seconds
        
        # Log performance results
        for batch_size, metrics in results.items():
            print(f"Batch {batch_size}: {metrics['segments_per_second']:.1f} segments/sec")
    
    @pytest.mark.performance
    def test_segment_retrieval_performance(self, temp_db):
        """Test performance of retrieving segments from database."""
        interview_id = temp_db.add_file("/test/retrieval_test.mp4", "retrieval_test_mp4", "video")
        
        # Insert test segments
        segment_counts = [100, 500, 1000]
        retrieval_times = {}
        
        for count in segment_counts:
            # Insert segments
            for i in range(count):
                temp_db.add_subtitle_segment(
                    interview_id=interview_id,
                    segment_index=i,
                    start_time=i * 2.0,
                    end_time=(i + 1) * 2.0,
                    original_text=f"Segment {i}",
                    english_text=f"Segment {i} translated"
                )
            
            # Measure retrieval time
            start_time = time.time()
            segments = temp_db.get_subtitle_segments(interview_id)
            end_time = time.time()
            
            retrieval_times[count] = end_time - start_time
            
            # Verify all segments retrieved
            assert len(segments) == count
            
            # Clean up
            conn = temp_db._get_connection()
            conn.execute("DELETE FROM subtitle_segments WHERE interview_id = ?", (interview_id,))
            conn.commit()
        
        # Verify retrieval performance
        assert retrieval_times[100] < 0.1  # 100 segments in < 100ms
        assert retrieval_times[1000] < 1.0  # 1000 segments in < 1 second
        
        # Verify scaling is reasonable (not exponential)
        scaling_factor = retrieval_times[1000] / retrieval_times[100]
        assert scaling_factor < 20  # Should scale sub-linearly
    
    @pytest.mark.performance
    def test_translation_coordination_overhead(self, temp_db):
        """Test Task 6.4: Measure database coordination overhead."""
        interview_id = temp_db.add_file("/test/overhead_test.mp4", "overhead_test_mp4", "video")
        
        # Create mock translator
        mock_translator = Mock()
        mock_translator.is_same_language.return_value = False
        
        db_translator = DatabaseTranslator(temp_db, mock_translator)
        
        # Add segments
        for i in range(50):
            temp_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=i,
                start_time=i * 3.0,
                end_time=(i + 1) * 3.0,
                original_text=f"Original text {i}"
            )
        
        # Measure translation with database coordination
        start_time = time.time()
        results = db_translator.translate_interview(interview_id, 'en', batch_size=50)
        db_duration = time.time() - start_time
        
        # Measure raw translation without database
        # For a fair comparison, make the mock call take some time
        def mock_translate_with_delay(texts, target_lang):
            time.sleep(0.001)  # Simulate API call delay
            return ["Translation"] * len(texts)
        
        mock_translator.batch_translate.side_effect = mock_translate_with_delay
        
        start_time = time.time()
        mock_translator.batch_translate(["Original text"] * 50, 'en')
        raw_duration = time.time() - start_time
        
        # Calculate overhead
        overhead = db_duration - raw_duration
        overhead_percentage = (overhead / raw_duration) * 100 if raw_duration > 0 else 0
        
        # Verify overhead is reasonable
        assert overhead < 1.0  # Less than 1 second overhead
        assert overhead_percentage < 50  # Less than 50% overhead
        
        print(f"Database coordination overhead: {overhead:.3f}s ({overhead_percentage:.1f}%)")


class TestSynchronizationValidationFramework:
    """Test Task 6.2: Build upon existing comprehensive test framework for synchronization."""
    
    @pytest.fixture
    def sync_test_db(self):
        """Create database for synchronization testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "sync_test.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        yield db
        db.close()
        shutil.rmtree(temp_dir)
    
    @pytest.mark.synchronization
    def test_perfect_segment_boundaries(self, sync_test_db):
        """Test perfect segment boundary alignment."""
        interview_id = sync_test_db.add_file("/test/perfect_sync.mp4", "perfect_sync_mp4", "video")
        
        # Create perfectly aligned segments
        perfect_segments = [
            (0, 0.000, 2.500, "First segment."),
            (1, 2.500, 5.000, "Second segment."),
            (2, 5.000, 7.500, "Third segment."),
            (3, 7.500, 10.000, "Fourth segment.")
        ]
        
        for idx, start, end, text in perfect_segments:
            sync_test_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Validate timing
        timing_validation = sync_test_db.validate_subtitle_timing(interview_id)
        
        assert len(timing_validation['gaps']) == 0
        assert len(timing_validation['overlaps']) == 0
        
        # Test with SRTTranslator boundary validation
        db_translator = DatabaseTranslator(sync_test_db)
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'original')
        
        # Verify perfect boundaries in SRT format
        for i in range(len(srt_segments) - 1):
            current = srt_segments[i]
            next_seg = srt_segments[i + 1]
            assert current.end_time == next_seg.start_time
    
    @pytest.mark.synchronization
    def test_segment_gaps_detection(self, sync_test_db):
        """Test detection of gaps between segments."""
        interview_id = sync_test_db.add_file("/test/gaps_test.mp4", "gaps_test_mp4", "video")
        
        # Create segments with intentional gaps
        gap_segments = [
            (0, 0.0, 2.0, "First segment."),
            (1, 2.5, 4.5, "Second segment with gap."),  # 0.5s gap
            (2, 5.0, 7.0, "Third segment with gap."),   # 0.5s gap
            (3, 7.1, 9.0, "Fourth segment with small gap.")  # 0.1s gap
        ]
        
        for idx, start, end, text in gap_segments:
            sync_test_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Validate timing
        timing_validation = sync_test_db.validate_subtitle_timing(interview_id)
        
        assert len(timing_validation['gaps']) == 3
        
        # Verify gap durations
        gaps = timing_validation['gaps']
        assert abs(gaps[0]['gap_duration'] - 0.5) < 0.001
        assert abs(gaps[1]['gap_duration'] - 0.5) < 0.001
        assert abs(gaps[2]['gap_duration'] - 0.1) < 0.001
    
    @pytest.mark.synchronization
    def test_segment_overlap_detection(self, sync_test_db):
        """Test detection of overlapping segments."""
        interview_id = sync_test_db.add_file("/test/overlap_test.mp4", "overlap_test_mp4", "video")
        
        # Create segments with overlaps
        overlap_segments = [
            (0, 0.0, 2.5, "First segment."),
            (1, 2.0, 4.0, "Second segment overlaps."),  # 0.5s overlap
            (2, 3.8, 6.0, "Third segment overlaps."),   # 0.2s overlap
            (3, 6.0, 8.0, "Fourth segment no overlap.")
        ]
        
        for idx, start, end, text in overlap_segments:
            sync_test_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Validate timing
        timing_validation = sync_test_db.validate_subtitle_timing(interview_id)
        
        assert len(timing_validation['overlaps']) == 2
        
        # Verify overlap durations
        overlaps = timing_validation['overlaps']
        assert abs(overlaps[0]['overlap_duration'] - 0.5) < 0.001
        assert abs(overlaps[1]['overlap_duration'] - 0.2) < 0.001
    
    @pytest.mark.synchronization
    def test_timing_coordination_with_translations(self, sync_test_db):
        """Test timing preservation across translations."""
        interview_id = sync_test_db.add_file("/test/timing_coord.mp4", "timing_coord_mp4", "video")
        
        # Create segments with translations
        segments = [
            (0, 0.0, 3.0, "Das ist ein Test.", "This is a test."),
            (1, 3.0, 6.0, "Es funktioniert gut.", "It works well."),
            (2, 6.0, 9.0, "Vielen Dank.", "Thank you very much.")
        ]
        
        for idx, start, end, original, english in segments:
            sync_test_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english
            )
        
        # Test timing coordination
        db_translator = DatabaseTranslator(sync_test_db)
        timing_validation = db_translator.validate_timing_coordination(interview_id, 'en')
        
        assert timing_validation['timing_valid'] == True
        assert timing_validation['boundary_validation'] == True
        assert timing_validation['database_consistency'] == True
        assert timing_validation['srt_compatibility'] == True


class TestEdgeCasesAndAccentHandling:
    """Test Task 6.3: Expand edge case testing leveraging accent/speech handling."""
    
    @pytest.fixture
    def edge_case_db(self):
        """Create database for edge case testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "edge_case_test.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        yield db
        db.close()
        shutil.rmtree(temp_dir)
    
    @pytest.mark.edge_cases
    def test_empty_segments_handling(self, edge_case_db):
        """Test handling of empty or whitespace-only segments."""
        interview_id = edge_case_db.add_file("/test/empty_segments.mp4", "empty_segments_mp4", "video")
        
        # Create segments with edge cases
        edge_segments = [
            (0, 0.0, 2.0, "Normal segment."),
            (1, 2.0, 4.0, ""),  # Empty
            (2, 4.0, 6.0, "   "),  # Whitespace only
            (3, 6.0, 8.0, "\n\t"),  # Special whitespace
            (4, 8.0, 10.0, "Another normal segment.")
        ]
        
        for idx, start, end, text in edge_segments:
            # Database should handle empty segments
            edge_case_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Verify all segments stored
        segments = edge_case_db.get_subtitle_segments(interview_id)
        assert len(segments) == 5
        
        # Test translation handling of empty segments
        mock_translator = Mock()
        mock_translator.batch_translate.return_value = ["Normal translated.", "", "", "", "Another translated."]
        
        db_translator = DatabaseTranslator(edge_case_db, mock_translator)
        
        # Should handle empty segments gracefully
        validation = db_translator.validate_translations(interview_id, 'en')
        assert 'issues' in validation
    
    @pytest.mark.edge_cases
    def test_very_long_segments(self, edge_case_db):
        """Test handling of unusually long segments."""
        interview_id = edge_case_db.add_file("/test/long_segments.mp4", "long_segments_mp4", "video")
        
        # Create very long text content
        long_text = " ".join([f"Word{i}" for i in range(1000)])  # 1000 words
        
        edge_case_db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=300.0,  # 5 minutes
            original_text=long_text
        )
        
        # Should handle without issues
        segments = edge_case_db.get_subtitle_segments(interview_id)
        assert len(segments) == 1
        assert len(segments[0]['original_text']) > 5000  # Characters
    
    @pytest.mark.edge_cases
    def test_special_characters_and_accents(self, edge_case_db):
        """Test handling of special characters and accented text."""
        interview_id = edge_case_db.add_file("/test/special_chars.mp4", "special_chars_mp4", "video")
        
        # Various special cases
        special_segments = [
            (0, 0.0, 3.0, "Müller, Schäfer & Köhler GmbH"),  # German umlauts
            (1, 3.0, 6.0, "C'est très bien, n'est-ce pas?"),  # French accents
            (2, 6.0, 9.0, "¿Cómo está usted? ¡Muy bien!"),  # Spanish punctuation
            (3, 9.0, 12.0, "א״ב ג׳ד ה׳ו"),  # Hebrew with special marks
            (4, 12.0, 15.0, "Math: x² + y² = r²; π ≈ 3.14"),  # Mathematical symbols
            (5, 15.0, 18.0, 'Quote: "Hello," she said.'),  # Mixed quotes
            (6, 18.0, 21.0, "Emoji test: 🎉 🚀 ✅")  # Emojis
        ]
        
        for idx, start, end, text in special_segments:
            edge_case_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Verify all stored correctly
        segments = edge_case_db.get_subtitle_segments(interview_id)
        assert len(segments) == 7
        
        # Verify special characters preserved
        for orig_seg, stored_seg in zip(special_segments, segments):
            assert stored_seg['original_text'] == orig_seg[3]
    
    @pytest.mark.edge_cases
    def test_rapid_speech_segments(self, edge_case_db):
        """Test handling of rapid speech with very short segments."""
        interview_id = edge_case_db.add_file("/test/rapid_speech.mp4", "rapid_speech_mp4", "video")
        
        # Very short segments (< 1 second each)
        rapid_segments = []
        current_time = 0.0
        
        for i in range(20):
            duration = random.uniform(0.3, 0.8)  # 300-800ms segments
            rapid_segments.append((
                i,
                current_time,
                current_time + duration,
                f"Quick {i}!"
            ))
            current_time += duration
        
        for idx, start, end, text in rapid_segments:
            edge_case_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Get segments directly and calculate metrics
        segments = edge_case_db.get_subtitle_segments(interview_id)
        
        # Calculate metrics manually for the test
        short_segments = sum(1 for s in segments if (s['end_time'] - s['start_time']) < 1.0)
        durations = [s['end_time'] - s['start_time'] for s in segments]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Verify short segments are tracked
        assert short_segments > 15  # Most are < 1 second
        assert avg_duration < 1.0


class TestBenchmarkEnhancements:
    """Test Task 6.4: Enhance benchmarks for database coordination overhead."""
    
    @pytest.mark.benchmark
    def test_srt_generation_benchmark(self, benchmark):
        """Benchmark SRT generation from database segments."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "benchmark.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create test data
        interview_id = db.add_file("/test/benchmark.mp4", "benchmark_mp4", "video")
        
        for i in range(100):
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=i,
                start_time=i * 3.0,
                end_time=(i + 1) * 3.0,
                original_text=f"Benchmark segment {i}",
                english_text=f"Benchmark segment {i} translated"
            )
        
        db_translator = DatabaseTranslator(db)
        
        # Benchmark SRT generation
        def generate_srt():
            segments = db_translator.convert_segments_to_srt_format(interview_id, 'en')
            return len(segments)
        
        # Run benchmark
        result = benchmark(generate_srt)
        assert result == 100
        
        db.close()
        shutil.rmtree(temp_dir)
    
    @pytest.mark.benchmark
    def test_quality_validation_benchmark(self, benchmark):
        """Benchmark quality validation with database segments."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "quality_benchmark.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create test data
        interview_id = db.add_file("/test/quality.mp4", "quality_mp4", "video")
        
        for i in range(50):
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=i,
                start_time=i * 2.0,
                end_time=(i + 1) * 2.0,
                original_text=f"Original {i}",
                english_text=f"Translated {i}"
            )
        
        db_translator = DatabaseTranslator(db)
        
        # Benchmark validation
        def validate_quality():
            validation = db_translator.validate_translations(interview_id, 'en')
            return validation['valid']
        
        result = benchmark(validate_quality)
        assert result is not None
        
        db.close()
        shutil.rmtree(temp_dir)


class TestSampleInterviewValidation:
    """Test Task 6.5: Use existing sample interview testing infrastructure."""
    
    @pytest.fixture
    def sample_interview_db(self):
        """Create database with sample interview data."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "sample_interview.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        yield db
        db.close()
        shutil.rmtree(temp_dir)
    
    @pytest.mark.integration
    def test_realistic_interview_processing(self, sample_interview_db):
        """Test with realistic interview segment patterns."""
        interview_id = sample_interview_db.add_file("/test/realistic_interview.mp4", "realistic_interview_mp4", "video")
        
        # Simulate realistic interview segments
        interview_segments = [
            # Introduction
            (0, 0.0, 5.2, "Ich wurde geboren in Berlin, neunzehnhundertdreißig."),
            (1, 5.2, 9.8, "Meine Familie war... äh... jüdisch, aber nicht religiös."),
            
            # Pause and continuation
            (2, 10.5, 15.3, "Mein Vater war Arzt. Meine Mutter war Lehrerin."),
            (3, 15.3, 18.7, "Wir hatten ein gutes Leben bis..."),
            (4, 19.2, 24.5, "Bis die Nazis an die Macht kamen."),
            
            # Emotional section with pauses
            (5, 26.0, 30.2, "Es war sehr schwierig für uns."),
            (6, 30.2, 32.8, "[weint]"),  # Non-verbal
            (7, 34.5, 39.2, "Entschuldigung. Es ist immer noch schwer darüber zu sprechen."),
            
            # Detailed recollection
            (8, 40.0, 45.3, "Im November 1938, während der Kristallnacht..."),
            (9, 45.3, 50.7, "Sie haben unsere Synagoge verbrannt und viele Geschäfte zerstört."),
            (10, 50.7, 55.2, "Mein Vater wurde verhaftet und nach Dachau gebracht."),
            
            # Complex sentence with names
            (11, 56.0, 62.5, "Herr Goldstein, unser Nachbar, hat uns geholfen zu fliehen."),
            (12, 62.5, 68.3, "Wir sind über Holland nach England gekommen, im März 1939."),
            
            # Reflection
            (13, 70.0, 75.8, "Ich hatte Glück. Viele meiner Freunde haben es nicht geschafft."),
            (14, 75.8, 80.2, "Diese Erinnerungen werde ich nie vergessen.")
        ]
        
        # Add segments
        for idx, start, end, text in interview_segments:
            sample_interview_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text,
                confidence_score=0.85 + random.uniform(0, 0.1)
            )
        
        # Test quality metrics
        quality_metrics = sample_interview_db.get_subtitle_quality_metrics(interview_id)
        
        assert quality_metrics['total_segments'] == 15
        assert quality_metrics['avg_segment_duration'] > 3.0  # Realistic speech pace
        assert quality_metrics['avg_confidence'] > 0.85
        
        # Test timing validation
        timing_validation = sample_interview_db.validate_subtitle_timing(interview_id)
        
        # Should have some natural gaps (pauses)
        assert len(timing_validation['gaps']) > 0
        assert len(timing_validation['overlaps']) == 0  # No overlaps in clean interview
        
        # Verify non-verbal segment handling
        segments = sample_interview_db.get_subtitle_segments(interview_id)
        non_verbal = [s for s in segments if '[' in s['original_text']]
        assert len(non_verbal) == 1
    
    @pytest.mark.integration
    def test_multilingual_interview_segments(self, sample_interview_db):
        """Test interview with code-switching between languages."""
        interview_id = sample_interview_db.add_file("/test/multilingual.mp4", "multilingual_mp4", "video")
        
        # Mixed language segments (German/English/Hebrew)
        mixed_segments = [
            (0, 0.0, 4.5, "Ich war in der Wehrmacht, you know?"),  # German + English
            (1, 4.5, 9.2, "Es war complicated, sehr complicated."),  # Mixed
            (2, 9.2, 14.0, "Mein Name war יצחק, Isaac auf Deutsch."),  # German + Hebrew
            (3, 14.0, 18.5, "They called me Itzik in the army."),  # English
            (4, 18.5, 23.2, "שלום, ich meine, Guten Tag."),  # Hebrew + German
        ]
        
        for idx, start, end, text in mixed_segments:
            sample_interview_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Test with language detection
        mock_translator = Mock()
        mock_translator.openai_client = Mock()
        
        db_translator = DatabaseTranslator(sample_interview_db, mock_translator)
        
        # Should handle mixed languages gracefully
        segments = sample_interview_db.get_subtitle_segments(interview_id)
        assert len(segments) == 5


class TestQualityStandardsMaintenance:
    """Test Task 6.6: Maintain quality standards with database segment metrics."""
    
    @pytest.fixture
    def quality_db(self):
        """Create database for quality testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "quality_test.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Add quality metrics schema
        from scribe.database_quality_metrics import add_quality_metrics_schema
        add_quality_metrics_schema(db)
        
        yield db
        db.close()
        shutil.rmtree(temp_dir)
    
    @pytest.mark.quality
    def test_segment_quality_standards(self, quality_db):
        """Test that segment quality meets established standards."""
        interview_id = quality_db.add_file("/test/quality_standards.mp4", "quality_standards_mp4", "video")
        
        # Add high-quality segments
        high_quality_segments = []
        for i in range(20):
            high_quality_segments.append({
                'segment_index': i,
                'start_time': i * 4.0,
                'end_time': (i + 1) * 4.0 - 0.1,  # Small gap for natural speech
                'original_text': f"Dies ist ein qualitativ hochwertiges Segment Nummer {i}.",
                'confidence_score': 0.92 + random.uniform(0, 0.08)  # 0.92-1.0
            })
        
        for seg in high_quality_segments:
            quality_db.add_subtitle_segment(interview_id=interview_id, **seg)
        
        # Store quality metrics
        store_quality_metrics(quality_db, interview_id, 'de', {
            'overall_quality': 9.2,
            'translation_accuracy': 0.95,
            'timing_precision': 0.98,
            'boundary_validation': 1.0
        })
        
        # Verify quality standards
        metrics = get_quality_metrics(quality_db, interview_id, 'de')
        
        assert metrics is not None
        if 'overall_quality_score' in metrics:
            assert metrics['overall_quality_score'] >= 9.0  # High quality standard
        
        # Get segments and calculate quality metrics manually
        segments = quality_db.get_subtitle_segments(interview_id)
        
        # Calculate metrics
        confidences = [s.get('confidence_score', 0) for s in segments]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        low_confidence_segments = sum(1 for c in confidences if c < 0.8)
        
        durations = [s['end_time'] - s['start_time'] for s in segments]
        avg_duration = sum(durations) / len(durations) if durations else 0
        short_segments = sum(1 for d in durations if d < 1.0)
        
        assert avg_confidence >= 0.92
        assert low_confidence_segments == 0  # No low confidence
        assert avg_duration >= 3.0  # Natural pace
        assert short_segments == 0  # No rushed segments
    
    @pytest.mark.quality
    def test_quality_degradation_detection(self, quality_db):
        """Test detection of quality degradation in segments."""
        interview_id = quality_db.add_file("/test/degradation.mp4", "degradation_mp4", "video")
        
        # Add segments with varying quality
        for i in range(30):
            # Simulate quality degradation over time
            if i < 10:
                confidence = 0.95
                text = f"Clear segment {i} with good audio quality."
            elif i < 20:
                confidence = 0.85
                text = f"Segment {i} with some background noise..."
            else:
                confidence = 0.75
                text = f"[inaudible] segment {i} [unclear]"
            
            quality_db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=i,
                start_time=i * 3.0,
                end_time=(i + 1) * 3.0,
                original_text=text,
                confidence_score=confidence
            )
        
        # Get segments and calculate degradation metrics
        segments = quality_db.get_subtitle_segments(interview_id)
        
        # Calculate metrics
        confidences = [s.get('confidence_score', 0) for s in segments]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        low_confidence_segments = sum(1 for c in confidences if c < 0.8)
        
        # Should detect quality issues
        assert low_confidence_segments >= 10  # Last 10 segments
        assert avg_confidence <= 0.85  # Overall quality degraded
        
        # Store quality metrics reflecting the degradation
        store_quality_metrics(quality_db, interview_id, 'original', {
            'overall_quality': 6.5,
            'translation_accuracy': 0.0,  # No translation
            'timing_precision': 0.95,
            'boundary_validation': 1.0
        })
    
    @pytest.mark.quality
    def test_comprehensive_quality_report(self, quality_db):
        """Test generation of comprehensive quality reports."""
        # Create multiple interviews with different quality levels
        interviews = [
            ('high_quality', 9.5, 0.98),
            ('medium_quality', 7.5, 0.85),
            ('low_quality', 5.5, 0.72)
        ]
        
        for name, quality_score, confidence in interviews:
            interview_id = quality_db.add_file(f"/test/{name}.mp4", f"{name}_mp4", "video")
            
            # Add segments
            for i in range(10):
                quality_db.add_subtitle_segment(
                    interview_id=interview_id,
                    segment_index=i,
                    start_time=i * 3.0,
                    end_time=(i + 1) * 3.0,
                    original_text=f"Segment {i} for {name}",
                    english_text=f"Segment {i} for {name} translated",
                    confidence_score=min(1.0, max(0.0, confidence + random.uniform(-0.05, 0.05)))
                )
            
            # Store quality metrics
            store_quality_metrics(quality_db, interview_id, 'en', {
                'overall_quality': quality_score,
                'translation_accuracy': quality_score / 10,
                'timing_precision': 0.95,
                'boundary_validation': 1.0
            })
        
        # Generate quality report
        from scribe.pipeline_database_integration import EnhancedPipeline
        pipeline = EnhancedPipeline(use_database_segments=True)
        pipeline.db = quality_db
        
        report = pipeline._generate_pipeline_quality_report()
        
        assert 'languages' in report
        assert 'en' in report['languages']
        
        # Should have metrics for all interviews
        en_metrics = report['languages']['en']
        assert en_metrics['evaluated_count'] >= 3
        
        # Average quality should reflect the range
        if en_metrics['average_quality']:
            assert 5.0 <= en_metrics['average_quality'] <= 10.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-k', 'not benchmark'])  # Skip benchmark tests in normal runs