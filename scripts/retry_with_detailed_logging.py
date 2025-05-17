#!/usr/bin/env python3
"""
Retry Transcription with Detailed Logging

This script retries transcription for a specific file with enhanced logging
to capture detailed information from ElevenLabs API responses.

Usage:
    python retry_with_detailed_logging.py --file-id FILE_ID
"""

import os
import sys
import time
import argparse
import json
import requests
from pathlib import Path
import logging
import tempfile
import shutil

# Add core_modules to the Python path
sys.path.append(str(Path(__file__).parent.parent / 'core_modules'))
from log_config import setup_logger
from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

# Set up very detailed logging
logger = setup_logger('elevenlabs_debug', 'elevenlabs_detailed.log', level=logging.DEBUG)

# Import elevenlabs with detailed logging
try:
    import elevenlabs
    from elevenlabs.client import ElevenLabs
    
    # Patch the ElevenLabs speech_to_text method to add detailed logging
    original_speech_to_text = ElevenLabs.speech_to_text
    
    def patched_speech_to_text(self, *args, **kwargs):
        """Patched speech_to_text method with detailed logging"""
        logger.debug(f"ElevenLabs speech_to_text called with args: {args}")
        logger.debug(f"ElevenLabs speech_to_text kwargs: {kwargs}")
        
        try:
            result = original_speech_to_text(self, *args, **kwargs)
            logger.debug(f"ElevenLabs speech_to_text SUCCESS: {result}")
            return result
        except Exception as e:
            logger.error(f"ElevenLabs speech_to_text ERROR: {str(e)}")
            if hasattr(e, 'response') and e.response:
                try:
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error(f"Response headers: {e.response.headers}")
                    logger.error(f"Response content: {e.response.content.decode('utf-8', errors='replace')}")
                except Exception as decode_err:
                    logger.error(f"Error decoding response: {decode_err}")
            else:
                logger.error("No response object available")
            raise
    
    # Apply the patch
    ElevenLabs.speech_to_text = patched_speech_to_text
    logger.info("Successfully patched ElevenLabs speech_to_text method for detailed logging")
    
except ImportError:
    logger.error("Failed to import elevenlabs. Please install with: pip install elevenlabs")
    sys.exit(1)

def get_file_by_id(db, file_id):
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

def reset_file_status(db, file_id):
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
    return False

