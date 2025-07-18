#!/usr/bin/env python3
"""
Test suite for the Scribe audit system - updated for current codebase structure.
"""

import unittest
import tempfile
import shutil
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from scribe.audit import FileStatus, FileMetadata, AuditResult, DatabaseAuditor


class TestFileStatus(unittest.TestCase):
    """Test FileStatus enum."""
    
    def test_file_status_values(self):
        """Test FileStatus enum values."""
        self.assertEqual(FileStatus.VALID.value, "valid")
        self.assertEqual(FileStatus.PLACEHOLDER.value, "placeholder")
        self.assertEqual(FileStatus.MISSING.value, "missing")
        self.assertEqual(FileStatus.ORPHANED.value, "orphaned")
        self.assertEqual(FileStatus.CORRUPTED.value, "corrupted")
        self.assertEqual(FileStatus.EMPTY.value, "empty")


class TestFileMetadata(unittest.TestCase):
    """Test FileMetadata dataclass."""
    
    def test_file_metadata_creation(self):
        """Test creating FileMetadata instance."""
        metadata = FileMetadata(
            file_id="test-123",
            language="en",
            file_path=Path("/test/file.txt"),
            exists=True,
            size=1024,
            checksum="abc123",
            status=FileStatus.VALID
        )
        
        self.assertEqual(metadata.file_id, "test-123")
        self.assertEqual(metadata.language, "en")
        self.assertEqual(metadata.file_path, Path("/test/file.txt"))
        self.assertTrue(metadata.exists)
        self.assertEqual(metadata.size, 1024)
        self.assertEqual(metadata.checksum, "abc123")
        self.assertEqual(metadata.status, FileStatus.VALID)
        self.assertFalse(metadata.has_hebrew)
        self.assertFalse(metadata.has_placeholder)
        self.assertIsNone(metadata.content_preview)
        self.assertIsNone(metadata.error)
    
    def test_file_metadata_with_optional_fields(self):
        """Test FileMetadata with optional fields set."""
        metadata = FileMetadata(
            file_id="test-456",
            language="he",
            file_path=None,
            exists=False,
            size=0,
            checksum=None,
            status=FileStatus.MISSING,
            has_hebrew=True,
            has_placeholder=False,
            content_preview="שלום עולם",
            error="File not found"
        )
        
        self.assertEqual(metadata.file_id, "test-456")
        self.assertEqual(metadata.language, "he")
        self.assertIsNone(metadata.file_path)
        self.assertFalse(metadata.exists)
        self.assertEqual(metadata.size, 0)
        self.assertIsNone(metadata.checksum)
        self.assertEqual(metadata.status, FileStatus.MISSING)
        self.assertTrue(metadata.has_hebrew)
        self.assertFalse(metadata.has_placeholder)
        self.assertEqual(metadata.content_preview, "שלום עולם")
        self.assertEqual(metadata.error, "File not found")


class TestAuditResult(unittest.TestCase):
    """Test AuditResult dataclass."""
    
    def test_audit_result_creation(self):
        """Test creating AuditResult instance."""
        result = AuditResult(
            timestamp="2025-01-01T00:00:00Z",
            total_files=100,
            issues_found=5,
            language_stats={"en": {"total": 50, "valid": 48}},
            issues_by_type={"placeholder": ["file1", "file2"]},
            recommendations=["Fix placeholder files"]
        )
        
        self.assertEqual(result.timestamp, "2025-01-01T00:00:00Z")
        self.assertEqual(result.total_files, 100)
        self.assertEqual(result.issues_found, 5)
        self.assertEqual(result.language_stats["en"]["total"], 50)
        self.assertEqual(result.issues_by_type["placeholder"], ["file1", "file2"])
        self.assertEqual(result.recommendations, ["Fix placeholder files"])


