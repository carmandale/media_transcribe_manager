#!/usr/bin/env python3
"""
Tests for database-coordinated translation functionality.
Extends batch language detection tests (83% coverage) for segment coordination.
"""

import pytest
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from scribe.database import Database
from scribe.batch_language_detection import detect_languages_for_segments, detect_languages_batch
from scribe.database_translation import DatabaseTranslator, translate_interview_from_database
from scribe.translate import HistoricalTranslator


class TestDatabaseTranslationCoordination:
    """Test database integration with translation pipeline."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_segments_for_translation(self, temp_dir):
        """Test fetching segments that need translation."""
        db_path = temp_dir / "test_translation.db"
        db = Database(db_path)
        
        # Ensure migration is run
        db._migrate_to_subtitle_segments()
        
        # Add test interview
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        # Add segments with partial translations
        segments = [
            # Segment with no translations
            {
                'interview_id': interview_id,
                'segment_index': 0,
                'start_time': 0.0,
                'end_time': 2.5,
                'original_text': 'Ich wurde geboren.',
                'german_text': None,
                'english_text': None,
                'hebrew_text': None
            },
            # Segment with English translation only
            {
                'interview_id': interview_id,
                'segment_index': 1,
                'start_time': 3.0,
                'end_time': 5.5,
                'original_text': 'In Deutschland.',
                'german_text': None,
                'english_text': 'In Germany.',
                'hebrew_text': None
            },
            # Segment with all translations
            {
                'interview_id': interview_id,
                'segment_index': 2,
                'start_time': 6.0,
                'end_time': 8.5,
                'original_text': 'Neunzehn dreißig.',
                'german_text': 'Neunzehn dreißig.',
                'english_text': 'Nineteen thirty.',
                'hebrew_text': 'תשע עשרה שלושים.'
            }
        ]
        
        # Add segments to database
        for seg in segments:
            db.add_subtitle_segment(
                interview_id=seg['interview_id'],
                segment_index=seg['segment_index'],
                start_time=seg['start_time'],
                end_time=seg['end_time'],
                original_text=seg['original_text'],
                german_text=seg.get('german_text'),
                english_text=seg.get('english_text'),
                hebrew_text=seg.get('hebrew_text')
            )
        
        # Test fetching segments needing English translation
        english_needed = db.get_subtitle_segments(interview_id)
        segments_needing_english = [s for s in english_needed if not s.get('english_text')]
        assert len(segments_needing_english) == 1
        assert segments_needing_english[0]['original_text'] == 'Ich wurde geboren.'
        
        # Test fetching segments needing Hebrew translation
        hebrew_needed = [s for s in english_needed if not s.get('hebrew_text')]
        assert len(hebrew_needed) == 2
        
        db.close()
    
    @pytest.mark.unit
    def test_batch_language_detection_for_database_segments(self):
        """Test batch language detection works with database segment format."""
        # Create mock OpenAI client
        mock_openai = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: German
3: English
4: Hebrew"""))]
        mock_openai.chat.completions.create.return_value = mock_response
        
        # Test segments in database format (dict instead of SRTSegment)
        segments = [
            {'id': 1, 'original_text': 'Ich wurde geboren in Berlin.'},
            {'id': 2, 'original_text': 'Das war neunzehn dreißig.'},
            {'id': 3, 'original_text': 'My family moved away.'},
            {'id': 4, 'original_text': 'שלום, מה שלומך?'}  # Hebrew: Hello, how are you?
        ]
        
        # Extract texts for detection
        texts = [seg['original_text'] for seg in segments]
        
        # Run batch detection
        detected_languages = detect_languages_batch(texts, mock_openai)
        
        # Verify results
        assert detected_languages[0] == 'de'  # German
        assert detected_languages[1] == 'de'  # German
        assert detected_languages[2] == 'en'  # English
        assert detected_languages[3] == 'he'  # Hebrew
        
        # Verify API was called correctly
        mock_openai.chat.completions.create.assert_called_once()
        call_args = mock_openai.chat.completions.create.call_args
        assert call_args[1]['model'] == 'gpt-4o-mini'
        assert 'Ich wurde geboren' in call_args[1]['messages'][0]['content']
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_segment_language_coordination_with_database(self, temp_dir):
        """Test coordinating language detection with database storage."""
        db_path = temp_dir / "test_lang_coord.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Add test interview
        interview_id = db.add_file("/test/multilang.mp4", "multilang_mp4", "video")
        
        # Add segments in multiple languages
        test_segments = [
            ('Guten Tag, ich bin Johann.', 'de'),
            ('My name is John.', 'en'),
            ('אני גר בירושלים.', 'he'),  # I live in Jerusalem
            ('Das ist sehr wichtig.', 'de'),
            ('Thank you very much.', 'en')
        ]
        
        # Add to database
        for i, (text, expected_lang) in enumerate(test_segments):
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=i,
                start_time=i * 3.0,
                end_time=(i + 1) * 3.0,
                original_text=text
            )
        
        # Mock language detection
        mock_openai = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: Hebrew