def retry_transcription(file_id, split_audio=False, segment_duration=600):
    """
    Retry transcription with detailed logging.
    
    Args:
        file_id: ID of file to transcribe
        split_audio: Whether to split audio into segments
        segment_duration: Duration of each segment in seconds
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
        'segment_duration': segment_duration if split_audio else None,
        'api_retries': 3,
        'request_options': {
            'timeout_in_seconds': 600  # 10 minutes timeout
        }
    }
    
    # Connect to database
    db = DatabaseManager('media_tracking.db')
    
    # Get file details
    file = get_file_by_id(db, file_id)
    if not file:
        return False
    
    logger.info(f"Retrying transcription for file: {file['file_id']}")
    logger.info(f"File details: {json.dumps(file, indent=2, default=str)}")
    
    # Create file manager
    file_manager = FileManager(db, config)
    
    # Create transcription manager with extended timeout
    transcription_manager = TranscriptionManager(db, config)
    transcription_manager.set_file_manager(file_manager)
    
    # Reset file status
    if not reset_file_status(db, file_id):
        logger.error(f"Failed to reset status for file {file_id}")
        return False
    
    # Get audio path
    audio_path = file['original_path']
    
    # Log audio file details
    logger.info(f"Audio path: {audio_path}")
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found at {audio_path}")
        return False
    
    file_size = os.path.getsize(audio_path)
    logger.info(f"Audio file size: {file_size / (1024*1024):.2f} MB")
    
    # If splitting audio, create temporary directory
    temp_dir = None
    if split_audio:
        import subprocess
        temp_dir = tempfile.mkdtemp(prefix="split_audio_")
        logger.info(f"Created temporary directory for split audio: {temp_dir}")
        
        # Get audio duration
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True, check=True
            )
            duration = float(result.stdout.strip())
            logger.info(f"Audio duration: {duration:.2f} seconds")
            
            # Calculate number of segments
            num_segments = int(duration / segment_duration) + 1
            logger.info(f"Splitting into {num_segments} segments of {segment_duration} seconds")
            
            # Split audio into segments
            segments = []
            for i in range(num_segments):
                start = i * segment_duration
                segment_path = os.path.join(temp_dir, f"segment_{i:03d}.mp3")
                
                cmd = [
                    "ffmpeg", "-v", "warning", "-i", audio_path,
                    "-ss", str(start), "-t", str(segment_duration),
                    "-acodec", "libmp3lame", "-ab", "192k", "-ar", "44100",
                    "-y", segment_path
                ]
                
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    segments.append((segment_path, start))
                    logger.info(f"Created segment {i+1}/{num_segments}: {segment_path}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error creating segment {i+1}: {e}")
                    if e.stderr:
                        logger.error(f"ffmpeg error: {e.stderr}")
            
            # Process each segment
            all_texts = []
            
            for idx, (segment_path, start_time) in enumerate(segments):
                logger.info(f"Processing segment {idx+1}/{len(segments)} starting at {start_time:.2f}s")
                
                # Verify segment exists and has content
                if not os.path.exists(segment_path) or os.path.getsize(segment_path) == 0:
                    logger.warning(f"Segment {idx+1} is empty or doesn't exist, skipping")
                    continue
                
                try:
                    # Apply additional setup for ElevenLabs API if needed
                    elevenlabs_client = elevenlabs.ElevenLabs(
                        api_key=config['elevenlabs']['api_key']
                    )
                    
                    # Open the audio file
                    with open(segment_path, "rb") as audio_file:
                        # Log attempt
                        logger.info(f"Sending segment {idx+1} to ElevenLabs API")
                        
                        # Make API request with detailed error tracking
                        try:
                            # Call API with all available options for maximum compatibility
                            result = elevenlabs_client.speech_to_text(
                                audio=audio_file,
                                model=config['elevenlabs']['model'],
                                language_detection=True,
                                speakers_count=config['elevenlabs'].get('speaker_count', 32),
                                speakers_detection=config['elevenlabs'].get('speaker_detection', True),
                                word_timestamps=True
                            )
                            
                            # Log success
                            logger.info(f"Successfully transcribed segment {idx+1}")
                            
                            # Store segment text
                            if hasattr(result, 'text') and result.text:
                                all_texts.append(result.text)
                                logger.info(f"Segment {idx+1} text: {result.text[:100]}...")
                            else:
                                logger.warning(f"No text returned for segment {idx+1}")
                                
                        except Exception as e:
                            logger.error(f"Error transcribing segment {idx+1}: {e}")
                            # Try to gather more error details
                            try:
                                logger.error(f"Error type: {type(e).__name__}")
                                logger.error(f"Error attributes: {dir(e)}")
                                if hasattr(e, '__dict__'):
                                    logger.error(f"Error dict: {e.__dict__}")
                            except:
                                pass
                
                except Exception as e:
                    logger.error(f"Error processing segment {idx+1}: {e}")
            
            # Combine all segment texts
            if all_texts:
                full_text = " ".join(all_texts)
                
                # Save combined transcript
                transcript_path = file_manager.get_transcript_path(file_id)
                os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
                
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(full_text)
                
                logger.info(f"Saved combined transcript to {transcript_path}")
                logger.info(f"Transcript length: {len(full_text)} characters")
                
                # Update status
                db.update_status(
                    file_id=file_id,
                    status='completed',
                    transcription_status='completed'
                )
                
                return True
            else:
                logger.error("No text generated from any segment")
                return False
                
        except Exception as e:
            logger.error(f"Error in split audio processing: {e}")
            return False
        finally:
            # Clean up temp directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
    
    # If not splitting, process normally
    else:
        # Start transcription
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
    parser = argparse.ArgumentParser(description="Retry transcription with detailed logging")
    parser.add_argument("--file-id", type=str, required=True,
                        help="ID of file to transcribe")
    parser.add_argument("--split", action="store_true",
                        help="Split audio into segments for processing")
    parser.add_argument("--segment-duration", type=int, default=600,
                        help="Duration of each segment in seconds (default: 600)")
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
    
    logger.info(f"Starting detailed retry for file: {args.file_id}")
    
    # Retry with detailed logging
    if retry_transcription(args.file_id, args.split, args.segment_duration):
        logger.info("Transcription completed successfully")
        return 0
    else:
        logger.error("Transcription failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())