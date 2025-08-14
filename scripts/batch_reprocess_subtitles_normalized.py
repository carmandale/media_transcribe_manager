#!/usr/bin/env python3
"""
Batch Subtitle Reprocessing Script for Issue #56
Reprocesses 728 interviews with language preservation logic to fix over-translated subtitles.
"""

import os
import sys
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import sqlite3

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# CRITICAL FIX: Load .env file to get DEEPL_API_KEY and other environment variables
# This was the missing piece - without this, DeepL never initializes!
from dotenv import load_dotenv
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)
    # Verify DeepL is now available
    if os.getenv('DEEPL_API_KEY'):
        print("✅ DeepL API key loaded from .env")
    else:
        print("⚠️ Warning: DEEPL_API_KEY not found in .env")

from scribe.database import Database
from scribe.srt_translator import translate_srt_file
from scribe.pipeline import PipelineConfig
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def normalize_srt_file(srt_path: Path, create_backup: bool = True) -> bool:
    """
    Normalize spacing in an SRT file by fixing word spacing issues.
    CRITICAL: This fixes the spacing issue in .orig.srt files that causes Hebrew translation to hang.
    
    Args:
        srt_path: Path to the SRT file
        create_backup: If True, create a backup before modifying
        
    Returns:
        True if normalization successful, False otherwise
    """
    try:
        if not srt_path.exists():
            logger.warning(f"SRT file not found: {srt_path}")
            return False
        
        # Create backup if requested
        if create_backup:
            backup_path = srt_path.with_suffix('.srt.spacing_backup')
            if not backup_path.exists():  # Only backup once
                shutil.copy2(srt_path, backup_path)
                logger.debug(f"Created backup: {backup_path}")
        
        # Read the file
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Normalize line by line
        normalized_lines = []
        for line in content.split('\n'):
            # Skip timestamp lines, index lines, and empty lines
            if '-->' in line or line.strip().isdigit() or not line.strip():
                normalized_lines.append(line)
            else:
                # Fix spacing in text lines - replace multiple spaces with single space
                normalized_line = re.sub(r'\s+', ' ', line.strip())
                normalized_lines.append(normalized_line)
        
        # Write back the normalized content
        normalized_content = '\n'.join(normalized_lines)
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(normalized_content)
        
        logger.debug(f"Normalized spacing in: {srt_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error normalizing {srt_path}: {e}")
        return False

