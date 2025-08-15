"""
Memory profiling tests for subtitle translation system.

This module tests memory usage patterns and identifies potential memory leaks
in the translation pipeline.
"""

import os
import gc
import sys
import json
import psutil
import tempfile
import tracemalloc
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock
import pytest

# Import the modules to test
sys.path.insert(0, str(Path(__file__).parent.parent))

from scribe.srt_translator import SRTTranslator
from scribe.batch_language_detection import detect_languages_batch, detect_languages_for_segments


class TestMemoryUsage:
    """Test memory usage patterns in the translation system."""
    
    @pytest.fixture
    def process_monitor(self):
        """Monitor process memory usage."""
        process = psutil.Process()
        return process
    
    @pytest.fixture
    def memory_tracker(self):
        """Track memory allocations."""
        tracemalloc.start()
        yield
        tracemalloc.stop()
    
    def get_memory_usage(self, process_monitor):
        """Get current memory usage in MB."""
        return process_monitor.memory_info().rss / 1024 / 1024
    
    def test_memory_usage_srt_parsing(self, process_monitor, memory_tracker):
        """Test memory usage when parsing large SRT files."""
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        # Record initial memory
        gc.collect()
        initial_memory = self.get_memory_usage(process_monitor)
        
        # Create large SRT content (10,000 segments)
        segments = []
        for i in range(10000):
            segments.append(
                f"{i+1}\n{i//3600:02d}:{(i%3600)//60:02d}:{i%60:02d},000 --> "
                f"{i//3600:02d}:{(i%3600)//60:02d}:{(i%60)+1:02d},000\n"
                f"This is segment {i} with some text content that simulates real subtitles.\n"
            )
        large_srt = "\n".join(segments)
        
        # Parse the SRT
        parsed_segments = translator.parse_srt(large_srt)
        
        # Record memory after parsing
        after_parse_memory = self.get_memory_usage(process_monitor)
        memory_increase = after_parse_memory - initial_memory
        
        # Clean up
        del parsed_segments
        del large_srt
        gc.collect()
        
        # Record memory after cleanup
        final_memory = self.get_memory_usage(process_monitor)
        
        # Assertions
        assert memory_increase < 100  # Should use less than 100MB for 10k segments
        assert final_memory - initial_memory < 10  # Most memory should be released
        
        # Get memory snapshot
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')[:10]
        
        # Log top memory consumers
        print("\nTop 10 memory allocations:")
        for stat in top_stats:
            print(stat)
    
    def test_memory_leak_detection_file_processing(self, process_monitor, tmp_path):
        """Test for memory leaks in repeated file processing."""
        gc.collect()
        initial_memory = self.get_memory_usage(process_monitor)
        
        # Process multiple files in sequence
        memory_readings = []
        
        for i in range(10):
            # Create test file
            test_file = tmp_path / f"test_{i}.srt"
            test_file.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nTest content\n" * 100,
                encoding='utf-8'
            )
            
            # Create translator (should be garbage collected each iteration)
            translator = SRTTranslator(
                translator_type="openai",
                api_key="test-key"
            )
            
            # Parse file
            content = test_file.read_text(encoding='utf-8')
            segments = translator.parse_srt(content)
            
            # Force garbage collection
            del translator
            del segments
            del content
            gc.collect()
            
            # Record memory
            current_memory = self.get_memory_usage(process_monitor)
            memory_readings.append(current_memory)
        
        # Check for memory leak pattern
        # Memory should stabilize, not continuously increase
        first_half_avg = sum(memory_readings[:5]) / 5
        second_half_avg = sum(memory_readings[5:]) / 5
        
        # Allow for some variance but not continuous growth
        assert second_half_avg - first_half_avg < 5  # Less than 5MB growth
    
    def test_memory_usage_batch_processing(self, process_monitor, tmp_path):
        """Test memory usage during batch processing."""
        gc.collect()
        initial_memory = self.get_memory_usage(process_monitor)
        
        # Create batch of files
        files = []
        for i in range(50):
            file_path = tmp_path / f"batch_{i}.srt"
            file_path.write_text(
                f"1\n00:00:00,000 --> 00:00:01,000\nBatch file {i}\n" * 20,
                encoding='utf-8'
            )
            files.append(file_path)
        
        # Process batch
        texts = []
        for f in files:
            content = f.read_text(encoding='utf-8')
            texts.append(content)
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "en"
        mock_client.chat.completions.create.return_value = mock_response
        
        # Process texts in batches
        results = detect_languages_batch(texts, mock_client)
        
        # Check memory after batch processing
        after_batch_memory = self.get_memory_usage(process_monitor)
        memory_used = after_batch_memory - initial_memory
        
        # Clean up
        del results
        del detector
        gc.collect()
        
        final_memory = self.get_memory_usage(process_monitor)
        
        # Assertions
        assert memory_used < 50  # Should use less than 50MB for 50 files
        assert final_memory - initial_memory < 10  # Memory should be released
    
    def test_memory_usage_concurrent_operations(self, process_monitor):
        """Test memory usage with concurrent operations."""
        from concurrent.futures import ThreadPoolExecutor
        import threading
        
        gc.collect()
        initial_memory = self.get_memory_usage(process_monitor)
        memory_readings = []
        lock = threading.Lock()
        
        def process_item(item_id):
            """Simulate processing with memory allocation."""
            # Allocate some memory
            data = [f"Data_{item_id}_{i}" for i in range(1000)]
            
            # Record memory usage
            with lock:
                current_memory = self.get_memory_usage(process_monitor)
                memory_readings.append(current_memory)
            
            # Simulate work
            result = len(data)
            
            # Clean up
            del data
            return result
        
        # Process items concurrently
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_item, i) for i in range(20)]
            results = [f.result() for f in futures]
        
        # Force cleanup
        gc.collect()
        final_memory = self.get_memory_usage(process_monitor)
        
        # Check peak memory usage
        peak_memory = max(memory_readings) if memory_readings else initial_memory
        peak_increase = peak_memory - initial_memory
        
        # Assertions
        assert peak_increase < 100  # Peak should be reasonable
        assert final_memory - initial_memory < 10  # Memory should be released
    
    def test_memory_efficient_file_streaming(self, tmp_path):
        """Test memory-efficient file streaming for large files."""
        # Create a large file
        large_file = tmp_path / "large.srt"
        
        # Write file in chunks to avoid memory issues
        with open(large_file, 'w', encoding='utf-8') as f:
            for i in range(10000):
                f.write(f"{i+1}\n")
                f.write(f"00:{i//60:02d}:{i%60:02d},000 --> 00:{i//60:02d}:{(i%60)+1:02d},000\n")
                f.write(f"Segment {i} text\n\n")
        
        # Test streaming read
        def stream_read_file(file_path, chunk_size=8192):
            """Read file in chunks."""
            segments = []
            current_segment = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Process chunk (simplified)
                    lines = chunk.split('\n')
                    for line in lines:
                        if line.strip() == '' and current_segment:
                            segments.append('\n'.join(current_segment))
                            current_segment = []
                        else:
                            current_segment.append(line)
            
            return len(segments)
        
        # Measure memory usage during streaming
        tracemalloc.start()
        initial = tracemalloc.get_traced_memory()
        
        segment_count = stream_read_file(large_file)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Memory usage should be minimal for streaming
        memory_used_mb = (peak - initial[0]) / 1024 / 1024
        assert memory_used_mb < 10  # Should use less than 10MB for streaming


