#!/usr/bin/env python3
"""
Script to retry transcription for the two problematic files with fixed path handling
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("retry_transcription.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import required modules
sys.path.append(os.getcwd())  # Ensure the current working directory is in the path
from core_modules.db_manager import DatabaseManager
from core_modules.transcription import TranscriptionManager
from core_modules.file_manager import FileManager
from scripts.load_env import load_env_vars

def retry_problematic_files():
    """Retry transcription for problematic files with fixed path handling"""
    
    # Load environment variables
    load_env_vars()
    
    # Setup basic config
    config = {
        'elevenlabs': {
            'api_key': os.getenv('ELEVENLABS_API_KEY'),
            'model': 'scribe_v1',
            'speaker_detection': True,
            'speaker_count': 32
        },
        'output_directory': './output',
        'db_path': './media_tracking.db'
    }
    
    # Create database connection
    db_path = config.get('db_path', './media_tracking.db')
    db_manager = DatabaseManager(db_path=db_path)
    
    # Problematic file IDs - replace with actual IDs from your database
    file_ids = [
        "0e39bce9-8fa7-451a-8a50-5a9f8fc4493f",  # Jürgen Krackow file
        "4a7415b3-31f8-40a8-b326-5092c0b05a81"   # Barry Gourary file
    ]
    
    # Confirm these files exist in the database
    for file_id in file_ids:
        file_details = db_manager.get_file_status(file_id)
        if not file_details:
            logger.error(f"File ID not found in database: {file_id}")
            continue
            
        logger.info(f"Found file in database: {file_id}")
        
        # Show original path
        original_path = file_details['original_path']
        logger.info(f"Original path: {original_path}")
        
        # Check if file exists
        path_obj = Path(original_path)
        if not path_obj.exists():
            logger.error(f"File does not exist at original path: {original_path}")
            continue
            
        logger.info(f"File exists. Size: {path_obj.stat().st_size / (1024 * 1024):.2f} MB")
        
        # Mark as pending for re-transcription
        db_manager.update_status(
            file_id=file_id,
            status='pending',
            transcription_status='not_started',
            qa_status=None,
            qa_result=None,
            error_count=0
        )
        logger.info(f"Reset status for file: {file_id}")
    
    # Create the file manager and transcription manager
    file_manager = FileManager(db_manager=db_manager, config=config)
    transcription_manager = TranscriptionManager(
        db_manager=db_manager, 
        config=config,
        auto_detect_language=True
    )
    transcription_manager.set_file_manager(file_manager)
    
    # Process each file
    for file_id in file_ids:
        file_details = db_manager.get_file_status(file_id)
        if not file_details:
            continue
            
        # Get audio path
        audio_path = file_details['original_path']
        logger.info(f"Starting transcription for: {file_id}")
        logger.info(f"Audio path: {audio_path}")
        
        try:
            # Transcribe the file
            success = transcription_manager.transcribe_audio(
                file_id=file_id,
                audio_path=audio_path,
                file_details=file_details
            )
            
            if success:
                logger.info(f"Successfully transcribed file: {file_id}")
            else:
                logger.error(f"Failed to transcribe file: {file_id}")
                
        except Exception as e:
            logger.error(f"Exception during transcription of {file_id}: {e}", exc_info=True)

if __name__ == "__main__":
    retry_problematic_files()