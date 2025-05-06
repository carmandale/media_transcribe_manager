#!/usr/bin/env python3
"""
Script to directly transcribe problematic files using ElevenLabs API.
This script bypasses the database and directly transcribes the files.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import time
import json
import argparse
from pathlib import Path
import logging
import datetime
import dotenv

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("direct_transcribe.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()

# Check for ElevenLabs API key
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
if not ELEVENLABS_API_KEY:
    logger.error("ElevenLabs API key not found in environment variables")
    print("ElevenLabs API key (ELEVENLABS_API_KEY) not found.")
    print("Please set it in your environment or .env file.")
    sys.exit(1)

# Import ElevenLabs
try:
    from elevenlabs import ElevenLabs
    from elevenlabs.core.api_error import ApiError
except ImportError:
    logger.error("ElevenLabs Python SDK not installed")
    print("Please install ElevenLabs Python SDK: pip install elevenlabs==0.2.26")
    sys.exit(1)

# Problematic files
PROBLEMATIC_FILES = [
    {
        "file_id": "0e39bce9-8fa7-451a-8a50-5a9f8fc4493f",
        "path": "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/_ORIGINAL_SOURCE/Bryan Rigg - new jon 10-9-2023/57c Jürgen Krackow (25% Jew) 14 Nov. 1994 Munich, Ger/side b.mp3",
        "name": "jurgen_krackow_side_b.mp3"
    },
    {
        "file_id": "4a7415b3-31f8-40a8-b326-5092c0b05a81",
        "path": "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/_ORIGINAL_SOURCE/Bryan Rigg - D/Audio Tapes Hitler's Jewish Soliers/90 Barry Gourary (Grandson of Rebbe Schneersohn), 18 May & 30 July 2003, NY, USA & Rabbi Chaskel Besser 15 July 2003/side B.mp3",
        "name": "barry_gourary_side_b.mp3"
    }
]

OUTPUT_DIR = "./output"
TRANSCRIPT_DIR = os.path.join(OUTPUT_DIR, "transcripts")
SUBTITLE_DIR = os.path.join(OUTPUT_DIR, "subtitles/orig")

def _split_audio_file(audio_path: str, max_size_mb: int = 25) -> list:
    """
    Split a large audio file into smaller segments if it exceeds max_size_mb.
    Returns a list of tuples (segment_path, start_time_seconds).
    """
    # Convert to Path object for robust path handling
    path_obj = Path(audio_path)
    split_temp_dir = None
    
    if not path_obj.exists():
        logger.error(f"Audio file not found for splitting: {audio_path}")
        return []
        
    file_size_mb = path_obj.stat().st_size / (1024 * 1024)
    if file_size_mb <= max_size_mb:
        return [(str(path_obj), 0.0)]
        
    try:
        # Create temporary directory for segments
        split_temp_dir = tempfile.mkdtemp(prefix="audio_segments_")
        logger.info(f"Created temporary directory for segments: {split_temp_dir}")
        
        # Use str(path_obj) to ensure proper quoting in subprocess
        # Get total duration via ffprobe
        ffprobe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(path_obj)
        ]
        
        logger.debug(f"Running ffprobe command: {' '.join(ffprobe_cmd)}")
        output = subprocess.check_output(ffprobe_cmd)
        duration = float(output.decode().strip())
        logger.debug(f"Detected duration: {duration} seconds")
        
        # Determine number of segments
        num_segments = int(file_size_mb / max_size_mb) + 1
        segment_duration = duration / num_segments
        
        # Cap each segment to 10 minutes to avoid oversized chunks
        MAX_SEGMENT_SECONDS = 600  # 10 minutes
        if segment_duration > MAX_SEGMENT_SECONDS:
            num_segments = int(duration / MAX_SEGMENT_SECONDS) + 1
            segment_duration = duration / num_segments
            
        logger.info(f"Splitting into {num_segments} segments of ~{segment_duration:.2f} seconds each")
            
        segments = []
        for i in range(num_segments):
            start = i * segment_duration
            segment_path = Path(split_temp_dir) / f"segment_{i:03d}.mp3"
            
            if i < num_segments - 1:
                duration_arg = ['-t', str(segment_duration)]
            else:
                duration_arg = []
                
            # Use str() on Path objects for subprocess to handle quoting correctly
            ffmpeg_cmd = [
                'ffmpeg', '-v', 'warning', '-i', str(path_obj),
                '-ss', str(start), *duration_arg,
                '-acodec', 'libmp3lame', '-ab', '192k', '-ar', '44100',
                '-y', str(segment_path)
            ]
            
            try:
                logger.debug(f"Running ffmpeg command for segment {i}: {' '.join(ffmpeg_cmd)}")
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                segments.append((str(segment_path), start))
                logger.info(f"Created segment {i+1}/{num_segments}: {segment_path}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error creating audio segment {i}: {e}")
                if e.stderr:
                    logger.error(f"FFMPEG error: {e.stderr.decode('utf-8', errors='replace')}")
                    
        logger.info(f"Split audio into {len(segments)} segments")
        return segments
    
    except Exception as e:
        logger.error(f"Error during audio split preparation: {e}")
        if split_temp_dir:
            try:
                shutil.rmtree(split_temp_dir, ignore_errors=True)
            except:
                pass
        return []

def _format_timestamp_for_srt(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (00:00:00,000)."""
    time_obj = datetime.timedelta(seconds=seconds)
    
    # Calculate hours, minutes, seconds
    hours, remainder = divmod(int(time_obj.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Get milliseconds
    milliseconds = int((time_obj.total_seconds() % 1) * 1000)
    
    # Format the timestamp for SRT
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def create_srt_subtitles(transcription) -> str:
    """Create SRT subtitle file from a transcription."""
    if not hasattr(transcription, 'words') or not transcription.words:
        logger.warning("Transcription does not have word-level timestamps for SRT creation")
        return ""
    
    srt_lines = []
    subtitle_index = 1
    current_line = []
    start_time = None
    
    # Maximum number of characters per subtitle
    MAX_CHARS = 40
    # Maximum duration for a single subtitle (in seconds)
    MAX_DURATION = 5.0
    
    for word in transcription.words:
        # Skip words without timing info
        if not hasattr(word, 'start') or not hasattr(word, 'end'):
            continue
            
        # Initialize subtitle with first word
        if not current_line:
            start_time = word.start
            current_line.append(word.text)
            continue
            
        # Calculate current subtitle length
        current_text = ' '.join(current_line)
        new_text = f"{current_text} {word.text}"
            
        # Check if adding this word would exceed our constraints
        current_duration = word.end - start_time
        if (len(new_text) > MAX_CHARS or current_duration > MAX_DURATION):
            # Finalize current subtitle
            subtitle_text = current_text
            end_time = word.start  # End time of previous word
            
            # Add completed subtitle
            srt_lines.append(str(subtitle_index))
            srt_lines.append(f"{_format_timestamp_for_srt(start_time)} --> {_format_timestamp_for_srt(end_time)}")
            srt_lines.append(subtitle_text)
            srt_lines.append("")  # Empty line between subtitles
            
            # Start new subtitle
            subtitle_index += 1
            current_line = [word.text]
            start_time = word.start
        else:
            # Add word to current line
            current_line.append(word.text)
    
    # Don't forget the last subtitle
    if current_line and start_time is not None:
        last_word = transcription.words[-1]
        subtitle_text = ' '.join(current_line)
        
        srt_lines.append(str(subtitle_index))
        srt_lines.append(f"{_format_timestamp_for_srt(start_time)} --> {_format_timestamp_for_srt(last_word.end)}")
        srt_lines.append(subtitle_text)
        srt_lines.append("")  # Empty line at the end
    
    return '\n'.join(srt_lines)

def transcribe_audio(file_info: dict, api_key: str = None) -> bool:
    """Transcribe an audio file using ElevenLabs Speech-to-Text API."""
    file_id = file_info["file_id"]
    audio_path = file_info["path"]
    file_name = file_info["name"]
    
    # Create output directories if they don't exist
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    os.makedirs(SUBTITLE_DIR, exist_ok=True)
    
    # Set up output paths
    transcript_path = Path(TRANSCRIPT_DIR) / f"{file_id}_{file_name}.txt"
    json_path = transcript_path.with_suffix('.json')
    srt_path = Path(SUBTITLE_DIR) / f"{file_id}_{file_name}.srt"
    
    logger.info(f"Starting transcription for: {file_name}")
    logger.info(f"Audio path: {audio_path}")
    logger.info(f"Transcript will be saved to: {transcript_path}")
    
    # Check if the file exists
    path_obj = Path(audio_path)
    if not path_obj.exists():
        logger.error(f"Audio file not found: {audio_path}")
        return False
    
    # Initialize ElevenLabs client
    client = ElevenLabs(api_key=api_key or ELEVENLABS_API_KEY)
    
    # Check for large audio files and split if necessary
    max_size_mb = 25
    file_size_mb = path_obj.stat().st_size / (1024 * 1024)
    
    # Split audio if needed
    split_temp_dir = None
    if file_size_mb > max_size_mb:
        logger.info(f"Audio file size {file_size_mb:.2f}MB exceeds {max_size_mb}MB, splitting into segments...")
        segments = _split_audio_file(audio_path, max_size_mb)
        if not segments:
            logger.error("Audio splitting failed, aborting transcription.")
            return False
            
        logger.info(f"File split into {len(segments)} segments")
        
        # Prepare for combined results
        all_texts = []
        all_words = []
        combined_json = []
        
        # Transcribe each segment with retry on transient API errors
        max_retries = 8
        for seg_path, seg_start in segments:
            logger.info(f"Transcribing segment starting at {seg_start:.2f}s: {seg_path}")
            with open(seg_path, 'rb') as audio_file:
                api_params = {
                    "file": audio_file,
                    "model_id": "scribe_v1",
                    "tag_audio_events": True,
                    "diarize": True,  # Enable speaker detection
                    "timestamps_granularity": "word"
                }
                
                # Use German as default language for these files
                api_params["language_code"] = "deu"
                
                # Request options with extended timeout
                request_options = {"timeout_in_seconds": 300}
                
                # Attempt transcription with retries
                for attempt in range(max_retries):
                    try:
                        logger.info(f"API request attempt {attempt+1}/{max_retries}")
                        transcription_seg = client.speech_to_text.convert(**api_params, request_options=request_options)
                        break
                    except ApiError as e:
                        if attempt < max_retries - 1:
                            backoff = min(2 ** attempt, 60)  # cap backoff at 60s
                            logger.warning(f"API error on segment (attempt {attempt+1}/{max_retries}): {e}. Retrying in {backoff}s...")
                            time.sleep(backoff)
                            continue
                        logger.error(f"API error on segment after {max_retries} attempts: {e}")
                        return False
                    except Exception as e:
                        logger.error(f"Unexpected error: {e}")
                        return False
                        
                # Validate segment response
                if not transcription_seg or not getattr(transcription_seg, 'text', None):
                    logger.error(f"Transcription returned no text for segment at {seg_start:.2f}s")
                    return False
                    
                # Accumulate results
                all_texts.append(transcription_seg.text)
                combined_json.append(transcription_seg.dict())
                if hasattr(transcription_seg, 'words'):
                    for w in transcription_seg.words:
                        new_w = w.model_copy(update={
                            'start': w.start + seg_start,
                            'end': w.end + seg_start
                        })
                        all_words.append(new_w)
                        
                # Brief pause between segments
                time.sleep(1)
                
        # Get path to split temp dir from first segment
        if segments and segments[0][0]:
            split_temp_dir = os.path.dirname(segments[0][0])
                
        # Combine and save full transcript
        full_text = " ".join(all_texts)
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(full_text, encoding='utf-8')
        logger.info(f"Combined transcript saved to: {transcript_path}")
        
        # Save combined JSON
        json_path.write_text(json.dumps(combined_json, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info(f"Combined JSON saved to: {json_path}")
        
        # Generate SRT from combined words
        if all_words:
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            fake = type('T', (object,), {'words': all_words})
            srt_content = create_srt_subtitles(fake)
            srt_path.write_text(srt_content, encoding='utf-8')
            logger.info(f"SRT subtitles saved to: {srt_path}")
    else:
        # Transcribe small file directly
        logger.info(f"Transcribing file directly (size: {file_size_mb:.2f}MB)")
        try:
            with open(audio_path, 'rb') as audio_file:
                # Prepare API params
                api_params = {
                    "file": audio_file,
                    "model_id": "scribe_v1",
                    "tag_audio_events": True,
                    "diarize": True,  # Enable speaker detection
                    "timestamps_granularity": "word",
                    "language_code": "deu"  # Use German as default
                }
                
                # Request options with extended timeout
                request_options = {"timeout_in_seconds": 300}
                
                # Transcribe with retry on transient API errors
                max_retries = 8
                for attempt in range(max_retries):
                    try:
                        logger.info(f"API request attempt {attempt+1}/{max_retries}")
                        transcription = client.speech_to_text.convert(**api_params, request_options=request_options)
                        break
                    except ApiError as e:
                        if attempt < max_retries - 1:
                            backoff = min(2 ** attempt, 60)  # cap backoff at 60s
                            logger.warning(f"API error (attempt {attempt+1}/{max_retries}): {e}. Retrying in {backoff}s...")
                            time.sleep(backoff)
                            continue
                        logger.error(f"API error after {max_retries} attempts: {e}")
                        return False
                    except Exception as e:
                        logger.error(f"Unexpected error: {e}")
                        return False
                
                # Check if transcription was successful
                if not transcription or not hasattr(transcription, 'text') or not transcription.text:
                    logger.error("Failed to get transcription text")
                    return False
                    
                # Store the transcription JSON
                transcription_json = json.dumps(transcription.dict(), ensure_ascii=False, indent=2)
                logger.debug(f"Transcription response: {transcription_json[:100]}...")
                
                # Save the transcription text to file
                transcript_path.parent.mkdir(parents=True, exist_ok=True)
                transcript_path.write_text(transcription.text, encoding='utf-8')
                logger.info(f"Transcription saved to: {transcript_path}")
                
                # Save full transcription response to a JSON file
                json_path.write_text(transcription_json, encoding='utf-8')
                logger.info(f"Saved full transcription JSON to: {json_path}")
                
                # Create SRT subtitles if available
                if hasattr(transcription, 'words') and transcription.words:
                    srt_path.parent.mkdir(parents=True, exist_ok=True)
                    srt_content = create_srt_subtitles(transcription)
                    srt_path.write_text(srt_content, encoding='utf-8')
                    logger.info(f"SRT subtitles saved to: {srt_path}")
                
        except Exception as e:
            logger.error(f"Error transcribing audio {audio_path}: {e}")
            return False
    
    # Clean up split segments
    if split_temp_dir and os.path.exists(split_temp_dir):
        try:
            shutil.rmtree(split_temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary audio segments: {split_temp_dir}")
        except:
            pass
    
    logger.info(f"Transcription completed for: {file_name}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Transcribe problematic files directly')
    parser.add_argument('--file', type=int, choices=[0, 1], help='Select file to transcribe (0 for Jürgen Krackow, 1 for Barry Gourary)')
    args = parser.parse_args()
    
    # Print available files
    print("Available problematic files:")
    for i, file in enumerate(PROBLEMATIC_FILES):
        print(f"[{i}] {file['name']} - {file['path']}")
    
    # Process specific file if provided, otherwise both
    files_to_process = [PROBLEMATIC_FILES[args.file]] if args.file is not None else PROBLEMATIC_FILES
    
    # Transcribe each file
    for file_info in files_to_process:
        print(f"\nProcessing: {file_info['name']}")
        success = transcribe_audio(file_info)
        if success:
            print(f"✅ Successfully transcribed {file_info['name']}")
        else:
            print(f"❌ Failed to transcribe {file_info['name']}")
    
    print("\nTranscription complete!")

if __name__ == "__main__":
    main()