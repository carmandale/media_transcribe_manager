"""
Core utility function tests focused on coverage improvement.

These tests target essential utility functions in utils.py
to increase overall test coverage efficiently.
"""
import pytest
import uuid
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import TimeoutError as FutureTimeoutError

from scribe.utils import (
    normalize_path,
    sanitize_filename,
    generate_file_id,
    ensure_directory,
    calculate_checksum,
    ProgressTracker,
    SimpleWorkerPool,
    WorkerPoolError
)


class TestPathUtilities:
    """Test path and filename utilities."""
    
    @pytest.mark.unit
    def test_normalize_path_simple(self):
        """Test basic path normalization."""
        result = normalize_path("test/path/file.txt")
        assert isinstance(result, Path)
        assert result.name == "file.txt"
    
    @pytest.mark.unit
    def test_normalize_path_unicode(self):
        """Test path normalization with Unicode characters."""
        unicode_path = "test/café/résumé.txt"
        result = normalize_path(unicode_path)
        assert isinstance(result, Path)
        assert "café" in str(result)
        assert "résumé.txt" in str(result)
    
    @pytest.mark.unit
    def test_normalize_path_absolute(self):
        """Test normalization of absolute paths."""
        abs_path = "/absolute/path/to/file.txt"
        result = normalize_path(abs_path)
        assert isinstance(result, Path)
        assert result.is_absolute()
    
    @pytest.mark.unit
    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization."""
        result = sanitize_filename("normal_file.txt")
        assert result == "normal_file.txt"
    
    @pytest.mark.unit
    def test_sanitize_filename_special_chars(self):
        """Test sanitization of special characters."""
        result = sanitize_filename("file<>:\"/\\|?*.txt")
        # Should remove or replace dangerous characters
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "?" not in result
        assert "*" not in result
    
    @pytest.mark.unit
    def test_sanitize_filename_empty(self):
        """Test sanitization of empty filename."""
        result = sanitize_filename("")
        assert len(result) > 0  # Should provide fallback
    
    @pytest.mark.unit
    def test_sanitize_filename_long(self):
        """Test sanitization of very long filename."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) < 255  # Should truncate to filesystem limits


