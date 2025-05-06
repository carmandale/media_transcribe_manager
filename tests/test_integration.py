#!/usr/bin/env python3
"""
Integration tests for the database connection pooling feature.

This module tests the integration between the DatabaseConnectionPool and DatabaseManager
using real-world workflows to ensure everything functions correctly.
"""

import os
import sys
import unittest
import tempfile
import threading
import time
import concurrent.futures
from pathlib import Path
import sqlite3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_connection_pool import DatabaseConnectionPool
from db_manager import DatabaseManager


class TestIntegration(unittest.TestCase):
    """
    Integration tests for database connection pooling.
    """
    
    def setUp(self):
        """Set up test database and data."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_file = os.path.join(self.temp_dir.name, 'test_integration.db')
        self.db_manager = DatabaseManager(self.db_file)
        
        # Create test directory structure
        self.output_dir = os.path.join(self.temp_dir.name, 'output')
        self.transcripts_dir = os.path.join(self.output_dir, 'transcripts')
        os.makedirs(self.transcripts_dir, exist_ok=True)
        
        # Add test files
        self.test_files = [
            {'path': '/test/file1.mp3', 'filename': 'file1.mp3', 'type': 'audio', 'size': 1024, 'duration': 60.0},
            {'path': '/test/file2.mp3', 'filename': 'file2.mp3', 'type': 'audio', 'size': 2048, 'duration': 120.0},
            {'path': '/test/file3.mp4', 'filename': 'file3.mp4', 'type': 'video', 'size': 4096, 'duration': 180.0},
        ]
        
        self.file_ids = []
        for file_info in self.test_files:
            file_id = self.db_manager.add_media_file(
                file_path=file_info['path'],
                safe_filename=file_info['filename'],
                media_type=file_info['type'],
                file_size=file_info['size'],
                duration=file_info['duration']
            )
            self.file_ids.append(file_id)
            
            # Create dummy transcript file for testing
            base_name = os.path.splitext(file_info['filename'])[0]
            transcript_path = os.path.join(self.transcripts_dir, f"{base_name}.txt")
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"This is a test transcript for {file_info['filename']}.\n" * 10)
    
    def tearDown(self):
        """Clean up test database and files."""
        self.db_manager.close()
        self.temp_dir.cleanup()
    
    def test_concurrent_file_updates(self):
        """Test concurrent updates to files using the connection pool."""
        num_threads = 5
        update_successful = [0]
        lock = threading.Lock()
        
        def update_worker(file_id, thread_num):
            """Worker function that updates a file's metadata."""
            try:
                success = self.db_manager.update_media_file(
                    file_id=file_id,
                    file_size=1000 + thread_num
                )
                
                # Also update status
                status_success = self.db_manager.update_status(
                    file_id=file_id, 
                    status="in-progress",
                    transcription_status="completed"
                )
                
                # Log an error
                error_success = self.db_manager.log_error(
                    file_id=file_id,
                    process_stage=f"test-thread-{thread_num}",
                    error_message=f"Test error from thread {thread_num}",
                    error_details=f"Details from thread {thread_num}"
                )
                
                if success and status_success and error_success:
                    with lock:
                        update_successful[0] += 1
                        
            except Exception as e:
                logger.error(f"Error in thread {thread_num}: {e}")
        
        # Use ThreadPoolExecutor to run updates concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit tasks
            futures = []
            for i in range(num_threads):
                # Use a different file for each thread to avoid contention
                file_id = self.file_ids[i % len(self.file_ids)]
                futures.append(executor.submit(update_worker, file_id, i))
            
            # Wait for all tasks to complete
            concurrent.futures.wait(futures)
        
        # Verify all updates were successful
        self.assertEqual(update_successful[0], num_threads, 
                         f"Only {update_successful[0]} of {num_threads} threads completed successfully")
    
    def test_parallel_queries(self):
        """Test running parallel queries against the database using the connection pool."""
        num_threads = 10
        queries_successful = [0]
        lock = threading.Lock()
        
        def query_worker(thread_num):
            """Worker function that runs queries."""
            try:
                # Get a file by ID
                file = self.db_manager.get_file_by_id(self.file_ids[thread_num % len(self.file_ids)])
                
                # Get file status
                status = self.db_manager.get_file_status(self.file_ids[thread_num % len(self.file_ids)])
                
                # Get files by status
                files = self.db_manager.get_files_by_status('pending')
                
                # All queries succeeded
                if file and status and files is not None:
                    with lock:
                        queries_successful[0] += 1
                        
            except Exception as e:
                logger.error(f"Error in query thread {thread_num}: {e}")
        
        # Use ThreadPoolExecutor to run queries concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit tasks
            futures = []
            for i in range(num_threads):
                futures.append(executor.submit(query_worker, i))
            
            # Wait for all tasks to complete
            concurrent.futures.wait(futures)
        
        # Verify all queries were successful
        self.assertEqual(queries_successful[0], num_threads, 
                         f"Only {queries_successful[0]} of {num_threads} threads completed successfully")
        
    def test_mixed_operations(self):
        """Test a mix of read and write operations using the connection pool."""
        num_threads = 8
        operations_successful = [0]
        lock = threading.Lock()
        
        def mixed_worker(thread_num):
            """Worker function that performs a mix of operations."""
            try:
                file_id = self.file_ids[thread_num % len(self.file_ids)]
                
                # Perform different operations based on thread number
                if thread_num % 3 == 0:
                    # Write operation - update file
                    success = self.db_manager.update_media_file(
                        file_id=file_id,
                        file_size=2000 + thread_num
                    )
                elif thread_num % 3 == 1:
                    # Read operation - get file status
                    result = self.db_manager.get_file_status(file_id)
                    success = result is not None
                else:
                    # Mixed - log error and read error count
                    self.db_manager.log_error(
                        file_id=file_id,
                        process_stage=f"test-mixed-{thread_num}",
                        error_message=f"Test mixed error {thread_num}"
                    )
                    
                    errors = self.db_manager.execute_query(
                        "SELECT COUNT(*) as count FROM errors WHERE file_id = ?",
                        (file_id,)
                    )
                    success = errors and 'count' in errors[0]
                
                if success:
                    with lock:
                        operations_successful[0] += 1
                        
            except Exception as e:
                logger.error(f"Error in mixed thread {thread_num}: {e}")
        
        # Use ThreadPoolExecutor to run operations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit tasks
            futures = []
            for i in range(num_threads):
                futures.append(executor.submit(mixed_worker, i))
            
            # Wait for all tasks to complete
            concurrent.futures.wait(futures)
        
        # Verify all operations were successful
        self.assertEqual(operations_successful[0], num_threads, 
                         f"Only {operations_successful[0]} of {num_threads} operations completed successfully")
    
    def test_connection_pool_sharing(self):
        """Test that multiple managers share the same connection pool for the same database."""
        # Create multiple database managers pointing to the same DB file
        manager1 = self.db_manager
        manager2 = DatabaseManager(self.db_file)
        manager3 = DatabaseManager(self.db_file)
        
        # Verify they share the same pool instance
        self.assertIs(manager1.pool, manager2.pool)
        self.assertIs(manager2.pool, manager3.pool)
        
        # Verify they can access the same data
        file_id = self.file_ids[0]
        
        file1 = manager1.get_file_by_id(file_id)
        file2 = manager2.get_file_by_id(file_id)
        file3 = manager3.get_file_by_id(file_id)
        
        self.assertEqual(file1['file_id'], file_id)
        self.assertEqual(file2['file_id'], file_id)
        self.assertEqual(file3['file_id'], file_id)
        
        # Clean up
        manager2.close()
        manager3.close()
    
    def test_resource_management(self):
        """Test proper management of database connections and resources."""
        # Make a series of requests to potentially exhaust connections if they're not managed
        for _ in range(50):
            # Mix of read and write operations
            file_id = self.file_ids[0]
            
            # Read operation
            self.db_manager.get_file_status(file_id)
            
            # Write operation
            self.db_manager.update_status(
                file_id=file_id,
                status="in-progress",
                transcription_status="in-progress"
            )
            
            # Another read
            errors = self.db_manager.execute_query(
                "SELECT COUNT(*) as count FROM errors"
            )
        
        # Verify we can still get connections from the pool
        self.assertLess(len(self.db_manager.pool._in_use), self.db_manager.pool.max_connections)
        
        # Verify we can still execute queries
        result = self.db_manager.execute_query("SELECT COUNT(*) as count FROM media_files")
        self.assertEqual(result[0]['count'], len(self.test_files))


if __name__ == '__main__':
    unittest.main()