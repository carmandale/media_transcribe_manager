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
    
    @pytest.fixture
    def mock_database(self):
        """Create mock database."""
        return Mock()
    
    @pytest.fixture
    def pipeline_config(self, temp_dir):
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
    def pipeline(self, pipeline_config, mock_database):
        """Create pipeline instance with mocks."""
        with patch('scribe.pipeline.Database') as mock_db_class:
            mock_db_class.return_value = mock_database
            pipeline = Pipeline(pipeline_config)
            pipeline.db = mock_database
            return pipeline
    
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
    def test_transcription_failure_recovery(self, pipeline, mock_database):
        """Test recovery from transcription failures."""
        file_data = {'file_id': 'test-123', 'file_path': '/test/file.mp4'}
        
        with patch('scribe.pipeline.transcribe_file') as mock_transcribe:
            # First attempt fails, second succeeds
            mock_transcribe.side_effect = [
                Exception("API Error"),
                {'success': True, 'text': 'Recovered transcription'}
            ]
            
            # First attempt should fail
            success = pipeline._process_transcription(file_data)
            assert success is False
            
            # Second attempt should succeed
            success = pipeline._process_transcription(file_data)
            assert success is True
    
    @pytest.mark.unit
    def test_partial_pipeline_completion(self, pipeline, mock_database):
        """Test handling of partial pipeline completion."""
        file_data = {'file_id': 'test-123', 'file_path': Path('/test/file.mp4')}
        
        with patch.object(pipeline, '_process_transcription', return_value=True), \
             patch.object(pipeline, '_process_translation') as mock_trans, \
             patch.object(pipeline, '_process_evaluation', return_value=7.0):
            
            # Make German translation fail
            mock_trans.side_effect = [True, Exception("German API down")]
            
            result = pipeline.process_file(file_data)
            
            # Should complete what it can
            assert result.transcribed is True
            assert result.translations.get("en") is True
            assert "de" not in result.translations or result.translations["de"] is False
            assert len(result.errors) > 0
            assert "German API down" in str(result.errors)


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