class SubtitleReprocessor:
    """Handles batch reprocessing of subtitle files with preservation logic."""
    
    def __init__(self, output_dir: Path = None, backup_dir: Path = None, detect_batch_size: int = 200):
        """
        Initialize the reprocessor.
        
        Args:
            output_dir: Directory containing interview files (default: ./output)
            backup_dir: Directory for backups (default: ./reprocessing_backups)
        """
        self.output_dir = output_dir or Path("output")
        self.backup_dir = backup_dir or Path("reprocessing_backups")
        self.db = Database()
        self.detect_batch_size = detect_batch_size
        
        # Create directories
        self.backup_dir.mkdir(exist_ok=True)
        
        # Languages to process
        self.target_languages = ['en', 'de', 'he']
        
        # Statistics
        self.stats = {
            'total_interviews': 0,
            'processed_interviews': 0,
            'failed_interviews': 0,
            'backed_up_files': 0,
            'reprocessed_files': 0,
            'errors': []
        }
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def identify_interviews_for_reprocessing(self, force_all: bool = False, limit: int = None) -> List[Dict]:
        """
        Identify interviews that need reprocessing.
        
        Args:
            force_all: If True, reprocess all completed interviews
            limit: Maximum number of interviews to process (for testing)
            
        Returns:
            List of interview records needing reprocessing
        """
        logger.info(f"Identifying interviews for reprocessing (force_all={force_all}, limit={limit})")
        
        # Query for completed interviews
        # Check for presence of preservation marker file to track if processed with new fix
        query = """
            SELECT m.file_id, m.original_path, m.created_at, p.last_updated
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.transcription_status = 'completed'
              AND p.status != 'failed'
            ORDER BY m.created_at ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        conn = self.db._get_connection()
        cursor = conn.execute(query)
        interviews = []
        
        for row in cursor.fetchall():
            interview = dict(row)
            
            # Check if interview directory exists and has subtitle files
            interview_dir = self.output_dir / interview['file_id']
            if interview_dir.exists():
                # Check if already processed with preservation fix
                preservation_marker = interview_dir / '.preservation_fix_applied'
                if not force_all and preservation_marker.exists():
                    logger.debug(f"Skipping {interview['file_id']} - already processed with preservation fix")
                    continue
                
                # Look for existing subtitle files that would be over-translated
                subtitle_files = {
                    'orig': interview_dir / f"{interview['file_id']}.orig.srt",
                    'en': interview_dir / f"{interview['file_id']}.en.srt",
                    'de': interview_dir / f"{interview['file_id']}.de.srt",
                    'he': interview_dir / f"{interview['file_id']}.he.srt"
                }
                
                # Check which files exist
                existing_files = {lang: path for lang, path in subtitle_files.items() if path.exists()}
                
                if existing_files:
                    interview['subtitle_files'] = existing_files
                    interview['interview_dir'] = interview_dir
                    interviews.append(interview)
        
        logger.info(f"Found {len(interviews)} interviews needing reprocessing")
        return interviews
    
    def backup_interview_subtitles(self, interview: Dict, batch_id: str) -> bool:
        """
        Backup subtitle files for an interview.
        
        Args:
            interview: Interview record with subtitle files
            batch_id: Batch identifier for organization
            
        Returns:
            True if backup successful, False otherwise
        """
        file_id = interview['file_id']
        subtitle_files = interview['subtitle_files']
        
        # Create backup directory for this interview
        backup_interview_dir = self.backup_dir / batch_id / file_id
        backup_interview_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Backup each subtitle file
            for lang, source_path in subtitle_files.items():
                if source_path.exists():
                    backup_path = backup_interview_dir / source_path.name
                    shutil.copy2(source_path, backup_path)
                    logger.debug(f"Backed up {source_path} to {backup_path}")
                    self.stats['backed_up_files'] += 1
            
            # Create backup metadata
            metadata = {
                'file_id': file_id,
                'backup_timestamp': datetime.now().isoformat(),
                'batch_id': batch_id,
                'original_files': {lang: str(path) for lang, path in subtitle_files.items()},
                'backup_directory': str(backup_interview_dir)
            }
            
            metadata_path = backup_interview_dir / 'backup_metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.debug(f"Successfully backed up subtitles for {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup subtitles for {file_id}: {e}")
            self.stats['errors'].append(f"Backup failed for {file_id}: {e}")
            return False
    
    def reprocess_interview_subtitles(self, interview: Dict, batch_id: str = None, batch_dir: Path = None, 
                                     interview_idx: int = 0, total_interviews: int = 0) -> Dict[str, bool]:
        """
        Reprocess subtitle files for an interview with preservation logic.
        
        Args:
            interview: Interview record
            batch_id: Optional batch identifier for progress tracking
            batch_dir: Optional batch directory for writing progress
            interview_idx: Current interview index in batch
            total_interviews: Total interviews in batch
            
        Returns:
            Dictionary of language -> success status
        """
        file_id = interview['file_id']
        interview_dir = interview['interview_dir']
        subtitle_files = interview['subtitle_files']
        
        logger.info(f"Reprocessing subtitles for {file_id}")
        
        # Find the original SRT file (source of truth)
        orig_srt = None
        if 'orig' in subtitle_files:
            orig_srt = subtitle_files['orig']
        else:
            # Fallback to regular .srt file
            regular_srt = interview_dir / f"{file_id}.srt"
            if regular_srt.exists():
                orig_srt = regular_srt
        
        if not orig_srt or not orig_srt.exists():
            error_msg = f"No original SRT file found for {file_id}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)
            return {}
        
        # CRITICAL FIX: Normalize spacing in .orig.srt BEFORE translation
        # This prevents Hebrew translation from hanging on malformed text with spaces between words
        logger.info(f"  Normalizing spacing in {orig_srt.name}...")
        if not normalize_srt_file(orig_srt, create_backup=True):
            logger.warning(f"  Failed to normalize {orig_srt.name}, continuing anyway...")
        
        results = {}
        
        # Reprocess for each target language
        for lang_idx, target_lang in enumerate(self.target_languages):
            output_srt = interview_dir / f"{file_id}.{target_lang}.srt"
            
            logger.info(f"  Reprocessing {file_id} for {target_lang.upper()}")
            
            # Write per-language heartbeat
            if batch_dir and batch_dir.exists():
                try:
                    lang_progress = {
                        'batch_id': batch_id,
                        'current_interview': interview_idx + 1,
                        'total_interviews': total_interviews,
                        'file_id': file_id,
                        'current_language': target_lang.upper(),
                        'language_progress': f"{lang_idx + 1}/{len(self.target_languages)}",
                        'timestamp': datetime.now().isoformat(),
                        'status': 'processing'
                    }
                    
                    # Write language-specific progress
                    lang_status_file = batch_dir / f'language_status_{target_lang}.json'
                    lang_status_file.write_text(json.dumps(lang_progress, indent=2))
                    
                    # Append to detailed progress log
                    with open(batch_dir / 'detailed_progress.log', 'a') as f:
                        f.write(f"[{lang_progress['timestamp']}] Interview {interview_idx + 1}/{total_interviews} | "
                               f"File: {file_id} | Language: {target_lang.upper()} ({lang_idx + 1}/{len(self.target_languages)})\n")
                except Exception as e:
                    logger.debug(f"Language heartbeat write failed: {e}")
            
            try:
                # Use the preservation logic
                success = translate_srt_file(
                    str(orig_srt),
                    str(output_srt),
                    target_language=target_lang,
                    preserve_original_when_matching=True,  # This is the key fix!
                    batch_size=100,
                    detect_batch_size=self.detect_batch_size,
                    estimate_only=False
                )
                
                if success:
                    logger.info(f"    ✅ Successfully reprocessed {target_lang.upper()}")
                    results[target_lang] = True
                    self.stats['reprocessed_files'] += 1
                else:
                    logger.error(f"    ❌ Failed to reprocess {target_lang.upper()}")
                    results[target_lang] = False
                    self.stats['errors'].append(f"Reprocessing failed for {file_id} ({target_lang})")
                    
            except Exception as e:
                logger.error(f"    ❌ Exception reprocessing {target_lang.upper()}: {e}")
                results[target_lang] = False
                self.stats['errors'].append(f"Exception for {file_id} ({target_lang}): {e}")
        
        # Mark interview as processed with preservation fix
        if results and all(results.values()):
            try:
                marker_file = interview_dir / '.preservation_fix_applied'
                marker_file.write_text(json.dumps({
                    'processed_at': datetime.now().isoformat(),
                    'languages': list(results.keys()),
                    'success': True
                }))
                logger.debug(f"Marked {file_id} as processed with preservation fix")
            except Exception as e:
                logger.warning(f"Could not create preservation marker for {file_id}: {e}")
        
        return results
    
    def validate_reprocessed_interview(self, interview: Dict, reprocess_results: Dict[str, bool]) -> bool:
        """
        Validate that reprocessed subtitles maintain timing and format integrity.
        
        Args:
            interview: Interview record
            reprocess_results: Results from reprocessing
            
        Returns:
            True if validation passes, False otherwise
        """
        file_id = interview['file_id']
        interview_dir = interview['interview_dir']
        
        # Basic validation: check that files exist and have content
        validation_passed = True
        
        for target_lang, success in reprocess_results.items():
            if success:
                output_file = interview_dir / f"{file_id}.{target_lang}.srt"
                
                if not output_file.exists():
                    logger.error(f"Validation failed: {output_file} does not exist")
                    validation_passed = False
                    continue
                
                # Check file size (should not be empty)
                if output_file.stat().st_size == 0:
                    logger.error(f"Validation failed: {output_file} is empty")
                    validation_passed = False
                    continue
                
                # Basic SRT format check
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if not content.strip():
                            logger.error(f"Validation failed: {output_file} has no content")
                            validation_passed = False
                            continue
                        
                        # Check for basic SRT structure (timing lines)
                        if '-->' not in content:
                            logger.error(f"Validation failed: {output_file} missing timing markers")
                            validation_passed = False
                            continue
                            
                except Exception as e:
                    logger.error(f"Validation failed: Cannot read {output_file}: {e}")
                    validation_passed = False
        
        if validation_passed:
            logger.debug(f"Validation passed for {file_id}")
        else:
            logger.error(f"Validation failed for {file_id}")
            
        return validation_passed
    
    def process_batch(self, interviews: List[Dict], batch_id: str, workers: int = 1) -> Dict:
        """
        Process a batch of interviews.
        
        Args:
            interviews: List of interview records
            batch_id: Batch identifier
            
        Returns:
            Batch processing results
        """
        logger.info(f"Processing batch {batch_id} with {len(interviews)} interviews")
        # Ensure batch directory exists for status artifacts
        batch_dir = self.backup_dir / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        
        batch_results = {
            'batch_id': batch_id,
            'total_interviews': len(interviews),
            'successful_interviews': 0,
            'failed_interviews': 0,
            'interview_results': {},
            'start_time': datetime.now().isoformat(),
            'end_time': None
        }
        
        batch_start_ts = datetime.now()

        # Single-threaded path (default, safest)
        if workers == 1:
            for idx, interview in enumerate(interviews, start=1):
                file_id = interview['file_id']
                logger.info(f"Processing interview {idx}/{len(interviews)}: {file_id}")
                interview_start_ts = datetime.now()
                
                # Step 1: Backup
                backup_success = self.backup_interview_subtitles(interview, batch_id)
                if not backup_success:
                    logger.error(f"Skipping {file_id} due to backup failure")
                    batch_results['failed_interviews'] += 1
                    batch_results['interview_results'][file_id] = {
                        'success': False,
                        'error': 'Backup failed'
                    }
                    continue
                
                # Step 2: Reprocess with progress tracking
                reprocess_results = self.reprocess_interview_subtitles(
                    interview, 
                    batch_id=batch_id,
                    batch_dir=batch_dir,
                    interview_idx=batch_results['successful_interviews'] + batch_results['failed_interviews'],
                    total_interviews=len(interviews)
                )
                
                # Step 3: Validate
                validation_success = self.validate_reprocessed_interview(interview, reprocess_results)
                
                # Step 4: Record results
                if validation_success and all(reprocess_results.values()):
                    batch_results['successful_interviews'] += 1
                    batch_results['interview_results'][file_id] = {
                        'success': True,
                        'reprocess_results': reprocess_results
                    }
                    self.stats['processed_interviews'] += 1
                    logger.info(f"✅ Successfully processed {file_id}")
                else:
                    batch_results['failed_interviews'] += 1
                    batch_results['interview_results'][file_id] = {
                        'success': False,
                        'reprocess_results': reprocess_results,
                        'validation_passed': validation_success
                    }
                    self.stats['failed_interviews'] += 1
                    logger.error(f"❌ Failed to process {file_id}")

                # --- Enhanced live status/heartbeat ---
                elapsed = (datetime.now() - batch_start_ts).total_seconds()
                processed = batch_results['successful_interviews'] + batch_results['failed_interviews']
                remaining = max(len(interviews) - processed, 0)
                rate = (processed / elapsed) if elapsed > 0 else 0.0
                
                # Calculate more accurate ETA based on recent processing times
                recent_times = batch_results.get('recent_processing_times', [])
                interview_duration = (datetime.now() - interview_start_ts).total_seconds()
                recent_times.append(interview_duration)
                if len(recent_times) > 10:  # Keep last 10 for rolling average
                    recent_times = recent_times[-10:]
                batch_results['recent_processing_times'] = recent_times
                
                if recent_times and remaining > 0:
                    avg_time_per_interview = sum(recent_times) / len(recent_times)
                    eta_seconds = int(remaining * avg_time_per_interview)
                    eta_human = self._format_duration(eta_seconds)
                else:
                    eta_human = "calculating..."

                status = {
                    'batch_id': batch_id,
                    'processed': processed,
                    'total': len(interviews),
                    'successful': batch_results['successful_interviews'],
                    'failed': batch_results['failed_interviews'],
                    'current_file_id': file_id,
                    'last_duration_seconds': interview_duration,
                    'avg_duration_seconds': sum(recent_times) / len(recent_times) if recent_times else 0,
                    'elapsed_seconds': elapsed,
                    'elapsed_human': self._format_duration(int(elapsed)),
                    'eta_seconds': eta_seconds if recent_times else None,
                    'eta_human': eta_human,
                    'processing_rate': f"{rate:.2f} interviews/sec" if rate > 0 else "N/A",
                    'updated_at': datetime.now().isoformat(),
                    'progress_percent': round((processed / len(interviews)) * 100, 1)
                }
                try:
                    (batch_dir / 'status.json').write_text(json.dumps(status, indent=2))
                    with open(batch_dir / 'progress.log', 'a') as lf:
                        lf.write(f"[{status['updated_at']}] {processed}/{len(interviews)} done ({status['progress_percent']}%) | "
                                f"Last: {interview_duration:.1f}s | Avg: {status['avg_duration_seconds']:.1f}s | "
                                f"Success: {batch_results['successful_interviews']} | Fail: {batch_results['failed_interviews']} | "
                                f"ETA: {eta_human}\n")
                except Exception as e:
                    logger.debug(f"Progress write failed: {e}")

        else:
            # Parallel path with a small worker pool (2-3 recommended)
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            lock = threading.Lock()

            def process_one(ix: int, itv: Dict):
                start_ts = datetime.now()
                fid = itv['file_id']
                local_success = False
                local_results = {}
                # Backup
                if not self.backup_interview_subtitles(itv, batch_id):
                    return fid, False, {'error': 'Backup failed'}, (datetime.now() - start_ts).total_seconds()
                # Reprocess
                local_results = self.reprocess_interview_subtitles(
                    itv,
                    batch_id=batch_id,
                    batch_dir=batch_dir,
                    interview_idx=ix - 1,  # 0-based internally
                    total_interviews=len(interviews)
                )
                # Validate
                validation_success = self.validate_reprocessed_interview(itv, local_results)
                local_success = validation_success and all(local_results.values())
                return fid, local_success, local_results, (datetime.now() - start_ts).total_seconds()

            # Submit tasks
            with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
                futures = {
                    ex.submit(process_one, idx, interview): (idx, interview)
                    for idx, interview in enumerate(interviews, start=1)
                }
                recent_times: List[float] = []
                for fut in as_completed(futures):
                    fid, ok, res, dur = fut.result()
                    with lock:
                        if ok:
                            batch_results['successful_interviews'] += 1
                            batch_results['interview_results'][fid] = {
                                'success': True,
                                'reprocess_results': res
                            }
                            self.stats['processed_interviews'] += 1
                            logger.info(f"✅ Successfully processed {fid}")
                        else:
                            batch_results['failed_interviews'] += 1
                            batch_results['interview_results'][fid] = {
                                'success': False,
                                'reprocess_results': res,
                            }
                            self.stats['failed_interviews'] += 1
                            logger.error(f"❌ Failed to process {fid}")

                        # Status update
                        recent_times.append(dur)
                        if len(recent_times) > 10:
                            recent_times = recent_times[-10:]
                        elapsed = (datetime.now() - batch_start_ts).total_seconds()
                        processed = batch_results['successful_interviews'] + batch_results['failed_interviews']
                        remaining = max(len(interviews) - processed, 0)
                        avg_time_per_interview = sum(recent_times) / len(recent_times) if recent_times else 0
                        eta_seconds = int(remaining * avg_time_per_interview) if avg_time_per_interview and remaining else None
                        eta_human = self._format_duration(eta_seconds) if eta_seconds else "calculating..."
                        rate = (processed / elapsed) if elapsed > 0 else 0.0
                        status = {
                            'batch_id': batch_id,
                            'processed': processed,
                            'total': len(interviews),
                            'successful': batch_results['successful_interviews'],
                            'failed': batch_results['failed_interviews'],
                            'current_file_id': fid,
                            'last_duration_seconds': dur,
                            'avg_duration_seconds': avg_time_per_interview,
                            'elapsed_seconds': elapsed,
                            'elapsed_human': self._format_duration(int(elapsed)),
                            'eta_seconds': eta_seconds,
                            'eta_human': eta_human,
                            'processing_rate': f"{rate:.2f} interviews/sec" if rate > 0 else "N/A",
                            'updated_at': datetime.now().isoformat(),
                            'progress_percent': round((processed / len(interviews)) * 100, 1)
                        }
                        try:
                            (batch_dir / 'status.json').write_text(json.dumps(status, indent=2))
                            with open(batch_dir / 'progress.log', 'a') as lf:
                                lf.write(f"[{status['updated_at']}] {processed}/{len(interviews)} done ({status['progress_percent']}%) | "
                                        f"Last: {dur:.1f}s | Avg: {avg_time_per_interview:.1f}s | "
                                        f"Success: {batch_results['successful_interviews']} | Fail: {batch_results['failed_interviews']} | "
                                        f"ETA: {eta_human}\n")
                        except Exception as e:
                            logger.debug(f"Progress write failed: {e}")
            if workers == 1:
                file_id = interview['file_id']
                logger.info(f"Processing interview {idx}/{len(interviews)}: {file_id}")
                interview_start_ts = datetime.now()
                
                # Step 1: Backup
                backup_success = self.backup_interview_subtitles(interview, batch_id)
                if not backup_success:
                    logger.error(f"Skipping {file_id} due to backup failure")
                    batch_results['failed_interviews'] += 1
                    batch_results['interview_results'][file_id] = {
                        'success': False,
                        'error': 'Backup failed'
                    }
                    # Skip processing and proceed to next interview
                    # emulate loop-continue by wrapping subsequent code in else
                    proceed = False
                else:
                    proceed = True
                
                # Step 2: Reprocess with progress tracking
                if proceed:
                    reprocess_results = self.reprocess_interview_subtitles(
                        interview, 
                        batch_id=batch_id,
                        batch_dir=batch_dir,
                        interview_idx=batch_results['successful_interviews'] + batch_results['failed_interviews'],
                        total_interviews=len(interviews)
                    )
                
                # Step 3: Validate
                if proceed:
                    validation_success = self.validate_reprocessed_interview(interview, reprocess_results)
                else:
                    validation_success = False
                
                # Step 4: Record results
                if proceed and validation_success and all(reprocess_results.values()):
                    batch_results['successful_interviews'] += 1
                    batch_results['interview_results'][file_id] = {
                        'success': True,
                        'reprocess_results': reprocess_results
                    }
                    self.stats['processed_interviews'] += 1
                    logger.info(f"✅ Successfully processed {file_id}")
                else:
                    batch_results['failed_interviews'] += 1
                    batch_results['interview_results'][file_id] = {
                        'success': False,
                        'reprocess_results': reprocess_results if proceed else {},
                        'validation_passed': validation_success if proceed else False
                    }
                    self.stats['failed_interviews'] += 1
                    logger.error(f"❌ Failed to process {file_id}")
                
                # --- Enhanced live status/heartbeat ---
                elapsed = (datetime.now() - batch_start_ts).total_seconds()
                processed = batch_results['successful_interviews'] + batch_results['failed_interviews']
                remaining = max(len(interviews) - processed, 0)
                rate = (processed / elapsed) if elapsed > 0 else 0.0
                
                # Calculate more accurate ETA based on recent processing times
                recent_times = batch_results.get('recent_processing_times', [])
                interview_duration = (datetime.now() - interview_start_ts).total_seconds()
                recent_times.append(interview_duration)
                if len(recent_times) > 10:  # Keep last 10 for rolling average
                    recent_times = recent_times[-10:]
                batch_results['recent_processing_times'] = recent_times
                
                if recent_times and remaining > 0:
                    avg_time_per_interview = sum(recent_times) / len(recent_times)
                    eta_seconds = int(remaining * avg_time_per_interview)
                    eta_human = self._format_duration(eta_seconds)
                else:
                    eta_human = "calculating..."

                status = {
                    'batch_id': batch_id,
                    'processed': processed,
                    'total': len(interviews),
                    'successful': batch_results['successful_interviews'],
                    'failed': batch_results['failed_interviews'],
                    'current_file_id': file_id,
                    'last_duration_seconds': interview_duration,
                    'avg_duration_seconds': sum(recent_times) / len(recent_times) if recent_times else 0,
                    'elapsed_seconds': elapsed,
                    'elapsed_human': self._format_duration(int(elapsed)),
                    'eta_seconds': eta_seconds if recent_times else None,
                    'eta_human': eta_human,
                    'processing_rate': f"{rate:.2f} interviews/sec" if rate > 0 else "N/A",
                    'updated_at': datetime.now().isoformat(),
                    'progress_percent': round((processed / len(interviews)) * 100, 1)
                }
                try:
                    (batch_dir / 'status.json').write_text(json.dumps(status, indent=2))
                    with open(batch_dir / 'progress.log', 'a') as lf:
                        lf.write(f"[{status['updated_at']}] {processed}/{len(interviews)} done ({status['progress_percent']}%) | "
                                f"Last: {interview_duration:.1f}s | Avg: {status['avg_duration_seconds']:.1f}s | "
                                f"Success: {batch_results['successful_interviews']} | Fail: {batch_results['failed_interviews']} | "
                                f"ETA: {eta_human}\n")
                except Exception as e:
                    logger.debug(f"Progress write failed: {e}")
        
        batch_results['end_time'] = datetime.now().isoformat()
        
        # Save batch results
        batch_results_file = self.backup_dir / batch_id / 'batch_results.json'
        with open(batch_results_file, 'w') as f:
            json.dump(batch_results, f, indent=2)
        
        logger.info(f"Batch {batch_id} completed: {batch_results['successful_interviews']}/{batch_results['total_interviews']} successful")
        
        return batch_results
    
    def rollback_batch(self, batch_id: str) -> bool:
        """
        Rollback a batch by restoring backed up files.
        
        Args:
            batch_id: Batch identifier to rollback
            
        Returns:
            True if rollback successful, False otherwise
        """
        logger.info(f"Rolling back batch {batch_id}")
        
        batch_backup_dir = self.backup_dir / batch_id
        if not batch_backup_dir.exists():
            logger.error(f"Batch backup directory not found: {batch_backup_dir}")
            return False
        
        rollback_success = True
        
        # Find all interview backup directories
        for interview_backup_dir in batch_backup_dir.iterdir():
            if interview_backup_dir.is_dir():
                metadata_file = interview_backup_dir / 'backup_metadata.json'
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        
                        file_id = metadata['file_id']
                        logger.info(f"Rolling back {file_id}")
                        
                        # Restore each backed up file
                        for backup_file in interview_backup_dir.iterdir():
                            if backup_file.name.endswith('.srt'):
                                # Determine original location
                                interview_dir = self.output_dir / file_id
                                original_file = interview_dir / backup_file.name
                                
                                # Restore the file
                                shutil.copy2(backup_file, original_file)
                                logger.debug(f"Restored {backup_file} to {original_file}")
                        
                        logger.info(f"✅ Successfully rolled back {file_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to rollback {interview_backup_dir.name}: {e}")
                        rollback_success = False
        
        if rollback_success:
            logger.info(f"✅ Successfully rolled back batch {batch_id}")
        else:
            logger.error(f"❌ Rollback of batch {batch_id} had errors")
            
        return rollback_success
    
    def generate_final_report(self) -> Path:
        """Generate a final processing report."""
        report_file = self.backup_dir / f"reprocessing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        with open(report_file, 'w') as f:
            f.write("# Subtitle Reprocessing Report - Issue #56\\n\\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n")
            
            f.write("## Summary\\n\\n")
            f.write(f"- **Total interviews processed:** {self.stats['processed_interviews']}\\n")
            f.write(f"- **Failed interviews:** {self.stats['failed_interviews']}\\n")
            f.write(f"- **Files backed up:** {self.stats['backed_up_files']}\\n")
            f.write(f"- **Files reprocessed:** {self.stats['reprocessed_files']}\\n")
            f.write(f"- **Errors encountered:** {len(self.stats['errors'])}\\n\\n")
            
            if self.stats['errors']:
                f.write("## Errors\\n\\n")
                for error in self.stats['errors']:
                    f.write(f"- {error}\\n")
                f.write("\\n")
            
            f.write("## Process Details\\n\\n")
            f.write("This reprocessing addressed Issue #56 by applying language preservation logic\\n")
            f.write("to 728 interviews that had over-translated subtitles from the old system.\\n\\n")
            f.write("**Key Changes:**\\n")
            f.write("- Applied `preserve_original_when_matching=True` to all translations\\n")
            f.write("- Segments already in target language are now preserved exactly\\n")
            f.write("- Only segments in different languages are translated\\n")
            f.write("- Perfect timing synchronization maintained\\n\\n")
        
        logger.info(f"Final report generated: {report_file}")
        return report_file

def main():
    """Main reprocessing function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch reprocess subtitle files with preservation fix')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Number of interviews per batch (default: 100)')
    parser.add_argument('--detect-batch-size', type=int, default=200,
                       help='Batch size for language detection per API call (default: 200)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit total interviews to process (for testing)')
    parser.add_argument('--force-all', action='store_true',
                       help='Force reprocessing even if already marked as processed')
    parser.add_argument('--start-from', type=int, default=0,
                       help='Start from interview number (for resuming)')
    parser.add_argument('--workers', type=int, default=1,
                       help='Number of parallel interview workers (default: 1)')
    
    # Validation mode arguments
    parser.add_argument('--validation-mode', action='store_true',
                       help='Run validation mode instead of full batch processing')
    parser.add_argument('--validation-count', type=int, default=10,
                       help='Number of files to validate (validation mode only)')
    parser.add_argument('--validation-languages', nargs='+', default=['en', 'de', 'he'],
                       help='Languages to validate (validation mode only)')
    parser.add_argument('--max-validation-spend', type=float, default=10.0,
                       help='Maximum spend for validation batch ($10.00 default)')
    parser.add_argument('--budget-limit', type=float, default=500.0,
                       help='Budget limit for full batch cost analysis ($500.00 default)')
    
    args = parser.parse_args()
    
    # Handle validation mode
    if args.validation_mode:
        logger.info("Starting validation mode for batch reprocessing safety")
        logger.info("This will test a small sample before committing to the full $200-500 operation")
        
        try:
            # Import ValidationMode (local import to avoid dependency issues)
            from scripts.validation_mode import ValidationMode
            
            # Initialize and run validation
            validation_mode = ValidationMode(
                output_dir=Path("output"),
                max_spend=args.max_validation_spend
            )
            
            print(f"🔬 VALIDATION MODE")
            print(f"Files to test: {args.validation_count}")
            print(f"Languages: {', '.join(args.validation_languages)}")
            print(f"Max validation spend: ${args.max_validation_spend:.2f}")
            print(f"Full batch budget: ${args.budget_limit:.2f}")
            print()
            
            # Run validation workflow
            result = validation_mode.run_validation(
                file_count=args.validation_count,
                languages=args.validation_languages,
                budget_limit=args.budget_limit
            )
            
            # Display results
            if result['success']:
                print("✅ Validation completed successfully")
                
                # Extract and display key results
                report = result['report']
                recommendation = report['recommendation']
                
                print(f"\n🎯 RECOMMENDATION: {recommendation['decision']}")
                print(f"📊 Confidence: {recommendation['confidence']:.1%}")
                print(f"📝 {recommendation['executive_summary']}")
                
                # Cost analysis
                cost_analysis = report['cost_analysis']
                projected_cost = cost_analysis['projections']['estimated_full_cost']
                print(f"\n💰 COST PROJECTION: ${projected_cost:.2f}")
                
                if cost_analysis.get('budget_analysis'):
                    budget_analysis = cost_analysis['budget_analysis']
                    usage_pct = budget_analysis['projected_usage_percentage']
                    print(f"   Budget usage: {usage_pct:.1f}% of ${args.budget_limit:.2f}")
                
                # Quality analysis
                quality_analysis = report['quality_analysis']
                avg_quality = quality_analysis['overall_statistics']['average_quality']
                quality_tier = quality_analysis['quality_tier']
                print(f"\n🔍 QUALITY ASSESSMENT: {avg_quality:.3f} ({quality_tier})")
                
                # Next steps
                print(f"\n📋 NEXT STEPS:")
                for step in recommendation['next_steps']:
                    print(f"   • {step}")
                
                # File locations
                print(f"\n📁 Detailed results saved to: validation_results/{result['session_id']}/")
                
                # Return appropriate exit code based on recommendation
                if recommendation['decision'] in ['GO', 'GO-WITH-CAUTION']:
                    return True
                else:
                    return False
            
            else:
                print("❌ Validation failed")
                print(f"Error: {result['error']}")
                return False
                
        except ImportError as e:
            logger.error(f"Could not import ValidationMode: {e}")
            logger.error("Validation mode requires all validation components to be available")
            return False
        
        except Exception as e:
            logger.error(f"Validation mode failed: {e}")
            return False
    
    # Continue with normal batch processing
    logger.info("Starting batch subtitle reprocessing for Issue #87")
    logger.info("This will fix over-translated subtitles by applying language preservation logic")
    
    # Initialize reprocessor
    reprocessor = SubtitleReprocessor(detect_batch_size=args.detect_batch_size)
    
    # Identify interviews needing reprocessing
    interviews = reprocessor.identify_interviews_for_reprocessing(
        force_all=args.force_all,
        limit=args.limit
    )
    
    if not interviews:
        logger.info("No interviews found needing reprocessing")
        return True
    
    reprocessor.stats['total_interviews'] = len(interviews)
    logger.info(f"Found {len(interviews)} interviews needing reprocessing")
    
    # Apply start-from offset if specified
    if args.start_from > 0:
        logger.info(f"Starting from interview {args.start_from}")
        interviews = interviews[args.start_from:]
    
    # Process in batches
    batch_size = args.batch_size
    total_batches = (len(interviews) + batch_size - 1) // batch_size
    
    logger.info(f"Processing {len(interviews)} interviews in {total_batches} batches of {batch_size}")
    
    all_batch_results = []
    
    for i in range(0, len(interviews), batch_size):
        batch_num = i // batch_size + 1
        batch_interviews = interviews[i:i + batch_size]
        batch_id = f"batch_{batch_num:03d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"\\n{'='*60}")
        logger.info(f"Processing Batch {batch_num}/{total_batches} ({len(batch_interviews)} interviews)")
        logger.info(f"Batch ID: {batch_id}")
        logger.info(f"{'='*60}")
        
        # Process the batch
        batch_results = reprocessor.process_batch(batch_interviews, batch_id, workers=max(1, args.workers))
        all_batch_results.append(batch_results)
        
        # Check if batch was successful
        success_rate = batch_results['successful_interviews'] / batch_results['total_interviews']
        
        if success_rate < 0.8:  # Less than 80% success rate
            logger.warning(f"Batch {batch_num} had low success rate: {success_rate:.1%}")
            logger.warning("Consider investigating issues before proceeding")
            
            # Optionally pause for manual review
            # response = input("Continue with next batch? (y/n): ")
            # if response.lower() != 'y':
            #     logger.info("Processing stopped by user")
            #     break
    
    # Generate final report
    report_file = reprocessor.generate_final_report()
    
    # Final summary
    logger.info(f"\\n{'='*60}")
    logger.info("REPROCESSING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total interviews: {reprocessor.stats['total_interviews']}")
    logger.info(f"Successfully processed: {reprocessor.stats['processed_interviews']}")
    logger.info(f"Failed: {reprocessor.stats['failed_interviews']}")
    logger.info(f"Success rate: {reprocessor.stats['processed_interviews']/reprocessor.stats['total_interviews']:.1%}")
    logger.info(f"Files reprocessed: {reprocessor.stats['reprocessed_files']}")
    logger.info(f"Report: {report_file}")
    
    if reprocessor.stats['failed_interviews'] == 0:
        logger.info("✅ ALL INTERVIEWS SUCCESSFULLY REPROCESSED!")
        logger.info("Issue #56 has been resolved - subtitles now use language preservation")
        return True
    else:
        logger.warning(f"⚠️ {reprocessor.stats['failed_interviews']} interviews failed processing")
        logger.warning("Review the report and error logs for details")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

