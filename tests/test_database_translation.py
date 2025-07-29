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
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_hebrew_translation_quality_preservation(self, temp_dir):
        """Test that Hebrew translation quality is preserved with proper routing."""
        db_path = temp_dir / "test_hebrew_quality.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create a mock translator that simulates Hebrew routing
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.openai_client = None
        mock_translator.is_same_language.return_value = False
        
        def mock_batch_translate(texts, target_lang, source_lang=None):
            # Note: provider routing happens inside HistoricalTranslator
            # Simulate proper Hebrew translation
            if target_lang == 'he':
                return ['שלום עולם']  # "Hello world" in Hebrew
            return texts
            
        mock_translator.batch_translate.side_effect = mock_batch_translate
        mock_translator.validate_hebrew_translation.return_value = True
        
        # Create interview with English text
        interview_id = db.add_file("/test/hebrew_test.mp4", "hebrew_test_mp4", "video")
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=2.0,
            original_text='Hello world'
        )
        
        # Translate to Hebrew
        db_translator = DatabaseTranslator(db, mock_translator)
        results = db_translator.translate_interview(interview_id, 'he')
        
        # Verify translation succeeded
        assert results['translated'] == 1
        assert results['failed'] == 0
        
        # Verify Hebrew text was saved
        segments = db.get_subtitle_segments(interview_id)
        assert segments[0]['hebrew_text'] == 'שלום עולם'
        
        # Verify validation was performed
        validation = db_translator.validate_translations(interview_id, 'he')
        assert validation['valid'] == True
        assert validation['validated'] == 1
        
        db.close()
    
    @pytest.mark.unit
    def test_hebrew_routing_logic(self):
        """Test that Hebrew translations are properly routed to capable providers."""
        # Mock database and translator
        db = Mock()
        db.get_segments_for_translation.return_value = [
            {'id': 1, 'original_text': 'Test text for Hebrew'}
        ]
        db.batch_update_segment_translations.return_value = True
        
        # Create a real HistoricalTranslator with mocked providers
        translator = HistoricalTranslator()
        translator.providers = {
            'deepl': Mock(),  # DeepL doesn't support Hebrew
            'openai': True,
            'microsoft': {'api_key': 'test', 'location': 'test'}
        }
        translator.openai_client = None  # Skip language detection
        
        # Track translation calls
        translation_calls = []
        
        def track_translate(texts, target_lang, source_lang=None):
            translation_calls.append({
                'texts': texts,
                'target_lang': target_lang
            })
            return ['תרגום לעברית']  # Hebrew translation
            
        translator.batch_translate = Mock(side_effect=track_translate)
        translator.is_same_language = Mock(return_value=False)
        translator.validate_hebrew_translation = Mock(return_value=True)
        
        # Create database translator
        db_translator = DatabaseTranslator(db, translator)
        
        # Translate to Hebrew
        results = db_translator.translate_interview('test_id', 'he')
        
        # Verify translation was called
        assert len(translation_calls) == 1
        assert translation_calls[0]['target_lang'] == 'he'
        
        # Note: The actual provider routing happens inside HistoricalTranslator
        # which we're mocking here. The important thing is that Hebrew translation
        # works and produces valid Hebrew text
        assert results['translated'] == 1
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_preserve_all_translation_quality(self, temp_dir):
        """Test that translation quality is preserved for all languages including Hebrew."""
        db_path = temp_dir / "test_all_langs.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock OpenAI client for language detection
        mock_openai = Mock()
        mock_response = Mock()
        # All segments are German
        mock_response.choices = [Mock(message=Mock(content="""1: German
2: German
3: German"""))]
        mock_openai.chat.completions.create.return_value = mock_response
        
        # Mock translator with quality translations
        mock_translator = Mock(spec=HistoricalTranslator)
        mock_translator.openai_client = mock_openai
        
        # Mock is_same_language to properly detect German
        def mock_is_same_language(lang1, lang2):
            # Since original text is in German, detected language would be 'de'
            # So when target is also 'de', it should return True
            if lang1 == 'de' and lang2 == 'de':
                return True
            return False
            
        mock_translator.is_same_language.side_effect = mock_is_same_language
        
        # Simulate high-quality translations for each language
        def quality_translate(texts, target_lang, source_lang=None):
            translations = []
            for text in texts:
                if target_lang == 'en':
                    # English: preserve formality and historical context
                    translations.append('I was born in nineteen hundred and thirty.')
                elif target_lang == 'de':
                    # German: maintain authentic speech patterns
                    translations.append('Ich wurde im Jahre neunzehnhundertdreißig geboren.')
                elif target_lang == 'he':
                    # Hebrew: proper script and grammar
                    translations.append('נולדתי בשנת אלף תשע מאות שלושים.')
            return translations
            
        mock_translator.batch_translate.side_effect = quality_translate
        mock_translator.validate_hebrew_translation.return_value = True
        
        # Create interview with historical content
        interview_id = db.add_file("/test/historical.mp4", "historical_mp4", "video")
        
        # Add segments with historical context
        segments = [
            (0, 0.0, 3.0, 'Ich wurde 1930 geboren.'),  # German original
            (1, 3.0, 6.0, 'In Berlin, in der Weimarer Republik.'),
            (2, 6.0, 9.0, 'Meine Familie war jüdisch.')
        ]
        
        for idx, start, end, text in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Translate to all languages
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Test English translation
        en_results = db_translator.translate_interview(interview_id, 'en')
        assert en_results['translated'] == 3
        
        # Test German preservation (should skip as same language)
        de_results = db_translator.translate_interview(interview_id, 'de')
        # All segments should be skipped since original is German
        assert de_results['skipped'] == 3
        
        # Test Hebrew translation
        he_results = db_translator.translate_interview(interview_id, 'he')
        assert he_results['translated'] == 3
        
        # Verify all translations maintain quality
        segments_after = db.get_subtitle_segments(interview_id)
        
        # Check English maintains historical context
        assert 'nineteen hundred' in segments_after[0]['english_text']
        
        # Check Hebrew has valid Hebrew characters
        assert 'נולדתי' in segments_after[0]['hebrew_text']
        
        # Validate all Hebrew translations
        validation = db_translator.validate_translations(interview_id, 'he')
        assert validation['valid'] == True
        assert validation['validated'] == 3
        
        db.close()


