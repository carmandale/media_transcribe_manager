#!/usr/bin/env python3
"""
Transcription Manager for Media Transcription and Translation Tool
------------------------------------------------------------------
Handles all transcription operations including:
- Audio transcription using ElevenLabs Scribe API
- Transcription format management
- SRT subtitle generation
"""

import os
import logging
import json
import time
import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import re
import math  # needed for splitting logic

import time
try:
    from elevenlabs.core.api_error import ApiError
except ImportError:
    class ApiError(Exception):
        """Stub for ElevenLabs API errors."""
        pass

try:
    import requests
except ImportError:
    requests = None
import subprocess
import tempfile
import shutil
try:
    from tqdm import tqdm
except ImportError:
    # Fallback for progress bar
    tqdm = lambda iterable, **kwargs: iterable
try:
    from elevenlabs.client import ElevenLabs
except ImportError:
    ElevenLabs = None

# Dummy ElevenLabs client stub when SDK is unavailable (e.g., dry-run without installation)
if ElevenLabs is None:
    class ElevenLabs:
        def __init__(self, api_key=None):
            pass
        @property
        def speech_to_text(self):
            return self
        def convert(self, *args, **kwargs):
            # Return a dummy response with minimal attributes
            class DummyResponse:
                text = ""
                words = []
                def dict(self):
                    return {}
            return DummyResponse()
try:
    from dotenv import load_dotenv
except ImportError:
    # Fallback if python-dotenv is not installed
    load_dotenv = lambda *args, **kwargs: None