4: German
5: English"""))]
        mock_openai.chat.completions.create.return_value = mock_response
        
        # Get segments from database
        segments = db.get_subtitle_segments(interview_id)
        texts = [seg['original_text'] for seg in segments]
        
        # Detect languages
        detected = detect_languages_batch(texts, mock_openai)
        
        # Verify coordination
        assert len(detected) == 5
        assert detected[0] == 'de'
        assert detected[1] == 'en'
        assert detected[2] == 'he'
        assert detected[3] == 'de'
        assert detected[4] == 'en'
        
        # Store detected languages back to database (future enhancement)
        # This would be part of the translation coordinator
        
        db.close()
    
    @pytest.mark.unit
    def test_batch_size_handling_for_large_interviews(self):
        """Test batch language detection handles large interviews correctly."""
        mock_openai = Mock()
        
        # Create 150 segments (will require multiple batches with size 50)
        large_segment_list = []
        for i in range(150):
            if i % 3 == 0:
                text = f"Das ist Segment nummer {i}."
                lang = "German"
            elif i % 3 == 1:
                text = f"This is segment number {i}."
                lang = "English"
            else:
                text = f"זה קטע מספר {i}."  # This is segment number X
                lang = "Hebrew"
            large_segment_list.append({'text': text, 'expected_lang': lang})
        
        # Mock responses for each batch
        def create_batch_response(start_idx, batch_size):
            lines = []
            for i in range(min(batch_size, 150 - start_idx)):
                actual_idx = start_idx + i
                lang = large_segment_list[actual_idx]['expected_lang']
                lines.append(f"{i+1}: {lang}")
            return "\n".join(lines)
        
        # Configure mock to return appropriate response for each batch
        call_count = 0
        def mock_create(*args, **kwargs):
            nonlocal call_count
            start_idx = call_count * 50
            response_text = create_batch_response(start_idx, 50)
            call_count += 1
            return Mock(choices=[Mock(message=Mock(content=response_text))])
        
        mock_openai.chat.completions.create.side_effect = mock_create
        
        # Process in batches
        all_texts = [seg['text'] for seg in large_segment_list]
        all_results = []
        
        # Process in batches like the real system
        batch_size = 50
        for i in range(0, len(all_texts), batch_size):
            batch = all_texts[i:i + batch_size]
            results = detect_languages_batch(batch, mock_openai)
            all_results.extend(results)
        
        # Verify all segments were processed
        assert len(all_results) == 150
        
        # Verify language detection pattern
        for i, (result, segment) in enumerate(zip(all_results, large_segment_list)):
            expected = {'German': 'de', 'English': 'en', 'Hebrew': 'he'}[segment['expected_lang']]
            assert result == expected, f"Segment {i} failed: expected {expected}, got {result}"
        
        # Verify correct number of API calls
        assert mock_openai.chat.completions.create.call_count == 3  # 150 segments / 50 per batch
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_language_detection_preserves_segment_order(self, temp_dir):
        """Test that batch processing maintains correct segment order."""
        db_path = temp_dir / "test_order.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        interview_id = db.add_file("/test/ordered.mp4", "ordered_mp4", "video")
        
        # Add segments with specific order
        ordered_texts = [
            "First segment in English.",
            "Zweiter Abschnitt auf Deutsch.",
            "Third segment in English.",
            "Vierter Abschnitt auf Deutsch.",
            "Fifth and final segment."
        ]
        
        for i, text in enumerate(ordered_texts):
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=i,
                start_time=i * 3.0,
                end_time=(i + 1) * 3.0,
                original_text=text
            )
        
        # Get segments from database (should maintain order)
        segments = db.get_subtitle_segments(interview_id)
        
        # Verify order is preserved
        for i, seg in enumerate(segments):
            assert seg['segment_index'] == i
            assert seg['original_text'] == ordered_texts[i]
        
        db.close()
    
    @pytest.mark.unit
    def test_non_verbal_segment_handling(self):
        """Test that non-verbal segments are handled correctly."""
        mock_openai = Mock()
        mock_response = Mock()
        # GPT should recognize non-verbal content
        mock_response.choices = [Mock(message=Mock(content="""1: English
