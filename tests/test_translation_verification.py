#!/usr/bin/env python3
"""
Comprehensive verification tests for Task 3.6.

This test suite verifies that enhanced database translation functionality
preserves all existing functionality and quality while adding new capabilities.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil

from scribe.database import Database
from scribe.database_translation import (
    DatabaseTranslator, 
    translate_interview_from_database,
    coordinate_translation_timing,
    validate_interview_translation_quality
)
from scribe.translate import HistoricalTranslator
from scribe.srt_translator import SRTTranslator, SRTSegment
from scribe.evaluate import HistoricalEvaluator


class TestEnhancedTranslationPreservation:
    """Verify that enhanced translation preserves all existing functionality (Task 3.6)."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_existing_translation_workflow_preserved(self, temp_dir):
        """Verify that existing translation workflow continues to work unchanged."""
        db_path = temp_dir / "test_preservation.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator with existing behavior
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.batch_translate.return_value = ['I was born.', 'In Germany.', 'Nineteen thirty.']
        mock_translator.is_same_language.return_value = False
        mock_translator.validate_hebrew_translation.return_value = True
        mock_translator.openai_client = None  # Simulate no OpenAI client
        
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Create interview with segments
        interview_id = db.add_file("/test/preservation.mp4", "preservation_mp4", "video")
        
        segments = [
            (0, 0.0, 3.0, 'Ich wurde geboren.'),
            (1, 3.0, 6.0, 'In Deutschland.'),
            (2, 6.0, 9.0, 'Neunzehnhundertdreißig.')
        ]
        
        for idx, start, end, original in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        # Test basic translation functionality (existing workflow)
        results = db_translator.translate_interview(interview_id, 'en', batch_size=50)
        
        # Verify existing functionality preserved
        assert results['total_segments'] == 3
        assert results['translated'] == 3
        assert results['skipped'] == 0
        assert results['failed'] == 0
        
        # Verify translations were saved
        segments_after = db.get_subtitle_segments(interview_id)
        assert segments_after[0]['english_text'] == 'I was born.'
        assert segments_after[1]['english_text'] == 'In Germany.'
        assert segments_after[2]['english_text'] == 'Nineteen thirty.'
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_basic_validation_backward_compatible(self, temp_dir):
        """Verify that basic validation (enhanced_quality_check=False) preserves existing behavior."""
        db_path = temp_dir / "test_basic_validation.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator
        mock_translator = Mock()
        mock_translator.validate_hebrew_translation.return_value = True
        
        # No evaluator for basic validation
        db_translator = DatabaseTranslator(db, mock_translator, evaluator=None)
        
        # Create interview
        interview_id = db.add_file("/test/basic.mp4", "basic_mp4", "video")
        
        # Add segments with translations
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=3.0,
            original_text='Test original.',
            english_text='Test English.',
            hebrew_text='טסט עברית.'
        )
        
        # Test basic validation (should work without evaluator)
        validation_results = db_translator.validate_translations(
            interview_id, 
            'he', 
            enhanced_quality_check=False
        )
        
        # Verify basic validation works as before
        assert validation_results['valid'] == True
        assert validation_results['validated'] == 1
        assert validation_results['issues'] == []
        assert 'quality_scores' in validation_results  # New field, but doesn't affect basic validation
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database  
    def test_timing_coordination_preserved(self, temp_dir):
        """Verify that timing coordination from Task 3.4 still works correctly."""
        db_path = temp_dir / "test_timing_preserved.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview with precise timing
        interview_id = db.add_file("/test/timing.mp4", "timing_mp4", "video")
        
        segments = [
            (0, 0.0, 2.5, 'First segment.', 'Erstes Segment.', 'קטע ראשון.'),
            (1, 2.5, 5.125, 'Second segment.', 'Zweites Segment.', 'קטע שני.'),
            (2, 5.125, 8.75, 'Third segment.', 'Drittes Segment.', 'קטע שלישי.')
        ]
        
        for idx, start, end, original, german, hebrew in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                german_text=german,
                hebrew_text=hebrew
            )
        
        # Test timing coordination (from Task 3.4)
        coordination_results = coordinate_translation_timing(
            db,
            interview_id,
            target_languages=['de', 'he'],
            validate_timing=True
        )
        
        # Verify timing coordination still works
        assert coordination_results['overall_success'] == True
        assert coordination_results['timing_coordination_active'] == True
        
        # Check each language
        for lang in ['de', 'he']:
            lang_results = coordination_results['languages'][lang]
            assert lang_results['timing_valid'] == True
            assert lang_results['boundary_validation'] == True
            assert lang_results['segment_count'] == 3
            assert lang_results['srt_conversion_success'] == True
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_srt_translator_integration_preserved(self, temp_dir):
        """Verify that SRTTranslator integration continues to work."""
        db_path = temp_dir / "test_srt_integration.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock translator
        mock_translator = Mock()
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Create interview
        interview_id = db.add_file("/test/srt.mp4", "srt_mp4", "video")
        
        # Add segments
        segments = [
            (0, 0.0, 2.0, 'First.'),
            (1, 2.0, 4.0, 'Second.'),
            (2, 4.0, 6.0, 'Third.')
        ]
        
        for idx, start, end, text in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Test SRT conversion
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'original')
        
        # Verify SRT segments match expected format
        assert len(srt_segments) == 3
        assert all(isinstance(seg, SRTSegment) for seg in srt_segments)
        
        # Verify timing is exact
        assert srt_segments[0].start_time == "00:00:00,000"
        assert srt_segments[0].end_time == "00:00:02,000"
        assert srt_segments[1].start_time == "00:00:02,000"
        assert srt_segments[1].end_time == "00:00:04,000"
        
        # Verify indices are 1-based (SRT standard)
        assert srt_segments[0].index == 1
        assert srt_segments[1].index == 2
        assert srt_segments[2].index == 3
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_hebrew_validation_preserved(self, temp_dir):
        """Verify that Hebrew validation continues to work as before."""
        db_path = temp_dir / "test_hebrew_preserved.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator with Hebrew validation
        mock_translator = Mock()
        
        # Mock the validation behavior
        def mock_hebrew_validator(text):
            # Return True only if text contains Hebrew characters
            return any('\u0590' <= c <= '\u05FF' for c in text)
        
        mock_translator.validate_hebrew_translation.side_effect = mock_hebrew_validator
        
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Create interview
        interview_id = db.add_file("/test/hebrew.mp4", "hebrew_mp4", "video")
        
        # Add valid Hebrew segment
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=3.0,
            original_text='Test original.',
            hebrew_text='בדיקה עברית.'  # Valid Hebrew
        )
        
        # Add invalid Hebrew segment
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=1,
            start_time=3.0,
            end_time=6.0,
            original_text='Another test.',
            hebrew_text='Not Hebrew text'  # Invalid - no Hebrew characters
        )
        
        # Test validation
        validation_results = db_translator.validate_translations(interview_id, 'he')
        
        # Should fail due to invalid Hebrew
        assert validation_results['valid'] == False
        assert validation_results['validated'] == 2
        assert len(validation_results['issues']) >= 1
        assert "Segment 1 has invalid Hebrew translation" in validation_results['issues'][0]
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_pipeline_functions_preserved(self, temp_dir):
        """Verify that pipeline integration functions work as before."""
        db_path = temp_dir / "test_pipeline_preserved.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator
        mock_translator = Mock()
        mock_translator.batch_translate.return_value = ['Translated text.']
        mock_translator.is_same_language.return_value = False
        mock_translator.validate_hebrew_translation.return_value = True
        mock_translator.openai_client = None
        
        # Create interview
        interview_id = db.add_file("/test/pipeline.mp4", "pipeline_mp4", "video")
        
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=3.0,
            original_text='Original text.'
        )
        
        # Test existing pipeline function
        results = translate_interview_from_database(
            db,
            interview_id,
            target_languages=['en'],
            translator=mock_translator
        )
        
        # Verify pipeline function works
        assert 'en' in results
        assert results['en']['translated'] == 1
        assert results['en']['failed'] == 0
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_enhanced_validation_additive_only(self, temp_dir):
        """Verify that enhanced validation is additive and doesn't break existing validation."""
        db_path = temp_dir / "test_enhanced_additive.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator and evaluator
        mock_translator = Mock()
        mock_translator.validate_hebrew_translation.return_value = True
        
        mock_evaluator = Mock()
        mock_evaluator.evaluate.return_value = {'scores': {'composite_score': 8.5}}
        mock_evaluator.get_score.return_value = 8.5
        
        db_translator = DatabaseTranslator(db, mock_translator, mock_evaluator)
        
        # Create interview
        interview_id = db.add_file("/test/enhanced.mp4", "enhanced_mp4", "video")
        
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=3.0,
            original_text='Test.',
            hebrew_text='בדיקה.'
        )
        
        # Test both basic and enhanced validation
        basic_results = db_translator.validate_translations(interview_id, 'he', enhanced_quality_check=False)
        enhanced_results = db_translator.validate_translations(interview_id, 'he', enhanced_quality_check=True)
        
        # Both should pass
        assert basic_results['valid'] == True
        assert enhanced_results['valid'] == True
        
        # Enhanced should have additional quality scores
        assert 'quality_scores' in enhanced_results
        assert len(enhanced_results['quality_scores']) > len(basic_results['quality_scores'])
        
        db.close()
    
    @pytest.mark.unit
    def test_translation_quality_metrics_preserved(self, temp_dir):
        """Verify that existing translation quality patterns are maintained."""
        db_path = temp_dir / "test_quality_preserved.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock components
        mock_translator = Mock()
        mock_translator.batch_translate.return_value = [
            'I was born in nineteen thirty.',
            'In the Wehrmacht.'
        ]
        mock_translator.is_same_language.return_value = False
        mock_translator.openai_client = Mock()
        
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Create interview
        interview_id = db.add_file("/test/quality.mp4", "quality_mp4", "video")
        
        # Historical content that should preserve quality
        segments = [
            (0, 0.0, 4.0, 'Ich wurde geboren neunzehnhundertdreißig.'),
            (1, 4.0, 8.0, 'In die Wehrmacht.')
        ]
        
        for idx, start, end, original in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        # Translate
        results = db_translator.translate_interview(interview_id, 'en')
        
        # Verify quality patterns preserved
        segments_after = db.get_subtitle_segments(interview_id)
        
        # Check that historical patterns are preserved (e.g., "nineteen thirty" not "1930")
        assert 'nineteen thirty' in segments_after[0]['english_text'].lower()
        assert 'wehrmacht' in segments_after[1]['english_text'].lower()
        
        db.close()


