"""
Comprehensive tests for the utils module.

Tests cover all utility functions including:
- Path normalization and sanitization
- File ID generation
- Progress tracking
- Worker pool management
- Directory management
- General utility functions
"""
import pytest
import time
import uuid
import hashlib
import unicodedata
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from concurrent.futures import TimeoutError

from scribe.utils import (
    normalize_path, sanitize_filename, generate_file_id,
    ensure_directory, ProgressTracker, SimpleWorkerPool, WorkerPoolError,
    calculate_checksum, get_file_info, find_transcript_file, chunk_list, safe_execute
)


class TestPathUtilities:
    """Test path handling utilities."""
    
    @pytest.mark.unit
    def test_normalize_path(self):
        """Test path normalization."""
        # Basic path
        path = normalize_path("/test/path/file.mp4")
        assert isinstance(path, Path)
        assert path.is_absolute()
        
        # Path with Unicode
        unicode_path = normalize_path("/test/παθ/文件.mp4")
        assert isinstance(unicode_path, Path)
        
        # Relative path becomes absolute
        rel_path = normalize_path("./relative/path")
        assert rel_path.is_absolute()
        
        # Path with spaces
        space_path = normalize_path("/test/path with spaces/file.mp4")
        assert isinstance(space_path, Path)
    
    @pytest.mark.unit
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Normal filename
        assert sanitize_filename("normal_file.mp4") == "normal_file.mp4"
        
        # Filename with spaces
        assert sanitize_filename("file with spaces.mp4") == "file_with_spaces.mp4"
        
        # Special characters
        assert sanitize_filename("file:with*special?chars.mp4") == "file_with_special_chars.mp4"
        
        # Unicode characters
        assert sanitize_filename("файл_文件.mp4") == "файл_文件.mp4"
        
        # Leading/trailing spaces
        assert sanitize_filename("  file.mp4  ") == "file.mp4"
        
        # Multiple dots
        assert sanitize_filename("file.name.with.dots.mp4") == "file.name.with.dots.mp4"
        
        # Very long filename
        long_name = "a" * 300 + ".mp4"
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) <= 255  # Max filename length on most systems
        assert sanitized.endswith(".mp4")
    
    @pytest.mark.unit
    def test_sanitize_filename_edge_cases(self):
        """Test edge cases for filename sanitization."""
        # Empty string
        assert sanitize_filename("") == "unnamed"
        
        # Only extension
        assert sanitize_filename(".mp4") == "unnamed.mp4"
        
        # No extension
        assert sanitize_filename("filename") == "filename"
        
        # Path separators
        assert "/" not in sanitize_filename("path/to/file.mp4")
        assert "\\" not in sanitize_filename("path\\to\\file.mp4")
        
        # Reserved Windows names
        assert sanitize_filename("CON.mp4") != "CON.mp4"
        assert sanitize_filename("PRN.txt") != "PRN.txt"
        assert sanitize_filename("AUX.doc") != "AUX.doc"


class TestFileIDGeneration:
    """Test file ID generation."""
    
    @pytest.mark.unit
    def test_generate_file_id(self):
        """Test basic file ID generation."""
        file_path = Path("/test/path/video.mp4")
        file_id = generate_file_id(file_path)
        
        # Should be a valid UUID format
        assert len(file_id) == 36
        assert file_id.count('-') == 4
        
        # Should be consistent for same path
        file_id2 = generate_file_id(file_path)
        assert file_id == file_id2
        
        # Different paths should have different IDs
        other_path = Path("/test/path/other.mp4")
        other_id = generate_file_id(other_path)
        assert other_id != file_id
    
    @pytest.mark.unit
    def test_generate_file_id_with_metadata(self):
        """Test file ID generation with metadata."""
        file_path = Path("/test/video.mp4")
        
        # With size metadata
        id_with_size = generate_file_id(file_path, file_size=12345)
        
        # Should still be valid UUID format
        assert len(id_with_size) == 36
        
        # Different metadata should create different IDs
        id_different_size = generate_file_id(file_path, file_size=54321)
        assert id_with_size != id_different_size
        
        # With modification time
        id_with_mtime = generate_file_id(file_path, mtime=1234567890)
        assert len(id_with_mtime) == 36
    
    @pytest.mark.unit
    def test_generate_file_id_unicode_paths(self):
        """Test file ID generation with Unicode paths."""
        unicode_path = Path("/test/видео/文件.mp4")
        file_id = generate_file_id(unicode_path)
        
        assert len(file_id) == 36
        
        # Should be consistent
        file_id2 = generate_file_id(unicode_path)
        assert file_id == file_id2


