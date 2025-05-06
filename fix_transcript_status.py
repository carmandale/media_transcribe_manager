#!/usr/bin/env python3
"""
Fix incorrect transcript status for files marked as completed but missing their transcript files.
"""

import os
import db_manager

def main():
    # Connect to the database
    db = db_manager.DatabaseManager('media_tracking.db')
    
    # Get all files marked as having completed transcription
    files = db.execute_query(
        '''SELECT media_files.file_id, safe_filename, transcription_status 
           FROM media_files 
           JOIN processing_status ON media_files.file_id = processing_status.file_id 
           WHERE transcription_status = "completed"'''
    )
    
    print(f"Checking {len(files)} files marked as completed...")
    
    fixed_count = 0
    for file in files:
        file_id = file['file_id']
        filename = file['safe_filename']
        base_name = os.path.splitext(filename)[0]
        
        # Check if transcript file exists
        transcript_path = os.path.join('./output/transcripts', f"{file_id}_{base_name}.txt")
        if not os.path.exists(transcript_path):
            # Update status to failed
            db.update_transcription_status(file_id, 'failed')
            
            # Log error
            error_msg = f"Transcript file missing despite status of completed"
            db.log_error(file_id, 'transcription', error_msg, f"File path: {transcript_path}")
            
            fixed_count += 1
            print(f"Updated status for {file_id} from completed to failed")
    
    print(f"\nFixed {fixed_count} files with incorrect status")

if __name__ == "__main__":
    main()