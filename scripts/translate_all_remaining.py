#!/usr/bin/env python3
"""
Translate All Remaining Files

This script processes all files that need translation in a cleaner way,
focusing on files that have completed transcription but need translation.
"""

import os
import sys
import logging
import subprocess
import time
import sqlite3
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('translate_all_remaining.log')
    ]
)

logger = logging.getLogger(__name__)

def fix_database_inconsistencies():
    """Fix any database inconsistencies that might be preventing translation."""
    try:
        conn = sqlite3.connect('media_tracking.db')
        cursor = conn.cursor()
        
        # Fix any files marked as "in-progress" for transcription but with transcript files
        cursor.execute("""
        SELECT m.file_id, m.safe_filename 
        FROM media_files m 
        JOIN processing_status p ON m.file_id = p.file_id 
        WHERE p.transcription_status = 'in-progress'
        """)
        
        in_progress_files = cursor.fetchall()
        fixed_count = 0
        
        for file_id, safe_filename in in_progress_files:
            # Construct transcript path
            base_name = os.path.splitext(safe_filename)[0]
            transcript_path = os.path.join('./output/transcripts', f"{base_name}.txt")
            
            # If transcript exists, mark as completed
            if os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 0:
                cursor.execute(
                    "UPDATE processing_status SET transcription_status = 'completed' WHERE file_id = ?",
                    (file_id,)
                )
                fixed_count += 1
                logger.info(f"Fixed file {file_id} - transcript exists but status was 'in-progress'")
            else:
                # If no transcript exists, mark as failed
                cursor.execute(
                    "UPDATE processing_status SET transcription_status = 'failed' WHERE file_id = ?",
                    (file_id,)
                )
                logger.info(f"Marked file {file_id} as 'failed' - no transcript file found")
        
        conn.commit()
        logger.info(f"Fixed {fixed_count} files with inconsistent transcription status")
        
        # Clear any stale "in-progress" translation statuses
        for lang in ['en', 'de', 'he']:
            cursor.execute(f"""
            UPDATE processing_status 
            SET translation_{lang}_status = 'not_started' 
            WHERE translation_{lang}_status = 'in-progress'
            """)
            
            if cursor.rowcount > 0:
                logger.info(f"Reset {cursor.rowcount} stale 'in-progress' translation_{lang}_status entries")
        
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")

def get_pending_translations():
    """Get counts of pending translations for each language."""
    conn = sqlite3.connect('media_tracking.db')
    cursor = conn.cursor()
    
    results = {}
    
    for lang in ['en', 'de', 'he']:
        cursor.execute(f"""
        SELECT COUNT(*) FROM processing_status 
        WHERE translation_{lang}_status IN ('not_started', 'failed')
        AND transcription_status = 'completed'
        """)
        
        count = cursor.fetchone()[0]
        results[lang] = count
    
    conn.close()
    return results

def process_translations():
    """Process translations for all languages."""
    # Get pending counts
    pending = get_pending_translations()
    logger.info(f"Pending translations: {pending}")
    
    total_processed = 0
    
    # Process each language sequentially
    for lang in ['en', 'de', 'he']:
        if pending[lang] > 0:
            logger.info(f"Processing {pending[lang]} {lang} translations")
            
            try:
                # Use smaller batch sizes to avoid issues
                batch_size = 5
                
                # Run the translation process
                cmd = f"python parallel_translation.py --language {lang} --batch-size {batch_size}"
                logger.info(f"Running command: {cmd}")
                
                # Run and capture output
                result = subprocess.run(cmd, shell=True, check=True, 
                                       capture_output=True, text=True)
                
                logger.info(f"Command completed with output: {result.stdout}")
                
                if "No files found" in result.stdout:
                    logger.warning(f"No files found for {lang} translation despite database showing {pending[lang]} pending files")
                else:
                    logger.info(f"Successfully processed some {lang} translations")
                    total_processed += 1
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Error processing {lang} translations: {e}")
                logger.error(f"Command output: {e.stdout}")
                logger.error(f"Command error: {e.stderr}")
                
            # Pause between languages to avoid potential conflicts
            time.sleep(2)
    
    return total_processed

def main():
    logger.info("Starting translation of all remaining files")
    
    # Fix any database inconsistencies
    fix_database_inconsistencies()
    
    # Process translations for all languages
    processed = process_translations()
    
    if processed > 0:
        logger.info(f"Successfully processed translations for {processed} languages")
    else:
        logger.warning("No translations were processed")
    
    # Check if we still have pending translations
    pending = get_pending_translations()
    total_pending = sum(pending.values())
    
    if total_pending > 0:
        logger.info(f"There are still {total_pending} translations pending: {pending}")
    else:
        logger.info("All translations have been processed!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())