class TestDirectoryManagement:
    """Test directory management utilities."""
    
    @pytest.mark.unit
    def test_ensure_directory(self, temp_dir):
        """Test directory creation."""
        # Create new directory
        new_dir = temp_dir / "new" / "nested" / "dir"
        result = ensure_directory(new_dir)
        
        assert result == new_dir
        assert new_dir.exists()
        assert new_dir.is_dir()
        
        # Existing directory should work
        result2 = ensure_directory(new_dir)
        assert result2 == new_dir
        
        # String path should work
        str_path = str(temp_dir / "string_path")
        result3 = ensure_directory(str_path)
        assert Path(result3).exists()
    
    @pytest.mark.unit
    def test_ensure_directory_with_file(self, temp_dir):
        """Test ensure_directory with existing file."""
        # Create a file
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        
        # Should raise error if path is a file
        with pytest.raises(Exception):
            ensure_directory(test_file)


class TestProgressTracker:
    """Test progress tracking functionality."""
    
    @pytest.mark.unit
    def test_progress_tracker_basic(self, capsys):
        """Test basic progress tracking."""
        tracker = ProgressTracker(total=10, description="Testing")
        
        tracker.start()
        captured = capsys.readouterr()
        assert "Testing" in captured.out
        assert "0/10" in captured.out
        
        # Update progress
        tracker.update(5)
        captured = capsys.readouterr()
        assert "5/10" in captured.out
        assert "50%" in captured.out
        
        # Finish
        tracker.finish()
        captured = capsys.readouterr()
        assert "completed" in captured.out.lower()
    
    @pytest.mark.unit
    def test_progress_tracker_with_eta(self, capsys):
        """Test progress tracker with ETA calculation."""
        tracker = ProgressTracker(total=100, description="Processing", show_eta=True)
        
        tracker.start()
        time.sleep(0.1)  # Let some time pass
        
        tracker.update(10)
        captured = capsys.readouterr()
        
        # Should show some form of time estimate
        assert "10/100" in captured.out
        assert any(time_unit in captured.out for time_unit in ["s", "m", "h", "remaining", "ETA"])
    
    @pytest.mark.unit
    def test_progress_tracker_no_total(self, capsys):
        """Test progress tracker without total count."""
        tracker = ProgressTracker(description="Processing")
        
        tracker.start()
        tracker.update(1)
        captured = capsys.readouterr()
        
        # Should show count without percentage
        assert "1" in captured.out
        assert "%" not in captured.out
    
    @pytest.mark.unit
    def test_progress_tracker_context_manager(self, capsys):
        """Test progress tracker as context manager."""
        with ProgressTracker(total=5, description="Context") as tracker:
            for i in range(5):
                tracker.update(1)
        
        captured = capsys.readouterr()
        assert "completed" in captured.out.lower()


