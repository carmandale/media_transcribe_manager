#!/usr/bin/env python3
"""
Test suite for the Scribe audit system.
"""

import unittest
import pytest
import asyncio
import tempfile
import shutil
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

# Skip all tests in this file - replaced by test_audit_new.py
pytestmark = pytest.mark.skip(reason="Old test file with incorrect imports - replaced by test_audit_new.py")


class TestFileAnalyzer(unittest.TestCase):
    """Test FileAnalyzer class."""
    
    def setUp(self):
        self.analyzer = FileAnalyzer()
    
    def test_contains_hebrew(self):
        """Test Hebrew character detection."""
        # Test with Hebrew text
        self.assertTrue(FileAnalyzer.contains_hebrew("שלום עולם"))
        self.assertTrue(FileAnalyzer.contains_hebrew("Hello שלום World"))
        
        # Test without Hebrew
        self.assertFalse(FileAnalyzer.contains_hebrew("Hello World"))
        self.assertFalse(FileAnalyzer.contains_hebrew("Guten Tag"))
        self.assertFalse(FileAnalyzer.contains_hebrew(""))
    
    def test_has_placeholder(self):
        """Test placeholder detection."""
        analyzer = FileAnalyzer()
        
        # Test various placeholder patterns
        self.assertTrue(analyzer.has_placeholder("[HEBREW TRANSLATION]"))
        self.assertTrue(analyzer.has_placeholder("Text with [GERMAN TRANSLATION] inside"))
        self.assertTrue(analyzer.has_placeholder("<<<PLACEHOLDER>>>"))
        self.assertTrue(analyzer.has_placeholder("Translation pending"))
        self.assertTrue(analyzer.has_placeholder("TO BE TRANSLATED"))
        
        # Test case insensitive
        self.assertTrue(analyzer.has_placeholder("[hebrew translation]"))
        
        # Test without placeholders
        self.assertFalse(analyzer.has_placeholder("Normal text"))
        self.assertFalse(analyzer.has_placeholder("שלום עולם"))
    
    def test_detect_language(self):
        """Test language detection."""
        # Test Hebrew
        self.assertEqual(FileAnalyzer.detect_language("שלום עולם"), "he")
        self.assertEqual(FileAnalyzer.detect_language("Hello שלום"), "he")
        
        # Test German
        german_text = "Das ist ein Test. Der Mann und die Frau sind nicht zu Hause."
        self.assertEqual(FileAnalyzer.detect_language(german_text), "de")
        
        # Test English (default)
        self.assertEqual(FileAnalyzer.detect_language("Hello world"), "en")
        self.assertEqual(FileAnalyzer.detect_language(""), "en")


