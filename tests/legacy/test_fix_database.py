#!/usr/bin/env python3
"""
Test suite for database status fixing functionality.
"""

import unittest
import tempfile
import shutil
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from fix_database_status import (
    DatabaseStatusFixer, UpdateRecord, FixReport
)


class TestDatabaseStatusFixer(unittest.TestCase):
    """Test cases for DatabaseStatusFixer class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create test database
        self.db_path = self.test_path / "test_media_tracking.db"
        self._create_test_database()
        
        # Create test audit report
        self.audit_report_path = self.test_path / "test_audit_report.json"
        self._create_test_audit_report()
        
        # Create fixer instance
        self.fixer = DatabaseStatusFixer(
            db_path=self.db_path,
            audit_report_path=self.audit_report_path,
            dry_run=False
        )
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _create_test_database(self):
        """Create a test database with sample data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE media_files (
                file_id TEXT PRIMARY KEY,
                safe_filename TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE processing_status (
                file_id TEXT PRIMARY KEY,
                status TEXT,
                translation_en_status TEXT,
                translation_de_status TEXT,
                translation_he_status TEXT,
                last_updated TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES media_files(file_id)
            )
        ''')
        
        # Insert test data
        test_files = [
            # Valid Hebrew translations
            ('valid_he_1', 'valid1.mp4'),
            ('valid_he_2', 'valid2.mp4'),
            
            # Placeholder Hebrew files (marked complete but have placeholders)
            ('placeholder_he_1', 'placeholder1.mp4'),
            ('placeholder_he_2', 'placeholder2.mp4'),
            ('placeholder_he_3', 'placeholder3.mp4'),
            
            # Missing Hebrew files (marked complete but don't exist)
            ('missing_he_1', 'missing1.mp4'),
            ('missing_he_2', 'missing2.mp4'),
        ]
        
        for file_id, filename in test_files:
            cursor.execute(
                'INSERT INTO media_files (file_id, safe_filename) VALUES (?, ?)',
                (file_id, filename)
            )
            
            # All marked as completed initially
            cursor.execute('''
                INSERT INTO processing_status 
                (file_id, status, translation_en_status, translation_de_status, 
                 translation_he_status, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (file_id, 'completed', 'completed', 'completed', 'completed', datetime.now()))
        
        conn.commit()
        conn.close()
    
    def _create_test_audit_report(self):
        """Create a test audit report."""
        audit_data = {
            "discrepancies": {
                "placeholder_file": [
                    {"file_id": "placeholder_he_1", "language": "he", "details": {}},
                    {"file_id": "placeholder_he_2", "language": "he", "details": {}},
                    {"file_id": "placeholder_he_3", "language": "he", "details": {}},
                ],
                "missing_file": [
                    {"file_id": "missing_he_1", "language": "he", "details": {}},
                    {"file_id": "missing_he_2", "language": "he", "details": {}},
                ]
            }
        }
        
        with open(self.audit_report_path, 'w') as f:
            json.dump(audit_data, f)
    
    def test_backup_database(self):
        """Test database backup functionality."""
        backup_path = self.fixer.backup_database()
        
        self.assertTrue(backup_path.exists())
        self.assertTrue(backup_path.name.startswith("media_tracking_before_fix_"))
        self.assertTrue(backup_path.suffix == ".db")
        
        # Verify backup is identical to original
        self.assertEqual(
            backup_path.stat().st_size,
            self.db_path.stat().st_size
        )
    
    def test_backup_database_dry_run(self):
        """Test database backup in dry run mode."""
        fixer = DatabaseStatusFixer(
            db_path=self.db_path,
            audit_report_path=self.audit_report_path,
            dry_run=True
        )
        
        backup_path = fixer.backup_database()
        self.assertFalse(backup_path.exists())  # Should not create actual backup
    
    def test_parse_audit_report(self):
        """Test parsing of audit report."""
        placeholder_files, missing_files = self.fixer.parse_audit_report()
        
        self.assertEqual(len(placeholder_files), 3)
        self.assertEqual(len(missing_files), 2)
        
        self.assertIn("placeholder_he_1", placeholder_files)
        self.assertIn("placeholder_he_2", placeholder_files)
        self.assertIn("placeholder_he_3", placeholder_files)
        
        self.assertIn("missing_he_1", missing_files)
        self.assertIn("missing_he_2", missing_files)
    
    def test_get_database_stats(self):
        """Test getting database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats = self.fixer.get_database_stats(conn)
        
        # Check structure
        self.assertIn('en', stats)
        self.assertIn('de', stats)
        self.assertIn('he', stats)
        
        # Check Hebrew stats (all marked complete initially)
        he_stats = stats['he']
        self.assertEqual(he_stats['total'], 7)
        self.assertEqual(he_stats['completed'], 7)
        self.assertEqual(he_stats['completion_percentage'], '100.0%')
    
    def test_fix_placeholder_files(self):
        """Test fixing placeholder files."""
        with self.fixer.db_transaction() as conn:
            updated = self.fixer.fix_placeholder_files(
                conn, 
                ['placeholder_he_1', 'placeholder_he_2']
            )
        
        self.assertEqual(updated, 2)
        
        # Verify database was updated
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT translation_he_status FROM processing_status WHERE file_id = ?",
            ('placeholder_he_1',)
        )
        status = cursor.fetchone()[0]
        self.assertEqual(status, 'pending')
        
        conn.close()
        
        # Check update records
        self.assertEqual(len(self.fixer.update_records), 2)
        self.assertEqual(self.fixer.update_records[0].new_status, 'pending')
        self.assertEqual(self.fixer.update_records[0].reason, 'File contains placeholder text')
    
    def test_fix_missing_files(self):
        """Test fixing missing files."""
        with self.fixer.db_transaction() as conn:
            updated = self.fixer.fix_missing_files(
                conn,
                ['missing_he_1', 'missing_he_2']
            )
        
        self.assertEqual(updated, 2)
        
        # Verify database was updated
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT translation_he_status FROM processing_status WHERE file_id = ?",
            ('missing_he_1',)
        )
        status = cursor.fetchone()[0]
        self.assertEqual(status, 'failed')
        
        conn.close()
        
        # Check update records
        self.assertEqual(len(self.fixer.update_records), 2)
        self.assertEqual(self.fixer.update_records[0].new_status, 'failed')
        self.assertEqual(self.fixer.update_records[0].reason, 'Translation file missing')
    
    def test_transaction_rollback_on_error(self):
        """Test that transactions roll back on error."""
        # Create a fixer with an invalid file ID in the audit report
        audit_data = {
            "discrepancies": {
                "placeholder_file": [
                    {"file_id": "placeholder_he_1", "language": "he", "details": {}},
                    {"file_id": "INVALID_ID", "language": "he", "details": {}},  # This will cause error
                ],
                "missing_file": []
            }
        }
        
        invalid_audit_path = self.test_path / "invalid_audit.json"
        with open(invalid_audit_path, 'w') as f:
            json.dump(audit_data, f)
        
        fixer = DatabaseStatusFixer(
            db_path=self.db_path,
            audit_report_path=invalid_audit_path,
            dry_run=False
        )
        
        # Try to fix - should handle error gracefully
        placeholder_files, _ = fixer.parse_audit_report()
        
        with fixer.db_transaction() as conn:
            updated = fixer.fix_placeholder_files(conn, placeholder_files)
        
        # Should have updated only the valid file
        self.assertEqual(updated, 1)
        self.assertEqual(len(fixer.errors), 1)
        
        # Verify the valid update was applied
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT translation_he_status FROM processing_status WHERE file_id = ?",
            ('placeholder_he_1',)
        )
        status = cursor.fetchone()[0]
        self.assertEqual(status, 'pending')  # Should be updated
        
        conn.close()
    
    def test_run_complete_fix(self):
        """Test running the complete fix process."""
        report = self.fixer.run()
        
        # Check report structure
        self.assertIsInstance(report, FixReport)
        self.assertEqual(report.records_updated, 5)  # 3 placeholder + 2 missing
        self.assertEqual(report.placeholder_files_fixed, 3)
        self.assertEqual(report.missing_files_fixed, 2)
        
        # Check before/after stats
        self.assertEqual(report.before_stats['he']['completion_percentage'], '100.0%')
        self.assertNotEqual(report.after_stats['he']['completion_percentage'], '100.0%')
        
        # Calculate expected completion: 2 valid out of 7 total = 28.6%
        expected_percentage = f"{(2 / 7 * 100):.1f}%"
        self.assertEqual(report.after_stats['he']['completion_percentage'], expected_percentage)
        
        # English and German should remain unchanged
        self.assertEqual(
            report.before_stats['en']['completion_percentage'],
            report.after_stats['en']['completion_percentage']
        )
        self.assertEqual(
            report.before_stats['de']['completion_percentage'],
            report.after_stats['de']['completion_percentage']
        )
    
    def test_dry_run_mode(self):
        """Test dry run mode doesn't modify database."""
        fixer = DatabaseStatusFixer(
            db_path=self.db_path,
            audit_report_path=self.audit_report_path,
            dry_run=True
        )
        
        # Get initial state
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT translation_he_status FROM processing_status WHERE file_id = ?",
                      ('placeholder_he_1',))
        initial_status = cursor.fetchone()[0]
        conn.close()
        
        # Run fix in dry run mode
        report = fixer.run()
        
        # Verify no changes were made
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT translation_he_status FROM processing_status WHERE file_id = ?",
                      ('placeholder_he_1',))
        final_status = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(initial_status, final_status)
        self.assertEqual(initial_status, 'completed')  # Should still be completed
        
        # Report should still show what would have been done
        self.assertEqual(report.records_updated, 5)
    
    def test_save_report(self):
        """Test saving fix report."""
        report = self.fixer.run()
        
        report_path = self.test_path / "test_fix_report.json"
        self.fixer.save_report(report, report_path)
        
        self.assertTrue(report_path.exists())
        
        # Load and verify report
        with open(report_path, 'r') as f:
            saved_report = json.load(f)
        
        self.assertEqual(saved_report['records_updated'], 5)
        self.assertEqual(saved_report['placeholder_files_fixed'], 3)
        self.assertEqual(saved_report['missing_files_fixed'], 2)
    
    def test_missing_database_file(self):
        """Test error handling for missing database."""
        with self.assertRaises(FileNotFoundError):
            DatabaseStatusFixer(
                db_path=Path("/nonexistent/database.db"),
                audit_report_path=self.audit_report_path
            )
    
    def test_missing_audit_report(self):
        """Test error handling for missing audit report."""
        with self.assertRaises(FileNotFoundError):
            DatabaseStatusFixer(
                db_path=self.db_path,
                audit_report_path=Path("/nonexistent/audit.json")
            )