class TestSimpleWorkerPool:
    """Test worker pool functionality."""
    
    @pytest.mark.unit
    def test_worker_pool_basic(self):
        """Test basic worker pool operations."""
        def square(x):
            return x * x
        
        pool = SimpleWorkerPool(max_workers=2)
        
        # Map function over inputs
        inputs = [1, 2, 3, 4, 5]
        results = pool.map(square, inputs)
        
        assert results == [1, 4, 9, 16, 25]
        
        # Shutdown
        pool.shutdown()
    
    @pytest.mark.unit
    def test_worker_pool_with_errors(self):
        """Test worker pool error handling."""
        def faulty_function(x):
            if x == 3:
                raise ValueError("Error on 3")
            return x * 2
        
        pool = SimpleWorkerPool(max_workers=2)
        
        inputs = [1, 2, 3, 4, 5]
        
        # Should now raise WorkerPoolError instead of returning partial results
        with pytest.raises(WorkerPoolError, match="Map operation failed"):
            pool.map(faulty_function, inputs)
        
        pool.shutdown()
    
    @pytest.mark.unit
    def test_worker_pool_timeout(self):
        """Test worker pool with timeout."""
        def slow_function(x):
            time.sleep(x)
            return x
        
        pool = SimpleWorkerPool(max_workers=2, timeout=0.5)
        
        inputs = [0.1, 0.2, 2.0, 0.1]  # Third item will timeout
        
        # Should now raise WorkerPoolError instead of returning partial results
        with pytest.raises(WorkerPoolError, match="Failed to process"):
            pool.map(slow_function, inputs)
        
        pool.shutdown()
    
    @pytest.mark.unit
    def test_worker_pool_context_manager(self):
        """Test worker pool as context manager."""
        def double(x):
            return x * 2
        
        with SimpleWorkerPool(max_workers=3) as pool:
            results = pool.map(double, [1, 2, 3])
            assert results == [2, 4, 6]
        
        # Pool should be shut down after context
    
    @pytest.mark.unit
    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_worker_pool_submit_with_callback(self, mock_executor_class):
        """Test worker pool submit with callback."""
        mock_executor = Mock()
        mock_future = Mock()
        mock_future.result.return_value = 42
        mock_executor.submit.return_value = mock_future
        mock_executor_class.return_value = mock_executor
        
        callback_results = []
        
        def callback(future):
            callback_results.append(future.result())
        
        pool = SimpleWorkerPool(max_workers=2)
        pool.executor = mock_executor
        
        # Submit with callback
        future = pool.submit_with_callback(lambda x: x * 2, 21, callback=callback)
        
        # Simulate future completion
        mock_future.add_done_callback.assert_called_once()
        callback_func = mock_future.add_done_callback.call_args[0][0]
        callback_func(mock_future)
        
        assert callback_results == [42]


class TestUtilityHelpers:
    """Test miscellaneous utility functions."""
    
    @pytest.mark.unit
    def test_format_file_size(self):
        """Test file size formatting."""
        # Import if available
        try:
            from scribe.utils import format_file_size
            
            assert format_file_size(1024) == "1.0 KB"
            assert format_file_size(1024 * 1024) == "1.0 MB"
            assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
            assert format_file_size(512) == "512 B"
            assert format_file_size(1536) == "1.5 KB"
        except ImportError:
            pytest.skip("format_file_size not available")
    
    @pytest.mark.unit
    def test_format_duration(self):
        """Test duration formatting."""
        try:
            from scribe.utils import format_duration
            
            assert format_duration(60) == "1:00"
            assert format_duration(3600) == "1:00:00"
            assert format_duration(3661) == "1:01:01"
            assert format_duration(90) == "1:30"
            assert format_duration(45) == "0:45"
        except ImportError:
            pytest.skip("format_duration not available")
    
    @pytest.mark.unit
    def test_retry_with_backoff(self):
        """Test retry utility with exponential backoff."""
        try:
            from scribe.utils import retry_with_backoff
            
            call_count = 0
            
            @retry_with_backoff(max_attempts=3, initial_delay=0.01)
            def flaky_function():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ValueError("Temporary error")
                return "success"
            
            result = flaky_function()
            assert result == "success"
            assert call_count == 3
        except ImportError:
            pytest.skip("retry_with_backoff not available")


