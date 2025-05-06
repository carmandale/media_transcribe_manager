#!/usr/bin/env python3
"""
Pipeline Manager Module
----------------------
Manages and orchestrates the entire media processing pipeline, including:
- Pipeline monitoring and status tracking
- Special handling for problematic files
- Parallel processing of transcription and translation tasks
- Command-line interface for all pipeline operations

This module consolidates functionality from:
- run_parallel_processing.py
- monitor_and_restart.py
- transcribe_problematic_files.py
- translate_all_remaining.py
- process_remaining_files.py
- monitor_progress.sh
"""

import os
import sys
import time
import logging
import argparse
import subprocess
import signal
import threading
import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable
import json
import tempfile
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pipeline_manager.log')
    ]
)

logger = logging.getLogger(__name__)

# Import local modules
from db_manager import DatabaseManager
from file_manager import FileManager
from worker_pool import WorkerPool

# Optional imports
try:
    from transcription import TranscriptionManager
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    logger.warning("TranscriptionManager not available. Transcription features disabled.")
    TRANSCRIPTION_AVAILABLE = False
    
try:
    from translation import TranslationManager
    TRANSLATION_AVAILABLE = True
except ImportError:
    logger.warning("TranslationManager not available. Translation features disabled.")
    TRANSLATION_AVAILABLE = False


