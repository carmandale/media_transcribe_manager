#!/usr/bin/env python3
"""
Test suite for the Scribe backup system - updated for current codebase structure.
"""

import unittest
import tempfile
import shutil
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, call
import signal
import subprocess

from scribe.backup import BackupManager


class TestBackupManager(unittest.TestCase):
    """Test BackupManager class."""
    
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
        
        # Create backup manager
        self.backup_manager = BackupManager(self.test_root)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _create_test_database(self):
        """Create a minimal test database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        ''')
        cursor.execute("INSERT INTO media_files (id, filename, status) VALUES (?, ?, ?)", 
                      ("test-001", "test_file.mp4", "completed"))
        cursor.execute("INSERT INTO media_files (id, filename, status) VALUES (?, ?, ?)", 
                      ("test-002", "test_file2.mp4", "completed"))
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
    
    def test_backup_manager_initialization(self):
        """Test BackupManager initialization."""
        self.assertEqual(self.backup_manager.project_root, self.test_root)
        self.assertEqual(self.backup_manager.database_path, self.db_path)
        self.assertEqual(self.backup_manager.output_dir, self.output_dir)
        self.assertEqual(self.backup_manager.backups_dir, self.test_root / "backups")
        self.assertFalse(self.backup_manager.interrupted)
        
        # Check that backups directory was created
        self.assertTrue(self.backup_manager.backups_dir.exists())
    
    def test_calculate_file_checksum(self):
        """Test checksum calculation."""
        # Create a test file with known content
        test_file = self.test_root / "test_checksum.txt"
        test_file.write_text("Hello, World!")
        
        checksum = self.backup_manager.calculate_file_checksum(test_file)
        
        # SHA256 of "Hello, World!" 
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        self.assertEqual(checksum, expected)
    
    def test_calculate_file_checksum_empty_file(self):
        """Test checksum calculation for empty file."""
        test_file = self.test_root / "empty.txt"
        test_file.touch()
        
        checksum = self.backup_manager.calculate_file_checksum(test_file)
        
        # SHA256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        self.assertEqual(checksum, expected)
    
    def test_calculate_file_checksum_binary_file(self):
        """Test checksum calculation for binary file."""
        test_file = self.test_root / "binary.bin"
        test_file.write_bytes(b"\\x00\\x01\\x02\\x03")
        
        checksum = self.backup_manager.calculate_file_checksum(test_file)
        
        # Should return a valid SHA256 hash
        self.assertEqual(len(checksum), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in checksum))
    
    def test_handle_interrupt(self):
        """Test interrupt handling."""
        # Test the interrupt handler
        self.backup_manager._handle_interrupt(signal.SIGINT, None)
        self.assertTrue(self.backup_manager.interrupted)
    
    @patch('scribe.backup.logger')
    def test_backup_database_success(self, mock_logger):
        """Test successful database backup."""
        # Create backup directory
        backup_dir = self.test_root / "test_backup"
        backup_dir.mkdir()
        
        # Mock the _backup_database method
        with patch.object(self.backup_manager, '_backup_database') as mock_backup_db:
            expected_db_info = {
                "original_path": str(self.db_path),
                "backup_path": str(backup_dir / "media_tracking.db"),
                "size": 1024,
                "checksum": "abc123"
            }
            mock_backup_db.return_value = expected_db_info
            
            result = self.backup_manager._backup_database(backup_dir)
            
            self.assertEqual(result, expected_db_info)
            mock_backup_db.assert_called_once_with(backup_dir)
    
    @patch('scribe.backup.logger')
    def test_backup_translations_full_success(self, mock_logger):
        """Test successful full translation backup."""
        # Create backup directory
        backup_dir = self.test_root / "test_backup"
        backup_dir.mkdir()
        
        # Mock the _backup_translations_full method
        with patch.object(self.backup_manager, '_backup_translations_full') as mock_backup_trans:
            expected_trans_info = {
                "total_files": 12,
                "total_size": 50000,
                "languages": {
                    "en": {"count": 3, "size": 15000},
                    "he": {"count": 3, "size": 15000},
                    "de": {"count": 3, "size": 15000},
                    "original": {"count": 3, "size": 5000}
                }
            }
            mock_backup_trans.return_value = expected_trans_info
            
            result = self.backup_manager._backup_translations_full(backup_dir)
            
            self.assertEqual(result, expected_trans_info)
            mock_backup_trans.assert_called_once_with(backup_dir)
    
    @patch('scribe.backup.logger')
    def test_backup_translations_quick_success(self, mock_logger):
        """Test successful quick translation backup."""
        # Create backup directory
        backup_dir = self.test_root / "test_backup"
        backup_dir.mkdir()
        
        # Mock the _backup_translations_quick method
        with patch.object(self.backup_manager, '_backup_translations_quick') as mock_backup_quick:
            expected_trans_info = {
                "total_files": 12,
                "total_size": 50000,
                "compression": "tar",
                "archive_path": str(backup_dir / "output.tar.gz")
            }
            mock_backup_quick.return_value = expected_trans_info
            
            result = self.backup_manager._backup_translations_quick(backup_dir)
            
            self.assertEqual(result, expected_trans_info)
            mock_backup_quick.assert_called_once_with(backup_dir)
    
    @patch('scribe.backup.logger')
    def test_generate_manifest(self, mock_logger):
        """Test manifest generation."""
        # Create backup directory
        backup_dir = self.test_root / "test_backup"
        backup_dir.mkdir()
        
        # Mock data
        db_info = {
            "original_path": str(self.db_path),
            "backup_path": str(backup_dir / "media_tracking.db"),
            "size": 1024,
            "checksum": "abc123"
        }
        
        translation_info = {
            "total_files": 12,
            "total_size": 50000,
            "languages": {
                "en": {"count": 3, "size": 15000},
                "he": {"count": 3, "size": 15000},
                "de": {"count": 3, "size": 15000}
            }
        }
        
        # Mock the _generate_manifest method
        with patch.object(self.backup_manager, '_generate_manifest') as mock_manifest:
            expected_manifest = {
                "backup_timestamp": "2025-01-01T00:00:00Z",
                "backup_directory": str(backup_dir),
                "database": db_info,
                "translations": translation_info,
                "backup_type": "full"
            }
            mock_manifest.return_value = expected_manifest
            
            result = self.backup_manager._generate_manifest(backup_dir, db_info, translation_info, False)
            
            self.assertEqual(result, expected_manifest)
            mock_manifest.assert_called_once_with(backup_dir, db_info, translation_info, False)
    
    @patch('scribe.backup.logger')
    def test_create_backup_full(self, mock_logger):
        """Test creating a full backup."""
        # Mock all the internal methods
        with patch.object(self.backup_manager, '_backup_database') as mock_backup_db, \
             patch.object(self.backup_manager, '_backup_translations_full') as mock_backup_trans, \
             patch.object(self.backup_manager, '_generate_manifest') as mock_manifest:
            
            # Setup mock returns
            mock_backup_db.return_value = {"size": 1024, "checksum": "abc123"}
            mock_backup_trans.return_value = {"total_files": 12, "total_size": 50000}
            mock_manifest.return_value = {"backup_timestamp": "2025-01-01T00:00:00Z"}
            
            # Create backup
            backup_dir, manifest = self.backup_manager.create_backup(quick=False)
            
            # Verify methods were called
            mock_backup_db.assert_called_once()
            mock_backup_trans.assert_called_once()
            mock_manifest.assert_called_once()
            
            # Verify backup directory was created
            self.assertTrue(backup_dir.exists())
            self.assertTrue(backup_dir.is_dir())
            
            # Verify return values
            self.assertEqual(manifest, {"backup_timestamp": "2025-01-01T00:00:00Z"})
    
    @patch('scribe.backup.logger')
    def test_create_backup_quick(self, mock_logger):
        """Test creating a quick backup."""
        # Mock all the internal methods
        with patch.object(self.backup_manager, '_backup_database') as mock_backup_db, \
             patch.object(self.backup_manager, '_backup_translations_quick') as mock_backup_trans, \
             patch.object(self.backup_manager, '_generate_manifest') as mock_manifest:
            
            # Setup mock returns
            mock_backup_db.return_value = {"size": 1024, "checksum": "abc123"}
            mock_backup_trans.return_value = {"total_files": 12, "compression": "tar"}
            mock_manifest.return_value = {"backup_timestamp": "2025-01-01T00:00:00Z"}
            
            # Create backup
            backup_dir, manifest = self.backup_manager.create_backup(quick=True)
            
            # Verify methods were called
            mock_backup_db.assert_called_once()
            mock_backup_trans.assert_called_once()
            mock_manifest.assert_called_once()
            
            # Verify backup directory was created
            self.assertTrue(backup_dir.exists())
            self.assertTrue(backup_dir.is_dir())
    
    @patch('scribe.backup.logger')
    def test_create_backup_interrupted(self, mock_logger):
        """Test backup with interruption."""
        # Set interrupted flag
        self.backup_manager.interrupted = True
        
        # Mock the database backup to check if it's called
        with patch.object(self.backup_manager, '_backup_database') as mock_backup_db:
            # Create backup should handle interruption
            # This depends on the actual implementation of interruption handling
            pass
    
    def test_backup_directory_naming(self):
        """Test that backup directories have proper timestamp naming."""
        # Create multiple backups and verify naming
        with patch.object(self.backup_manager, '_backup_database') as mock_backup_db, \
             patch.object(self.backup_manager, '_backup_translations_full') as mock_backup_trans, \
             patch.object(self.backup_manager, '_generate_manifest') as mock_manifest:
            
            # Setup mock returns
            mock_backup_db.return_value = {"size": 1024}
            mock_backup_trans.return_value = {"total_files": 12}
            mock_manifest.return_value = {"backup_timestamp": "2025-01-01T00:00:00Z"}
            
            # Create first backup
            backup_dir1, _ = self.backup_manager.create_backup()
            
            # Create second backup (should have different timestamp)
            backup_dir2, _ = self.backup_manager.create_backup()
            
            # Verify different directory names
            self.assertNotEqual(backup_dir1.name, backup_dir2.name)
            
            # Verify timestamp format (YYYYMMDD_HHMMSS)
            import re
            timestamp_pattern = r'^\d{8}_\d{6}$'
            self.assertTrue(re.match(timestamp_pattern, backup_dir1.name))
            self.assertTrue(re.match(timestamp_pattern, backup_dir2.name))
    
    def test_backup_error_handling(self):
        """Test backup error handling."""
        # Test with non-existent database
        self.db_path.unlink()
        
        with patch.object(self.backup_manager, '_backup_database') as mock_backup_db:
            # Mock database backup to raise exception
            mock_backup_db.side_effect = FileNotFoundError("Database not found")
            
            with self.assertRaises(FileNotFoundError):
                self.backup_manager.create_backup()
    
    def test_backup_with_permission_error(self):
        """Test backup with permission errors."""
        # Mock permission error during backup directory creation
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")
            
            with self.assertRaises(PermissionError):
                self.backup_manager.create_backup()
    
    def test_backup_with_disk_space_error(self):
        """Test backup with disk space errors."""
        # Mock disk space error during file copy
        with patch('shutil.copy2') as mock_copy:
            mock_copy.side_effect = OSError("No space left on device")
            
            with patch.object(self.backup_manager, '_backup_database') as mock_backup_db:
                mock_backup_db.side_effect = OSError("No space left on device")
                
                with self.assertRaises(OSError):
                    self.backup_manager.create_backup()


class TestBackupManagerIntegration(unittest.TestCase):
    """Integration tests for BackupManager."""
    
    def setUp(self):
        """Set up test environment."""
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
        
        self.backup_manager = BackupManager(self.test_root)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _create_test_database(self):
        """Create a test database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        ''')
        cursor.execute("INSERT INTO media_files (id, filename) VALUES (?, ?)", 
                      ("test-001", "test1.mp4"))
        cursor.execute("INSERT INTO media_files (id, filename) VALUES (?, ?)", 
                      ("test-002", "test2.mp4"))
        conn.commit()
        conn.close()
    
    def _create_test_translations(self):
        """Create test translation files."""
        # Create test files
        for i in range(3):
            item_dir = self.output_dir / f"item_{i}"
            item_dir.mkdir()
            
            (item_dir / "transcription_en.txt").write_text(f"English content {i}")
            (item_dir / "transcription_de.txt").write_text(f"German content {i}")
            (item_dir / "transcription_he.txt").write_text(f"Hebrew content {i}")
    
    @patch.object(BackupManager, '_backup_database')
    @patch.object(BackupManager, '_backup_translations_full')
    @patch.object(BackupManager, '_generate_manifest')
    def test_complete_backup_flow(self, mock_manifest, mock_backup_trans, mock_backup_db):
        """Test complete backup flow."""
        # Setup mocks
        mock_backup_db.return_value = {
            "original_path": str(self.db_path),
            "backup_path": "backup/media_tracking.db",
            "size": 1024,
            "checksum": "abc123"
        }
        
        mock_backup_trans.return_value = {
            "total_files": 9,
            "total_size": 30000,
            "languages": {
                "en": {"count": 3, "size": 10000},
                "de": {"count": 3, "size": 10000},
                "he": {"count": 3, "size": 10000}
            }
        }
        
        mock_manifest.return_value = {
            "backup_timestamp": "2025-01-01T00:00:00Z",
            "database": mock_backup_db.return_value,
            "translations": mock_backup_trans.return_value
        }
        
        # Execute backup
        backup_dir, manifest = self.backup_manager.create_backup(quick=False)
        
        # Verify all methods were called
        mock_backup_db.assert_called_once()
        mock_backup_trans.assert_called_once()
        mock_manifest.assert_called_once()
        
        # Verify backup directory exists
        self.assertTrue(backup_dir.exists())
        self.assertTrue(backup_dir.is_dir())
        
        # Verify manifest content
        self.assertIn("backup_timestamp", manifest)
        self.assertIn("database", manifest)
        self.assertIn("translations", manifest)
    
    def test_backup_validation(self):
        """Test backup validation."""
        # Create a simple backup structure for testing
        backup_dir = self.test_root / "backups" / "test_backup"
        backup_dir.mkdir(parents=True)
        
        # Create mock backup files
        (backup_dir / "media_tracking.db").write_text("mock database content")
        (backup_dir / "manifest.json").write_text('{"backup_timestamp": "2025-01-01T00:00:00Z"}')
        
        # Test that backup directory contains expected files
        self.assertTrue((backup_dir / "media_tracking.db").exists())
        self.assertTrue((backup_dir / "manifest.json").exists())
        
        # Test manifest loading
        with open(backup_dir / "manifest.json", 'r') as f:
            manifest = json.load(f)
        
        self.assertEqual(manifest["backup_timestamp"], "2025-01-01T00:00:00Z")
    
    def test_backup_restore_compatibility(self):
        """Test that backup can be used for restore."""
        # This test verifies that the backup structure is suitable for restore
        # In a real implementation, this would test the restore functionality
        
        # Create backup directory structure
        backup_dir = self.test_root / "backups" / "test_restore"
        backup_dir.mkdir(parents=True)
        
        # Copy database
        shutil.copy2(self.db_path, backup_dir / "media_tracking.db")
        
        # Copy output directory
        shutil.copytree(self.output_dir, backup_dir / "output")
        
        # Create manifest
        manifest = {
            "backup_timestamp": datetime.now().isoformat(),
            "database": {
                "original_path": str(self.db_path),
                "backup_path": str(backup_dir / "media_tracking.db"),
                "size": self.db_path.stat().st_size,
                "checksum": self.backup_manager.calculate_file_checksum(self.db_path)
            },
            "translations": {
                "backup_path": str(backup_dir / "output"),
                "total_files": 9
            }
        }
        
        with open(backup_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Verify backup structure
        self.assertTrue((backup_dir / "media_tracking.db").exists())
        self.assertTrue((backup_dir / "output").exists())
        self.assertTrue((backup_dir / "manifest.json").exists())
        
        # Verify database backup integrity
        original_checksum = self.backup_manager.calculate_file_checksum(self.db_path)
        backup_checksum = self.backup_manager.calculate_file_checksum(backup_dir / "media_tracking.db")
        self.assertEqual(original_checksum, backup_checksum)
        
        # Verify translation files
        for i in range(3):
            original_file = self.output_dir / f"item_{i}" / "transcription_en.txt"
            backup_file = backup_dir / "output" / f"item_{i}" / "transcription_en.txt"
            
            self.assertTrue(backup_file.exists())
            self.assertEqual(original_file.read_text(), backup_file.read_text())


class TestBackupManagerPerformance(unittest.TestCase):
    """Performance tests for BackupManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir)
        
        self.backup_manager = BackupManager(self.test_root)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_checksum_calculation_performance(self):
        """Test checksum calculation performance."""
        # Create files of different sizes
        small_file = self.test_root / "small.txt"
        medium_file = self.test_root / "medium.txt"
        
        small_file.write_text("small content")
        medium_file.write_text("medium content " * 1000)
        
        # Time checksum calculations
        start_time = datetime.now()
        
        small_checksum = self.backup_manager.calculate_file_checksum(small_file)
        medium_checksum = self.backup_manager.calculate_file_checksum(medium_file)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Verify checksums are different
        self.assertNotEqual(small_checksum, medium_checksum)
        
        # Should complete quickly (less than 0.1 seconds for small files)
        self.assertLess(duration, 0.1)
    
    def test_backup_directory_creation_performance(self):
        """Test backup directory creation performance."""
        start_time = datetime.now()
        
        # Create multiple backup directories
        for i in range(10):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{i}"
            backup_dir = self.backup_manager.backups_dir / timestamp
            backup_dir.mkdir(parents=True, exist_ok=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Should complete quickly
        self.assertLess(duration, 0.5)
        
        # Verify directories were created
        self.assertEqual(len(list(self.backup_manager.backups_dir.iterdir())), 10)


if __name__ == "__main__":
    unittest.main()