class TestChecksumCalculation:
    """Test checksum calculation functionality."""
    
    @pytest.mark.unit
    def test_calculate_checksum_basic(self, temp_dir):
        """Test basic checksum calculation with SHA256."""
        test_file = temp_dir / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)
        
        checksum = calculate_checksum(str(test_file))
        
        # Verify it's SHA256 hash (64 hex characters)
        assert len(checksum) == 64
        assert all(c in '0123456789abcdef' for c in checksum)
        
        # Verify it's consistent
        checksum2 = calculate_checksum(str(test_file))
        assert checksum == checksum2
    
    @pytest.mark.unit
    def test_calculate_checksum_different_algorithms(self, temp_dir):
        """Test checksum calculation with different algorithms."""
        test_file = temp_dir / "test.txt"
        test_content = b"Test content for hashing"
        test_file.write_bytes(test_content)
        
        # Test SHA256
        sha256_checksum = calculate_checksum(str(test_file), 'sha256')
        assert len(sha256_checksum) == 64
        
        # Test SHA1
        sha1_checksum = calculate_checksum(str(test_file), 'sha1')
        assert len(sha1_checksum) == 40
        
        # Test MD5
        md5_checksum = calculate_checksum(str(test_file), 'md5')
        assert len(md5_checksum) == 32
        
        # They should all be different
        assert sha256_checksum != sha1_checksum != md5_checksum
    
    @pytest.mark.unit
    def test_calculate_checksum_large_file(self, temp_dir):
        """Test checksum calculation with large file."""
        test_file = temp_dir / "large_test.txt"
        # Create a 1MB file
        test_content = b"A" * (1024 * 1024)
        test_file.write_bytes(test_content)
        
        checksum = calculate_checksum(str(test_file))
        
        # Should still work and be consistent
        assert len(checksum) == 64
        checksum2 = calculate_checksum(str(test_file))
        assert checksum == checksum2
    
    @pytest.mark.unit
    def test_calculate_checksum_empty_file(self, temp_dir):
        """Test checksum calculation with empty file."""
        test_file = temp_dir / "empty.txt"
        test_file.write_bytes(b"")
        
        checksum = calculate_checksum(str(test_file))
        
        # Should work with empty file
        assert len(checksum) == 64
        # SHA256 of empty string
        assert checksum == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class TestFileInfo:
    """Test file information retrieval."""
    
    @pytest.mark.unit
    def test_get_file_info_existing_file(self, temp_dir):
        """Test getting info for existing file."""
        test_file = temp_dir / "test.mp4"
        test_content = b"fake video content"
        test_file.write_bytes(test_content)
        
        info = get_file_info(str(test_file))
        
        assert info['exists'] is True
        assert info['size'] == len(test_content)
        assert info['is_file'] is True
        assert info['is_dir'] is False
        assert info['extension'] == '.mp4'
        assert info['stem'] == 'test'
        assert 'modified' in info
    
    @pytest.mark.unit
    def test_get_file_info_nonexistent_file(self, temp_dir):
        """Test getting info for non-existent file."""
        nonexistent_file = temp_dir / "does_not_exist.txt"
        
        info = get_file_info(str(nonexistent_file))
        
        assert info['exists'] is False
        assert len(info) == 1  # Only 'exists' key
    
    @pytest.mark.unit
    def test_get_file_info_directory(self, temp_dir):
        """Test getting info for directory."""
        test_dir = temp_dir / "subdir"
        test_dir.mkdir()
        
        info = get_file_info(str(test_dir))
        
        assert info['exists'] is True
        assert info['is_file'] is False
        assert info['is_dir'] is True
        assert info['extension'] == ''
        assert info['stem'] == 'subdir'
    
    @pytest.mark.unit
    def test_get_file_info_unicode_path(self, temp_dir):
        """Test getting info for file with Unicode path."""
        unicode_file = temp_dir / "тест_файл.txt"
        unicode_file.write_text("content")
        
        info = get_file_info(str(unicode_file))
        
        assert info['exists'] is True
        assert info['is_file'] is True
        assert info['stem'] == 'тест_файл'
        assert info['extension'] == '.txt'


