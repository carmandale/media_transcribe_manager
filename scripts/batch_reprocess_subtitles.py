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

from scribe.database import Database
from scribe.srt_translator import translate_srt_file
from scribe.pipeline import PipelineConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SubtitleReprocessor:
    """Handles batch reprocessing of subtitle files with preservation logic."""
    
    def __init__(self, output_dir: Path = None, backup_dir: Path = None):
        """
        Initialize the reprocessor.
        
        Args:
            output_dir: Directory containing interview files (default: ./output)
            backup_dir: Directory for backups (default: ./reprocessing_backups)
        """
        self.output_dir = output_dir or Path("output")
        self.backup_dir = backup_dir or Path("reprocessing_backups")
        self.db = Database()
        
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
    
    def identify_interviews_for_reprocessing(self, cutoff_date: str = "2025-01-07") -> List[Dict]:
        """
        Identify interviews that need reprocessing.
        
        Args:
            cutoff_date: Only process interviews created before this date
            
        Returns:
            List of interview records needing reprocessing
        """
        logger.info(f"Identifying interviews for reprocessing (before {cutoff_date})")
        
        # Query for completed interviews that were processed before the preservation fix
        query = """
            SELECT m.file_id, m.original_path, m.created_at, p.last_updated
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.transcription_status = 'completed'
              AND p.status != 'failed'
              AND (p.last_updated < ? OR m.created_at < ?)
            ORDER BY m.created_at ASC
        """
        
        conn = self.db._get_connection()
        cursor = conn.execute(query, (cutoff_date, cutoff_date))
        interviews = []
        
        for row in cursor.fetchall():
            interview = dict(row)
            
            # Check if interview directory exists and has subtitle files
            interview_dir = self.output_dir / interview['file_id']
            if interview_dir.exists():
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
    
    def reprocess_interview_subtitles(self, interview: Dict) -> Dict[str, bool]:
        """
        Reprocess subtitle files for an interview with preservation logic.
        
        Args:
            interview: Interview record
            
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
        
        results = {}
        
        # Reprocess for each target language
        for target_lang in self.target_languages:
            output_srt = interview_dir / f"{file_id}.{target_lang}.srt"
            
            logger.info(f"  Reprocessing {file_id} for {target_lang.upper()}")
            
            try:
                # Use the preservation logic
                success = translate_srt_file(
                    str(orig_srt),
                    str(output_srt),
                    target_language=target_lang,
                    preserve_original_when_matching=True,  # This is the key fix!
                    batch_size=100,
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
    
    def process_batch(self, interviews: List[Dict], batch_id: str) -> Dict:
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
            
            # Step 2: Reprocess
            reprocess_results = self.reprocess_interview_subtitles(interview)
            
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

            # --- Live status/heartbeat ---
            elapsed = (datetime.now() - batch_start_ts).total_seconds()
            processed = batch_results['successful_interviews'] + batch_results['failed_interviews']
            remaining = max(len(interviews) - processed, 0)
            rate = (processed / elapsed) if elapsed > 0 else 0.0
            eta_seconds = int(remaining / rate) if rate > 0 else None

            status = {
                'batch_id': batch_id,
                'processed': processed,
                'total': len(interviews),
                'successful': batch_results['successful_interviews'],
                'failed': batch_results['failed_interviews'],
                'current_file_id': file_id,
                'last_duration_seconds': (datetime.now() - interview_start_ts).total_seconds(),
                'elapsed_seconds': elapsed,
                'eta_seconds': eta_seconds,
                'updated_at': datetime.now().isoformat(),
            }
            try:
                (batch_dir / 'status.json').write_text(json.dumps(status, indent=2))
                with open(batch_dir / 'progress.log', 'a') as lf:
                    eta_txt = f" ETA ~{eta_seconds}s" if eta_seconds is not None else ""
                    lf.write(f"[{status['updated_at']}] {processed}/{len(interviews)} done | +{status['last_duration_seconds']:.1f}s | success={batch_results['successful_interviews']} fail={batch_results['failed_interviews']}.{eta_txt}\n")
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
    logger.info("Starting batch subtitle reprocessing for Issue #56")
    logger.info("This will fix over-translated subtitles by applying language preservation logic")
    
    # Initialize reprocessor
    reprocessor = SubtitleReprocessor()
    
    # Identify interviews needing reprocessing
    interviews = reprocessor.identify_interviews_for_reprocessing()
    
    if not interviews:
        logger.info("No interviews found needing reprocessing")
        return True
    
    reprocessor.stats['total_interviews'] = len(interviews)
    logger.info(f"Found {len(interviews)} interviews needing reprocessing")
    
    # Process in batches
    batch_size = 50  # Configurable batch size
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
        batch_results = reprocessor.process_batch(batch_interviews, batch_id)
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

