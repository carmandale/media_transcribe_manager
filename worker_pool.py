#!/usr/bin/env python3
"""
Worker Pool for Media Transcription and Translation Tool
-------------------------------------------------------
Handles parallel processing using a thread pool executor for improved performance.
"""

import os
import logging
import threading
import time
from typing import Callable, List, Any, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import multiprocessing

# Configure logging
logger = logging.getLogger(__name__)


class WorkerPool:
    """
    Manages a pool of worker threads for parallel processing.
    
    This class provides methods for:
    - Executing tasks in parallel
    - Monitoring task progress
    - Safely shutting down the worker pool
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the worker pool.
        
        Args:
            max_workers: Maximum number of worker threads (default: auto-detect based on CPU cores)
        """
        # Determine workers count if not specified
        if max_workers is None:
            # Use CPU count - 1 to avoid saturating the system
            # But ensure at least one worker
            max_workers = max(1, multiprocessing.cpu_count() - 1)
        
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = {}  # Track submitted tasks
        self.active = True
        
        logger.info(f"Worker pool initialized with {max_workers} workers")
    
    def submit(self, task_id: str, func: Callable, *args, **kwargs) -> Future:
        """
        Submit a task to the worker pool.
        
        Args:
            task_id: Unique identifier for the task
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Future object for the submitted task
        """
        if not self.active:
            logger.warning("Worker pool is shutting down, cannot submit new tasks")
            raise RuntimeError("Worker pool is shutting down")
        
        future = self.executor.submit(func, *args, **kwargs)
        self.futures[task_id] = future
        
        logger.debug(f"Submitted task {task_id} to worker pool")
        return future
    
    def map(self, func: Callable, items: List[Any]) -> List[Any]:
        """
        Apply a function to each item in a list using the worker pool.
        
        Args:
            func: Function to apply to each item
            items: List of items to process
            
        Returns:
            List of results
        """
        if not self.active:
            logger.warning("Worker pool is shutting down, cannot submit new tasks")
            raise RuntimeError("Worker pool is shutting down")
        
        return list(self.executor.map(func, items))
    
    def process_batch(self, task_func: Callable, items: List[Any], 
                    callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Process a batch of items with status tracking.
        
        Args:
            task_func: Function to apply to each item
            items: List of items to process
            callback: Optional callback function to call for each completed task
            
        Returns:
            Dictionary with processing statistics
        """
        if not items:
            logger.warning("No items to process")
            return {
                'submitted': 0,
                'completed': 0,
                'failed': 0,
                'results': {}
            }
        
        futures_map = {}
        results = {}
        completed = 0
        failed = 0
        
        # Submit all tasks
        for item in items:
            item_id = str(getattr(item, 'id', id(item)))
            future = self.submit(item_id, task_func, item)
            futures_map[future] = item_id
        
        # Process results as they complete
        for future in as_completed(futures_map):
            item_id = futures_map[future]
            
            try:
                result = future.result()
                results[item_id] = result
                completed += 1
                
                if callback:
                    callback(item_id, result, None)
                    
            except Exception as e:
                logger.error(f"Task {item_id} failed: {e}")
                results[item_id] = None
                failed += 1
                
                if callback:
                    callback(item_id, None, e)
        
        logger.info(f"Batch processing completed: {completed} succeeded, {failed} failed")
        
        return {
            'submitted': len(items),
            'completed': completed,
            'failed': failed,
            'results': results
        }
    
    def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Tuple[bool, Any]:
        """
        Wait for a specific task to complete.
        
        Args:
            task_id: Unique identifier for the task
            timeout: Maximum time to wait in seconds
            
        Returns:
            Tuple of (is_completed, result_or_exception)
        """
        if task_id not in self.futures:
            logger.warning(f"Task {task_id} not found in worker pool")
            return False, None
        
        future = self.futures[task_id]
        
        try:
            result = future.result(timeout=timeout)
            return True, result
            
        except Exception as e:
            return False, e
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task if it hasn't started executing.
        
        Args:
            task_id: Unique identifier for the task
            
        Returns:
            True if the task was cancelled, False otherwise
        """
        if task_id not in self.futures:
            logger.warning(f"Task {task_id} not found in worker pool")
            return False
        
        future = self.futures[task_id]
        cancelled = future.cancel()
        
        if cancelled:
            logger.debug(f"Cancelled task {task_id}")
            self.futures.pop(task_id)
        else:
            logger.debug(f"Could not cancel task {task_id} (already running or completed)")
        
        return cancelled
    
    def shutdown(self, wait: bool = True, cancel_pending: bool = False) -> None:
        """
        Shutdown the worker pool.
        
        Args:
            wait: Wait for pending tasks to complete before shutting down
            cancel_pending: Cancel any pending tasks
        """
        if not self.active:
            logger.debug("Worker pool already shut down")
            return
        
        self.active = False
        
        if cancel_pending:
            # Cancel all pending tasks
            for task_id, future in list(self.futures.items()):
                if not future.done():
                    cancelled = future.cancel()
                    if cancelled:
                        logger.debug(f"Cancelled pending task {task_id} during shutdown")
        
        # Shutdown the executor
        logger.info(f"Shutting down worker pool ({'waiting for completion' if wait else 'not waiting'})")
        self.executor.shutdown(wait=wait)
        
        logger.debug("Worker pool shutdown complete")
    
    def __enter__(self):
        """Support for context manager usage."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure executor is properly shut down when used as a context manager."""
        self.shutdown()
