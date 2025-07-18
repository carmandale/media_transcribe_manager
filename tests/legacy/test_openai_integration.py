#!/usr/bin/env python3
"""
Test suite for OpenAI API integration for Hebrew translation.
Tests API connection, translation quality, error handling, and cost tracking.
"""

import os
import asyncio
import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import time

import openai
from dotenv import load_dotenv

from openai_integration import (
    HebrewTranslator, APIUsageStats, TranslationProgress, PRICING
)


class TestAPIUsageStats(unittest.TestCase):
    """Test cases for APIUsageStats class."""
    
    def setUp(self):
        """Set up test instance."""
        self.stats = APIUsageStats()
    
    def test_calculate_cost(self):
        """Test cost calculation for different models."""
        # Test GPT-4 Turbo pricing
        cost = self.stats.calculate_cost(1000, 1000, "gpt-4-turbo-preview")
        expected = (1000/1000 * 0.01) + (1000/1000 * 0.03)
        self.assertAlmostEqual(cost, expected, places=4)
        
        # Test with different token counts
        cost = self.stats.calculate_cost(5000, 2000, "gpt-4-0125-preview")
        expected = (5000/1000 * 0.01) + (2000/1000 * 0.03)
        self.assertAlmostEqual(cost, expected, places=4)
        
        # Test unknown model fallback
        cost = self.stats.calculate_cost(1000, 1000, "unknown-model")
        expected = (1000/1000 * 0.01) + (1000/1000 * 0.03)
        self.assertAlmostEqual(cost, expected, places=4)
    
    def test_update_stats(self):
        """Test updating usage statistics."""
        # Update with successful request
        self.stats.update(1500, 2000, "gpt-4-turbo-preview", success=True)
        
        self.assertEqual(self.stats.total_requests, 1)
        self.assertEqual(self.stats.successful_requests, 1)
        self.assertEqual(self.stats.failed_requests, 0)
        self.assertEqual(self.stats.total_prompt_tokens, 1500)
        self.assertEqual(self.stats.total_completion_tokens, 2000)
        self.assertEqual(self.stats.total_tokens, 3500)
        
        expected_cost = (1500/1000 * 0.01) + (2000/1000 * 0.03)
        self.assertAlmostEqual(self.stats.total_cost, expected_cost, places=4)
        
        # Update with failed request
        self.stats.update(0, 0, "gpt-4-turbo-preview", success=False)
        
        self.assertEqual(self.stats.total_requests, 2)
        self.assertEqual(self.stats.successful_requests, 1)
        self.assertEqual(self.stats.failed_requests, 1)
    
    def test_add_error(self):
        """Test error tracking."""
        self.stats.add_error("RateLimitError", "Too many requests", "file_123")
        
        self.assertEqual(len(self.stats.errors), 1)
        error = self.stats.errors[0]
        self.assertEqual(error['type'], "RateLimitError")
        self.assertEqual(error['message'], "Too many requests")
        self.assertEqual(error['file_id'], "file_123")
        self.assertIn('timestamp', error)
    
    def test_cost_warning_threshold(self):
        """Test cost warning at $10 increments."""
        # This should trigger warning at $10
        with patch('openai_integration.logger') as mock_logger:
            # Add requests totaling just over $10
            for _ in range(100):
                self.stats.update(1000, 1000, "gpt-4-turbo-preview")
            
            # Check if warning was logged
            warning_called = any(
                call[0][0].startswith("Total API cost has exceeded")
                for call in mock_logger.warning.call_args_list
            )
            self.assertTrue(warning_called)


