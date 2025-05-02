#!/usr/bin/env python3
"""
Retry failed transcriptions
---------------------------
This script attempts to retry transcription for specific files that previously failed
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)))
import logging
import yaml
from pathlib import Path

from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('retry_transcription.log')
    ]
)
logger = logging.getLogger('retry_transcription')

def main():
    """Retry transcription for failed files"""
    # Load configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize database manager
    db_path = config.get('database', {}).get('path', 'media_tracking.db')
    db_manager = DatabaseManager(db_path)
    
    # Initialize file manager
    file_manager = FileManager(config)
    
    # Initialize transcription manager
    transcription_manager = TranscriptionManager(db_manager, config)
    transcription_manager.set_file_manager(file_manager)
    
    # Get specific file IDs to retry (from command-line arguments or hardcoded)
    file_ids = []
    if len(sys.argv) > 1:
        file_ids = sys.argv[1:]
    else:
        # Hardcoded example file IDs (from our query)
        file_ids = [
            "56bdb14e-908b-4f27-9c44-677367b802a9",  # CSPAN Hitler's Jewish Soldiers
            "3f6f8936-8aae-4ed9-92fc-eca877ed037a",  # Hide in Plain Sight
            "a15c39e2-73d2-4cb0-a706-e0c3bfd65a34"   # Die Soldater mit - halben Strn
        ]
    
    # Process each file
    for file_id in file_ids:
        # Get file details
        file_details = db_manager.get_file_details(file_id)
        if not file_details:
            logger.error(f"File ID not found in database: {file_id}")
            continue
        
        # Reset transcription status to 'not_started'
        db_manager.update_status(
            file_id=file_id,
            transcription_status='not_started'
        )
        
        logger.info(f"Retrying transcription for: {file_details['original_path']}")
        
        # Get audio path from the file manager
        audio_path = file_manager.get_audio_path(file_id)
        if not audio_path:
            logger.error(f"Audio file not found for {file_id}")
            continue
        
        # Verify the audio file exists
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found at path: {audio_path}")
            continue
            
        # Perform transcription
        if transcription_manager.transcribe_audio(file_id, audio_path, file_details):
            logger.info(f"Successfully transcribed: {file_id}")
        else:
            logger.error(f"Failed to transcribe: {file_id}")

if __name__ == "__main__":
    main()