class TestMemoryOptimization:
    """Test memory optimization strategies."""
    
    def test_object_pooling_efficiency(self):
        """Test efficiency of object pooling for translators."""
        from queue import Queue
        
        class TranslatorPool:
            """Simple translator pool implementation."""
            
            def __init__(self, size=4):
                self.pool = Queue(maxsize=size)
                for _ in range(size):
                    translator = Mock(spec=SRTTranslator)
                    self.pool.put(translator)
            
            def acquire(self):
                """Get translator from pool."""
                return self.pool.get()
            
            def release(self, translator):
                """Return translator to pool."""
                self.pool.put(translator)
        
        # Test pool efficiency
        pool = TranslatorPool(size=2)
        
        # Track memory before
        tracemalloc.start()
        
        # Use translators from pool
        translators_used = []
        for i in range(10):
            t = pool.acquire()
            translators_used.append(id(t))  # Track object identity
            pool.release(t)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Check that we're reusing objects
        unique_translators = len(set(translators_used))
        assert unique_translators == 2  # Should only have 2 unique objects
        
        # Memory should be minimal
        memory_used_kb = peak / 1024
        assert memory_used_kb < 100  # Less than 100KB for pool
    
    def test_lazy_loading_optimization(self, tmp_path):
        """Test lazy loading of translation data."""
        
        class LazyTranslationLoader:
            """Lazy loader for translation data."""
            
            def __init__(self, file_path):
                self.file_path = file_path
                self._data = None
            
            @property
            def data(self):
                """Load data on first access."""
                if self._data is None:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        self._data = json.load(f)
                return self._data
            
            def clear(self):
                """Clear cached data."""
                self._data = None
        
        # Create test data file
        test_data = {"translations": [f"text_{i}" for i in range(1000)]}
        data_file = tmp_path / "translations.json"
        with open(data_file, 'w') as f:
            json.dump(test_data, f)
        
        # Test lazy loading
        tracemalloc.start()
        
        # Create loader (should not load data yet)
        loader = LazyTranslationLoader(data_file)
        after_create = tracemalloc.get_traced_memory()[0]
        
        # Access data (should load now)
        _ = loader.data
        after_load = tracemalloc.get_traced_memory()[0]
        
        # Clear data
        loader.clear()
        gc.collect()
        after_clear = tracemalloc.get_traced_memory()[0]
        
        tracemalloc.stop()
        
        # Verify lazy loading behavior
        assert after_load > after_create  # Data loaded on access
        assert after_clear < after_load  # Memory released after clear
    
    def test_generator_memory_efficiency(self):
        """Test memory efficiency of generators vs lists."""
        
        def create_segments_list(count):
            """Create all segments in memory."""
            return [f"Segment {i}" for i in range(count)]
        
        def create_segments_generator(count):
            """Generate segments on demand."""
            for i in range(count):
                yield f"Segment {i}"
        
        # Compare memory usage
        tracemalloc.start()
        
        # List approach
        list_start = tracemalloc.get_traced_memory()[0]
        segments_list = create_segments_list(10000)
        list_sum = sum(len(s) for s in segments_list)
        list_peak = tracemalloc.get_traced_memory()[1]
        
        # Clear list
        del segments_list
        gc.collect()
        
        # Generator approach
        gen_start = tracemalloc.get_traced_memory()[0]
        segments_gen = create_segments_generator(10000)
        gen_sum = sum(len(s) for s in segments_gen)
        gen_peak = tracemalloc.get_traced_memory()[1]
        
        tracemalloc.stop()
        
        # Verify results are the same
        assert list_sum == gen_sum
        
        # Generator should use significantly less memory
        list_memory = list_peak - list_start
        gen_memory = gen_peak - gen_start
        assert gen_memory < list_memory / 10  # Generator uses <10% of list memory
    
    def test_cache_memory_management(self):
        """Test memory management for translation cache."""
        from functools import lru_cache
        import weakref
        
        class TranslationCache:
            """Cache with memory management."""
            
            def __init__(self, max_size=100):
                self.cache = {}
                self.max_size = max_size
                self.access_count = {}
            
            def get(self, key):
                """Get from cache with LRU tracking."""
                if key in self.cache:
                    self.access_count[key] = self.access_count.get(key, 0) + 1
                    return self.cache[key]
                return None
            
            def put(self, key, value):
                """Add to cache with size limit."""
                if len(self.cache) >= self.max_size:
                    # Remove least recently used
                    lru_key = min(self.access_count, key=self.access_count.get)
                    del self.cache[lru_key]
                    del self.access_count[lru_key]
                
                self.cache[key] = value
                self.access_count[key] = 0
            
            def clear(self):
                """Clear cache."""
                self.cache.clear()
                self.access_count.clear()
        
        # Test cache memory management
        cache = TranslationCache(max_size=50)
        
        # Fill cache beyond limit
        for i in range(100):
            cache.put(f"key_{i}", f"value_{i}" * 100)
        
        # Check cache size is limited
        assert len(cache.cache) <= 50
        
        # Clear and check memory is released
        cache.clear()
        assert len(cache.cache) == 0


