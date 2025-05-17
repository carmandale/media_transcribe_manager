#!/usr/bin/env python3
"""
Parallel Transcription Processor

This script processes multiple audio files for transcription in parallel,
significantly speeding up the processing of untranscribed files.

Usage:
    python parallel_transcription.py [--workers N] [--batch-size N]
"""

import os
import sys
import time
import argparse
import concurrent.futures
from typing import List, Dict, Any, Optional
import pathlib
from pathlib import Path

# Ensure project root is on the Python path so core_modules can be imported
script_dir = pathlib.Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))
from core_modules.db_manager import DatabaseManager
from core_modules.file_manager import FileManager
from core_modules.transcription import TranscriptionManager
from core_modules.log_config import setup_logger

# Configure logging
logger = setup_logger('parallel_transcription', 'parallel_transcription.log')

def load_environment():
    """Load environment variables and verify API keys are set."""
    # Try to load from .env file if available
    # Look for .env in script directory or project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    # Fallback to project root .env
    if not os.path.exists(env_path):
        env_path = os.path.join(script_dir, '..', '.env')
    if os.path.exists(env_path):
        try:
            import dotenv
            dotenv.load_dotenv(env_path)
            logger.info(f"Loaded environment from {env_path}")
        except ImportError:
            logger.warning("dotenv not available, using defaults")
    
    # Check if required keys are set
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        logger.error("ELEVENLABS_API_KEY not found in environment")
        logger.error("Please ensure it is set in your .env file")
        return False
        
    logger.info(f"API key loaded: {api_key[:5]}...{api_key[-5:]}")
    return True

def get_files_for_transcription(db: DatabaseManager, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get files that need transcription."""
    query = """
    SELECT *
    FROM processing_status
    WHERE transcription_status IN ('not_started', 'failed')
    ORDER BY file_id
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    files = db.execute_query(query)
    return files

def transcribe_single_file(file: Dict[str, Any], db: DatabaseManager, file_manager: FileManager, 
                          transcription_manager: TranscriptionManager) -> bool:
    """Process a single file for transcription."""
    file_id = file['file_id']
    
    logger.info(f"Processing file: {file_id}")
    
    # Get audio path
    audio_path = file_manager.get_audio_path(file_id)
    if not audio_path:
        logger.error(f"Audio file not found for {file_id}")
        return False
    
    # Verify file exists
    if not os.path.exists(audio_path):
        logger.error(f"Audio file does not exist at path: {audio_path}")
        return False
    
    # Transcribe audio
    start_time = time.time()
    success = transcription_manager.transcribe_audio(
        file_id=file_id,
        audio_path=audio_path,
        file_details=file
    )
    
    elapsed = time.time() - start_time
    if success:
        logger.info(f"Successfully transcribed {file_id} in {elapsed:.2f} seconds")
        
        # Verify transcript exists
        transcript_path = file_manager.get_transcript_path(file_id)
        if os.path.exists(transcript_path):
            logger.info(f"Transcript created at: {transcript_path} ({os.path.getsize(transcript_path)} bytes)")
        else:
            logger.warning(f"Transcription marked successful but file not found at: {transcript_path}")
    else:
        logger.error(f"Failed to transcribe {file_id} after {elapsed:.2f} seconds")
    
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
    
    # Create shared managers
    file_manager = FileManager(db, config)
    
    # Track statistics
    processed_count = 0
    success_count = 0
    error_count = 0
    
    # Process in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a transcription manager per worker
        futures = []
        
        for file in files:
            # Create a dedicated transcription manager for each file
            # This avoids sharing the same manager across threads
            transcription_manager = TranscriptionManager(db, config)
            transcription_manager.set_file_manager(file_manager)
            
            # Submit task to executor
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
            processed_count += 1
            try:
                success = future.result()
                if success:
                    success_count += 1
                else:
                    error_count += 1
                
                logger.info(f"Progress: {processed_count}/{len(files)} files processed. "
                           f"Success: {success_count}, Errors: {error_count}")
            except Exception as e:
                error_count += 1
                logger.error(f"Exception during processing: {e}")
    
    logger.info(f"All files processed. Success: {success_count}, Errors: {error_count}")
    return success_count, error_count

def main():
    parser = argparse.ArgumentParser(description="Process audio files for transcription in parallel")
    parser.add_argument("--workers", type=int, default=5, 
                        help="Maximum number of concurrent workers (default: 5)")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Number of files to process (default: all pending files)")
    args = parser.parse_args()
    
    # Verify environment is set up correctly
    if not load_environment():
        logger.error("Failed to load environment variables")
        return 1
    
    # Connect to database using Path to ensure correct path handling
    db_file = str(Path(__file__).parent.parent / 'media_tracking.db')
    db = DatabaseManager(db_file)
    
    # Get files for transcription
    files = get_files_for_transcription(db, args.batch_size)
    if not files:
        logger.info("No files found for transcription")
        return 0
    
    logger.info(f"Found {len(files)} files for transcription")
    
    # Process files in parallel
    start_time = time.time()
    success_count, error_count = process_files_parallel(files, args.workers, db)
    elapsed = time.time() - start_time
    
    logger.info(f"Completed in {elapsed:.2f} seconds")
    logger.info(f"Success: {success_count}, Errors: {error_count}")
    
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())