#!/usr/bin/env python3
"""
Retry QA Failed Files

This script finds and retries files that have been marked as qa_failed.
It provides detailed diagnostics and enhanced retry capabilities.

Usage:
    python retry_qa_failed.py [--limit N] [--timeout-multiplier N]
"""

import os
import sys
import argparse
import time
from pathlib import Path
import tempfile
import shutil
import subprocess

# Add core_modules to the Python path
sys.path.append(str(Path(__file__).parent.parent / 'core_modules'))
from log_config import setup_logger
from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

# Configure logging
logger = setup_logger('retry_qa_failed', 'retry_qa_failed.log')

def get_qa_failed_files(db: DatabaseManager, limit=None):
    """Get files marked as qa_failed for transcription."""
    query = """
    SELECT m.*, p.*
    FROM media_files m
    JOIN processing_status p ON m.file_id = p.file_id
    WHERE p.transcription_status = 'qa_failed'
    ORDER BY p.last_updated DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
        
    return db.execute_query(query)

def reset_file_status(db: DatabaseManager, file_id: str):
    """Reset the status of a file to retry it."""
    # First, clear any errors associated with this file
    db.clear_file_errors(file_id)
    
    # Then set the transcription status back to 'not_started'
    query = """
    UPDATE processing_status 
    SET transcription_status = 'not_started', status = 'pending'
    WHERE file_id = ?
    """
    
    rows_affected = db.execute_update(query, (file_id,))
    return rows_affected > 0

def verify_file_existence(file_path: str) -> bool:
    """Verify that the file exists and is accessible."""
    try:
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File does not exist: {file_path}")
            return False
        
        file_size = path.stat().st_size
        if file_size == 0:
            logger.error(f"File is empty (0 bytes): {file_path}")
            return False
            
        logger.info(f"File exists and is {file_size / (1024*1024):.2f} MB")
        return True
    except Exception as e:
        logger.error(f"Error checking file {file_path}: {e}")
        return False

def verify_audio_integrity(file_path: str) -> bool:
    """Verify audio file integrity using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", 
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
             file_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        # If ffprobe can read duration, file is likely valid
        duration = float(result.stdout.strip())
        logger.info(f"Audio file is valid with duration: {duration:.2f} seconds")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Audio file integrity check failed: {e.stderr}")
        return False
    except ValueError as e:
        logger.error(f"Could not parse duration: {e}")
        return False
    except Exception as e:
        logger.error(f"Error checking audio integrity: {e}")
        return False

def retry_transcription(file: dict, config: dict, timeout_multiplier: float = 2.0) -> bool:
    """Retry transcription with extended timeout."""
    db = DatabaseManager(config.get('db_path', 'media_tracking.db'))
    file_manager = FileManager(db, config)
    transcription_manager = TranscriptionManager(db, config)
    transcription_manager.set_file_manager(file_manager)
    
    file_id = file['file_id']
    audio_path = file['original_path']
    
    # Verify file exists
    if not verify_file_existence(audio_path):
        logger.error(f"File verification failed for {file_id}")
        return False
    
    # Verify audio integrity
    if not verify_audio_integrity(audio_path):
        logger.error(f"Audio integrity check failed for {file_id}")
        return False
    
    # Set extended timeout for API calls
    default_timeout = 300  # 5 minutes
    extended_timeout = int(default_timeout * timeout_multiplier)
    
    # Update request options with extended timeout
    request_options = {"timeout_in_seconds": extended_timeout}
    transcription_manager.request_options = request_options
    
    logger.info(f"Retrying transcription for {file_id} with {extended_timeout}s timeout")
    
    # Reset status
    reset_file_status(db, file_id)
    
    # Retry transcription
    start_time = time.time()
    success = transcription_manager.transcribe_audio(
        file_id=file_id,
        audio_path=audio_path,
        file_details=file
    )
    
    elapsed = time.time() - start_time
    
    if success:
        logger.info(f"Successfully transcribed {file_id} in {elapsed:.2f} seconds")
        return True
    else:
        logger.error(f"Failed to transcribe {file_id} after {elapsed:.2f} seconds")
        return False

def main():
    parser = argparse.ArgumentParser(description="Retry files marked as qa_failed")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of files to process")
    parser.add_argument("--timeout-multiplier", type=float, default=2.0,
                        help="Multiply default timeout by this factor (default: 2.0)")
    args = parser.parse_args()
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("dotenv not available, using environment variables as is")
    
    # Basic configuration
    config = {
        'db_path': 'media_tracking.db',
        'output_directory': './output',
        'elevenlabs': {
            'api_key': os.getenv('ELEVENLABS_API_KEY'),
            'model': 'scribe_v1'
        }
    }
    
    # Connect to database
    db = DatabaseManager(config['db_path'])
    
    # Get QA failed files
    files = get_qa_failed_files(db, args.limit)
    
    if not files:
        logger.info("No QA failed files found to retry")
        return 0
    
    logger.info(f"Found {len(files)} QA failed files to retry")
    
    # Process each file
    success_count = 0
    error_count = 0
    
    for file in files:
        file_id = file['file_id']
        logger.info(f"Processing {file_id}: {file['original_path']}")
        
        # Retry with extended timeout
        if retry_transcription(file, config, args.timeout_multiplier):
            success_count += 1
            logger.info(f"Retry successful for {file_id}")
        else:
            error_count += 1
            logger.error(f"Retry failed for {file_id}")
    
    logger.info(f"Retry complete. Success: {success_count}, Errors: {error_count}")
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())