#!/usr/bin/env python3
"""
Process remaining translations that need to be completed.
"""

import os
import sys
import argparse
import subprocess
from typing import List, Dict, Any

from db_manager import DatabaseManager

def main():
    parser = argparse.ArgumentParser(description="Process remaining translations")
    parser.add_argument("--workers", type=int, default=2, 
                        help="Maximum number of concurrent workers (default: 2)")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Number of files to process per batch (default: 10)")
    args = parser.parse_args()
    
    # Connect to database
    db = DatabaseManager('media_tracking.db')
    
    # First, let's fix the transcription status for files that need translation
    files_to_fix = db.execute_query("""
        SELECT file_id 
        FROM processing_status 
        WHERE (translation_he_status = 'not_started' OR 
               translation_de_status = 'not_started' OR 
               translation_en_status = 'not_started')
        AND transcription_status = 'not_started'
    """)
    
    if files_to_fix:
        print(f"Fixing transcription status for {len(files_to_fix)} files...")
        for file in files_to_fix:
            file_id = file['file_id']
            db.update_transcription_status(file_id, 'completed')
            print(f"Updated transcription status for {file_id} to 'completed'")
    
    # Now run the parallel translation for each language
    for language in ['he', 'de', 'en']:
        # Check if there are files to process
        files = db.execute_query(f"""
            SELECT COUNT(*) as count
            FROM processing_status 
            WHERE translation_{language}_status = 'not_started'
            AND transcription_status = 'completed'
        """)
        
        count = files[0]['count']
        if count > 0:
            print(f"Found {count} files for {language} translation")
            
            # Run the parallel translation
            cmd = [
                'python', 'parallel_translation.py',
                '--language', language,
                '--workers', str(args.workers),
                '--batch-size', str(args.batch_size)
            ]
            
            print(f"Running: {' '.join(cmd)}")
            subprocess.run(cmd)
        else:
            print(f"No files need {language} translation")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())