class TestQualityValidationCompatibility:
    """Verify quality validation framework compatibility."""
    
    @pytest.mark.unit
    def test_existing_evaluator_integration(self):
        """Verify that existing HistoricalEvaluator integrates properly."""
        # Mock database and translator
        mock_db = Mock()
        mock_translator = Mock()
        mock_translator.openai_client = Mock()
        
        # Real evaluator (mocked for testing)
        mock_evaluator = Mock(spec=HistoricalEvaluator)
        mock_evaluator.evaluate.return_value = {
            'scores': {
                'content_accuracy': 8.5,
                'speech_pattern_fidelity': 7.8,
                'cultural_context': 8.2,
                'overall_historical_reliability': 8.3
            },
            'composite_score': 8.2
        }
        mock_evaluator.get_score.return_value = 8.2
        
        db_translator = DatabaseTranslator(mock_db, mock_translator, mock_evaluator)
        
        # Mock database response
        mock_db.get_subtitle_segments.return_value = [
            {
                'segment_index': 0,
                'original_text': 'Ich wurde geboren.',
                'english_text': 'I was born.',
                'german_text': 'Ich wurde geboren.',
                'hebrew_text': 'נולדתי.'
            }
        ]
        
        # Test quality evaluation
        quality_results = db_translator.evaluate_translation_quality('test_id', ['en'])
        
        # Verify evaluator was called with correct parameters
        mock_evaluator.evaluate.assert_called_with(
            'Ich wurde geboren.',
            'I was born.',
            language='en',
            enhanced=True
        )
        
        # Verify results structure
        assert quality_results['interview_id'] == 'test_id'
        assert 'en' in quality_results['languages']
        assert quality_results['languages']['en']['average_score'] == 8.2