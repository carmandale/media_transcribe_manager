#!/usr/bin/env python3
"""
Tests for db_maintenance.py
"""

import os
import sys
import unittest
import tempfile
import sqlite3
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_manager import DatabaseManager
from db_maintenance import DatabaseMaintenance


class TestDatabaseMaintenance(unittest.TestCase):
    """Test the DatabaseMaintenance class."""
    
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
        
        # Set up transcript directories
        self.transcript_dir = self.output_dir / "transcripts"
        self.transcript_dir.mkdir(exist_ok=True)
        
        # Set up translation directories
        self.translations_dir = self.output_dir / "translations"
        self.translations_dir.mkdir(exist_ok=True)
        
        # Create a mock file manager
        self.file_manager_mock = MagicMock()
        self.file_manager_mock.get_transcript_path.return_value = str(self.transcript_dir / "test_transcript.txt")
        self.file_manager_mock.get_translation_path.return_value = str(self.translations_dir / "test_translation.txt")
        self.file_manager_mock.get_audio_path.return_value = str(self.test_dir / "test_audio.mp3")
        
        # Create DatabaseMaintenance instance
        self.db_manager = DatabaseManager(str(self.db_path))
        self.maintenance = DatabaseMaintenance(str(self.db_path))
        self.maintenance.file_manager = self.file_manager_mock
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Close and remove temp database
        del self.db_manager
        del self.maintenance
        
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
            # Normal file
            ('file1', '/path/to/file1.mp3', 'completed', 'completed', 'completed', 'completed', 'completed', 'eng', 1600000000),
            # File with stalled transcription
            ('file2', '/path/to/file2.mp3', 'in-progress', 'in-progress', 'not_started', 'not_started', 'not_started', '', 1600000000),
            # File with path issue
            ('file3', '/path/to/file with%20spaces.mp3', 'completed', 'completed', 'in-progress', 'in-progress', 'in-progress', 'deu', 1600000000),
            # File with missing transcript
            ('file4', '/path/to/file4.mp3', 'completed', 'completed', 'failed', 'failed', 'failed', 'eng', 1600000000),
            # Problem file
            ('file5', '/path/to/file5.mp3', 'failed', 'failed', 'not_started', 'not_started', 'not_started', '', 1600000000)
        ]
        
        cursor.executemany(
            "INSERT INTO processing_status VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            sample_files
        )
        
        # Insert sample error log entries
        sample_errors = [
            ('file2', 'transcription', 'Stalled process', 'Timeout reached', 1600000000),
            ('file5', 'transcription', 'Transcription failed', 'Invalid audio format', 1600000000),
            ('file5', 'transcription', 'Retry failed', 'API error', 1600000100)
        ]
        
        cursor.executemany(
            "INSERT INTO error_log (file_id, process_stage, error_message, error_details, timestamp) VALUES (?, ?, ?, ?, ?)",
            sample_errors
        )
        
        conn.commit()
        conn.close()
    
    def create_test_files(self):
        """Create test transcript and translation files."""
        # Create transcript file
        transcript_path = Path(self.file_manager_mock.get_transcript_path.return_value)
        transcript_path.parent.mkdir(exist_ok=True)
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write("Test transcript content")
        
        # Create translation file
        translation_path = Path(self.file_manager_mock.get_translation_path.return_value)
        translation_path.parent.mkdir(exist_ok=True)
        with open(translation_path, 'w', encoding='utf-8') as f:
            f.write("Test translation content")
    
    def test_fix_stalled_files(self):
        """Test fixing stalled files."""
        # Mock the time.time function to return a fixed value
        with patch('time.time', return_value=1600010000):
            # Call the method
            fixed_count = self.maintenance.fix_stalled_files(timeout_minutes=30, reset_all=False)
            
            # Verify results
            self.assertEqual(fixed_count, 1, "Should have fixed 1 stalled file")
            
            # Check database state
            file2 = self.db_manager.execute_query("SELECT * FROM processing_status WHERE file_id = 'file2'")[0]
            self.assertEqual(file2['transcription_status'], 'failed', "Transcription status should be reset to failed")
    
    def test_fix_stalled_files_reset_all(self):
        """Test fixing all in-progress files regardless of time."""
        # Call the method with reset_all=True
        fixed_count = self.maintenance.fix_stalled_files(reset_all=True)
        
        # Verify results
        self.assertEqual(fixed_count, 2, "Should have fixed 2 stalled files (file2 and file3)")
    
    def test_fix_path_issues(self):
        """Test fixing path issues."""
        # Mock Path.exists to return True for all paths
        with patch('pathlib.Path.exists', return_value=True):
            # Call the method
            fixed_count = self.maintenance.fix_path_issues()
            
            # Verify results
            self.assertEqual(fixed_count, 1, "Should have fixed 1 path issue")
            
            # Check database state
            file3 = self.db_manager.execute_query("SELECT * FROM processing_status WHERE file_id = 'file3'")[0]
            self.assertEqual(file3['file_path'], '/path/to/file with spaces.mp3', "Path should be fixed")
    
    def test_fix_missing_transcripts(self):
        """Test fixing missing transcripts."""
        # Mock transcript file existence check
        def mock_exists(path):
            return 'file1' in str(path)
        
        with patch('pathlib.Path.exists', side_effect=mock_exists):
            # Call the method
            fixed_count = self.maintenance.fix_missing_transcripts()
            
            # Verify results
            self.assertEqual(fixed_count, 2, "Should find 2 missing transcripts (file3, file4)")
            
            # Check database state with reset_to_failed=True
            file4 = self.db_manager.execute_query("SELECT * FROM processing_status WHERE file_id = 'file4'")[0]
            self.assertEqual(file4['transcription_status'], 'failed', "Transcription status should be reset to failed")
    
    def test_mark_problem_files(self):
        """Test marking problematic files."""
        # Call the method with specific file IDs
        file_ids = ['file2', 'file5']
        marked_count = self.maintenance.mark_problem_files(file_ids=file_ids, status='qa_failed', reason='Test marking')
        
        # Verify results
        self.assertEqual(marked_count, 2, "Should have marked 2 files")
        
        # Check database state
        file2 = self.db_manager.execute_query("SELECT * FROM processing_status WHERE file_id = 'file2'")[0]
        file5 = self.db_manager.execute_query("SELECT * FROM processing_status WHERE file_id = 'file5'")[0]
        
        self.assertEqual(file2['status'], 'qa_failed', "File2 status should be qa_failed")
        self.assertEqual(file5['status'], 'qa_failed', "File5 status should be qa_failed")
    
    def test_verify_consistency(self):
        """Test verifying database and filesystem consistency."""
        # Create one test file
        self.create_test_files()
        
        # Mock file existence checks
        original_exists = Path.exists
        
        def mock_exists(path):
            # Only file1's transcript exists
            if 'file1' in str(path):
                return True
            elif 'test_transcript.txt' in str(path) or 'test_translation.txt' in str(path):
                return original_exists(path)
            return False
        
        with patch('pathlib.Path.exists', side_effect=mock_exists):
            # Call the method with report_only=True
            stats = self.maintenance.verify_consistency(report_only=True)
            
            # Verify results
            self.assertEqual(stats['missing_transcript'], 2, "Should find 2 missing transcripts")
            self.assertEqual(stats['status_mismatch'], 2, "Should find 2 files with status mismatch")


if __name__ == '__main__':
    unittest.main()