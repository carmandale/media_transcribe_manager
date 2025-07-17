#!/usr/bin/env python3
"""
Utility functions for the Scribe media processing system.
Provides common utilities for path handling, file ID generation, and parallel processing.
"""

import os
import re
import uuid
import hashlib
import logging
import unicodedata
import multiprocessing
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

logger = logging.getLogger(__name__)


class WorkerPoolError(Exception):
    """Exception raised when worker pool operations fail."""
    
    def __init__(self, message: str, errors: List[Tuple[Any, Exception]]):
        super().__init__(message)
        self.errors = errors


# Path Management Utilities
def normalize_path(path: str) -> Path:
    """
    Normalize a file path to handle Unicode and special characters.
    
    Args:
        path: Path string that may contain Unicode or special characters
        
    Returns:
        Normalized Path object
    """
    # Convert to Path object
    path_obj = Path(path)
    
    # Normalize Unicode (NFC form for consistency)
    normalized_str = unicodedata.normalize('NFC', str(path_obj))
    
    # Return as Path object
    return Path(normalized_str).resolve()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe processing and storage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for all file systems
    """
    if not filename or not filename.strip():
        return "unnamed"
    
    # Split the filename and extension
    filename = filename.strip()
    
    # Special case: handle filenames that are just an extension (e.g., ".mp4")
    if filename.startswith('.') and filename.count('.') == 1:
        base_name = ""
        extension = filename
    else:
        base_name, extension = os.path.splitext(filename)
    
    # Convert to lowercase
    base_name = base_name.lower()
    extension = extension.lower()
    
    # Normalize Unicode (preserve Unicode characters, don't strip to ASCII)
    base_name = unicodedata.normalize('NFC', base_name)
    
    # Replace only the most problematic characters for file systems
    # Keep Unicode letters and numbers, replace only filesystem-unsafe chars
    base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)  # Windows/filesystem illegal chars
    base_name = re.sub(r'\s+', '_', base_name)  # Replace spaces with underscores
    
    # Replace multiple underscores with a single one
    base_name = re.sub(r'_+', '_', base_name)
    
    # Remove leading/trailing underscores
    base_name = base_name.strip('_')
    
    # Handle Windows reserved names
    reserved_names = {
        'con', 'prn', 'aux', 'nul',
        'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
        'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
    }
    
    if base_name.lower() in reserved_names:
        base_name = f"_{base_name}"
    
    # Handle special case where extension starts with underscore
    if not base_name and extension.startswith('.'):
        base_name = "unnamed"
    elif not base_name:
        base_name = "unnamed"
    
    # Truncate if too long (max 200 chars for base name)
    if len(base_name) > 200:
        base_name = base_name[:200].rstrip('_')
    
    return f"{base_name}{extension}"


def generate_file_id(file_path: str = None, **metadata) -> str:
    """
    Generate a unique file ID based on file path and optional metadata.
    
    Args:
        file_path: Path to the file (optional)
        **metadata: Additional metadata to include in ID generation
        
    Returns:
        Unique file ID string
    """
    if file_path is None:
        # Legacy behavior - generate random UUID
        return str(uuid.uuid4())
    
    # Create consistent ID based on file path and metadata
    path_str = str(Path(file_path).resolve())
    
    # Include metadata in hash if provided
    hash_input = path_str
    if metadata:
        # Sort metadata for consistency
        sorted_metadata = sorted(metadata.items())
        metadata_str = str(sorted_metadata)
        hash_input = f"{path_str}|{metadata_str}"
    
    # Generate hash and format as UUID-like string
    hash_obj = hashlib.sha256(hash_input.encode('utf-8'))
    hash_hex = hash_obj.hexdigest()
    
    # Format as UUID (8-4-4-4-12)
    uuid_formatted = f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"
    
    return uuid_formatted


def calculate_checksum(file_path: str, algorithm: str = 'sha256') -> str:
    """
    Calculate file checksum for integrity verification.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (default: sha256)
        
    Returns:
        Hexadecimal checksum string
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b''):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


