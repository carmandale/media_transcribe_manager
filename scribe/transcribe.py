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
        
        # Extract words with timing
        words = []
        if hasattr(response, 'words') and response.words:
            try:
                for word in response.words:
                    words.append({
                        'text': word.text,
                        'start': word.start,
                        'end': word.end,
                        'speaker': getattr(word, 'speaker', None)
                    })
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
            json_data = {
                'text': result.text,
                'language': result.language,
                'confidence': result.confidence,
                'duration': result.duration,
                'words': result.words,
                'speakers': result.speakers,
                'segments': result.segments,
                'metadata': result.metadata
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
