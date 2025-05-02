#!/usr/bin/env python3
"""
File Manager for Media Transcription and Translation Tool
--------------------------------------------------------
Handles all file operations including:
- Discovering media files in directories
- File validation and metadata extraction
- Filename sanitization
- Audio extraction from video files
- File organization
"""

import os
import re
import shutil
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
import unicodedata
import tempfile
import time
import subprocess

try:
    import moviepy.editor as mp
except ImportError:
    mp = None
try:
    from tqdm import tqdm
except ImportError:
    # Fallback progress bar
    tqdm = lambda iterable, **kwargs: iterable

from db_manager import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class FileManager:
    """
    Manages all file operations for the Media Transcription and Translation Tool.
    
    This class provides methods for:
    - Discovering media files in directories
    - Validating media files and extracting metadata
    - Sanitizing filenames for safe processing
    - Extracting audio from video files
    - Organizing processed files
    """
    
    def __init__(self, db_manager: DatabaseManager, config: Dict[str, Any]):
        """
        Initialize the file manager.
        
        Args:
            db_manager: Database manager instance
            config: Configuration dictionary
        """
        self.db_manager = db_manager
        self.config = config
        
        # Create output directory if it doesn't exist
        self.output_dir = config.get('output_directory', './output')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set up media extensions from config or use defaults
        self.media_extensions = config.get('media_extensions', {
            'audio': ['.mp3', '.wav', '.m4a', '.aac', '.flac'],
            'video': ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        })
        
        # Audio extraction settings
        self.audio_format = config.get('extract_audio_format', 'mp3')
        self.audio_bitrate = config.get('extract_audio_quality', '192k')
        
        # Create subdirectories for different file types
        self.audio_dir = os.path.join(self.output_dir, 'audio')
        self.transcript_dir = os.path.join(self.output_dir, 'transcripts')
        self.translation_dir = os.path.join(self.output_dir, 'translations')
        self.subtitles_dir = os.path.join(self.output_dir, 'subtitles')
        self.videos_dir = os.path.join(self.output_dir, 'videos')
        
        for directory in [self.audio_dir, self.transcript_dir, 
                         self.translation_dir, self.subtitles_dir,
                         self.videos_dir]:
            os.makedirs(directory, exist_ok=True)
        
    def discover_files(self, directory: str, limit: Optional[int] = None) -> List[str]:
        """
        Recursively discover audio and video files in a directory.
        
        Args:
            directory: Directory to scan for media files
            limit: Maximum number of files to return (optional)
            
        Returns:
            List of file IDs that were discovered and added to the database
        """
        if not os.path.isdir(directory):
            logger.error(f"Directory does not exist: {directory}")
            return []
        
        # Get all supported extensions as a flattened list
        all_extensions = set()
        for ext_list in self.media_extensions.values():
            all_extensions.update(ext_list)
        
        logger.info(f"Scanning directory: {directory}")
        logger.info(f"Supported file extensions: {', '.join(all_extensions)}")
        
        # Track discovered files
        discovered_files = []
        processed_count = 0
        skipped_count = 0
        
        # Use tqdm for progress indication during discovery
        for root, _, files in tqdm(os.walk(directory), desc="Scanning directories"):
            for file in files:
                file_path = os.path.join(root, file)
                
                # Skip already discovered files
                if self.db_manager.get_file_by_path(file_path):
                    skipped_count += 1
                    continue
                
                # Check file extension
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in all_extensions:
                    # Determine media type
                    media_type = 'audio' if file_ext in self.media_extensions['audio'] else 'video'
                    
                    # Generate safe filename
                    safe_filename = self.sanitize_filename(file)
                    
                    # Add to database
                    file_id = self.db_manager.add_media_file(
                        file_path=file_path,
                        safe_filename=safe_filename,
                        media_type=media_type,
                        file_size=os.path.getsize(file_path)
                    )
                    
                    discovered_files.append(file_id)
                    processed_count += 1
                    
                    # Update with additional metadata in the background
                    try:
                        self._update_media_metadata(file_id, file_path, media_type)
                    except Exception as e:
                        logger.warning(f"Could not update metadata for {file_path}: {e}")
                    
                    # Check if we've reached the limit
                    if limit and processed_count >= limit:
                        logger.info(f"Reached limit of {limit} files")
                        break
            
            # Check if we've reached the limit after processing a directory
            if limit and processed_count >= limit:
                break
        
        logger.info(f"Discovery completed. Found {processed_count} new files. Skipped {skipped_count} existing files.")
        return discovered_files
    
    def process_single_file(self, file_path: str) -> Optional[str]:
        """
        Process a single media file.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            File ID if processed successfully, None otherwise
        """
        if not os.path.isfile(file_path):
            logger.error(f"File does not exist: {file_path}")
            return None
        
        # Check if file already exists in database
        existing_file = self.db_manager.get_file_by_path(file_path)
        if existing_file:
            logger.info(f"File already exists in database: {file_path}")
            return existing_file['file_id']
        
        # Check file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Get all supported extensions as a flattened list
        all_extensions = set()
        for ext_list in self.media_extensions.values():
            all_extensions.update(ext_list)
        
        if file_ext not in all_extensions:
            logger.error(f"Unsupported file type: {file_ext}")
            return None
        
        # Determine media type
        media_type = 'audio' if file_ext in self.media_extensions['audio'] else 'video'
        
        # Generate safe filename
        filename = os.path.basename(file_path)
        safe_filename = self.sanitize_filename(filename)
        
        # Add to database
        file_id = self.db_manager.add_media_file(
            file_path=file_path,
            safe_filename=safe_filename,
            media_type=media_type,
            file_size=os.path.getsize(file_path)
        )
        
        # Update with additional metadata
        try:
            self._update_media_metadata(file_id, file_path, media_type)
        except Exception as e:
            logger.warning(f"Could not update metadata for {file_path}: {e}")
        
        logger.info(f"Added file to database: {file_path}")
        return file_id
    
    def retry_files(self, status: str = 'failed') -> List[str]:
        """
        Get files with a specific status for retry.
        
        Args:
            status: Status to filter by ('pending', 'in-progress', 'failed', 'completed')
            
        Returns:
            List of file IDs that can be retried
        """
        files = self.db_manager.get_files_by_status(status)
        file_ids = [file['file_id'] for file in files]
        
        logger.info(f"Found {len(file_ids)} files with status '{status}' for retry")
        return file_ids
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename for safe processing.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Split the filename and extension
        base_name, extension = os.path.splitext(filename)
        
        # Convert to lowercase
        base_name = base_name.lower()
        extension = extension.lower()
        
        # Remove accents and normalize unicode
        base_name = unicodedata.normalize('NFKD', base_name).encode('ASCII', 'ignore').decode('ASCII')
        
        # Replace any non-alphanumeric characters with underscores
        base_name = re.sub(r'[^a-z0-9]', '_', base_name)
        
        # Replace multiple underscores with a single one
        base_name = re.sub(r'_+', '_', base_name)
        
        # Remove leading/trailing underscores
        base_name = base_name.strip('_')
        
        # Ensure the name is not empty
        if not base_name:
            base_name = "file"
        
        # Add timestamp to ensure uniqueness
        timestamp = int(time.time())
        
        # Create the safe filename
        safe_filename = f"{base_name}_{timestamp}{extension}"
        
        return safe_filename
    
    def _update_media_metadata(self, file_id: str, file_path: str, media_type: str) -> bool:
        """
        Update media file metadata such as duration and checksum.
        
        Args:
            file_id: Unique ID of the file
            file_path: Path to the media file
            media_type: Type of media ('audio' or 'video')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate file checksum
            checksum = self._calculate_file_checksum(file_path)
            
            # Get media duration
            duration = None
            try:
                if media_type == 'video':
                    clip = mp.VideoFileClip(file_path)
                    duration = clip.duration
                    clip.close()
                elif media_type == 'audio':
                    clip = mp.AudioFileClip(file_path)
                    duration = clip.duration
                    clip.close()
            except Exception as e:
                logger.warning(f"Could not determine duration for {file_path}: {e}")
            
            # Update database
            return self.db_manager.update_media_file(
                file_id=file_id,
                checksum=checksum,
                duration=duration
            )
        
        except Exception as e:
            logger.error(f"Error updating metadata for {file_path}: {e}")
            return False
    
    def _calculate_file_checksum(self, file_path: str, algorithm: str = 'md5') -> str:
        """
        Calculate a file checksum.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use
            
        Returns:
            Hexadecimal checksum string
        """
        hash_alg = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            # Read and update in chunks to avoid loading large files into memory
            for chunk in iter(lambda: f.read(4096), b''):
                hash_alg.update(chunk)
                
        return hash_alg.hexdigest()
    
    def extract_audio_from_video(self, file_id: str) -> bool:
        """
        Extract audio from a video file.
        
        Args:
            file_id: Unique ID of the video file
            
        Returns:
            True if successful, False otherwise
        """
        # Get file details
        file_details = self.db_manager.get_file_status(file_id)
        
        if not file_details:
            logger.error(f"File not found in database: {file_id}")
            return False
        
        # Check if this is a video file
        if file_details['media_type'] != 'video':
            logger.warning(f"File is not a video: {file_id}")
            return False
        
        # Check if the original file exists
        original_path = file_details['original_path']
        if not os.path.exists(original_path):
            logger.error(f"Original file not found: {original_path}")
            self.db_manager.log_error(
                file_id=file_id,
                process_stage='extraction',
                error_message="Original file not found",
                error_details=f"Path: {original_path}"
            )
            return False
        
        # Generate output audio path
        audio_filename = f"{file_id}_{os.path.splitext(os.path.basename(original_path))[0]}.{self.audio_format}"
        audio_path = os.path.join(self.audio_dir, audio_filename)
        
        # Update status to in-progress
        self.db_manager.update_status(
            file_id=file_id,
            status='in-progress'
        )
        
        try:
            logger.info(f"Extracting audio from: {original_path}")
            
            # Use ffmpeg directly instead of moviepy
            os.makedirs(os.path.dirname(audio_path), exist_ok=True)
            
            # Prepare ffmpeg command
            audio_bitrate = self.audio_bitrate
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', original_path,  # Input file
                '-vn',  # Disable video
                '-acodec', 'libmp3lame' if self.audio_format == 'mp3' else 'pcm_s16le',  # Audio codec
                '-ab', audio_bitrate,  # Audio bitrate
                '-ar', '44100',  # Audio sample rate
                '-y',  # Overwrite output file if it exists
                audio_path  # Output file
            ]
            
            # Execute ffmpeg command
            logger.info(f"Running ffmpeg command: {' '.join(ffmpeg_cmd)}")
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for completion and capture output
            stdout, stderr = process.communicate()
            
            # Check if extraction was successful
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace')
                logger.error(f"FFmpeg error: {error_msg}")
                self.db_manager.log_error(
                    file_id=file_id,
                    process_stage='extraction',
                    error_message="Audio extraction failed",
                    error_details=error_msg
                )
                self.db_manager.update_status(
                    file_id=file_id,
                    status='failed'
                )
                return False
            
            logger.info(f"Successfully extracted audio to: {audio_path}")
            
            # Update database with the audio path
            self.db_manager.update_status(
                file_id=file_id,
                status='completed',
                transcription_status='not_started'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error extracting audio from {original_path}: {str(e)}")
            
            # Log error in database
            self.db_manager.log_error(
                file_id=file_id,
                process_stage='extraction',
                error_message="Audio extraction failed",
                error_details=str(e)
            )
            
            # Update status to failed
            self.db_manager.update_status(
                file_id=file_id,
                status='failed'
            )
            
            return False
    
    def extract_audio_batch(self, limit: Optional[int] = None) -> Tuple[int, int]:
        """
        Extract audio from a batch of video files.
        
        Args:
            limit: Maximum number of files to process
            
        Returns:
            Tuple of (success_count, fail_count)
        """
        # Get all video files that need audio extraction
        files = self.db_manager.get_files_by_status('pending')
        video_files = [f for f in files if f['media_type'] == 'video']
        
        if limit:
            video_files = video_files[:limit]
        
        logger.info(f"Found {len(video_files)} video files for audio extraction")
        
        success_count = 0
        fail_count = 0
        
        # Process each file
        for file in tqdm(video_files, desc="Extracting audio"):
            file_id = file['file_id']
            
            if self.extract_audio_from_video(file_id):
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(f"Audio extraction completed. Success: {success_count}, Failed: {fail_count}")
        return success_count, fail_count
    
    def get_audio_path(self, file_id: str) -> Optional[str]:
        """
        Get the path to the audio file for a given file ID.
        
        Args:
            file_id: Unique ID of the file
            
        Returns:
            Path to the audio file, or None if not found
        """
        file_details = self.db_manager.get_file_status(file_id)
        
        if not file_details:
            logger.error(f"File not found in database: {file_id}")
            return None
        
        # For audio files, return the original path
        if file_details['media_type'] == 'audio':
            return file_details['original_path']
        
        # For video files, construct the audio path
        audio_filename = f"{file_id}_{os.path.splitext(os.path.basename(file_details['original_path']))[0]}.{self.audio_format}"
        audio_path = os.path.join(self.audio_dir, audio_filename)
        
        # Check if the audio file exists
        if not os.path.exists(audio_path):
            logger.warning(f"Audio file not found for {file_id}: {audio_path}")
            return None
        
        return audio_path
    
    def get_transcript_path(self, file_id: str, language: str = None) -> str:
        """
        Get the path where a transcript file should be saved.
        
        Args:
            file_id: Unique ID of the file
            language: Language code (optional)
            
        Returns:
            Path where the transcript file should be saved
        """
        file_details = self.db_manager.get_file_status(file_id)
        
        if not file_details:
            logger.error(f"File not found in database: {file_id}")
            return None
        
        safe_filename = file_details['safe_filename']
        base_name = os.path.splitext(safe_filename)[0]
        
        # Include file_id in the filename for traceability
        if language:
            transcript_filename = f"{file_id}_{base_name}_{language}.txt"
        else:
            transcript_filename = f"{file_id}_{base_name}.txt"
        
        return os.path.join(self.transcript_dir, transcript_filename)
    
    def get_translation_path(self, file_id: str, language: str) -> str:
        """
        Get the path where a translation file should be saved.
        
        Args:
            file_id: Unique ID of the file
            language: Language code
            
        Returns:
            Path where the translation file should be saved
        """
        file_details = self.db_manager.get_file_status(file_id)
        
        if not file_details:
            logger.error(f"File not found in database: {file_id}")
            return None
        
        safe_filename = file_details['safe_filename']
        base_name = os.path.splitext(safe_filename)[0]
        
        # Include file_id in the filename for traceability
        translation_filename = f"{file_id}_{base_name}_{language}.txt"
        
        # Create language-specific subdirectory
        lang_dir = os.path.join(self.translation_dir, language)
        os.makedirs(lang_dir, exist_ok=True)
        
        return os.path.join(lang_dir, translation_filename)
    
    def get_subtitle_path(self, file_id: str, language: str) -> str:
        """
        Get the path where a subtitle file should be saved.
        
        Args:
            file_id: Unique ID of the file
            language: Language code
            
        Returns:
            Path where the subtitle file should be saved
        """
        file_details = self.db_manager.get_file_status(file_id)
        
        if not file_details:
            logger.error(f"File not found in database: {file_id}")
            return None
        
        safe_filename = file_details['safe_filename']
        base_name = os.path.splitext(safe_filename)[0]
        
        # Include file_id in the filename for traceability
        subtitle_filename = f"{file_id}_{base_name}_{language}.srt"
        
        # Create language-specific subdirectory
        lang_dir = os.path.join(self.subtitles_dir, language)
        os.makedirs(lang_dir, exist_ok=True)
        
        return os.path.join(lang_dir, subtitle_filename)
    
    def get_video_path(self, file_id: str) -> Optional[str]:
        """
        Get the path where a video symbolic link should be created.
        
        Args:
            file_id: Unique ID of the file
            
        Returns:
            Path where the video symbolic link should be created, or None if file not found
        """
        file_details = self.db_manager.get_file_status(file_id)
        
        if not file_details:
            logger.error(f"File not found in database: {file_id}")
            return None
        
        # Skip non-video files
        if file_details['media_type'] != 'video':
            logger.warning(f"File is not a video: {file_id}")
            return None
            
        safe_filename = file_details['safe_filename']
        base_name = os.path.splitext(safe_filename)[0]
        
        # Get the original file extension
        original_path = file_details['original_path']
        file_ext = os.path.splitext(original_path)[1].lower()
        
        # Include file_id in the filename for traceability (matching subtitle pattern)
        video_filename = f"{file_id}_{base_name}_orig{file_ext}"
        
        return os.path.join(self.videos_dir, video_filename)
