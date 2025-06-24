#!/usr/bin/env python3
"""
Test suite for Hebrew Translation Pipeline.
"""

import unittest
import asyncio
import tempfile
import shutil
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from hebrew_translation_pipeline import (
    HebrewTranslationPipeline,
    FileProcessingResult,
    PipelineStatistics,
    estimate_translation_cost
)
from openai_integration import HebrewTranslator, APIUsageStats


class TestFileProcessingResult(unittest.TestCase):
    """Test FileProcessingResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a processing result."""
        result = FileProcessingResult(
            file_id="test_001",
            issue_type="placeholder",
            success=True,
            processing_time=1.5,
            hebrew_char_count=150
        )
        
        self.assertEqual(result.file_id, "test_001")
        self.assertEqual(result.issue_type, "placeholder")
        self.assertTrue(result.success)
        self.assertEqual(result.processing_time, 1.5)
        self.assertEqual(result.hebrew_char_count, 150)
        self.assertIsNone(result.error)
    
    def test_failed_result(self):
        """Test creating a failed result."""
        result = FileProcessingResult(
            file_id="test_002",
            issue_type="missing",
            success=False,
            error="File not found"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "File not found")
        self.assertEqual(result.hebrew_char_count, 0)


class TestPipelineStatistics(unittest.TestCase):
    """Test PipelineStatistics dataclass."""
    
    def test_success_rate(self):
        """Test success rate calculation."""
        stats = PipelineStatistics(
            total_files=100,
            successful=85,
            failed=10,
            skipped=5
        )
        
        self.assertEqual(stats.success_rate, 85.0)
    
    def test_empty_statistics(self):
        """Test statistics with no files."""
        stats = PipelineStatistics()
        
        self.assertEqual(stats.success_rate, 0.0)
        self.assertEqual(stats.average_time_per_file, 0.0)
        self.assertEqual(stats.estimated_time_remaining, 0.0)
    
    def test_time_calculations(self):
        """Test time-related calculations."""
        stats = PipelineStatistics(
            total_files=100,
            successful=25,
            failed=5,
            total_time=250.0  # 10 seconds per file
        )
        
        self.assertEqual(stats.average_time_per_file, 10.0)
        # 70 files remaining (100 - 25 - 5 - 0) * 10 seconds each
        self.assertEqual(stats.estimated_time_remaining, 700.0)


