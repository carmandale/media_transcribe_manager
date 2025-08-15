"""
Load testing for subtitle translation system.

This module performs load testing to verify system behavior under stress,
including concurrent operations, high volume processing, and resource limits.
"""

import os
import sys
import time
import json
import random
import threading
import tempfile
import statistics
from pathlib import Path
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from unittest.mock import Mock, patch, MagicMock
import pytest

# Import the modules to test
sys.path.insert(0, str(Path(__file__).parent.parent))

from scribe.srt_translator import SRTTranslator
from scribe.batch_language_detection import detect_languages_batch, detect_languages_for_segments


class TestConcurrentLoadTesting:
    """Load tests for concurrent translation operations."""
    
    @pytest.fixture
    def sample_files(self, tmp_path) -> List[Path]:
        """Create sample SRT files for load testing."""
        files = []
        for i in range(100):
            file_path = tmp_path / f"load_test_{i:04d}.srt"
            # Variable size files to simulate real workload
            segment_count = random.randint(10, 100)
            segments = []
            for j in range(segment_count):
                segments.append(
                    f"{j+1}\n00:{j//60:02d}:{j%60:02d},000 --> 00:{j//60:02d}:{(j%60)+1:02d},000\n"
                    f"This is segment {j} of file {i}.\n"
                )
            file_path.write_text("\n".join(segments), encoding='utf-8')
            files.append(file_path)
        return files
    
    def test_load_concurrent_file_processing(self, sample_files, tmp_path):
        """Test system under load with concurrent file processing."""
        
        def process_file_mock(file_path):
            """Mock file processing with simulated latency."""
            content = file_path.read_text(encoding='utf-8')
            # Simulate processing time based on file size
            time.sleep(0.001 * len(content) / 100)
            return {
                'file': file_path.name,
                'segments': content.count('\n\n'),
                'status': 'completed'
            }
        
        # Test with different worker counts
        worker_counts = [1, 2, 4, 8, 16]
        results = {}
        
        for worker_count in worker_counts:
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(process_file_mock, f): f
                    for f in sample_files
                }
                
                completed = []
                for future in as_completed(futures):
                    result = future.result()
                    completed.append(result)
            
            elapsed = time.time() - start_time
            results[worker_count] = {
                'time': elapsed,
                'throughput': len(sample_files) / elapsed,
                'completed': len(completed)
            }
            
            # All files should be processed
            assert len(completed) == len(sample_files)
        
        # Verify scaling efficiency
        # More workers should generally improve throughput
        assert results[4]['throughput'] > results[1]['throughput']
        
        # Log performance metrics
        print("\nLoad Test Results:")
        for workers, metrics in results.items():
            print(f"Workers: {workers:2d} | Time: {metrics['time']:.2f}s | "
                  f"Throughput: {metrics['throughput']:.1f} files/sec")
    
    def test_load_api_rate_limiting(self):
        """Test system behavior under API rate limits."""
        
        class RateLimitedAPI:
            """Mock API with rate limiting."""
            
            def __init__(self, requests_per_second=10):
                self.requests_per_second = requests_per_second
                self.last_request_time = 0
                self.request_count = 0
                self.lock = threading.Lock()
            
            def translate(self, text):
                """Translate with rate limiting."""
                with self.lock:
                    current_time = time.time()
                    time_since_last = current_time - self.last_request_time
                    
                    if time_since_last < 1.0 / self.requests_per_second:
                        sleep_time = (1.0 / self.requests_per_second) - time_since_last
                        time.sleep(sleep_time)
                    
                    self.last_request_time = time.time()
                    self.request_count += 1
                    
                    return f"Translated: {text[:20]}"
        
        # Create rate-limited API
        api = RateLimitedAPI(requests_per_second=20)
        
        # Generate concurrent requests
        def make_request(request_id):
            """Make API request."""
            start = time.time()
            result = api.translate(f"Text {request_id}")
            elapsed = time.time() - start
            return request_id, elapsed, result
        
        # Test with burst of concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(100)]
            results = [f.result() for f in futures]
        
        # Verify all requests completed
        assert len(results) == 100
        
        # Check rate limiting worked
        total_time = max(r[1] for r in results)
        actual_rate = len(results) / total_time
        assert actual_rate <= 25  # Should be close to limit with some overhead
    
    def test_load_memory_stress(self, tmp_path):
        """Test system behavior under memory pressure."""
        import gc
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Create large dataset
        large_files = []
        for i in range(50):
            file_path = tmp_path / f"large_{i}.srt"
            # Create file with many segments
            segments = []
            for j in range(500):
                segments.append(
                    f"{j+1}\n{j//3600:02d}:{(j%3600)//60:02d}:{j%60:02d},000 --> "
                    f"{j//3600:02d}:{(j%3600)//60:02d}:{(j%60)+1:02d},000\n"
                    f"This is a longer segment with more text to consume memory. " * 5 + "\n"
                )
            file_path.write_text("\n".join(segments), encoding='utf-8')
            large_files.append(file_path)
        
        # Process files concurrently
        def process_large_file(file_path):
            """Process large file."""
            content = file_path.read_text(encoding='utf-8')
            # Parse and hold in memory
            lines = content.split('\n')
            segments = []
            for i in range(0, len(lines), 4):
                if i + 2 < len(lines):
                    segments.append({
                        'index': lines[i],
                        'timing': lines[i+1] if i+1 < len(lines) else '',
                        'text': lines[i+2] if i+2 < len(lines) else ''
                    })
            return len(segments)
        
        # Process with limited workers to control memory
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_large_file, f) for f in large_files]
            results = [f.result() for f in futures]
        
        # Check memory usage
        peak_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = peak_memory - initial_memory
        
        # Clean up
        del large_files
        del results
        gc.collect()
        
        # Memory increase should be reasonable
        assert memory_increase < 500  # Less than 500MB increase
        
        # All files should be processed
        assert len(results) == 50
    
    def test_load_error_recovery(self):
        """Test system recovery under high error rates."""
        
        class UnreliableAPI:
            """Mock API that fails intermittently."""
            
            def __init__(self, failure_rate=0.3):
                self.failure_rate = failure_rate
                self.call_count = 0
                self.lock = threading.Lock()
            
            def translate(self, text, retry_count=3):
                """Translate with possible failures."""
                with self.lock:
                    self.call_count += 1
                
                for attempt in range(retry_count):
                    if random.random() > self.failure_rate:
                        return f"Translated: {text}"
                    
                    if attempt < retry_count - 1:
                        time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                
                raise Exception(f"Translation failed after {retry_count} attempts")
        
        # Create unreliable API
        api = UnreliableAPI(failure_rate=0.3)
        
        # Process many requests
        def process_with_retry(item_id):
            """Process with retry logic."""
            try:
                result = api.translate(f"Item {item_id}")
                return item_id, 'success', result
            except Exception as e:
                return item_id, 'failed', str(e)
        
        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(process_with_retry, i) for i in range(100)]
            results = [f.result() for f in futures]
        
        # Count successes and failures
        successes = sum(1 for _, status, _ in results if status == 'success')
        failures = sum(1 for _, status, _ in results if status == 'failed')
        
        # With 30% failure rate and 3 retries, most should succeed
        assert successes > 60  # At least 60% should succeed
        assert api.call_count > 100  # Should have retries
        
        print(f"\nError Recovery: {successes} successes, {failures} failures, "
              f"{api.call_count} total API calls")


