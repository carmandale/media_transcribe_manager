#!/usr/bin/env python3
"""
Test script to verify the timeout fix for ElevenLabs API transcription.
This script attempts to transcribe a single audio file using the updated
TranscriptionManager with extended timeout settings.
"""
import os
import logging
import argparse
from dotenv import load_dotenv
from transcription import TranscriptionManager
from file_manager import FileManager
from db_manager import DatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_timeout')

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test the transcription timeout fix')
    parser.add_argument('--audio_path', required=True, help='Path to the audio file to transcribe')
    parser.add_argument('--db_path', default='./media_tracking.db', help='Path to the database file')
    parser.add_argument('--timeout', type=int, default=300, help='Timeout value in seconds (default: 300)')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Initialize managers
    db_manager = DatabaseManager(args.db_path)
    file_manager = FileManager(db_manager)
    
    # Create config with custom timeout
    config = {
        'force_reprocess': True,  # Force reprocessing even if transcript exists
        'api_timeout': args.timeout  # Pass timeout value to config
    }
    
    # Initialize transcription manager with config
    transcription_manager = TranscriptionManager(
        db_manager=db_manager,
        file_manager=file_manager,
        config=config
    )
    
    # Get audio file info
    audio_path = os.path.abspath(args.audio_path)
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return False
    
    file_basename = os.path.basename(audio_path)
    file_id = file_basename.split('.')[0]  # Use filename without extension as ID
    
    # Create dummy file details for testing
    file_details = {
        'file_id': file_id,
        'file_path': audio_path,
        'detected_language': None,  # Let auto-detection work
        'duration': 0,  # Not needed for this test
    }
    
    # Attempt transcription with the new timeout setting
    logger.info(f"Starting test transcription with {args.timeout} seconds timeout")
    success = transcription_manager.transcribe_audio(
        file_id=file_id,
        audio_path=audio_path,
        file_details=file_details
    )
    
    if success:
        logger.info("✅ Transcription successful! The timeout fix works.")
        transcript_path = file_manager.get_transcript_path(file_id)
        logger.info(f"Transcript saved to: {transcript_path}")
    else:
        logger.error("❌ Transcription failed. Check logs for details.")
    
    return success

if __name__ == '__main__':
    main()
