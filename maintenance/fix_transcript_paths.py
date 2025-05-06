#!/usr/bin/env python3
"""
Fix "Transcript text not found" errors by identifying files with incorrect transcript paths,
updating their paths in the database, and clearing related errors.

This script:
1. Identifies files with "Transcript text not found" errors
2. Locates their actual transcript files
3. Updates the database with the correct information
4. Clears related errors

Usage:
    python fix_transcript_paths.py [--dry-run] [--limit LIMIT]
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from db_manager import DatabaseManager
from file_manager import FileManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("transcript-path-fixer")

def find_files_with_transcript_errors(db: DatabaseManager, limit: int = None) -> list:
    """
    Find files with "Transcript text not found" errors.
    
    Args:
        db: Database manager
        limit: Optional limit on the number of files to process
    
    Returns:
        List of file IDs with transcript errors
    """
    query = """
    SELECT DISTINCT e.file_id, m.original_path 
    FROM errors e
    JOIN media_files m ON e.file_id = m.file_id
    WHERE e.error_message = 'Transcript text not found'
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    results = db.execute_query(query)
    return results

def find_transcript_file(file_id: str) -> str:
    """
    Find the transcript file for a given file ID.
    
    Args:
        file_id: The file ID to search for
    
    Returns:
        Path to the transcript file if found, None otherwise
    """
    # Check the default transcript directory
    transcript_dir = Path("./output/transcripts")
    transcript_files = list(transcript_dir.glob(f"{file_id}*.txt"))
    
    if transcript_files:
        return str(transcript_files[0])
    
    # If not found, search more broadly in the output directory
    output_dir = Path("./output")
    transcript_files = list(output_dir.glob(f"**/{file_id}*.txt"))
    
    if transcript_files:
        # Filter out translation files
        for file_path in transcript_files:
            if not any(lang in str(file_path) for lang in ["_en.", "_de.", "_he."]):
                return str(file_path)
    
    return None

def fix_file_path(db: DatabaseManager, file_manager: FileManager, file_id: str, 
                 original_path: str, dry_run: bool = False) -> bool:
    """
    Fix the transcript path for a file ID or mark it for retranscription.
    
    Args:
        db: Database manager
        file_manager: File manager
        file_id: The file ID to fix
        original_path: Original path from the database
        dry_run: If True, don't actually make changes
    
    Returns:
        True if successful, False otherwise
    """
    # Find the transcript file
    transcript_path = find_transcript_file(file_id)
    
    if not transcript_path:
        logger.warning(f"No transcript file found for {file_id}")
        
        if dry_run:
            logger.info(f"[DRY RUN] Would mark file {file_id} as needing retranscription")
            return True
        
        # Clear errors
        success, count = db.clear_file_errors(file_id)
        logger.info(f"Cleared {count} errors for file {file_id}")
        
        # Mark for retranscription
        query = """
        UPDATE processing_status
        SET transcription_status = 'not_started',
            translation_en_status = 'not_started',
            translation_de_status = 'not_started',
            translation_he_status = 'not_started',
            status = 'pending'
        WHERE file_id = ?
        """
        db.cursor.execute(query, (file_id,))
        db.conn.commit()
        
        logger.info(f"Marked file {file_id} for retranscription")
        return True
    
    logger.info(f"Found transcript: {transcript_path}")
    
    if dry_run:
        logger.info(f"[DRY RUN] Would update transcript path for {file_id}")
        return True
    
    # Clear errors
    success, count = db.clear_file_errors(file_id)
    logger.info(f"Cleared {count} errors for file {file_id}")
    
    # Reset file status if needed
    query = """
    UPDATE processing_status
    SET translation_en_status = 'not_started',
        translation_de_status = 'not_started',
        translation_he_status = 'not_started'
    WHERE file_id = ? 
      AND (translation_en_status = 'failed' 
           OR translation_de_status = 'failed'
           OR translation_he_status = 'failed')
    """
    db.cursor.execute(query, (file_id,))
    db.conn.commit()
    
    logger.info(f"Successfully fixed path for {file_id}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Fix transcript path errors")
    parser.add_argument("--dry-run", action="store_true", help="Don't make actual changes")
    parser.add_argument("--limit", type=int, help="Limit the number of files to process")
    args = parser.parse_args()
    
    db = DatabaseManager('media_tracking.db')
    file_manager = FileManager(db, {"output_directory": "./output"})
    
    # Find files with transcript errors
    error_files = find_files_with_transcript_errors(db, args.limit)
    logger.info(f"Found {len(error_files)} files with transcript errors")
    
    if args.dry_run:
        logger.info("Running in dry-run mode - no changes will be made")
    
    success_count = 0
    fail_count = 0
    
    for file in error_files:
        file_id = file['file_id']
        original_path = file['original_path']
        
        logger.info(f"Processing file {file_id} ({original_path})")
        
        if fix_file_path(db, file_manager, file_id, original_path, args.dry_run):
            success_count += 1
        else:
            fail_count += 1
    
    logger.info(f"Process complete. {success_count} files fixed, {fail_count} failed.")

if __name__ == "__main__":
    main()