class TestScalabilityLoadTesting:
    """Test system scalability under various load patterns."""
    
    def test_load_linear_scaling(self, tmp_path):
        """Test linear scaling with increasing workload."""
        
        def create_workload(size):
            """Create workload of specified size."""
            files = []
            for i in range(size):
                file_path = tmp_path / f"scale_{size}_{i}.srt"
                file_path.write_text(
                    f"1\n00:00:00,000 --> 00:00:01,000\nContent {i}\n",
                    encoding='utf-8'
                )
                files.append(file_path)
            return files
        
        def process_workload(files):
            """Process workload and measure time."""
            start = time.time()
            results = []
            for f in files:
                content = f.read_text(encoding='utf-8')
                results.append(len(content))
            return time.time() - start
        
        # Test with increasing workload sizes
        sizes = [10, 20, 40, 80]
        times = []
        
        for size in sizes:
            files = create_workload(size)
            elapsed = process_workload(files)
            times.append(elapsed)
            
            # Clean up
            for f in files:
                f.unlink()
        
        # Check for roughly linear scaling
        # Time should roughly double as workload doubles
        for i in range(1, len(times)):
            ratio = times[i] / times[i-1]
            # Allow for some variance (1.5x to 2.5x)
            assert 1.5 <= ratio <= 2.5
    
    def test_load_burst_traffic(self):
        """Test system response to burst traffic patterns."""
        
        class RequestTracker:
            """Track request patterns."""
            
            def __init__(self):
                self.requests = []
                self.lock = threading.Lock()
            
            def record_request(self, request_id):
                """Record request with timestamp."""
                with self.lock:
                    self.requests.append({
                        'id': request_id,
                        'time': time.time()
                    })
        
        tracker = RequestTracker()
        
        def process_request(request_id, delay=0):
            """Process request with optional delay."""
            time.sleep(delay)
            tracker.record_request(request_id)
            # Simulate work
            time.sleep(random.uniform(0.01, 0.05))
            return request_id
        
        # Create burst pattern
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            
            # First burst
            for i in range(50):
                futures.append(executor.submit(process_request, f"burst1_{i}"))
            
            # Pause
            time.sleep(0.5)
            
            # Second burst
            for i in range(50):
                futures.append(executor.submit(process_request, f"burst2_{i}", 0))
            
            # Collect results
            results = [f.result() for f in futures]
        
        # Analyze request patterns
        assert len(tracker.requests) == 100
        
        # Calculate request rate over time windows
        start_time = min(r['time'] for r in tracker.requests)
        end_time = max(r['time'] for r in tracker.requests)
        duration = end_time - start_time
        
        # System should handle bursts without failing
        assert len(results) == 100
        assert duration < 5  # Should complete reasonably quickly
    
    def test_load_sustained_throughput(self):
        """Test sustained throughput over extended period."""
        
        class ThroughputMonitor:
            """Monitor throughput over time."""
            
            def __init__(self, window_size=1.0):
                self.window_size = window_size
                self.completed = []
                self.lock = threading.Lock()
            
            def record_completion(self, item_id):
                """Record completion time."""
                with self.lock:
                    self.completed.append({
                        'id': item_id,
                        'time': time.time()
                    })
            
            def get_throughput(self, current_time):
                """Calculate current throughput."""
                with self.lock:
                    window_start = current_time - self.window_size
                    recent = [c for c in self.completed 
                             if c['time'] >= window_start]
                    return len(recent) / self.window_size if recent else 0
        
        monitor = ThroughputMonitor()
        
        def sustained_worker(item_id, duration=5):
            """Worker for sustained load."""
            start = time.time()
            while time.time() - start < duration:
                # Simulate work
                time.sleep(random.uniform(0.01, 0.03))
                monitor.record_completion(f"{item_id}_{time.time()}")
            return item_id
        
        # Run sustained load
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(sustained_worker, i, 2) for i in range(4)]
            results = [f.result() for f in futures]
        
        # Calculate throughput statistics
        if monitor.completed:
            throughputs = []
            for c in monitor.completed[10:]:  # Skip warmup
                tp = monitor.get_throughput(c['time'])
                if tp > 0:
                    throughputs.append(tp)
            
            if throughputs:
                avg_throughput = statistics.mean(throughputs)
                std_throughput = statistics.stdev(throughputs) if len(throughputs) > 1 else 0
                
                # Throughput should be relatively stable
                assert avg_throughput > 50  # At least 50 items/sec
                if std_throughput > 0:
                    coefficient_of_variation = std_throughput / avg_throughput
                    assert coefficient_of_variation < 0.5  # Relatively stable


