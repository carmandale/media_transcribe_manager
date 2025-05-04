#!/usr/bin/env python3
"""
Check if transcript files exist for problematic files and fix paths if needed.
"""

import os
import sys
from db_manager import DatabaseManager
from file_manager import FileManager

def check_transcript(file_id):
    """Check if transcript exists for file ID and print details."""
    # Basic configuration
    config = {'output_directory': './output'}
    db = DatabaseManager('media_tracking.db')
    fm = FileManager(db, config)
    
    # Get file details
    file_details = db.get_file_status(file_id)
    if not file_details:
        print(f"Error: File ID {file_id} not found in database")
        return
    
    print(f"File ID: {file_id}")
    print(f"Transcription status: {file_details['transcription_status']}")
    print(f"Translation EN status: {file_details['translation_en_status']}")
    print(f"Translation DE status: {file_details['translation_de_status']}")
    print(f"Translation HE status: {file_details['translation_he_status']}")
    
    # Check transcript path
    transcript_path = fm.get_transcript_path(file_id)
    print(f"Transcript path: {transcript_path}")
    print(f"Transcript exists: {os.path.exists(transcript_path)}")
    
    if os.path.exists(transcript_path):
        file_size = os.path.getsize(transcript_path)
        print(f"Transcript file size: {file_size} bytes")
        
        # Show preview of content
        if file_size > 0:
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    content = f.read(300)
                    print("\nTranscript preview:")
                    print(content + "..." if len(content) >= 300 else content)
            except Exception as e:
                print(f"Error reading transcript: {e}")
        else:
            print("Transcript file is empty")
    
    # Check translation paths
    for lang in ['en', 'de', 'he']:
        translation_path = fm.get_translation_path(file_id, lang)
        print(f"\nTranslation {lang.upper()} path: {translation_path}")
        exists = os.path.exists(translation_path)
        print(f"Translation exists: {exists}")
        
        if exists:
            file_size = os.path.getsize(translation_path)
            print(f"Translation file size: {file_size} bytes")
            
            # Show preview of content
            if file_size > 0:
                try:
                    with open(translation_path, 'r', encoding='utf-8') as f:
                        content = f.read(300)
                        print(f"\nTranslation {lang.upper()} preview:")
                        print(content + "..." if len(content) >= 300 else content)
                except Exception as e:
                    print(f"Error reading translation: {e}")
            else:
                print("Translation file is empty")

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_transcript_file.py <file_id>")
        sys.exit(1)
    
    file_id = sys.argv[1]
    check_transcript(file_id)

if __name__ == "__main__":
    main()