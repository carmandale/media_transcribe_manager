#!/usr/bin/env python3
"""
Find All Missing Transcripts

This script finds all files in the database that have a 'completed' transcription status
but the transcript file doesn't actually exist on disk.

Usage:
    python find_all_missing_transcripts.py [--reset]

Options:
    --reset    Reset transcription status for all files with missing transcripts
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
    parser = argparse.ArgumentParser(description="Find all files with missing transcripts")
    parser.add_argument("--reset", action="store_true", help="Reset transcription status for files with missing transcripts")
    args = parser.parse_args()
    
    # Basic configuration
    config = {'output_directory': './output'}
    db = DatabaseManager('media_tracking.db')
    file_manager = FileManager(db, config)
    
    # Find all files with 'completed' transcription status
    logger.info("Finding all files with 'completed' transcription status")
    query = """
    SELECT file_id 
    FROM processing_status 
    WHERE transcription_status = 'completed'
    """
    completed_files = db.execute_query(query)
    logger.info(f"Found {len(completed_files)} files with 'completed' transcription status")
    
    # Check which ones are missing transcript files
    files_to_reset = []
    for file_record in completed_files:
        file_id = file_record['file_id']
        
        transcript_path = file_manager.get_transcript_path(file_id)
        
        # Check if transcript file exists
        if not os.path.exists(transcript_path):
            files_to_reset.append({
                'file_id': file_id,
                'transcript_path': transcript_path
            })
    
    logger.info(f"Found {len(files_to_reset)} files with missing transcript files")
    
    # Print details of missing files
    for i, file in enumerate(files_to_reset[:10], 1):  # Show first 10 files
        logger.info(f"{i}. File ID: {file['file_id']}")
        logger.info(f"   Missing transcript: {file['transcript_path']}")
    
    if len(files_to_reset) > 10:
        logger.info(f"... and {len(files_to_reset) - 10} more files")
    
    # Reset transcription status if requested
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
            
            reset_count += 1
            
            # Log progress every 10 files
            if reset_count % 10 == 0:
                logger.info(f"Reset {reset_count}/{len(files_to_reset)} files")
        
        logger.info(f"Reset {reset_count} files for retranscription")
    elif not args.reset and files_to_reset:
        logger.info("Dry run completed. Use --reset to actually reset the file statuses.")

if __name__ == "__main__":
    main()