class TestResourceLimitTesting:
    """Test system behavior at resource limits."""
    
    def test_load_max_thread_limit(self):
        """Test system with maximum thread limit."""
        import threading
        
        initial_threads = threading.active_count()
        max_threads = 100
        
        def thread_worker(item_id, barrier):
            """Worker that waits at barrier."""
            barrier.wait()
            return item_id
        
        # Create barrier for synchronization
        barrier = threading.Barrier(max_threads + 1)
        
        threads = []
        try:
            for i in range(max_threads):
                t = threading.Thread(target=thread_worker, args=(i, barrier))
                t.start()
                threads.append(t)
            
            # Check thread count
            current_threads = threading.active_count()
            assert current_threads - initial_threads <= max_threads + 5  # Some overhead
            
            # Release all threads
            barrier.wait()
            
        finally:
            # Clean up
            for t in threads:
                t.join(timeout=1)
        
        # Verify cleanup
        final_threads = threading.active_count()
        assert final_threads <= initial_threads + 5
    
    def test_load_file_descriptor_limit(self, tmp_path):
        """Test system behavior at file descriptor limits."""
        import resource
        
        # Get current limit
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        
        # Create many files
        files = []
        file_handles = []
        
        try:
            # Try to open many files (but stay under limit)
            target_count = min(100, soft_limit - 50)
            
            for i in range(target_count):
                file_path = tmp_path / f"fd_test_{i}.txt"
                file_path.write_text(f"Test {i}")
                files.append(file_path)
            
            # Open files simultaneously
            for f in files[:50]:  # Open subset to avoid hitting limit
                handle = open(f, 'r')
                file_handles.append(handle)
            
            # Should handle this without issues
            assert len(file_handles) == 50
            
        finally:
            # Clean up
            for handle in file_handles:
                handle.close()
    
    def test_load_queue_saturation(self):
        """Test behavior with saturated work queues."""
        import queue
        from concurrent.futures import ThreadPoolExecutor
        
        work_queue = queue.Queue(maxsize=10)
        result_queue = queue.Queue()
        
        def producer(count):
            """Add items to queue."""
            for i in range(count):
                try:
                    work_queue.put(f"item_{i}", timeout=1)
                except queue.Full:
                    result_queue.put(('dropped', i))
        
        def consumer():
            """Process items from queue."""
            while True:
                try:
                    item = work_queue.get(timeout=0.5)
                    if item is None:
                        break
                    # Simulate slow processing
                    time.sleep(0.1)
                    result_queue.put(('processed', item))
                    work_queue.task_done()
                except queue.Empty:
                    break
        
        # Start consumers and producers
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Start consumers
            consumer_futures = [executor.submit(consumer) for _ in range(2)]
            
            # Start producers (will overwhelm queue)
            producer_future = executor.submit(producer, 50)
            
            # Wait for producer
            producer_future.result()
            
            # Signal consumers to stop
            for _ in range(2):
                work_queue.put(None)
            
            # Wait for consumers
            for f in consumer_futures:
                f.result()
        
        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())
        
        processed = sum(1 for r in results if r[0] == 'processed')
        dropped = sum(1 for r in results if r[0] == 'dropped')
        
        # Should process some but may drop some due to queue limit
        assert processed > 0
        assert processed + dropped <= 50