class TestRealDatabaseStructure(unittest.TestCase):
    """Test with production-like database structure."""
    
    def setUp(self):
        """Set up test with production schema."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create production-like database
        self.db_path = self.test_path / "media_tracking.db"
        self._create_production_schema()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.test_dir)
    
    def _create_production_schema(self):
        """Create database with production schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Production schema
        cursor.execute('''
            CREATE TABLE media_files (
                file_id TEXT PRIMARY KEY,
                original_path TEXT NOT NULL,
                safe_filename TEXT NOT NULL,
                file_size INTEGER,
                duration REAL,
                checksum TEXT,
                media_type TEXT,
                detected_language TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE processing_status (
                file_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                transcription_status TEXT,
                translation_en_status TEXT,
                translation_he_status TEXT,
                translation_de_status TEXT DEFAULT 'not_started',
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                last_updated TIMESTAMP,
                attempts INTEGER DEFAULT 0,
                FOREIGN KEY (file_id) REFERENCES media_files(file_id)
            )
        ''')
        
        # Add sample data
        cursor.execute(
            "INSERT INTO media_files (file_id, original_path, safe_filename) VALUES (?, ?, ?)",
            ('test_file_1', '/path/to/file1.mp4', 'file1.mp4')
        )
        
        cursor.execute('''
            INSERT INTO processing_status 
            (file_id, status, translation_he_status, last_updated)
            VALUES (?, ?, ?, ?)
        ''', ('test_file_1', 'completed', 'completed', datetime.now()))
        
        conn.commit()
        conn.close()
    
    def test_production_schema_compatibility(self):
        """Test that fixer works with production schema."""
        # Create minimal audit report
        audit_data = {
            "discrepancies": {
                "placeholder_file": [
                    {"file_id": "test_file_1", "language": "he", "details": {}}
                ],
                "missing_file": []
            }
        }
        
        audit_path = self.test_path / "audit.json"
        with open(audit_path, 'w') as f:
            json.dump(audit_data, f)
        
        # Create fixer and run
        fixer = DatabaseStatusFixer(
            db_path=self.db_path,
            audit_report_path=audit_path,
            dry_run=False
        )
        
        with fixer.db_transaction() as conn:
            updated = fixer.fix_placeholder_files(conn, ['test_file_1'])
        
        self.assertEqual(updated, 1)
        
        # Verify update
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT translation_he_status FROM processing_status WHERE file_id = ?",
            ('test_file_1',)
        )
        status = cursor.fetchone()[0]
        self.assertEqual(status, 'pending')
        conn.close()


if __name__ == "__main__":
    unittest.main()