2: English
3: English
4: German"""))]
        mock_openai.chat.completions.create.return_value = mock_response
        
        # Mix of verbal and non-verbal content
        segments = [
            {'text': '♪♪'},  # Music notation
            {'text': '[inaudible]'},  # Inaudible marker
            {'text': '...'},  # Pause
            {'text': 'Das ist gut.'}  # Actual German text
        ]
        
        texts = [seg['text'] for seg in segments]
        results = detect_languages_batch(texts, mock_openai)
        
        # Non-verbal segments might be detected as English (default) or None
        # The important thing is they're processed without errors
        assert len(results) == 4
        assert results[3] == 'de'  # Real German text should be detected


class TestDatabaseTranslator:
    """Test the DatabaseTranslator class."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_database_translator_initialization(self, temp_dir):
        """Test DatabaseTranslator initialization."""
        db_path = temp_dir / "test_init.db"
        db = Database(db_path)
        
        # Initialize with default translator
        db_translator = DatabaseTranslator(db)
        assert db_translator.db == db
        assert isinstance(db_translator.translator, HistoricalTranslator)
        
        # Initialize with custom translator
        custom_translator = HistoricalTranslator({'openai_model': 'gpt-4'})
        db_translator2 = DatabaseTranslator(db, custom_translator)
        assert db_translator2.translator == custom_translator
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_translate_interview_basic(self, temp_dir):
        """Test basic interview translation flow."""
        db_path = temp_dir / "test_translate.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.openai_client = None  # Skip language detection
        mock_translator.is_same_language.return_value = False
        mock_translator.batch_translate.return_value = [
            'I was born.',
            'In Germany.',
            'Nineteen thirty.'
        ]
        
        # Create test interview with segments
        interview_id = db.add_file("/test/interview.mp4", "interview_mp4", "video")
        
        segments = [
            (0, 0.0, 2.5, 'Ich wurde geboren.'),
            (1, 3.0, 5.5, 'In Deutschland.'),
            (2, 6.0, 8.5, 'Neunzehn dreißig.')
        ]
        
        for idx, start, end, text in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Create translator and translate
        db_translator = DatabaseTranslator(db, mock_translator)
        results = db_translator.translate_interview(interview_id, 'en')
        
        # Verify results
        assert results['total_segments'] == 3
        assert results['translated'] == 3
        assert results['skipped'] == 0
        assert results['failed'] == 0
        assert len(results['errors']) == 0
        
        # Verify translations were saved
        segments_after = db.get_subtitle_segments(interview_id)
        assert segments_after[0]['english_text'] == 'I was born.'
        assert segments_after[1]['english_text'] == 'In Germany.'
        assert segments_after[2]['english_text'] == 'Nineteen thirty.'
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_language_detection_integration(self, temp_dir):
        """Test translation with language detection."""
        db_path = temp_dir / "test_lang_detect.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock OpenAI client for language detection
        mock_openai = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: English
