"""
Comprehensive tests for the pipeline module.

Tests cover all major functionality including:
- Pipeline configuration
- Full workflow orchestration
- Batch processing
- Worker pool management
- Error handling and recovery
- Progress tracking
"""
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from scribe.pipeline import (
    PipelineConfig, PipelineResult, Pipeline
)


# Module-level fixtures for shared use across test classes
@pytest.fixture
def mock_database():
    """Create mock database."""
    return Mock()


@pytest.fixture
def pipeline_config(temp_dir):
    """Create test pipeline config."""
    return PipelineConfig(
        input_dir=temp_dir / "input",
        output_dir=temp_dir / "output",
        languages=["en", "de"],
        transcription_workers=2,
        translation_workers=2,
        batch_size=10
    )


@pytest.fixture
def pipeline(pipeline_config, mock_database):
    """Create pipeline instance with mocks."""
    with patch('scribe.pipeline.Database') as mock_db_class:
        mock_db_class.return_value = mock_database
        pipeline = Pipeline(pipeline_config)
        pipeline.db = mock_database
        return pipeline


class TestPipelineConfig:
    """Test PipelineConfig dataclass."""
    
    @pytest.mark.unit
    def test_default_config(self):
        """Test default pipeline configuration."""
        config = PipelineConfig()
        
        assert config.input_dir == Path("input")
        assert config.output_dir == Path("output")
        assert config.languages == ["en", "de", "he"]
        assert config.transcription_workers == 10
        assert config.translation_workers == 8
        assert config.evaluation_sample_size == 100
        assert config.batch_size == 50
        assert config.openai_model is None
    
    @pytest.mark.unit
    def test_custom_config(self):
        """Test custom pipeline configuration."""
        config = PipelineConfig(
            input_dir=Path("/custom/input"),
            output_dir=Path("/custom/output"),
            languages=["en", "fr"],
            transcription_workers=5,
            openai_model="gpt-4"
        )
        
        assert config.input_dir == Path("/custom/input")
        assert config.languages == ["en", "fr"]
        assert config.transcription_workers == 5
        assert config.openai_model == "gpt-4"


class TestPipelineResult:
    """Test PipelineResult dataclass."""
    
    @pytest.mark.unit
    def test_default_result(self):
        """Test default pipeline result."""
        result = PipelineResult(
            file_id="test-123",
            file_path=Path("/test/file.mp4")
        )
        
        assert result.file_id == "test-123"
        assert result.file_path == Path("/test/file.mp4")
        assert result.transcribed is False
        assert result.translations == {}
        assert result.evaluations == {}
        assert result.errors == []
        assert result.processing_time == 0.0
    
    @pytest.mark.unit
    def test_result_with_data(self):
        """Test pipeline result with processing data."""
        result = PipelineResult(
            file_id="test-123",
            file_path=Path("/test/file.mp4"),
            transcribed=True,
            translations={"en": True, "de": True, "he": False},
            evaluations={"en": 8.5, "de": 7.8},
            errors=["Hebrew translation failed"],
            processing_time=123.45
        )
        
        assert result.transcribed is True
        assert result.translations["en"] is True
        assert result.translations["he"] is False
        assert result.evaluations["en"] == 8.5
        assert len(result.errors) == 1


