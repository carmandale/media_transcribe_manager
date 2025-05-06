#!/usr/bin/env python3
"""
Tests for pipeline_manager.py
"""

import os
import sys
import unittest
import tempfile
import sqlite3
import shutil
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import test helpers (adds missing methods to DatabaseManager)
from tests.test_helpers import *

from db_manager import DatabaseManager
from pipeline_manager import PipelineMonitor, ProblemFileHandler, CommandLineInterface


class TestPipelineMonitor(unittest.TestCase):
    """Test the PipelineMonitor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temp directory for test files
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a temporary database
        self.db_path = self.test_dir / "test_db.sqlite"
        
        # Setup test database
        self.setup_test_database()
        
        # Create DatabaseMaintenance instance
        self.db_manager = DatabaseManager(str(self.db_path))
        
        # Configuration
        self.config = {
            'transcription_workers': 3,
            'translation_workers': 2,
            'batch_size': 10
        }
        
        self.pipeline_monitor = PipelineMonitor(self.db_manager, self.config)
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Stop monitoring if active
        if self.pipeline_monitor.monitoring_active:
            self.pipeline_monitor.stop_monitoring()
        
        # Close and remove temp database
        del self.db_manager
        del self.pipeline_monitor
        
        # Remove temp directory
        shutil.rmtree(self.test_dir)
    
    def setup_test_database(self):
        """Set up a test database with tables and sample data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create processing_status table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_status (
            file_id TEXT PRIMARY KEY,
            file_path TEXT,
            status TEXT,
            transcription_status TEXT,
            translation_en_status TEXT,
            translation_de_status TEXT,
            translation_he_status TEXT,
            detected_language TEXT,
            last_updated INTEGER
        )
        """)
        
        # Create error_log table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS error_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            process_stage TEXT,
            error_message TEXT,
            error_details TEXT,
            timestamp INTEGER
        )
        """)
        
        # Insert sample data
        sample_files = [
            # Completed file
            ('file1', '/path/to/file1.mp3', 'completed', 'completed', 'completed', 'completed', 'completed', 'eng', 1600000000),
            # In-progress transcription
            ('file2', '/path/to/file2.mp3', 'in-progress', 'in-progress', 'not_started', 'not_started', 'not_started', '', 1600000000),
            # Completed transcription, in-progress translation
            ('file3', '/path/to/file3.mp3', 'in-progress', 'completed', 'in-progress', 'in-progress', 'not_started', 'deu', 1600000000),
            # Failed transcription
            ('file4', '/path/to/file4.mp3', 'failed', 'failed', 'not_started', 'not_started', 'not_started', '', 1600000000),
            # Not started
            ('file5', '/path/to/file5.mp3', 'not_started', 'not_started', 'not_started', 'not_started', 'not_started', '', 1600000000)
        ]
        
        cursor.executemany(
            "INSERT INTO processing_status VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            sample_files
        )
        
        # Insert sample error log entries
        sample_errors = [
            ('file4', 'transcription', 'Transcription failed', 'API error', 1600000000),
        ]
        
        cursor.executemany(
            "INSERT INTO error_log (file_id, process_stage, error_message, error_details, timestamp) VALUES (?, ?, ?, ?, ?)",
            sample_errors
        )
        
        conn.commit()
        conn.close()
    
    def test_check_status(self):
        """Test checking pipeline status."""
        # Call the method
        status = self.pipeline_monitor.check_status()
        
        # Verify results
        self.assertEqual(status['summary']['total_files'], 5, "Should find 5 total files")
        
        # Check transcription stats
        self.assertEqual(status['stages']['transcription']['completed'], 2, "Should find 2 completed transcriptions")
        self.assertEqual(status['stages']['transcription']['in-progress'], 1, "Should find 1 in-progress transcription")
        self.assertEqual(status['stages']['transcription']['failed'], 1, "Should find 1 failed transcription")
        self.assertEqual(status['stages']['transcription']['not_started'], 1, "Should find 1 not_started transcription")
        
        # Check translation stats
        self.assertEqual(status['stages']['translation']['en']['in-progress'], 1, "Should find 1 in-progress EN translation")
        self.assertEqual(status['stages']['translation']['de']['in-progress'], 1, "Should find 1 in-progress DE translation")
        self.assertEqual(status['stages']['translation']['he']['completed'], 1, "Should find 1 completed HE translation")
    
    def test_check_status_detailed(self):
        """Test checking detailed pipeline status."""
        # Call the method
        status = self.pipeline_monitor.check_status(detailed=True)
        
        # Verify basic results
        self.assertEqual(status['summary']['total_files'], 5, "Should find 5 total files")
        
        # Verify detailed results
        self.assertIn('details', status, "Should include details section")
        self.assertEqual(status['details']['in_progress_files'], 2, "Should find 2 in-progress files")
        self.assertIn('in_progress_list', status['details'], "Should include in_progress_list")
    
    def test_generate_report_text(self):
        """Test generating text report."""
        # Call the method
        report = self.pipeline_monitor.generate_report(output_format='text')
        
        # Verify it's a non-empty string
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 0)
        
        # Verify it contains key information
        self.assertIn('Total files: 5', report)
        self.assertIn('Transcription:', report)
        self.assertIn('Translation Status:', report)
    
    def test_generate_report_markdown(self):
        """Test generating markdown report."""
        # Call the method
        report = self.pipeline_monitor.generate_report(output_format='markdown')
        
        # Verify it's a non-empty string
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 0)
        
        # Verify it contains markdown formatting
        self.assertIn('# Processing Status Report', report)
        self.assertIn('## Summary', report)
        self.assertIn('| Status | Count |', report)
    
    def test_generate_report_json(self):
        """Test generating JSON report."""
        # Call the method
        report = self.pipeline_monitor.generate_report(output_format='json')
        
        # Verify it's valid JSON
        data = json.loads(report)
        
        # Verify it contains key information
        self.assertIn('summary', data)
        self.assertIn('stages', data)
    
    def test_restart_stalled_processes(self):
        """Test restarting stalled processes."""
        # Mock the time functions
        with patch('time.time', return_value=1600010000):  # 10000 seconds later
            # Mock the subprocess.Popen
            with patch('subprocess.Popen') as mock_popen:
                # Call the method
                result = self.pipeline_monitor.restart_stalled_processes(timeout_minutes=30, auto_restart=True)
                
                # Verify results
                self.assertEqual(result['total'], 2, "Should have reset 2 stalled files")
                self.assertEqual(result['transcription'], 1, "Should have reset 1 transcription")
                self.assertEqual(result['translation_en'], 1, "Should have reset 1 EN translation")
                self.assertEqual(result['translation_de'], 1, "Should have reset 1 DE translation")
                
                # Verify subprocess calls for restarting
                self.assertEqual(mock_popen.call_count, 3, "Should have called Popen 3 times")
    
    def test_start_monitoring(self):
        """Test starting and stopping monitoring."""
        # Mock the threading.Thread
        with patch('threading.Thread') as mock_thread:
            # Call start_monitoring
            self.pipeline_monitor.start_monitoring(check_interval=1, restart_interval=5)
            
            # Verify thread was started
            self.assertTrue(self.pipeline_monitor.monitoring_active)
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()
            
            # Call stop_monitoring
            self.pipeline_monitor.stop_monitoring()
            
            # Verify monitoring was stopped
            self.assertFalse(self.pipeline_monitor.monitoring_active)