# Worker Pool for Parallel Processing
class SimpleWorkerPool:
    """
    Simple thread pool for parallel processing tasks.
    """
    
    def __init__(self, max_workers: Optional[int] = None, timeout: Optional[float] = None):
        """
        Initialize the worker pool.
        
        Args:
            max_workers: Maximum number of workers (default: CPU count - 1)
            timeout: Default timeout for operations (optional)
        """
        if max_workers is None:
            max_workers = max(1, multiprocessing.cpu_count() - 1)
        
        self.max_workers = max_workers
        self.default_timeout = timeout
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"Worker pool initialized with {max_workers} workers")
    
    def map(self, func: Callable, items: List[Any], timeout: Optional[float] = None) -> List[Any]:
        """
        Apply a function to each item in parallel.
        
        Args:
            func: Function to apply
            items: List of items to process
            timeout: Optional timeout for each task (uses default_timeout if None)
            
        Returns:
            List of results in the same order as inputs
            
        Raises:
            WorkerPoolError: If any tasks fail, to prevent silent data loss
        """
        # Use provided timeout or default timeout
        effective_timeout = timeout or self.default_timeout
        
        try:
            if effective_timeout:
                # Use submit for timeout support
                futures = [self.executor.submit(func, item) for item in items]
                results = []
                errors = []
                for i, future in enumerate(futures):
                    try:
                        result = future.result(timeout=effective_timeout)
                        results.append(result)
                    except TimeoutError as e:
                        logger.warning(f"Task timed out after {effective_timeout}s for item {items[i]}")
                        errors.append((items[i], e))
                        results.append(None)
                    except Exception as e:
                        logger.error(f"Task failed for item {items[i]}: {e}")
                        errors.append((items[i], e))
                        results.append(None)
                
                # CRITICAL FIX: Raise exception if any tasks failed to prevent silent data loss
                if errors:
                    raise WorkerPoolError(f"Failed to process {len(errors)} items", errors)
                
                return results
            else:
                return list(self.executor.map(func, items))
        except WorkerPoolError:
            # Re-raise WorkerPoolError as-is
            raise
        except Exception as e:
            logger.error(f"Map operation failed: {e}")
            raise WorkerPoolError(f"Map operation failed: {e}", [(item, e) for item in items])
    
    def process_batch(self, func: Callable, items: List[Any], 
                     callback: Optional[Callable] = None,
                     timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Process a batch of items with progress tracking and timeout handling.
        
        Args:
            func: Function to apply to each item
            items: List of items to process
            callback: Optional callback for each completed item
            timeout: Optional timeout per task in seconds (default: 120)
            
        Returns:
            Dictionary with processing statistics
        """
        if not items:
            return {
                'total': 0,
                'completed': 0,
                'failed': 0,
                'results': {}
            }
        
        futures = {}
        results = {}
        completed = 0
        failed = 0
        timeout = timeout or self.default_timeout or 120  # Use default or 2 minute timeout per task
        
        # Submit all tasks
        for item in items:
            future = self.executor.submit(func, item)
            futures[future] = item
        
        # Process results as they complete with overall timeout
        # Use reasonable overall timeout - don't multiply by number of items
        overall_timeout = min(timeout * 3, 300)  # Max 5 minutes total or 3x per-task timeout
        for future in as_completed(futures, timeout=overall_timeout):
            item = futures[future]
            
            try:
                # Individual task timeout
                result = future.result(timeout=timeout)
                results[str(item)] = result
                completed += 1
                
                if callback:
                    callback(item, result, None)
                    
            except TimeoutError:
                logger.warning(f"Task timed out for {item} after {timeout}s")
                results[str(item)] = None
                failed += 1
                
                if callback:
                    callback(item, None, TimeoutError(f"Timeout after {timeout}s"))
                    
            except Exception as e:
                logger.error(f"Task failed for {item}: {e}")
                results[str(item)] = None
                failed += 1
                
                if callback:
                    callback(item, None, e)
        
        return {
            'total': len(items),
            'completed': completed,
            'failed': failed,
            'results': results
        }
    
    def submit_with_callback(self, func: Callable, item: Any, callback: Optional[Callable] = None, timeout: Optional[float] = None):
        """
        Submit a single task with optional callback.
        
        Args:
            func: Function to apply
            item: Item to process
            callback: Optional callback function
            timeout: Optional timeout for the task
        
        Returns:
            Future object
        """
        future = self.executor.submit(func, item)
        
        if callback:
            def done_callback(fut):
                # CALLBACK FIX: Pass the future object directly to the callback
                # This matches the test expectation where callback(future) is called
                callback(fut)
            
            future.add_done_callback(done_callback)
        
        return future
    
    def _call_callback_safely(self, callback: Callable, item: Any, result: Any, error: Optional[Exception]):
        """
        Call callback function with automatic signature detection.
        
        Args:
            callback: Callback function to call
            item: Item being processed
            result: Result of processing (or None if error)
            error: Exception if processing failed (or None if successful)
        """
        import inspect
        
        try:
            # Get callback signature
            sig = inspect.signature(callback)
            param_count = len(sig.parameters)
            
            # Call with appropriate number of arguments
            if param_count == 1:
                callback(result)
            elif param_count == 2:
                callback(item, result)
            elif param_count == 3:
                callback(item, result, error)
            else:
                # Try 3-arg version as default
                callback(item, result, error)
                
        except Exception as e:
            logger.error(f"Error calling callback: {e}")
            # Try fallback with just the result
            try:
                callback(result)
            except Exception as fallback_error:
                logger.error(f"Callback fallback also failed: {fallback_error}")
    
    def shutdown(self, wait: bool = True):
        """
        Shutdown the worker pool.
        
        Args:
            wait: Whether to wait for pending tasks
        """
        self.executor.shutdown(wait=wait)
        logger.info("Worker pool shut down")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


# Progress Tracking
class ProgressTracker:
    """
    Simple progress tracker for batch operations.
    """
    
    def __init__(self, total: int = None, description: str = "Processing", show_eta: bool = True):
        """
        Initialize progress tracker.
        
        Args:
            total: Total number of items
            description: Description for progress display
            show_eta: Whether to show estimated time of arrival
        """
        self.total = total
        self.description = description
        self.show_eta = show_eta
        self.current = 0
        self.completed = 0
        self.failed = 0
        self.start_time = None
    
    def start(self):
        """Start the progress tracker."""
        import time
        self.start_time = time.time()
        # Print initial state
        if self.total:
            print(f"{self.description}: 0% (0/{self.total}) - Success: 0, Failed: 0")
        else:
            print(f"{self.description}: 0 processed - Success: 0, Failed: 0")
    
    def update(self, amount: int = 1, success: bool = True):
        """Update progress with amount and success/failure status."""
        self.current += amount
        if success:
            self.completed += amount
        else:
            self.failed += amount
        
        # Print progress for testing
        if self.total:
            percentage = (self.current / self.total) * 100
            print(f"{self.description}: {percentage:.0f}% ({self.current}/{self.total}) - Success: {self.completed}, Failed: {self.failed}")
            
            # Also log at certain intervals
            if percentage % 10 == 0 or self.current == self.total:
                logger.info(
                    f"{self.description}: {percentage:.0f}% "
                    f"({self.current}/{self.total}) - "
                    f"Success: {self.completed}, Failed: {self.failed}"
                )
        else:
            # For unknown total, log every 10 items
            print(f"{self.description}: {self.current} processed - Success: {self.completed}, Failed: {self.failed}")
            if self.current % 10 == 0:
                logger.info(
                    f"{self.description}: {self.current} processed - "
                    f"Success: {self.completed}, Failed: {self.failed}"
                )
    
    def get_stats(self) -> Dict[str, int]:
        """Get current statistics."""
        return {
            'total': self.total,
            'processed': self.current,
            'completed': self.completed,
            'failed': self.failed,
            'remaining': self.total - self.current if self.total else 0
        }
    
    def finish(self):
        """Finish the progress tracker."""
        if self.total:
            print(f"{self.description}: completed - Success: {self.completed}, Failed: {self.failed}")
        else:
            print(f"{self.description}: completed - Success: {self.completed}, Failed: {self.failed}")
        logger.info(f"{self.description} completed - Success: {self.completed}, Failed: {self.failed}")
    
    def __enter__(self):
        """Enter context manager."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        self.finish()


# File System Utilities
def ensure_directory(path: str) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Get basic file information.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file information
    """
    path = Path(file_path)
    
    if not path.exists():
        return {'exists': False}
    
    stat = path.stat()
    
    return {
        'exists': True,
        'size': stat.st_size,
        'modified': stat.st_mtime,
        'is_file': path.is_file(),
        'is_dir': path.is_dir(),
        'extension': path.suffix.lower(),
        'stem': path.stem
    }


def find_transcript_file(file_output_dir: Path, file_id: str) -> Optional[Path]:
    """
    Find the most likely original transcript file in an output directory.

    Args:
        file_output_dir: The directory where output files are stored.
        file_id: The unique ID of the file.

    Returns:
        The Path to the transcript file, or None if not found.
    """
    # Common transcript file extensions in order of preference
    preferred_filenames = [
        f"{file_id}.txt",
        f"{file_id}.orig.srt",
        f"{file_id}.en.txt"
    ]

    for filename in preferred_filenames:
        path = file_output_dir / filename
        if path.exists():
            logger.debug(f"Found transcript file: {path}")
            return path
    
    logger.warning(f"Could not find a primary transcript file for {file_id}. "
                   f"Checked for: {', '.join(preferred_filenames)}")
    return None


# Batch Processing Utilities
def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        items: List to split
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def safe_execute(func: Callable, *args, **kwargs) -> Tuple[bool, Any]:
    """
    Safely execute a function and return success status with result.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Tuple of (success, result_or_error)
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        logger.error(f"Error in {func.__name__}: {e}")
        return False, e