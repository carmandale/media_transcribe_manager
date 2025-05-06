#!/usr/bin/env python3
"""
Process remaining files that need both transcription and translation.
"""

import os
import sys
import argparse
import subprocess
import time
from typing import List, Dict, Any

from db_manager import DatabaseManager

def main():
    parser = argparse.ArgumentParser(description="Process remaining files (transcription + translation)")
    parser.add_argument("--workers", type=int, default=2, 
                        help="Maximum number of concurrent workers (default: 2)")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Number of files to process per batch (default: 10)")
    args = parser.parse_args()
    
    # Connect to database
    db = DatabaseManager('media_tracking.db')
    
    # First, let's get the files that need transcription
    files_to_transcribe = db.execute_query("""
        SELECT file_id 
        FROM processing_status 
        WHERE transcription_status = 'not_started'
    """)
    
    if files_to_transcribe:
        print(f"Found {len(files_to_transcribe)} files that need transcription")
        
        # Run the parallel transcription process
        cmd = [
            'python', 'parallel_transcription.py',
            '--workers', str(args.workers),
            '--batch-size', str(args.batch_size)
        ]
        
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd)
        
        # Give time for the database to update
        print("Waiting for transcription to complete...")
        time.sleep(5)
    else:
        print("No files need transcription")
    
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
            
            # Give time for the database to update
            print(f"Waiting for {language} translation to complete...")
            time.sleep(5)
        else:
            print(f"No files need {language} translation")
    
    print("\nFinal status:")
    # Print final status
    for process in ['transcription', 'translation_en', 'translation_de', 'translation_he']:
        counts = db.execute_query(f"""
            SELECT {process}_status, COUNT(*) as count
            FROM processing_status
            GROUP BY {process}_status
        """)
        
        print(f"\n{process.replace('_', ' ').title()}:")
        for status in counts:
            print(f"- {status[process + '_status']}: {status['count']}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())