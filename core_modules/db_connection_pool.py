#!/usr/bin/env python3
"""
Database Connection Pool for Media Transcription and Translation Tool
--------------------------------------------------------------------
Provides a thread-safe connection pool for SQLite database access
with automatic connection management and cleanup.
"""

import os
import sqlite3
import logging
import threading
import time
import weakref
import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """
    Thread-safe connection pool for SQLite database access.
    
    This class manages a pool of database connections, ensuring:
    - Thread-safety for multiple threads accessing the database
    - Connection reuse to minimize overhead
    - Proper connection cleanup to prevent resource leaks
    - Automatic connection recovery after errors
    """
    
    def __init__(self, db_file: str, max_connections: int = 10, timeout: float = 30.0):
        """
        Initialize the database connection pool.
        
        Args:
            db_file: Path to SQLite database file
            max_connections: Maximum number of connections in the pool
            timeout: Maximum time to wait for a connection in seconds
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)
        
        self.db_file = db_file
        self.max_connections = max_connections
        self.timeout = timeout
        
        # Connection pool storage
        self._connections = []
        self._in_use = set()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Track connections created by this pool
        self._connection_count = 0
        
        # Finalizer to handle connections that weren't properly closed
        self._finalizer = weakref.finalize(
            self, self._close_connections, self._connections, self._in_use
        )
        
        logger.debug(f"Initialized database connection pool for {db_file}")
    
    def _close_connections(self, connections, in_use):
        """
        Close all connections when the pool is garbage collected.
        
        This method is called by the finalizer when the pool is garbage collected.
        It ensures all connections are properly closed to prevent resource leaks.
        """
        with self._lock:
            for conn in connections:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing connection during cleanup: {e}")
            
            for conn in in_use:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing in-use connection during cleanup: {e}")
            
            logger.debug(f"Closed {len(connections) + len(in_use)} connections during cleanup")
    
    def _create_connection(self) -> sqlite3.Connection:
        """
        Create a new SQLite connection.
        
        Returns:
            New SQLite connection object
        """
        try:
            # Create connection with check_same_thread=False for thread safety
            thread_id = threading.get_ident()
            conn = sqlite3.connect(self.db_file, check_same_thread=False)
            
            # Register adapter for datetime objects (to address deprecation warning)
            sqlite3.register_adapter(datetime.datetime, lambda dt: dt.isoformat())
            
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Set row factory for dict-like access
            conn.row_factory = sqlite3.Row
            
            # We can't store attributes directly on the connection object
            # Log the thread ID instead for debugging
            logger.debug(f"Connection created in thread {thread_id}")
            
            # Track connection count
            with self._lock:
                self._connection_count += 1
                
            logger.debug(f"Created new database connection for thread {thread_id} ({self._connection_count} total)")
            return conn
            
        except sqlite3.Error as e:
            logger.error(f"Error creating database connection: {e}")
            raise
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get a connection from the pool.
        
        This method either returns an available connection from the pool
        or creates a new connection if none are available and the pool isn't full.
        
        Returns:
            SQLite connection object
        
        Raises:
            TimeoutError: If no connection is available within the timeout period
        """
        # Get thread ID for thread-local connections
        thread_id = threading.get_ident()
        
        # Check if thread already has a connection
        if hasattr(self._local, 'connection'):
            # Return the existing connection for this thread
            return self._local.connection
        
        # Get the current time for timeout tracking
        start_time = time.time()
        
        while True:
            with self._lock:
                # Check for available connection in the pool
                if self._connections:
                    conn = self._connections.pop()
                    self._in_use.add(conn)
                    self._local.connection = conn
                    return conn
                
                # Create new connection if pool isn't full
                if len(self._in_use) < self.max_connections:
                    # Create a connection with check_same_thread=False for the pool
                    # This is safe because we manually manage thread access
                    conn = sqlite3.connect(self.db_file, check_same_thread=False)
                    
                    # Register adapter for datetime objects (to address deprecation warning)
                    sqlite3.register_adapter(datetime.datetime, lambda dt: dt.isoformat())
                    
                    # Enable foreign keys
                    conn.execute("PRAGMA foreign_keys = ON")
                    
                    # Set row factory for dict-like access
                    conn.row_factory = sqlite3.Row
                    
                    # Track connection count
                    self._connection_count += 1
                    
                    # We can't store attributes directly on the connection object
                    # Log the thread ID instead for debugging
                    logger.debug(f"Connection created in thread {thread_id}")
                    
                    logger.debug(f"Created new database connection for thread {thread_id} ({self._connection_count} total)")
                    
                    self._in_use.add(conn)
                    self._local.connection = conn
                    return conn
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= self.timeout:
                logger.error(f"Timeout waiting for database connection after {elapsed:.2f} seconds")
                raise TimeoutError(f"Timeout waiting for database connection after {elapsed:.2f} seconds")
            
            # Wait and try again
            time.sleep(0.1)
    
    def release_connection(self, conn: Optional[sqlite3.Connection] = None) -> None:
        """
        Release a connection back to the pool.
        
        Args:
            conn: Connection to release (uses thread-local if None)
        """
        # If no connection specified, use thread-local
        if conn is None:
            if hasattr(self._local, 'connection'):
                conn = self._local.connection
                delattr(self._local, 'connection')
            else:
                return
        
        with self._lock:
            # Only handle connections tracked by this pool
            if conn in self._in_use:
                self._in_use.remove(conn)
                
                # Test the connection to ensure it's still usable
                try:
                    conn.execute("SELECT 1").fetchone()
                    # Connection is good, return to pool
                    self._connections.append(conn)
                    logger.debug(f"Released connection back to pool (available: {len(self._connections)}, in use: {len(self._in_use)})")
                except sqlite3.Error as e:
                    # Connection is bad, close it
                    logger.debug(f"Closing bad connection: {e}")
                    try:
                        conn.close()
                    except Exception as close_err:
                        logger.debug(f"Error closing connection: {close_err}")
                        
                # Always clear thread-local reference
                if hasattr(self._local, 'connection') and self._local.connection == conn:
                    delattr(self._local, 'connection')
    
    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            # Close all available connections
            for conn in self._connections:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            
            # Clear the pool
            self._connections.clear()
            
            # Close all in-use connections
            in_use = list(self._in_use)
            for conn in in_use:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing in-use connection: {e}")
                self._in_use.remove(conn)
            
            logger.info(f"Closed all database connections ({self._connection_count} total)")
    
    def execute_query(self, query: str, params: Any = None) -> list:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query to execute
            params: Parameters for query (optional)
            
        Returns:
            List of results
        """
        thread_id = threading.get_ident()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Get column names if available
            if cursor.description:
                columns = [description[0] for description in cursor.description]
                results = []
                for row in cursor.fetchall():
                    if isinstance(row, sqlite3.Row):
                        results.append(dict(row))
                    else:
                        results.append({columns[i]: row[i] for i in range(len(columns))})
            else:
                results = []
                
            return results
        except sqlite3.Error as e:
            logger.error(f"Error executing query in thread {thread_id}: {e}\nQuery: {query}\nParams: {params}")
            # Don't re-raise; we don't want worker threads to crash
            return []
        finally:
            self.release_connection(conn)
    
    def execute_update(self, query: str, params: Any = None) -> int:
        """
        Execute an update query and commit changes.
        
        Args:
            query: SQL query to execute
            params: Parameters for query (optional)
            
        Returns:
            Number of rows affected
        """
        thread_id = threading.get_ident()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            rows_affected = cursor.rowcount
            logger.debug(f"Update in thread {thread_id} affected {rows_affected} rows")
            return rows_affected
        except sqlite3.Error as e:
            try:
                conn.rollback()
            except sqlite3.Error as rollback_error:
                logger.error(f"Error during rollback in thread {thread_id}: {rollback_error}")
                
            logger.error(f"Error executing update in thread {thread_id}: {e}\nQuery: {query}\nParams: {params}")
            # Don't re-raise in worker threads
            return 0
        finally:
            self.release_connection(conn)
    
    def execute_transaction(self, queries: list) -> bool:
        """
        Execute multiple queries as a transaction.
        
        Args:
            queries: List of (query, params) tuples
            
        Returns:
            True if transaction succeeded
        """
        thread_id = threading.get_ident()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            for i, (query, params) in enumerate(queries):
                try:
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                except sqlite3.Error as query_error:
                    logger.error(f"Error executing query {i} in transaction (thread {thread_id}): {query_error}")
                    raise
            
            conn.commit()
            logger.debug(f"Transaction with {len(queries)} queries completed successfully in thread {thread_id}")
            return True
        except sqlite3.Error as e:
            try:
                conn.rollback()
            except sqlite3.Error as rollback_error:
                logger.error(f"Error during rollback in thread {thread_id}: {rollback_error}")
                
            logger.error(f"Error executing transaction in thread {thread_id}: {e}")
            # We don't re-raise the exception to prevent crashes in worker threads
            return False
        finally:
            self.release_connection(conn)
    
    def __enter__(self):
        """Context manager enter."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_all()
        return False  # Don't suppress exceptions