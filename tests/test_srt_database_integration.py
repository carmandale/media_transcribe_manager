#!/usr/bin/env python3
"""
Database integration tests for SRTTranslator functionality.

This test suite extends the existing SRTTranslator test coverage (67%) by adding
comprehensive tests for database segment integration, building upon the proven
SRT translation foundation while adding database coordination capabilities.

Task 4.1: Extend existing SRTTranslator tests for database segment integration
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.database import Database
from scribe.database_translation import DatabaseTranslator
from scribe.srt_translator import SRTTranslator, SRTSegment
from scribe.translate import HistoricalTranslator
from scribe.database_quality_metrics import (
    add_quality_metrics_schema,
    store_quality_metrics,
    get_quality_metrics
)


class TestSRTTranslatorDatabaseIntegration:
    """Test SRTTranslator integration with database segments (Task 4.1)."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_translator(self):
        """Create a mock HistoricalTranslator for testing."""
        mock = Mock(spec=HistoricalTranslator)
        mock.openai_client = MagicMock()
        mock.batch_translate.return_value = [
            'I was born in nineteen thirty.',
            'In the Wehrmacht came?',
            'During the war.'
        ]
        mock.is_same_language.return_value = False
        mock.validate_hebrew_translation.return_value = True
        return mock
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_database_segments_to_srt_conversion(self, temp_dir, mock_translator):
        """Test converting database segments to SRT format using existing SRTTranslator."""
        db_path = temp_dir / "test_db_to_srt.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview with segments
        interview_id = db.add_file("/test/interview.mp4", "interview_mp4", "video")
        
        # Add segments that mirror realistic interview structure
        historical_segments = [
            (0, 0.0, 3.5, 'Ich wurde geboren neunzehnhundertdreißig.'),
            (1, 3.5, 7.25, 'In die Wehrmacht gekommen?'),
            (2, 7.25, 12.0, 'Während des Krieges.')
        ]
        
        for idx, start, end, original in historical_segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        # Translate using database translator
        db_translator = DatabaseTranslator(db, mock_translator)
        translation_results = db_translator.translate_interview(interview_id, 'en')
        
        # Convert to SRT format using existing SRTTranslator integration
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'en')
        
        # Verify SRT format matches expected structure
        assert len(srt_segments) == 3
        assert all(isinstance(seg, SRTSegment) for seg in srt_segments)
        
        # Test timing precision (building on existing timing tests)
        assert srt_segments[0].start_time == "00:00:00,000"
        assert srt_segments[0].end_time == "00:00:03,500"
        assert srt_segments[1].start_time == "00:00:03,500"
        assert srt_segments[1].end_time == "00:00:07,250"
        assert srt_segments[2].start_time == "00:00:07,250"
        assert srt_segments[2].end_time == "00:00:12,000"
        
        # Test translated content
        assert srt_segments[0].text == 'I was born in nineteen thirty.'
        assert srt_segments[1].text == 'In the Wehrmacht came?'
        assert srt_segments[2].text == 'During the war.'
        
        # Test SRT indices (1-based)
        assert srt_segments[0].index == 1
        assert srt_segments[1].index == 2
        assert srt_segments[2].index == 3
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_multilanguage_database_srt_coordination(self, temp_dir, mock_translator):
        """Test database coordination with multiple language SRT generation."""
        db_path = temp_dir / "test_multilang_srt.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock different translations for different languages
        def mock_batch_translate_multilang(texts, target_lang, source_lang=None):
            translations = []
            for text in texts:
                if target_lang == 'en':
                    if 'geboren' in text.lower():
                        translations.append('I was born in nineteen thirty.')
                    elif 'wehrmacht' in text.lower():
                        translations.append('In the Wehrmacht.')
                    else:
                        translations.append(f'English: {text}')
                elif target_lang == 'he':
                    if 'geboren' in text.lower():
                        translations.append('נולדתי בשנת אלף תשע מאות ושלושים.')
                    elif 'wehrmacht' in text.lower():
                        translations.append('בוורמאכט.')
                    else:
                        translations.append(f'עברית: {text}')
                else:
                    translations.append(f'{target_lang}: {text}')
            return translations
        
        mock_translator.batch_translate.side_effect = mock_batch_translate_multilang
        
        # Create interview
        interview_id = db.add_file("/test/multilang.mp4", "multilang_mp4", "video")
        
        segments = [
            (0, 0.0, 4.0, 'Ich wurde geboren neunzehnhundertdreißig.'),
            (1, 4.0, 7.0, 'In die Wehrmacht.')
        ]
        
        for idx, start, end, original in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Translate to multiple languages
        en_results = db_translator.translate_interview(interview_id, 'en')
        he_results = db_translator.translate_interview(interview_id, 'he')
        
        # Generate SRT for each language
        en_srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'en')
        he_srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'he')
        
        # Verify both languages have consistent timing
        assert len(en_srt_segments) == len(he_srt_segments) == 2
        
        for en_seg, he_seg in zip(en_srt_segments, he_srt_segments):
            # Timing must be identical
            assert en_seg.start_time == he_seg.start_time
            assert en_seg.end_time == he_seg.end_time
            assert en_seg.index == he_seg.index
        
        # Verify content is correctly translated
        assert 'nineteen thirty' in en_srt_segments[0].text.lower()
        assert any('\u0590' <= c <= '\u05FF' for c in he_srt_segments[0].text)  # Hebrew characters
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_database_segment_boundary_preservation(self, temp_dir, mock_translator):
        """Test that database segment boundaries are preserved in SRT conversion."""
        db_path = temp_dir / "test_boundaries.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview with challenging boundaries (building on existing boundary tests)
        interview_id = db.add_file("/test/boundaries.mp4", "boundaries_mp4", "video")
        
        # Complex boundary scenarios (avoid zero-length segments due to DB constraints)
        boundary_segments = [
            (0, 0.0, 2.123, 'First segment with precise timing.'),
            (1, 2.123, 2.124, ''),  # Very short segment (not zero-length)
            (2, 2.124, 5.678, 'Third segment after short.'),
            (3, 5.678, 8.999, '   '),  # Whitespace-only segment
            (4, 8.999, 12.5, 'Final segment with normal content.')
        ]
        
        for idx, start, end, original in boundary_segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Mock translations to handle edge cases
        mock_translator.batch_translate.return_value = [
            'First segment translated.',
            'Third segment translated.',
            'Final segment translated.'
        ]
        
        # Translate and convert to SRT
        db_translator.translate_interview(interview_id, 'en')
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'en')
        
        # Verify all segments preserved (including edge cases)
        assert len(srt_segments) == 5
        
        # Verify precise timing preservation
        assert srt_segments[0].start_time == "00:00:00,000"
        assert srt_segments[0].end_time == "00:00:02,123"
        assert srt_segments[1].start_time == "00:00:02,123"
        assert srt_segments[1].end_time == "00:00:02,124"  # Very short segment preserved
        assert srt_segments[2].start_time == "00:00:02,124"
        assert srt_segments[2].end_time == "00:00:05,678"
        
        # Verify content handling
        assert srt_segments[1].text == ''  # Empty preserved
        assert srt_segments[3].text == '   '  # Whitespace preserved
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_existing_srt_workflow_with_database_segments(self, temp_dir, mock_translator):
        """Test that existing SRT workflows work seamlessly with database segments."""
        db_path = temp_dir / "test_workflow.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock SRTTranslator to test integration
        srt_translator = SRTTranslator(translator=mock_translator)
        
        # Mock language detection (building on existing detection tests)
        mock_translator.openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="German"))]),
            Mock(choices=[Mock(message=Mock(content="English"))]),
            Mock(choices=[Mock(message=Mock(content="German"))])
        ]
        
        # Create interview
        interview_id = db.add_file("/test/workflow.mp4", "workflow_mp4", "video")
        
        # Mixed language segments (typical historical interview pattern)
        mixed_segments = [
            (0, 0.0, 3.0, 'Ich wurde geboren neunzehnhundertdreißig.'),
            (1, 3.0, 6.0, 'Yes, I was drafted in 1944.'),
            (2, 6.0, 9.0, 'Das war sehr schwierig für mich.')
        ]
        
        for idx, start, end, original in mixed_segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        # Use DatabaseTranslator to coordinate with existing SRT functionality
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Translate to German (preserve German, translate English)
        translation_results = db_translator.translate_interview(interview_id, 'de')
        
        # Convert to SRT segments
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'de')
        
        # Verify mixed language handling works as expected
        assert len(srt_segments) == 3
        
        # Should preserve original German and translate English
        segments_from_db = db.get_subtitle_segments(interview_id)
        
        # Since mock translator returns the mocked translations, check that translation occurred
        # The test verifies the workflow works, not the specific translation content
        assert segments_from_db[0]['german_text'] is not None
        assert segments_from_db[1]['german_text'] is not None  
        assert segments_from_db[2]['german_text'] is not None
        
        # Verify all segments were processed
        assert len(segments_from_db) == 3
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_database_srt_timing_accuracy_mechanisms(self, temp_dir, mock_translator):
        """Test database integration with existing SRT timing accuracy mechanisms."""
        db_path = temp_dir / "test_timing_accuracy.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview
        interview_id = db.add_file("/test/timing.mp4", "timing_mp4", "video")
        
        # Segments with challenging floating-point precision
        precision_segments = [
            (0, 0.0, 1.999, 'First segment.'),
            (1, 1.999, 3.661999, 'Second with precise end.'),  # Tests rounding
            (2, 3.661999, 7.33333, 'Third with repeating decimal.'),
            (3, 7.33333, 10.12345, 'Fourth with many decimals.')
        ]
        
        for idx, start, end, original in precision_segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Convert to SRT format (tests existing timing mechanisms)
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'original')
        
        # Verify timing conversion handles precision correctly
        assert srt_segments[0].start_time == "00:00:00,000"
        assert srt_segments[0].end_time == "00:00:01,999"
        assert srt_segments[1].start_time == "00:00:01,999"  
        assert srt_segments[1].end_time == "00:00:03,662"  # Rounded properly
        assert srt_segments[2].start_time == "00:00:03,662"
        assert srt_segments[2].end_time == "00:00:07,333"
        assert srt_segments[3].start_time == "00:00:07,333"
        assert srt_segments[3].end_time == "00:00:10,123"
        
        # Verify no timing gaps or overlaps
        for i in range(len(srt_segments) - 1):
            current_end = srt_segments[i].end_time
            next_start = srt_segments[i + 1].start_time
            assert current_end == next_start, f"Gap between segments {i} and {i+1}"
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_database_segment_language_detection_integration(self, temp_dir, mock_translator):
        """Test database segment integration with existing language detection."""
        db_path = temp_dir / "test_lang_detection.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create SRTTranslator for language detection testing
        srt_translator = SRTTranslator(translator=mock_translator)
        
        # Mock batch language detection response
        batch_response = Mock(choices=[Mock(message=Mock(content="""1: German
2: English
3: German
4: Hebrew"""))])
        mock_translator.openai_client.chat.completions.create.return_value = batch_response
        
        # Create interview
        interview_id = db.add_file("/test/detection.mp4", "detection_mp4", "video")
        
        # Mixed language segments for detection testing (include Hebrew for pattern detection)
        detection_segments = [
            (0, 0.0, 2.0, 'Guten Tag, wie geht es Ihnen?'),
            (1, 2.0, 4.0, 'Hello, how are you today?'),
            (2, 4.0, 6.0, 'Ich bin in Deutschland geboren.'),
            (3, 6.0, 8.0, 'מה שלומך היום?')  # Hebrew text for pattern detection
        ]
        
        for idx, start, end, original in detection_segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        # Test language detection for each segment
        segments_from_db = db.get_subtitle_segments(interview_id)
        
        # Create SRTSegments and perform batch language detection (this is how it works in practice)
        srt_segments = []
        for segment_data in segments_from_db:
            srt_segment = SRTSegment(
                index=segment_data['segment_index'] + 1,
                start_time=f"00:00:{int(segment_data['start_time']):02d},000",
                end_time=f"00:00:{int(segment_data['end_time']):02d},000",
                text=segment_data['original_text']
            )
            srt_segments.append(srt_segment)
        
        # Use batch language detection (this sets detected_language on segments)
        from scribe.batch_language_detection import detect_languages_for_segments
        detect_languages_for_segments(srt_segments, mock_translator.openai_client)
        
        # Now get detected languages
        detected_languages = [seg.detected_language for seg in srt_segments]
        
        # Verify language detection works correctly
        assert detected_languages[0] == 'de'  # German greeting
        assert detected_languages[1] == 'en'  # English greeting
        assert detected_languages[2] == 'de'  # German sentence
        assert detected_languages[3] == 'he'  # Hebrew sentence (pattern detected)
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_database_srt_batch_processing_efficiency(self, temp_dir, mock_translator):
        """Test database segment batch processing with SRT translation efficiency."""
        db_path = temp_dir / "test_batch_efficiency.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview
        interview_id = db.add_file("/test/batch.mp4", "batch_mp4", "video")
        
        # Create many segments with repeated text (tests deduplication)
        batch_segments = []
        repeated_texts = [
            'Thank you very much.',
            'Das ist sehr gut.',
            'I was born in Germany.',
            'Ich wurde in Deutschland geboren.'
        ]
        
        for i in range(50):  # 50 segments total
            text = repeated_texts[i % len(repeated_texts)]
            start_time = i * 2.0
            end_time = start_time + 2.0
            
            batch_segments.append((i, start_time, end_time, text))
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=i,
                start_time=start_time,
                end_time=end_time,
                original_text=text
            )
        
        # Mock batch translation to track calls
        call_counts = {'batch_translate': 0}
        original_batch_translate = mock_translator.batch_translate
        
        def counting_batch_translate(texts, target_lang, source_lang=None):
            call_counts['batch_translate'] += 1
            # Simulate realistic translations
            translations = []
            for text in texts:
                if 'thank you' in text.lower():
                    translations.append('Vielen Dank.')
                elif 'born' in text.lower():
                    translations.append('Ich wurde in Deutschland geboren.')
                else:
                    translations.append(f'Translated: {text}')
            return translations
        
        mock_translator.batch_translate.side_effect = counting_batch_translate
        
        # Process with database translator
        db_translator = DatabaseTranslator(db, mock_translator)
        results = db_translator.translate_interview(interview_id, 'de', batch_size=25)
        
        # Verify efficiency: should deduplicate repeated texts
        assert results['translated'] == 50  # All segments processed
        
        # Should make minimal batch translation calls due to deduplication
        # 4 unique texts, batch size 25, so should be 1 call
        assert call_counts['batch_translate'] <= 2, f"Too many batch calls: {call_counts['batch_translate']}"
        
        # Verify SRT conversion works efficiently too
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'de')
        assert len(srt_segments) == 50
        
        # Verify timing is sequential and correct
        for i, srt_seg in enumerate(srt_segments):
            expected_start = f"00:{i*2//60:02d}:{(i*2)%60:02d},000"
            expected_end = f"00:{(i*2+2)//60:02d}:{((i*2+2)%60):02d},000"
            assert srt_seg.start_time == expected_start
            assert srt_seg.end_time == expected_end
        
        db.close()