class TestFileAnalyzerAsync(unittest.TestCase):
    """Test async methods of FileAnalyzer."""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.analyzer = FileAnalyzer()
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    async def test_analyze_translation_file_valid(self):
        """Test analyzing a valid translation file."""
        # Create test file
        file_path = self.test_path / "test.txt"
        file_path.write_text("This is a valid English translation.")
        
        metadata = await self.analyzer.analyze_translation_file(
            file_path, "test_id", "en"
        )
        
        self.assertEqual(metadata.file_id, "test_id")
        self.assertEqual(metadata.language, "en")
        self.assertTrue(metadata.exists)
        self.assertEqual(metadata.status, FileStatus.VALID)
        self.assertFalse(metadata.has_hebrew)
        self.assertFalse(metadata.has_placeholder)
        self.assertIsNotNone(metadata.checksum)
    
    async def test_analyze_translation_file_placeholder(self):
        """Test analyzing a file with placeholder."""
        # Create test file with placeholder
        file_path = self.test_path / "test_he.txt"
        file_path.write_text("[HEBREW TRANSLATION]")
        
        metadata = await self.analyzer.analyze_translation_file(
            file_path, "test_id", "he"
        )
        
        self.assertEqual(metadata.status, FileStatus.PLACEHOLDER)
        self.assertTrue(metadata.has_placeholder)
        self.assertFalse(metadata.has_hebrew)
    
    async def test_analyze_translation_file_hebrew(self):
        """Test analyzing a valid Hebrew file."""
        # Create test file with Hebrew
        file_path = self.test_path / "test_he.txt"
        file_path.write_text("שלום עולם - זהו תרגום לעברית")
        
        metadata = await self.analyzer.analyze_translation_file(
            file_path, "test_id", "he"
        )
        
        self.assertEqual(metadata.status, FileStatus.VALID)
        self.assertFalse(metadata.has_placeholder)
        self.assertTrue(metadata.has_hebrew)
    
    async def test_analyze_translation_file_missing(self):
        """Test analyzing a missing file."""
        file_path = self.test_path / "missing.txt"
        
        metadata = await self.analyzer.analyze_translation_file(
            file_path, "test_id", "en"
        )
        
        self.assertFalse(metadata.exists)
        self.assertEqual(metadata.status, FileStatus.MISSING)
        self.assertEqual(metadata.size, 0)
        self.assertIsNone(metadata.checksum)
    
    async def test_analyze_translation_file_empty(self):
        """Test analyzing an empty file."""
        file_path = self.test_path / "empty.txt"
        file_path.touch()  # Create empty file
        
        metadata = await self.analyzer.analyze_translation_file(
            file_path, "test_id", "en"
        )
        
        self.assertTrue(metadata.exists)
        self.assertEqual(metadata.status, FileStatus.EMPTY)
        self.assertEqual(metadata.size, 0)
    
    async def test_analyze_hebrew_without_hebrew_chars(self):
        """Test Hebrew file without Hebrew characters (should be placeholder)."""
        file_path = self.test_path / "fake_he.txt"
        file_path.write_text("This is supposed to be Hebrew but it's not")
        
        metadata = await self.analyzer.analyze_translation_file(
            file_path, "test_id", "he"
        )
        
        self.assertEqual(metadata.status, FileStatus.PLACEHOLDER)
        self.assertFalse(metadata.has_hebrew)
    
    def test_analyze_translation_file(self):
        """Run async tests."""
        asyncio.run(self.test_analyze_translation_file_valid())
        asyncio.run(self.test_analyze_translation_file_placeholder())
        asyncio.run(self.test_analyze_translation_file_hebrew())
        asyncio.run(self.test_analyze_translation_file_missing())
        asyncio.run(self.test_analyze_translation_file_empty())
        asyncio.run(self.test_analyze_hebrew_without_hebrew_chars())


