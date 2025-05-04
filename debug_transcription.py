#!/usr/bin/env python3
"""
Debug Transcription Issues

This script helps diagnose specific issues with transcription failures by:
1. Selecting a problematic file
2. Attempting to process it with extra debug logging
3. Verifying file integrity and format
4. Checking temporary directories and file paths
5. Testing file access and permissions

Usage:
    python debug_transcription.py [--file-id FILE_ID]
"""

import os
import sys
import logging
import argparse
import subprocess
import random
from pathlib import Path
import time
import tempfile
import shutil
import json
from typing import Optional, Dict, Any, List, Tuple

from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager
import elevenlabs

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_transcription.log')
    ]
)

logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from file or use defaults."""
    # Get API key from environment or use hardcoded value if not available
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("Warning: ELEVENLABS_API_KEY not found in environment, using hardcoded key")
        api_key = "sk_e067dc46fad47e2ef355ba909b7ad5ff938c0b1d6cf63e43"
    
    config = {
        'output_directory': './output',
        'elevenlabs': {
            'api_key': api_key,
            'model': 'scribe_v1', 
            'speaker_detection': True,
            'speaker_count': 32
        },
        'max_audio_size_mb': 25,
        'api_retries': 8,
        'segment_pause': 1,
        'force_reprocess': True  # Force reprocessing for debug purposes
    }
    
    print(f"API key configured: {api_key[:5]}...{api_key[-5:]}")
    return config

def get_problematic_file(db: DatabaseManager, file_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get a problematic file to debug."""
    if file_id:
        file = db.get_file_status(file_id)
        if not file:
            logger.error(f"File with ID {file_id} not found in database")
            return None
        return file
    
    # If no file_id provided, select a random file with transcription errors
    query = """
    SELECT ps.* 
    FROM processing_status ps
    JOIN errors e ON ps.file_id = e.file_id
    WHERE 
        e.process_stage = 'transcription'
        AND ps.transcription_status IN ('failed', 'not_started')
    ORDER BY RANDOM()
    LIMIT 1
    """
    
    results = db.execute_query(query)
    if not results:
        logger.error("No files with transcription errors found")
        return None
    
    return results[0]