class TestFileUtilities:
    """Test file-related utility functions."""
    
    @pytest.mark.unit
    def test_generate_file_id_format(self):
        """Test that file ID generation produces valid UUID."""
        file_id = generate_file_id()
        
        # Should be a valid UUID string
        uuid_obj = uuid.UUID(file_id)
        assert str(uuid_obj) == file_id
        assert len(file_id) == 36  # Standard UUID length
    
    @pytest.mark.unit
    def test_generate_file_id_uniqueness(self):
        """Test that file IDs are unique."""
        ids = [generate_file_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All should be unique
    
    @pytest.mark.unit
    def test_ensure_directory_exists(self, temp_dir):
        """Test directory creation when directory doesn't exist."""
        new_dir = temp_dir / "new_directory"
        assert not new_dir.exists()
        
        ensure_directory(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    @pytest.mark.unit
    def test_ensure_directory_already_exists(self, temp_dir):
        """Test directory creation when directory already exists."""
        existing_dir = temp_dir / "existing"
        existing_dir.mkdir()
        assert existing_dir.exists()
        
        # Should not raise error
        ensure_directory(existing_dir)
        assert existing_dir.exists()
    
    @pytest.mark.unit
    def test_ensure_directory_nested(self, temp_dir):
        """Test creation of nested directories."""
        nested_dir = temp_dir / "level1" / "level2" / "level3"
        assert not nested_dir.exists()
        
        ensure_directory(nested_dir)
        assert nested_dir.exists()
        assert nested_dir.is_dir()
    
    @pytest.mark.unit
    def test_calculate_checksum(self, temp_dir):
        """Test file checksum calculation."""
        test_file = temp_dir / "test.txt"
        test_content = "This is test content for hashing"
        test_file.write_text(test_content)
        
        file_hash = calculate_checksum(str(test_file))
        
        # Verify it's a valid hash
        assert len(file_hash) == 64  # SHA256 hex length
        assert all(c in '0123456789abcdef' for c in file_hash)
        
        # Should be consistent
        second_hash = calculate_checksum(str(test_file))
        assert file_hash == second_hash
    
    @pytest.mark.unit
    def test_calculate_checksum_different_files(self, temp_dir):
        """Test that different files produce different hashes."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        
        file1.write_text("Content 1")
        file2.write_text("Content 2")
        
        hash1 = calculate_checksum(str(file1))
        hash2 = calculate_checksum(str(file2))
        
        assert hash1 != hash2
    
    @pytest.mark.unit
    def test_calculate_checksum_nonexistent_file(self, temp_dir):
        """Test checksum calculation for non-existent file."""
        missing_file = temp_dir / "missing.txt"
        
        # Should handle gracefully (return None or raise appropriate error)
        with pytest.raises((FileNotFoundError, OSError)):
            calculate_checksum(str(missing_file))


class TestProgressTracker:
    """Test progress tracking functionality."""
    
    @pytest.mark.unit
    def test_progress_tracker_init(self):
        """Test ProgressTracker initialization."""
        tracker = ProgressTracker(total=100, description="Test Task")
        
        assert tracker.total == 100
        assert tracker.current == 0
        assert tracker.description == "Test Task"
    
    @pytest.mark.unit
    def test_progress_tracker_update(self):
        """Test progress tracking updates."""
        tracker = ProgressTracker(total=100, description="Test")
        
        tracker.update(25)
        assert tracker.current == 25
        
        tracker.update(50)
        assert tracker.current == 75
        
        # Should not exceed total
        tracker.update(50)
        assert tracker.current == 100
    
    @pytest.mark.unit
    def test_progress_tracker_percentage(self):
        """Test percentage calculation."""
        tracker = ProgressTracker(total=100, description="Test")
        
        assert tracker.percentage() == 0.0
        
        tracker.update(25)
        assert tracker.percentage() == 25.0
        
        tracker.update(75)
        assert tracker.percentage() == 100.0
    
    @pytest.mark.unit
    def test_progress_tracker_zero_total(self):
        """Test progress tracker with zero total."""
        tracker = ProgressTracker(total=0, description="Empty Task")
        
        # Should handle gracefully
        assert tracker.percentage() == 100.0  # Or 0.0, depending on implementation
    
    @pytest.mark.unit
    def test_progress_tracker_string_representation(self):
        """Test string representation of progress."""
        tracker = ProgressTracker(total=100, description="Test Task")
        tracker.update(30)
        
        progress_str = str(tracker)
        assert "Test Task" in progress_str
        assert "30" in progress_str or "30%" in progress_str


class TestSimpleWorkerPool:
    """Test worker pool functionality."""
    
    @pytest.mark.unit
    def test_worker_pool_init(self):
        """Test SimpleWorkerPool initialization."""
        pool = SimpleWorkerPool(max_workers=4)
        assert pool.max_workers == 4
    
    @pytest.mark.unit
    def test_worker_pool_map_success(self):
        """Test successful parallel processing."""
        def square(x):
            return x * x
        
        pool = SimpleWorkerPool(max_workers=2)
        numbers = [1, 2, 3, 4, 5]
        
        results = pool.map(square, numbers)
        
        assert results == [1, 4, 9, 16, 25]
    
    @pytest.mark.unit
    def test_worker_pool_map_with_errors(self):
        """Test handling of errors in worker pool."""
        def failing_function(x):
            if x == 3:
                raise ValueError(f"Error with {x}")
            return x * 2
        
        pool = SimpleWorkerPool(max_workers=2)
        numbers = [1, 2, 3, 4, 5]
        
        # Should raise WorkerPoolError
        with pytest.raises(WorkerPoolError) as exc_info:
            pool.map(failing_function, numbers)
        
        assert len(exc_info.value.errors) > 0
        assert any("Error with 3" in str(err[1]) for err in exc_info.value.errors)
    
    @pytest.mark.unit
    def test_worker_pool_empty_input(self):
        """Test worker pool with empty input."""
        def dummy_function(x):
            return x
        
        pool = SimpleWorkerPool(max_workers=2)
        results = pool.map(dummy_function, [])
        
        assert results == []
    
    @pytest.mark.unit
    def test_worker_pool_single_item(self):
        """Test worker pool with single item."""
        def double(x):
            return x * 2
        
        pool = SimpleWorkerPool(max_workers=2)
        results = pool.map(double, [5])
        
        assert results == [10]
    
    @pytest.mark.unit
    def test_worker_pool_timeout_handling(self):
        """Test worker pool timeout behavior."""
        import time
        
        def slow_function(x):
            time.sleep(0.1)
            return x
        
        pool = SimpleWorkerPool(max_workers=2, timeout=0.05)
        
        # Should handle timeout gracefully
        with pytest.raises((WorkerPoolError, FutureTimeoutError)):
            pool.map(slow_function, [1, 2, 3])


class TestWorkerPoolError:
    """Test WorkerPoolError exception class."""
    
    @pytest.mark.unit
    def test_worker_pool_error_creation(self):
        """Test WorkerPoolError creation and attributes."""
        errors = [(1, ValueError("Test error 1")), (2, RuntimeError("Test error 2"))]
        
        exception = WorkerPoolError("Multiple errors occurred", errors)
        
        assert str(exception) == "Multiple errors occurred"
        assert exception.errors == errors
        assert len(exception.errors) == 2
    
    @pytest.mark.unit
    def test_worker_pool_error_empty_errors(self):
        """Test WorkerPoolError with empty errors list."""
        exception = WorkerPoolError("No specific errors", [])
        
        assert str(exception) == "No specific errors"
        assert exception.errors == []


class TestUtilityIntegration:
    """Test integration between utility functions."""
    
    @pytest.mark.unit
    def test_file_processing_workflow(self, temp_dir):
        """Test typical file processing workflow using multiple utilities."""
        # Create test file
        test_file = temp_dir / "test file with spaces.txt"
        test_content = "Test content for integration"
        test_file.write_text(test_content)
        
        # Generate file ID
        file_id = generate_file_id()
        assert len(file_id) == 36
        
        # Normalize path
        normalized = normalize_path(str(test_file))
        assert normalized.exists()
        
        # Calculate hash
        file_hash = calculate_checksum(str(normalized))
        assert len(file_hash) == 64
        
        # Create output directory
        output_dir = temp_dir / "output" / file_id
        ensure_directory(output_dir)
        assert output_dir.exists()
        
        # Sanitize filename for output
        safe_name = sanitize_filename(test_file.name)
        assert " " not in safe_name or safe_name == test_file.name  # Depends on implementation
    
    @pytest.mark.unit
    def test_parallel_file_processing(self, temp_dir):
        """Test parallel processing of multiple files."""
        # Create multiple test files
        files = []
        for i in range(5):
            test_file = temp_dir / f"test_{i}.txt"
            test_file.write_text(f"Content {i}")
            files.append(test_file)
        
        def process_file(file_path):
            # Simulate file processing
            return {
                'path': str(file_path),
                'hash': calculate_checksum(str(file_path)),
                'id': generate_file_id()
            }
        
        pool = SimpleWorkerPool(max_workers=3)
        results = pool.map(process_file, files)
        
        assert len(results) == 5
        assert all('hash' in result for result in results)
        assert all('id' in result for result in results)
        assert len(set(result['id'] for result in results)) == 5  # All unique IDs