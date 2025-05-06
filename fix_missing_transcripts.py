#!/usr/bin/env python3
"""
Fix files with missing transcripts.

This script identifies files marked as having transcripts but actually missing them,
resets their transcription status, and prepares them for reprocessing.
"""

import os
import sys
import argparse
import concurrent.futures
from typing import List, Dict, Any

from db_manager import DatabaseManager
from file_manager import FileManager

def get_files_with_missing_transcripts(db: DatabaseManager) -> List[Dict[str, Any]]:
    """Get files marked as completed but with missing transcript files."""
    # Get all files marked as having completed transcription
    files = db.execute_query(
        '''SELECT media_files.file_id, safe_filename, transcription_status, translation_en_status, 
                  translation_de_status, translation_he_status 
           FROM media_files 
           JOIN processing_status ON media_files.file_id = processing_status.file_id
        '''
    )
    
    # Filter files with missing transcripts
    missing_transcripts = []
    file_manager = FileManager(db, {'output_directory': './output'})
    
    for file in files:
        file_id = file['file_id']
        transcript_path = file_manager.get_transcript_path(file_id)
        
        if not os.path.exists(transcript_path):
            missing_transcripts.append(file)
            
    return missing_transcripts
    
def main():
    parser = argparse.ArgumentParser(description="Fix files with missing transcripts")
    parser.add_argument("--fix", action="store_true", 
                        help="Actually fix the database (otherwise just reports issues)")
    args = parser.parse_args()
    
    # Connect to database
    db = DatabaseManager('media_tracking.db')
    
    # Find files with missing transcripts
    problem_files = get_files_with_missing_transcripts(db)
    
    if not problem_files:
        print("No files with missing transcripts found")
        return 0
    
    # Print summary
    print(f"Found {len(problem_files)} files with missing transcripts:")
    for idx, file in enumerate(problem_files, 1):
        file_id = file['file_id']
        transcription_status = file['transcription_status']
        en_status = file['translation_en_status'] 
        de_status = file['translation_de_status']
        he_status = file['translation_he_status']
        
        print(f"{idx}. {file_id}")
        print(f"   Transcription: {transcription_status}")
        print(f"   Translation EN: {en_status}, DE: {de_status}, HE: {he_status}")
        
    # Fix database if requested
    if args.fix:
        print("\nFixing database records...")
        for file in problem_files:
            file_id = file['file_id']
            
            # Reset transcription status
            db.update_transcription_status(file_id, 'failed')
            
            # If any translation is not_started, keep it that way
            # Otherwise reset all translations to not_started
            if (file['translation_en_status'] == 'not_started' or 
                file['translation_de_status'] == 'not_started' or
                file['translation_he_status'] == 'not_started'):
                pass  # Keep current translation status
            else:
                # Reset all translations
                db.update_translation_status(file_id, 'en', 'not_started')
                db.update_translation_status(file_id, 'de', 'not_started')
                db.update_translation_status(file_id, 'he', 'not_started')
            
            # Log error
            db.log_error(file_id, 'transcription', 
                         "Missing transcript file despite completed status",
                         f"File marked as {file['transcription_status']} but no transcript file exists")
            
            print(f"Reset file {file_id} to failed transcription")
            
        print(f"\nReset {len(problem_files)} files. Run the following to process them:")
        print("python parallel_transcription.py --workers 2 --batch-size 10")
    else:
        print("\nRun with --fix flag to reset these files in the database")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())