class PipelineMonitor:
    """
    Monitors and tracks pipeline progress across all processing stages.
    """
    
    def __init__(self, db_manager: DatabaseManager, config: Dict[str, Any] = None):
        """
        Initialize the pipeline monitor.
        
        Args:
            db_manager: Database manager instance
            config: Configuration dictionary (optional)
        """
        self.db_manager = db_manager
        self.config = config or {}
        
        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # Status tracking
        self.last_check_time = 0
        self.last_status = {}
        
    def check_status(self, detailed: bool = False) -> Dict[str, Any]:
        """
        Check current pipeline status.
        
        Args:
            detailed: Whether to include detailed information
            
        Returns:
            Dictionary with status information
        """
        status = {
            'timestamp': int(time.time()),
            'summary': {},
            'stages': {}
        }
        
        # Get total file count
        total_files_query = "SELECT COUNT(*) as count FROM processing_status"
        total_result = self.db_manager.execute_query(total_files_query)
        total_files = total_result[0]['count'] if total_result else 0
        
        status['summary']['total_files'] = total_files
        
        # Check transcription status
        for trans_status in ['not_started', 'in-progress', 'completed', 'failed', 'qa_failed']:
            query = f"""
            SELECT COUNT(*) as count FROM processing_status 
            WHERE transcription_status = '{trans_status}'
            """
            result = self.db_manager.execute_query(query)
            count = result[0]['count'] if result else 0
            
            if 'transcription' not in status['stages']:
                status['stages']['transcription'] = {}
            status['stages']['transcription'][trans_status] = count
        
        # Check translation status for each language
        for language in ['en', 'de', 'he']:
            status_field = f"translation_{language}_status"
            
            for trans_status in ['not_started', 'in-progress', 'completed', 'failed', 'qa_failed']:
                query = f"""
                SELECT COUNT(*) as count FROM processing_status 
                WHERE {status_field} = '{trans_status}'
                """
                result = self.db_manager.execute_query(query)
                count = result[0]['count'] if result else 0
                
                if 'translation' not in status['stages']:
                    status['stages']['translation'] = {}
                if language not in status['stages']['translation']:
                    status['stages']['translation'][language] = {}
                status['stages']['translation'][language][trans_status] = count
        
        # Calculate summary statistics
        if 'transcription' in status['stages']:
            completed = status['stages']['transcription'].get('completed', 0)
            status['summary']['transcription_percent'] = round((completed / total_files) * 100, 1) if total_files else 0
        
        if 'translation' in status['stages']:
            for language in status['stages']['translation']:
                completed = status['stages']['translation'][language].get('completed', 0)
                status['summary'][f'translation_{language}_percent'] = round((completed / total_files) * 100, 1) if total_files else 0
        
        # Add detailed information if requested
        if detailed:
            # Check for stalled processes
            stalled_query = """
            SELECT * FROM processing_status 
            WHERE status = 'in-progress' OR transcription_status = 'in-progress'
            OR translation_en_status = 'in-progress' OR translation_de_status = 'in-progress'
            OR translation_he_status = 'in-progress'
            """
            stalled_results = self.db_manager.execute_query(stalled_query)
            
            status['details'] = {
                'in_progress_files': len(stalled_results) if stalled_results else 0,
                'in_progress_list': [r['file_id'] for r in stalled_results] if stalled_results else []
            }
            
            # Check recent errors
            error_query = """
            SELECT * FROM error_log 
            ORDER BY timestamp DESC LIMIT 10
            """
            error_results = self.db_manager.execute_query(error_query)
            
            status['details']['recent_errors'] = error_results if error_results else []
            
            # Add processing rate information
            if self.last_check_time > 0 and self.last_status:
                time_diff = status['timestamp'] - self.last_check_time
                if time_diff > 0:
                    rates = {}
                    
                    # Calculate transcription rate
                    if 'transcription' in status['stages'] and 'transcription' in self.last_status.get('stages', {}):
                        current = status['stages']['transcription'].get('completed', 0)
                        previous = self.last_status['stages']['transcription'].get('completed', 0)
                        rate = (current - previous) / (time_diff / 3600)  # per hour
                        rates['transcription'] = round(rate, 2)
                    
                    # Calculate translation rates
                    if 'translation' in status['stages'] and 'translation' in self.last_status.get('stages', {}):
                        for language in status['stages']['translation']:
                            if language in self.last_status['stages']['translation']:
                                current = status['stages']['translation'][language].get('completed', 0)
                                previous = self.last_status['stages']['translation'][language].get('completed', 0)
                                rate = (current - previous) / (time_diff / 3600)  # per hour
                                rates[f'translation_{language}'] = round(rate, 2)
                    
                    status['details']['processing_rates'] = rates
                    
        # Store for rate calculations
        self.last_check_time = status['timestamp']
        self.last_status = status
        
        return status
    
    def generate_report(self, output_format: str = 'text') -> str:
        """
        Generate a report of pipeline status.
        
        Args:
            output_format: Format for report ('text', 'json', or 'markdown')
            
        Returns:
            Formatted report string
        """
        # Get current status
        status = self.check_status(detailed=True)
        
        # JSON format is simplest
        if output_format == 'json':
            return json.dumps(status, indent=2)
        
        # Generate text or markdown report
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if output_format == 'markdown':
            lines = [
                f"# Processing Status Report",
                f"Generated: {now}\n",
                "## Summary",
                f"- Total files: {status['summary']['total_files']}",
                f"- Transcription: {status['summary'].get('transcription_percent', 0)}% complete",
            ]
            
            # Add translation summaries
            for lang_code in ['en', 'de', 'he']:
                lang_name = {'en': 'English', 'de': 'German', 'he': 'Hebrew'}.get(lang_code, lang_code)
                lang_percent = status['summary'].get(f'translation_{lang_code}_percent', 0)
                lines.append(f"- {lang_name} translation: {lang_percent}% complete")
            
            # Add stage details
            lines.append("\n## Transcription Status")
            lines.append("| Status | Count |")
            lines.append("|--------|-------|")
            for status_name, count in status['stages'].get('transcription', {}).items():
                lines.append(f"| {status_name} | {count} |")
            
            # Add translation details
            lines.append("\n## Translation Status")
            
            for lang_code in ['en', 'de', 'he']:
                lang_name = {'en': 'English', 'de': 'German', 'he': 'Hebrew'}.get(lang_code, lang_code)
                lines.append(f"\n### {lang_name}")
                lines.append("| Status | Count |")
                lines.append("|--------|-------|")
                for status_name, count in status['stages'].get('translation', {}).get(lang_code, {}).items():
                    lines.append(f"| {status_name} | {count} |")
            
            # Add processing rates if available
            if 'details' in status and 'processing_rates' in status['details']:
                lines.append("\n## Processing Rates (files per hour)")
                for rate_name, rate_value in status['details']['processing_rates'].items():
                    pretty_name = rate_name.replace('_', ' ').title()
                    lines.append(f"- {pretty_name}: {rate_value}")
            
        else:  # Text format
            lines = [
                f"Processing Status Report",
                f"Generated: {now}\n",
                "Summary:",
                f"- Total files: {status['summary']['total_files']}",
                f"- Transcription: {status['summary'].get('transcription_percent', 0)}% complete",
            ]
            
            # Add translation summaries
            for lang_code in ['en', 'de', 'he']:
                lang_name = {'en': 'English', 'de': 'German', 'he': 'Hebrew'}.get(lang_code, lang_code)
                lang_percent = status['summary'].get(f'translation_{lang_code}_percent', 0)
                lines.append(f"- {lang_name} translation: {lang_percent}% complete")
            
            # Add stage details
            lines.append("\nTranscription Status:")
            for status_name, count in status['stages'].get('transcription', {}).items():
                lines.append(f"- {status_name}: {count}")
            
            # Add translation details
            lines.append("\nTranslation Status:")
            
            for lang_code in ['en', 'de', 'he']:
                lang_name = {'en': 'English', 'de': 'German', 'he': 'Hebrew'}.get(lang_code, lang_code)
                lines.append(f"\n{lang_name}:")
                for status_name, count in status['stages'].get('translation', {}).get(lang_code, {}).items():
                    lines.append(f"- {status_name}: {count}")
            
            # Add processing rates if available
            if 'details' in status and 'processing_rates' in status['details']:
                lines.append("\nProcessing Rates (files per hour):")
                for rate_name, rate_value in status['details']['processing_rates'].items():
                    pretty_name = rate_name.replace('_', ' ').title()
                    lines.append(f"- {pretty_name}: {rate_value}")
        
        return '\n'.join(lines)
    
    def _check_and_restart_stalled(self, timeout_minutes: int = 30) -> Dict[str, int]:
        """
        Check for stalled processes and restart them.
        
        Args:
            timeout_minutes: Minutes after which to consider a process stalled
            
        Returns:
            Dictionary with counts of restarted processes
        """
        logger.info(f"Checking for stalled processes (timeout: {timeout_minutes} minutes)...")
        
        # Calculate cutoff time
        cutoff_time = int(time.time()) - (timeout_minutes * 60)
        
        # Find stalled processes
        query = """
        SELECT * FROM processing_status 
        WHERE (status = 'in-progress' OR transcription_status = 'in-progress'
            OR translation_en_status = 'in-progress' OR translation_de_status = 'in-progress'
            OR translation_he_status = 'in-progress')
        AND last_updated < ?
        """
        
        stalled_files = self.db_manager.execute_query(query, (cutoff_time,))
        
        if not stalled_files:
            logger.info("No stalled processes found.")
            return {'total': 0}
        
        logger.info(f"Found {len(stalled_files)} stalled files")
        
        # Categorize by status
        reset_counts = {
            'transcription': 0,
            'translation_en': 0,
            'translation_de': 0,
            'translation_he': 0,
            'total': 0
        }
        
        # Reset status for stalled files
        for file in stalled_files:
            file_id = file['file_id']
            updates = {}
            
            # Check each status field
            if file['transcription_status'] == 'in-progress':
                updates['transcription_status'] = 'failed'
                reset_counts['transcription'] += 1
            
            for lang in ['en', 'de', 'he']:
                status_field = f"translation_{lang}_status"
                if file[status_field] == 'in-progress':
                    updates[status_field] = 'failed'
                    reset_counts[f'translation_{lang}'] += 1
            
            # Set overall status to failed if nothing completed successfully
            if (file['transcription_status'] not in ['completed', 'qa_failed'] and
                file['translation_en_status'] not in ['completed', 'qa_failed'] and
                file['translation_de_status'] not in ['completed', 'qa_failed'] and
                file['translation_he_status'] not in ['completed', 'qa_failed']):
                updates['status'] = 'failed'
            
            # Update database if changes needed
            if updates:
                update_query = "UPDATE processing_status SET "
                update_parts = []
                values = []
                
                for field, value in updates.items():
                    update_parts.append(f"{field} = ?")
                    values.append(value)
                
                # Add last_updated
                update_parts.append("last_updated = ?")
                values.append(int(time.time()))
                
                # Complete query
                update_query += ", ".join(update_parts)
                update_query += " WHERE file_id = ?"
                values.append(file_id)
                
                # Execute update
                self.db_manager.execute_update(update_query, tuple(values))
                reset_counts['total'] += 1
                logger.info(f"Reset status for file {file_id}")
        
        logger.info(f"Reset {reset_counts['total']} stalled files")
        return reset_counts
    
    def restart_stalled_processes(self, timeout_minutes: int = 30, auto_restart: bool = True) -> Dict[str, int]:
        """
        Identify and restart stalled processes.
        
        Args:
            timeout_minutes: Minutes after which to consider a process stalled
            auto_restart: Whether to automatically restart pipeline processes
            
        Returns:
            Dictionary with counts of restarted processes
        """
        # Reset stalled files in the database
        reset_counts = self._check_and_restart_stalled(timeout_minutes)
        
        # Restart pipeline if needed
        if auto_restart and reset_counts['total'] > 0:
            logger.info("Restarting pipeline processes...")
            
            # Check which processes need restarting
            processes_to_start = []
            
            if reset_counts.get('transcription', 0) > 0:
                processes_to_start.append('transcription')
            
            for lang in ['en', 'de', 'he']:
                if reset_counts.get(f'translation_{lang}', 0) > 0:
                    processes_to_start.append(f'translation_{lang}')
            
            # Launch appropriate processes
            batch_size = self.config.get('batch_size', 20)
            
            if 'transcription' in processes_to_start:
                # Start transcription process
                transcription_workers = self.config.get('transcription_workers', 5)
                self._start_parallel_transcription(workers=transcription_workers, batch_size=batch_size)
            
            # Start translation processes
            translation_workers = self.config.get('translation_workers', 5)
            for process in processes_to_start:
                if process.startswith('translation_'):
                    language = process.split('_')[1]
                    self._start_parallel_translation(language=language, workers=translation_workers, batch_size=batch_size)
        
        return reset_counts
    
    def _start_parallel_transcription(self, workers: int = 5, batch_size: Optional[int] = None) -> bool:
        """
        Start parallel transcription process.
        
        Args:
            workers: Number of worker threads
            batch_size: Number of files to process
            
        Returns:
            True if process started successfully
        """
        if not TRANSCRIPTION_AVAILABLE:
            logger.error("Cannot start transcription: TranscriptionManager not available")
            return False
        
        logger.info(f"Starting parallel transcription with {workers} workers")
        
        # Build command
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "parallel_transcription.py"),
            "--workers", str(workers)
        ]
        
        if batch_size:
            cmd.extend(["--batch-size", str(batch_size)])
        
        # Start process detached
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            logger.info(f"Started transcription process: {' '.join(cmd)}")
            return True
        except Exception as e:
            logger.error(f"Failed to start transcription process: {e}")
            return False
    
    def _start_parallel_translation(self, language: str, workers: int = 5, batch_size: Optional[int] = None) -> bool:
        """
        Start parallel translation process.
        
        Args:
            language: Language code to translate to
            workers: Number of worker threads
            batch_size: Number of files to process
            
        Returns:
            True if process started successfully
        """
        if not TRANSLATION_AVAILABLE:
            logger.error("Cannot start translation: TranslationManager not available")
            return False
        
        logger.info(f"Starting parallel translation for {language} with {workers} workers")
        
        # Build command
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "parallel_translation.py"),
            "--language", language,
            "--workers", str(workers)
        ]
        
        if batch_size:
            cmd.extend(["--batch-size", str(batch_size)])
        
        # Start process detached
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            logger.info(f"Started translation process: {' '.join(cmd)}")
            return True
        except Exception as e:
            logger.error(f"Failed to start translation process: {e}")
            return False
    
    def _monitor_thread_func(self, check_interval: int = 60, 
                           restart_interval: int = 600, 
                           auto_restart: bool = True) -> None:
        """
        Background thread function for continuous monitoring.
        
        Args:
            check_interval: Seconds between status checks
            restart_interval: Seconds between restart checks
            auto_restart: Whether to automatically restart processes
        """
        last_restart_check = 0
        restart_interval_seconds = restart_interval
        
        while not self.stop_event.is_set():
            try:
                # Check status
                status = self.check_status()
                
                # Log current status
                logger.info(f"Status: "
                           f"Transcription: {status['summary'].get('transcription_percent', 0)}% | "
                           f"EN: {status['summary'].get('translation_en_percent', 0)}% | "
                           f"DE: {status['summary'].get('translation_de_percent', 0)}% | "
                           f"HE: {status['summary'].get('translation_he_percent', 0)}%")
                
                # Check for stalled processes at specified intervals
                current_time = int(time.time())
                if auto_restart and (current_time - last_restart_check) >= restart_interval_seconds:
                    self.restart_stalled_processes(timeout_minutes=30, auto_restart=True)
                    last_restart_check = current_time
                
                # Wait for next check
                for _ in range(check_interval):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in monitor thread: {e}")
                time.sleep(check_interval)
    
    def start_monitoring(self, check_interval: int = 60, 
                        restart_interval: int = 600, 
                        auto_restart: bool = True) -> None:
        """
        Start background monitoring thread.
        
        Args:
            check_interval: Seconds between status checks
            restart_interval: Seconds between restart checks
            auto_restart: Whether to automatically restart processes
        """
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        logger.info(f"Starting monitoring (check: {check_interval}s, "
                   f"restart: {restart_interval}s, auto-restart: {auto_restart})")
        
        # Reset stop event
        self.stop_event.clear()
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_thread_func,
            args=(check_interval, restart_interval, auto_restart),
            daemon=True
        )
        self.monitor_thread.start()
        self.monitoring_active = True
    
    def stop_monitoring(self) -> None:
        """Stop background monitoring thread."""
        if not self.monitoring_active:
            logger.warning("Monitoring not active")
            return
        
        logger.info("Stopping monitoring")
        
        # Signal thread to stop
        self.stop_event.set()
        
        # Wait for thread to end
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        self.monitoring_active = False
        self.monitor_thread = None


