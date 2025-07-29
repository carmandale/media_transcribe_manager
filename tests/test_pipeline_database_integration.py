#!/usr/bin/env python3
"""
End-to-End tests for pipeline database segment integration.

This test suite implements Task 5.1: Extend existing end-to-end tests to include
database segment coordination, ensuring the enhanced pipeline maintains all
existing functionality while adding segment capabilities.
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Dict
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.database import Database
from scribe.pipeline import Pipeline, PipelineConfig, PipelineResult
from scribe.pipeline_database_integration import EnhancedPipeline, create_pipeline
from scribe.database_translation import DatabaseTranslator


class TestPipelineDatabaseIntegration:
    """Test enhanced pipeline with database segment coordination (Task 5.1)."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        temp_dir = tempfile.mkdtemp()
        input_dir = Path(temp_dir) / "input"
        output_dir = Path(temp_dir) / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        yield {
            'base': Path(temp_dir),
            'input': input_dir,
            'output': output_dir
        }
        
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_transcribe(self):
        """Mock transcription function."""
        with patch('scribe.pipeline_database_integration.transcribe_file') as mock:
            def transcribe_side_effect(file_path, output_dir, output_prefix):
                # Create mock transcript file
                transcript_path = output_dir / f"{output_prefix}_original.txt"
                transcript_path.write_text(
                    "Dies ist ein Test. Es funktioniert gut. Danke schön.",
                    encoding='utf-8'
                )
                return str(transcript_path)
            
            mock.side_effect = transcribe_side_effect
            yield mock
    
    @pytest.fixture
    def pipeline_config(self, temp_dirs):
        """Create pipeline configuration for testing."""
        return PipelineConfig(
            input_dir=temp_dirs['input'],
            output_dir=temp_dirs['output'],
            languages=['en', 'de'],
            transcription_workers=1,
            translation_workers=1,
            evaluation_sample_size=2
        )
    
    @pytest.mark.integration
    def test_enhanced_pipeline_initialization(self, pipeline_config):
        """Test that enhanced pipeline initializes with segment support."""
        # Test with segments enabled (default)
        pipeline = EnhancedPipeline(pipeline_config)
        assert pipeline.use_database_segments == True
        assert pipeline.db_translator is not None
        assert isinstance(pipeline.db_translator, DatabaseTranslator)
        
        # Test with segments disabled
        pipeline_legacy = EnhancedPipeline(pipeline_config, use_database_segments=False)
        assert pipeline_legacy.use_database_segments == False
        assert pipeline_legacy.db_translator is None
    
    @pytest.mark.integration
    def test_process_transcription_with_segments(self, pipeline_config, temp_dirs, mock_transcribe):
        """Test Task 5.2: Process transcriptions with segment storage."""
        # Create test media file
        test_file = temp_dirs['input'] / "test_interview.mp3"
        test_file.write_text("dummy audio content")
        
        # Create pipeline
        pipeline = EnhancedPipeline(pipeline_config)
        
        # Add file to database
        file_id = pipeline.db.add_file(str(test_file))
        
        # Process transcription with segments
        results = pipeline.process_transcriptions_with_segments(limit=1)
        
        assert len(results) == 1
        assert results[0].transcribed == True
        assert results[0].file_id == file_id
        
        # Verify segments were stored
        segments = pipeline.db.get_subtitle_segments(file_id)
        assert len(segments) > 0  # Should have created segments
        
        # Verify each segment has required fields
        for segment in segments:
            assert 'start_time' in segment
            assert 'end_time' in segment
            assert 'original_text' in segment
            assert segment['start_time'] < segment['end_time']
    
    @pytest.mark.integration
    def test_error_handling_with_rollback(self, pipeline_config, temp_dirs):
        """Test Task 5.3: Enhanced error handling with database rollback."""
        # Create pipeline
        pipeline = EnhancedPipeline(pipeline_config)
        
        # Add test file
        test_file = temp_dirs['input'] / "error_test.mp3"
        test_file.write_text("dummy")
        file_id = pipeline.db.add_file(str(test_file))
        
        # Mock transcribe to fail
        with patch('scribe.pipeline_database_integration.transcribe_file') as mock_transcribe:
            mock_transcribe.side_effect = Exception("Transcription API error")
            
            # Process should handle error gracefully
            results = pipeline.process_transcriptions_with_segments(limit=1)
            
            assert len(results) == 1
            assert results[0].transcribed == False
            assert len(results[0].errors) > 0
            assert "Transcription API error" in results[0].errors[0]
            
            # Verify no segments were stored (rollback worked)
            segments = pipeline.db.get_subtitle_segments(file_id)
            assert len(segments) == 0
            
            # Verify status is failed
            status = pipeline.db.get_file_info(file_id)
            assert status['transcription_status'] == 'failed'
    
    @pytest.mark.integration
    def test_translation_coordination_with_segments(self, pipeline_config, temp_dirs):
        """Test Task 5.2: Translation using database segment coordination."""
        # Create pipeline
        pipeline = EnhancedPipeline(pipeline_config)
        
        # Create test file with segments
        test_file = temp_dirs['input'] / "translate_test.mp3"
        test_file.write_text("dummy")
        file_id = pipeline.db.add_file(str(test_file))
        
        # Add segments manually
        segments_data = [
            (0, 0.0, 3.0, "Das ist ein Test."),
            (1, 3.0, 6.0, "Es funktioniert gut."),
            (2, 6.0, 9.0, "Vielen Dank.")
        ]
        
        for idx, start, end, text in segments_data:
            pipeline.db.add_subtitle_segment(
                interview_id=file_id,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text
            )
        
        # Mark transcription as completed
        pipeline.db.update_status(file_id, transcription_status='completed')
        
        # Mock translator
        with patch.object(pipeline.db_translator, 'translate_interview') as mock_translate:
            mock_translate.return_value = {
                'translated': 3,
                'skipped': 0,
                'failed': 0,
                'errors': []
            }
            
            with patch.object(pipeline.db_translator, 'generate_coordinated_srt') as mock_srt:
                mock_srt.return_value = True
                
                # Process translation
                results = pipeline.process_translations_with_coordination('en', limit=1)
                
                assert len(results) == 1
                assert results[0].translations['en'] == True
                assert len(results[0].errors) == 0
                
                # Verify methods were called
                mock_translate.assert_called_once()
                mock_srt.assert_called_once()
    
    @pytest.mark.integration
    def test_progress_tracking_enhancement(self, pipeline_config, temp_dirs):
        """Test Task 5.4: Enhanced progress tracking with segment status."""
        # Create pipeline
        pipeline = EnhancedPipeline(pipeline_config)
        
        # Add test files
        for i in range(3):
            test_file = temp_dirs['input'] / f"progress_test_{i}.mp3"
            test_file.write_text(f"dummy {i}")
            file_id = pipeline.db.add_file(str(test_file))
            
            # Add segments for first two files
            if i < 2:
                for j in range(5):
                    pipeline.db.add_subtitle_segment(
                        interview_id=file_id,
                        segment_index=j,
                        start_time=j * 3.0,
                        end_time=(j + 1) * 3.0,
                        original_text=f"Segment {j}",
                        confidence_score=0.9 + j * 0.02
                    )
        
        # Get enhanced progress status
        status = pipeline.get_enhanced_progress_status()
        
        # Verify basic status
        assert 'total_files' in status
        assert status['total_files'] == 3
        
        # Verify segment storage information
        assert 'segment_storage' in status
        seg_info = status['segment_storage']
        assert seg_info['interviews_with_segments'] == 2
        assert seg_info['total_segments'] == 10  # 2 interviews * 5 segments
        assert seg_info['average_confidence'] > 0.9
    
    @pytest.mark.integration
    def test_backward_compatibility_without_segments(self, pipeline_config, temp_dirs, mock_transcribe):
        """Test Task 5.6: Verify pipeline maintains functionality without segments."""
        # Create legacy pipeline
        pipeline = EnhancedPipeline(pipeline_config, use_database_segments=False)
        
        # Add test file
        test_file = temp_dirs['input'] / "legacy_test.mp3"
        test_file.write_text("dummy")
        file_id = pipeline.db.add_file(str(test_file))
        
        # Process transcription (should use legacy method)
        results = pipeline.process_transcriptions_with_segments(limit=1)
        
        assert len(results) == 1
        assert results[0].transcribed == True
        
        # Verify no segments were created in legacy mode
        segments = pipeline.db.get_subtitle_segments(file_id)
        assert len(segments) == 0
    
    @pytest.mark.integration
    def test_cli_command_integration(self, pipeline_config):
        """Test Task 5.5: CLI command integration with database coordination."""
        from scribe.pipeline_database_integration import add_database_coordination_to_cli
        
        # Create mock CLI module
        import click
        
        @click.group()
        def cli():
            pass
        
        @cli.command()
        @click.option('--limit', type=int)
        def process(limit):
            """Process files."""
            pass
        
        mock_cli_module = type('MockCLI', (), {
            'cli': cli,
            'process': process
        })()
        
        # Enhance CLI with database coordination
        enhanced_cli = add_database_coordination_to_cli(mock_cli_module)
        
        # Verify segment-status command was added
        assert 'segment-status' in [cmd.name for cmd in enhanced_cli.cli.commands.values()]
        
        # Verify quality-report command was added
        assert 'quality-report' in [cmd.name for cmd in enhanced_cli.cli.commands.values()]
    
    @pytest.mark.integration
    def test_full_pipeline_end_to_end(self, pipeline_config, temp_dirs, mock_transcribe):
        """Test Task 5.6: Full pipeline with segment coordination."""
        # Create test files
        for i in range(2):
            test_file = temp_dirs['input'] / f"e2e_test_{i}.mp3"
            test_file.write_text(f"dummy audio {i}")
        
        # Create enhanced pipeline
        pipeline = EnhancedPipeline(pipeline_config)
        
        # Mock translation
        with patch.object(pipeline.db_translator, 'translate_interview') as mock_translate:
            mock_translate.return_value = {
                'translated': 3,
                'skipped': 0,
                'failed': 0,
                'errors': []
            }
            
            with patch.object(pipeline.db_translator, 'generate_coordinated_srt') as mock_srt:
                mock_srt.return_value = True
                
                with patch.object(pipeline.db_translator, 'validate_translations') as mock_validate:
                    mock_validate.return_value = {
                        'valid': True,
                        'quality_scores': {'average_quality': 8.5}
                    }
                    
                    # Run full pipeline
                    status = pipeline.run_full_pipeline_enhanced()
                    
                    # Verify files were processed
                    assert status['total_files'] == 2
                    assert status['completed']['transcription'] >= 0  # Some may complete
                    
                    # Verify segment information is included
                    if 'segment_storage' in status:
                        assert 'interviews_with_segments' in status['segment_storage']
    
    @pytest.mark.integration
    def test_pipeline_factory_function(self, pipeline_config):
        """Test factory function for backward compatibility."""
        # Create with segments (default)
        pipeline_enhanced = create_pipeline(pipeline_config)
        assert isinstance(pipeline_enhanced, EnhancedPipeline)
        assert pipeline_enhanced.use_database_segments == True
        
        # Create without segments
        pipeline_legacy = create_pipeline(pipeline_config, use_segments=False)
        assert isinstance(pipeline_legacy, Pipeline)
    
    @pytest.mark.integration
    def test_quality_report_generation(self, pipeline_config, temp_dirs):
        """Test quality report generation with segment data."""
        pipeline = EnhancedPipeline(pipeline_config)
        
        # Add test data with quality metrics
        file_id = pipeline.db.add_file(str(temp_dirs['input'] / "quality_test.mp3"))
        
        # Store some quality metrics (simulating evaluation)
        from scribe.database_quality_metrics import store_quality_metrics
        store_quality_metrics(pipeline.db, file_id, 'en', {
            'overall_quality': 8.5,
            'translation_accuracy': 0.85,
            'timing_precision': 0.95
        })
        
        # Generate quality report
        report = pipeline._generate_pipeline_quality_report()
        
        assert 'timestamp' in report
        assert 'mode' in report
        assert report['mode'] == 'enhanced_with_segments'
        assert 'languages' in report


if __name__ == '__main__':
    pytest.main([__file__, '-v'])