class TestPipeline:
    """Test main Pipeline functionality."""
    
    @pytest.mark.unit
    def test_pipeline_initialization(self, pipeline_config, temp_dir):
        """Test pipeline initialization."""
        with patch('scribe.pipeline.Database') as mock_db_class:
            pipeline = Pipeline(pipeline_config)
            
            assert pipeline.config == pipeline_config
            assert pipeline.db is not None
            # Output directories should be created
            assert (temp_dir / "output").exists()
    
    @pytest.mark.unit
    @patch('scribe.pipeline.transcribe_file')
    def test_process_transcription(self, mock_transcribe, pipeline, mock_database):
        """Test transcription processing."""
        # Setup mock file
        file_data = {
            'file_id': 'test-123',
            'file_path': '/test/audio.mp4',
            'transcription_status': 'pending'
        }
        
        # Mock transcribe success
        mock_transcribe.return_value = {
            'success': True,
            'text': 'Transcribed text',
            'language': 'en',
            'duration': 120.0
        }
        
        # Process transcription
        success = pipeline._process_transcription(file_data)
        
        assert success is True
        mock_transcribe.assert_called_once()
        mock_database.update_status.assert_called()
    
    @pytest.mark.unit
    @patch('scribe.pipeline.translate_text')
    def test_process_translation(self, mock_translate, pipeline, mock_database, temp_dir):
        """Test translation processing."""
        # Create test transcript file
        file_id = "test-123"
        transcript_dir = temp_dir / "output" / file_id
        transcript_dir.mkdir(parents=True)
        transcript_file = transcript_dir / "transcript.txt"
        transcript_file.write_text("Original transcript text")
        
        file_data = {
            'file_id': file_id,
            'file_path': '/test/audio.mp4'
        }
        
        # Mock translation
        mock_translate.return_value = "Translated text"
        
        # Process translation
        success = pipeline._process_translation(file_data, "de")
        
        assert success is True
        mock_translate.assert_called_once_with(
            "Original transcript text",
            "de",
            source_language="en"
        )
        
        # Check translation was saved
        translation_file = transcript_dir / "translation_de.txt"
        assert translation_file.exists()
        assert translation_file.read_text() == "Translated text"
    
    @pytest.mark.unit
    @patch('scribe.pipeline.translate_text')
    @patch('scribe.pipeline.validate_hebrew')
    def test_process_hebrew_translation(self, mock_validate, mock_translate, pipeline, mock_database, temp_dir):
        """Test Hebrew translation with validation."""
        # Setup
        file_id = "test-123"
        transcript_dir = temp_dir / "output" / file_id
        transcript_dir.mkdir(parents=True)
        transcript_file = transcript_dir / "transcript.txt"
        transcript_file.write_text("Original text")
        
        file_data = {'file_id': file_id, 'file_path': '/test/audio.mp4'}
        
        # Mock Hebrew translation
        mock_translate.return_value = "טקסט בעברית"
        mock_validate.return_value = True
        
        # Process
        success = pipeline._process_translation(file_data, "he")
        
        assert success is True
        mock_validate.assert_called_once_with("טקסט בעברית")
    
    @pytest.mark.unit
    @patch('scribe.pipeline.evaluate_translation')
    def test_process_evaluation(self, mock_evaluate, pipeline, temp_dir):
        """Test translation evaluation."""
        # Setup files
        file_id = "test-123"
        output_dir = temp_dir / "output" / file_id
        output_dir.mkdir(parents=True)
        
        transcript_file = output_dir / "transcript.txt"
        transcript_file.write_text("Original text")
        
        translation_file = output_dir / "translation_de.txt"
        translation_file.write_text("German translation")
        
        file_data = {'file_id': file_id}
        
        # Mock evaluation
        mock_evaluate.return_value = (8.5, {
            'scores': {'content_accuracy': 9.0},
            'suitability': 'Excellent'
        })
        
        # Process
        score = pipeline._process_evaluation(file_data, "de")
        
        assert score == 8.5
        mock_evaluate.assert_called_once()
        
        # Check evaluation was saved
        eval_file = output_dir / "evaluation_de.json"
        assert eval_file.exists()
    
    @pytest.mark.unit
    def test_process_file_complete_workflow(self, pipeline, mock_database):
        """Test processing a single file through complete workflow."""
        with patch.object(pipeline, '_process_transcription', return_value=True), \
             patch.object(pipeline, '_process_translation', return_value=True) as mock_trans, \
             patch.object(pipeline, '_process_evaluation', return_value=8.0) as mock_eval:
            
            file_data = {
                'file_id': 'test-123',
                'file_path': Path('/test/file.mp4')
            }
            
            result = pipeline.process_file(file_data)
            
            assert result.file_id == 'test-123'
            assert result.transcribed is True
            assert result.translations == {"en": True, "de": True}
            assert result.evaluations == {"en": 8.0, "de": 8.0}
            assert len(result.errors) == 0
            assert result.processing_time > 0
            
            # Verify all languages were processed
            assert mock_trans.call_count == 2
            assert mock_eval.call_count == 2
    
    @pytest.mark.unit
    def test_process_file_with_errors(self, pipeline, mock_database):
        """Test file processing with errors."""
        with patch.object(pipeline, '_process_transcription', side_effect=Exception("Transcription failed")):
            
            file_data = {
                'file_id': 'test-123',
                'file_path': Path('/test/file.mp4')
            }
            
            result = pipeline.process_file(file_data)
            
            assert result.transcribed is False
            assert len(result.errors) > 0
            assert "Transcription failed" in result.errors[0]
    
    @pytest.mark.unit
    @patch('scribe.pipeline.SimpleWorkerPool')
    def test_run_batch_processing(self, mock_pool_class, pipeline, mock_database):
        """Test batch processing with worker pool."""
        # Mock database files
        test_files = [
            {'file_id': f'file-{i}', 'file_path': f'/test/file_{i}.mp4'}
            for i in range(5)
        ]
        mock_database.get_pending_files.return_value = test_files
        
        # Mock worker pool
        mock_pool = Mock()
        mock_results = [Mock(file_id=f['file_id']) for f in test_files]
        mock_pool.map.return_value = mock_results
        mock_pool_class.return_value = mock_pool
        
        # Run batch
        results = pipeline.run_batch(stage="transcription", limit=5)
        
        assert len(results) == 5
        mock_pool.map.assert_called_once()
        
        # Verify progress tracking
        mock_database.get_pending_files.assert_called_with('transcription', limit=5)
    
    @pytest.mark.unit
    def test_run_full_pipeline(self, pipeline, mock_database):
        """Test running full pipeline."""
        # Mock database responses for different stages
        mock_database.get_pending_files.side_effect = [
            [{'file_id': 'file-1', 'file_path': '/test/file1.mp4'}],  # transcription
            [{'file_id': 'file-1', 'file_path': '/test/file1.mp4'}],  # translation_en
            [{'file_id': 'file-1', 'file_path': '/test/file1.mp4'}],  # translation_de
            []  # evaluation (none to process)
        ]
        
        with patch.object(pipeline, 'run_batch') as mock_run_batch:
            mock_run_batch.return_value = [Mock()]
            
            summary = pipeline.run()
            
            # Should process all stages
            assert mock_run_batch.call_count >= 3
            assert 'transcription' in str(mock_run_batch.call_args_list)
            assert 'translation' in str(mock_run_batch.call_args_list)
    
    @pytest.mark.unit
    @patch('scribe.pipeline.ProgressTracker')
    def test_progress_tracking(self, mock_tracker_class, pipeline, mock_database):
        """Test progress tracking during processing."""
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        # Mock some files to process
        mock_database.get_pending_files.return_value = [
            {'file_id': f'file-{i}', 'file_path': f'/test/file_{i}.mp4'}
            for i in range(3)
        ]
        
        with patch.object(pipeline, 'process_file') as mock_process:
            mock_process.return_value = PipelineResult('test', Path('/test'))
            
            pipeline.run_batch("transcription", limit=3)
            
            # Progress tracker should be used
            mock_tracker.start.assert_called_once()
            assert mock_tracker.update.call_count >= 3
            mock_tracker.finish.assert_called_once()


