#!/usr/bin/env python3
"""
Database Maintenance Module
---------------------------
Handles database maintenance operations including:
- Fixing stalled file statuses
- Correcting problematic file paths
- Marking consistently failing files
- Verifying database consistency with filesystem
- Fixing Hebrew translations with placeholder text

This module consolidates functionality from:
- fix_stalled_files.py
- fix_path_issues.py
- fix_problem_translations.py
- fix_transcript_status.py
- fix_missing_transcripts.py
"""

import os
import sys
import time
import logging
import argparse
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from pathlib import Path
import sqlite3
import unicodedata
import json
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('db_maintenance.log')
    ]
)

logger = logging.getLogger(__name__)

# Import local modules
from db_manager import DatabaseManager
from file_manager import FileManager
try:
    from translation import TranslationManager
    TRANSLATION_AVAILABLE = True
except ImportError:
    logger.warning("TranslationManager not available. Hebrew translation fixes disabled.")
    TRANSLATION_AVAILABLE = False


class DatabaseMaintenance:
    """
    Database maintenance operations for the media tracking database.
    """
    
    def __init__(self, db_path: str = 'media_tracking.db'):
        """
        Initialize the database maintenance class.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
        # Default configuration
        self.config = {
            'output_directory': './output',
            'stalled_timeout_minutes': 30,
            'elevenlabs': {
                'api_key': os.getenv('ELEVENLABS_API_KEY'),
                'model': 'scribe_v1'
            },
            'translation': {
                'max_retries': 3,
                'openai_model': 'gpt-4o'
            }
        }
        
        # Initialize file manager for path operations
        self.file_manager = FileManager(self.db_manager, self.config)

    def fix_stalled_files(self, timeout_minutes: int = None, 
                         reset_all: bool = False) -> int:
        """
        Reset status of files stuck in 'in-progress' state.
        
        Args:
            timeout_minutes: Minutes after which to consider a process stalled
            reset_all: If True, reset all in-progress files regardless of time
            
        Returns:
            Number of files fixed
        """
        if timeout_minutes is None:
            timeout_minutes = self.config.get('stalled_timeout_minutes', 30)
            
        logger.info(f"Identifying stalled files (timeout: {timeout_minutes} minutes)...")
        
        # Calculate the cutoff timestamp
        current_time = int(time.time())
        cutoff_time = current_time - (timeout_minutes * 60)
        
        # Prepare query conditions
        conditions = []
        params = []
        
        # Add status conditions
        status_conditions = [
            "status = 'in-progress'",
            "transcription_status = 'in-progress'",
            "translation_en_status = 'in-progress'",
            "translation_de_status = 'in-progress'",
            "translation_he_status = 'in-progress'"
        ]
        conditions.append(f"({' OR '.join(status_conditions)})")
        
        # Add timestamp condition if not resetting all
        if not reset_all:
            conditions.append("last_updated < ?")
            params.append(cutoff_time)
            
        # Build the final query
        query = f"""
        SELECT * FROM processing_status 
        WHERE {' AND '.join(conditions)}
        """
        
        # Execute query to find stalled files
        stalled_files = self.db_manager.execute_query(query, params)
        
        if not stalled_files:
            logger.info("No stalled files found.")
            return 0
            
        logger.info(f"Found {len(stalled_files)} stalled files")
        
        # Track fixed count
        fixed_count = 0
        
        # Begin transaction for batch updates
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        try:
            for file in stalled_files:
                file_id = file['file_id']
                needs_update = False
                updates = []
                
                # Check each status field
                if file['status'] == 'in-progress':
                    updates.append("status = 'not_started'")
                    needs_update = True
                    
                if file['transcription_status'] == 'in-progress':
                    # Check if transcript file exists
                    transcript_path = Path(self.file_manager.get_transcript_path(file_id))
                    if transcript_path.exists() and transcript_path.stat().st_size > 0:
                        updates.append("transcription_status = 'completed'")
                    else:
                        updates.append("transcription_status = 'failed'")
                    needs_update = True
                    
                # Check translation statuses
                for lang in ['en', 'de', 'he']:
                    status_field = f"translation_{lang}_status"
                    if file[status_field] == 'in-progress':
                        # Check if translation file exists
                        translation_path = Path(self.file_manager.get_translation_path(file_id, lang))
                        if translation_path.exists() and translation_path.stat().st_size > 0:
                            updates.append(f"{status_field} = 'completed'")
                        else:
                            updates.append(f"{status_field} = 'failed'")
                        needs_update = True
                
                if needs_update and updates:
                    # Execute update with all field changes
                    update_query = f"""
                    UPDATE processing_status 
                    SET {', '.join(updates)}, last_updated = ?
                    WHERE file_id = ?
                    """
                    cursor.execute(update_query, (current_time, file_id))
                    fixed_count += 1
                    logger.info(f"Reset status for file {file_id}")
                    
            # Commit all changes
            conn.commit()
            logger.info(f"Fixed {fixed_count} stalled files")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error fixing stalled files: {e}")
            raise
        finally:
            conn.close()
            
        return fixed_count

    def fix_path_issues(self, path_mapping: Optional[Dict[str, str]] = None, 
                       verify: bool = True) -> int:
        """
        Fix incorrect file paths in the database.
        
        Args:
            path_mapping: Dictionary mapping file_ids to correct paths
            verify: Whether to verify file existence after correction
            
        Returns:
            Number of paths fixed
        """
        # If no mapping provided, use known pattern fixes
        if not path_mapping:
            # Check for common path issues in the database
            query = """
            SELECT file_id, file_path FROM processing_status
            WHERE file_path LIKE '%\\%%' OR file_path LIKE '%[%' OR file_path LIKE '%]%'
            OR file_path LIKE '%(%' OR file_path LIKE '%)%'
            """
            problematic_files = self.db_manager.execute_query(query)
            
            if not problematic_files:
                logger.info("No files with path issues found")
                return 0
            
            logger.info(f"Found {len(problematic_files)} files with potential path issues")
            
            # Create path mapping
            path_mapping = {}
            for file in problematic_files:
                file_id = file['file_id']
                old_path = file['file_path']
                
                # Clean up problematic characters
                new_path = old_path
                new_path = new_path.replace('%20', ' ')  # URL encoding
                new_path = new_path.replace('\\', '/')   # Normalize slashes
                
                # Normalize unicode characters
                new_path = unicodedata.normalize('NFC', new_path)
                
                # Only add to mapping if path changed
                if new_path != old_path:
                    path_mapping[file_id] = new_path
        
        # Return early if no paths to fix
        if not path_mapping:
            logger.info("No path corrections needed")
            return 0
            
        logger.info(f"Will update {len(path_mapping)} file paths")
        
        # Begin transaction for batch updates
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        fixed_count = 0
        
        try:
            for file_id, new_path in path_mapping.items():
                # If verification is enabled, check if the file exists at the new path
                if verify:
                    new_path_obj = Path(new_path)
                    if not new_path_obj.exists():
                        logger.warning(f"New path does not exist, skipping: {new_path}")
                        continue
                
                # Update the path in the database
                update_query = """
                UPDATE processing_status 
                SET file_path = ?, last_updated = ?
                WHERE file_id = ?
                """
                current_time = int(time.time())
                cursor.execute(update_query, (new_path, current_time, file_id))
                fixed_count += 1
                logger.info(f"Updated path for file {file_id}")
            
            # Commit all changes
            conn.commit()
            logger.info(f"Fixed {fixed_count} file paths")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error fixing file paths: {e}")
            raise
        finally:
            conn.close()
            
        return fixed_count

    def fix_missing_transcripts(self, reset_to_failed: bool = True, 
                               batch_size: int = 20) -> int:
        """
        Fix files with missing transcript files.
        
        Args:
            reset_to_failed: Reset transcription status to 'failed' if True
            batch_size: Process in batches of this size
            
        Returns:
            Number of files fixed
        """
        # Find files marked as completed but missing transcript files
        query = """
        SELECT * FROM processing_status 
        WHERE transcription_status = 'completed'
        """
        
        completed_files = self.db_manager.execute_query(query)
        
        if not completed_files:
            logger.info("No files with completed transcription status found.")
            return 0
            
        logger.info(f"Checking {len(completed_files)} files with completed transcription status")
        
        # Files with missing transcripts
        missing_transcripts = []
        
        # Check existence of transcript files
        for file in completed_files:
            file_id = file['file_id']
            transcript_path = Path(self.file_manager.get_transcript_path(file_id))
            
            if not transcript_path.exists() or transcript_path.stat().st_size == 0:
                missing_transcripts.append(file_id)
                logger.info(f"Missing transcript: {file_id} (path: {transcript_path})")
        
        if not missing_transcripts:
            logger.info("No files with missing transcripts found.")
            return 0
            
        logger.info(f"Found {len(missing_transcripts)} files with missing transcripts")
        
        # Return if we don't want to reset status
        if not reset_to_failed:
            return len(missing_transcripts)
            
        # Process in batches
        fixed_count = 0
        total_batches = (len(missing_transcripts) + batch_size - 1) // batch_size
        
        for i in range(total_batches):
            batch = missing_transcripts[i * batch_size:(i + 1) * batch_size]
            
            # Skip empty batches
            if not batch:
                continue
                
            # Begin transaction for batch updates
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            try:
                for file_id in batch:
                    update_query = """
                    UPDATE processing_status 
                    SET transcription_status = 'failed', status = 'failed', last_updated = ?
                    WHERE file_id = ?
                    """
                    current_time = int(time.time())
                    cursor.execute(update_query, (current_time, file_id))
                    fixed_count += 1
                    
                    # Also reset translation statuses since they depend on transcription
                    update_trans_query = """
                    UPDATE processing_status 
                    SET translation_en_status = 'not_started', 
                        translation_de_status = 'not_started',
                        translation_he_status = 'not_started'
                    WHERE file_id = ?
                    """
                    cursor.execute(update_trans_query, (file_id,))
                
                # Commit batch
                conn.commit()
                logger.info(f"Fixed batch {i+1}/{total_batches} ({len(batch)} files)")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error fixing batch {i+1}: {e}")
            finally:
                conn.close()
                
        logger.info(f"Fixed {fixed_count} files with missing transcripts")
        return fixed_count

    def mark_problem_files(self, file_ids: Optional[List[str]] = None, 
                          status: str = 'qa_failed', reason: str = '') -> int:
        """
        Mark problematic files with special status.
        
        Args:
            file_ids: List of file IDs to mark (if None, load from problem file)
            status: Status to set (default: 'qa_failed')
            reason: Reason for marking as problem
            
        Returns:
            Number of files marked
        """
        # If file_ids not provided, try to load from problematic_translations.json
        if not file_ids:
            problem_file = Path('problematic_translations.json')
            if problem_file.exists():
                try:
                    with open(problem_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        file_ids = data.get('file_ids', [])
                except Exception as e:
                    logger.error(f"Error loading problem file list: {e}")
                    return 0
            else:
                logger.warning("No file IDs provided and problem file not found")
                return 0
        
        if not file_ids:
            logger.info("No problem files to mark")
            return 0
            
        logger.info(f"Marking {len(file_ids)} files as '{status}'")
        
        # Begin transaction for batch updates
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        marked_count = 0
        current_time = int(time.time())
        
        try:
            for file_id in file_ids:
                # Mark the file with special status
                update_query = """
                UPDATE processing_status 
                SET status = ?, last_updated = ?
                WHERE file_id = ?
                """
                cursor.execute(update_query, (status, current_time, file_id))
                
                # Log the reason if provided
                if reason:
                    error_query = """
                    INSERT INTO error_log 
                    (file_id, process_stage, error_message, error_details, timestamp)
                    VALUES (?, 'qa', ?, ?, ?)
                    """
                    cursor.execute(error_query, 
                                  (file_id, f"Marked as {status}", reason, current_time))
                
                marked_count += 1
            
            # Commit all changes
            conn.commit()
            logger.info(f"Marked {marked_count} files as '{status}'")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error marking problem files: {e}")
            raise
        finally:
            conn.close()
            
        return marked_count

    def verify_consistency(self, auto_fix: bool = False, 
                          report_only: bool = False) -> Dict[str, int]:
        """
        Verify consistency between database and file system.
        
        Args:
            auto_fix: Automatically fix inconsistencies if True
            report_only: Only report issues, don't make changes
            
        Returns:
            Dictionary with counts of different inconsistency types
        """
        logger.info("Verifying database and filesystem consistency...")
        
        # Get all files from database with their file paths
        all_files = self.db_manager.execute_query("""
            SELECT m.*, p.* 
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
        """)
        
        # Statistics
        stats = {
            'total_files': len(all_files),
            'missing_source': 0,
            'missing_transcript': 0,
            'missing_translation_en': 0,
            'missing_translation_de': 0,
            'missing_translation_he': 0,
            'status_mismatch': 0,
            'fixed': 0
        }
        
        # Files needing fixes
        fixes = []
        
        # Check each file
        for file in all_files:
            file_id = file['file_id']
            inconsistencies = []
            
            # 1. Check source file existence
            source_path = Path(file['original_path'])
            if not source_path.exists():
                stats['missing_source'] += 1
                inconsistencies.append('missing_source')
            
            # 2. Check transcript if marked completed
            if file['transcription_status'] == 'completed':
                transcript_path = Path(self.file_manager.get_transcript_path(file_id))
                if not transcript_path.exists() or transcript_path.stat().st_size == 0:
                    stats['missing_transcript'] += 1
                    inconsistencies.append('missing_transcript')
            
            # 3. Check translations if marked completed
            for lang in ['en', 'de', 'he']:
                status_field = f"translation_{lang}_status"
                if file[status_field] == 'completed':
                    translation_path = Path(self.file_manager.get_translation_path(file_id, lang))
                    if not translation_path.exists() or translation_path.stat().st_size == 0:
                        stats[f'missing_translation_{lang}'] += 1
                        inconsistencies.append(f'missing_translation_{lang}')
            
            # Add to fix list if needed
            if inconsistencies:
                fixes.append({
                    'file_id': file_id,
                    'inconsistencies': inconsistencies
                })
                stats['status_mismatch'] += 1
        
        # Log summary
        logger.info(f"Consistency verification complete")
        logger.info(f"Total files: {stats['total_files']}")
        logger.info(f"Files with missing source: {stats['missing_source']}")
        logger.info(f"Files with missing transcript: {stats['missing_transcript']}")
        logger.info(f"Files with missing EN translation: {stats['missing_translation_en']}")
        logger.info(f"Files with missing DE translation: {stats['missing_translation_de']}")
        logger.info(f"Files with missing HE translation: {stats['missing_translation_he']}")
        logger.info(f"Total files with inconsistencies: {stats['status_mismatch']}")
        
        # Stop if only reporting
        if report_only or not auto_fix:
            return stats
            
        # Fix inconsistencies
        if fixes:
            logger.info(f"Fixing {len(fixes)} files with inconsistencies")
            
            # Begin transaction for batch updates
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            try:
                for fix in fixes:
                    file_id = fix['file_id']
                    updates = []
                    
                    for issue in fix['inconsistencies']:
                        if issue == 'missing_source':
                            # Just log this, we can't fix missing source files
                            continue
                            
                        elif issue == 'missing_transcript':
                            updates.append("transcription_status = 'failed'")
                            updates.append("status = 'failed'")
                            
                        elif issue.startswith('missing_translation_'):
                            lang = issue.split('_')[-1]
                            updates.append(f"translation_{lang}_status = 'failed'")
                    
                    if updates:
                        # Execute update with all field changes
                        update_query = f"""
                        UPDATE processing_status 
                        SET {', '.join(updates)}, last_updated = ?
                        WHERE file_id = ?
                        """
                        current_time = int(time.time())
                        cursor.execute(update_query, (current_time, file_id))
                        stats['fixed'] += 1
                
                # Commit all changes
                conn.commit()
                logger.info(f"Fixed {stats['fixed']} files with inconsistencies")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error fixing inconsistencies: {e}")
            finally:
                conn.close()
        
        return stats

    def fix_hebrew_translations(self, batch_size: int = 20, 
                               language_model: str = 'gpt-4o') -> int:
        """
        Fix Hebrew translations with placeholder text.
        
        Args:
            batch_size: Process in batches of this size
            language_model: OpenAI model to use for translation
            
        Returns:
            Number of files fixed
        """
        if not TRANSLATION_AVAILABLE:
            logger.error("TranslationManager not available. Cannot fix Hebrew translations.")
            return 0
            
        # Find files with placeholder Hebrew translations
        query = """
        SELECT * FROM processing_status 
        WHERE translation_he_status = 'completed'
        """
        
        completed_files = self.db_manager.execute_query(query)
        
        if not completed_files:
            logger.info("No files with completed Hebrew translation status found.")
            return 0
            
        logger.info(f"Checking {len(completed_files)} files with completed Hebrew translations")
        
        # Files with placeholder translations
        placeholder_files = []
        
        # Check for placeholder text in Hebrew translations
        for file in completed_files:
            file_id = file['file_id']
            he_path = Path(self.file_manager.get_translation_path(file_id, 'he'))
            
            if not he_path.exists():
                continue
                
            try:
                with open(he_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "[HEBREW TRANSLATION]" in content:
                        placeholder_files.append(file_id)
                        logger.info(f"Found placeholder translation: {file_id}")
            except Exception as e:
                logger.error(f"Error reading Hebrew translation for {file_id}: {e}")
        
        if not placeholder_files:
            logger.info("No files with placeholder Hebrew translations found.")
            return 0
            
        logger.info(f"Found {len(placeholder_files)} files with placeholder Hebrew translations")
        
        # Initialize translation manager if needed
        from translation import TranslationManager
        translation_config = {
            'api_keys': {
                'openai': os.getenv('OPENAI_API_KEY')
            },
            'translation': {
                'model': language_model
            }
        }
        translation_manager = TranslationManager(self.db_manager, translation_config)
        translation_manager.set_file_manager(self.file_manager)
        
        # Process in batches
        fixed_count = 0
        total_batches = (len(placeholder_files) + batch_size - 1) // batch_size
        
        for i in range(total_batches):
            batch = placeholder_files[i * batch_size:(i + 1) * batch_size]
            
            # Skip empty batches
            if not batch:
                continue
                
            logger.info(f"Processing batch {i+1}/{total_batches} ({len(batch)} files)")
            
            for file_id in batch:
                # Get source transcript
                transcript_text = None
                transcript_path = Path(self.file_manager.get_transcript_path(file_id))
                
                if transcript_path.exists():
                    try:
                        with open(transcript_path, 'r', encoding='utf-8') as f:
                            transcript_text = f.read()
                    except Exception as e:
                        logger.error(f"Error reading transcript for {file_id}: {e}")
                        continue
                
                if not transcript_text:
                    logger.error(f"No transcript found for {file_id}")
                    continue
                
                # Translate to Hebrew
                try:
                    # Mark as in-progress
                    self.db_manager.update_status(
                        file_id=file_id,
                        translation_he_status='in-progress'
                    )
                    
                    # Perform translation
                    success = translation_manager.translate_text(
                        file_id=file_id,
                        text=transcript_text,
                        source_language='auto',  # Auto-detect
                        target_language='he',
                        force_reprocess=True
                    )
                    
                    if success:
                        fixed_count += 1
                        logger.info(f"Successfully fixed Hebrew translation for {file_id}")
                    else:
                        logger.error(f"Failed to fix Hebrew translation for {file_id}")
                        # Reset to completed but with placeholder
                        self.db_manager.update_status(
                            file_id=file_id,
                            translation_he_status='completed'
                        )
                except Exception as e:
                    logger.error(f"Error translating Hebrew for {file_id}: {e}")
                    # Reset to completed but with placeholder
                    self.db_manager.update_status(
                        file_id=file_id,
                        translation_he_status='completed'
                    )
                
                # Brief pause to avoid API rate limits
                time.sleep(1)
            
            logger.info(f"Completed batch {i+1}/{total_batches}")
        
        logger.info(f"Fixed {fixed_count} Hebrew translations")
        return fixed_count


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Database maintenance utilities")
    
    # General options
    parser.add_argument('--db-path', type=str, default='media_tracking.db',
                        help='Path to SQLite database file')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Maintenance command to execute')
    
    # fix-stalled-files command
    stalled_parser = subparsers.add_parser('fix-stalled-files', 
                                          help='Reset status of stalled processing')
    stalled_parser.add_argument('--timeout', type=int, default=30,
                               help='Minutes after which to consider a process stalled')
    stalled_parser.add_argument('--reset-all', action='store_true',
                               help='Reset all in-progress files regardless of time')
    
    # fix-path-issues command
    path_parser = subparsers.add_parser('fix-path-issues', 
                                       help='Fix incorrect file paths')
    path_parser.add_argument('--mapping-file', type=str,
                            help='JSON file with file_id to path mapping')
    path_parser.add_argument('--no-verify', action='store_true',
                            help='Skip verification of file existence')
    
    # fix-missing-transcripts command
    trans_parser = subparsers.add_parser('fix-missing-transcripts', 
                                        help='Fix files with missing transcripts')
    trans_parser.add_argument('--no-reset', action='store_true',
                             help='Do not reset status to failed')
    trans_parser.add_argument('--batch-size', type=int, default=20,
                             help='Process in batches of this size')
    
    # mark-problem-files command
    mark_parser = subparsers.add_parser('mark-problem-files', 
                                       help='Mark problematic files')
    mark_parser.add_argument('--file-ids', type=str,
                            help='Comma-separated list of file IDs to mark')
    mark_parser.add_argument('--status', type=str, default='qa_failed',
                            help='Status to set (default: qa_failed)')
    mark_parser.add_argument('--reason', type=str, default='',
                            help='Reason for marking as problem')
    
    # verify-consistency command
    verify_parser = subparsers.add_parser('verify-consistency', 
                                         help='Verify database and filesystem consistency')
    verify_parser.add_argument('--auto-fix', action='store_true',
                              help='Automatically fix inconsistencies')
    verify_parser.add_argument('--report-only', action='store_true',
                              help='Only report issues, no fixes')
    
    # fix-hebrew-translations command
    hebrew_parser = subparsers.add_parser('fix-hebrew-translations', 
                                         help='Fix Hebrew translations with placeholder text')
    hebrew_parser.add_argument('--batch-size', type=int, default=20,
                              help='Process in batches of this size')
    hebrew_parser.add_argument('--model', type=str, default='gpt-4o',
                              help='OpenAI model to use for translation')
    
    return parser.parse_args()


def main():
    """Main function to run from command line."""
    args = parse_arguments()
    
    # Initialize maintenance class
    db_maintenance = DatabaseMaintenance(args.db_path)
    
    # Execute requested command
    if args.command == 'fix-stalled-files':
        db_maintenance.fix_stalled_files(
            timeout_minutes=args.timeout,
            reset_all=args.reset_all
        )
        
    elif args.command == 'fix-path-issues':
        # Load mapping file if provided
        path_mapping = None
        if args.mapping_file:
            mapping_path = Path(args.mapping_file)
            if mapping_path.exists():
                try:
                    with open(mapping_path, 'r', encoding='utf-8') as f:
                        path_mapping = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading path mapping file: {e}")
                    return 1
        
        db_maintenance.fix_path_issues(
            path_mapping=path_mapping,
            verify=not args.no_verify
        )
        
    elif args.command == 'fix-missing-transcripts':
        db_maintenance.fix_missing_transcripts(
            reset_to_failed=not args.no_reset,
            batch_size=args.batch_size
        )
        
    elif args.command == 'mark-problem-files':
        # Parse file IDs if provided
        file_ids = None
        if args.file_ids:
            file_ids = [fid.strip() for fid in args.file_ids.split(',')]
        
        db_maintenance.mark_problem_files(
            file_ids=file_ids,
            status=args.status,
            reason=args.reason
        )
        
    elif args.command == 'verify-consistency':
        db_maintenance.verify_consistency(
            auto_fix=args.auto_fix,
            report_only=args.report_only
        )
        
    elif args.command == 'fix-hebrew-translations':
        db_maintenance.fix_hebrew_translations(
            batch_size=args.batch_size,
            language_model=args.model
        )
        
    else:
        logger.error("No valid command specified")
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())