#!/usr/bin/env python3
"""
Tests for the DatabaseManager class.
"""

import os
import sys
import unittest
import tempfile
import threading
import time
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """
    Test suite for the DatabaseManager class.
    """
    
    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_file = os.path.join(self.temp_dir.name, 'test_manager.db')
        self.db_manager = DatabaseManager(self.db_file)
    
    def tearDown(self):
        """Clean up test database."""
        self.db_manager.close()
        self.temp_dir.cleanup()
    
    def test_add_media_file(self):
        """Test adding a media file to the database."""
        file_id = self.db_manager.add_media_file(
            file_path="/test/path/file.mp3",
            safe_filename="file.mp3",
            media_type="audio",
            file_size=1024,
            duration=60.5
        )
        
        # Verify file was added
        file_info = self.db_manager.get_file_by_id(file_id)
        self.assertIsNotNone(file_info)
        self.assertEqual(file_info['original_path'], "/test/path/file.mp3")
        self.assertEqual(file_info['safe_filename'], "file.mp3")
        self.assertEqual(file_info['media_type'], "audio")
        self.assertEqual(file_info['file_size'], 1024)
        self.assertEqual(file_info['duration'], 60.5)
    
    def test_update_status(self):
        """Test updating a file's processing status."""
        # Add a file
        file_id = self.db_manager.add_media_file(
            file_path="/test/path/file.mp3",
            safe_filename="file.mp3",
            media_type="audio"
        )
        
        # Update status
        self.db_manager.update_status(
            file_id=file_id,
            status="in-progress",
            transcription_status="completed"
        )
        
        # Verify status was updated
        file_status = self.db_manager.get_file_status(file_id)
        self.assertEqual(file_status['status'], "in-progress")
        self.assertEqual(file_status['transcription_status'], "completed")
    
    def test_log_error(self):
        """Test logging an error."""
        # Add a file
        file_id = self.db_manager.add_media_file(
            file_path="/test/path/file.mp3",
            safe_filename="file.mp3",
            media_type="audio"
        )
        
        # Log an error
        self.db_manager.log_error(
            file_id=file_id,
            process_stage="transcription",
            error_message="Test error",
            error_details="Detailed error info"
        )
        
        # Execute a query to get the error
        errors = self.db_manager.execute_query(
            "SELECT * FROM errors WHERE file_id = ?",
            (file_id,)
        )
        
        # Verify error was logged
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['file_id'], file_id)
        self.assertEqual(errors[0]['process_stage'], "transcription")
        self.assertEqual(errors[0]['error_message'], "Test error")
        self.assertEqual(errors[0]['error_details'], "Detailed error info")
    
    def test_execute_query(self):
        """Test executing a query."""
        # Add some files
        file_id1 = self.db_manager.add_media_file(
            file_path="/test/path/file1.mp3",
            safe_filename="file1.mp3",
            media_type="audio"
        )
        file_id2 = self.db_manager.add_media_file(
            file_path="/test/path/file2.mp3",
            safe_filename="file2.mp3",
            media_type="audio"
        )
        
        # Query files
        files = self.db_manager.execute_query(
            "SELECT * FROM media_files ORDER BY safe_filename"
        )
        
        # Verify query result
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]['safe_filename'], "file1.mp3")
        self.assertEqual(files[1]['safe_filename'], "file2.mp3")
    
    def test_execute_update(self):
        """Test executing an update query."""
        # Add a file
        file_id = self.db_manager.add_media_file(
            file_path="/test/path/file.mp3",
            safe_filename="file.mp3",
            media_type="audio"
        )
        
        # Update using execute_update
        rows_affected = self.db_manager.execute_update(
            "UPDATE media_files SET file_size = ? WHERE file_id = ?",
            (2048, file_id)
        )
        
        # Verify update
        self.assertEqual(rows_affected, 1)
        file_info = self.db_manager.get_file_by_id(file_id)
        self.assertEqual(file_info['file_size'], 2048)
    
    def test_concurrent_access(self):
        """Test concurrent access to the database."""
        num_threads = 5
        iterations_per_thread = 10
        
        # Add a file to work with
        file_id = self.db_manager.add_media_file(
            file_path="/test/path/concurrent.mp3",
            safe_filename="concurrent.mp3",
            media_type="audio"
        )
        
        # Track success count
        success_count = [0]
        error_count = [0]
        
        def worker():
            """Worker function that updates and reads the file."""
            try:
                for i in range(iterations_per_thread):
                    # Update file
                    self.db_manager.update_media_file(
                        file_id=file_id,
                        file_size=1000 + i
                    )
                    
                    # Read file
                    file_info = self.db_manager.get_file_by_id(file_id)
                    self.assertIsNotNone(file_info)
                    
                    # Log a test error
                    self.db_manager.log_error(
                        file_id=file_id,
                        process_stage=f"test-{threading.get_ident()}-{i}",
                        error_message=f"Test error {i}"
                    )
                
                # Increment success count
                with threading.Lock():
                    success_count[0] += 1
            
            except Exception as e:
                print(f"Thread error: {e}")
                with threading.Lock():
                    error_count[0] += 1
        
        # Create and start threads
        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify all threads succeeded
        self.assertEqual(success_count[0], num_threads)
        self.assertEqual(error_count[0], 0)
        
        # Verify we have the expected number of error records
        errors = self.db_manager.execute_query(
            "SELECT COUNT(*) as count FROM errors WHERE file_id = ?",
            (file_id,)
        )
        self.assertEqual(errors[0]['count'], num_threads * iterations_per_thread)
    
    def test_connection_pool_sharing(self):
        """Test that multiple instances share the same connection pool."""
        # Create another manager for the same database
        db_manager2 = DatabaseManager(self.db_file)
        
        # Verify they share the same pool
        self.assertIs(self.db_manager.pool, db_manager2.pool)
        
        # Clean up
        db_manager2.close()


if __name__ == '__main__':
    unittest.main()