from db_manager import DatabaseManager
from file_manager import FileManager

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class TranscriptionManager:
    """
    Manages all transcription operations for the Media Transcription and Translation Tool.
    
    This class provides methods for:
    - Transcribing audio files using ElevenLabs Scribe API
    - Converting transcription to different formats
    - Generating subtitles from transcriptions
    """
    
    def __init__(self, db_manager: DatabaseManager, config: Dict[str, Any],
                 auto_detect_language: bool = True, force_language: Optional[str] = None):
        """
        Initialize the transcription manager.
        
        Args:
            db_manager: Database manager instance
            config: Configuration dictionary
            auto_detect_language: Whether to auto-detect language (default: True)
            force_language: Force specific language code (overrides auto-detection)
        """
        self.db_manager = db_manager
        self.config = config
        
        # Language settings
        self.auto_detect_language = auto_detect_language
        self.force_language = force_language
        
        # Initialize ElevenLabs client
        self.api_key = config.get('elevenlabs', {}).get('api_key') or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            logger.error("ElevenLabs API key not found in config or environment variables")
            raise ValueError("ElevenLabs API key is required for transcription")
        
        self.client = ElevenLabs(api_key=self.api_key)
        
        # Set transcription model and options
        self.model_id = config.get('elevenlabs', {}).get('model', 'scribe_v1')
        self.speaker_detection = config.get('elevenlabs', {}).get('speaker_detection', True)
        self.speaker_count = config.get('elevenlabs', {}).get('speaker_count', 32)
        
        # Create file manager instance for file operations
        self.file_manager = None
        # Directory used to store split audio segments (if any)
        self._split_temp_dir: Optional[str] = None
    
    def set_file_manager(self, file_manager: FileManager) -> None:
        """
        Set the file manager instance.
        
        Args:
            file_manager: FileManager instance
        """
        self.file_manager = file_manager
    
    def _split_audio_file(self, audio_path: str, max_size_mb: int = 25) -> List[Tuple[str, float]]:
        """
        Split a large audio file into smaller segments if it exceeds max_size_mb.
        Returns a list of tuples (segment_path, start_time_seconds).
        """
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found for splitting: {audio_path}")
            return []
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size_mb <= max_size_mb:
            return [(audio_path, 0.0)]
        try:
            # Create temporary directory for segments
            temp_dir = tempfile.mkdtemp(prefix="audio_segments_")
            self._split_temp_dir = temp_dir
            # Get total duration via ffprobe
            ffprobe_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
            ]
            output = subprocess.check_output(ffprobe_cmd)
            duration = float(output.decode().strip())
        except Exception as e:
            logger.error(f"Error during audio split preparation: {e}")
            if self._split_temp_dir:
                shutil.rmtree(self._split_temp_dir, ignore_errors=True)
                self._split_temp_dir = None
            return []
        # Determine number of segments
        num_segments = int(file_size_mb / max_size_mb) + 1
        segment_duration = duration / num_segments
        # Cap each segment to 10 minutes to avoid oversized chunks that sometimes
        # trigger API 500 errors.
        MAX_SEGMENT_SECONDS = 600  # 10 minutes
        if segment_duration > MAX_SEGMENT_SECONDS:
            num_segments = math.ceil(duration / MAX_SEGMENT_SECONDS)
            segment_duration = duration / num_segments
        segments: List[Tuple[str, float]] = []
        for i in range(num_segments):
            start = i * segment_duration
            segment_path = os.path.join(temp_dir, f"segment_{i:03d}.mp3")
            if i < num_segments - 1:
                duration_arg = ['-t', str(segment_duration)]
            else:
                duration_arg = []
            ffmpeg_cmd = [
                'ffmpeg', '-v', 'warning', '-i', audio_path,
                '-ss', str(start), *duration_arg,
                '-acodec', 'libmp3lame', '-ab', '192k', '-ar', '44100',
                '-y', segment_path
            ]
            try:
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                segments.append((segment_path, start))
            except subprocess.CalledProcessError as e:
                logger.error(f"Error creating audio segment {i}: {e}")
        return segments
    
    def transcribe_audio(
        self, file_id: str, audio_path: str, file_details: Dict[str, Any],
        auto_detect_language: Optional[bool] = None
    ) -> bool:
        """
        Transcribe an audio file using ElevenLabs Speech-to-Text API.
        
        Args:
            file_id: Unique ID of the file
            audio_path: Path to the audio file
            file_details: Dictionary containing file details
            auto_detect_language: Whether to auto-detect language (overrides class setting)
            
        Returns:
            True if successful, False otherwise
        """
        transcript_path = self.file_manager.get_transcript_path(file_id)
        
        # Check if transcription already exists and we're not forcing reprocessing
        if os.path.exists(transcript_path) and not self.config.get('force_reprocess', False):
            logger.info(f"Transcription already exists at {transcript_path}, skipping")
            # Ensure database reflects completion even if we skip actual processing
            self.db_manager.update_status(
                file_id=file_id,
                status='completed',
                transcription_status='completed'
            )
            return True
        
        # If we're forcing reprocessing, log it
        if os.path.exists(transcript_path) and self.config.get('force_reprocess', False):
            logger.info(f"Force reprocessing enabled, transcribing again: {transcript_path}")
        
        # Set transcription status to in-progress
        self.db_manager.update_status(
            file_id=file_id,
            status='in-progress',
            transcription_status='in-progress'
        )
        # Check for large audio files and split if necessary
        max_size_mb = self.config.get('max_audio_size_mb', 25)
        try:
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        except Exception:
            file_size_mb = 0
        if file_size_mb > max_size_mb:
            logger.info(f"Audio file size {file_size_mb:.2f}MB exceeds {max_size_mb}MB, splitting into segments...")
            segments = self._split_audio_file(audio_path, max_size_mb)
            if not segments:
                logger.error("Audio splitting failed, aborting transcription.")
                self.db_manager.update_status(file_id=file_id, status='failed', transcription_status='failed')
                return False
            all_texts: List[str] = []
            all_words = []
            combined_json = []
            # Prepare API options
            request_options = {"timeout_in_seconds": 300}
            # Determine language parameter once
            use_auto = auto_detect_language if auto_detect_language is not None else self.auto_detect_language
            if self.force_language:
                source_lang = self.force_language
            elif use_auto:
                source_lang = None
            else:
                source_lang = file_details.get('detected_language') or 'deu'
            # Transcribe each segment
            # Transcribe each segment with retry on transient API errors
            max_retries = self.config.get('api_retries', 8)
            for seg_path, seg_start in segments:
                logger.info(f"Transcribing segment starting at {seg_start:.2f}s: {seg_path}")
                with open(seg_path, 'rb') as audio_file:
                    api_params = {
                        "file": audio_file,
                        "model_id": self.model_id,
                        "tag_audio_events": True,
                        "diarize": self.speaker_detection,
                        "timestamps_granularity": "word"
                    }
                    if source_lang is not None:
                        api_params["language_code"] = source_lang
                    # Attempt transcription with retries (keep file handle open)
                    for attempt in range(max_retries):
                        try:
                            transcription_seg = self.client.speech_to_text.convert(**api_params, request_options=request_options)
                            break
                        except ApiError as e:
                            if attempt < max_retries - 1:
                                backoff = min(2 ** attempt, 60)  # cap backoff at 60s
                                logger.warning(f"API error on segment at {seg_start:.2f}s (attempt {attempt+1}/{max_retries}): {e}. Retrying in {backoff}s...")
                                time.sleep(backoff)
                                continue
                            logger.error(f"API error on segment at {seg_start:.2f}s after {max_retries} attempts: {e}")
                            self.db_manager.log_error(
                                file_id=file_id,
                                process_stage='transcription',
                                error_message='API error during segment transcription',
                                error_details=str(e)
                            )
                            self.db_manager.update_status(file_id=file_id, status='failed', transcription_status='failed')
                            # Clean up segments
                            if self._split_temp_dir:
                                shutil.rmtree(self._split_temp_dir, ignore_errors=True)
                                self._split_temp_dir = None
                            return False
                        except Exception as e:
                            logger.error(f"Unexpected error on segment at {seg_start:.2f}s: {e}")
                            self.db_manager.log_error(
                                file_id=file_id,
                                process_stage='transcription',
                                error_message='Error during segment transcription',
                                error_details=str(e)
                            )
                            self.db_manager.update_status(file_id=file_id, status='failed', transcription_status='failed')
                            if self._split_temp_dir:
                                shutil.rmtree(self._split_temp_dir, ignore_errors=True)
                                self._split_temp_dir = None
                            return False
                # Validate segment response
                if not transcription_seg or not getattr(transcription_seg, 'text', None):
                    logger.error(f"Transcription returned no text for segment at {seg_start:.2f}s")
                    self.db_manager.update_status(file_id=file_id, status='failed', transcription_status='failed')
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
                # Brief pause between segments to avoid hitting API rate limits
                time.sleep(self.config.get('segment_pause', 1))
            # Combine and save full transcript
            full_text = " ".join(all_texts)
            transcript_path = self.file_manager.get_transcript_path(file_id)
            os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(full_text)
            # Save combined JSON for debugging
            json_path = f"{transcript_path}.segments.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(combined_json, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved combined transcription JSON to: {json_path}")
            # Generate SRT from combined words
            if all_words:
                srt_path = self.file_manager.get_subtitle_path(file_id, 'orig')
                os.makedirs(os.path.dirname(srt_path), exist_ok=True)
                fake = type('T', (object,), {'words': all_words})
                srt_content = self.create_srt_subtitles(fake)
                with open(srt_path, 'w', encoding='utf-8') as f:
                    f.write(srt_content)
                logger.info(f"SRT subtitles saved to: {srt_path}")
            # Clean up split segments
            if self._split_temp_dir:
                shutil.rmtree(self._split_temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up temporary audio segments: {self._split_temp_dir}")
                self._split_temp_dir = None
            # Update statuses
            self.db_manager.update_status(
                file_id=file_id,
                status='completed',
                transcription_status='completed'
            )
            logger.info(f"Transcription completed for: {file_id}")
            return True
        
        # Determine whether to auto-detect language
        # Priority: 1. Method parameter, 2. Class setting, 3. Default to True
        use_auto_detect = auto_detect_language if auto_detect_language is not None else self.auto_detect_language
        
        try:
            logger.info(f"Transcribing audio file: {audio_path}")
            
            # Determine language based on parameters
            if self.force_language:
                # Use forced language from command line or config
                source_lang = self.force_language
                logger.info(f"Using forced language code: {source_lang}")
            elif use_auto_detect:
                # Use None to let ElevenLabs auto-detect the language
                source_lang = None
                logger.info("Using automatic language detection")
            else:
                # Use detected language from file details or default to German
                source_lang = file_details.get('detected_language') or "deu"
                logger.info(f"Using language from database: {source_lang}")
            
            # Prepare audio file for transcription as in video_to_text.py
            with open(audio_path, 'rb') as audio_file:
                # Prepare API params
                api_params = {
                    "file": audio_file,
                    "model_id": self.model_id,
                    "tag_audio_events": True,
                    "diarize": self.speaker_detection,
                    "timestamps_granularity": "word"
                }
                
                # Only add language_code param if we're not doing auto-detection
                if source_lang is not None:
                    api_params["language_code"] = source_lang
                
                # Add request options with an extended timeout to prevent "read operation timed out" errors
                request_options = {
                    "timeout_in_seconds": 300  # 5 minutes
                }
                logger.info(f"Setting API timeout to {request_options['timeout_in_seconds']} seconds")
                
                # Transcribe with retry on transient API errors
                max_retries = self.config.get('api_retries', 8)
                for attempt in range(max_retries):
                    try:
                        transcription = self.client.speech_to_text.convert(**api_params, request_options=request_options)
                        break
                    except ApiError as e:
                        if attempt < max_retries - 1:
                            backoff = min(2 ** attempt, 60)  # cap backoff at 60s
                            logger.warning(f"API error on file {file_id} (attempt {attempt+1}/{max_retries}): {e}. Retrying in {backoff}s...")
                            time.sleep(backoff)
                            continue
                        logger.error(f"API error on file {file_id} after {max_retries} attempts: {e}")
                        raise
                # Check if transcription was successful
                if not transcription or not hasattr(transcription, 'text') or not transcription.text:
                    logger.error(f"Failed to get transcription text for {file_id}")
                    self.db_manager.update_transcription_status(file_id, 'failed')
                    return False
                
                # Store the transcription JSON 
                transcription_json = json.dumps(transcription.dict(), ensure_ascii=False, indent=2)
                
                # Debug: Print the entire response to find where language data is stored
                logger.debug(f"Transcription response: {transcription_json}")

                # Save the transcription text to file
                transcript_path = self.file_manager.get_transcript_path(file_id)
                os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
                
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(transcription.text)
                
                logger.info(f"Transcription saved to: {transcript_path}")
                
                # Store detected language in the database
                # Extract language from the response - check for top-level language_code field
                detected_language = None
                prob = getattr(transcription, 'language_probability', None)
                
                # Check different possible locations for language information
                if hasattr(transcription, 'language_code'):
                    detected_language = transcription.language_code
                    if prob is not None:
                        logger.info(f"Detected language: {detected_language} (confidence: {prob:.2f})")
                    else:
                        logger.info(f"Detected language: {detected_language}")
                elif hasattr(transcription, 'detected_language'):
                    detected_language = transcription.detected_language
                    logger.info(f"Detected language: {detected_language}")
                elif hasattr(transcription, 'metadata') and 'detected_language' in transcription.metadata:
                    detected_language = transcription.metadata['detected_language']
                    logger.info(f"Detected language from metadata: {detected_language}")
                elif hasattr(transcription, 'language'):
                    detected_language = transcription.language
                    logger.info(f"Detected language from 'language' field: {detected_language}")
                
                # If we found a language, save it to database
                if detected_language:
                    self.db_manager.update_file_language(file_id, detected_language)
                else:
                    logger.warning("No language detected in API response")
                    
                # Also save full transcription response to a JSON file for debugging
                json_path = os.path.join(os.path.dirname(transcript_path), f"{os.path.basename(transcript_path)}.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    f.write(transcription_json)
                logger.debug(f"Saved full transcription JSON to: {json_path}")
                
                # Create SRT subtitles if available
                if hasattr(transcription, 'words') and transcription.words:
                    srt_path = self.file_manager.get_subtitle_path(file_id, 'orig')
                    os.makedirs(os.path.dirname(srt_path), exist_ok=True)
                    
                    srt_content = self.create_srt_subtitles(transcription)
                    with open(srt_path, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    
                    logger.info(f"SRT subtitles saved to: {srt_path}")
                
                # Update status to completed
                self.db_manager.update_status(
                    file_id=file_id,
                    status='completed',
                    transcription_status='completed'
                )
                
                logger.info(f"Transcription completed for: {file_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error transcribing audio {audio_path}: {e}")
            
            # Log error in database
            self.db_manager.log_error(
                file_id=file_id,
                process_stage='transcription',
                error_message="Transcription failed",
                error_details=str(e)
            )
            
            # Update status to failed
            self.db_manager.update_status(
                file_id=file_id,
                status='failed',
                transcription_status='failed'
            )
            
            return False
    
    def transcribe_batch(self, limit: Optional[int] = None):
        """
        Process a batch of files for transcription.
        
        Args:
            limit: Maximum number of files to process
        """
        files = self.db_manager.get_files_for_transcription(limit)
        logger.info(f"Found {len(files)} files for transcription")
        
        success_count = 0
        fail_count = 0
        
        for file in tqdm(files, desc="Transcribing audio"):
            file_id = file['file_id']
            audio_path = self.file_manager.get_audio_path(file_id)
            
            if not audio_path:
                logger.error(f"Audio file not found for {file_id}")
                self.db_manager.log_error(
                    file_id=file_id,
                    process_stage='transcription',
                    error_message="Audio file not found",
                    error_details=f"File ID: {file_id}"
                )
                fail_count += 1
                continue
                
            if self.transcribe_audio(file_id, audio_path, file):
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(f"Transcription completed. Success: {success_count}, Failed: {fail_count}")
    
    def create_srt_subtitles(self, transcription: Any) -> str:
        """
        Create SRT subtitle file from a transcription.
        
        Args:
            transcription: Transcription object from ElevenLabs API
            
        Returns:
            SRT formatted string
        """
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
                srt_lines.append(f"{self._format_timestamp_for_srt(start_time)} --> {self._format_timestamp_for_srt(end_time)}")
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
            srt_lines.append(f"{self._format_timestamp_for_srt(start_time)} --> {self._format_timestamp_for_srt(last_word.end)}")
            srt_lines.append(subtitle_text)
            srt_lines.append("")  # Empty line at the end
        
        return '\n'.join(srt_lines)
    
    def _format_timestamp_for_srt(self, seconds: float) -> str:
        """
        Convert seconds to SRT timestamp format (00:00:00,000).
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted timestamp string
        """
        # Create a timedelta object
        time_obj = datetime.timedelta(seconds=seconds)
        
        # Calculate hours, minutes, seconds
        hours, remainder = divmod(int(time_obj.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Get milliseconds
        milliseconds = int((time_obj.total_seconds() % 1) * 1000)
        
        # Format the timestamp for SRT
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    def get_transcript_text(self, file_id: str) -> Optional[str]:
        """
        Get the transcription text for a file.
        
        Args:
            file_id: Unique ID of the file
            
        Returns:
            Transcription text or None if not found
        """
        # Check if file manager is set
        if not self.file_manager:
            logger.error("File manager not set in transcription manager")
            return None
        
        # Get transcript path
        transcript_path = self.file_manager.get_transcript_path(file_id)
        
        if not os.path.exists(transcript_path):
            logger.warning(f"Transcript file not found: {transcript_path}")
            return None
        
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error reading transcript {transcript_path}: {e}")
            return None
