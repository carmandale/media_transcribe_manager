"""
Performance benchmark tests for subtitle translation system.

This module tests the performance characteristics of the translation pipeline,
including translation speed, memory usage, and concurrent operation efficiency.
"""

import os
import time
import json
import threading
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

# Import the modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scribe.srt_translator import SRTTranslator
from scribe.batch_language_detection import detect_languages_batch, detect_languages_for_segments


class TestTranslationPerformance:
    """Benchmark tests for translation speed."""
    
    @pytest.fixture
    def sample_srt_small(self) -> str:
        """Small SRT file with 10 segments."""
        segments = []
        for i in range(1, 11):
            segments.append(f"{i}\n00:00:{i:02d},000 --> 00:00:{i+1:02d},000\nThis is segment {i}.\n")
        return "\n".join(segments)
    
    @pytest.fixture
    def sample_srt_medium(self) -> str:
        """Medium SRT file with 100 segments."""
        segments = []
        for i in range(1, 101):
            minutes = i // 60
            seconds = i % 60
            segments.append(
                f"{i}\n00:{minutes:02d}:{seconds:02d},000 --> 00:{minutes:02d}:{seconds+1:02d},000\n"
                f"This is a longer segment {i} with more text to translate.\n"
            )
        return "\n".join(segments)
    
    @pytest.fixture
    def sample_srt_large(self) -> str:
        """Large SRT file with 1000 segments (typical interview)."""
        segments = []
        for i in range(1, 1001):
            hours = i // 3600
            minutes = (i % 3600) // 60
            seconds = i % 60
            segments.append(
                f"{i}\n{hours:02d}:{minutes:02d}:{seconds:02d},000 --> {hours:02d}:{minutes:02d}:{seconds+1:02d},000\n"
                f"This is segment {i}. It contains a typical amount of text that you might find "
                f"in an interview transcript, with natural speech patterns and occasional pauses.\n"
            )
        return "\n".join(segments)
    
    @pytest.fixture
    def mock_translator(self):
        """Mock translator with realistic response times."""
        translator = Mock(spec=SRTTranslator)
        
        def mock_translate(text, source_lang, target_lang):
            # Simulate API latency based on text length
            word_count = len(text.split())
            delay = 0.001 * word_count  # 1ms per word
            time.sleep(delay)
            return f"[{target_lang}] {text}"
        
        translator.translate = Mock(side_effect=mock_translate)
        return translator
    
    def test_benchmark_parse_srt_small(self, benchmark, sample_srt_small):
        """Benchmark parsing small SRT files."""
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        result = benchmark(translator.parse_srt, sample_srt_small)
        assert len(result) == 10
    
    def test_benchmark_parse_srt_medium(self, benchmark, sample_srt_medium):
        """Benchmark parsing medium SRT files."""
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        result = benchmark(translator.parse_srt, sample_srt_medium)
        assert len(result) == 100
    
    def test_benchmark_parse_srt_large(self, benchmark, sample_srt_large):
        """Benchmark parsing large SRT files."""
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        result = benchmark(translator.parse_srt, sample_srt_large)
        assert len(result) == 1000
    
    @patch('scribe.srt_translator.OpenAI')
    def test_benchmark_translate_small_file(self, mock_openai, benchmark, sample_srt_small, tmp_path):
        """Benchmark translating small SRT files."""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock translation response
        def mock_create(**kwargs):
            response = MagicMock()
            response.choices = [MagicMock()]
            response.choices[0].message.content = f"Translated: {kwargs['messages'][1]['content']}"
            return response
        
        mock_client.chat.completions.create = mock_create
        
        # Create translator
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        # Create test file
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_small, encoding='utf-8')
        output_file = tmp_path / "output.srt"
        
        # Benchmark translation
        result = benchmark(
            translator.translate_srt_file,
            str(input_file),
            str(output_file),
            "en",
            "de"
        )
        
        assert output_file.exists()
    
    @patch('scribe.srt_translator.OpenAI')
    def test_benchmark_translate_large_file(self, mock_openai, benchmark, sample_srt_large, tmp_path):
        """Benchmark translating large SRT files (typical interview)."""
        # Mock OpenAI client with batching simulation
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        def mock_create(**kwargs):
            response = MagicMock()
            response.choices = [MagicMock()]
            # Simulate processing time
            time.sleep(0.01)  # 10ms per batch
            response.choices[0].message.content = f"Translated: {kwargs['messages'][1]['content'][:100]}"
            return response
        
        mock_client.chat.completions.create = mock_create
        
        # Create translator
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        # Create test file
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_large, encoding='utf-8')
        output_file = tmp_path / "output.srt"
        
        # Benchmark translation
        benchmark.pedantic(
            translator.translate_srt_file,
            args=(str(input_file), str(output_file), "en", "de"),
            rounds=3,
            iterations=1
        )
        
        assert output_file.exists()
    
    def test_benchmark_format_srt_generation(self, benchmark):
        """Benchmark SRT format generation."""
        # Create sample segments
        segments = []
        for i in range(100):
            segments.append({
                'index': i + 1,
                'start': f"00:00:{i:02d},000",
                'end': f"00:00:{i+1:02d},000",
                'text': f"This is translated segment {i}"
            })
        
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        result = benchmark(translator.format_srt, segments)
        assert len(result.split('\n\n')) >= 99  # At least 99 segments


