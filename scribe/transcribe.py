#!/usr/bin/env python3
"""
Clean Transcription Module for Historical Preservation
-----------------------------------------------------
Focused module for verbatim transcription of audio/video files
using ElevenLabs Scribe API with speaker diarization.

Designed for historical preservation with emphasis on:
- Verbatim accuracy including speech patterns
- Speaker identification and diarization
- Robust error handling and retries
- Support for large files via segmentation
"""

import os
import json
import time
import logging
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs.core.api_error import ApiError
except ImportError:
    raise ImportError("ElevenLabs SDK required. Install with: pip install elevenlabs")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TranscriptionConfig:
    """Configuration for transcription service."""
    api_key: str
    model: str = "scribe_v1"
    speaker_detection: bool = True
    speaker_count: int = 32
    max_file_size_mb: int = 25
    max_segment_duration: int = 600  # 10 minutes
    api_timeout: int = 300  # 5 minutes
    max_retries: int = 8
    segment_pause: float = 1.0
    auto_detect_language: bool = True
    force_language: Optional[str] = None


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    words: List[Dict[str, Any]] = field(default_factory=list)
    segments: List[Dict[str, Any]] = field(default_factory=list)
    speakers: List[Dict[str, Any]] = field(default_factory=list)
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AudioExtractor:
    """Extract audio from video files using ffmpeg."""
    
    @staticmethod
    def extract_audio(video_path: Path, output_format: str = "mp3", 
                     bitrate: str = "192k") -> Path:
        """
        Extract audio from video file.
        
        Args:
            video_path: Path to video file
            output_format: Audio format (mp3, wav)
            bitrate: Audio bitrate
            
        Returns:
            Path to extracted audio file
        """
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp:
            audio_path = Path(tmp.name)
        
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vn',  # No video
            '-acodec', 'libmp3lame' if output_format == 'mp3' else 'pcm_s16le',
            '-ab', bitrate,
            '-ar', '44100',
            '-y',  # Overwrite
            str(audio_path)
        ]
        
        logger.info(f"Extracting audio from: {video_path}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Audio extracted to: {audio_path}")
            return audio_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            audio_path.unlink(missing_ok=True)
            raise RuntimeError(f"Audio extraction failed: {e.stderr}")
    
    @staticmethod
    def get_duration(media_path: Path) -> float:
        """Get duration of media file in seconds."""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(media_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Could not get duration for {media_path}: {e}")
            return 0.0


class AudioSegmenter:
    """Split large audio files into segments for processing."""
    
    @staticmethod
    def split_audio(audio_path: Path, max_size_mb: int = 25, 
                   max_segment_duration: int = 600) -> List[Tuple[Path, float]]:
        """
        Split audio file into segments if needed.
        
        Args:
            audio_path: Path to audio file
            max_size_mb: Maximum segment size in MB
            max_segment_duration: Maximum segment duration in seconds
            
        Returns:
            List of (segment_path, start_time) tuples
        """
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        if file_size_mb <= max_size_mb:
            return [(audio_path, 0.0)]
        
        # Get total duration
        duration = AudioExtractor.get_duration(audio_path)
        if duration == 0:
            logger.warning("Could not determine duration, returning original file")
            return [(audio_path, 0.0)]
        
        # Calculate segments
        num_segments = int(file_size_mb / max_size_mb) + 1
        segment_duration = duration / num_segments
        
        # Cap segment duration
        if segment_duration > max_segment_duration:
            num_segments = int(duration / max_segment_duration) + 1
            segment_duration = duration / num_segments
        
        # Create temporary directory for segments
        temp_dir = tempfile.mkdtemp(prefix="audio_segments_")
        segments: List[Tuple[Path, float]] = []
        
        logger.info(f"Splitting {audio_path} into {num_segments} segments")
        
        for i in range(num_segments):
            start = i * segment_duration
            segment_path = Path(temp_dir) / f"segment_{i:03d}.mp3"
            
            cmd = [
                'ffmpeg', '-v', 'warning',
                '-i', str(audio_path),
                '-ss', str(start)
            ]
            
            if i < num_segments - 1:
                cmd.extend(['-t', str(segment_duration)])
            
            cmd.extend([
                '-acodec', 'libmp3lame',
                '-ab', '192k',
                '-ar', '44100',
                '-y', str(segment_path)
            ])
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                segments.append((segment_path, start))
            except subprocess.CalledProcessError as e:
                logger.error(f"Error creating segment {i}: {e}")
                # Clean up on error
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise
        
        return segments


class Transcriber:
    """Main transcription service using ElevenLabs Scribe."""
    
    def __init__(self, config: TranscriptionConfig):
        """Initialize transcriber with configuration."""
        self.config = config
        self.client = ElevenLabs(api_key=config.api_key)
        self._temp_dirs: List[str] = []
    
    def transcribe_file(self, file_path: Path) -> TranscriptionResult:
        """
        Transcribe an audio or video file.
        
        Args:
            file_path: Path to media file
            
        Returns:
            TranscriptionResult with transcription data
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Determine if we need to extract audio
        audio_path = file_path
        extracted_audio = None
        
        if file_path.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            logger.info(f"Extracting audio from video: {file_path}")
            extracted_audio = AudioExtractor.extract_audio(file_path)
            audio_path = extracted_audio
        
        try:
            # Check if we need to split the file
            segments = AudioSegmenter.split_audio(
                audio_path, 
                self.config.max_file_size_mb,
                self.config.max_segment_duration
            )
            
            if len(segments) > 1:
                result = self._transcribe_segments(segments)
            else:
                result = self._transcribe_single(audio_path)
            
            return result
            
        finally:
            # Clean up extracted audio
            if extracted_audio:
                extracted_audio.unlink(missing_ok=True)
            
            # Clean up any segment directories
            for temp_dir in self._temp_dirs:
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._temp_dirs.clear()
    
    def _transcribe_single(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe a single audio file."""
        logger.info(f"Transcribing: {audio_path}")
        
        # Prepare API parameters
        api_params = {
            "model_id": self.config.model,
            "tag_audio_events": True,
            "diarize": self.config.speaker_detection,
            "timestamps_granularity": "word"
        }
        
        # Add language parameter if specified
        if self.config.force_language:
            api_params["language_code"] = self.config.force_language
        elif not self.config.auto_detect_language:
            # Could add logic to detect language from filename or metadata
            pass
        
        # Retry logic for API calls
        for attempt in range(self.config.max_retries):
            try:
                with open(audio_path, 'rb') as audio_file:
                    response = self.client.speech_to_text.convert(
                        file=audio_file,
                        **api_params,
                        request_options={"timeout_in_seconds": self.config.api_timeout}
                    )
                
                # Extract result data
                return self._parse_response(response)
                
            except ApiError as e:
                if attempt < self.config.max_retries - 1:
                    backoff = min(2 ** attempt, 60)
                    logger.warning(f"API error (attempt {attempt + 1}): {e}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                else:
                    logger.error(f"API error after {self.config.max_retries} attempts: {e}")
                    raise
    
    def _transcribe_segments(self, segments: List[Tuple[Path, float]]) -> TranscriptionResult:
        """Transcribe multiple segments and combine results."""
        logger.info(f"Transcribing {len(segments)} segments")
        
        # Track segment directory for cleanup
        if segments and segments[0][0].parent.name.startswith("audio_segments_"):
            self._temp_dirs.append(str(segments[0][0].parent))
        
        all_texts: List[str] = []
        all_words: List[Dict[str, Any]] = []
        all_segments: List[Dict[str, Any]] = []
        detected_language = None
        total_confidence = 0.0
        confidence_count = 0
        
        for i, (segment_path, start_time) in enumerate(segments):
            logger.info(f"Transcribing segment {i + 1}/{len(segments)} at {start_time:.1f}s")
            
            result = self._transcribe_single(segment_path)
            
            # Accumulate text
            all_texts.append(result.text)
            
            # Adjust word timings
            for word in result.words:
                adjusted_word = word.copy()
                adjusted_word['start'] += start_time
                adjusted_word['end'] += start_time
                all_words.append(adjusted_word)
            
            # Track language detection
            if result.language and not detected_language:
                detected_language = result.language
            
            # Track confidence
            if result.confidence:
                total_confidence += result.confidence
                confidence_count += 1
            
            # Store segment data
            all_segments.append({
                'segment_index': i,
                'start_time': start_time,
                'text': result.text,
                'metadata': result.metadata
            })
            
            # Brief pause between segments
            if i < len(segments) - 1:
                time.sleep(self.config.segment_pause)
        
        # Combine results
        combined_text = " ".join(all_texts)
        avg_confidence = total_confidence / confidence_count if confidence_count > 0 else None
        
        return TranscriptionResult(
            text=combined_text,
            language=detected_language,
            confidence=avg_confidence,
            words=all_words,
            segments=all_segments,
            metadata={'segmented': True, 'segment_count': len(segments)}
        )
    
    def _parse_response(self, response) -> TranscriptionResult:
        """Parse ElevenLabs API response into TranscriptionResult."""
        # Extract basic fields
        text = getattr(response, 'text', '')
        
        # Extract language info
        language = None
        confidence = None
        
        if hasattr(response, 'language_code'):
            language = response.language_code
        elif hasattr(response, 'detected_language'):
            language = response.detected_language
        elif hasattr(response, 'language'):
            language = response.language
        
        if hasattr(response, 'language_probability'):
            confidence = response.language_probability
        
        # Extract words with timing - enhanced for subtitle-first architecture
        words = []
        if hasattr(response, 'words') and response.words:
            try:
                for word in response.words:
                    word_data = {
                        'text': word.text,
                        'start': word.start,
                        'end': word.end,
                        'speaker': getattr(word, 'speaker', None)
                    }
                    
                    # Capture additional timestamp data for subtitle-first processing
                    if hasattr(word, 'confidence'):
                        word_data['confidence'] = word.confidence
                    if hasattr(word, 'probability'):
                        word_data['probability'] = word.probability
                    if hasattr(word, 'speaker_id'):
                        word_data['speaker_id'] = word.speaker_id
                    
                    words.append(word_data)
            except (TypeError, AttributeError):
                # Handle case where words is not iterable (e.g., in tests)
                pass
        
        # Extract speaker information
        speakers = []
        if hasattr(response, 'speakers') and response.speakers:
            try:
                for speaker in response.speakers:
                    speakers.append({
                        'id': speaker.id,
                        'name': getattr(speaker, 'name', f"Speaker {speaker.id}")
                    })
            except (TypeError, AttributeError):
                # Handle case where speakers is not iterable (e.g., in tests)
                pass
        
        # Store full response as metadata
        metadata = {}
        if hasattr(response, 'dict'):
            metadata = response.dict()
        
        return TranscriptionResult(
            text=text,
            language=language,
            confidence=confidence,
            words=words,
            speakers=speakers,
            metadata=metadata
        )
    
    def create_subtitle_segments(self, words: List[Dict[str, Any]], 
                               max_duration: float = 4.0, 
                               min_gap: float = 0.5,
                               max_chars: int = 40,
                               fallback_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Create subtitle segments from word-level timestamps.
        
        This method implements natural segment boundary detection based on:
        - Timing gaps between words (speaker pauses)
        - Maximum segment duration limits
        - Character count limits for readability
        - Speaker change boundaries
        
        Includes fallback handling when word-level timestamps are unavailable.
        
        Args:
            words: List of word dictionaries with timing data
            max_duration: Maximum segment duration in seconds
            min_gap: Minimum gap to trigger segment boundary (seconds)
            max_chars: Maximum characters per segment
            fallback_text: Text to use if no word-level data available
            
        Returns:
            List of segment dictionaries with timing and text data
        """
        # Fallback: No word-level timestamps available
        if not words:
            if fallback_text:
                logger.warning("No word-level timestamps available, creating fallback segment")
                return self._create_fallback_segments(fallback_text, max_duration, max_chars)
            else:
                logger.warning("No word-level timestamps and no fallback text provided")
                return []
        
        # Check if words have timing information
        valid_words = [w for w in words if 'start' in w and 'end' in w and 
                      isinstance(w.get('start'), (int, float)) and 
                      isinstance(w.get('end'), (int, float))]
        
        if not valid_words:
            if fallback_text:
                logger.warning("Word data lacks timing information, using fallback segmentation")
                return self._create_fallback_segments(fallback_text, max_duration, max_chars)
            else:
                # Create basic segments from word text only
                logger.warning("No timing data available, creating basic text segments")
                return self._create_text_only_segments(words, max_chars)
        
        # Use only valid words for timing-based segmentation
        words = valid_words
        
        segments = []
        current_segment_words = []
        segment_start = None
        
        for i, word in enumerate(words):
            if not current_segment_words:
                # Start new segment
                segment_start = word["start"]
                current_segment_words = [word]
                continue
            
            # Check if we should end current segment
            current_duration = word["end"] - segment_start
            gap_from_previous = word["start"] - words[i-1]["end"]
            current_text = ' '.join([w['text'] for w in current_segment_words])
            new_text = f"{current_text} {word['text']}"
            
            # Check speaker change (if available)
            speaker_change = (
                word.get('speaker') is not None and 
                current_segment_words[-1].get('speaker') is not None and
                word.get('speaker') != current_segment_words[-1].get('speaker')
            )
            
            should_end_segment = (
                current_duration > max_duration or 
                gap_from_previous > min_gap or
                len(new_text) > max_chars or
                speaker_change
            )
            
            if should_end_segment:
                # End current segment
                segment_end = current_segment_words[-1]["end"]
                segment_text = ' '.join([w['text'] for w in current_segment_words])
                
                # Calculate average confidence if available
                confidences = [w.get('confidence', 0) for w in current_segment_words if w.get('confidence')]
                avg_confidence = sum(confidences) / len(confidences) if confidences else None
                
                segments.append({
                    'start_time': segment_start,
                    'end_time': segment_end,
                    'duration': segment_end - segment_start,
                    'text': segment_text,
                    'word_count': len(current_segment_words),
                    'confidence_score': avg_confidence,
                    'speaker': current_segment_words[0].get('speaker'),
                    'words': current_segment_words.copy()
                })
                
                # Start new segment
                segment_start = word["start"]
                current_segment_words = [word]
            else:
                current_segment_words.append(word)
        
        # Add final segment
        if current_segment_words and segment_start is not None:
            segment_end = current_segment_words[-1]["end"]
            segment_text = ' '.join([w['text'] for w in current_segment_words])
            
            # Calculate average confidence if available
            confidences = [w.get('confidence', 0) for w in current_segment_words if w.get('confidence')]
            avg_confidence = sum(confidences) / len(confidences) if confidences else None
            
            segments.append({
                'start_time': segment_start,
                'end_time': segment_end,
                'duration': segment_end - segment_start,
                'text': segment_text,
                'word_count': len(current_segment_words),
                'confidence_score': avg_confidence,
                'speaker': current_segment_words[0].get('speaker'),
                'words': current_segment_words.copy()
            })
        
        return segments
    
    def _create_fallback_segments(self, text: str, max_duration: float, max_chars: int) -> List[Dict[str, Any]]:
        """
        Create segments from text when timing data is unavailable.
        
        This method creates evenly-spaced segments based on character count
        and estimated reading speed when word-level timestamps are not available.
        """
        if not text.strip():
            return []
        
        # Split text into sentences first
        import re
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return []
        
        segments = []
        current_text = []
        estimated_start = 0.0
        
        # Estimate reading speed: ~150 words per minute = 2.5 words per second
        words_per_second = 2.5
        
        for i, sentence in enumerate(sentences):
            # Check if adding this sentence would exceed character limit
            current_combined = ' '.join(current_text + [sentence])
            
            if len(current_combined) > max_chars and current_text:
                # Finalize current segment
                segment_text = ' '.join(current_text)
                word_count = len(segment_text.split())
                estimated_duration = min(word_count / words_per_second, max_duration)
                
                segments.append({
                    'start_time': estimated_start,
                    'end_time': estimated_start + estimated_duration,
                    'duration': estimated_duration,
                    'text': segment_text,
                    'word_count': word_count,
                    'confidence_score': None,  # No confidence for fallback
                    'speaker': None,
                    'words': [],  # No word-level data
                    'fallback': True  # Mark as fallback segment
                })
                
                # Start new segment
                estimated_start += estimated_duration + 0.5  # Small gap between segments
                current_text = [sentence]
            else:
                current_text.append(sentence)
        
        # Add final segment
        if current_text:
            segment_text = ' '.join(current_text)
            word_count = len(segment_text.split())
            estimated_duration = min(word_count / words_per_second, max_duration)
            
            segments.append({
                'start_time': estimated_start,
                'end_time': estimated_start + estimated_duration,
                'duration': estimated_duration,
                'text': segment_text,
                'word_count': word_count,
                'confidence_score': None,
                'speaker': None,
                'words': [],
                'fallback': True
            })
        
        return segments
    
    def _create_text_only_segments(self, words: List[Dict[str, Any]], max_chars: int) -> List[Dict[str, Any]]:
        """
        Create segments from word list when timing data is invalid.
        
        This method creates segments based only on text content when
        words are available but lack proper timing information.
        """
        if not words:
            return []
        
        # Extract text from words
        word_texts = [w.get('text', '') for w in words if w.get('text')]
        full_text = ' '.join(word_texts)
        
        if not full_text.strip():
            return []
        
        # Use fallback method with the reconstructed text
        return self._create_fallback_segments(full_text, 4.0, max_chars)
    
    def store_subtitle_segments(self, interview_id: str, segments: List[Dict[str, Any]], 
                               database_path: Optional[str] = None) -> bool:
        """
        Store subtitle segments in the database.
        
        This method integrates with the subtitle-first architecture by storing
        segments with precise timing data that can be used for perfect subtitle
        synchronization.
        
        Args:
            interview_id: Unique identifier for the interview
            segments: List of segment dictionaries from create_subtitle_segments()
            database_path: Optional path to database (uses default if None)
            
        Returns:
            True if storage successful, False otherwise
        """
        try:
            from .database import Database
            
            # Initialize database connection
            if database_path:
                db = Database(database_path)
            else:
                db = Database()  # Uses default path
            
            # Store each segment
            for i, segment in enumerate(segments):
                db.add_subtitle_segment(
                    interview_id=interview_id,
                    segment_index=i,
                    start_time=segment['start_time'],
                    end_time=segment['end_time'],
                    original_text=segment['text'],
                    confidence_score=segment.get('confidence_score')
                )
            
            db.close()
            logger.info(f"Stored {len(segments)} subtitle segments for interview {interview_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store subtitle segments: {e}")
            return False
    
    def transcribe_with_subtitle_segments(self, file_path: Path, interview_id: str,
                                        database_path: Optional[str] = None,
                                        segment_params: Optional[Dict[str, Any]] = None) -> TranscriptionResult:
        """
        Transcribe a file and automatically create and store subtitle segments.
        
        This is the main method for the subtitle-first architecture workflow:
        1. Transcribe audio with word-level timestamps
        2. Create natural subtitle segments from word boundaries
        3. Store segments in database for perfect synchronization
        4. Return full transcription result
        
        Args:
            file_path: Path to media file
            interview_id: Unique identifier for the interview
            database_path: Optional path to database
            segment_params: Optional parameters for segment creation
            
        Returns:
            TranscriptionResult with populated segments data
        """
        # Set default segment parameters
        if segment_params is None:
            segment_params = {
                'max_duration': 4.0,
                'min_gap': 0.5,
                'max_chars': 40
            }
        
        # Perform transcription
        result = self.transcribe_file(file_path)
        
        # Create subtitle segments from word-level timestamps with fallback
        segments = self.create_subtitle_segments(
            result.words, 
            fallback_text=result.text,  # Use full transcript as fallback
            **segment_params
        )
        
        if segments:
            # Store segments in database
            success = self.store_subtitle_segments(interview_id, segments, database_path)
            
            if success:
                # Add segments to result for immediate use
                result.segments = segments
                fallback_count = sum(1 for s in segments if s.get('fallback', False))
                if fallback_count > 0:
                    logger.info(f"Successfully processed {file_path} with {len(segments)} subtitle segments ({fallback_count} fallback)")
                else:
                    logger.info(f"Successfully processed {file_path} with {len(segments)} subtitle segments")
            else:
                logger.warning("Transcription succeeded but segment storage failed")
        else:
            logger.warning("Unable to create subtitle segments - no word data or fallback text available")
        
        return result
    
    def save_results(self, result: TranscriptionResult, output_path: Path,
                    save_json: bool = True, save_srt: bool = True):
        """
        Save transcription results to files.
        
        Args:
            result: TranscriptionResult to save
            output_path: Base path for output files (without extension)
            save_json: Whether to save detailed JSON
            save_srt: Whether to save SRT subtitles
        """
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save text transcript
        text_path = output_path.with_suffix('.txt')
        text_path.write_text(result.text, encoding='utf-8')
        logger.info(f"Saved transcript: {text_path}")
        
        # Save detailed JSON
        if save_json:
            json_path = output_path.with_suffix('.json')
            
            # Create JSON-safe data by filtering out non-serializable objects
            def make_json_safe(obj):
                """Convert object to JSON-safe format."""
                if hasattr(obj, '__dict__') and not isinstance(obj, (str, int, float, bool, type(None))):
                    # For complex objects like Mock, convert to string representation
                    return str(obj)
                elif isinstance(obj, dict):
                    return {k: make_json_safe(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_json_safe(item) for item in obj]
                else:
                    return obj
            
            json_data = {
                'text': result.text,
                'language': make_json_safe(result.language),
                'confidence': result.confidence,
                'duration': result.duration,
                'words': make_json_safe(result.words),
                'speakers': make_json_safe(result.speakers),
                'segments': make_json_safe(result.segments),
                'metadata': make_json_safe(result.metadata)
            }
            
            json_path.write_text(
                json.dumps(json_data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            logger.info(f"Saved JSON: {json_path}")
        
        # Save SRT subtitles
        if save_srt and result.words:
            srt_path = output_path.with_suffix('.srt')
            srt_content = self._create_srt(result.words)
            srt_path.write_text(srt_content, encoding='utf-8')
            logger.info(f"Saved SRT: {srt_path}")
    
    def _create_srt(self, words: List[Dict[str, Any]], 
                   max_chars: int = 40, max_duration: float = 5.0) -> str:
        """Create SRT subtitle content from word timings."""
        if not words:
            return ""
        
        srt_lines = []
        subtitle_index = 1
        current_line = []
        start_time = None
        
        for word in words:
            if 'start' not in word or 'end' not in word:
                continue
            
            # Initialize subtitle
            if not current_line:
                start_time = word['start']
                current_line.append(word['text'])
                continue
            
            # Check constraints
            current_text = ' '.join(current_line)
            new_text = f"{current_text} {word['text']}"
            duration = word['end'] - start_time
            
            if len(new_text) > max_chars or duration > max_duration:
                # Finalize current subtitle
                end_time = words[words.index(word) - 1]['end']
                
                srt_lines.append(str(subtitle_index))
                srt_lines.append(f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}")
                srt_lines.append(current_text)
                srt_lines.append("")
                
                # Start new subtitle
                subtitle_index += 1
                current_line = [word['text']]
                start_time = word['start']
            else:
                current_line.append(word['text'])
        
        # Add final subtitle
        if current_line and start_time is not None:
            srt_lines.append(str(subtitle_index))
            srt_lines.append(f"{self._format_srt_time(start_time)} --> {self._format_srt_time(words[-1]['end'])}")
            srt_lines.append(' '.join(current_line))
            srt_lines.append("")
        
        return '\n'.join(srt_lines)
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds as SRT timestamp (00:00:00,000)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# Convenience function for simple usage
def transcribe(file_path: str, api_key: str, output_dir: Optional[str] = None,
              **config_kwargs) -> TranscriptionResult:
    """
    Simple interface to transcribe a file.
    
    Args:
        file_path: Path to audio/video file
        api_key: ElevenLabs API key
        output_dir: Directory to save outputs (optional)
        **config_kwargs: Additional configuration options
        
    Returns:
        TranscriptionResult
    """
    # Create configuration
    config = TranscriptionConfig(api_key=api_key, **config_kwargs)
    
    # Create transcriber
    transcriber = Transcriber(config)
    
    # Transcribe file
    result = transcriber.transcribe_file(Path(file_path))
    
    # Save outputs if requested
    if output_dir:
        output_path = Path(output_dir) / Path(file_path).stem
        transcriber.save_results(result, output_path)
    
    return result


def transcribe_file(file_path: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Convenience function to transcribe a single file.
    
    Args:
        file_path: Path to the media file
        output_dir: Directory for output files
        
    Returns:
        Dictionary with transcription results
    """
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY environment variable not set")
        
    result = transcribe(file_path, api_key, output_dir)
    
    return {
        'file_path': file_path,
        'output_path': result.output_path,
        'language': result.language,
        'duration': getattr(result, 'duration', None),
        'words': len(result.words),
        'text': result.text,
        'success': True
    }


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python transcribe.py <file_path> <api_key> [output_dir]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    api_key = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        result = transcribe(file_path, api_key, output_dir)
        print(f"\nTranscription completed!")
        print(f"Language: {result.language}")
        print(f"Words: {len(result.words)}")
        print(f"Text preview: {result.text[:200]}...")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        sys.exit(1)
