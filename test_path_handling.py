#!/usr/bin/env python3
"""
Test script to verify path handling with problematic files
"""

import os
import sys
import logging
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import required modules
sys.path.append(os.getcwd())  # Ensure the current working directory is in the path
from core_modules.transcription import TranscriptionManager
from db_manager import DatabaseManager
from core_modules.file_manager import FileManager

def test_file_path_handling():
    """Test path handling for problematic file paths"""
    
    # Test files with special characters
    problematic_paths = [
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/_ORIGINAL_SOURCE/Bryan Rigg - new jon 10-9-2023/57c Jürgen Krackow (25% Jew) 14 Nov. 1994 Munich, Ger/side b.mp3",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/_ORIGINAL_SOURCE/Bryan Rigg - D/Audio Tapes Hitler's Jewish Soliers/90 Barry Gourary (Grandson of Rebbe Schneersohn), 18 May & 30 July 2003, NY, USA & Rabbi Chaskel Besser 15 July 2003/side B.mp3"
    ]
    
    # Check if files exist
    for path in problematic_paths:
        path_obj = Path(path)
        if path_obj.exists():
            logger.info(f"File exists: {path}")
            # Test file size calculation
            file_size_mb = path_obj.stat().st_size / (1024 * 1024)
            logger.info(f"File size: {file_size_mb:.2f} MB")
        else:
            logger.error(f"File does not exist: {path}")
    
    # Test subprocess handling with _split_audio_file method
    logger.info("Testing _split_audio_file method with problematic path...")
    
    # Create minimal config for transcription manager
    config = {
        'elevenlabs': {
            'api_key': 'dummy_key',  # We won't actually call the API
            'model': 'scribe_v1',
            'speaker_detection': True,
            'speaker_count': 32
        },
        'output_directory': './output',
        'max_audio_size_mb': 1  # Set to 1 MB to force splitting for testing
    }
    
    # Create database manager - this is just for initialization, we won't use it
    db_path = "./test_db.db"
    db_manager = DatabaseManager(db_path=db_path)
    
    # Create file manager
    file_manager = FileManager(db_manager=db_manager, config=config)
    
    # Create transcription manager
    transcription_manager = TranscriptionManager(db_manager=db_manager, config=config)
    transcription_manager.set_file_manager(file_manager)
    
    # Test the _split_audio_file method
    for path in problematic_paths:
        logger.info(f"Testing _split_audio_file with: {path}")
        try:
            segments = transcription_manager._split_audio_file(path, max_size_mb=1)
            logger.info(f"Successfully split file into {len(segments)} segments")
            for segment_path, start_time in segments:
                logger.info(f"Segment: {segment_path}, Start time: {start_time:.2f}s")
                # Clean up any temporary segment files
                if os.path.exists(segment_path) and segment_path != path:
                    os.remove(segment_path)
                    logger.info(f"Removed temporary segment: {segment_path}")
        except Exception as e:
            logger.error(f"Error splitting file: {e}")
    
    # Clean up temp dirs
    if transcription_manager._split_temp_dir and os.path.exists(transcription_manager._split_temp_dir):
        import shutil
        shutil.rmtree(transcription_manager._split_temp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temporary directory: {transcription_manager._split_temp_dir}")

if __name__ == "__main__":
    test_file_path_handling()