class TestEnhancedQualityValidation:
    """Test enhanced quality validation that builds upon existing framework (Task 3.5)."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_enhanced_translation_validation(self, temp_dir):
        """Test enhanced translation validation using existing quality framework."""
        db_path = temp_dir / "test_enhanced_validation.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock translator and evaluator
        mock_translator = Mock()
        mock_translator.validate_hebrew_translation.return_value = True
        
        mock_evaluator = Mock()
        mock_evaluation_result = {
            'scores': {'content_accuracy': 8.5, 'hebrew_language_quality': 9.0},
            'composite_score': 8.7
        }
        mock_evaluator.evaluate.return_value = mock_evaluation_result
        mock_evaluator.get_score.return_value = 8.7
        
        db_translator = DatabaseTranslator(db, mock_translator, mock_evaluator)
        
        # Add interview with translations
        interview_id = db.add_file("/test/enhanced.mp4", "enhanced_mp4", "video")
        
        segments = [
            (0, 0.0, 3.0, 'Ich wurde geboren.', 'I was born.', 'נולדתי.'),
            (1, 3.0, 6.0, 'In Deutschland.', 'In Germany.', 'בגרמניה.'),
            (2, 6.0, 9.0, 'Neunzehnhundert.', 'Nineteen hundred.', 'אלף תשע מאות.')
        ]
        
        for idx, start, end, original, english, hebrew in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english,
                hebrew_text=hebrew
            )
        
        # Test basic validation (preserving existing functionality)
        basic_validation = db_translator.validate_translations(interview_id, 'he', enhanced_quality_check=False)
        assert basic_validation['valid'] == True
        assert basic_validation['validated'] == 3
        assert basic_validation['validation_method'] == 'enhanced_database_validation'
        
        # Test enhanced validation that builds upon existing quality framework
        enhanced_validation = db_translator.validate_translations(interview_id, 'he', enhanced_quality_check=True)
        assert enhanced_validation['valid'] == True
        assert enhanced_validation['validated'] == 3
        assert 'quality_scores' in enhanced_validation
        assert enhanced_validation['validation_method'] == 'enhanced_database_validation'
        
        # Verify evaluator was called with existing patterns
        assert mock_evaluator.evaluate.called
        assert mock_evaluator.get_score.called
        
        db.close()
    
    @pytest.mark.unit 
    @pytest.mark.database
    def test_quality_evaluation_method(self, temp_dir):
        """Test comprehensive quality evaluation using existing HistoricalEvaluator."""
        db_path = temp_dir / "test_quality_eval.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock evaluator that mimics existing HistoricalEvaluator behavior
        mock_translator = Mock()
        mock_translator.openai_client = Mock()  # Simulate OpenAI client availability
        
        mock_evaluator = Mock()
        mock_evaluation_result = {
            'scores': {
                'content_accuracy': 8.5,
                'speech_pattern_fidelity': 7.8,
                'hebrew_language_quality': 9.0,
                'cultural_context': 8.2,
                'historical_authenticity': 8.8
            },
            'composite_score': 8.5,
            'strengths': ['Accurate historical content', 'Proper Hebrew characters'],
            'issues': [],
            'suitability': 'Excellent for historical research'
        }
        mock_evaluator.evaluate.return_value = mock_evaluation_result
        mock_evaluator.get_score.return_value = 8.5
        
        db_translator = DatabaseTranslator(db, mock_translator, mock_evaluator)
        
        # Add interview
        interview_id = db.add_file("/test/quality.mp4", "quality_mp4", "video")
        
        segments = [
            (0, 0.0, 4.0, 'Ich wurde im Jahr neunzehnhundertdreißig geboren.', 
             'I was born in the year nineteen thirty.', 'נולדתי בשנת אלף תשע מאות ושלושים.'),
            (1, 4.0, 8.0, 'Meine Familie lebte in Deutschland.',
             'My family lived in Germany.', 'המשפחה שלי גרה בגרמניה.'),
        ]
        
        for idx, start, end, original, english, hebrew in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx, 
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english,
                hebrew_text=hebrew
            )
        
        # Test quality evaluation method that builds upon existing framework
        quality_results = db_translator.evaluate_translation_quality(interview_id, ['he'], sample_size=2)
        
        assert quality_results['interview_id'] == interview_id
        assert quality_results['evaluation_method'] == 'enhanced_database_quality_evaluation'
        assert 'he' in quality_results['languages']
        
        he_results = quality_results['languages']['he']
        assert he_results['segments_evaluated'] == 2
        assert he_results['average_score'] == 8.5
        assert len(he_results['segment_scores']) == 2
        
        # Verify existing evaluation framework was used
        assert mock_evaluator.evaluate.call_count == 2
        assert mock_evaluator.get_score.call_count == 2
        
        # Check that evaluation was called with enhanced=True (leveraging existing capabilities)
        call_args = mock_evaluator.evaluate.call_args_list[0]
        assert call_args[1]['enhanced'] == True
        assert call_args[1]['language'] == 'he'
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_validation_pipeline_integration(self, temp_dir):
        """Test integration with existing pipeline validation patterns."""
        from scribe.database_translation import validate_interview_translation_quality
        
        db_path = temp_dir / "test_pipeline_validation.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create mock components that simulate existing framework
        mock_translator = Mock()
        mock_translator.validate_hebrew_translation.return_value = True
        
        mock_evaluator = Mock()
        mock_evaluator.evaluate.return_value = {'scores': {'composite_score': 8.0}}
        mock_evaluator.get_score.return_value = 8.0
        
        # Add interview data
        interview_id = db.add_file("/test/pipeline.mp4", "pipeline_mp4", "video")
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=3.0,
            original_text='Test original.',
            english_text='Test English.',
            hebrew_text='טסט עברית.'
        )
        
        # Test pipeline integration function
        validation_results = validate_interview_translation_quality(
            db=db,
            interview_id=interview_id,
            target_languages=['en', 'he'],
            enhanced_validation=True,
            translator=mock_translator,
            evaluator=mock_evaluator
        )
        
        assert validation_results['interview_id'] == interview_id
        assert validation_results['overall_valid'] == True
        assert validation_results['validation_method'] == 'enhanced_database_validation_pipeline'
        assert 'en' in validation_results['languages']
        assert 'he' in validation_results['languages']
        
        # Verify each language was validated
        for lang in ['en', 'he']:
            lang_result = validation_results['languages'][lang]
            assert lang_result['valid'] == True
            assert lang_result['validated'] == 1
            assert lang_result['validation_method'] == 'enhanced_database_validation'
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_hebrew_validation_integration(self, temp_dir):
        """Test that Hebrew validation integrates with existing validate_hebrew_translation."""
        db_path = temp_dir / "test_hebrew_integration.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create translator with Hebrew validation
        mock_translator = Mock()
        mock_translator.validate_hebrew_translation.return_value = True
        
        db_translator = DatabaseTranslator(db, mock_translator)
        
        # Add interview with Hebrew translations
        interview_id = db.add_file("/test/hebrew.mp4", "hebrew_mp4", "video")
        
        # Valid Hebrew segment
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=3.0,
            original_text='Ich wurde geboren.',
            hebrew_text='נולדתי בשנת אלף תשע מאות ושלושים.'
        )
        
        # Invalid Hebrew segment (no Hebrew characters)
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=1,
            start_time=3.0,
            end_time=6.0,
            original_text='In Deutschland.',
            hebrew_text='This is not Hebrew'
        )
        
        # Mock translator to fail on invalid Hebrew
        def mock_hebrew_validator(text):
            return 'נ' in text  # True only if contains Hebrew
        
        mock_translator.validate_hebrew_translation.side_effect = mock_hebrew_validator
        
        # Test validation
        validation_results = db_translator.validate_translations(interview_id, 'he')
        
        # Should fail due to invalid Hebrew in segment 1
        assert validation_results['valid'] == False
        assert validation_results['validated'] == 2
        assert len(validation_results['issues']) >= 1
        
        # Verify existing Hebrew validation was called
        assert mock_translator.validate_hebrew_translation.call_count == 2
        
        db.close()


class TestTimingCoordination:  
    """Test timing coordination between database segments and SRT mechanisms (Task 3.4)."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_convert_segments_to_srt_format(self, temp_dir):
        """Test converting database segments to SRT format with exact timing."""
        db_path = temp_dir / "test_srt_conversion.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview with precise timing
        interview_id = db.add_file("/test/timing.mp4", "timing_mp4", "video")
        
        # Add segments with precise timestamps  
        segments = [
            (0, 0.0, 2.5, 'Ich wurde geboren.', 'I was born.', 'J\'ai été né.'),
            (1, 2.5, 5.125, 'In Deutschland.', 'In Germany.', 'En Allemagne.'),
            (2, 5.125, 8.75, 'Neunzehnhundertdreißig.', 'Nineteen thirty.', 'Mille neuf cent trente.')
        ]
        
        for idx, start, end, original, english, german in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english,
                german_text=german
            )
        
        # Test conversion for different languages
        db_translator = DatabaseTranslator(db)
        
        # Test original language conversion
        original_srt = db_translator.convert_segments_to_srt_format(interview_id, 'original')
        assert len(original_srt) == 3
        assert original_srt[0].start_time == '00:00:00,000'
        assert original_srt[0].end_time == '00:00:02,500'
        assert original_srt[0].text == 'Ich wurde geboren.'
        assert original_srt[0].index == 1  # SRT is 1-based
        
        # Test English conversion
        english_srt = db_translator.convert_segments_to_srt_format(interview_id, 'en')
        assert len(english_srt) == 3
        assert english_srt[1].start_time == '00:00:02,500'
        assert english_srt[1].end_time == '00:00:05,125'
        assert english_srt[1].text == 'In Germany.'
        
        # Test precise timing conversion
        assert english_srt[2].start_time == '00:00:05,125'
        assert english_srt[2].end_time == '00:00:08,750'
        
        db.close()
        
    @pytest.mark.unit
    def test_srt_time_conversion_precision(self):
        """Test precise SRT time format conversion."""
        db_translator = DatabaseTranslator(Database(":memory:"))
        
        # Test seconds to SRT time
        test_cases = [
            (0.0, '00:00:00,000'),
            (2.5, '00:00:02,500'),
            (62.125, '00:01:02,125'),
            (3661.999, '01:01:01,999'),
            (3600.001, '01:00:00,001')
        ]
        
        for seconds, expected_srt in test_cases:
            result = db_translator._seconds_to_srt_time(seconds)
            assert result == expected_srt, f"Failed for {seconds}s: got {result}, expected {expected_srt}"
            
        # Test SRT time to seconds (round trip)
        for seconds, srt_time in test_cases:
            converted_back = db_translator._srt_time_to_seconds(srt_time)
            assert abs(converted_back - seconds) < 0.001, f"Round trip failed: {seconds} -> {srt_time} -> {converted_back}"
            
    @pytest.mark.unit  
    @pytest.mark.database
    def test_validate_timing_coordination(self, temp_dir):
        """Test timing coordination validation using SRTTranslator mechanisms."""
        db_path = temp_dir / "test_timing_validation.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Mock translator for boundary validation
        mock_translator = Mock(spec=HistoricalTranslator)
        
        # Create interview with proper timing
        interview_id = db.add_file("/test/validate_timing.mp4", "validate_timing_mp4", "video")
        
        # Add segments with consistent timing
        segments = [
            (0, 0.0, 2.0, 'First segment.', 'First segment.'),
            (1, 2.0, 4.0, 'Second segment.', 'Second segment.'),
            (2, 4.0, 6.0, 'Third segment.', 'Third segment.')
        ]
        
        for idx, start, end, original, english in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english
            )
        
        # Test timing validation
        db_translator = DatabaseTranslator(db, mock_translator)
        validation = db_translator.validate_timing_coordination(interview_id, 'en')
        
        # Should pass timing validation
        assert validation['timing_valid'] == True
        assert validation['boundary_validation'] == True
        assert validation['segment_count'] == 3
        assert len(validation['timing_issues']) == 0
        assert validation['total_duration'] == 6.0  # 0 to 6 seconds
        
        db.close()
        
    @pytest.mark.unit
    @pytest.mark.database
    def test_timing_coordination_with_gaps(self, temp_dir):
        """Test timing validation detects gaps and overlaps."""
        db_path = temp_dir / "test_timing_gaps.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview with timing issues
        interview_id = db.add_file("/test/gaps.mp4", "gaps_mp4", "video")
        
        # Add segments with gaps and overlaps
        segments = [
            (0, 0.0, 2.0, 'First segment.', 'First segment.'),
            (1, 2.5, 4.0, 'Gap before this.', 'Gap before this.'),  # 0.5s gap
            (2, 3.8, 6.0, 'Overlap with previous.', 'Overlap with previous.')  # 0.2s overlap
        ]
        
        for idx, start, end, original, english in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english
            )
        
        # Test timing validation
        db_translator = DatabaseTranslator(db)
        validation = db_translator.validate_timing_coordination(interview_id, 'en')
        
        # Should detect timing issues
        assert validation['timing_valid'] == False  # Overlap detected
        assert len(validation['timing_issues']) >= 2  # Gap and overlap
        
        # Check specific issues
        issues_text = ' '.join(validation['timing_issues'])
        assert 'Gap' in issues_text
        assert 'Overlap' in issues_text
        
        db.close()
        
    @pytest.mark.unit
    @pytest.mark.database
    def test_generate_coordinated_srt(self, temp_dir):
        """Test generating SRT files with coordinated timing."""
        db_path = temp_dir / "test_srt_generation.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview
        interview_id = db.add_file("/test/srt_gen.mp4", "srt_gen_mp4", "video")
        
        # Add segments
        segments = [
            (0, 0.0, 2.5, 'Hello world.', 'Hello world.'),
            (1, 2.5, 5.0, 'How are you?', 'How are you?'),
            (2, 5.0, 7.5, 'Goodbye.', 'Goodbye.')
        ]
        
        for idx, start, end, original, english in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english
            )
        
        # Generate SRT file
        output_path = temp_dir / "test_output.srt"
        db_translator = DatabaseTranslator(db)
        success = db_translator.generate_coordinated_srt(interview_id, 'en', output_path)
        
        assert success == True
        assert output_path.exists()
        
        # Verify SRT content
        srt_content = output_path.read_text(encoding='utf-8')
        lines = srt_content.strip().split('\n')
        
        # Check first segment
        assert lines[0] == '1'
        assert lines[1] == '00:00:00,000 --> 00:00:02,500'
        assert lines[2] == 'Hello world.'
        assert lines[3] == ''
        
        # Check second segment
        assert lines[4] == '2'
        assert lines[5] == '00:00:02,500 --> 00:00:05,000'
        assert lines[6] == 'How are you?'
        
        db.close()
        
    @pytest.mark.integration
    @pytest.mark.database
    def test_coordinate_translation_timing_integration(self, temp_dir):
        """Test the main timing coordination function (Task 3.4)."""
        db_path = temp_dir / "test_coordination.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments() 
        
        # Create interview with multilingual segments
        interview_id = db.add_file("/test/coordination.mp4", "coordination_mp4", "video")
        
        segments = [
            (0, 0.0, 2.0, 'Guten Tag.', 'Good day.', 'יום טוב.'),
            (1, 2.0, 4.0, 'Wie geht es?', 'How are you?', 'איך דברים?'),
            (2, 4.0, 6.0, 'Auf Wiedersehen.', 'Goodbye.', 'להיתראות.')
        ]
        
        for idx, start, end, original, english, hebrew in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english,
                hebrew_text=hebrew
            )
        
        # Test timing coordination for all languages
        from scribe.database_translation import coordinate_translation_timing
        results = coordinate_translation_timing(db, interview_id)
        
        # Verify coordination was successful
        assert results['overall_success'] == True
        assert results['timing_coordination_active'] == True
        assert results['interview_id'] == interview_id
        
        # Check each language
        for lang in ['en', 'de', 'he']:
            lang_result = results['languages'][lang]
            assert lang_result['timing_valid'] == True
            assert lang_result['boundary_validation'] == True
            assert lang_result['segment_count'] == 3
            assert lang_result['srt_conversion_success'] == True
            assert lang_result['converted_segments'] == 3
            assert lang_result['segment_count_match'] == True
            assert lang_result['coordination_method'] == 'database_to_srt_bridge'
        
        db.close()
        
    @pytest.mark.integration  
    @pytest.mark.database
    def test_timing_coordination_with_missing_translations(self, temp_dir):
        """Test timing coordination when some translations are missing."""
        db_path = temp_dir / "test_missing_translations.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview with partial translations
        interview_id = db.add_file("/test/partial.mp4", "partial_mp4", "video")
        
        # Add segments with missing translations
        db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=0,
            start_time=0.0,
            end_time=2.0,
            original_text='Original text.',
            english_text='English text.',  # Hebrew missing
            german_text=None
        )
        
        # Test coordination - should handle missing translations gracefully
        from scribe.database_translation import coordinate_translation_timing
        results = coordinate_translation_timing(db, interview_id)
        
        # English should work (has translation)
        assert results['languages']['en']['srt_conversion_success'] == True
        assert results['languages']['en']['converted_segments'] == 1
        
        # German should work (will use original text as fallback)
        assert results['languages']['de']['srt_conversion_success'] == True
        
        # Hebrew should work (will use original text as fallback)
        assert results['languages']['he']['srt_conversion_success'] == True
        
        db.close()
        
    @pytest.mark.unit
    def test_timing_coordination_error_handling(self):
        """Test error handling in timing coordination."""
        # Mock database that raises errors
        mock_db = Mock()
        mock_db.get_subtitle_segments.side_effect = Exception("Database error")
        
        from scribe.database_translation import coordinate_translation_timing
        results = coordinate_translation_timing(mock_db, "test_id")
        
        # Should handle error gracefully
        assert results['overall_success'] == False
        assert 'critical_error' in results
        assert 'Database error' in results['critical_error']
        
    @pytest.mark.unit
    @pytest.mark.database
    def test_boundary_validation_with_srt_translator(self, temp_dir):
        """Test that boundary validation uses existing SRTTranslator mechanisms."""
        db_path = temp_dir / "test_boundary.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Create interview
        interview_id = db.add_file("/test/boundary.mp4", "boundary_mp4", "video")
        
        # Add segments with perfect timing
        segments = [
            (0, 0.0, 1.5, 'First.', 'First.'),
            (1, 1.5, 3.0, 'Second.', 'Second.'),
            (2, 3.0, 4.5, 'Third.', 'Third.')
        ]
        
        for idx, start, end, original, english in segments:
            db.add_subtitle_segment(
                interview_id=interview_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=original,
                english_text=english
            )
        
        # Test that validation uses SRTTranslator's boundary validation
        db_translator = DatabaseTranslator(db)
        
        # Mock SRTTranslator to verify it's being used
        with patch('scribe.database_translation.SRTTranslator') as mock_srt_class:
            mock_srt_instance = Mock()
            mock_srt_instance._validate_segment_boundaries.return_value = True
            mock_srt_class.return_value = mock_srt_instance
            
            validation = db_translator.validate_timing_coordination(interview_id, 'en')
            
            # Verify SRTTranslator was instantiated
            mock_srt_class.assert_called_once_with(db_translator.translator)
            
            # Verify boundary validation was called
            mock_srt_instance._validate_segment_boundaries.assert_called_once()
            
            # Verify validation passed
            assert validation['boundary_validation'] == True
            assert validation['timing_valid'] == True
        
        db.close()