class TestTranscriptFileFinder:
    """Test transcript file finding functionality."""
    
    @pytest.mark.unit
    def test_find_transcript_file_basic(self, temp_dir):
        """Test basic transcript file finding."""
        file_id = "test123"
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # Create preferred transcript file
        transcript_file = output_dir / f"{file_id}.txt"
        transcript_file.write_text("transcript content")
        
        found_file = find_transcript_file(output_dir, file_id)
        
        assert found_file == transcript_file
        assert found_file.exists()
    
    @pytest.mark.unit
    def test_find_transcript_file_priority_order(self, temp_dir):
        """Test transcript file finding respects priority order."""
        file_id = "test456"
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # Create multiple transcript files
        orig_srt = output_dir / f"{file_id}.orig.srt"
        orig_srt.write_text("original srt content")
        
        en_txt = output_dir / f"{file_id}.en.txt"
        en_txt.write_text("english text content")
        
        txt_file = output_dir / f"{file_id}.txt"
        txt_file.write_text("main transcript content")
        
        # Should prefer .txt over others
        found_file = find_transcript_file(output_dir, file_id)
        assert found_file == txt_file
    
    @pytest.mark.unit
    def test_find_transcript_file_fallback_order(self, temp_dir):
        """Test transcript file finding fallback order."""
        file_id = "test789"
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # Only create .en.txt (lowest priority)
        en_txt = output_dir / f"{file_id}.en.txt"
        en_txt.write_text("english text content")
        
        found_file = find_transcript_file(output_dir, file_id)
        assert found_file == en_txt
        
        # Add .orig.srt (higher priority)
        orig_srt = output_dir / f"{file_id}.orig.srt"
        orig_srt.write_text("original srt content")
        
        found_file = find_transcript_file(output_dir, file_id)
        assert found_file == orig_srt
    
    @pytest.mark.unit
    def test_find_transcript_file_not_found(self, temp_dir):
        """Test transcript file finding when no files exist."""
        file_id = "nonexistent"
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        found_file = find_transcript_file(output_dir, file_id)
        assert found_file is None


class TestListChunking:
    """Test list chunking functionality."""
    
    @pytest.mark.unit
    def test_chunk_list_basic(self):
        """Test basic list chunking."""
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        chunks = chunk_list(items, 3)
        
        expected = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]
        assert chunks == expected
    
    @pytest.mark.unit
    def test_chunk_list_exact_division(self):
        """Test chunking with exact division."""
        items = [1, 2, 3, 4, 5, 6]
        chunks = chunk_list(items, 2)
        
        expected = [[1, 2], [3, 4], [5, 6]]
        assert chunks == expected
    
    @pytest.mark.unit
    def test_chunk_list_empty(self):
        """Test chunking empty list."""
        items = []
        chunks = chunk_list(items, 3)
        
        assert chunks == []
    
    @pytest.mark.unit
    def test_chunk_list_single_item(self):
        """Test chunking single item list."""
        items = [42]
        chunks = chunk_list(items, 3)
        
        assert chunks == [[42]]
    
    @pytest.mark.unit
    def test_chunk_list_chunk_size_larger_than_list(self):
        """Test chunking with chunk size larger than list."""
        items = [1, 2, 3]
        chunks = chunk_list(items, 10)
        
        assert chunks == [[1, 2, 3]]
    
    @pytest.mark.unit
    def test_chunk_list_chunk_size_one(self):
        """Test chunking with chunk size of 1."""
        items = [1, 2, 3]
        chunks = chunk_list(items, 1)
        
        expected = [[1], [2], [3]]
        assert chunks == expected


