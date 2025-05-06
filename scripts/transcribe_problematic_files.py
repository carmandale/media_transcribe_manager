#!/usr/bin/env python3
"""
Special transcription script for problematic files that fail with the regular process.
This script uses an extended timeout and more detailed error reporting.
"""

import os
import sys
import time
import logging
from typing import List

from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('problematic_files.log')
    ]
)

logger = logging.getLogger(__name__)

# List of problematic file IDs to focus on
PROBLEMATIC_FILE_IDS = [
    '0e39bce9-8fa7-451a-8a50-5a9f8fc4493f',  # Jürgen Krackow file
    '4a7415b3-31f8-40a8-b326-5092c0b05a81',  # Barry Gourary file
]

def load_environment():
    """Load environment variables."""
    # Try to load from .env file if available
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            import dotenv
            dotenv.load_dotenv(env_path)
            logger.info("Loaded environment from .env file")
        except ImportError:
            logger.warning("dotenv not available, using defaults")
    
    # Check if required keys are set
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        logger.error("ELEVENLABS_API_KEY not found in environment")
        return False
    logger.info(f"API key loaded: {api_key[:5]}...{api_key[-5:]}")
    return True

def transcribe_problematic_file(file_id: str) -> bool:
    """
    Attempt to transcribe a known problematic file with extended timeout.
    
    Args:
        file_id: ID of the file to transcribe
        
    Returns:
        True if successful, False otherwise
    """
    # Connect to database
    db = DatabaseManager('media_tracking.db')
    
    # Get file information
    file_info = db.get_file_by_id(file_id)
    if not file_info:
        logger.error(f"File with ID {file_id} not found in database")
        return False
    
    logger.info(f"Processing problematic file: {file_id}")
    logger.info(f"Original path: {file_info['original_path']}")
    logger.info(f"Safe filename: {file_info['safe_filename']}")
    
    # Configure managers with extended timeouts
    config = {
        'output_directory': './output',
        'elevenlabs': {
            'api_key': os.getenv('ELEVENLABS_API_KEY'),
            'timeout': 600  # Extend timeout to 10 minutes for these problematic files
        }
    }
    
    file_manager = FileManager(db, config)
    
    # Set up transcription manager with extended timeout
    transcription_manager = TranscriptionManager(db, config)
    transcription_manager.file_manager = file_manager
    
    # Verify the source file exists
    original_path = file_info['original_path']
    if not os.path.exists(original_path):
        logger.error(f"Source file not found at: {original_path}")
        return False
    
    # Update status to in-progress
    db.update_transcription_status(file_id, 'in-progress')
    
    # Clear previous errors for this file
    db.clear_file_errors(file_id, 'transcription')
    
    # Record file size for debugging
    file_size = os.path.getsize(original_path) if os.path.exists(original_path) else "Unknown"
    logger.info(f"File size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
    
    try:
        # Attempt transcription with verbose logging
        logger.info(f"Starting transcription with extended timeout")
        start_time = time.time()
        
        # Call the transcribe_audio method directly with the right parameters
        # First get the audio path
        audio_path = file_info['original_path']
        
        # Update the TranscriptionManager's internal timeout setting
        transcription_manager.client._request_timeout = 600  # 10 minutes
        
        # Call transcribe_audio with the file information
        success = transcription_manager.transcribe_audio(
            file_id=file_id,
            audio_path=audio_path,
            file_details=file_info
        )
        
        elapsed = time.time() - start_time
        
        if success:
            logger.info(f"Successfully transcribed {file_id} in {elapsed:.2f} seconds")
            
            # Verify the transcript was created
            transcript_path = file_manager.get_transcript_path(file_id)
            if os.path.exists(transcript_path):
                logger.info(f"Transcript created at: {transcript_path} "
                           f"({os.path.getsize(transcript_path)} bytes)")
                return True
            else:
                logger.error(f"Transcription reported success but no transcript file found at: {transcript_path}")
                db.update_transcription_status(file_id, 'failed')
                return False
        else:
            logger.error(f"Failed to transcribe {file_id} after {elapsed:.2f} seconds")
            return False
            
    except Exception as e:
        logger.exception(f"Exception during transcription of {file_id}: {e}")
        db.update_transcription_status(file_id, 'failed')
        db.log_error(file_id, 'transcription', f"Exception: {e}", str(e))
        return False

def main():
    # Verify environment is set up correctly
    if not load_environment():
        logger.error("Failed to load environment variables")
        return 1
    
    # Process each problematic file
    success_count = 0
    error_count = 0
    
    for file_id in PROBLEMATIC_FILE_IDS:
        success = transcribe_problematic_file(file_id)
        if success:
            success_count += 1
        else:
            error_count += 1
    
    logger.info(f"Completed processing problematic files")
    logger.info(f"Success: {success_count}, Errors: {error_count}")
    
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())