class ProblemFileHandler:
    """
    Special handling for problematic files that fail regular processing.
    """
    
    def __init__(self, db_manager: DatabaseManager, file_manager: FileManager, config: Dict[str, Any] = None):
        """
        Initialize the problem file handler.
        
        Args:
            db_manager: Database manager instance
            file_manager: File manager instance
            config: Configuration dictionary (optional)
        """
        self.db_manager = db_manager
        self.file_manager = file_manager
        self.config = config or {}
    
    def identify_problem_files(self) -> Dict[str, List[str]]:
        """
        Identify problematic files based on error patterns.
        
        Returns:
            Dictionary mapping error types to lists of file IDs
        """
        problem_files = {
            'failed_multiple_times': [],
            'stalled': [],
            'empty_output': [],
            'invalid_audio': [],
            'timeout': []
        }
        
        # Find files that failed multiple times (3+)
        failure_query = """
        SELECT file_id, COUNT(*) as failure_count
        FROM error_log
        GROUP BY file_id
        HAVING COUNT(*) >= 3
        """
        
        failure_results = self.db_manager.execute_query(failure_query)
        if failure_results:
            problem_files['failed_multiple_times'] = [r['file_id'] for r in failure_results]
        
        # Find files stalled for a long time (24+ hours)
        long_stall_cutoff = int(time.time()) - (24 * 60 * 60)
        stall_query = """
        SELECT file_id FROM processing_status
        WHERE (status = 'in-progress' OR transcription_status = 'in-progress'
            OR translation_en_status = 'in-progress' OR translation_de_status = 'in-progress'
            OR translation_he_status = 'in-progress')
        AND last_updated < ?
        """
        
        stall_results = self.db_manager.execute_query(stall_query, (long_stall_cutoff,))
        if stall_results:
            problem_files['stalled'] = [r['file_id'] for r in stall_results]
        
        # Find files with empty output
        empty_query = """
        SELECT file_id FROM processing_status
        WHERE transcription_status = 'completed'
        """
        
        empty_results = self.db_manager.execute_query(empty_query)
        if empty_results:
            for result in empty_results:
                file_id = result['file_id']
                transcript_path = Path(self.file_manager.get_transcript_path(file_id))
                
                if transcript_path.exists() and transcript_path.stat().st_size < 10:
                    problem_files['empty_output'].append(file_id)
        
        # Check error log for specific error types
        for error_type, keywords in {
            'invalid_audio': ['invalid audio', 'corrupt', 'unsupported format'],
            'timeout': ['timeout', 'timed out', 'connection reset']
        }.items():
            pattern_conditions = []
            for keyword in keywords:
                pattern_conditions.append(f"error_message LIKE '%{keyword}%' OR error_details LIKE '%{keyword}%'")
            
            pattern_query = f"""
            SELECT DISTINCT file_id FROM error_log
            WHERE {' OR '.join(pattern_conditions)}
            """
            
            pattern_results = self.db_manager.execute_query(pattern_query)
            if pattern_results:
                problem_files[error_type] = [r['file_id'] for r in pattern_results]
        
        return problem_files
    
    def retry_problematic_files(self, file_ids: Optional[List[str]] = None, 
                              timeout_multiplier: float = 2.0,
                              max_retries: int = 3) -> Dict[str, int]:
        """
        Retry processing for problematic files with special handling.
        
        Args:
            file_ids: Specific file IDs to retry (if None, identify automatically)
            timeout_multiplier: Multiply default timeouts by this factor
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with counts of retried files and results
        """
        # Get problem files if not specified
        if file_ids is None:
            problem_files = self.identify_problem_files()
            # Flatten all categories
            file_ids = []
            for category in problem_files.values():
                file_ids.extend(category)
            # Remove duplicates
            file_ids = list(set(file_ids))
        
        if not file_ids:
            logger.info("No problematic files to retry")
            return {'total': 0}
        
        logger.info(f"Retrying {len(file_ids)} problematic files")
        
        # Results tracking
        results = {
            'total': len(file_ids),
            'transcription_success': 0,
            'transcription_failure': 0,
            'translation_success': 0,
            'translation_failure': 0
        }
        
        # Get retry counts from error log
        retry_counts = {}
        for file_id in file_ids:
            count_query = """
            SELECT COUNT(*) as retry_count FROM error_log
            WHERE file_id = ? AND error_message LIKE '%retry%'
            """
            count_result = self.db_manager.execute_query(count_query, (file_id,))
            retry_counts[file_id] = count_result[0]['retry_count'] if count_result else 0
        
        # Process each file individually with special handling
        for file_id in file_ids:
            if retry_counts.get(file_id, 0) >= max_retries:
                logger.warning(f"File {file_id} has been retried {retry_counts[file_id]} times, marking as qa_failed")
                self.db_manager.update_status(file_id=file_id, status='qa_failed')
                continue
            
            # Get file details
            file_query = "SELECT * FROM processing_status WHERE file_id = ?"
            file_results = self.db_manager.execute_query(file_query, (file_id,))
            
            if not file_results:
                logger.error(f"File {file_id} not found in database")
                continue
                
            file = file_results[0]
            file_path = file['file_path']
            
            # Check if file exists
            if not Path(file_path).exists():
                logger.error(f"Source file not found: {file_path}")
                continue
            
            # Retry transcription if needed
            if file['transcription_status'] in ['not_started', 'failed', 'in-progress']:
                success = self._retry_transcription(file_id, timeout_multiplier)
                if success:
                    results['transcription_success'] += 1
                else:
                    results['transcription_failure'] += 1
            
            # Retry translations if needed
            for lang in ['en', 'de', 'he']:
                status_field = f"translation_{lang}_status"
                
                if file[status_field] in ['not_started', 'failed', 'in-progress']:
                    # Only attempt translation if transcription succeeded
                    transcript_path = Path(self.file_manager.get_transcript_path(file_id))
                    if not transcript_path.exists() or transcript_path.stat().st_size == 0:
                        logger.warning(f"Cannot translate {file_id} to {lang}: missing transcript")
                        continue
                        
                    success = self._retry_translation(file_id, lang, timeout_multiplier)
                    if success:
                        results['translation_success'] += 1
                    else:
                        results['translation_failure'] += 1
        
        logger.info(f"Retry results: "
                   f"Transcription {results['transcription_success']}/{results['transcription_success'] + results['transcription_failure']} successful, "
                   f"Translation {results['translation_success']}/{results['translation_success'] + results['translation_failure']} successful")
        
        return results
    
    def _retry_transcription(self, file_id: str, timeout_multiplier: float = 2.0) -> bool:
        """
        Retry transcription with special handling for a problematic file.
        
        Args:
            file_id: File ID to retry
            timeout_multiplier: Multiply default timeouts by this factor
            
        Returns:
            True if successful
        """
        if not TRANSCRIPTION_AVAILABLE:
            logger.error(f"Cannot retry transcription for {file_id}: TranscriptionManager not available")
            return False
        
        logger.info(f"Retrying transcription for file {file_id}")
        
        try:
            # Get audio path
            audio_path = self.file_manager.get_audio_path(file_id)
            if not audio_path:
                logger.error(f"Audio path not found for {file_id}")
                return False
                
            # Create transcription manager with extended timeouts
            from transcription import TranscriptionManager
            
            # Deep copy config and modify timeouts
            import copy
            special_config = copy.deepcopy(self.config)
            
            # Extend timeouts and add retries
            if 'api_retries' in special_config:
                special_config['api_retries'] = int(special_config['api_retries'] * timeout_multiplier)
            else:
                special_config['api_retries'] = 12  # Default to 12 retries (more than normal)
                
            # Special audio splitting for problematic files
            # Use smaller chunks
            special_config['max_audio_size_mb'] = special_config.get('max_audio_size_mb', 25) / 1.5
            
            # Create manager and process
            transcription_manager = TranscriptionManager(self.db_manager, special_config)
            transcription_manager.set_file_manager(self.file_manager)
            
            # Mark as retry attempt in database
            self.db_manager.log_error(
                file_id=file_id,
                process_stage='transcription',
                error_message=f"Retry attempt with special handling",
                error_details=f"Timeout multiplier: {timeout_multiplier}, "
                             f"Retries: {special_config['api_retries']}, "
                             f"Chunk size: {special_config['max_audio_size_mb']}MB"
            )
            
            # Get file details
            file_query = "SELECT * FROM processing_status WHERE file_id = ?"
            file_results = self.db_manager.execute_query(file_query, (file_id,))
            file_details = file_results[0] if file_results else {}
            
            # Attempt transcription
            success = transcription_manager.transcribe_audio(
                file_id=file_id,
                audio_path=audio_path,
                file_details=file_details,
                auto_detect_language=True  # Force auto-detection for problematic files
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error retrying transcription for {file_id}: {e}")
            
            # Log error
            self.db_manager.log_error(
                file_id=file_id,
                process_stage='transcription',
                error_message=f"Error during special retry",
                error_details=str(e)
            )
            
            # Update status
            self.db_manager.update_status(
                file_id=file_id,
                status='failed',
                transcription_status='failed'
            )
            
            return False
    
    def _retry_translation(self, file_id: str, language: str, timeout_multiplier: float = 2.0) -> bool:
        """
        Retry translation with special handling for a problematic file.
        
        Args:
            file_id: File ID to retry
            language: Target language code
            timeout_multiplier: Multiply default timeouts by this factor
            
        Returns:
            True if successful
        """
        if not TRANSLATION_AVAILABLE:
            logger.error(f"Cannot retry translation for {file_id}: TranslationManager not available")
            return False
        
        logger.info(f"Retrying {language} translation for file {file_id}")
        
        try:
            # Get transcript text
            transcript_path = Path(self.file_manager.get_transcript_path(file_id))
            if not transcript_path.exists():
                logger.error(f"Transcript not found for {file_id}")
                return False
                
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read()
                
            if not transcript_text:
                logger.error(f"Empty transcript for {file_id}")
                return False
                
            # Create translation manager with extended timeouts
            from translation import TranslationManager
            
            # Deep copy config and modify settings
            import copy
            special_config = copy.deepcopy(self.config)
            
            # Use smaller chunk size for translations
            if 'max_chunk_size' in special_config:
                special_config['max_chunk_size'] = int(special_config['max_chunk_size'] / 1.5)
            else:
                special_config['max_chunk_size'] = 1000  # Default to small chunks
            
            # Create manager and process
            translation_manager = TranslationManager(self.db_manager, special_config)
            translation_manager.set_file_manager(self.file_manager)
            
            # Mark as retry attempt in database
            self.db_manager.log_error(
                file_id=file_id,
                process_stage=f'translation_{language}',
                error_message=f"Retry attempt with special handling",
                error_details=f"Timeout multiplier: {timeout_multiplier}, "
                             f"Chunk size: {special_config.get('max_chunk_size', 'default')}"
            )
            
            # Determine source language
            file_query = "SELECT detected_language FROM processing_status WHERE file_id = ?"
            file_results = self.db_manager.execute_query(file_query, (file_id,))
            source_language = file_results[0]['detected_language'] if file_results else None
            
            if not source_language:
                source_language = 'auto'  # Fall back to auto-detection
            
            # Attempt translation
            success = translation_manager.translate_text(
                file_id=file_id,
                text=transcript_text,
                source_language=source_language,
                target_language=language,
                force_reprocess=True
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error retrying {language} translation for {file_id}: {e}")
            
            # Log error
            self.db_manager.log_error(
                file_id=file_id,
                process_stage=f'translation_{language}',
                error_message=f"Error during special retry",
                error_details=str(e)
            )
            
            # Update status
            self.db_manager.update_status(
                file_id=file_id,
                **{f"translation_{language}_status": 'failed'}
            )
            
            return False
    
    def special_case_processing(self, file_ids: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Apply special case processing for files that need custom handling.
        
        Args:
            file_ids: Specific file IDs to process (if None, identify automatically)
            
        Returns:
            Dictionary with counts of processed files
        """
        # Identify problem files if not specified
        if file_ids is None:
            problem_files = self.identify_problem_files()
            # Use timeout and invalid audio categories
            file_ids = []
            for category in ['timeout', 'invalid_audio']:
                if category in problem_files:
                    file_ids.extend(problem_files[category])
            # Remove duplicates
            file_ids = list(set(file_ids))
        
        if not file_ids:
            logger.info("No files needing special case processing")
            return {'total': 0}
        
        logger.info(f"Applying special case processing to {len(file_ids)} files")
        
        # Results tracking
        results = {
            'total': len(file_ids),
            'processed': 0,
            'skipped': 0,
            'failed': 0
        }
        
        # Special case handling functions
        handlers = {
            'preprocess_audio': self._preprocess_audio,
            'fix_corrupt_audio': self._fix_corrupt_audio,
            'split_long_audio': self._split_long_audio,
            # Add more handlers as needed
        }
        
        # Process each file
        for file_id in file_ids:
            # Get file details
            file_query = "SELECT * FROM processing_status WHERE file_id = ?"
            file_results = self.db_manager.execute_query(file_query, (file_id,))
            
            if not file_results:
                logger.error(f"File {file_id} not found in database")
                results['skipped'] += 1
                continue
                
            file = file_results[0]
            file_path = file['file_path']
            
            # Check if file exists
            if not Path(file_path).exists():
                logger.error(f"Source file not found: {file_path}")
                results['skipped'] += 1
                continue
            
            # Determine which handlers to apply based on error patterns
            error_query = "SELECT * FROM error_log WHERE file_id = ? ORDER BY timestamp DESC LIMIT 5"
            error_results = self.db_manager.execute_query(error_query, (file_id,))
            
            applicable_handlers = []
            for handler_name, handler_func in handlers.items():
                if self._should_apply_handler(handler_name, file, error_results):
                    applicable_handlers.append(handler_func)
            
            if not applicable_handlers:
                logger.info(f"No special case handlers applicable for {file_id}")
                results['skipped'] += 1
                continue
            
            # Apply handlers in sequence
            success = False
            for handler in applicable_handlers:
                try:
                    if handler(file_id, file):
                        success = True
                        break
                except Exception as e:
                    logger.error(f"Error applying special case handler to {file_id}: {e}")
            
            if success:
                results['processed'] += 1
            else:
                results['failed'] += 1
        
        logger.info(f"Special case processing results: "
                   f"Processed: {results['processed']}, "
                   f"Skipped: {results['skipped']}, "
                   f"Failed: {results['failed']}")
        
        return results
    
    def _should_apply_handler(self, handler_name: str, file: Dict[str, Any], 
                             errors: List[Dict[str, Any]]) -> bool:
        """
        Determine if a handler should be applied based on file details and errors.
        
        Args:
            handler_name: Name of the handler
            file: File details dictionary
            errors: List of error records for the file
            
        Returns:
            True if handler should be applied
        """
        # Extract error messages and details
        error_texts = []
        for error in errors:
            if error.get('error_message'):
                error_texts.append(error['error_message'])
            if error.get('error_details'):
                error_texts.append(error['error_details'])
        
        error_text = ' '.join(error_texts).lower()
        
        # Check for handler-specific patterns
        if handler_name == 'preprocess_audio':
            # Apply to all audio files with issues
            return True
            
        elif handler_name == 'fix_corrupt_audio':
            # Look for corruption indicators
            corruption_patterns = ['corrupt', 'invalid', 'unsupported', 'header', 'format']
            return any(pattern in error_text for pattern in corruption_patterns)
            
        elif handler_name == 'split_long_audio':
            # Look for timeout or memory indicators
            timeout_patterns = ['timeout', 'timed out', 'memory', 'too large']
            return any(pattern in error_text for pattern in timeout_patterns)
        
        # Default to not applying
        return False
    
    def _preprocess_audio(self, file_id: str, file: Dict[str, Any]) -> bool:
        """
        Preprocess audio to handle common issues.
        
        Args:
            file_id: File ID to process
            file: File details dictionary
            
        Returns:
            True if successful
        """
        logger.info(f"Preprocessing audio for {file_id}")
        
        try:
            # Get source file path
            source_path = Path(file['file_path'])
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Create temporary directory for processing
            temp_dir = Path(tempfile.mkdtemp(prefix=f"audio_preprocess_{file_id}_"))
            processed_path = temp_dir / f"{file_id}_processed.mp3"
            
            # Basic audio normalization using ffmpeg
            # This handles various issues like volume levels and basic format problems
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', str(source_path),
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',  # Normalize audio levels
                '-ar', '44100',  # Consistent sample rate
                '-ac', '1',      # Convert to mono
                '-codec:a', 'libmp3lame',
                '-q:a', '2',     # High quality encoding
                str(processed_path)
            ]
            
            # Run ffmpeg
            logger.info(f"Running ffmpeg preprocessing: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(
                ffmpeg_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False  # Don't raise exception on non-zero exit
            )
            
            if result.returncode != 0 or not processed_path.exists():
                logger.error(f"ffmpeg preprocessing failed: {result.stderr.decode()}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # Make sure the result is valid
            if processed_path.stat().st_size < 1000:
                logger.error(f"Processed file too small: {processed_path.stat().st_size} bytes")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # Replace original file with processed version for transcription
            actual_audio_path = self.file_manager.get_audio_path(file_id)
            if actual_audio_path:
                # Create backup of original
                backup_path = Path(actual_audio_path + ".backup")
                if not backup_path.exists():
                    shutil.copy2(actual_audio_path, backup_path)
                
                # Copy processed file to original location
                shutil.copy2(processed_path, actual_audio_path)
                logger.info(f"Replaced {actual_audio_path} with preprocessed audio")
                
                # Clean up
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                # Reset transcription status
                self.db_manager.update_status(
                    file_id=file_id,
                    transcription_status='not_started'
                )
                
                return True
            else:
                logger.error(f"Could not determine audio path for {file_id}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
                
        except Exception as e:
            logger.error(f"Error preprocessing audio for {file_id}: {e}")
            return False
    
    def _fix_corrupt_audio(self, file_id: str, file: Dict[str, Any]) -> bool:
        """
        Fix corrupt audio files using reconstruction techniques.
        
        Args:
            file_id: File ID to process
            file: File details dictionary
            
        Returns:
            True if successful
        """
        logger.info(f"Attempting to fix corrupt audio for {file_id}")
        
        try:
            # Get source file path
            source_path = Path(file['file_path'])
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Create temporary directory for processing
            temp_dir = Path(tempfile.mkdtemp(prefix=f"audio_fix_{file_id}_"))
            fixed_path = temp_dir / f"{file_id}_fixed.mp3"
            
            # Try to fix headers and recover audio using ffmpeg
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-err_detect', 'ignore_err',  # Ignore errors
                '-i', str(source_path),
                '-acodec', 'libmp3lame',
                '-ar', '44100',  # Consistent sample rate
                '-ac', '1',      # Convert to mono
                str(fixed_path)
            ]
            
            # Run ffmpeg
            logger.info(f"Running ffmpeg fix: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(
                ffmpeg_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False  # Don't raise exception on non-zero exit
            )
            
            if result.returncode != 0 or not fixed_path.exists():
                logger.error(f"ffmpeg fix failed: {result.stderr.decode()}")
                
                # Try alternate approach - extract raw PCM and re-encode
                pcm_path = temp_dir / "raw_audio.pcm"
                ffmpeg_raw_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(source_path),
                    '-f', 's16le',  # Raw PCM format
                    '-ar', '44100',
                    '-ac', '1',
                    str(pcm_path)
                ]
                
                logger.info(f"Trying raw PCM extraction: {' '.join(ffmpeg_raw_cmd)}")
                subprocess.run(ffmpeg_raw_cmd, check=False)
                
                if pcm_path.exists() and pcm_path.stat().st_size > 1000:
                    # Rebuild from PCM
                    ffmpeg_rebuild_cmd = [
                        'ffmpeg', '-y',
                        '-f', 's16le',  # Raw PCM format
                        '-ar', '44100',
                        '-ac', '1',
                        '-i', str(pcm_path),
                        '-acodec', 'libmp3lame',
                        str(fixed_path)
                    ]
                    
                    logger.info(f"Rebuilding from PCM: {' '.join(ffmpeg_rebuild_cmd)}")
                    subprocess.run(ffmpeg_rebuild_cmd, check=False)
                
                # If still not fixed, give up
                if not fixed_path.exists() or fixed_path.stat().st_size < 1000:
                    logger.error("All fix attempts failed")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return False
            
            # Replace original file with fixed version for transcription
            actual_audio_path = self.file_manager.get_audio_path(file_id)
            if actual_audio_path:
                # Create backup of original
                backup_path = Path(actual_audio_path + ".corrupt")
                if not backup_path.exists():
                    shutil.copy2(actual_audio_path, backup_path)
                
                # Copy fixed file to original location
                shutil.copy2(fixed_path, actual_audio_path)
                logger.info(f"Replaced {actual_audio_path} with fixed audio")
                
                # Clean up
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                # Reset transcription status
                self.db_manager.update_status(
                    file_id=file_id,
                    transcription_status='not_started'
                )
                
                return True
            else:
                logger.error(f"Could not determine audio path for {file_id}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
                
        except Exception as e:
            logger.error(f"Error fixing corrupt audio for {file_id}: {e}")
            return False
    
    def _split_long_audio(self, file_id: str, file: Dict[str, Any]) -> bool:
        """
        Split long audio files into smaller segments for easier processing.
        
        Args:
            file_id: File ID to process
            file: File details dictionary
            
        Returns:
            True if successful
        """
        logger.info(f"Splitting long audio for {file_id}")
        
        try:
            # Get source file path
            source_path = Path(file['file_path'])
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            # Get duration using ffprobe
            ffprobe_cmd = [
                'ffprobe', '-v', 'error', 
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                str(source_path)
            ]
            
            result = subprocess.run(
                ffprobe_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"ffprobe failed: {result.stderr.decode()}")
                return False
                
            try:
                duration = float(result.stdout.decode().strip())
            except ValueError:
                logger.error(f"Could not parse duration: {result.stdout.decode()}")
                return False
                
            logger.info(f"Audio duration: {duration:.2f} seconds")
            
            # Split only if longer than 20 minutes
            if duration < 1200:  # 20 minutes in seconds
                logger.info(f"Audio not long enough to require splitting (duration: {duration:.2f}s)")
                return False
            
            # Create temporary directory for segments
            temp_dir = Path(tempfile.mkdtemp(prefix=f"audio_split_{file_id}_"))
            
            # Determine number of segments (aim for ~5 minute segments)
            segment_count = max(2, int(duration / 300) + 1)
            segment_duration = duration / segment_count
            
            logger.info(f"Splitting into {segment_count} segments of ~{segment_duration:.2f}s each")
            
            # Create segments
            segment_paths = []
            for i in range(segment_count):
                start_time = i * segment_duration
                
                # Last segment gets the remainder
                if i < segment_count - 1:
                    duration_arg = ['-t', str(segment_duration)]
                else:
                    duration_arg = []
                    
                segment_path = temp_dir / f"segment_{i:03d}.mp3"
                segment_paths.append(segment_path)
                
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(source_path),
                    '-ss', str(start_time),
                    *duration_arg,
                    '-vn',  # No video
                    '-acodec', 'libmp3lame',
                    '-ar', '44100',
                    '-ac', '1',
                    str(segment_path)
                ]
                
                logger.info(f"Creating segment {i+1}/{segment_count}: {' '.join(ffmpeg_cmd)}")
                result = subprocess.run(ffmpeg_cmd, check=False)
                
                if result.returncode != 0 or not segment_path.exists():
                    logger.error(f"Failed to create segment {i+1}")
                    return False
            
            # If all segments were created successfully
            if len(segment_paths) == segment_count and all(p.exists() for p in segment_paths):
                # Create a special directory for segments
                segments_dir = Path(file['file_path']).parent / f"{file_id}_segments"
                segments_dir.mkdir(exist_ok=True)
                
                # Move segments to final location
                for i, segment_path in enumerate(segment_paths):
                    target_path = segments_dir / f"{file_id}_segment_{i:03d}.mp3"
                    shutil.copy2(segment_path, target_path)
                    logger.info(f"Created segment: {target_path}")
                
                # Create a manifest file
                manifest_path = segments_dir / f"{file_id}_manifest.json"
                manifest = {
                    'file_id': file_id,
                    'original_path': str(source_path),
                    'segment_count': segment_count,
                    'segments': [
                        {
                            'index': i,
                            'path': str(segments_dir / f"{file_id}_segment_{i:03d}.mp3"),
                            'start_time': i * segment_duration,
                            'duration': segment_duration if i < segment_count - 1 else (duration - i * segment_duration)
                        }
                        for i in range(segment_count)
                    ]
                }
                
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)
                
                logger.info(f"Created segment manifest: {manifest_path}")
                
                # Clean up temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                # Add each segment as a new file in the database
                for i, segment in enumerate(manifest['segments']):
                    segment_file_id = f"{file_id}_segment_{i:03d}"
                    
                    # Check if segment already exists in database
                    check_query = "SELECT COUNT(*) as count FROM processing_status WHERE file_id = ?"
                    check_result = self.db_manager.execute_query(check_query, (segment_file_id,))
                    
                    if check_result and check_result[0]['count'] > 0:
                        logger.info(f"Segment {segment_file_id} already in database, skipping")
                        continue
                    
                    # Insert segment as new file
                    insert_query = """
                    INSERT INTO processing_status (
                        file_id, file_path, status, 
                        transcription_status, 
                        translation_en_status, translation_de_status, translation_he_status,
                        detected_language, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    
                    self.db_manager.execute_update(
                        insert_query,
                        (
                            segment_file_id,
                            segment['path'],
                            'not_started',
                            'not_started',
                            'not_started',
                            'not_started',
                            'not_started',
                            file.get('detected_language', ''),
                            int(time.time())
                        )
                    )
                    
                    logger.info(f"Added segment {segment_file_id} to database")
                
                # Mark original file as special
                self.db_manager.update_status(
                    file_id=file_id,
                    status='segmented',
                    transcription_status='segmented'
                )
                
                # Log the segmentation
                self.db_manager.log_error(
                    file_id=file_id,
                    process_stage='special_processing',
                    error_message=f"Split into {segment_count} segments",
                    error_details=f"Segment manifest: {manifest_path}"
                )
                
                return True
                
            else:
                logger.error("Failed to create all segments")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
                
        except Exception as e:
            logger.error(f"Error splitting audio for {file_id}: {e}")
            return False


class CommandLineInterface:
    """
    Command-line interface for all pipeline operations.
    """
    
    def __init__(self):
        """Initialize the command-line interface."""
        self.parser = argparse.ArgumentParser(
            description="Media Processing Pipeline Manager"
        )
        
        # Global options
        self.parser.add_argument('--db-path', type=str, default='media_tracking.db',
                                help='Path to SQLite database file')
        self.parser.add_argument('--config', type=str,
                                help='Path to configuration JSON file')
        self.parser.add_argument('--log-level', type=str, default='INFO',
                                choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                                help='Logging level')
        
        # Subcommands
        self.subparsers = self.parser.add_subparsers(dest='command', help='Command to execute')
        
        # status command
        status_parser = self.subparsers.add_parser('status', help='Check pipeline status')
        status_parser.add_argument('--detailed', action='store_true',
                                  help='Show detailed status information')
        status_parser.add_argument('--format', type=str, default='text',
                                 choices=['text', 'json', 'markdown'],
                                 help='Output format for report')
        
        # monitor command
        monitor_parser = self.subparsers.add_parser('monitor', help='Start pipeline monitoring')
        monitor_parser.add_argument('--check-interval', type=int, default=60,
                                   help='Seconds between status checks')
        monitor_parser.add_argument('--restart-interval', type=int, default=600,
                                   help='Seconds between restart checks')
        monitor_parser.add_argument('--no-auto-restart', action='store_true',
                                   help='Disable automatic restart of stalled processes')
        
        # restart command
        restart_parser = self.subparsers.add_parser('restart', help='Restart stalled processes')
        restart_parser.add_argument('--timeout', type=int, default=30,
                                   help='Minutes after which to consider a process stalled')
        restart_parser.add_argument('--no-auto-restart', action='store_true',
                                   help='Only reset status, do not start new processes')
        
        # start command
        start_parser = self.subparsers.add_parser('start', help='Start pipeline processes')
        start_parser.add_argument('--transcription', action='store_true',
                                 help='Start transcription process')
        start_parser.add_argument('--translation', type=str,
                                 help='Languages to translate (comma-separated, e.g., "en,de,he")')
        start_parser.add_argument('--transcription-workers', type=int, default=5,
                                 help='Number of transcription worker threads')
        start_parser.add_argument('--translation-workers', type=int, default=5,
                                 help='Number of translation worker threads per language')
        start_parser.add_argument('--batch-size', type=int,
                                 help='Batch size for processing')
        
        # retry command
        retry_parser = self.subparsers.add_parser('retry', help='Retry problematic files')
        retry_parser.add_argument('--file-ids', type=str,
                                 help='Comma-separated list of file IDs to retry')
        retry_parser.add_argument('--timeout-multiplier', type=float, default=2.0,
                                 help='Multiply default timeouts by this factor')
        retry_parser.add_argument('--max-retries', type=int, default=3,
                                 help='Maximum number of retry attempts')
        
        # special command
        special_parser = self.subparsers.add_parser('special', help='Apply special case processing')
        special_parser.add_argument('--file-ids', type=str,
                                   help='Comma-separated list of file IDs to process')
        
    def parse_arguments(self):
        """Parse command-line arguments."""
        return self.parser.parse_args()
    
    def run_command(self, args):
        """
        Run the specified command.
        
        Args:
            args: Parsed command-line arguments
        """
        # Set up logging
        log_level = getattr(logging, args.log_level)
        logging.getLogger().setLevel(log_level)
        
        # Load configuration
        config = {}
        if args.config:
            config_path = Path(args.config)
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading configuration: {e}")
                    return 1
        
        # Load environment variables from .env if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        # Connect to database
        db_manager = DatabaseManager(args.db_path)
        
        # Create file manager
        file_manager = FileManager(db_manager, config)
        
        # Create pipeline monitor
        pipeline_monitor = PipelineMonitor(db_manager, config)
        
        # Create problem file handler
        problem_handler = ProblemFileHandler(db_manager, file_manager, config)
        
        # Execute command
        if args.command == 'status':
            if args.format == 'json':
                # For JSON format, print detailed status by default
                status = pipeline_monitor.check_status(detailed=True)
                print(json.dumps(status, indent=2))
            else:
                # Generate report with requested format
                report = pipeline_monitor.generate_report(output_format=args.format)
                print(report)
            
        elif args.command == 'monitor':
            check_interval = args.check_interval
            restart_interval = args.restart_interval
            auto_restart = not args.no_auto_restart
            
            logger.info(f"Starting pipeline monitoring (press Ctrl+C to stop)")
            logger.info(f"Check interval: {check_interval}s")
            logger.info(f"Restart interval: {restart_interval}s")
            logger.info(f"Auto-restart: {'Enabled' if auto_restart else 'Disabled'}")
            
            try:
                # Start monitoring
                pipeline_monitor.start_monitoring(
                    check_interval=check_interval,
                    restart_interval=restart_interval,
                    auto_restart=auto_restart
                )
                
                # Keep main thread alive
                while True:
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Stopping monitoring (Ctrl+C pressed)")
                pipeline_monitor.stop_monitoring()
                
        elif args.command == 'restart':
            timeout = args.timeout
            auto_restart = not args.no_auto_restart
            
            result = pipeline_monitor.restart_stalled_processes(
                timeout_minutes=timeout,
                auto_restart=auto_restart
            )
            
            logger.info(f"Restart results: {result}")
            
        elif args.command == 'start':
            # Start requested processes
            processes_started = False
            
            if args.transcription:
                # Start transcription
                transcription_workers = args.transcription_workers
                pipeline_monitor._start_parallel_transcription(
                    workers=transcription_workers,
                    batch_size=args.batch_size
                )
                processes_started = True
            
            if args.translation:
                # Parse languages
                languages = [lang.strip() for lang in args.translation.split(',')]
                translation_workers = args.translation_workers
                
                # Start translation for each language
                for language in languages:
                    if language in ['en', 'de', 'he']:
                        pipeline_monitor._start_parallel_translation(
                            language=language,
                            workers=translation_workers,
                            batch_size=args.batch_size
                        )
                        processes_started = True
                    else:
                        logger.warning(f"Unsupported language: {language}")
            
            if not processes_started:
                logger.error("No processes specified to start")
                return 1
                
        elif args.command == 'retry':
            # Parse file IDs if provided
            file_ids = None
            if args.file_ids:
                file_ids = [file_id.strip() for file_id in args.file_ids.split(',')]
            
            # Retry problematic files
            result = problem_handler.retry_problematic_files(
                file_ids=file_ids,
                timeout_multiplier=args.timeout_multiplier,
                max_retries=args.max_retries
            )
            
            logger.info(f"Retry results: {result}")
            
        elif args.command == 'special':
            # Parse file IDs if provided
            file_ids = None
            if args.file_ids:
                file_ids = [file_id.strip() for file_id in args.file_ids.split(',')]
            
            # Apply special case processing
            result = problem_handler.special_case_processing(file_ids=file_ids)
            
            logger.info(f"Special processing results: {result}")
            
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
            
        return 0
    
    def start_parallel_pipeline(self, transcription_workers: int, translation_workers: int, 
                               languages: List[str], batch_size: Optional[int] = None):
        """
        Start complete parallel pipeline with both transcription and translation.
        
        Args:
            transcription_workers: Number of transcription worker threads
            translation_workers: Number of translation worker threads per language
            languages: List of language codes to translate to
            batch_size: Batch size for processing
        """
        # Create args object for run_command
        class Args:
            pass
        
        args = Args()
        args.command = 'start'
        args.db_path = 'media_tracking.db'
        args.config = None
        args.log_level = 'INFO'
        args.transcription = True
        args.translation = ','.join(languages)
        args.transcription_workers = transcription_workers
        args.translation_workers = translation_workers
        args.batch_size = batch_size
        
        return self.run_command(args)


def main():
    """Main function."""
    # Create CLI and run
    cli = CommandLineInterface()
    args = cli.parse_arguments()
    return cli.run_command(args)


if __name__ == "__main__":
    sys.exit(main())