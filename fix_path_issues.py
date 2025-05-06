#!/usr/bin/env python3
"""
Fix Path Issues Script

This script fixes problematic file paths in the database and updates the status
to retry processing with the fixed paths.
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fix_path_issues.log')
    ]
)

logger = logging.getLogger(__name__)

# Mapping of problematic file IDs to their new paths
PATH_FIXES = {
    '0e39bce9-8fa7-451a-8a50-5a9f8fc4493f': './fixed_source/jurgen_krackow_side_b.mp3',
    '4a7415b3-31f8-40a8-b326-5092c0b05a81': './fixed_source/barry_gourary_side_b.mp3'
}

def fix_file_paths():
    """Fix problematic file paths in the database."""
    try:
        # Connect to the database
        conn = sqlite3.connect('media_tracking.db')
        cursor = conn.cursor()
        
        total_fixed = 0
        
        for file_id, new_path in PATH_FIXES.items():
            # Get current path
            cursor.execute(
                "SELECT original_path FROM media_files WHERE file_id = ?",
                (file_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                logger.warning(f"File ID {file_id} not found in database")
                continue
                
            current_path = result[0]
            
            # Convert to absolute path if needed
            if new_path.startswith('./'):
                new_path = os.path.abspath(new_path)
                
            logger.info(f"Updating file {file_id}:")
            logger.info(f"  Old path: {current_path}")
            logger.info(f"  New path: {new_path}")
            
            # Verify the new file exists
            if not os.path.exists(new_path):
                logger.error(f"New path does not exist: {new_path}")
                continue
                
            # Update the path in the database
            cursor.execute(
                "UPDATE media_files SET original_path = ? WHERE file_id = ?",
                (new_path, file_id)
            )
            
            # Also update safe_filename to something simpler
            new_safe_filename = os.path.basename(new_path)
            cursor.execute(
                "UPDATE media_files SET safe_filename = ? WHERE file_id = ?",
                (new_safe_filename, file_id)
            )
            
            # Reset the transcription status to retry
            cursor.execute(
                "UPDATE processing_status SET transcription_status = 'not_started', status = 'pending' WHERE file_id = ?",
                (file_id,)
            )
            
            # Clear any errors for this file
            cursor.execute(
                "DELETE FROM errors WHERE file_id = ?",
                (file_id,)
            )
            
            total_fixed += 1
            
        # Commit changes
        conn.commit()
        logger.info(f"Fixed {total_fixed} file paths")
        
        # Close connection
        conn.close()
        
        return total_fixed
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return 0

def main():
    logger.info("Starting path fix script")
    
    fixed_count = fix_file_paths()
    
    if fixed_count > 0:
        logger.info(f"Successfully fixed {fixed_count} file paths")
        logger.info("Files are ready for reprocessing")
        return 0
    else:
        logger.error("Failed to fix file paths")
        return 1

if __name__ == "__main__":
    sys.exit(main())