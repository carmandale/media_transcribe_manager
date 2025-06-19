#!/usr/bin/env python3
"""Test script to check database schema and identify remaining issues."""

import sys
sys.path.append('.')

from scribe.database import Database

def test_database_schema():
    """Test if all required tables exist."""
    print("Testing database schema...")
    
    db = Database(':memory:')
    conn = db._get_connection()
    
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Found tables: {tables}")
    
    required_tables = ['media_files', 'processing_status', 'errors', 'quality_evaluations']
    missing_tables = []
    
    for table in required_tables:
        if table not in tables:
            missing_tables.append(table)
    
    if missing_tables:
        print(f"❌ Missing tables: {missing_tables}")
        return False
    else:
        print("✅ All required tables found")
        return True

def test_quality_evaluations_schema():
    """Test quality_evaluations table schema if it exists."""
    print("\nTesting quality_evaluations table schema...")
    
    db = Database(':memory:')
    conn = db._get_connection()
    
    try:
        cursor = conn.execute("PRAGMA table_info(quality_evaluations)")
        columns = cursor.fetchall()
        
        if columns:
            print("✅ quality_evaluations table schema:")
            for col in columns:
                print(f"  - {col[1]} {col[2]} {'NOT NULL' if col[3] else ''}")
            return True
        else:
            print("❌ quality_evaluations table not found")
            return False
    except Exception as e:
        print(f"❌ Error checking quality_evaluations schema: {e}")
        return False

if __name__ == "__main__":
    schema_ok = test_database_schema()
    quality_table_ok = test_quality_evaluations_schema()
    
    if schema_ok and quality_table_ok:
        print("\n✅ Database schema is complete")
        sys.exit(0)
    else:
        print("\n❌ Database schema issues found")
        sys.exit(1)
