#!/usr/bin/env python3
"""
Simple test script to verify subprocess path handling with problematic file paths
"""

import os
import sys
import logging
import subprocess
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

def test_subprocess_paths():
    """Test subprocess path handling for problematic file paths"""
    
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
    
    # Test subprocess handling with ffprobe command
    for path in problematic_paths:
        path_obj = Path(path)
        if path_obj.exists():
            logger.info(f"Testing ffprobe with: {path}")
            try:
                # Use str(path_obj) to ensure proper quoting in subprocess
                ffprobe_cmd = [
                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', str(path_obj)
                ]
                
                logger.debug(f"Running ffprobe command: {' '.join(ffprobe_cmd)}")
                output = subprocess.check_output(ffprobe_cmd)
                duration = float(output.decode().strip())
                logger.info(f"Successfully got duration: {duration} seconds")
            except Exception as e:
                logger.error(f"Error with ffprobe: {e}")

            # Test ffmpeg command for a small segment
            try:
                import tempfile
                temp_dir = tempfile.mkdtemp(prefix="audio_segments_")
                segment_path = Path(temp_dir) / "test_segment.mp3"
                
                # Use str() on Path objects for subprocess to handle quoting correctly
                ffmpeg_cmd = [
                    'ffmpeg', '-v', 'warning', '-i', str(path_obj),
                    '-ss', '0', '-t', '5',  # Just take first 5 seconds
                    '-acodec', 'libmp3lame', '-ab', '192k', '-ar', '44100',
                    '-y', str(segment_path)
                ]
                
                logger.debug(f"Running ffmpeg command: {' '.join(ffmpeg_cmd)}")
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if segment_path.exists():
                    logger.info(f"Successfully created segment: {segment_path} (size: {segment_path.stat().st_size / 1024:.2f} KB)")
                    # Clean up
                    os.remove(segment_path)
                
                # Clean up temp dir
                os.rmdir(temp_dir)
                
            except Exception as e:
                logger.error(f"Error with ffmpeg: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    test_subprocess_paths()