#!/usr/bin/env python3
"""
Integration test for enhanced translation system.

This test verifies that all enhancements from Tasks 3.1-3.5 work together
correctly while preserving all existing functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
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
from scribe.srt_translator import SRTTranslator
from scribe.evaluate import HistoricalEvaluator


class TestEnhancedTranslationIntegration:
    """Full integration test for enhanced translation system (Task 3.6)."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_full_enhanced_translation_pipeline(self, temp_dir):
        """Test the complete enhanced translation pipeline end-to-end."""
        db_path = temp_dir / "test_full_pipeline.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create realistic mock components
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.openai_client = Mock()  # Simulate OpenAI available
        
        # Mock batch translation with realistic responses
        def mock_batch_translate(texts, target_lang, source_lang=None):
            translations = []
            for text in texts:
                if target_lang == 'en':
                    if 'geboren' in text.lower():
                        translations.append('I was born in nineteen thirty.')
                    elif 'wehrmacht' in text.lower():
                        translations.append('In the Wehrmacht.')
                    elif 'krieg' in text.lower():
                        translations.append('During the war.')
                    else:
                        translations.append(f'English: {text}')
                elif target_lang == 'he':
                    if 'geboren' in text.lower():
                        translations.append('נולדתי בשנת אלף תשע מאות ושלושים.')
                    elif 'wehrmacht' in text.lower():
                        translations.append('בוורמאכט.')
                    elif 'krieg' in text.lower():
                        translations.append('במהלך המלחמה.')
                    else:
                        translations.append(f'עברית: {text}')
                else:
                    translations.append(f'{target_lang}: {text}')
            return translations
        
        mock_translator.batch_translate.side_effect = mock_batch_translate
        mock_translator.is_same_language.return_value = False
        mock_translator.validate_hebrew_translation.return_value = True
        
        # Mock evaluator with realistic quality scores
        mock_evaluator = Mock(spec=HistoricalEvaluator)
        
        def mock_evaluate(original, translation, language='auto', enhanced=False):
            # Simulate quality evaluation
            score = 8.5
            if 'wehrmacht' in translation.lower():
                score = 9.0  # Higher score for preserved historical terms
            elif language == 'he' and any('\u0590' <= c <= '\u05FF' for c in translation):
                score = 8.7  # Good Hebrew translation
                
            return {
                'scores': {
                    'content_accuracy': score,
                    'speech_pattern_fidelity': score - 0.5,
                    'cultural_context': score - 0.3,
                    'overall_historical_reliability': score
                },
                'composite_score': score,
                'strengths': ['Accurate historical content', 'Proper term preservation'],
                'issues': [],
                'suitability': 'Excellent for historical research'
            }
        
        mock_evaluator.evaluate.side_effect = mock_evaluate
        mock_evaluator.get_score.side_effect = lambda result: result['composite_score']
        
        # Create interview with historical content
        interview_id = db.add_file("/test/wehrmacht_interview.mp4", "wehrmacht_interview_mp4", "video")
        
        # Add segments with historical testimony
        segments = [
            (0, 0.0, 5.0, 'Ich wurde geboren neunzehnhundertdreißig.'),
            (1, 5.0, 10.0, 'In die Wehrmacht.'),
            (2, 10.0, 15.0, 'Während des Krieges.')
        ]
        
        for idx, start, end, original in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original
            )
        
        # Step 1: Translate using enhanced database translation
        db_translator = DatabaseTranslator(db, mock_translator, mock_evaluator)
        
        # Translate to English and Hebrew
        en_results = db_translator.translate_interview(interview_id, 'en')
        he_results = db_translator.translate_interview(interview_id, 'he')
        
        # Verify translations completed
        assert en_results['translated'] == 3
        assert he_results['translated'] == 3
        
        # Step 2: Validate translations with enhanced quality check
        en_validation = db_translator.validate_translations(interview_id, 'en', enhanced_quality_check=True)
        he_validation = db_translator.validate_translations(interview_id, 'he', enhanced_quality_check=True)
        
        # Verify validations pass
        assert en_validation['valid'] == True
        assert he_validation['valid'] == True
        assert 'quality_scores' in en_validation
        assert 'quality_scores' in he_validation
        
        # Step 3: Verify timing coordination
        timing_results = coordinate_translation_timing(db, interview_id, ['en', 'he'])
        assert timing_results['overall_success'] == True
        assert timing_results['languages']['en']['timing_valid'] == True
        assert timing_results['languages']['he']['timing_valid'] == True
        
        # Step 4: Test SRT generation with coordinated timing
        srt_segments = db_translator.convert_segments_to_srt_format(interview_id, 'en')
        assert len(srt_segments) == 3
        assert srt_segments[0].start_time == "00:00:00,000"
        assert srt_segments[0].end_time == "00:00:05,000"
        assert srt_segments[0].text == 'I was born in nineteen thirty.'
        
        # Step 5: Test quality evaluation
        quality_results = db_translator.evaluate_translation_quality(interview_id, ['en', 'he'])
        assert quality_results['overall_quality'] > 8.0
        assert quality_results['languages']['en']['average_score'] >= 8.5
        assert quality_results['languages']['he']['average_score'] >= 8.5
        
        # Step 6: Verify historical content preservation
        segments_after = db.get_subtitle_segments(interview_id)
        
        # Check English preserves "nineteen thirty" not "1930"
        assert 'nineteen thirty' in segments_after[0]['english_text'].lower()
        
        # Check Wehrmacht is preserved
        assert 'wehrmacht' in segments_after[1]['english_text'].lower()
        
        # Check Hebrew has valid Hebrew characters
        assert any('\u0590' <= c <= '\u05FF' for c in segments_after[0]['hebrew_text'])
        
        # Step 7: Test pipeline integration function
        pipeline_validation = validate_interview_translation_quality(
            db,
            interview_id,
            target_languages=['en', 'he'],
            enhanced_validation=True,
            translator=mock_translator,
            evaluator=mock_evaluator
        )
        
        assert pipeline_validation['overall_valid'] == True
        assert pipeline_validation['validation_method'] == 'enhanced_database_validation_pipeline'
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_backward_compatibility_with_no_evaluator(self, temp_dir):
        """Verify system works without evaluator (backward compatibility)."""
        db_path = temp_dir / "test_backward_compat.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator without OpenAI (simulating basic setup)
        mock_translator = Mock()
        mock_translator.batch_translate.return_value = ['Translation 1', 'Translation 2']
        mock_translator.is_same_language.return_value = False
        mock_translator.validate_hebrew_translation.return_value = True
        mock_translator.openai_client = None  # No OpenAI available
        
        # Create translator without evaluator
        db_translator = DatabaseTranslator(db, mock_translator, evaluator=None)
        
        # Create interview
        interview_id = db.add_file("/test/basic.mp4", "basic_mp4", "video")
        
        segments = [
            (0, 0.0, 3.0, 'First segment.'),
            (1, 3.0, 6.0, 'Second segment.')
        ]
        
        for idx, start, end, text in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Should work without evaluator
        results = db_translator.translate_interview(interview_id, 'en')
        assert results['translated'] == 2
        
        # Basic validation should work
        validation = db_translator.validate_translations(interview_id, 'en', enhanced_quality_check=False)
        assert validation['valid'] == True
        
        # Enhanced validation should gracefully handle missing evaluator
        enhanced_validation = db_translator.validate_translations(interview_id, 'en', enhanced_quality_check=True)
        assert enhanced_validation['valid'] == True  # Should still pass basic validation
        
        # Quality evaluation should handle missing evaluator
        quality_results = db_translator.evaluate_translation_quality(interview_id, ['en'])
        assert quality_results['overall_quality'] == 0.0  # No evaluator, no scores
        assert quality_results['languages'] == {}  # No languages evaluated without evaluator
        
        db.close()


class TestEnhancementsSummary:
    """Summary verification of all enhancements from Tasks 3.1-3.5."""
    
    def test_all_enhancements_integrated(self):
        """Verify all task enhancements are properly integrated."""
        # Task 3.1: Batch language detection for segments
        from scribe.database_translation import DatabaseTranslator
        assert hasattr(DatabaseTranslator, '_translate_batch')
        
        # Task 3.2: Database segments with DeepL integration
        assert hasattr(DatabaseTranslator, 'translate_interview')
        
        # Task 3.3: Hebrew translation quality preservation
        assert hasattr(DatabaseTranslator, 'validate_translations')
        
        # Task 3.4: Timing coordination
        from scribe.database_translation import coordinate_translation_timing
        assert callable(coordinate_translation_timing)
        
        # Task 3.5: Enhanced quality validation
        assert hasattr(DatabaseTranslator, 'evaluate_translation_quality')
        assert hasattr(DatabaseTranslator, 'validate_translations')
        
        # All integration functions available
        from scribe.database_translation import (
            translate_interview_from_database,
            validate_interview_translation_quality
        )
        assert callable(translate_interview_from_database)
        assert callable(validate_interview_translation_quality)