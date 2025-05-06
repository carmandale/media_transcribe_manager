#!/usr/bin/env python3
"""
Fix Stalled Files Script

This script identifies and fixes files that are stuck in 'in-progress' state
but don't have the necessary files to proceed with processing.
"""

import os
import sys
import logging
from db_manager import DatabaseManager
from file_manager import FileManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fix_stalled_files.log')
    ]
)

logger = logging.getLogger(__name__)

def fix_transcription_status():
    """
    Find files marked as 'in-progress' for transcription but with no transcript file,
    and mark them as 'failed'.
    """
    db = DatabaseManager('media_tracking.db')
    config = {'output_directory': './output'}
    file_manager = FileManager(db, config)
    
    # Get files with transcription in progress
    files = db.execute_query("""
        SELECT m.file_id, m.safe_filename 
        FROM media_files m 
        JOIN processing_status p ON m.file_id = p.file_id 
        WHERE p.transcription_status = 'in-progress'
    """)
    
    if not files:
        logger.info("No files with transcription in progress")
        return
    
    logger.info(f"Found {len(files)} files with transcription in progress")
    fixed_count = 0
    
    for file in files:
        file_id = file['file_id']
        transcript_path = file_manager.get_transcript_path(file_id)
        
        if not os.path.exists(transcript_path):
            logger.info(f"File {file_id} is marked in-progress but no transcript found at {transcript_path}")
            
            # Update status to failed - using direct cursor approach for UPDATE statements
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE processing_status SET transcription_status = 'failed' WHERE file_id = ?",
                (file_id,)
            )
            conn.commit()
            
            # Log the error
            db.log_error(
                file_id=file_id, 
                process_stage="transcription", 
                error_message="Marked as failed by fix_stalled_files.py", 
                error_details="File was in-progress but no transcript file was found"
            )
            
            fixed_count += 1
    
    logger.info(f"Fixed {fixed_count} stalled transcription files")

def fix_translation_status():
    """
    Find files marked with translation in progress but no actual translation file,
    and mark them as 'failed'.
    """
    db = DatabaseManager('media_tracking.db')
    config = {'output_directory': './output'}
    file_manager = FileManager(db, config)
    
    languages = ['en', 'de', 'he']
    
    for language in languages:
        # Get files with translation in progress
        status_field = f"translation_{language}_status"
        files = db.execute_query(f"""
            SELECT m.file_id, m.safe_filename 
            FROM media_files m 
            JOIN processing_status p ON m.file_id = p.file_id 
            WHERE p.{status_field} = 'in-progress'
        """)
        
        if not files:
            logger.info(f"No files with {language} translation in progress")
            continue
            
        logger.info(f"Found {len(files)} files with {language} translation in progress")
        fixed_count = 0
        
        for file in files:
            file_id = file['file_id']
            translation_path = file_manager.get_translation_path(file_id, language)
            
            if not os.path.exists(translation_path):
                logger.info(f"File {file_id} is marked with {language} translation in-progress but no file found at {translation_path}")
                
                # Update status to failed - using direct cursor approach for UPDATE statements
                conn = db._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE processing_status SET {status_field} = 'failed' WHERE file_id = ?",
                    (file_id,)
                )
                conn.commit()
                
                # Log the error
                db.log_error(
                    file_id=file_id, 
                    process_stage=f"translation_{language}", 
                    error_message="Marked as failed by fix_stalled_files.py", 
                    error_details=f"File was in-progress but no {language} translation file was found"
                )
                
                fixed_count += 1
        
        logger.info(f"Fixed {fixed_count} stalled {language} translation files")

def fix_inconsistent_files():
    """
    Find files that have transcripts but are not marked as completed in the database,
    and update their status.
    """
    db = DatabaseManager('media_tracking.db')
    config = {'output_directory': './output'}
    file_manager = FileManager(db, config)
    
    # Get all files from database
    files = db.execute_query("""
        SELECT m.file_id, m.safe_filename, p.transcription_status
        FROM media_files m 
        JOIN processing_status p ON m.file_id = p.file_id
        WHERE p.transcription_status != 'completed'
    """)
    
    logger.info(f"Checking {len(files)} files for transcript consistency")
    fixed_count = 0
    
    for file in files:
        file_id = file['file_id']
        transcript_path = file_manager.get_transcript_path(file_id)
        
        if os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 0:
            logger.info(f"File {file_id} has a transcript but status is {file['transcription_status']}")
            
            # Update status to completed - using direct cursor approach for UPDATE statements
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE processing_status SET transcription_status = 'completed' WHERE file_id = ?",
                (file_id,)
            )
            conn.commit()
            
            fixed_count += 1
    
    logger.info(f"Fixed {fixed_count} inconsistent transcription files")
    
    # Now check for translation files
    languages = ['en', 'de', 'he']
    
    for language in languages:
        # Get files with incomplete translation status
        status_field = f"translation_{language}_status"
        files = db.execute_query(f"""
            SELECT m.file_id, m.safe_filename, p.{status_field} as status
            FROM media_files m 
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.{status_field} != 'completed'
        """)
        
        logger.info(f"Checking {len(files)} files for {language} translation consistency")
        fixed_count = 0
        
        for file in files:
            file_id = file['file_id']
            translation_path = file_manager.get_translation_path(file_id, language)
            
            if os.path.exists(translation_path) and os.path.getsize(translation_path) > 0:
                logger.info(f"File {file_id} has a {language} translation but status is {file['status']}")
                
                # Update status to completed - using direct cursor approach for UPDATE statements
                conn = db._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE processing_status SET {status_field} = 'completed' WHERE file_id = ?",
                    (file_id,)
                )
                conn.commit()
                
                fixed_count += 1
        
        logger.info(f"Fixed {fixed_count} inconsistent {language} translation files")

def main():
    logger.info("Starting fix_stalled_files script")
    
    fix_transcription_status()
    fix_translation_status()
    fix_inconsistent_files()
    
    logger.info("Fix stalled files completed")

if __name__ == "__main__":
    main()