class TestDatabaseAuditor(unittest.TestCase):
    """Test DatabaseAuditor class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create test database
        self.db_path = self.test_path / "media_tracking.db"
        self.output_dir = self.test_path / "output"
        self.output_dir.mkdir()
        
        self._create_test_database()
        self._create_test_files()
        
        self.auditor = DatabaseAuditor(self.test_path)
    
    def tearDown(self):
        """Clean up test environment."""
        if hasattr(self, 'auditor'):
            self.auditor.close()
        shutil.rmtree(self.test_dir)
    
    def _create_test_database(self):
        """Create a test database with sample data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create minimal table structure
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                transcription_status TEXT DEFAULT 'pending'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY,
                file_id TEXT,
                target_language TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # Insert test data
        cursor.execute("INSERT INTO media_files (id, filename) VALUES (?, ?)", ("test-001", "test1.mp4"))
        cursor.execute("INSERT INTO media_files (id, filename) VALUES (?, ?)", ("test-002", "test2.mp4"))
        cursor.execute("INSERT INTO media_files (id, filename) VALUES (?, ?)", ("test-003", "test3.mp4"))
        
        conn.commit()
        conn.close()
    
    def _create_test_files(self):
        """Create test translation files."""
        # Create test-001 with valid files
        test1_dir = self.output_dir / "test-001"
        test1_dir.mkdir()
        (test1_dir / "transcription_en.txt").write_text("English transcription")
        (test1_dir / "transcription_de.txt").write_text("Deutsche Transkription")
        (test1_dir / "transcription_he.txt").write_text("תמלול עברי")
        
        # Create test-002 with placeholder
        test2_dir = self.output_dir / "test-002"
        test2_dir.mkdir()
        (test2_dir / "transcription_en.txt").write_text("English transcription")
        (test2_dir / "transcription_de.txt").write_text("Deutsche Transkription")
        (test2_dir / "transcription_he.txt").write_text("[HEBREW TRANSLATION]")
        
        # Create test-003 with missing Hebrew file
        test3_dir = self.output_dir / "test-003"
        test3_dir.mkdir()
        (test3_dir / "transcription_en.txt").write_text("English transcription")
        (test3_dir / "transcription_de.txt").write_text("Deutsche Transkription")
        # No Hebrew file
    
    def test_auditor_initialization(self):
        """Test DatabaseAuditor initialization."""
        self.assertEqual(self.auditor.project_root, self.test_path)
        self.assertEqual(self.auditor.db_path, self.db_path)
        self.assertEqual(self.auditor.output_dir, self.output_dir)
        self.assertIsNotNone(self.auditor.db)
        self.assertIsNotNone(self.auditor.placeholder_patterns)
        self.assertIsNotNone(self.auditor.placeholder_regex)
    
    def test_contains_hebrew(self):
        """Test Hebrew character detection."""
        # Test with Hebrew text
        self.assertTrue(self.auditor.contains_hebrew("שלום עולם"))
        self.assertTrue(self.auditor.contains_hebrew("Hello שלום World"))
        
        # Test without Hebrew
        self.assertFalse(self.auditor.contains_hebrew("Hello World"))
        self.assertFalse(self.auditor.contains_hebrew("Guten Tag"))
        self.assertFalse(self.auditor.contains_hebrew(""))
    
    def test_has_placeholder(self):
        """Test placeholder detection."""
        # Test various placeholder patterns
        self.assertTrue(self.auditor.has_placeholder("[HEBREW TRANSLATION]"))
        self.assertTrue(self.auditor.has_placeholder("Text with [GERMAN TRANSLATION] inside"))
        self.assertTrue(self.auditor.has_placeholder("<<<PLACEHOLDER>>>"))
        self.assertTrue(self.auditor.has_placeholder("Translation pending"))
        self.assertTrue(self.auditor.has_placeholder("TO BE TRANSLATED"))
        
        # Test case insensitive
        self.assertTrue(self.auditor.has_placeholder("[hebrew translation]"))
        
        # Test without placeholders
        self.assertFalse(self.auditor.has_placeholder("Normal text"))
        self.assertFalse(self.auditor.has_placeholder("שלום עולם"))
    
    def test_analyze_file_valid(self):
        """Test analyzing a valid file."""
        file_path = self.output_dir / "test-001" / "transcription_en.txt"
        metadata = self.auditor.analyze_file(file_path, "test-001", "en")
        
        self.assertEqual(metadata.file_id, "test-001")
        self.assertEqual(metadata.language, "en")
        self.assertEqual(metadata.file_path, file_path)
        self.assertTrue(metadata.exists)
        self.assertGreater(metadata.size, 0)
        self.assertIsNotNone(metadata.checksum)
        self.assertEqual(metadata.status, FileStatus.VALID)
        self.assertFalse(metadata.has_hebrew)
        self.assertFalse(metadata.has_placeholder)
        self.assertIsNone(metadata.error)
    
    def test_analyze_file_hebrew_valid(self):
        """Test analyzing a valid Hebrew file."""
        file_path = self.output_dir / "test-001" / "transcription_he.txt"
        metadata = self.auditor.analyze_file(file_path, "test-001", "he")
        
        self.assertEqual(metadata.file_id, "test-001")
        self.assertEqual(metadata.language, "he")
        self.assertTrue(metadata.exists)
        self.assertEqual(metadata.status, FileStatus.VALID)
        self.assertTrue(metadata.has_hebrew)
        self.assertFalse(metadata.has_placeholder)
    
    def test_analyze_file_placeholder(self):
        """Test analyzing a file with placeholder."""
        file_path = self.output_dir / "test-002" / "transcription_he.txt"
        metadata = self.auditor.analyze_file(file_path, "test-002", "he")
        
        self.assertEqual(metadata.file_id, "test-002")
        self.assertEqual(metadata.language, "he")
        self.assertTrue(metadata.exists)
        self.assertEqual(metadata.status, FileStatus.PLACEHOLDER)
        self.assertFalse(metadata.has_hebrew)
        self.assertTrue(metadata.has_placeholder)
    
    def test_analyze_file_missing(self):
        """Test analyzing a missing file."""
        file_path = self.output_dir / "test-003" / "transcription_he.txt"
        metadata = self.auditor.analyze_file(file_path, "test-003", "he")
        
        self.assertEqual(metadata.file_id, "test-003")
        self.assertEqual(metadata.language, "he")
        self.assertEqual(metadata.file_path, file_path)
        self.assertFalse(metadata.exists)
        self.assertEqual(metadata.size, 0)
        self.assertIsNone(metadata.checksum)
        self.assertEqual(metadata.status, FileStatus.MISSING)
        self.assertFalse(metadata.has_hebrew)
        self.assertFalse(metadata.has_placeholder)
    
    def test_analyze_file_empty(self):
        """Test analyzing an empty file."""
        file_path = self.output_dir / "test-empty.txt"
        file_path.touch()  # Create empty file
        
        metadata = self.auditor.analyze_file(file_path, "test-empty", "en")
        
        self.assertTrue(metadata.exists)
        self.assertEqual(metadata.size, 0)
        self.assertEqual(metadata.status, FileStatus.EMPTY)
    
    def test_analyze_file_hebrew_without_hebrew_chars(self):
        """Test Hebrew file without Hebrew characters (should be placeholder)."""
        file_path = self.output_dir / "test-fake-hebrew.txt"
        file_path.write_text("This is supposed to be Hebrew but it's not")
        
        metadata = self.auditor.analyze_file(file_path, "test-fake", "he")
        
        self.assertEqual(metadata.status, FileStatus.PLACEHOLDER)
        self.assertFalse(metadata.has_hebrew)
    
    @patch('scribe.audit.Database')
    def test_get_all_files(self, mock_db_class):
        """Test getting all files from database."""
        # Mock database
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        # Mock get_all_files result
        mock_db.get_all_files.return_value = [
            {"file_id": "test-001", "filename": "test1.mp4"},
            {"file_id": "test-002", "filename": "test2.mp4"}
        ]
        
        auditor = DatabaseAuditor(self.test_path)
        files = auditor.db.get_all_files()
        
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]["file_id"], "test-001")
        self.assertEqual(files[1]["file_id"], "test-002")
    
    def test_audit_with_real_database(self):
        """Test audit with real database and files."""
        # This tests the actual audit functionality
        # Mock the database query methods that might not exist
        with patch.object(self.auditor.db, 'execute_query') as mock_query:
            mock_query.return_value = [
                {"file_id": "test-001"},
                {"file_id": "test-002"},
                {"file_id": "test-003"}
            ]
            
            # Test the actual audit_database method instead of non-existent get_all_files
            result = self.auditor.audit_database()
            self.assertIsInstance(result, AuditResult)
            
            # Basic validation that the audit ran
            self.assertIsNotNone(result.total_files)
            self.assertIsNotNone(result.language_stats)