class TestHebrewTranslationPipeline(unittest.IsolatedAsyncioTestCase):
    """Test HebrewTranslationPipeline class."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create test directories
        self.output_dir = self.test_path / "output"
        self.output_dir.mkdir()
        
        # Create test database
        self.db_path = self.test_path / "test.db"
        self._create_test_database()
        
        # Create test audit report
        self.audit_path = self.test_path / "audit_report.json"
        self._create_test_audit_report()
        
        # Create mock translator
        self.mock_translator = AsyncMock(spec=HebrewTranslator)
        self.mock_translator.model = "gpt-4o-mini"
        self.mock_translator.usage_stats = APIUsageStats()
        self.mock_translator.translate.return_value = "תרגום בעברית"
        self.mock_translator.save_progress = MagicMock()
        self.mock_translator.get_usage_stats.return_value = APIUsageStats()
    
    async def asyncTearDown(self):
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
                safe_filename TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE processing_status (
                file_id TEXT PRIMARY KEY,
                translation_he_status TEXT,
                last_updated TIMESTAMP
            )
        ''')
        
        # Insert test data
        test_files = [
            ('test_001', 'test1.mp4'),
            ('test_002', 'test2.mp4'),
            ('test_003', 'test3.mp4')
        ]
        
        for file_id, filename in test_files:
            cursor.execute(
                'INSERT INTO media_files VALUES (?, ?)',
                (file_id, filename)
            )
            cursor.execute(
                'INSERT INTO processing_status VALUES (?, ?, ?)',
                (file_id, 'pending', datetime.now())
            )
        
        conn.commit()
        conn.close()
    
    def _create_test_audit_report(self):
        """Create a test audit report."""
        audit_data = {
            "discrepancies": {
                "placeholder_file": [
                    {"file_id": "test_001", "language": "he"},
                    {"file_id": "test_002", "language": "he"}
                ],
                "missing_file": [
                    {"file_id": "test_003", "language": "he"}
                ]
            }
        }
        
        with open(self.audit_path, 'w') as f:
            json.dump(audit_data, f)
    
    def _create_test_files(self):
        """Create test English source files."""
        for file_id in ['test_001', 'test_002', 'test_003']:
            file_dir = self.output_dir / file_id
            file_dir.mkdir(exist_ok=True)
            
            en_file = file_dir / f"{file_id}.en.txt"
            en_file.write_text("This is a test English text for translation.")
            
            # Create placeholder Hebrew file for test_001
            if file_id == 'test_001':
                he_file = file_dir / f"{file_id}.he.txt"
                he_file.write_text("[HEBREW TRANSLATION]")
    
    async def test_load_audit_report(self):
        """Test loading and parsing audit report."""
        pipeline = HebrewTranslationPipeline(
            audit_report_path=self.audit_path,
            output_dir=self.output_dir,
            db_path=self.db_path,
            translator=self.mock_translator
        )
        
        placeholder_files, missing_files = pipeline.load_audit_report()
        
        self.assertEqual(len(placeholder_files), 2)
        self.assertEqual(len(missing_files), 1)
        self.assertEqual(placeholder_files[0]['file_id'], 'test_001')
        self.assertEqual(missing_files[0]['file_id'], 'test_003')
    
    async def test_process_file_success(self):
        """Test successful file processing."""
        self._create_test_files()
        
        pipeline = HebrewTranslationPipeline(
            audit_report_path=self.audit_path,
            output_dir=self.output_dir,
            db_path=self.db_path,
            translator=self.mock_translator,
            dry_run=True
        )
        
        result = await pipeline.process_file('test_001', 'placeholder')
        
        self.assertTrue(result.success)
        self.assertIsNone(result.error)
        self.assertGreater(result.hebrew_char_count, 0)
        self.mock_translator.translate.assert_called_once()
    
    async def test_process_file_missing_english(self):
        """Test processing when English file is missing."""
        pipeline = HebrewTranslationPipeline(
            audit_report_path=self.audit_path,
            output_dir=self.output_dir,
            db_path=self.db_path,
            translator=self.mock_translator
        )
        
        result = await pipeline.process_file('nonexistent', 'missing')
        
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
        self.mock_translator.translate.assert_not_called()
    
    async def test_process_file_empty_english(self):
        """Test processing when English file is empty."""
        # Create empty file
        file_dir = self.output_dir / 'empty_test'
        file_dir.mkdir()
        en_file = file_dir / 'empty_test.en.txt'
        en_file.write_text("")
        
        pipeline = HebrewTranslationPipeline(
            audit_report_path=self.audit_path,
            output_dir=self.output_dir,
            db_path=self.db_path,
            translator=self.mock_translator
        )
        
        result = await pipeline.process_file('empty_test', 'placeholder')
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Empty English source file")
    
    async def test_database_update(self):
        """Test database status updates."""
        self._create_test_files()
        
        pipeline = HebrewTranslationPipeline(
            audit_report_path=self.audit_path,
            output_dir=self.output_dir,
            db_path=self.db_path,
            translator=self.mock_translator,
            dry_run=False
        )
        
        # Process a file
        result = await pipeline.process_file('test_001', 'placeholder')
        
        # Update database
        await pipeline.update_database_status([result])
        
        # Check database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT translation_he_status FROM processing_status WHERE file_id = ?",
            ('test_001',)
        )
        status = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(status, 'completed')
    
    async def test_dry_run_mode(self):
        """Test dry run mode doesn't save files."""
        self._create_test_files()
        
        pipeline = HebrewTranslationPipeline(
            audit_report_path=self.audit_path,
            output_dir=self.output_dir,
            db_path=self.db_path,
            translator=self.mock_translator,
            dry_run=True
        )
        
        # Remove any existing Hebrew file
        he_file = self.output_dir / 'test_002' / 'test_002.he.txt'
        he_file.unlink(missing_ok=True)
        
        result = await pipeline.process_file('test_002', 'missing')
        
        self.assertTrue(result.success)
        # File should not exist in dry run mode
        self.assertFalse(he_file.exists())
    
    @patch('hebrew_translation_pipeline.print')
    async def test_progress_display(self, mock_print):
        """Test progress display."""
        pipeline = HebrewTranslationPipeline(
            audit_report_path=self.audit_path,
            output_dir=self.output_dir,
            db_path=self.db_path,
            translator=self.mock_translator
        )
        
        pipeline.statistics.start_time = datetime.now()
        pipeline.statistics.total_files = 100
        
        await pipeline.display_progress(50, 100, force=True)
        
        # Check that progress was printed
        mock_print.assert_called()
        call_args = str(mock_print.call_args)
        self.assertIn("50/100", call_args)
        self.assertIn("50.0%", call_args)
    
    async def test_full_pipeline_run(self):
        """Test complete pipeline execution."""
        self._create_test_files()
        
        pipeline = HebrewTranslationPipeline(
            audit_report_path=self.audit_path,
            output_dir=self.output_dir,
            db_path=self.db_path,
            translator=self.mock_translator,
            dry_run=True
        )
        
        stats = await pipeline.run()
        
        self.assertEqual(stats.total_files, 3)
        self.assertEqual(stats.successful, 3)
        self.assertEqual(stats.failed, 0)
        self.assertEqual(stats.success_rate, 100.0)


class TestCostEstimation(unittest.TestCase):
    """Test cost estimation functions."""
    
    def test_estimate_translation_cost(self):
        """Test translation cost estimation."""
        estimates = estimate_translation_cost(100, avg_chars=10000)
        
        self.assertIn('gpt-4o', estimates)
        self.assertIn('gpt-4o-mini', estimates)
        
        # Check gpt-4o-mini is cheaper
        self.assertLess(
            estimates['gpt-4o-mini']['total_cost'],
            estimates['gpt-4o']['total_cost']
        )
        
        # Verify calculations
        gpt4o_mini = estimates['gpt-4o-mini']
        self.assertAlmostEqual(
            gpt4o_mini['total_cost'],
            gpt4o_mini['input_cost'] + gpt4o_mini['output_cost'],
            places=2
        )
        self.assertAlmostEqual(
            gpt4o_mini['per_file'],
            gpt4o_mini['total_cost'] / 100,
            places=4
        )


if __name__ == '__main__':
    unittest.main()