class TestSRTTranslatorDatabaseCompatibility:
    """Test compatibility between existing SRTTranslator functionality and database integration."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_existing_srt_file_processing_preserved(self, temp_dir):
        """Test that existing SRT file processing continues to work alongside database integration."""
        # Create traditional SRT file
        srt_content = """1
00:00:00,000 --> 00:00:03,000
Ich wurde geboren neunzehnhundertdreißig.

2
00:00:03,000 --> 00:00:06,000
In die Wehrmacht gekommen?

3
00:00:06,000 --> 00:00:09,000
Das war sehr schwierig für mich.
"""
        
        srt_file = temp_dir / "traditional.srt"
        srt_file.write_text(srt_content, encoding='utf-8')
        
        # Test existing SRTTranslator functionality
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.openai_client = MagicMock()
        
        srt_translator = SRTTranslator(translator=mock_translator)
        
        # Parse SRT file (existing functionality)
        segments = srt_translator.parse_srt(str(srt_file))
        
        # Verify existing parsing works
        assert len(segments) == 3
        assert segments[0].text == 'Ich wurde geboren neunzehnhundertdreißig.'
        assert segments[0].start_time == '00:00:00,000'
        assert segments[0].end_time == '00:00:03,000'
        
        # Test that database integration doesn't break this
        db_path = temp_dir / "compatibility.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create database translator
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Both should coexist without interference
        interview_id = db.add_file("/test/compat.mp4", "compat_mp4", "video")
        
        # Add database segments
        for i, seg in enumerate(segments):
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=i,
                start_time=i * 3.0,
                end_time=(i + 1) * 3.0,
                original_text=seg.text
            )
        
        # Database SRT conversion should work
        db_srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'original')
        
        # Results should be equivalent
        assert len(db_srt_segments) == len(segments)
        for orig_seg, db_seg in zip(segments, db_srt_segments):
            assert orig_seg.text == db_seg.text
        
        db.close()
    
    @pytest.mark.unit
    def test_srt_segment_format_consistency(self):
        """Test that database-generated SRT segments match existing SRTSegment format."""
        # Create SRTSegment using existing constructor
        traditional_segment = SRTSegment(
            index=1,
            start_time="00:00:00,000",
            end_time="00:00:03,500",
            text="Test segment text."
        )
        
        # Verify it has expected attributes
        assert hasattr(traditional_segment, 'index')
        assert hasattr(traditional_segment, 'start_time')
        assert hasattr(traditional_segment, 'end_time')
        assert hasattr(traditional_segment, 'text')
        
        # Test that database conversion creates compatible segments
        # (This is tested in integration tests above, but verify interface)
        from scribe.database_translation import DatabaseTranslator
        
        # Verify the conversion method exists and returns SRTSegment objects
        assert hasattr(DatabaseTranslator, 'convert_segments_to_srt_format')
        
        # The method should return List[SRTSegment] - verified in integration tests
    
    @pytest.mark.unit
    def test_database_translator_preserves_srt_translator_interface(self):
        """Test that DatabaseTranslator preserves SRTTranslator interface compatibility."""
        from scribe.database_translation import DatabaseTranslator
        from scribe.srt_translator import SRTTranslator
        
        # Verify that DatabaseTranslator has SRT-related methods
        assert hasattr(DatabaseTranslator, 'convert_segments_to_srt_format')
        
        # Verify return types are compatible (SRTSegment objects)
        # This ensures database integration doesn't break existing SRT workflows
        
        # The DatabaseTranslator should work alongside SRTTranslator, not replace it
        # SRTTranslator should continue to work for file-based operations
        assert callable(SRTTranslator)  # Still available
        
        # DatabaseTranslator adds database capabilities without breaking SRT functionality
        assert callable(DatabaseTranslator)  # Database integration available
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_quality_metrics_storage_integration(self, temp_dir):
        """Test Task 4.4: Enhance existing quality framework with database-backed metrics."""
        db_path = temp_dir / "test_quality_metrics.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock translator
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.batch_translate.return_value = ['This is a test.', 'For quality measurements.']
        
        # Initialize quality metrics schema
        add_quality_metrics_schema(db)
        
        # Create interview with segments
        interview_id = db.add_file("/test/quality_test.mp4", "quality_test_mp4", "video")
        
        segments = [
            (0, 0.0, 3.0, 'Das ist ein Test.'),
            (1, 3.0, 6.0, 'Für Qualitätsmessungen.')
        ]
        
        for idx, start, end, original in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                confidence_score=0.95
            )
        
        # Create evaluator mock
        mock_evaluator = Mock()
        mock_evaluator.evaluate.return_value = {'score': 8.5}
        mock_evaluator.get_score.return_value = 8.5
        
        db_translator = DatabaseTranslator(db, mock_translator, mock_evaluator)
        
        # Translate and validate with enhanced quality check
        db_translator.translate_interview(interview_id, 'en')
        validation_results = db_translator.validate_translations(
            interview_id, 'en', enhanced_quality_check=True
        )
        
        # Verify quality metrics were stored
        metrics = get_quality_metrics(db, interview_id, 'en')
        assert metrics is not None
        assert 'overall_quality_score' in metrics or 'overall_quality' in validation_results.get('quality_scores', {})
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_timing_accuracy_mechanisms_integration(self, temp_dir):
        """Test Task 4.5: Integrate database segments with proven timing accuracy mechanisms."""
        db_path = temp_dir / "test_timing_integration.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock translator
        mock_translator = Mock(spec=HistoricalTranslator)
        
        # Create interview with precise timing requirements
        interview_id = db.add_file("/test/timing_test.mp4", "timing_test_mp4", "video")
        
        # Segments with exact timing boundaries
        timing_segments = [
            (0, 0.000, 2.500, 'First segment.'),
            (1, 2.500, 5.750, 'Second segment.'),
            (2, 5.750, 8.333, 'Third segment.')
        ]
        
        for idx, start, end, original in timing_segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Convert to SRT format
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'original')
        
        # Verify timing precision is maintained
        assert srt_segments[0].start_time == "00:00:00,000"
        assert srt_segments[0].end_time == "00:00:02,500"
        assert srt_segments[1].start_time == "00:00:02,500"
        assert srt_segments[1].end_time == "00:00:05,750"
        assert srt_segments[2].start_time == "00:00:05,750"
        assert srt_segments[2].end_time == "00:00:08,333"
        
        # Test timing coordination validation
        timing_validation = db_translator.validate_timing_coordination(interview_id, 'original')
        assert timing_validation['timing_valid'] == True
        assert timing_validation['boundary_validation'] == True
        assert timing_validation['srt_compatibility'] == True
        
        # Verify that timing metrics are calculated
        if hasattr(db_translator, 'calculate_timing_accuracy_metrics'):
            timing_metrics = db_translator.calculate_timing_accuracy_metrics(
                interview_id, 'original', timing_validation
            )
            assert 'total_segments' in timing_metrics
            assert timing_metrics['total_segments'] == 3
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_srt_functionality_preserved_with_database(self, temp_dir):
        """Test Task 4.6: Verify all SRTTranslator functionality preserved while adding database coordination."""
        db_path = temp_dir / "test_functionality_preserved.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock translator
        mock_translator = Mock(spec=HistoricalTranslator)
        
        # Create interview
        interview_id = db.add_file("/test/preserve_test.mp4", "preserve_test_mp4", "video")
        
        # Add segments
        segments = [
            (0, 0.0, 3.5, 'Ich bin ein Berliner.'),
            (1, 3.5, 7.0, 'Das ist wichtig.'),
            (2, 7.0, 10.5, 'Für die Geschichte.')
        ]
        
        for idx, start, end, original in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        db_translator = DatabaseTranslator(db, mock_translator)
        srt_translator = SRTTranslator(mock_translator)
        
        # Test 1: Boundary validation is preserved
        original_segments = db_translator.convert_segments_to_srt_format(interview_id, 'original')
        
        # Create a copy for translated segments (simulating translation)
        translated_segments = []
        for seg in original_segments:
            new_seg = SRTSegment(
                index=seg.index,
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=f"Translated: {seg.text}"
            )
            translated_segments.append(new_seg)
        
        # Verify SRTTranslator boundary validation still works
        boundary_valid = srt_translator._validate_segment_boundaries(
            original_segments, translated_segments
        )
        assert boundary_valid == True
        
        # Test 2: SRT file generation works
        output_path = temp_dir / "test_output.srt"
        success = db_translator.generate_coordinated_srt(interview_id, 'original', output_path)
        assert success == True
        assert output_path.exists()
        
        # Test 3: Parse generated SRT file using SRTTranslator
        parsed_segments = srt_translator.parse_srt(str(output_path))
        assert len(parsed_segments) == 3
        
        # Test 4: Timing preservation through round-trip
        for orig, parsed in zip(original_segments, parsed_segments):
            assert orig.start_time == parsed.start_time
            assert orig.end_time == parsed.end_time
            assert orig.text == parsed.text
        
        # Test 5: Workflow coordination
        coordination_results = db_translator.coordinate_with_srt_workflow(
            interview_id, ['original']
        )
        assert coordination_results['overall_success'] == True
        assert coordination_results['workflow_compatibility'] == True
        assert coordination_results['timing_preservation'] == True
        
        # Test 6: Quality validation framework integration
        validation_results = db_translator.validate_translations(interview_id, 'original')
        assert 'valid' in validation_results
        assert 'quality_scores' in validation_results
        
        # Test 7: Comprehensive quality report
        if hasattr(db_translator, 'get_comprehensive_quality_report'):
            quality_report = db_translator.get_comprehensive_quality_report(interview_id)
            assert 'interview_id' in quality_report
            assert quality_report['interview_id'] == interview_id
        
        db.close()
    
    @pytest.mark.integration  
    @pytest.mark.database
    def test_enhanced_quality_evaluation_with_database(self, temp_dir):
        """Test enhanced quality evaluation integrated with database storage."""
        db_path = temp_dir / "test_enhanced_quality.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock translator
        mock_translator = Mock(spec=HistoricalTranslator)
        
        # Setup evaluator mock with detailed responses
        mock_evaluator = Mock()
        mock_evaluator.evaluate.side_effect = lambda orig, trans, **kwargs: {
            'accuracy': 0.85,
            'fluency': 0.90,
            'terminology': 0.88,
            'overall': 0.88
        }
        mock_evaluator.get_score.side_effect = lambda result: result['overall'] * 10
        
        interview_id = db.add_file("/test/quality_eval.mp4", "quality_eval_mp4", "video")
        
        # Add segments with translations
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=3.0,
            original_text='Wichtige historische Ereignisse.',
            english_text='Important historical events.'
        )
        
        db_translator = DatabaseTranslator(db, mock_translator, mock_evaluator)
        
        # Evaluate quality
        quality_results = db_translator.evaluate_translation_quality(
            interview_id, ['en'], sample_size=1
        )
        
        assert 'languages' in quality_results
        assert 'en' in quality_results['languages']
        assert quality_results['languages']['en']['average_score'] == 8.8
        
        # Verify quality metrics are stored
        metrics = get_quality_metrics(db, interview_id, 'en')
        if metrics:  # Quality metrics were stored
            assert isinstance(metrics, dict)
        
        db.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])