class TestTranslationProgress(unittest.TestCase):
    """Test cases for TranslationProgress class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.progress = TranslationProgress()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_mark_completed(self):
        """Test marking files as completed."""
        self.progress.mark_completed("file_001")
        self.progress.mark_completed("file_002")
        
        self.assertIn("file_001", self.progress.completed_files)
        self.assertIn("file_002", self.progress.completed_files)
        self.assertTrue(self.progress.is_completed("file_001"))
        
        # Test duplicate handling
        self.progress.mark_completed("file_001")
        self.assertEqual(self.progress.completed_files.count("file_001"), 1)
    
    def test_mark_failed(self):
        """Test marking files as failed."""
        self.progress.mark_failed("file_003", "API error")
        
        self.assertEqual(len(self.progress.failed_files), 1)
        failed = self.progress.failed_files[0]
        self.assertEqual(failed['file_id'], "file_003")
        self.assertEqual(failed['reason'], "API error")
        self.assertIn('timestamp', failed)
    
    def test_save_and_load(self):
        """Test saving and loading progress."""
        # Add some progress
        self.progress.mark_completed("file_001")
        self.progress.mark_completed("file_002")
        self.progress.mark_failed("file_003", "Network error")
        
        # Save to file
        progress_file = self.test_path / "progress.json"
        self.progress.save(progress_file)
        
        self.assertTrue(progress_file.exists())
        
        # Load from file
        loaded = TranslationProgress.load(progress_file)
        
        self.assertEqual(len(loaded.completed_files), 2)
        self.assertIn("file_001", loaded.completed_files)
        self.assertIn("file_002", loaded.completed_files)
        self.assertEqual(len(loaded.failed_files), 1)
        self.assertEqual(loaded.failed_files[0]['file_id'], "file_003")
    
    def test_load_nonexistent_file(self):
        """Test loading from non-existent file."""
        progress_file = self.test_path / "nonexistent.json"
        loaded = TranslationProgress.load(progress_file)
        
        # Should return empty progress
        self.assertEqual(len(loaded.completed_files), 0)
        self.assertEqual(len(loaded.failed_files), 0)


class TestHebrewTranslator(unittest.IsolatedAsyncioTestCase):
    """Test cases for HebrewTranslator class."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create test translator with mock API key
        self.translator = HebrewTranslator(
            api_key="test-api-key",
            progress_file=self.test_path / "test_progress.json"
        )
    
    async def asyncTearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    @patch('openai.AsyncOpenAI')
    async def test_translate_success(self, mock_openai_class):
        """Test successful translation."""
        # Mock the OpenAI response
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="שלום עולם"))]
        mock_response.usage = MagicMock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Create new translator with mocked client
        translator = HebrewTranslator(api_key="test-key")
        translator.client = mock_client
        
        # Perform translation
        result = await translator.translate("Hello world", "test_001")
        
        self.assertEqual(result, "שלום עולם")
        self.assertTrue(translator.progress.is_completed("test_001"))
        self.assertEqual(translator.usage_stats.successful_requests, 1)
        self.assertEqual(translator.usage_stats.total_prompt_tokens, 100)
        self.assertEqual(translator.usage_stats.total_completion_tokens, 50)
    
    @patch('openai.AsyncOpenAI')
    async def test_translate_with_retry(self, mock_openai_class):
        """Test translation with retry on rate limit."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # First call raises rate limit error, second succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="תרגום"))]
        mock_response.usage = MagicMock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                openai.RateLimitError("Rate limit exceeded", response=None, body=None),
                mock_response
            ]
        )
        
        translator = HebrewTranslator(api_key="test-key")
        translator.client = mock_client
        
        # Should succeed after retry
        result = await translator.translate("Test", "test_002")
        
        self.assertEqual(result, "תרגום")
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)
    
    @patch('openai.AsyncOpenAI')
    async def test_translate_failure(self, mock_openai_class):
        """Test handling of translation failure."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # All attempts fail
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.APIError("Server error", response=None, body=None)
        )
        
        translator = HebrewTranslator(api_key="test-key")
        translator.client = mock_client
        
        result = await translator.translate("Test", "test_003")
        
        self.assertIsNone(result)
        self.assertEqual(translator.usage_stats.failed_requests, 1)
        self.assertEqual(len(translator.progress.failed_files), 1)
        self.assertEqual(translator.progress.failed_files[0]['file_id'], "test_003")
    
    async def test_skip_completed_files(self):
        """Test that completed files are skipped."""
        # Mark file as completed
        self.translator.progress.mark_completed("test_004")
        
        result = await self.translator.translate("Test", "test_004")
        
        self.assertIsNone(result)
    
    @patch('openai.AsyncOpenAI')
    async def test_batch_translation(self, mock_openai_class):
        """Test batch translation functionality."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock responses for batch
        responses = [
            MagicMock(
                choices=[MagicMock(message=MagicMock(content=f"תרגום {i}"))],
                usage=MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            )
            for i in range(3)
        ]
        
        mock_client.chat.completions.create = AsyncMock(side_effect=responses)
        
        translator = HebrewTranslator(api_key="test-key", max_concurrent=2)
        translator.client = mock_client
        
        # Prepare batch
        texts = [
            ("file_001", "Text 1"),
            ("file_002", "Text 2"),
            ("file_003", "Text 3")
        ]
        
        # Track progress
        progress_updates = []
        def progress_callback(completed, total):
            progress_updates.append((completed, total))
        
        results = await translator.translate_batch(texts, progress_callback)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(results["file_001"], "תרגום 0")
        self.assertEqual(results["file_002"], "תרגום 1")
        self.assertEqual(results["file_003"], "תרגום 2")
        
        # Check progress updates
        self.assertEqual(len(progress_updates), 3)
        self.assertEqual(progress_updates[-1], (3, 3))
    
    def test_estimate_cost(self):
        """Test cost estimation."""
        texts = [
            "This is a sample text with about 50 characters.",
            "Another sample text that's a bit longer with more content here.",
            "A third text sample for testing cost estimation functionality."
        ]
        
        estimate = self.translator.estimate_cost(texts)
        
        # Check structure
        self.assertIn('total_characters', estimate)
        self.assertIn('estimated_input_tokens', estimate)
        self.assertIn('estimated_output_tokens', estimate)
        self.assertIn('estimated_total_cost', estimate)
        self.assertIn('cost_per_file', estimate)
        
        # Verify calculations
        total_chars = sum(len(text) for text in texts)
        self.assertEqual(estimate['total_characters'], total_chars)
        
        # Rough token estimate (1 token ≈ 4 chars)
        expected_tokens = total_chars / 4
        self.assertAlmostEqual(
            estimate['estimated_input_tokens'],
            expected_tokens,
            delta=10
        )
        
        # Cost calculation
        input_cost = (expected_tokens / 1000) * PRICING["gpt-4-0125-preview"]["input"]
        output_cost = (expected_tokens / 1000) * PRICING["gpt-4-0125-preview"]["output"]
        expected_total = input_cost + output_cost
        
        self.assertAlmostEqual(
            estimate['estimated_total_cost'],
            expected_total,
            places=2
        )
    
    @patch('openai.AsyncOpenAI')
    async def test_connection_test(self, mock_openai_class):
        """Test API connection testing."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="חיבור מוצלח"))]
        mock_response.usage = MagicMock(
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30
        )
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        translator = HebrewTranslator(api_key="test-key")
        translator.client = mock_client
        
        result = await translator.test_connection()
        
        self.assertTrue(result)
        self.assertEqual(translator.usage_stats.successful_requests, 1)
    
    def test_save_usage_report(self):
        """Test saving usage report."""
        # Add some usage data
        self.translator.usage_stats.update(1000, 500, "gpt-4-0125-preview")
        self.translator.progress.mark_completed("file_001")
        self.translator.progress.mark_failed("file_002", "Test error")
        
        # Save report
        report_path = self.test_path / "usage_report.json"
        self.translator.save_usage_report(report_path)
        
        self.assertTrue(report_path.exists())
        
        # Load and verify report
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        self.assertIn('usage_stats', report)
        self.assertIn('progress', report)
        self.assertIn('model_config', report)
        
        self.assertEqual(report['usage_stats']['total_requests'], 1)
        self.assertEqual(report['progress']['completed_files'], 1)
        self.assertEqual(report['progress']['failed_files'], 1)
        self.assertAlmostEqual(report['progress']['completion_rate'], 0.5, places=2)


