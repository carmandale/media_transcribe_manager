#!/usr/bin/env python3
"""
Test suite for the Scribe backup system.
"""

import unittest
import tempfile
import shutil
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from create_backup import ScribeBackup


class TestScribeBackup(unittest.TestCase):
    """Test cases for ScribeBackup class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir)
        
        # Create test structure
        self.db_path = self.test_root / "media_tracking.db"
        self.output_dir = self.test_root / "output"
        self.output_dir.mkdir()
        
        # Create test database
        self._create_test_database()
        
        # Create test translation files
        self._create_test_translations()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _create_test_database(self):
        """Create a minimal test database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_files (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT
            )
        ''')
        cursor.execute("INSERT INTO media_files (filename, status) VALUES (?, ?)", 
                      ("test_file.mp4", "completed"))
        conn.commit()
        conn.close()
    
    def _create_test_translations(self):
        """Create test translation files."""
        # Create a few test items
        for i in range(3):
            item_dir = self.output_dir / f"item_{i}"
            item_dir.mkdir()
            
            # Create translation files
            (item_dir / "transcription_original.txt").write_text(f"Original text {i}")
            (item_dir / "transcription_en.txt").write_text(f"English text {i}")
            (item_dir / "transcription_he.txt").write_text(f"Hebrew text {i}")
            (item_dir / "transcription_de.txt").write_text(f"German text {i}")
    
    def test_create_timestamped_backup_dir(self):
        """Test creating timestamped backup directory."""
        backup = ScribeBackup(self.test_root)
        backup_dir = backup.create_timestamped_backup_dir()
        
        self.assertTrue(backup_dir.exists())
        self.assertTrue(backup_dir.is_dir())
        # Check timestamp format
        timestamp = backup_dir.name
        self.assertRegex(timestamp, r'^\d{8}_\d{6}')
    
    def test_create_timestamped_backup_dir_dry_run(self):
        """Test creating backup directory in dry run mode."""
        backup = ScribeBackup(self.test_root, dry_run=True)
        backup_dir = backup.create_timestamped_backup_dir()
        
        # Directory should not actually be created in dry run
        self.assertFalse(backup_dir.exists())
    
    def test_calculate_file_checksum(self):
        """Test checksum calculation."""
        backup = ScribeBackup(self.test_root)
        
        # Create a test file with known content
        test_file = self.test_root / "test_checksum.txt"
        test_file.write_text("Hello, World!")
        
        checksum = backup.calculate_file_checksum(test_file)
        
        # SHA256 of "Hello, World!" 
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        self.assertEqual(checksum, expected)
    
    def test_backup_database(self):
        """Test database backup functionality."""
        backup = ScribeBackup(self.test_root)
        backup_dir = backup.create_timestamped_backup_dir()
        
        db_info = backup.backup_database(backup_dir)
        
        # Check backup was created
        backup_db = backup_dir / "media_tracking.db"
        self.assertTrue(backup_db.exists())
        
        # Check info structure
        self.assertIn("original_path", db_info)
        self.assertIn("backup_path", db_info)
        self.assertIn("size", db_info)
        self.assertIn("original_checksum", db_info)
        self.assertIn("backup_checksum", db_info)
        
        # Verify checksums match
        self.assertEqual(db_info["original_checksum"], db_info["backup_checksum"])
    
    def test_backup_database_missing(self):
        """Test handling of missing database."""
        # Remove database
        self.db_path.unlink()
        
        backup = ScribeBackup(self.test_root)
        backup_dir = backup.create_timestamped_backup_dir()
        
        with self.assertRaises(FileNotFoundError):
            backup.backup_database(backup_dir)
    
    def test_backup_translation_directories(self):
        """Test translation directory backup."""
        backup = ScribeBackup(self.test_root)
        backup_dir = backup.create_timestamped_backup_dir()
        
        stats = backup.backup_translation_directories(backup_dir)
        
        # Check backup was created
        output_backup = backup_dir / "output"
        self.assertTrue(output_backup.exists())
        
        # Check statistics
        self.assertGreater(stats["total_files"], 0)
        self.assertGreater(stats["total_size"], 0)
        self.assertIn("languages", stats)
        
        # Verify files were copied
        for i in range(3):
            item_backup = output_backup / f"item_{i}"
            self.assertTrue(item_backup.exists())
            self.assertTrue((item_backup / "transcription_en.txt").exists())
    
    def test_generate_manifest(self):
        """Test manifest generation."""
        backup = ScribeBackup(self.test_root)
        backup_dir = backup.create_timestamped_backup_dir()
        
        # Mock data
        db_info = {
            "original_path": str(self.db_path),
            "backup_path": str(backup_dir / "media_tracking.db"),
            "size": 1024,
            "checksum": "abc123"
        }
        
        translation_stats = {
            "total_files": 12,
            "total_size": 50000,
            "languages": {
                "en": {"count": 3, "size": 15000},
                "he": {"count": 3, "size": 15000},
                "de": {"count": 3, "size": 15000}
            }
        }
        
        manifest_path = backup.generate_manifest(backup_dir, db_info, translation_stats)
        
        # Check manifest was created
        self.assertTrue(manifest_path.exists())
        
        # Load and verify manifest
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        self.assertIn("backup_timestamp", manifest)
        self.assertIn("backup_directory", manifest)
        self.assertIn("database", manifest)
        self.assertIn("translations", manifest)
        self.assertIn("validation_status", manifest)
        self.assertEqual(manifest["database"], db_info)
        self.assertEqual(manifest["translations"], translation_stats)
    
    def test_run_backup_complete(self):
        """Test complete backup process."""
        backup = ScribeBackup(self.test_root)
        backup_dir, manifest_data = backup.run_backup()
        
        # Check backup directory exists
        self.assertTrue(backup_dir.exists())
        
        # Check all components were backed up
        self.assertTrue((backup_dir / "media_tracking.db").exists())
        self.assertTrue((backup_dir / "output").exists())
        self.assertTrue((backup_dir / "manifest.json").exists())
        
        # Check manifest data
        self.assertIn("backup_timestamp", manifest_data)
        self.assertIn("database", manifest_data)
        self.assertIn("translations", manifest_data)
    
    def test_dry_run_mode(self):
        """Test dry run mode doesn't create files."""
        backup = ScribeBackup(self.test_root, dry_run=True)
        backup_dir, manifest_data = backup.run_backup()
        
        # Nothing should be created in dry run
        self.assertFalse(backup_dir.exists())
    
    def test_backup_with_validation_issues(self):
        """Test backup includes validation issues if available."""
        # Create validation issues file
        validation_issues = {
            "hebrew_placeholders": ["item_1", "item_2"],
            "missing_hebrew": ["item_3"]
        }
        validation_path = self.test_root / "validation_issues.json"
        with open(validation_path, 'w') as f:
            json.dump(validation_issues, f)
        
        backup = ScribeBackup(self.test_root)
        backup_dir, manifest_data = backup.run_backup()
        
        # Check validation issues are included
        self.assertEqual(
            manifest_data["validation_status"]["hebrew_placeholders"], 
            2
        )
        self.assertEqual(
            manifest_data["validation_status"]["missing_hebrew"], 
            1
        )
    
    def test_permission_error_handling(self):
        """Test handling of permission errors."""
        backup = ScribeBackup(self.test_root)
        
        # Mock makedirs to raise PermissionError
        with patch('pathlib.Path.mkdir', side_effect=PermissionError("No permission")):
            with self.assertRaises(PermissionError):
                backup.create_timestamped_backup_dir()
    
    def test_timestamp_collision_handling(self):
        """Test handling of timestamp collisions."""
        backup = ScribeBackup(self.test_root)
        
        # Create first backup
        first_dir = backup.create_timestamped_backup_dir()
        
        # Mock datetime to return same timestamp
        with patch('create_backup.datetime') as mock_datetime:
            # First call returns same timestamp (collision)
            # Second call adds microseconds
            mock_datetime.now.side_effect = [
                datetime.strptime(first_dir.name, "%Y%m%d_%H%M%S"),
                datetime.now()
            ]
            
            second_dir = backup.create_timestamped_backup_dir()
            
            # Should have different names
            self.assertNotEqual(first_dir.name, second_dir.name)


class TestBackupIntegration(unittest.TestCase):
    """Integration tests for backup system."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_restore_from_backup(self):
        """Test that backup can be restored."""
        # Create original structure
        db_path = self.test_root / "media_tracking.db"
        output_dir = self.test_root / "output"
        output_dir.mkdir()
        
        # Create test database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
        cursor.execute("INSERT INTO test (data) VALUES (?)", ("test data",))
        conn.commit()
        conn.close()
        
        # Create test files
        item_dir = output_dir / "item_1"
        item_dir.mkdir()
        (item_dir / "test.txt").write_text("Original content")
        
        # Create backup
        backup = ScribeBackup(self.test_root)
        backup_dir, _ = backup.run_backup()
        
        # Modify original files
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE test SET data = ?", ("modified data",))
        conn.commit()
        conn.close()
        (item_dir / "test.txt").write_text("Modified content")
        
        # Simulate restore by copying back
        shutil.copy2(backup_dir / "media_tracking.db", db_path)
        shutil.rmtree(output_dir)
        shutil.copytree(backup_dir / "output", output_dir)
        
        # Verify restoration
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM test")
        data = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(data, "test data")
        self.assertEqual((item_dir / "test.txt").read_text(), "Original content")


if __name__ == "__main__":
    unittest.main()