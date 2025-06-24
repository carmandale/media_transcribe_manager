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
    # Split the filename and extension
    base_name, extension = os.path.splitext(filename)
    
    # Convert to lowercase
    base_name = base_name.lower()
    extension = extension.lower()
    
    # Remove accents and normalize unicode
    base_name = unicodedata.normalize('NFKD', base_name).encode('ASCII', 'ignore').decode('ASCII')
    
    # Replace any non-alphanumeric characters with underscores
    base_name = re.sub(r'[^a-z0-9]', '_', base_name)
    
    # Replace multiple underscores with a single one
    base_name = re.sub(r'_+', '_', base_name)
    
    # Remove leading/trailing underscores
    base_name = base_name.strip('_')
    
    # Ensure the name is not empty
    if not base_name:
        base_name = "file"
    
    # Truncate if too long (max 200 chars for base name)
    if len(base_name) > 200:
        base_name = base_name[:200].rstrip('_')
    
    return f"{base_name}{extension}"


def generate_file_id() -> str:
    """
    Generate a unique file ID using UUID4.
    
    Returns:
        Unique file ID string
    """
    return str(uuid.uuid4())


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
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the worker pool.
        
        Args:
            max_workers: Maximum number of workers (default: CPU count - 1)
        """
        if max_workers is None:
            max_workers = max(1, multiprocessing.cpu_count() - 1)
        
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"Worker pool initialized with {max_workers} workers")
    
    def map(self, func: Callable, items: List[Any]) -> List[Any]:
        """
        Apply a function to each item in parallel.
        
        Args:
            func: Function to apply
            items: List of items to process
            
        Returns:
            List of results in the same order as inputs
        """
        return list(self.executor.map(func, items))
    
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
        timeout = timeout or 120  # Default 2 minute timeout per task
        
        # Submit all tasks
        for item in items:
            future = self.executor.submit(func, item)
            futures[future] = item
        
        # Process results as they complete with timeout
        for future in as_completed(futures, timeout=timeout * len(items)):
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
    
    def __init__(self, total: int, description: str = "Processing"):
        """
        Initialize progress tracker.
        
        Args:
            total: Total number of items
            description: Description for progress display
        """
        self.total = total
        self.description = description
        self.current = 0
        self.completed = 0
        self.failed = 0
    
    def update(self, success: bool = True):
        """Update progress with success/failure status."""
        self.current += 1
        if success:
            self.completed += 1
        else:
            self.failed += 1
        
        # Log progress every 10% or at completion
        percentage = (self.current / self.total) * 100
        if percentage % 10 == 0 or self.current == self.total:
            logger.info(
                f"{self.description}: {percentage:.0f}% "
                f"({self.current}/{self.total}) - "
                f"Success: {self.completed}, Failed: {self.failed}"
            )
    
    def get_stats(self) -> Dict[str, int]:
        """Get current statistics."""
        return {
            'total': self.total,
            'processed': self.current,
            'completed': self.completed,
            'failed': self.failed,
            'remaining': self.total - self.current
        }


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