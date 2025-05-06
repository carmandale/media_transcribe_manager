#!/usr/bin/env python3
"""
Retry Transcription with Verbose Logging

This script retries transcription for a specific file with enhanced logging
to capture detailed information from ElevenLabs API responses.

Usage:
    python retry_with_verbose_logging.py --file-id FILE_ID
"""

import os
import sys
import time
import argparse
import json
import logging
from pathlib import Path
import tempfile
import shutil
import inspect

# Add core_modules to the Python path
sys.path.append(str(Path(__file__).parent.parent / 'core_modules'))
from log_config import setup_logger
from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

# Set up very detailed logging
logging.getLogger('elevenlabs').setLevel(logging.DEBUG)
logger = setup_logger('elevenlabs_debug', 'elevenlabs_detailed.log', level=logging.DEBUG)

# Add file handler for full transcription_monitoring.log
file_handler = logging.FileHandler('logs/transcription_monitoring.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)

# Import elevenlabs with monkey patching for verbose logging
try:
    import elevenlabs
    
    # Set up a request hook for logging
    def log_request_hook(request):
        logger.debug(f"ELEVENLABS API REQUEST: {request.method} {request.url}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        if request.body:
            logger.debug(f"Request body length: {len(request.body)} bytes")
        return request
    
    # Set up a response hook for logging
    def log_response_hook(response):
        logger.debug(f"ELEVENLABS API RESPONSE: Status {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        
        # Try to log response content if it's not too large
        try:
            if len(response.content) < 10000:  # Only log if less than 10KB
                logger.debug(f"Response content: {response.text[:1000]}...")
            else:
                logger.debug(f"Response content length: {len(response.content)} bytes (too large to log)")
        except Exception as e:
            logger.debug(f"Could not log response content: {e}")
        
        return response
    
    # Define a wrapper for the speech to text function
    original_speech_to_text = None
    if hasattr(elevenlabs, 'speech_to_text'):
        original_speech_to_text = elevenlabs.speech_to_text
        
        def speech_to_text_wrapper(audio, model="scribe_v1", **kwargs):
            logger.debug(f"ELEVENLABS speech_to_text CALL")
            logger.debug(f"Audio: {audio.name if hasattr(audio, 'name') else 'Unknown'}")
            logger.debug(f"Model: {model}")
            logger.debug(f"Other parameters: {kwargs}")
            
            try:
                start_time = time.time()
                result = original_speech_to_text(audio, model=model, **kwargs)
                elapsed = time.time() - start_time
                
                logger.debug(f"Speech-to-text SUCCESS in {elapsed:.2f}s")
                if hasattr(result, 'text'):
                    logger.debug(f"Returned text ({len(result.text)} chars): {result.text[:200]}...")
                
                return result
            except Exception as e:
                logger.error(f"ELEVENLABS API ERROR: {type(e).__name__}: {str(e)}")
                if hasattr(e, 'response'):
                    try:
                        logger.error(f"Status code: {e.response.status_code}")
                        logger.error(f"Response headers: {dict(e.response.headers)}")
                        logger.error(f"Response body: {e.response.text[:1000]}")
                    except Exception as detail_err:
                        logger.error(f"Error extracting response details: {detail_err}")
                raise
        
        # Apply the wrapper
        elevenlabs.speech_to_text = speech_to_text_wrapper
        logger.info("Successfully patched elevenlabs.speech_to_text for verbose logging")
    else:
        logger.warning("Could not find elevenlabs.speech_to_text method to patch")
    
except ImportError:
    logger.error("Failed to import elevenlabs. Please install with: pip install elevenlabs")
    sys.exit(1)

def get_file_by_id(db: DatabaseManager, file_id: str):
    """Get file details by ID."""
    query = """
    SELECT m.*, p.*
    FROM media_files m
    JOIN processing_status p ON m.file_id = p.file_id
    WHERE m.file_id = ?
    """
    results = db.execute_query(query, (file_id,))
    if not results:
        logger.error(f"File with ID {file_id} not found")
        return None
    return results[0]

def reset_file_status(db: DatabaseManager, file_id: str):
    """Reset the file status to retry transcription."""
    query = """
    UPDATE processing_status 
    SET transcription_status = 'not_started', 
        status = 'pending',
        last_updated = CURRENT_TIMESTAMP
    WHERE file_id = ?
    """
    affected = db.execute_update(query, (file_id,))
    if affected > 0:
        logger.info(f"Reset status for file {file_id}")
        # Clear any existing errors
        db.execute_update("DELETE FROM errors WHERE file_id = ?", (file_id,))
        return True
    else:
        logger.error(f"Failed to reset status for file {file_id}")
        return False

def retry_transcription(file_id: str, extended_timeout: int = 600, use_original_path: bool = True):
    """
    Retry transcription with verbose logging.
    
    Args:
        file_id: ID of file to transcribe
        extended_timeout: Extended timeout in seconds
        use_original_path: Whether to use the original source path
    """
    # Basic configuration
    config = {
        'output_directory': './output',
        'elevenlabs': {
            'api_key': os.getenv('ELEVENLABS_API_KEY'),
            'model': 'scribe_v1',
            'speaker_detection': True,
            'speaker_count': 32
        },
        'max_audio_size_mb': 25,  # Use the default splitting behavior
        'api_retries': 5,
        'segment_pause': 2,  # Add a longer pause between segments
        'request_options': {
            'timeout_in_seconds': extended_timeout  # Extended timeout
        }
    }
    
    # Connect to database
    db_path = str(Path(__file__).parent.parent / 'media_tracking.db')
    db = DatabaseManager(db_path)
    
    # Get file details
    file = get_file_by_id(db, file_id)
    if not file:
        return False
    
    logger.info(f"Retrying transcription for file: {file['file_id']}")
    logger.info(f"File details: {json.dumps({k: str(v) for k, v in file.items()}, indent=2)}")
    
    # Create file manager
    file_manager = FileManager(db, config)
    
    # Create transcription manager with extended timeout
    transcription_manager = TranscriptionManager(db, config)
    transcription_manager.set_file_manager(file_manager)
    transcription_manager.request_options = {"timeout_in_seconds": extended_timeout}
    
    # Reset file status
    if not reset_file_status(db, file_id):
        return False
    
    # Get audio path
    audio_path = file['original_path']
    
    # If using original path for Jürgen Krackow side b, use the path that works for side a
    if use_original_path and "jurgen_krackow_side_b.mp3" in audio_path:
        # This file was moved to fixed_source but is missing, use the original path instead
        original_path = "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/_ORIGINAL_SOURCE/Bryan Rigg - new jon 10-9-2023/57c Jürgen Krackow (25% Jew) 14 Nov. 1994 Munich, Ger/side b.mp3"
        logger.info(f"Using original path: {original_path} instead of {audio_path}")
        audio_path = original_path
    
    # Check if audio file exists
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found at {audio_path}")
        return False
    
    # Log audio file details
    file_size = os.path.getsize(audio_path)
    logger.info(f"Audio file size: {file_size / (1024*1024):.2f} MB")
    
    # Start transcription
    logger.info(f"Starting transcription with {extended_timeout}s timeout")
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
            logger.info(f"Transcript created at: {transcript_path}")
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"Transcript length: {len(content)} characters")
            logger.info(f"Transcript starts with: {content[:200]}...")
            return True
        else:
            logger.warning(f"Transcription marked successful but file not found at: {transcript_path}")
            return False
    else:
        logger.error(f"Failed to transcribe {file_id} after {elapsed:.2f} seconds")
        return False

def main():
    parser = argparse.ArgumentParser(description="Retry transcription with verbose logging")
    parser.add_argument("--file-id", type=str, required=True,
                        help="ID of file to transcribe")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Extended timeout in seconds (default: 600)")
    parser.add_argument("--use-original-path", action="store_true", default=True,
                        help="Use original source path for audio files")
    args = parser.parse_args()
    
    # Ensure environment variables are loaded
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("dotenv not available, using environment variables as is")
    
    # Check ElevenLabs API key
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        logger.error("ELEVENLABS_API_KEY not found in environment")
        return 1
    
    # Log API key (masked)
    masked_key = f"{api_key[:5]}...{api_key[-5:]}" if len(api_key) > 10 else "***"
    logger.info(f"Using ElevenLabs API key: {masked_key}")
    
    logger.info(f"Starting verbose retry for file: {args.file_id}")
    
    # Retry with verbose logging
    if retry_transcription(args.file_id, args.timeout, args.use_original_path):
        logger.info("Transcription completed successfully")
        return 0
    else:
        logger.error("Transcription failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())