class TestDatabaseAnalyzer(unittest.TestCase):
    """Test DatabaseAnalyzer class."""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test.db"
        self._create_test_database()
        self.analyzer = DatabaseAnalyzer(self.db_path)
    
    def tearDown(self):
        if self.analyzer.connection:
            self.analyzer.close()
        shutil.rmtree(self.test_dir)
    
    def _create_test_database(self):
        """Create a test database with sample data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE media_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE translations (
                id INTEGER PRIMARY KEY,
                file_id TEXT,
                target_language TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (file_id) REFERENCES media_files(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE evaluations (
                id INTEGER PRIMARY KEY,
                file_id TEXT,
                language TEXT,
                score REAL
            )
        ''')
        
        # Insert test data
        test_files = [
            ('file1', 'test1.mp4'),
            ('file2', 'test2.mp4'),
            ('file3', 'test3.mp4')
        ]
        cursor.executemany('INSERT INTO media_files VALUES (?, ?)', test_files)
        
        # Insert translations
        translations = [
            ('file1', 'en', 'completed'),
            ('file1', 'de', 'completed'),
            ('file1', 'he', 'completed'),  # This will be a placeholder
            ('file2', 'en', 'completed'),
            ('file2', 'de', 'pending'),
            ('file2', 'he', 'completed'),  # This will be missing
            ('file3', 'en', 'completed'),
            ('file3', 'de', 'completed'),
            ('file3', 'he', 'completed')   # This will be valid
        ]
        
        for file_id, lang, status in translations:
            cursor.execute(
                'INSERT INTO translations (file_id, target_language, status, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?)',
                (file_id, lang, status, '2025-01-01', '2025-01-01')
            )
        
        # Insert evaluations
        cursor.execute('INSERT INTO evaluations (file_id, language, score) VALUES (?, ?, ?)',
                      ('file1', 'en', 0.95))
        
        conn.commit()
        conn.close()
    
    def test_connect_and_close(self):
        """Test database connection."""
        self.analyzer.connect()
        self.assertIsNotNone(self.analyzer.connection)
        self.analyzer.close()
        # Should not raise an error to close again
        self.analyzer.close()
    
    def test_get_all_translation_records(self):
        """Test getting all translation records."""
        self.analyzer.connect()
        records = self.analyzer.get_all_translation_records()
        
        # Check structure
        self.assertIsInstance(records, dict)
        self.assertEqual(len(records), 3)  # 3 files
        
        # Check file1
        self.assertIn('file1', records)
        self.assertEqual(len(records['file1']), 3)  # 3 languages
        self.assertIn('en', records['file1'])
        self.assertIn('de', records['file1'])
        self.assertIn('he', records['file1'])
        
        # Check record details
        en_record = records['file1']['en']
        self.assertIsInstance(en_record, DatabaseRecord)
        self.assertEqual(en_record.file_id, 'file1')
        self.assertEqual(en_record.language, 'en')
        self.assertEqual(en_record.status, 'completed')
        self.assertTrue(en_record.evaluated)  # Has evaluation
        self.assertEqual(en_record.evaluation_score, 0.95)
        
        # Check file without evaluation
        de_record = records['file1']['de']
        self.assertFalse(de_record.evaluated)
        self.assertIsNone(de_record.evaluation_score)
    
    def test_get_total_file_count(self):
        """Test getting total file count."""
        self.analyzer.connect()
        count = self.analyzer.get_total_file_count()
        self.assertEqual(count, 3)


class TestFilesystemScanner(unittest.TestCase):
    """Test FilesystemScanner class."""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.test_dir) / "output"
        self.output_dir.mkdir()
        self._create_test_files()
        self.scanner = FilesystemScanner(self.output_dir)
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def _create_test_files(self):
        """Create test file structure."""
        # Create file1 with all languages
        file1_dir = self.output_dir / "file1"
        file1_dir.mkdir()
        (file1_dir / "transcription_en.txt").write_text("English")
        (file1_dir / "transcription_de.txt").write_text("Deutsch")
        (file1_dir / "transcription_he.txt").write_text("[HEBREW TRANSLATION]")
        (file1_dir / "transcription_original.txt").write_text("Original")
        
        # Create file2 with missing Hebrew
        file2_dir = self.output_dir / "file2"
        file2_dir.mkdir()
        (file2_dir / "transcription_en.txt").write_text("English")
        (file2_dir / "transcription_de.txt").write_text("Deutsch")
        
        # Create orphaned file (not in database)
        orphan_dir = self.output_dir / "orphan1"
        orphan_dir.mkdir()
        (orphan_dir / "transcription_en.txt").write_text("Orphaned")
    
    async def test_scan_output_directory(self):
        """Test scanning output directory."""
        files_map = await self.scanner.scan_output_directory()
        
        self.assertEqual(len(files_map), 3)  # 3 directories
        
        # Check file1
        self.assertIn('file1', files_map)
        self.assertEqual(len(files_map['file1']), 4)  # 4 languages including original
        self.assertIn('en', files_map['file1'])
        self.assertIn('de', files_map['file1'])
        self.assertIn('he', files_map['file1'])
        self.assertIn('original', files_map['file1'])
        
        # Check file2 (missing Hebrew)
        self.assertIn('file2', files_map)
        self.assertEqual(len(files_map['file2']), 2)  # Only en and de
        self.assertNotIn('he', files_map['file2'])
        
        # Check orphaned file
        self.assertIn('orphan1', files_map)
    
    async def test_scan_missing_directory(self):
        """Test scanning non-existent directory."""
        scanner = FilesystemScanner(Path("/non/existent/path"))
        files_map = await scanner.scan_output_directory()
        self.assertEqual(len(files_map), 0)
    
    def test_scan(self):
        """Run async tests."""
        asyncio.run(self.test_scan_output_directory())
        asyncio.run(self.test_scan_missing_directory())


class TestLanguageStatistics(unittest.TestCase):
    """Test LanguageStatistics class."""
    
    def test_to_dict(self):
        """Test converting statistics to dictionary."""
        stats = LanguageStatistics(
            expected_count=100,
            found_count=90,
            valid_count=80,
            placeholder_count=5,
            missing_count=10,
            corrupted_count=3,
            empty_count=2
        )
        
        result = stats.to_dict()
        
        self.assertEqual(result['expected'], 100)
        self.assertEqual(result['found'], 90)
        self.assertEqual(result['valid'], 80)
        self.assertEqual(result['placeholders'], 5)
        self.assertEqual(result['missing'], 10)
        self.assertEqual(result['completion_rate'], "80.0%")
    
    def test_to_dict_zero_expected(self):
        """Test with zero expected count."""
        stats = LanguageStatistics()
        result = stats.to_dict()
        self.assertEqual(result['completion_rate'], "0%")


class TestScribeAuditSystemIntegration(unittest.TestCase):
    """Integration tests for the complete audit system."""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self._setup_test_environment()
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def _setup_test_environment(self):
        """Set up a complete test environment."""
        # Create database
        db_path = self.test_path / "media_tracking.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create schema
        cursor.execute('''
            CREATE TABLE media_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE translations (
                id INTEGER PRIMARY KEY,
                file_id TEXT,
                target_language TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE evaluations (
                id INTEGER PRIMARY KEY,
                file_id TEXT,
                language TEXT,
                score REAL
            )
        ''')
        
        # Create output directory
        output_dir = self.test_path / "output"
        output_dir.mkdir()
        
        # Add test data to simulate known issues
        # We'll create a smaller test set that proportionally matches the expected ratios
        
        # Create 10 test files
        for i in range(10):
            file_id = f"test_{i:03d}"
            cursor.execute('INSERT INTO media_files VALUES (?, ?)', (file_id, f"test{i}.mp4"))
            
            # All files have EN and DE translations
            cursor.execute(
                'INSERT INTO translations (file_id, target_language, status) VALUES (?, ?, ?)',
                (file_id, 'en', 'completed')
            )
            cursor.execute(
                'INSERT INTO translations (file_id, target_language, status) VALUES (?, ?, ?)',
                (file_id, 'de', 'completed')
            )
            cursor.execute(
                'INSERT INTO translations (file_id, target_language, status) VALUES (?, ?, ?)',
                (file_id, 'he', 'completed')
            )
            
            # Create file directory
            file_dir = output_dir / file_id
            file_dir.mkdir()
            
            # Create EN and DE files
            (file_dir / "transcription_en.txt").write_text(f"English content for {file_id}")
            (file_dir / "transcription_de.txt").write_text(f"Der deutsche Inhalt für {file_id}")
            
            # Hebrew files: 
            # - 5 valid (50%)
            # - 3 placeholders (30%)
            # - 2 missing (20%)
            if i < 5:
                # Valid Hebrew
                (file_dir / "transcription_he.txt").write_text(f"תוכן עברי עבור {file_id}")
            elif i < 8:
                # Placeholder
                (file_dir / "transcription_he.txt").write_text("[HEBREW TRANSLATION]")
            # else: missing (don't create file)
        
        conn.commit()
        conn.close()
    
    async def test_full_audit_process(self):
        """Test the complete audit process."""
        audit_system = ScribeAuditSystem(self.test_path)
        report = await audit_system.run_audit()
        
        # Check report structure
        self.assertIsNotNone(report)
        self.assertIsNotNone(report.audit_timestamp)
        self.assertEqual(report.project_root, str(self.test_path))
        
        # Check summary
        self.assertEqual(report.summary['total_files_in_db'], 10)
        
        # Check language statistics
        he_stats = report.summary['languages']['he']
        self.assertEqual(he_stats['expected'], 10)
        self.assertEqual(he_stats['found'], 8)  # 2 missing
        self.assertEqual(he_stats['valid'], 5)
        self.assertEqual(he_stats['placeholders'], 3)
        self.assertEqual(he_stats['missing'], 2)
        
        # Check validation results (won't match exact numbers but ratios should be similar)
        validation = report.validation_results
        self.assertFalse(validation['validation_passed'])  # Won't match exact production numbers
        
        # Check performance
        self.assertLess(report.performance_metrics['total_execution_time'], 5.0)  # Should be fast for 10 files
    
    def test_integration(self):
        """Run async integration test."""
        asyncio.run(self.test_full_audit_process())


class TestPerformance(unittest.TestCase):
    """Test performance requirements."""
    
    async def test_large_file_set_performance(self):
        """Test that analyzer can handle many files efficiently."""
        analyzer = FileAnalyzer()
        
        # Create temporary files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create 100 test files
            files = []
            for i in range(100):
                file_path = temp_path / f"test_{i}.txt"
                file_path.write_text(f"Test content {i}")
                files.append((file_path, f"id_{i}", "en"))
            
            # Time the analysis
            start_time = datetime.now().timestamp()
            
            # Analyze all files concurrently
            tasks = [analyzer.analyze_translation_file(f[0], f[1], f[2]) for f in files]
            results = await asyncio.gather(*tasks)
            
            end_time = datetime.now().timestamp()
            total_time = end_time - start_time
            
            # Check results
            self.assertEqual(len(results), 100)
            self.assertTrue(all(r.status == FileStatus.VALID for r in results))
            
            # Performance check: should handle 100 files in under 2 seconds
            self.assertLess(total_time, 2.0)
            
            # Calculate rate
            rate = len(results) / total_time
            print(f"Performance: {rate:.0f} files/second")
    
    def test_performance(self):
        """Run async performance test."""
        asyncio.run(self.test_large_file_set_performance())


if __name__ == "__main__":
    unittest.main()