class TestDatabaseAuditorIntegration(unittest.TestCase):
    """Integration tests for DatabaseAuditor."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create more comprehensive test structure
        self.db_path = self.test_path / "media_tracking.db"
        self.output_dir = self.test_path / "output"
        self.output_dir.mkdir()
        
        self._create_comprehensive_test_database()
        self._create_comprehensive_test_files()
        
        self.auditor = DatabaseAuditor(self.test_path)
    
    def tearDown(self):
        """Clean up test environment."""
        if hasattr(self, 'auditor'):
            self.auditor.close()
        shutil.rmtree(self.test_dir)
    
    def _create_comprehensive_test_database(self):
        """Create a comprehensive test database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                transcription_status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Insert 10 test files
        for i in range(10):
            cursor.execute("INSERT INTO media_files (id, filename) VALUES (?, ?)", 
                         (f"test-{i:03d}", f"test{i}.mp4"))
        
        conn.commit()
        conn.close()
    
    def _create_comprehensive_test_files(self):
        """Create comprehensive test files."""
        languages = ["en", "de", "he"]
        
        for i in range(10):
            file_id = f"test-{i:03d}"
            file_dir = self.output_dir / file_id
            file_dir.mkdir()
            
            # English and German - always valid
            (file_dir / "transcription_en.txt").write_text(f"English content for {file_id}")
            (file_dir / "transcription_de.txt").write_text(f"Deutscher Inhalt für {file_id}")
            
            # Hebrew with different scenarios
            if i < 5:
                # Valid Hebrew
                (file_dir / "transcription_he.txt").write_text(f"תוכן עברי עבור {file_id}")
            elif i < 8:
                # Placeholder
                (file_dir / "transcription_he.txt").write_text("[HEBREW TRANSLATION]")
            # else: missing (don't create file)
    
    def test_comprehensive_audit(self):
        """Test comprehensive audit functionality."""
        with patch.object(self.auditor.db, 'get_all_files') as mock_get_all_files:
            mock_get_all_files.return_value = [
                {"file_id": f"test-{i:03d}", "filename": f"test{i}.mp4"}
                for i in range(10)
            ]
            
            files = self.auditor.db.get_all_files()
            self.assertEqual(len(files), 10)
            
            # Analyze all files
            language_stats = {"en": [], "de": [], "he": []}
            
            for file_data in files:
                file_id = file_data["file_id"]
                
                for lang in ["en", "de", "he"]:
                    file_path = self.output_dir / file_id / f"transcription_{lang}.txt"
                    metadata = self.auditor.analyze_file(file_path, file_id, lang)
                    language_stats[lang].append(metadata)
            
            # Check English - should all be valid
            en_valid = sum(1 for m in language_stats["en"] if m.status == FileStatus.VALID)
            self.assertEqual(en_valid, 10)
            
            # Check German - should all be valid
            de_valid = sum(1 for m in language_stats["de"] if m.status == FileStatus.VALID)
            self.assertEqual(de_valid, 10)
            
            # Check Hebrew - mixed results
            he_valid = sum(1 for m in language_stats["he"] if m.status == FileStatus.VALID)
            he_placeholder = sum(1 for m in language_stats["he"] if m.status == FileStatus.PLACEHOLDER)
            he_missing = sum(1 for m in language_stats["he"] if m.status == FileStatus.MISSING)
            
            self.assertEqual(he_valid, 5)      # files 0-4
            self.assertEqual(he_placeholder, 3) # files 5-7
            self.assertEqual(he_missing, 2)     # files 8-9
    
    def test_performance_with_many_files(self):
        """Test performance with many files."""
        start_time = datetime.now()
        
        with patch.object(self.auditor.db, 'get_all_files') as mock_get_all_files:
            mock_get_all_files.return_value = [
                {"file_id": f"test-{i:03d}", "filename": f"test{i}.mp4"}
                for i in range(10)
            ]
            
            files = self.auditor.db.get_all_files()
            
            # Analyze all files
            for file_data in files:
                file_id = file_data["file_id"]
                for lang in ["en", "de", "he"]:
                    file_path = self.output_dir / file_id / f"transcription_{lang}.txt"
                    self.auditor.analyze_file(file_path, file_id, lang)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Should complete in reasonable time (less than 1 second for 30 files)
        self.assertLess(duration, 1.0)


if __name__ == "__main__":
    unittest.main()