class TestSafeExecute:
    """Test safe function execution."""
    
    @pytest.mark.unit
    def test_safe_execute_success(self):
        """Test safe execution with successful function."""
        def add(a, b):
            return a + b
        
        success, result = safe_execute(add, 2, 3)
        
        assert success is True
        assert result == 5
    
    @pytest.mark.unit
    def test_safe_execute_with_exception(self):
        """Test safe execution with function that raises exception."""
        def divide(a, b):
            return a / b
        
        success, result = safe_execute(divide, 10, 0)
        
        assert success is False
        assert isinstance(result, ZeroDivisionError)
    
    @pytest.mark.unit
    def test_safe_execute_with_kwargs(self):
        """Test safe execution with keyword arguments."""
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"
        
        success, result = safe_execute(greet, "World", greeting="Hi")
        
        assert success is True
        assert result == "Hi, World!"
    
    @pytest.mark.unit
    def test_safe_execute_no_args(self):
        """Test safe execution with no arguments."""
        def get_answer():
            return 42
        
        success, result = safe_execute(get_answer)
        
        assert success is True
        assert result == 42
    
    @pytest.mark.unit
    def test_safe_execute_different_exceptions(self):
        """Test safe execution with different exception types."""
        def value_error_func():
            raise ValueError("Test error")
        
        def type_error_func():
            raise TypeError("Type error")
        
        success1, result1 = safe_execute(value_error_func)
        success2, result2 = safe_execute(type_error_func)
        
        assert success1 is False
        assert isinstance(result1, ValueError)
        assert success2 is False
        assert isinstance(result2, TypeError)


class TestProgressTrackerStats:
    """Test ProgressTracker statistics functionality."""
    
    @pytest.mark.unit
    def test_progress_tracker_get_stats_basic(self):
        """Test basic progress tracker statistics."""
        tracker = ProgressTracker(total=100, description="Test")
        
        stats = tracker.get_stats()
        
        assert stats['total'] == 100
        assert stats['processed'] == 0
        assert stats['completed'] == 0
        assert stats['failed'] == 0
        assert stats['remaining'] == 100
    
    @pytest.mark.unit
    def test_progress_tracker_get_stats_with_updates(self):
        """Test progress tracker statistics with updates."""
        tracker = ProgressTracker(total=50, description="Test")
        
        # Update with successes and failures
        tracker.update(10, success=True)
        tracker.update(5, success=False)
        
        stats = tracker.get_stats()
        
        assert stats['total'] == 50
        assert stats['processed'] == 15
        assert stats['completed'] == 10
        assert stats['failed'] == 5
        assert stats['remaining'] == 35
    
    @pytest.mark.unit
    def test_progress_tracker_get_stats_no_total(self):
        """Test progress tracker statistics with no total."""
        tracker = ProgressTracker(description="Test")
        
        tracker.update(25, success=True)
        tracker.update(10, success=False)
        
        stats = tracker.get_stats()
        
        assert stats['total'] is None
        assert stats['processed'] == 35
        assert stats['completed'] == 25
        assert stats['failed'] == 10
        assert stats['remaining'] == 0  # No total means no remaining


