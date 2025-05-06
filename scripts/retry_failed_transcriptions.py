#!/usr/bin/env python3
"""
Retry failed transcription tasks.
"""

import os
import sys
import argparse
import concurrent.futures
from typing import List, Dict, Any

from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

def get_failed_transcription_files(db: DatabaseManager, limit: int = None) -> List[Dict[str, Any]]:
    """Get files with failed transcription."""
    query = """
    SELECT m.*, p.*
    FROM media_files m
    JOIN processing_status p ON m.file_id = p.file_id
    WHERE p.transcription_status = 'failed'
    ORDER BY p.last_updated ASC
    """
    
    if limit is not None:
        query += f" LIMIT {int(limit)}"
        
    files = db.execute_query(query)
    return files

def transcribe_single_file(file: Dict[str, Any], db: DatabaseManager, 
                         file_manager: FileManager, transcription_manager: TranscriptionManager) -> bool:
    """Process a single file for transcription."""
    file_id = file['file_id']
    original_path = file['original_path']
    
    print(f"Retrying transcription for file: {file_id} ({original_path})")
    
    # Reset status to not_started to allow retrying
    db.update_transcription_status(file_id, 'not_started')
    
    # Get audio path
    audio_path = file_manager.get_audio_path(file_id)
    if not audio_path:
        print(f"Audio file not found for {file_id}")
        return False
    
    # Verify file exists
    if not os.path.exists(audio_path):
        print(f"Audio file does not exist at path: {audio_path}")
        return False
    
    # Transcribe audio
    success = transcription_manager.transcribe_audio(
        file_id=file_id,
        audio_path=audio_path,
        file_details=file
    )
    
    if success:
        print(f"Successfully transcribed file: {file_id}")
        
        # Verify transcript exists
        transcript_path = file_manager.get_transcript_path(file_id)
        if os.path.exists(transcript_path):
            print(f"Transcript created at: {transcript_path} ({os.path.getsize(transcript_path)} bytes)")
        else:
            print(f"Transcription marked successful but file not found at: {transcript_path}")
    else:
        print(f"Failed to transcribe file: {file_id}")
    
    return success

def process_files_parallel(files: List[Dict[str, Any]], max_workers: int, db: DatabaseManager):
    """Process files in parallel using a thread pool."""
    config = {
        'output_directory': './output',
        'elevenlabs': {
            'api_key': os.getenv('ELEVENLABS_API_KEY'),
            'model': 'scribe_v1',
            'speaker_detection': True,
            'speaker_count': 32
        },
        'max_audio_size_mb': 25,
        'api_retries': 8,
        'segment_pause': 1
    }
    
    # Create shared file manager
    file_manager = FileManager(db, config)
    
    # Track statistics
    success_count = 0
    error_count = 0
    
    # Process in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks to the executor
        futures = []
        for file in files:
            # Create a dedicated transcription manager for each file
            transcription_manager = TranscriptionManager(db, config)
            transcription_manager.set_file_manager(file_manager)
            
            future = executor.submit(
                transcribe_single_file, 
                file=file,
                db=db,
                file_manager=file_manager,
                transcription_manager=transcription_manager
            )
            futures.append(future)
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            try:
                success = future.result()
                if success:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                print(f"Error during processing: {e}")
                error_count += 1
                
            print(f"Progress: {success_count + error_count}/{len(files)}, "
                  f"Success: {success_count}, Errors: {error_count}")
    
    return success_count, error_count

def main():
    parser = argparse.ArgumentParser(description="Retry failed transcription tasks")
    parser.add_argument("--workers", type=int, default=2, 
                        help="Maximum number of concurrent workers (default: 2)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit the number of files to process")
    args = parser.parse_args()
    
    # Load environment
    try:
        import dotenv
        dotenv.load_dotenv()
        print("Loaded environment from .env file")
    except ImportError:
        print("dotenv module not available, using default environment")
    
    # Connect to database
    db = DatabaseManager('media_tracking.db')
    
    # Get failed transcription files
    files = get_failed_transcription_files(db, args.limit)
    if not files:
        print("No failed transcription files found")
        return 0
    
    print(f"Found {len(files)} failed transcription files")
    
    # Process files in parallel
    success_count, error_count = process_files_parallel(
        files, args.workers, db
    )
    
    print(f"Completed processing {len(files)} files")
    print(f"Success: {success_count}, Errors: {error_count}")
    
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())