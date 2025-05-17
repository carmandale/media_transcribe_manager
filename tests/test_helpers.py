#!/usr/bin/env python3
"""
Test helpers for the Scribe project tests.
"""

# Add execute_update method to DatabaseManager for tests
import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_manager import DatabaseManager

# Add missing methods to DatabaseManager for tests
if not hasattr(DatabaseManager, 'execute_update'):
    def execute_update(self, query, params=None):
        """Execute an update query and commit changes."""
        conn = sqlite3.connect(self.db_file)
        try:
            if params:
                conn.execute(query, params)
            else:
                conn.execute(query)
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # Add method to DatabaseManager
    setattr(DatabaseManager, 'execute_update', execute_update)

# Import sqlite3 after adding method
import sqlite3