class TestBatchProcessingPerformance:
    """Benchmark tests for batch processing efficiency."""
    
    @pytest.fixture
    def sample_files(self, tmp_path) -> List[Path]:
        """Create multiple sample SRT files."""
        files = []
        for i in range(10):
            file_path = tmp_path / f"interview_{i:03d}.srt"
            content = f"1\n00:00:00,000 --> 00:00:01,000\nInterview {i} content\n"
            file_path.write_text(content, encoding='utf-8')
            files.append(file_path)
        return files
    
    def test_benchmark_batch_detection(self, benchmark, sample_files):
        """Benchmark language detection for batch of files."""
        # Create text samples from files
        texts = []
        for f in sample_files:
            content = f.read_text(encoding='utf-8')
            texts.append(content)
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "en"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = benchmark(detect_languages_batch, texts[:10], mock_client)
        assert result is not None
    
    @patch('scribe.srt_translator.OpenAI')
    @patch('scribe.srt_translator.deepl.Translator')
    def test_benchmark_parallel_processing(self, mock_deepl, mock_openai, benchmark, tmp_path):
        """Benchmark parallel processing of multiple files."""
        # Setup mocks
        mock_openai_client = MagicMock()
        mock_openai.return_value = mock_openai_client
        
        def mock_translate(text, target_lang):
            return f"[{target_lang}] {text}"
        
        mock_deepl_instance = MagicMock()
        mock_deepl_instance.translate_text.return_value.text = "Translated text"
        mock_deepl.return_value = mock_deepl_instance
        
        # Create sample files
        files = []
        for i in range(4):  # Match worker count
            file_id = f"test_{i:03d}"
            input_dir = tmp_path / "output" / file_id
            input_dir.mkdir(parents=True)
            
            srt_file = input_dir / f"{file_id}.en.srt"
            srt_file.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTest content\n",
                encoding='utf-8'
            )
            files.append((str(srt_file), file_id))
        
        # Benchmark parallel processing
        def process_batch():
            results = []
            for file_path, file_id in files:
                # Simulate processing
                content = Path(file_path).read_text(encoding='utf-8')
                results.append(len(content))
            return results
        
        benchmark(process_batch)