class TestPerformanceRegression:
    """Test for performance regressions."""
    
    def test_performance_baseline_parsing(self):
        """Establish baseline performance for SRT parsing."""
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        # Create standard test file
        segments = []
        for i in range(100):
            segments.append(
                f"{i+1}\n00:00:{i:02d},000 --> 00:00:{i+1:02d},000\n"
                f"Standard segment text for baseline testing.\n"
            )
        srt_content = "\n".join(segments)
        
        # Measure parsing time
        iterations = 100
        times = []
        
        for _ in range(iterations):
            start = time.time()
            result = translator.parse_srt(srt_content)
            elapsed = time.time() - start
            times.append(elapsed)
        
        # Calculate statistics
        avg_time = statistics.mean(times)
        std_time = statistics.stdev(times)
        
        # Performance assertions (adjust based on hardware)
        assert avg_time < 0.01  # Should parse in less than 10ms
        assert std_time < avg_time * 0.5  # Consistent performance
        
        print(f"\nParsing Baseline: {avg_time*1000:.2f}ms ± {std_time*1000:.2f}ms")
    
    def test_performance_baseline_formatting(self):
        """Establish baseline performance for SRT formatting."""
        translator = SRTTranslator(
            translator_type="openai",
            api_key="test-key"
        )
        
        # Create standard segments
        segments = []
        for i in range(100):
            segments.append({
                'index': i + 1,
                'start': f"00:00:{i:02d},000",
                'end': f"00:00:{i+1:02d},000",
                'text': f"Formatted segment {i}"
            })
        
        # Measure formatting time
        iterations = 100
        times = []
        
        for _ in range(iterations):
            start = time.time()
            result = translator.format_srt(segments)
            elapsed = time.time() - start
            times.append(elapsed)
        
        # Calculate statistics
        avg_time = statistics.mean(times)
        std_time = statistics.stdev(times)
        
        # Performance assertions
        assert avg_time < 0.005  # Should format in less than 5ms
        assert std_time < avg_time * 0.5  # Consistent performance
        
        print(f"\nFormatting Baseline: {avg_time*1000:.2f}ms ± {std_time*1000:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])