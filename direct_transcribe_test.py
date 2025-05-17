#!/usr/bin/env python3
"""
Script to directly test transcription of problematic files without imports
"""

import os
import sys
import subprocess
import tempfile
import shutil
import time
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("direct_transcribe_test.log")
    ]
)
logger = logging.getLogger(__name__)

# Problematic file paths
problematic_paths = [
    "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/_ORIGINAL_SOURCE/Bryan Rigg - new jon 10-9-2023/57c Jürgen Krackow (25% Jew) 14 Nov. 1994 Munich, Ger/side b.mp3",
    "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/_ORIGINAL_SOURCE/Bryan Rigg - D/Audio Tapes Hitler's Jewish Soliers/90 Barry Gourary (Grandson of Rebbe Schneersohn), 18 May & 30 July 2003, NY, USA & Rabbi Chaskel Besser 15 July 2003/side B.mp3"
]

def test_split_audio_file(audio_path):
    """
    Split a large audio file into smaller segments if needed.
    """
    # Convert to Path object for robust path handling
    path_obj = Path(audio_path)
    
    if not path_obj.exists():
        logger.error(f"Audio file not found for splitting: {audio_path}")
        return False
        
    # Create temporary directory for segments
    temp_dir = tempfile.mkdtemp(prefix="audio_segments_")
    logger.info(f"Created temporary directory: {temp_dir}")
    
    try:
        # Use str(path_obj) to ensure proper quoting in subprocess
        # Get total duration via ffprobe
        ffprobe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(path_obj)
        ]
        
        logger.debug(f"Running ffprobe command: {' '.join(ffprobe_cmd)}")
        output = subprocess.check_output(ffprobe_cmd)
        duration = float(output.decode().strip())
        logger.info(f"Detected duration: {duration} seconds")
        
        # Create a 10-second test segment
        test_segment_path = Path(temp_dir) / "test_segment.mp3"
        ffmpeg_cmd = [
            'ffmpeg', '-v', 'warning', '-i', str(path_obj),
            '-ss', '0', '-t', '10',  # Just take first 10 seconds
            '-acodec', 'libmp3lame', '-ab', '192k', '-ar', '44100',
            '-y', str(test_segment_path)
        ]
        
        logger.debug(f"Running ffmpeg command: {' '.join(ffmpeg_cmd)}")
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if test_segment_path.exists():
            logger.info(f"Successfully created test segment: {test_segment_path}")
            logger.info(f"File size: {test_segment_path.stat().st_size / 1024:.2f} KB")
            return True
            
    except Exception as e:
        logger.error(f"Error processing audio file: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up directory {temp_dir}: {e}")
    
    return False

if __name__ == "__main__":
    logger.info("Starting direct transcription test...")
    
    for path in problematic_paths:
        logger.info(f"Testing file: {path}")
        path_obj = Path(path)
        
        if path_obj.exists():
            logger.info(f"File exists: {path}")
            logger.info(f"File size: {path_obj.stat().st_size / (1024 * 1024):.2f} MB")
            
            if test_split_audio_file(path):
                logger.info(f"Successfully processed test segment for {path}")
            else:
                logger.error(f"Failed to process test segment for {path}")
        else:
            logger.error(f"File not found: {path}")
    
    logger.info("Test completed.")