class TestConcurrentOperationPerformance:
    """Benchmark tests for concurrent translation operations."""
    
    def test_benchmark_thread_pool_efficiency(self, benchmark, tmp_path):
        """Benchmark thread pool efficiency with multiple workers."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Create work items
        work_items = []
        for i in range(20):
            work_items.append({
                'id': f"item_{i}",
                'text': f"Text to translate {i} " * 10  # Moderate length text
            })
        
        def mock_translate(item):
            """Simulate translation work."""
            time.sleep(0.01)  # Simulate API latency
            return {
                'id': item['id'],
                'translated': f"Translated: {item['text'][:50]}"
            }
        
        def process_with_workers(worker_count):
            """Process items with specified worker count."""
            results = []
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(mock_translate, item): item
                    for item in work_items
                }
                
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
            
            return results
        
        # Benchmark with 4 workers (optimal for most systems)
        result = benchmark(process_with_workers, 4)
        assert len(result) == 20
    
    def test_benchmark_lock_contention(self, benchmark):
        """Benchmark impact of lock contention on concurrent operations."""
        import threading
        
        shared_counter = {'value': 0}
        lock = threading.Lock()
        
        def increment_with_lock():
            """Increment counter with lock."""
            for _ in range(1000):
                with lock:
                    shared_counter['value'] += 1
        
        def run_concurrent_increments():
            """Run multiple threads incrementing counter."""
            shared_counter['value'] = 0
            threads = []
            
            for _ in range(4):
                thread = threading.Thread(target=increment_with_lock)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            return shared_counter['value']
        
        result = benchmark(run_concurrent_increments)
        assert result == 4000  # 4 threads * 1000 increments
    
    def test_benchmark_queue_processing(self, benchmark):
        """Benchmark queue-based processing pattern."""
        import queue
        from concurrent.futures import ThreadPoolExecutor
        
        # Create work queue
        work_queue = queue.Queue()
        result_queue = queue.Queue()
        
        def worker():
            """Process items from queue."""
            while True:
                item = work_queue.get()
                if item is None:
                    break
                
                # Simulate processing
                time.sleep(0.001)
                result = f"Processed: {item}"
                result_queue.put(result)
                work_queue.task_done()
        
        def process_queue_items():
            """Process all items through queue."""
            # Add items to queue
            for i in range(100):
                work_queue.put(f"item_{i}")
            
            # Start workers
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(worker) for _ in range(4)]
                
                # Wait for completion
                work_queue.join()
                
                # Stop workers
                for _ in range(4):
                    work_queue.put(None)
                
                # Collect results
                results = []
                while not result_queue.empty():
                    results.append(result_queue.get())
                
                return results
        
        results = benchmark(process_queue_items)
        assert len(results) == 100


class TestScalabilityBenchmarks:
    """Benchmark tests for system scalability."""
    
    def test_benchmark_scaling_with_file_count(self, benchmark, tmp_path):
        """Benchmark how performance scales with number of files."""
        def create_and_process_files(file_count):
            """Create and process specified number of files."""
            files = []
            for i in range(file_count):
                file_path = tmp_path / f"file_{i:04d}.srt"
                file_path.write_text(
                    f"1\n00:00:00,000 --> 00:00:01,000\nContent {i}\n",
                    encoding='utf-8'
                )
                files.append(file_path)
            
            # Simulate processing
            results = []
            for f in files:
                # Minimal processing simulation
                content = f.read_text()
                results.append(len(content))
            
            return sum(results)
        
        # Test with 100 files
        result = benchmark(create_and_process_files, 100)
        assert result > 0
    
    def test_benchmark_scaling_with_segment_count(self, benchmark):
        """Benchmark how performance scales with segment count per file."""
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        def create_srt_with_segments(segment_count):
            """Create SRT content with specified segment count."""
            segments = []
            for i in range(segment_count):
                segments.append(
                    f"{i+1}\n00:00:{i:02d},000 --> 00:00:{i+1:02d},000\n"
                    f"Segment {i} text\n"
                )
            return "\n".join(segments)
        
        # Benchmark parsing 500 segments
        srt_content = create_srt_with_segments(500)
        result = benchmark(translator.parse_srt, srt_content)
        assert len(result) == 500
    
    def test_benchmark_api_batch_sizes(self, benchmark):
        """Benchmark optimal API batch sizes for translation."""
        
        def process_with_batch_size(texts, batch_size):
            """Process texts with specified batch size."""
            batches = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                # Simulate API call with batch
                time.sleep(0.01 * len(batch))  # Simulate processing time
                batches.append(batch)
            return len(batches)
        
        # Create sample texts
        texts = [f"Text segment {i}" for i in range(100)]
        
        # Benchmark batch size of 10 (typical for translation APIs)
        batch_count = benchmark(process_with_batch_size, texts, 10)
        assert batch_count == 10


class TestResourceUsageBenchmarks:
    """Benchmark tests for resource usage patterns."""
    
    def test_benchmark_file_io_operations(self, benchmark, tmp_path):
        """Benchmark file I/O operations for SRT files."""
        # Create test file
        test_file = tmp_path / "test.srt"
        content = "\n".join([
            f"{i}\n00:00:{i:02d},000 --> 00:00:{i+1:02d},000\nText {i}"
            for i in range(100)
        ])
        
        def write_and_read():
            """Write and read file."""
            test_file.write_text(content, encoding='utf-8')
            return test_file.read_text(encoding='utf-8')
        
        result = benchmark(write_and_read)
        assert len(result) > 0
    
    def test_benchmark_json_operations(self, benchmark, tmp_path):
        """Benchmark JSON operations for progress tracking."""
        # Create sample progress data
        progress_data = {
            'completed': [f"file_{i:04d}" for i in range(100)],
            'failed': [f"file_{i:04d}" for i in range(100, 110)],
            'in_progress': f"file_0110",
            'stats': {
                'total': 200,
                'completed': 100,
                'failed': 10,
                'remaining': 90
            }
        }
        
        progress_file = tmp_path / "progress.json"
        
        def save_and_load_progress():
            """Save and load progress data."""
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            
            with open(progress_file, 'r') as f:
                return json.load(f)
        
        result = benchmark(save_and_load_progress)
        assert result['stats']['total'] == 200
    
    def test_benchmark_database_operations(self, benchmark, tmp_path):
        """Benchmark database operations for status tracking."""
        import sqlite3
        
        db_path = tmp_path / "test.db"
        
        def setup_and_query_db():
            """Setup database and run queries."""
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Create table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_status (
                    file_id TEXT PRIMARY KEY,
                    status TEXT,
                    updated_at TIMESTAMP
                )
            ''')
            
            # Insert records
            for i in range(100):
                cursor.execute(
                    "INSERT OR REPLACE INTO processing_status VALUES (?, ?, datetime('now'))",
                    (f"file_{i:04d}", "completed")
                )
            
            conn.commit()
            
            # Query records
            cursor.execute("SELECT COUNT(*) FROM processing_status WHERE status = 'completed'")
            count = cursor.fetchone()[0]
            
            conn.close()
            return count
        
        result = benchmark(setup_and_query_db)
        assert result == 100


# Performance comparison fixtures for different translation providers
class TestProviderPerformanceComparison:
    """Compare performance across different translation providers."""
    
    @pytest.mark.parametrize("provider", ["openai", "deepl", "microsoft"])
    def test_benchmark_provider_initialization(self, benchmark, provider):
        """Benchmark provider initialization time."""
        
        def init_translator():
            return SRTTranslator(
                translator_type=provider,
                api_key="test-key"
            )
        
        with patch('scribe.srt_translator.OpenAI'), \
             patch('scribe.srt_translator.deepl.Translator'), \
             patch('scribe.srt_translator.Translator'):
            
            translator = benchmark(init_translator)
            assert translator is not None
    
    def test_benchmark_fallback_chain(self, benchmark):
        """Benchmark performance of fallback chain execution."""
        
        def execute_with_fallback():
            """Simulate fallback chain execution."""
            providers = ['openai', 'deepl', 'microsoft']
            
            for i, provider in enumerate(providers):
                try:
                    if i < 2:  # Simulate first two providers failing
                        raise Exception(f"{provider} failed")
                    
                    # Success on third provider
                    time.sleep(0.01)  # Simulate API call
                    return f"Success with {provider}"
                except Exception:
                    continue
            
            return None
        
        result = benchmark(execute_with_fallback)
        assert "microsoft" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])