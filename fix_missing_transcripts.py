#!/usr/bin/env python3
"""
Fix Missing Transcripts

This script identifies files that have a 'completed' transcription status 
but missing transcript files. It:
1. Identifies files with "transcript not found" errors
2. Checks if transcription is marked completed but file is missing
3. Resets transcription status so they can be processed again

Usage:
    python fix_missing_transcripts.py [--reset]

Options:
    --reset    Reset transcription status for files with missing transcripts
"""

import os
import sys
import logging
import argparse
from db_manager import DatabaseManager
from file_manager import FileManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Fix missing transcript files")
    parser.add_argument("--reset", action="store_true", help="Reset transcription status for files with missing transcripts")
    args = parser.parse_args()
    
    # Basic configuration
    config = {'output_directory': './output'}
    db = DatabaseManager('media_tracking.db')
    file_manager = FileManager(db, config)
    
    # Step 1: Find files with "transcript not found" errors
    logger.info("Finding files with 'Transcript text not found' errors")
    query = """
    SELECT DISTINCT file_id
    FROM errors
    WHERE error_message = 'Transcript text not found'
    """
    problem_files = db.execute_query(query)
    logger.info(f"Found {len(problem_files)} files with transcript not found errors")
    
    # Step 2: Check each file's transcription status and file existence
    files_to_reset = []
    for file_record in problem_files:
        file_id = file_record['file_id']
        
        # Get file status from database
        file_status = db.get_file_status(file_id)
        if not file_status:
            logger.warning(f"File {file_id} not found in database, skipping")
            continue
        
        # Get transcript path
        transcript_path = file_manager.get_transcript_path(file_id)
        
        # Check if transcript status is completed but file is missing
        if (file_status['transcription_status'] == 'completed' and
            not os.path.exists(transcript_path)):
            
            files_to_reset.append({
                'file_id': file_id,
                'status': file_status['status'],
                'transcription_status': file_status['transcription_status'],
                'transcript_path': transcript_path,
                'file_exists': os.path.exists(transcript_path)
            })
            
            logger.info(f"File {file_id} has status 'completed' but transcript file is missing")
    
    logger.info(f"Found {len(files_to_reset)} files with completed status but missing transcript files")
    
    # Step 3: Reset transcription status if requested
    if args.reset and files_to_reset:
        logger.info("Resetting transcription status for files with missing transcripts")
        reset_count = 0
        
        for file in files_to_reset:
            file_id = file['file_id']
            
            # Check if audio file exists
            audio_path = file_manager.get_audio_path(file_id)
            if not audio_path or not os.path.exists(audio_path):
                logger.warning(f"Audio file not found for {file_id}, skipping reset")
                continue
            
            # Reset to not_started status
            db.update_status(
                file_id=file_id,
                status='pending',
                transcription_status='not_started',
                translation_en_status='not_started',
                translation_de_status='not_started',
                translation_he_status='not_started'
            )
            
            logger.info(f"Reset transcription status for file {file_id}")
            reset_count += 1
        
        logger.info(f"Reset {reset_count} files for retranscription")
    elif not args.reset:
        logger.info("Dry run completed. Use --reset to actually reset the file statuses.")
    else:
        logger.info("No files to reset")

if __name__ == "__main__":
    main()