class TestPipelineIntegration:
    """Integration tests for pipeline functionality."""
    
    @pytest.mark.integration
    def test_complete_pipeline_flow(self, temp_dir):
        """Test complete pipeline flow with mocked services."""
        # Create test structure
        input_dir = temp_dir / "input"
        output_dir = temp_dir / "output"
        input_dir.mkdir()
        
        # Create test file
        test_file = input_dir / "test_interview.mp4"
        test_file.write_bytes(b"fake video data")
        
        config = PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            languages=["en", "de"],
            transcription_workers=1,
            translation_workers=1
        )
        
        with patch('scribe.pipeline.Database') as mock_db_class, \
             patch('scribe.pipeline.transcribe_file') as mock_transcribe, \
             patch('scribe.pipeline.translate_text') as mock_translate, \
             patch('scribe.pipeline.evaluate_translation') as mock_evaluate:
            
            # Setup mocks
            mock_db = Mock()
            mock_db_class.return_value = mock_db
            
            # Mock database returns our test file
            mock_db.get_pending_files.side_effect = [
                [{'file_id': 'test-1', 'file_path': str(test_file)}],  # for transcription
                [],  # no more files
            ]
            
            # Mock successful transcription
            mock_transcribe.return_value = {
                'success': True,
                'text': 'This is the transcribed text',
                'language': 'en'
            }
            
            # Mock translations
            mock_translate.side_effect = [
                'This is the transcribed text',  # English
                'Dies ist der transkribierte Text'  # German
            ]
            
            # Mock evaluations
            mock_evaluate.side_effect = [
                (9.0, {'scores': {'accuracy': 9.5}}),  # English
                (8.5, {'scores': {'accuracy': 8.8}})   # German
            ]
            
            # Run pipeline
            pipeline = Pipeline(config)
            results = pipeline.run_batch("transcription")
            
            assert len(results) > 0
            
            # Verify output structure was created
            file_output_dir = output_dir / "test-1"
            assert file_output_dir.exists()


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery mechanisms."""
    
    @pytest.mark.unit
    def test_process_transcriptions_handles_empty_database(self, pipeline, mock_database):
        """Test process_transcriptions handles empty database gracefully."""
        # Mock database to return no pending files
        mock_database.get_pending_files.return_value = []
        
        results = pipeline.process_transcriptions()
        
        assert results == []
        mock_database.get_pending_files.assert_called_once_with('transcription', limit=None)
    
    @pytest.mark.unit
    def test_process_translations_handles_invalid_language(self, pipeline, mock_database):
        """Test process_translations handles invalid language gracefully."""
        # Mock database to return no pending files for invalid language
        mock_database.get_pending_files.return_value = []
        
        results = pipeline.process_translations("invalid_lang")
        
        assert results == []
        mock_database.get_pending_files.assert_called_once_with("translation_invalid_lang", limit=None)


class TestConfigurationValidation:
    """Test configuration validation and edge cases."""
    
    @pytest.mark.unit
    def test_invalid_worker_count(self):
        """Test handling of invalid worker counts."""
        config = PipelineConfig(
            transcription_workers=0,
            translation_workers=-1
        )
        
        with patch('scribe.pipeline.Database'):
            pipeline = Pipeline(config)
            
            # Should use sensible defaults
            assert pipeline.config.transcription_workers >= 1
            assert pipeline.config.translation_workers >= 1
    
    @pytest.mark.unit
    def test_missing_directories(self, temp_dir):
        """Test handling of missing directories."""
        config = PipelineConfig(
            input_dir=temp_dir / "nonexistent" / "input",
            output_dir=temp_dir / "nonexistent" / "output"
        )
        
        with patch('scribe.pipeline.Database'):
            pipeline = Pipeline(config)
            
            # Should create output directory
            assert config.output_dir.exists()


class TestMainPublicAPIMethods:
    """Test the main public API methods that users call."""
    
    @pytest.fixture
    def pipeline(self, temp_dir):
        """Create pipeline instance with test directories."""
        config = PipelineConfig(
            input_dir=temp_dir / "input",
            output_dir=temp_dir / "output",
            languages=["en", "de"]
        )
        with patch('scribe.pipeline.Database') as mock_db_class:
            mock_db = Mock()
            mock_db_class.return_value = mock_db
            pipeline = Pipeline(config)
            pipeline.db = mock_db
            return pipeline
    
    @pytest.mark.unit
    def test_scan_input_files_empty_directory(self, pipeline, temp_dir):
        """Test scanning empty input directory."""
        # Create empty input directory
        (temp_dir / "input").mkdir()
        
        files = pipeline.scan_input_files()
        assert files == []
    
    @pytest.mark.unit
    def test_scan_input_files_with_media_files(self, pipeline, temp_dir):
        """Test scanning directory with media files."""
        # Create input directory with test files
        input_dir = temp_dir / "input"
        input_dir.mkdir()
        
        # Create test files
        (input_dir / "test1.mp4").write_text("fake video")
        (input_dir / "test2.mp3").write_text("fake audio")
        (input_dir / "test3.wav").write_text("fake audio")
        (input_dir / "test4.txt").write_text("not media")  # Should be ignored
        
        files = pipeline.scan_input_files()
        
        # Should find 3 media files, not the txt file
        assert len(files) == 3
        assert any(f.name == "test1.mp4" for f in files)
        assert any(f.name == "test2.mp3" for f in files)
        assert any(f.name == "test3.wav" for f in files)
        assert not any(f.name == "test4.txt" for f in files)
    
    @pytest.mark.unit
    def test_scan_input_files_recursive(self, pipeline, temp_dir):
        """Test scanning subdirectories recursively."""
        # Create nested directory structure
        input_dir = temp_dir / "input"
        input_dir.mkdir()
        subdir = input_dir / "interviews" / "2024"
        subdir.mkdir(parents=True)
        
        # Create files in different levels
        (input_dir / "root.mp4").write_text("fake video")
        (subdir / "nested.mp3").write_text("fake audio")
        
        files = pipeline.scan_input_files()
        
        assert len(files) == 2
        assert any(f.name == "root.mp4" for f in files)
        assert any(f.name == "nested.mp3" for f in files)
    
    @pytest.mark.unit
    def test_add_files_to_database_new_files(self, pipeline):
        """Test adding new files to database."""
        # Mock database responses
        pipeline.db.add_file_simple.side_effect = ["file-1", "file-2", None]  # Third file already exists
        
        test_files = [
            Path("/test/file1.mp4"),
            Path("/test/file2.mp3"),
            Path("/test/file3.wav")  # Already exists
        ]
        
        added = pipeline.add_files_to_database(test_files)
        
        assert added == 2
        assert pipeline.db.add_file_simple.call_count == 3
    
    @pytest.mark.unit
    def test_add_files_to_database_all_existing(self, pipeline):
        """Test adding files that all already exist."""
        # Mock database to return None for all files (already exist)
        pipeline.db.add_file_simple.return_value = None
        
        test_files = [Path("/test/file1.mp4"), Path("/test/file2.mp3")]
        
        added = pipeline.add_files_to_database(test_files)
        
        assert added == 0
        assert pipeline.db.add_file_simple.call_count == 2
    
    @pytest.mark.unit
    def test_process_transcriptions_no_pending(self, pipeline):
        """Test processing transcriptions when no files are pending."""
        pipeline.db.get_pending_files.return_value = []
        
        results = pipeline.process_transcriptions()
        
        assert results == []
        pipeline.db.get_pending_files.assert_called_once_with('transcription', limit=None)
    
    @pytest.mark.unit
    @patch('scribe.pipeline.transcribe_file')
    @patch('scribe.pipeline.ProgressTracker')
    @patch('scribe.pipeline.SimpleWorkerPool')
    def test_process_transcriptions_success(self, mock_pool_class, mock_tracker_class, mock_transcribe, pipeline):
        """Test successful transcription processing."""
        # Mock pending files
        pending_files = [
            {'file_id': 'test-1', 'file_path': '/test/file1.mp4'},
            {'file_id': 'test-2', 'file_path': '/test/file2.mp3'}
        ]
        pipeline.db.get_pending_files.return_value = pending_files
        
        # Mock transcription success
        mock_transcribe.return_value = {
            'success': True,
            'text': 'Transcribed text',
            'language': 'en'
        }
        
        # Mock worker pool
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        mock_pool.__enter__.return_value = mock_pool
        
        # Mock that pool.map returns results for each file
        def mock_map(func, items):
            return [func(item) for item in items]
        mock_pool.map.side_effect = mock_map
        
        # Mock tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        results = pipeline.process_transcriptions()
        
        assert len(results) == 2
        assert all(r.transcribed for r in results)
        assert all(len(r.errors) == 0 for r in results)
        
        # Verify database updates
        assert pipeline.db.update_status.call_count == 4  # 2 files * 2 updates each
    
    @pytest.mark.unit
    @patch('scribe.pipeline.transcribe_file')
    @patch('scribe.pipeline.ProgressTracker')
    @patch('scribe.pipeline.SimpleWorkerPool')
    def test_process_transcriptions_with_failures(self, mock_pool_class, mock_tracker_class, mock_transcribe, pipeline):
        """Test transcription processing with failures."""
        # Mock pending files
        pending_files = [
            {'file_id': 'test-1', 'file_path': '/test/file1.mp4'},
        ]
        pipeline.db.get_pending_files.return_value = pending_files
        
        # Mock transcription failure
        mock_transcribe.side_effect = Exception("API Error")
        
        # Mock worker pool
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        mock_pool.__enter__.return_value = mock_pool
        
        def mock_map(func, items):
            return [func(item) for item in items]
        mock_pool.map.side_effect = mock_map
        
        # Mock tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        results = pipeline.process_transcriptions()
        
        assert len(results) == 1
        assert not results[0].transcribed
        assert len(results[0].errors) == 1
        assert "API Error" in results[0].errors[0]
    
    @pytest.mark.unit
    def test_process_translations_no_pending(self, pipeline):
        """Test processing translations when no files are pending."""
        pipeline.db.get_pending_files.return_value = []
        
        results = pipeline.process_translations("en")
        
        assert results == []
        pipeline.db.get_pending_files.assert_called_once_with('translation_en', limit=None)
    
    @pytest.mark.unit
    @patch('scribe.pipeline.translate_text')
    @patch('scribe.pipeline.ProgressTracker')
    @patch('scribe.pipeline.SimpleWorkerPool')
    def test_process_translations_success(self, mock_pool_class, mock_tracker_class, mock_translate, pipeline, temp_dir):
        """Test successful translation processing."""
        # Create test transcript file
        file_id = "test-1"
        transcript_dir = temp_dir / "output" / file_id
        transcript_dir.mkdir(parents=True)
        transcript_file = transcript_dir / f"{file_id}.txt"
        transcript_file.write_text("German transcript text")
        
        # Mock pending files
        pending_files = [{'file_id': file_id, 'file_path': '/test/file1.mp4'}]
        pipeline.db.get_pending_files.return_value = pending_files
        
        # Mock translation
        mock_translate.return_value = "English translation"
        
        # Mock worker pool
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        mock_pool.__enter__.return_value = mock_pool
        
        # Mock process_batch to return successful results
        mock_pool.process_batch.return_value = {
            'results': {str(pending_files[0]): Mock(translations={'en': True}, errors=[])},
            'completed': 1,
            'failed': 0
        }
        
        # Mock tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        results = pipeline.process_translations("en")
        
        assert len(results) == 1
        # Verify translation file was created
        translation_file = transcript_dir / f"{file_id}_en.txt"
        assert translation_file.exists()
        assert translation_file.read_text() == "English translation"
    
    @pytest.mark.unit
    @patch('scribe.pipeline.translate_text')
    @patch('scribe.pipeline.validate_hebrew')
    @patch('scribe.pipeline.ProgressTracker')
    @patch('scribe.pipeline.SimpleWorkerPool')
    def test_process_translations_hebrew_validation(self, mock_pool_class, mock_tracker_class, mock_validate, mock_translate, pipeline, temp_dir):
        """Test Hebrew translation with validation."""
        # Create test transcript file
        file_id = "test-1"
        transcript_dir = temp_dir / "output" / file_id
        transcript_dir.mkdir(parents=True)
        transcript_file = transcript_dir / f"{file_id}.txt"
        transcript_file.write_text("German transcript text")
        
        # Mock pending files
        pending_files = [{'file_id': file_id, 'file_path': '/test/file1.mp4'}]
        pipeline.db.get_pending_files.return_value = pending_files
        
        # Mock Hebrew translation and validation
        mock_translate.return_value = "טקסט בעברית"
        mock_validate.return_value = True
        
        # Mock worker pool
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        mock_pool.__enter__.return_value = mock_pool
        
        # Mock process_batch to return successful results
        mock_pool.process_batch.return_value = {
            'results': {str(pending_files[0]): Mock(translations={'he': True}, errors=[])},
            'completed': 1,
            'failed': 0
        }
        
        # Mock tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        results = pipeline.process_translations("he")
        
        assert len(results) == 1
        mock_validate.assert_called_once_with("טקסט בעברית")
    
    @pytest.mark.unit
    def test_evaluate_translations_no_pending(self, pipeline):
        """Test evaluating translations when no files need evaluation."""
        pipeline.db.execute_query.return_value = []
        
        results = pipeline.evaluate_translations("en")
        
        assert results == []
    
    @pytest.mark.unit
    @patch('scribe.pipeline.evaluate_translation')
    def test_evaluate_translations_success(self, mock_evaluate, pipeline, temp_dir):
        """Test successful translation evaluation."""
        # Create test files
        file_id = "test-1"
        output_dir = temp_dir / "output" / file_id
        output_dir.mkdir(parents=True)
        
        transcript_file = output_dir / f"{file_id}.txt"
        transcript_file.write_text("Original German text")
        
        translation_file = output_dir / f"{file_id}.en.txt"
        translation_file.write_text("English translation")
        
        # Mock database query
        pipeline.db.execute_query.return_value = [{'file_id': file_id}]
        
        # Mock database connection for INSERT
        mock_conn = Mock()
        pipeline.db._get_connection.return_value = mock_conn
        
        # Mock evaluation
        mock_evaluate.return_value = (8.5, {
            'issues': ['minor grammar'],
            'feedback': 'Good translation overall'
        })
        
        results = pipeline.evaluate_translations("en", sample_size=1)
        
        assert len(results) == 1
        assert results[0][0] == file_id
        assert results[0][1] == 8.5
        assert results[0][2]['issues'] == ['minor grammar']
        
        # Verify database insert was called
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    @pytest.mark.unit
    @patch('scribe.pipeline.evaluate_translation')
    def test_evaluate_translations_enhanced_hebrew(self, mock_evaluate, pipeline, temp_dir):
        """Test enhanced Hebrew evaluation with validation info."""
        # Create test files
        file_id = "test-1"
        output_dir = temp_dir / "output" / file_id
        output_dir.mkdir(parents=True)
        
        transcript_file = output_dir / f"{file_id}.txt"
        transcript_file.write_text("Original German text")
        
        translation_file = output_dir / f"{file_id}.he.txt"
        translation_file.write_text("תרגום עברי")
        
        # Mock database query
        pipeline.db.execute_query.return_value = [{'file_id': file_id}]
        
        # Mock database connection for INSERT
        mock_conn = Mock()
        pipeline.db._get_connection.return_value = mock_conn
        
        # Mock evaluation with Hebrew validation details
        mock_evaluate.return_value = (9.0, {
            'issues': [],
            'feedback': 'Excellent Hebrew translation',
            'suitability': 'Very suitable for historical preservation',
            'hebrew_validation': {'hebrew_ratio': 0.85}
        })
        
        results = pipeline.evaluate_translations("he", sample_size=1, enhanced=True, model="gpt-4.1")
        
        assert len(results) == 1
        assert results[0][1] == 9.0
        
        # Verify enhanced Hebrew info was included
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        comment = call_args[1][5]  # comment parameter
        assert "Very suitable for historical preservation" in comment
        assert "Hebrew ratio: 85.0%" in comment
    
    @pytest.mark.unit
    def test_translate_srt_files_no_pending(self, pipeline):
        """Test SRT translation when no files are pending."""
        pipeline.db.get_files_for_srt_translation.return_value = []
        
        results = pipeline.translate_srt_files("en")
        
        assert results == []
        pipeline.db.get_files_for_srt_translation.assert_called_once_with("en")
    
    @pytest.mark.unit
    @patch('scribe.pipeline.translate_srt_file')
    @patch('scribe.pipeline.ProgressTracker')
    @patch('scribe.pipeline.SimpleWorkerPool')
    def test_translate_srt_files_success(self, mock_pool_class, mock_tracker_class, mock_translate_srt, pipeline, temp_dir):
        """Test successful SRT file translation."""
        # Create test SRT file
        file_id = "test-1"
        srt_dir = temp_dir / "output" / file_id
        srt_dir.mkdir(parents=True)
        srt_file = srt_dir / f"{file_id}.orig.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nTest subtitle\n")
        
        # Mock pending files
        pending_files = [{'file_id': file_id, 'file_path': '/test/file1.mp4'}]
        pipeline.db.get_files_for_srt_translation.return_value = pending_files
        
        # Mock SRT translation success
        mock_translate_srt.return_value = True
        
        # Mock worker pool
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        mock_pool.__enter__.return_value = mock_pool
        
        # Mock process_batch to return successful results
        mock_pool.process_batch.return_value = {
            'results': {str(pending_files[0]): Mock(translations={'en_srt': True}, errors=[])},
            'completed': 1,
            'failed': 0
        }
        
        # Mock tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        results = pipeline.translate_srt_files("en")
        
        assert len(results) == 1
        mock_translate_srt.assert_called_once()
    
    @pytest.mark.unit
    @patch('scribe.pipeline.translate_srt_file')
    @patch('scribe.pipeline.ProgressTracker')
    @patch('scribe.pipeline.SimpleWorkerPool')
    def test_translate_srt_files_fallback_to_regular_srt(self, mock_pool_class, mock_tracker_class, mock_translate_srt, pipeline, temp_dir):
        """Test SRT translation with fallback to regular .srt file."""
        # Create test SRT file (regular .srt, not .orig.srt)
        file_id = "test-1"
        srt_dir = temp_dir / "output" / file_id
        srt_dir.mkdir(parents=True)
        srt_file = srt_dir / f"{file_id}.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nTest subtitle\n")
        
        # Mock pending files
        pending_files = [{'file_id': file_id, 'file_path': '/test/file1.mp4'}]
        pipeline.db.get_files_for_srt_translation.return_value = pending_files
        
        # Mock SRT translation success
        mock_translate_srt.return_value = True
        
        # Mock worker pool
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        mock_pool.__enter__.return_value = mock_pool
        
        # Mock process_batch to return successful results
        mock_pool.process_batch.return_value = {
            'results': {str(pending_files[0]): Mock(translations={'en_srt': True}, errors=[])},
            'completed': 1,
            'failed': 0
        }
        
        # Mock tracker
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        
        results = pipeline.translate_srt_files("en")
        
        assert len(results) == 1
        # Should have called with regular .srt file path
        mock_translate_srt.assert_called_once()
        args = mock_translate_srt.call_args[0]
        assert args[0].endswith(f"{file_id}.srt")
    
    @pytest.mark.unit
    @patch('scribe.pipeline.Pipeline.scan_input_files')
    @patch('scribe.pipeline.Pipeline.add_files_to_database')
    @patch('scribe.pipeline.Pipeline.process_transcriptions')
    @patch('scribe.pipeline.Pipeline.process_translations')
    @patch('scribe.pipeline.Pipeline.evaluate_translations')
    def test_run_full_pipeline(self, mock_eval, mock_translate, mock_transcribe, mock_add, mock_scan, pipeline):
        """Test running the full pipeline."""
        # Mock all the methods
        mock_scan.return_value = [Path("/test/file1.mp4")]
        mock_add.return_value = 1
        mock_transcribe.return_value = [Mock()]
        mock_translate.return_value = [Mock()]
        mock_eval.return_value = [("test-1", 8.5, {})]
        
        # Mock database summary
        pipeline.db.get_summary.return_value = {
            'total_files': 1,
            'transcribed': 1,
            'en_translated': 1,
            'de_translated': 1
        }
        
        pipeline.run_full_pipeline()
        
        # Verify all phases were called
        mock_scan.assert_called_once()
        mock_add.assert_called_once()
        mock_transcribe.assert_called_once()
        assert mock_translate.call_count == 2  # en and de
        assert mock_eval.call_count == 2  # en and de
        pipeline.db.get_summary.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions for pipeline usage."""
    
    @pytest.mark.unit
    @patch('scribe.pipeline.Pipeline')
    def test_run_pipeline_with_config(self, mock_pipeline_class):
        """Test run_pipeline convenience function with config."""
        from scribe.pipeline import run_pipeline
        
        config = PipelineConfig(languages=["en"])
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        run_pipeline(config)
        
        mock_pipeline_class.assert_called_once_with(config)
        mock_pipeline.run_full_pipeline.assert_called_once()
    
    @pytest.mark.unit
    @patch('scribe.pipeline.Pipeline')
    def test_run_pipeline_without_config(self, mock_pipeline_class):
        """Test run_pipeline convenience function without config."""
        from scribe.pipeline import run_pipeline
        
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        run_pipeline()
        
        mock_pipeline_class.assert_called_once_with(None)
        mock_pipeline.run_full_pipeline.assert_called_once()
    
    @pytest.mark.unit
    @patch('scribe.pipeline.Pipeline')
    def test_process_single_file_new_file(self, mock_pipeline_class):
        """Test process_single_file with new file."""
        from scribe.pipeline import process_single_file
        
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        # Mock adding new file
        mock_pipeline.db.add_file.return_value = {
            'file_id': 'test-1',
            'file_path': '/test/file.mp4'
        }
        
        # Mock processing results
        mock_pipeline.process_transcriptions.return_value = [
            Mock(transcribed=True)
        ]
        mock_pipeline.process_translations.return_value = [
            Mock(translations={'en': True})
        ]
        
        result = process_single_file("/test/file.mp4", ["en"])
        
        assert result.file_id == 'test-1'
        assert result.transcribed is True
        assert result.translations['en'] is True
        
        # Verify methods were called
        mock_pipeline.db.add_file.assert_called_once_with("/test/file.mp4")
        mock_pipeline.process_transcriptions.assert_called_once_with(limit=1)
        mock_pipeline.process_translations.assert_called_once_with("en", limit=1)
    
    @pytest.mark.unit
    @patch('scribe.pipeline.Pipeline')
    @patch('scribe.pipeline.generate_file_id')
    def test_process_single_file_existing_file(self, mock_generate_id, mock_pipeline_class):
        """Test process_single_file with existing file."""
        from scribe.pipeline import process_single_file
        
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        # Mock file already exists
        mock_pipeline.db.add_file.return_value = None
        mock_generate_id.return_value = 'existing-file-id'
        
        # Mock processing results
        mock_pipeline.process_transcriptions.return_value = [
            Mock(transcribed=True)
        ]
        mock_pipeline.process_translations.return_value = [
            Mock(translations={'en': True})
        ]
        
        result = process_single_file("/test/existing.mp4")
        
        assert result.file_id == 'existing-file-id'
        assert result.transcribed is True
        
        # Should use default languages from config
        mock_pipeline.process_translations.assert_called_once_with("en", limit=1)  # First language in default config