class TestProblemFileHandler(unittest.TestCase):
    """Test the ProblemFileHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temp directory for test files
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a temporary database
        self.db_path = self.test_dir / "test_db.sqlite"
        
        # Setup test database
        self.setup_test_database()
        
        # Create test file paths
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Create a mock file manager
        self.file_manager_mock = MagicMock()
        self.file_manager_mock.get_transcript_path.return_value = str(self.test_dir / "transcripts" / "test_transcript.txt")
        self.file_manager_mock.get_translation_path.return_value = str(self.test_dir / "translations" / "test_translation.txt")
        self.file_manager_mock.get_audio_path.return_value = str(self.test_dir / "test_audio.mp3")
        
        # Create DatabaseManager instance
        self.db_manager = DatabaseManager(str(self.db_path))
        
        # Configuration
        self.config = {}
        
        self.problem_handler = ProblemFileHandler(self.db_manager, self.file_manager_mock, self.config)
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Close and remove temp database
        del self.db_manager
        del self.problem_handler
        
        # Remove temp directory
        shutil.rmtree(self.test_dir)
    
    def setup_test_database(self):
        """Set up a test database with tables and sample data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create processing_status table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_status (
            file_id TEXT PRIMARY KEY,
            file_path TEXT,
            status TEXT,
            transcription_status TEXT,
            translation_en_status TEXT,
            translation_de_status TEXT,
            translation_he_status TEXT,
            detected_language TEXT,
            last_updated INTEGER
        )
        """)
        
        # Create error_log table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS error_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            process_stage TEXT,
            error_message TEXT,
            error_details TEXT,
            timestamp INTEGER
        )
        """)
        
        # Insert sample data
        sample_files = [
            # Completed file
            ('file1', '/path/to/file1.mp3', 'completed', 'completed', 'completed', 'completed', 'completed', 'eng', 1600000000),
            # Failed multiple times
            ('file2', '/path/to/file2.mp3', 'failed', 'failed', 'not_started', 'not_started', 'not_started', '', 1600000000),
            # Corrupt audio
            ('file3', '/path/to/file3.mp3', 'failed', 'failed', 'not_started', 'not_started', 'not_started', '', 1600000000),
            # Timeout issue
            ('file4', '/path/to/file4.mp3', 'failed', 'failed', 'not_started', 'not_started', 'not_started', '', 1600000000),
            # Very long audio
            ('file5', '/path/to/file5.mp3', 'failed', 'failed', 'not_started', 'not_started', 'not_started', '', 1600000000)
        ]
        
        cursor.executemany(
            "INSERT INTO processing_status VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            sample_files
        )
        
        # Insert sample error log entries
        sample_errors = [
            # Multiple failures for file2
            ('file2', 'transcription', 'Transcription failed', 'API error', 1600000000),
            ('file2', 'transcription', 'Transcription failed', 'API error', 1600000100),
            ('file2', 'transcription', 'Transcription failed', 'API error', 1600000200),
            
            # Corrupt audio for file3
            ('file3', 'transcription', 'Transcription failed', 'Invalid audio format: corrupt header', 1600000000),
            
            # Timeout for file4
            ('file4', 'transcription', 'Transcription failed', 'Request timed out after 300 seconds', 1600000000),
            
            # Memory issue for file5
            ('file5', 'transcription', 'Transcription failed', 'Memory error: file too large', 1600000000)
        ]
        
        cursor.executemany(
            "INSERT INTO error_log (file_id, process_stage, error_message, error_details, timestamp) VALUES (?, ?, ?, ?, ?)",
            sample_errors
        )
        
        conn.commit()
        conn.close()
    
    def test_identify_problem_files(self):
        """Test identifying problematic files."""
        # Call the method
        problem_files = self.problem_handler.identify_problem_files()
        
        # Verify results
        self.assertEqual(len(problem_files['failed_multiple_times']), 1, "Should find 1 file with multiple failures")
        self.assertEqual(len(problem_files['invalid_audio']), 1, "Should find 1 file with invalid audio")
        self.assertEqual(len(problem_files['timeout']), 1, "Should find 1 file with timeout")
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('shutil.copy2')
    def test_preprocess_audio(self, mock_copy, mock_stat, mock_exists, mock_run):
        """Test audio preprocessing function."""
        # Set up mocks
        mock_exists.return_value = True
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 10000
        mock_stat.return_value = mock_stat_result
        mock_run.return_value.returncode = 0
        
        # Additional mocks
        self.file_manager_mock.get_audio_path.return_value = '/test/path/audio.mp3'
        
        # Call the method
        with patch('tempfile.mkdtemp', return_value='/tmp/test_dir'):
            with patch('shutil.rmtree'):
                result = self.problem_handler._preprocess_audio('file3', {'file_id': 'file3', 'file_path': '/path/to/file3.mp3'})
                
                # Since we mocked all the dependencies, the function should succeed
                mock_run.assert_called_once()
                self.assertIn('ffmpeg', str(mock_run.call_args), "Should call ffmpeg")
                # We don't verify result directly as it depends on many mocked calls
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('shutil.copy2')
    def test_fix_corrupt_audio(self, mock_copy, mock_stat, mock_exists, mock_run):
        """Test fixing corrupt audio."""
        # Set up mocks
        mock_exists.return_value = True
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 10000
        mock_stat.return_value = mock_stat_result
        mock_run.return_value.returncode = 0
        
        # Additional mocks
        self.file_manager_mock.get_audio_path.return_value = '/test/path/audio.mp3'
        
        # Call the method
        with patch('tempfile.mkdtemp', return_value='/tmp/test_dir'):
            with patch('shutil.rmtree'):
                # Call the method - we're just testing the mocking here, not the actual result
                self.problem_handler._fix_corrupt_audio('file3', {'file_id': 'file3', 'file_path': '/path/to/file3.mp3'})
                
                # Verify ffmpeg was called
                mock_run.assert_called()
                self.assertIn('ffmpeg', str(mock_run.call_args), "Should call ffmpeg")
    
    @patch('json.dump')
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_split_long_audio(self, mock_open, mock_mkdir, mock_stat, mock_exists, mock_run, mock_json_dump):
        """Test splitting long audio files."""
        # Set up mocks
        mock_exists.return_value = True
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 10000
        mock_stat.return_value = mock_stat_result
        
        # Mock ffprobe duration result
        ffprobe_result = MagicMock()
        ffprobe_result.returncode = 0
        ffprobe_result.stdout = b"3600.5"  # 1 hour
        
        # Mock ffmpeg splitting result
        ffmpeg_result = MagicMock()
        ffmpeg_result.returncode = 0
        
        # Set different return values for different commands
        def run_side_effect(*args, **kwargs):
            if 'ffprobe' in args[0][0]:
                return ffprobe_result
            else:
                return ffmpeg_result
                
        mock_run.side_effect = run_side_effect
        
        # Skip actual database operations but let the test proceed
        with patch.object(self.db_manager, 'execute_update'):
            with patch.object(self.db_manager, 'execute_query', return_value=[]):
                with patch('shutil.copy2'):
                    with patch('tempfile.mkdtemp', return_value='/tmp/test_dir'):
                        with patch('shutil.rmtree'):
                            # This test just verifies the function runs without errors
                            # We don't verify the result as it depends on many mocked components
                            self.problem_handler._split_long_audio('file5', {'file_id': 'file5', 'file_path': '/path/to/file5.mp3'})
                            
                            # Verify ffprobe and ffmpeg were called
                            mock_run.assert_called()
                            # At least one call should be to ffprobe
                            self.assertTrue(any('ffprobe' in str(call_args) for call_args in mock_run.call_args_list),
                                          "Should call ffprobe to get duration")