class TestIntegrationScenarios(unittest.IsolatedAsyncioTestCase):
    """Integration tests with real-world scenarios."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
    
    async def asyncTearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    @patch('openai.AsyncOpenAI')
    async def test_resume_after_interruption(self, mock_openai_class):
        """Test resume capability after interruption."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # First session - complete 2 files
        progress_file = self.test_path / "progress.json"
        translator1 = HebrewTranslator(api_key="test-key", progress_file=progress_file)
        translator1.progress.mark_completed("file_001")
        translator1.progress.mark_completed("file_002")
        translator1.save_progress()
        
        # Second session - should skip completed files
        translator2 = HebrewTranslator(api_key="test-key", progress_file=progress_file)
        
        self.assertTrue(translator2.progress.is_completed("file_001"))
        self.assertTrue(translator2.progress.is_completed("file_002"))
        self.assertEqual(len(translator2.progress.completed_files), 2)
    
    @patch('openai.AsyncOpenAI')
    async def test_concurrent_rate_limiting(self, mock_openai_class):
        """Test concurrent request limiting."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Track concurrent calls
        concurrent_calls = []
        max_concurrent = 0
        
        async def mock_create(*args, **kwargs):
            concurrent_calls.append(time.time())
            nonlocal max_concurrent
            
            # Count current concurrent calls (within 0.1 second window)
            current_time = time.time()
            current_concurrent = sum(
                1 for t in concurrent_calls 
                if current_time - t < 0.1
            )
            max_concurrent = max(max_concurrent, current_concurrent)
            
            await asyncio.sleep(0.05)  # Simulate API delay
            
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content="תרגום"))],
                usage=MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            )
        
        mock_client.chat.completions.create = mock_create
        
        # Create translator with limited concurrency
        translator = HebrewTranslator(api_key="test-key", max_concurrent=3)
        translator.client = mock_client
        
        # Try to translate many files at once
        texts = [(f"file_{i:03d}", f"Text {i}") for i in range(10)]
        
        results = await translator.translate_batch(texts)
        
        # Should have processed all files
        self.assertEqual(len(results), 10)
        
        # But never exceeded max concurrent
        self.assertLessEqual(max_concurrent, 3)


class TestRealAPIConnection(unittest.IsolatedAsyncioTestCase):
    """Test with real OpenAI API (requires OPENAI_API_KEY in env)."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.skip_real_api = not bool(self.api_key)
        
        if not self.skip_real_api:
            self.translator = HebrewTranslator(api_key=self.api_key)
    
    async def test_real_connection(self):
        """Test real API connection."""
        if self.skip_real_api:
            self.skipTest("OPENAI_API_KEY not found in environment")
        
        connected = await self.translator.test_connection()
        self.assertTrue(connected)
    
    async def test_real_translation(self):
        """Test real translation quality."""
        if self.skip_real_api:
            self.skipTest("OPENAI_API_KEY not found in environment")
        
        # Sample from Scribe-style transcription
        sample_text = """
        Well, I was born in Berlin in 1925. My father was a doctor, 
        and we lived in a nice neighborhood until things started to change.
        """
        
        hebrew = await self.translator.translate(sample_text.strip(), "test_real_001")
        
        self.assertIsNotNone(hebrew)
        # Should contain Hebrew characters
        hebrew_chars = any('\u0590' <= c <= '\u05FF' for c in hebrew)
        self.assertTrue(hebrew_chars, "Translation should contain Hebrew characters")
        
        # Check cost tracking
        stats = self.translator.get_usage_stats()
        self.assertGreater(stats.total_cost, 0)
        self.assertLess(stats.total_cost, 0.50)  # Should be well under 50 cents
        
        print(f"\nReal translation test:")
        print(f"Original: {sample_text[:50]}...")
        print(f"Hebrew: {hebrew[:50]}...")
        print(f"Cost: ${stats.total_cost:.4f}")


if __name__ == "__main__":
    unittest.main()