class TestMemoryLeakDetection:
    """Detect and prevent memory leaks."""
    
    def test_circular_reference_detection(self):
        """Test detection of circular references that prevent garbage collection."""
        
        class Node:
            """Node with potential circular reference."""
            def __init__(self, value):
                self.value = value
                self.parent = None
                self.children = []
            
            def add_child(self, child):
                self.children.append(child)
                child.parent = self  # Creates circular reference
        
        # Create circular reference
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        root = Node("root")
        child1 = Node("child1")
        child2 = Node("child2")
        root.add_child(child1)
        root.add_child(child2)
        
        # Delete references
        del root
        del child1
        del child2
        
        # Force garbage collection
        collected = gc.collect()
        
        # Check that circular references were collected
        assert collected > 0  # Should collect the circular references
        
        final_objects = len(gc.get_objects())
        # Object count should return to near initial
        assert abs(final_objects - initial_objects) < 100
    
    def test_file_handle_leak_prevention(self, tmp_path):
        """Test prevention of file handle leaks."""
        import resource
        
        # Get initial file descriptor count
        initial_fds = len(os.listdir('/proc/self/fd')) if os.path.exists('/proc/self/fd') else 0
        
        def process_files_unsafe():
            """Process files without proper cleanup (leak risk)."""
            files = []
            for i in range(10):
                f = open(tmp_path / f"test_{i}.txt", 'w')
                f.write("test")
                files.append(f)
                # Forgot to close!
            return files
        
        def process_files_safe():
            """Process files with proper cleanup."""
            for i in range(10):
                with open(tmp_path / f"test_{i}.txt", 'w') as f:
                    f.write("test")
        
        # Test safe version
        process_files_safe()
        
        # Check file descriptors
        if os.path.exists('/proc/self/fd'):
            current_fds = len(os.listdir('/proc/self/fd'))
            # Should not leak file descriptors
            assert current_fds - initial_fds < 5
    
    def test_thread_resource_cleanup(self):
        """Test proper cleanup of thread resources."""
        import threading
        
        def thread_worker(data_list, lock):
            """Worker that uses shared resources."""
            with lock:
                data_list.append(threading.current_thread().name)
        
        # Track active threads
        initial_threads = threading.active_count()
        
        # Create threads
        data = []
        lock = threading.Lock()
        threads = []
        
        for i in range(10):
            t = threading.Thread(target=thread_worker, args=(data, lock))
            t.start()
            threads.append(t)
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Check thread cleanup
        final_threads = threading.active_count()
        assert final_threads == initial_threads  # All threads should be cleaned up
        assert len(data) == 10  # All threads should have executed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])