def verify_file_integrity(file_path: str) -> Tuple[bool, str]:
    """Verify file integrity using ffprobe."""
    try:
        # Run ffprobe to check file integrity
        cmd = [
            'ffprobe', '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return False, f"FFprobe error: {result.stderr}"
        
        # Check if duration is valid
        try:
            duration = float(result.stdout.strip())
            if duration <= 0:
                return False, f"Invalid duration: {duration} seconds"
        except ValueError:
            return False, f"Could not parse duration: {result.stdout}"
        
        return True, f"File valid, duration: {duration} seconds"
        
    except Exception as e:
        return False, f"Error checking file: {str(e)}"

def test_api_access():
    """Test ElevenLabs API access."""
    try:
        # Get API key from environment or use hardcoded value if not available
        api_key = os.getenv('ELEVENLABS_API_KEY')
        if not api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment, using hardcoded key")
            api_key = "sk_e067dc46fad47e2ef355ba909b7ad5ff938c0b1d6cf63e43"
            
        client = elevenlabs.ElevenLabs(api_key=api_key)
        
        # Check if speech_to_text is available
        if hasattr(client, 'speech_to_text'):
            logger.info("Speech-to-text API available")
            return True, "API connection successful, speech_to_text is available"
        else:
            logger.warning("Speech-to-text API not available on client")
            return False, "API connected but speech_to_text not available"
            
    except Exception as e:
        logger.error(f"API connection error: {str(e)}")
        return False, f"API connection failed: {str(e)}"

def test_transcription(file_id: str, audio_path: str, db: DatabaseManager, config: Dict[str, Any]) -> bool:
    """Test a single transcription with debug logging."""
    # Create test directories
    temp_dir = tempfile.mkdtemp(prefix="debug_transcription_")
    
    # Create test managers with debug config
    debug_config = config.copy()
    debug_config['output_directory'] = temp_dir
    
    try:
        # Initialize managers
        file_manager = FileManager(db, debug_config)
        transcription_manager = TranscriptionManager(db, debug_config)
        transcription_manager.set_file_manager(file_manager)
        
        # Create detailed testing record
        logger.info(f"Testing transcription for file: {file_id}")
        logger.info(f"Audio path: {audio_path}")
        logger.info(f"Audio file exists: {os.path.exists(audio_path)}")
        
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path) / (1024 * 1024)
            logger.info(f"Audio file size: {file_size:.2f} MB")
            
            # Check file integrity
            valid, message = verify_file_integrity(audio_path)
            logger.info(f"File integrity check: {message}")
            
            if valid:
                # Try transcription with a short timeout
                try:
                    # Get file metadata
                    file_details = db.get_file_status(file_id)
                    
                    # Create clean test entry in the database
                    test_id = f"test_{int(time.time())}_{file_id[-8:]}"
                    logger.info(f"Using test file ID: {test_id}")
                    
                    # Do quick test with small time segment
                    # Extract a 5-second clip for testing
                    test_clip_path = os.path.join(temp_dir, f"test_clip_{file_id}.mp3")
                    extract_cmd = [
                        'ffmpeg', '-v', 'warning', 
                        '-i', audio_path,
                        '-ss', '0', '-t', '5',  # Extract first 5 seconds
                        '-acodec', 'libmp3lame', '-ab', '192k', '-ar', '44100',
                        '-y', test_clip_path
                    ]
                    
                    logger.info(f"Extracting test clip with command: {' '.join(extract_cmd)}")
                    subprocess.run(extract_cmd, check=True)
                    
                    logger.info(f"Test clip created at: {test_clip_path}")
                    logger.info(f"Test clip exists: {os.path.exists(test_clip_path)}")
                    logger.info(f"Test clip size: {os.path.getsize(test_clip_path) / 1024:.2f} KB")
                    
                    # Test API access
                    api_ok, api_message = test_api_access()
                    logger.info(f"API test: {api_message}")
                    
                    if api_ok and os.path.exists(test_clip_path) and os.path.getsize(test_clip_path) > 0:
                        # Test transcription of small clip
                        logger.info("Testing transcription with small clip...")
                        
                        # Make sure API key is explicitly set in the transcription manager
                        # This is an additional safeguard
                        if not transcription_manager.api_key:
                            logger.warning("API key not set in transcription manager, setting it manually")
                            transcription_manager.api_key = "sk_e067dc46fad47e2ef355ba909b7ad5ff938c0b1d6cf63e43"
                            transcription_manager.client = elevenlabs.ElevenLabs(api_key=transcription_manager.api_key)
                        
                        # Use the original transcribe_audio method with our test parameters
                        result = transcription_manager.transcribe_audio(
                            file_id=test_id,
                            audio_path=test_clip_path,
                            file_details=file_details
                        )
                        
                        if result:
                            logger.info("Test transcription successful")
                            return True
                        else:
                            logger.error("Test transcription failed")
                    
                except Exception as e:
                    logger.error(f"Error during test transcription: {str(e)}")
        
        return False
    
    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Debug transcription issues")
    parser.add_argument("--file-id", help="Specific file ID to debug")
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    
    # Connect to database
    db = DatabaseManager('media_tracking.db')
    
    # Get file manager
    file_manager = FileManager(db, config)
    
    # Get a problematic file
    file = get_problematic_file(db, args.file_id)
    if not file:
        logger.error("No file selected for debugging")
        return
    
    file_id = file['file_id']
    logger.info(f"Selected file for debugging: {file_id}")
    
    # Get file details
    logger.info(f"File details: {json.dumps(file, indent=2)}")
    
    # Get audio path
    audio_path = file_manager.get_audio_path(file_id)
    if not audio_path:
        logger.error(f"Audio path not found for file: {file_id}")
        return
    
    # Check file existence
    if not os.path.exists(audio_path):
        logger.error(f"Audio file does not exist: {audio_path}")
        
        # Check original path
        original_path = file.get('original_path')
        if original_path:
            logger.info(f"Checking original path: {original_path}")
            if os.path.exists(original_path):
                logger.info(f"Original file exists: {original_path}")
            else:
                logger.error(f"Original file missing: {original_path}")
        return
    
    # Check file errors in database
    error_query = """
    SELECT * FROM errors
    WHERE file_id = ?
    ORDER BY timestamp DESC
    """
    errors = db.execute_query(error_query, [file_id])
    if errors:
        logger.info(f"Found {len(errors)} errors for this file:")
        for error in errors:
            logger.info(f"  {error['timestamp']} - {error['process_stage']} - {error['error_message']}")
            logger.info(f"  Details: {error['error_details']}")
    
    # Test transcription
    success = test_transcription(file_id, audio_path, db, config)
    
    if success:
        logger.info("Transcription test was successful, file should be able to be transcribed")
        
        # Reset transcription status to try again
        logger.info(f"Resetting transcription status for file: {file_id}")
        db.update_status(
            file_id=file_id,
            status='pending',
            transcription_status='not_started'
        )
    else:
        logger.error("Transcription test failed, file may have format issues")

if __name__ == "__main__":
    main()