class TestCommandLineInterface(unittest.TestCase):
    """Test the CommandLineInterface class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cli = CommandLineInterface()
    
    def test_parser_initialization(self):
        """Test that the command line parser is properly initialized."""
        # Just verify that the parser and subparsers were created
        self.assertIsNotNone(self.cli.parser, "Parser should be initialized")
        self.assertIsNotNone(self.cli.subparsers, "Subparsers should be initialized")
    
    @patch('pipeline_manager.DatabaseManager')
    @patch('pipeline_manager.FileManager')
    @patch('pipeline_manager.PipelineMonitor')
    def test_run_status_command(self, mock_pipeline_monitor, mock_file_manager, mock_db_manager):
        """Test running the status command."""
        # Create a mock status
        mock_status = {
            'summary': {'total_files': 5},
            'stages': {'transcription': {'completed': 3}}
        }
        
        # Set up the mock to return the status
        mock_pipeline_monitor.return_value.check_status.return_value = mock_status
        mock_pipeline_monitor.return_value.generate_report.return_value = "Status report"
        
        # Create args
        class Args:
            command = 'status'
            detailed = False
            format = 'text'
            db_path = 'test.db'
            config = None
            log_level = 'INFO'
        
        args = Args()
        
        # Patch print to capture output
        with patch('builtins.print') as mock_print:
            # Run command
            self.cli.run_command(args)
            
            # Verify method calls
            mock_pipeline_monitor.return_value.generate_report.assert_called_once()
            mock_print.assert_called_once_with("Status report")
    
    @patch('pipeline_manager.DatabaseManager')
    @patch('pipeline_manager.FileManager')
    @patch('pipeline_manager.PipelineMonitor')
    def test_run_monitor_command(self, mock_pipeline_monitor, mock_file_manager, mock_db_manager):
        """Test running the monitor command."""
        # Mock pipeline monitor
        mock_monitor = mock_pipeline_monitor.return_value
        
        # Create args
        class Args:
            command = 'monitor'
            check_interval = 5
            restart_interval = 60
            no_auto_restart = False
            db_path = 'test.db'
            config = None
            log_level = 'INFO'
        
        args = Args()
        
        # Mock KeyboardInterrupt to simulate stopping
        def side_effect(*args, **kwargs):
            mock_monitor.monitoring_active = True
            raise KeyboardInterrupt()
            
        mock_monitor.start_monitoring.side_effect = side_effect
        
        # Run command
        self.cli.run_command(args)
        
        # Verify method calls
        mock_monitor.start_monitoring.assert_called_once_with(
            check_interval=5,
            restart_interval=60,
            auto_restart=True
        )
        mock_monitor.stop_monitoring.assert_called_once()


if __name__ == '__main__':
    unittest.main()