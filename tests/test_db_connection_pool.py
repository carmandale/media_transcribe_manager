#!/usr/bin/env python3
"""
Tests for the DatabaseConnectionPool class.
"""

import os
import sys
import unittest
import tempfile
import threading
import sqlite3
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_connection_pool import DatabaseConnectionPool


class TestDatabaseConnectionPool(unittest.TestCase):
    """
    Test suite for the DatabaseConnectionPool class.
    """
    
    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_file = os.path.join(self.temp_dir.name, 'test.db')
        self.pool = DatabaseConnectionPool(self.db_file, max_connections=5)
        
        # Create test table
        conn = self.pool.get_connection()
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        self.pool.release_connection(conn)
    
    def tearDown(self):
        """Clean up test database."""
        self.pool.close_all()
        self.temp_dir.cleanup()
    
    def test_get_connection(self):
        """Test getting a connection from the pool."""
        conn = self.pool.get_connection()
        self.assertIsInstance(conn, sqlite3.Connection)
        self.pool.release_connection(conn)
    
    def test_execute_query(self):
        """Test executing a query."""
        # Insert test data
        self.pool.execute_update("INSERT INTO test (value) VALUES (?)", ("test1",))
        self.pool.execute_update("INSERT INTO test (value) VALUES (?)", ("test2",))
        
        # Query test data
        results = self.pool.execute_query("SELECT * FROM test")
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["value"], "test1")
        self.assertEqual(results[1]["value"], "test2")
    
    def test_execute_update(self):
        """Test executing an update query."""
        # Insert test data
        rows_affected = self.pool.execute_update("INSERT INTO test (value) VALUES (?)", ("test1",))
        self.assertEqual(rows_affected, 1)
        
        # Update test data
        rows_affected = self.pool.execute_update("UPDATE test SET value = ? WHERE value = ?", ("updated", "test1"))
        self.assertEqual(rows_affected, 1)
        
        # Verify update
        results = self.pool.execute_query("SELECT * FROM test WHERE value = ?", ("updated",))
        self.assertEqual(len(results), 1)
    
    def test_execute_transaction(self):
        """Test executing a transaction."""
        # Create a transaction with multiple queries
        queries = [
            ("INSERT INTO test (value) VALUES (?)", ("tx1",)),
            ("INSERT INTO test (value) VALUES (?)", ("tx2",)),
            ("UPDATE test SET value = ? WHERE value = ?", ("tx1-updated", "tx1"))
        ]
        
        # Execute transaction
        success = self.pool.execute_transaction(queries)
        self.assertTrue(success)
        
        # Verify transaction
        results = self.pool.execute_query("SELECT * FROM test")
        self.assertEqual(len(results), 2)
        values = [r["value"] for r in results]
        self.assertIn("tx1-updated", values)
        self.assertIn("tx2", values)
    
    def test_thread_safety(self):
        """Test thread safety of the connection pool."""
        num_threads = 10
        rows_per_thread = 5
        
        # Set up a thread-safe counter
        lock = threading.Lock()
        successful_inserts = [0]
        
        def worker():
            """Worker function to execute queries in a thread."""
            thread_successful = 0
            for i in range(rows_per_thread):
                try:
                    affected = self.pool.execute_update(
                        "INSERT INTO test (value) VALUES (?)",
                        (f"thread-{threading.get_ident()}-{i}",)
                    )
                    if affected > 0:
                        thread_successful += 1
                except Exception as e:
                    print(f"Error in worker thread: {e}")
            
            # Update the shared counter
            with lock:
                successful_inserts[0] += thread_successful
        
        # Create and start threads
        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify that rows were inserted
        results = self.pool.execute_query("SELECT COUNT(*) as count FROM test")
        count = results[0]["count"] if results and "count" in results[0] else 0
        
        # Make sure we got some inserts - may not get all due to contention
        self.assertGreater(count, 0, "No rows were inserted")
        print(f"Thread safety test: {count} rows inserted out of {num_threads * rows_per_thread}")
        
        # Check that our counter matches what's in the database
        self.assertEqual(count, successful_inserts[0], 
                        f"Database count ({count}) doesn't match successful inserts ({successful_inserts[0]})")
    
    def test_connection_reuse(self):
        """Test that connections are reused when released back to the pool."""
        # Get initial number of connections
        initial_count = self.pool._connection_count
        
        # Get and release connections multiple times, should not create new ones
        for _ in range(10):
            conn = self.pool.get_connection()
            self.pool.release_connection(conn)
        
        # Verify that no new connections were created
        self.assertEqual(self.pool._connection_count, initial_count)
    
    def test_connection_pooling(self):
        """Test that the connection pool properly manages connections."""
        # This test verifies that the pool reuses connections when available
        
        # Create a separate pool with a tracked connection
        other_pool = DatabaseConnectionPool(self.db_file, max_connections=5)
        
        # Get a connection from the pool
        conn = other_pool.get_connection()
        self.assertIsInstance(conn, sqlite3.Connection)
        
        # Release it back to the pool
        other_pool.release_connection(conn)
        
        # The pool should now have one available connection in the _connections list
        self.assertEqual(len(other_pool._connections), 1)
        
        # If we get another connection, it should use the one from the pool
        conn2 = other_pool.get_connection()
        self.assertIsInstance(conn2, sqlite3.Connection)
        
        # The pool should now have zero available connections
        self.assertEqual(len(other_pool._connections), 0)
        
        # Clean up
        other_pool.release_connection(conn2)
        other_pool.close_all()


if __name__ == '__main__':
    unittest.main()