class TestWorkerPoolProcessBatch:
    """Test SimpleWorkerPool process_batch method."""
    
    @pytest.mark.unit
    def test_process_batch_basic(self):
        """Test basic batch processing."""
        def double(x):
            return x * 2
        
        pool = SimpleWorkerPool(max_workers=2)
        items = [1, 2, 3, 4, 5]
        
        result = pool.process_batch(double, items)
        
        assert result['total'] == 5
        assert result['completed'] == 5
        assert result['failed'] == 0
        assert len(result['results']) == 5
        
        # Check that all items were processed
        for item in items:
            assert str(item) in result['results']
            assert result['results'][str(item)] == item * 2
        
        pool.shutdown()
    
    @pytest.mark.unit
    def test_process_batch_with_callback(self):
        """Test batch processing with callback."""
        def square(x):
            return x * x
        
        callback_results = []
        
        def callback(item, result, error):
            callback_results.append((item, result, error))
        
        pool = SimpleWorkerPool(max_workers=2)
        items = [1, 2, 3]
        
        result = pool.process_batch(square, items, callback=callback)
        
        assert result['total'] == 3
        assert result['completed'] == 3
        assert result['failed'] == 0
        assert len(callback_results) == 3
        
        # Check callback was called for each item
        for item, res, err in callback_results:
            assert item in items
            assert res == item * item
            assert err is None
        
        pool.shutdown()
    
    @pytest.mark.unit
    def test_process_batch_with_errors(self):
        """Test batch processing with some errors."""
        def problematic_func(x):
            if x == 3:
                raise ValueError("Error on 3")
            return x * 2
        
        pool = SimpleWorkerPool(max_workers=2)
        items = [1, 2, 3, 4, 5]
        
        result = pool.process_batch(problematic_func, items)
        
        assert result['total'] == 5
        assert result['completed'] == 4
        assert result['failed'] == 1
        assert result['results']['3'] is None  # Failed item
        assert result['results']['1'] == 2  # Successful items
        
        pool.shutdown()
    
    @pytest.mark.unit
    def test_process_batch_empty_items(self):
        """Test batch processing with empty items."""
        def identity(x):
            return x
        
        pool = SimpleWorkerPool(max_workers=2)
        items = []
        
        result = pool.process_batch(identity, items)
        
        assert result['total'] == 0
        assert result['completed'] == 0
        assert result['failed'] == 0
        assert result['results'] == {}
        
        pool.shutdown()
    
    @pytest.mark.unit
    def test_process_batch_with_timeout(self):
        """Test batch processing with timeout."""
        def slow_func(x):
            import time
            if x == 2:
                time.sleep(5)  # This will timeout
            return x
        
        pool = SimpleWorkerPool(max_workers=2)
        items = [1, 2, 3]
        
        result = pool.process_batch(slow_func, items, timeout=1.0)
        
        assert result['total'] == 3
        assert result['completed'] == 2  # 1 and 3 should succeed
        assert result['failed'] == 1  # 2 should timeout
        assert result['results']['2'] is None  # Timeout item
        
        pool.shutdown()


class TestIntegration:
    """Integration tests for utility functions."""
    
    @pytest.mark.integration
    def test_path_and_id_integration(self, temp_dir):
        """Test integration of path utilities and ID generation."""
        # Create a file with Unicode name
        unicode_name = "test_видео_文件.mp4"
        file_path = temp_dir / unicode_name
        file_path.write_bytes(b"test data")
        
        # Normalize path
        normalized = normalize_path(str(file_path))
        
        # Sanitize filename
        safe_name = sanitize_filename(normalized.name)
        
        # Generate ID
        file_id = generate_file_id(normalized)
        
        # Create output structure
        output_dir = temp_dir / "output" / file_id
        ensure_directory(output_dir)
        
        # Save with sanitized name
        output_file = output_dir / safe_name
        output_file.write_bytes(b"processed")
        
        assert output_file.exists()
        assert len(file_id) == 36
    
    @pytest.mark.integration
    def test_worker_pool_with_progress(self, capsys):
        """Test worker pool with progress tracking."""
        def process_item(item):
            time.sleep(0.01)  # Simulate work
            return item * 2
        
        items = list(range(10))
        
        with ProgressTracker(total=len(items), description="Processing") as tracker:
            with SimpleWorkerPool(max_workers=3) as pool:
                results = []
                
                # Submit all tasks
                futures = [pool.submit_with_callback(
                    process_item, 
                    item,
                    callback=lambda f: tracker.update(1)
                ) for item in items]
                
                # Collect results
                for future in futures:
                    try:
                        results.append(future.result())
                    except Exception:
                        results.append(None)
        
        assert len(results) == 10
        assert results[0] == 0
        assert results[5] == 10
        
        captured = capsys.readouterr()
        assert "completed" in captured.out.lower()