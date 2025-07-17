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
    ensure_directory, ProgressTracker, SimpleWorkerPool, WorkerPoolError
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
        with pytest.raises(WorkerPoolError, match="Failed to process 1 items"):
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