3: German"""))]
        mock_openai.chat.completions.create.return_value = mock_response
        
        # Mock translator
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.openai_client = mock_openai
        mock_translator.is_same_language.side_effect = lambda a, b: a == b
        mock_translator.batch_translate.return_value = ['In Germany.', 'Nineteen thirty.']
        
        # Create mixed language interview
        interview_id = db.add_file("/test/mixed.mp4", "mixed_mp4", "video")
        
        segments = [
            (0, 0.0, 2.5, 'In Deutschland.'),  # German - should translate
            (1, 3.0, 5.5, 'My name is John.'),  # English - should skip
            (2, 6.0, 8.5, 'Neunzehn dreißig.')  # German - should translate
        ]
        
        for idx, start, end, text in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Translate to English
        db_translator = DatabaseTranslator(db, mock_translator)
        results = db_translator.translate_interview(interview_id, 'en', detect_source_language=True)
        
        # Verify results
        assert results['translated'] == 2  # German segments
        assert results['skipped'] == 1     # English segment
        assert results['failed'] == 0
        
        # Verify language detection was called
        mock_openai.chat.completions.create.assert_called_once()
        
        db.close()
    
    @pytest.mark.unit
    def test_non_verbal_segment_handling(self):
        """Test that non-verbal segments are skipped."""
        db = Mock()
        db.get_segments_for_translation.return_value = [
            {'id': 1, 'original_text': '♪♪'},
            {'id': 2, 'original_text': '[inaudible]'},
            {'id': 3, 'original_text': '...'},
            {'id': 4, 'original_text': 'Hello world'}
        ]
        db.batch_update_segment_translations.return_value = True
        
        mock_translator = Mock()
        mock_translator.openai_client = None
        mock_translator.is_same_language.return_value = False
        mock_translator.batch_translate.return_value = ['Hallo Welt']
        
        db_translator = DatabaseTranslator(db, mock_translator)
        results = db_translator.translate_interview('test_id', 'de')
        
        assert results['skipped'] == 3  # Three non-verbal segments
        assert results['translated'] == 1  # One real segment
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_hebrew_translation_validation(self, temp_dir):
        """Test Hebrew translation validation."""
        db_path = temp_dir / "test_hebrew.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator that returns Hebrew
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.openai_client = None
        mock_translator.is_same_language.return_value = False
        mock_translator.batch_translate.return_value = ['שלום עולם']  # Hello world in Hebrew
        mock_translator.validate_hebrew_translation.return_value = True
        
        # Create interview
        interview_id = db.add_file("/test/hebrew.mp4", "hebrew_mp4", "video")
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=2.0,
            original_text='Hello world',
            hebrew_text='שלום עולם'
        )
        
        # Validate
        db_translator = DatabaseTranslator(db, mock_translator)
        validation = db_translator.validate_translations(interview_id, 'he')
        
        assert validation['valid'] == True
        assert validation['validated'] == 1
        assert len(validation['issues']) == 0
        
        db.close()
    
    @pytest.mark.unit
    def test_translation_error_handling(self):
        """Test error handling during translation."""
        db = Mock()
        db.get_segments_for_translation.return_value = [
            {'id': 1, 'original_text': 'Test text'}
        ]
        
        # Mock translator that raises error
        mock_translator = Mock()
        mock_translator.openai_client = None
        mock_translator.is_same_language.return_value = False
        mock_translator.batch_translate.side_effect = Exception("API error")
        
        db_translator = DatabaseTranslator(db, mock_translator)
        results = db_translator.translate_interview('test_id', 'de')
        
        assert results['failed'] == 1
        assert results['translated'] == 0
        assert 'API error' in results['errors'][0]
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_translation_status(self, temp_dir):
        """Test getting translation status."""
        db_path = temp_dir / "test_status.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview with partial translations
        interview_id = db.add_file("/test/status.mp4", "status_mp4", "video")
        
        # Add segments with varying translation states
        db.add_subtitle_segment(
            interview_id, 0, 0.0, 2.0, 'Text 1',
            german_text='Text 1 DE', english_text='Text 1 EN'  # Missing Hebrew
        )
        db.add_subtitle_segment(
            interview_id, 1, 2.0, 4.0, 'Text 2',
            german_text='Text 2 DE'  # Missing English and Hebrew
        )
        db.add_subtitle_segment(
            interview_id, 2, 4.0, 6.0, 'Text 3'  # No translations
        )
        
        db_translator = DatabaseTranslator(db)
        status = db_translator.get_translation_status(interview_id)
        
        assert status['total'] == 3
        assert status['de']['translated'] == 2
        assert status['de']['pending'] == 1
        assert status['en']['translated'] == 1
        assert status['en']['pending'] == 2
        assert status['he']['translated'] == 0
        assert status['he']['pending'] == 3
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_translate_interview_from_database_integration(self, temp_dir):
        """Test the pipeline integration function."""
        db_path = temp_dir / "test_pipeline.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.openai_client = None
        mock_translator.is_same_language.return_value = False
        mock_translator.batch_translate.side_effect = [
            ['Hello'],  # English translation
            ['Hallo'],  # German translation
            ['שלום']    # Hebrew translation
        ]
        
        # Create interview
        interview_id = db.add_file("/test/pipeline.mp4", "pipeline_mp4", "video")
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=2.0,
            original_text='Bonjour'  # French
        )
        
        # Translate using pipeline function
        results = translate_interview_from_database(
            db, interview_id, 
            target_languages=['en', 'de', 'he'],
            translator=mock_translator
        )
        
        # Verify all languages were processed
        assert 'en' in results
        assert 'de' in results
        assert 'he' in results
        
        assert results['en']['translated'] == 1
        assert results['de']['translated'] == 1
        assert results['he']['translated'] == 1
        
        db.close()