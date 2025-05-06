#!/usr/bin/env python3
"""
Check for files marked as completed in the database but missing their transcript files.
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
    
    missing_count = 0
    for file in files:
        file_id = file['file_id']
        filename = file['safe_filename']
        base_name = os.path.splitext(filename)[0]
        
        # Check if transcript file exists
        transcript_path = os.path.join('./output/transcripts', f"{file_id}_{base_name}.txt")
        if not os.path.exists(transcript_path):
            missing_count += 1
            if missing_count <= 10:
                print(f"Missing transcript: {file_id}_{base_name}.txt")
    
    print(f"\nTotal missing transcripts: {missing_count} out of {len(files)} completed files")
    
    # Check for files in in-progress status
    in_progress = db.execute_query(
        '''SELECT file_id, transcription_status, translation_en_status, 
                translation_de_status, translation_he_status
           FROM processing_status 
           WHERE status = "in-progress"'''
    )
    
    print(f"\nFiles in 'in-progress' status: {len(in_progress)}")
    for file in in_progress[:5]:
        print(f"- {file['file_id']}: T:{file['transcription_status']} EN:{file['translation_en_status']} "
              f"DE:{file['translation_de_status']} HE:{file['translation_he_status']}")

if __name__ == "__main__":
    main()