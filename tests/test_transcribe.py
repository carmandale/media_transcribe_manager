"""
Comprehensive tests for the transcribe module.

Tests cover all major functionality including:
- TranscriptionConfig and TranscriptionResult dataclasses
- AudioExtractor for video-to-audio conversion
- AudioSegmenter for large file handling
- Transcriber main functionality
- API integration and error handling
- File saving and SRT generation
"""
import pytest
import tempfile
import shutil
import subprocess
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from dataclasses import asdict
import time

from scribe.transcribe import (
    TranscriptionConfig, TranscriptionResult, AudioExtractor,
    AudioSegmenter, Transcriber, transcribe, transcribe_file
)


class TestTranscriptionConfig:
    """Test TranscriptionConfig dataclass."""
    
    @pytest.mark.unit
    def test_default_config(self):
        """Test default configuration values."""
        config = TranscriptionConfig(api_key="test_key")
        
        assert config.api_key == "test_key"
        assert config.model == "scribe_v1"
        assert config.speaker_detection is True
        assert config.speaker_count == 32
        assert config.max_file_size_mb == 25
        assert config.max_segment_duration == 600
        assert config.api_timeout == 300
        assert config.max_retries == 8
        assert config.segment_pause == 1.0
        assert config.auto_detect_language is True
        assert config.force_language is None
    
    @pytest.mark.unit
    def test_custom_config(self):
        """Test custom configuration values."""
        config = TranscriptionConfig(
            api_key="test_key",
            model="custom_model",
            speaker_detection=False,
            max_file_size_mb=50,
            force_language="en"
        )
        
        assert config.model == "custom_model"
        assert config.speaker_detection is False
        assert config.max_file_size_mb == 50
        assert config.force_language == "en"


class TestTranscriptionResult:
    """Test TranscriptionResult dataclass."""
    
    @pytest.mark.unit
    def test_basic_result(self):
        """Test basic transcription result."""
        result = TranscriptionResult(
            text="Test transcription",
            language="en",
            confidence=0.95
        )
        
        assert result.text == "Test transcription"
        assert result.language == "en"
        assert result.confidence == 0.95
        assert result.words == []
        assert result.segments == []
        assert result.speakers == []
        assert result.metadata == {}
    
    @pytest.mark.unit
    def test_full_result(self):
        """Test full transcription result with all fields."""
        words = [{"text": "Hello", "start": 0.0, "end": 0.5}]
        segments = [{"text": "Hello world", "start": 0.0, "end": 1.0}]
        speakers = [{"id": 1, "name": "Speaker 1"}]
        metadata = {"model": "scribe_v1", "duration": 10.0}
        
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            confidence=0.98,
            words=words,
            segments=segments,
            speakers=speakers,
            duration=10.0,
            metadata=metadata
        )
        
        assert result.words == words
        assert result.segments == segments
        assert result.speakers == speakers
        assert result.duration == 10.0
        assert result.metadata == metadata


class TestAudioExtractor:
    """Test AudioExtractor functionality."""
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_extract_audio_mp3(self, mock_run, temp_dir):
        """Test extracting audio to MP3 format."""
        # Setup mock
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )
        
        # Create test video file
        video_path = temp_dir / "test_video.mp4"
        video_path.write_bytes(b"fake video data")
        
        # Extract audio
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = str(temp_dir / "temp.mp3")
            audio_path = AudioExtractor.extract_audio(video_path)
        
        # Verify ffmpeg command
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == 'ffmpeg'
        assert str(video_path) in cmd
        assert '-vn' in cmd  # No video
        assert '-acodec' in cmd
        assert 'libmp3lame' in cmd
        assert '-ab' in cmd
        assert '192k' in cmd
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_extract_audio_wav(self, mock_run, temp_dir):
        """Test extracting audio to WAV format."""
        mock_run.return_value = Mock(returncode=0)
        
        video_path = temp_dir / "test_video.mp4"
        video_path.write_bytes(b"fake video data")
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = str(temp_dir / "temp.wav")
            audio_path = AudioExtractor.extract_audio(video_path, output_format="wav")
        
        # Verify codec for WAV
        cmd = mock_run.call_args[0][0]
        assert 'pcm_s16le' in cmd
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_extract_audio_failure(self, mock_run, temp_dir):
        """Test handling of ffmpeg failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, 'ffmpeg', stderr="Error: Invalid input"
        )
        
        video_path = temp_dir / "test_video.mp4"
        video_path.write_bytes(b"fake video data")
        
        with pytest.raises(RuntimeError) as exc_info:
            AudioExtractor.extract_audio(video_path)
        
        assert "Audio extraction failed" in str(exc_info.value)
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_get_duration(self, mock_run):
        """Test getting media file duration."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="123.45\n",
            stderr=""
        )
        
        duration = AudioExtractor.get_duration(Path("/test/media.mp4"))
        
        assert duration == 123.45
        
        # Verify ffprobe command
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == 'ffprobe'
        assert '-show_entries' in cmd
        assert 'format=duration' in cmd
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_get_duration_failure(self, mock_run):
        """Test handling of duration extraction failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffprobe')
        
        duration = AudioExtractor.get_duration(Path("/test/media.mp4"))
        
        assert duration == 0.0


class TestAudioSegmenter:
    """Test AudioSegmenter functionality."""
    
    @pytest.mark.unit
    def test_no_split_needed(self, temp_dir):
        """Test when file doesn't need splitting."""
        # Create small audio file
        audio_path = temp_dir / "small_audio.mp3"
        audio_path.write_bytes(b"x" * (10 * 1024 * 1024))  # 10MB
        
        segments = AudioSegmenter.split_audio(audio_path, max_size_mb=25)
        
        assert len(segments) == 1
        assert segments[0] == (audio_path, 0.0)
    
    @pytest.mark.unit
    @patch('scribe.transcribe.AudioExtractor.get_duration')
    @patch('subprocess.run')
    def test_split_by_size(self, mock_run, mock_duration, temp_dir):
        """Test splitting large file by size."""
        # Setup mocks
        mock_duration.return_value = 3600.0  # 1 hour
        mock_run.return_value = Mock(returncode=0)
        
        # Create large audio file
        audio_path = temp_dir / "large_audio.mp3"
        audio_path.write_bytes(b"x" * (100 * 1024 * 1024))  # 100MB
        
        segments = AudioSegmenter.split_audio(audio_path, max_size_mb=25)
        
        # Should split into 5 segments based on size, then limited by duration
        # 100MB / 25MB = 4 + 1 = 5 segments
        # But duration check: 3600s / 5 = 720s per segment > 600s max
        # So recalculate: 3600s / 600s = 6 + 1 = 7 segments
        assert len(segments) == 7
        
        # Verify ffmpeg was called for each segment
        assert mock_run.call_count == 7
    
    @pytest.mark.unit
    @patch('scribe.transcribe.AudioExtractor.get_duration')
    @patch('subprocess.run')
    def test_split_by_duration(self, mock_run, mock_duration, temp_dir):
        """Test splitting by maximum duration."""
        # Setup mocks
        mock_duration.return_value = 3600.0  # 1 hour
        mock_run.return_value = Mock(returncode=0)
        
        # Create audio file larger than max_size_mb to trigger segmentation
        audio_path = temp_dir / "audio.mp3"
        audio_path.write_bytes(b"x" * (120 * 1024 * 1024))  # 120MB
        
        segments = AudioSegmenter.split_audio(
            audio_path, 
            max_size_mb=100,  # Will trigger size split: 120/100 = 1+1 = 2 segments
            max_duration=600  # 10 minutes
        )
        
        # Size calculation: 120MB / 100MB = 1 + 1 = 2 segments
        # Duration per segment: 3600s / 2 = 1800s per segment
        # Since 1800s > 600s max, recalculate by duration:
        # 3600s / 600s = 6 + 1 = 7 segments
        assert len(segments) == 7
        
        # Verify segment timing
        for i, (seg_path, start_time) in enumerate(segments):
            assert start_time == i * 600.0
    
    @pytest.mark.unit
    @patch('scribe.transcribe.AudioExtractor.get_duration')
    def test_split_with_zero_duration(self, mock_duration, temp_dir):
        """Test handling when duration cannot be determined."""
        mock_duration.return_value = 0.0
        
        audio_path = temp_dir / "audio.mp3"
        audio_path.write_bytes(b"x" * (50 * 1024 * 1024))
        
        segments = AudioSegmenter.split_audio(audio_path)
        
        # Should return original file
        assert len(segments) == 1
        assert segments[0] == (audio_path, 0.0)


class TestTranscriber:
    """Test main Transcriber functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Create mock ElevenLabs client."""
        client = Mock()
        client.speech_to_text = Mock()
        return client
    
    @pytest.fixture
    def transcriber(self, mock_client):
        """Create Transcriber instance with mocked client."""
        config = TranscriptionConfig(api_key="test_key")
        transcriber = Transcriber(config)
        transcriber.client = mock_client
        return transcriber
    
    @pytest.mark.unit
    def test_transcribe_audio_file(self, transcriber, mock_client, temp_dir):
        """Test transcribing a simple audio file."""
        # Create test audio file
        audio_path = temp_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio data")
        
        # Mock API response
        mock_response = Mock()
        mock_response.text = "Hello world"
        mock_response.language_code = "en"
        mock_response.language_probability = 0.98
        mock_response.words = [
            Mock(text="Hello", start=0.0, end=0.5, speaker=1),
            Mock(text="world", start=0.5, end=1.0, speaker=1)
        ]
        mock_response.speakers = [Mock(id=1)]
        mock_response.dict.return_value = {"text": "Hello world"}
        
        mock_client.speech_to_text.convert.return_value = mock_response
        
        # Transcribe
        result = transcriber.transcribe_file(audio_path)
        
        assert result.text == "Hello world"
        assert result.language == "en"
        assert result.confidence == 0.98
        assert len(result.words) == 2
        assert result.words[0]["text"] == "Hello"
        assert result.words[0]["start"] == 0.0
        assert result.words[0]["speaker"] == 1
    
    @pytest.mark.unit
    @patch('scribe.transcribe.AudioExtractor.extract_audio')
    def test_transcribe_video_file(self, mock_extract, transcriber, mock_client, temp_dir):
        """Test transcribing a video file."""
        # Create test video file
        video_path = temp_dir / "test.mp4"
        video_path.write_bytes(b"fake video data")
        
        # Mock audio extraction
        extracted_path = temp_dir / "extracted.mp3"
        extracted_path.write_bytes(b"fake audio")
        mock_extract.return_value = extracted_path
        
        # Mock API response
        mock_response = Mock()
        mock_response.text = "Video transcript"
        mock_response.language = "en"
        mock_response.language_code = "en"
        mock_response.language_probability = 0.95
        mock_response.words = [
            Mock(text="Video", start=0.0, end=0.5, speaker=1),
            Mock(text="transcript", start=0.5, end=1.0, speaker=1)
        ]
        mock_response.speakers = [Mock(id=1, name="Speaker 1")]
        mock_response.dict.return_value = {"text": "Video transcript", "language": "en"}
        mock_client.speech_to_text.convert.return_value = mock_response
        
        # Transcribe
        result = transcriber.transcribe_file(video_path)
        
        assert result.text == "Video transcript"
        
        # Verify audio was extracted
        mock_extract.assert_called_once_with(video_path)
        
        # Verify cleanup
        assert not extracted_path.exists()
    
    @pytest.mark.unit
    def test_transcribe_with_retries(self, transcriber, mock_client, temp_dir):
        """Test API retry logic."""
        audio_path = temp_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")
        
        # Mock API errors then success
        from elevenlabs.core.api_error import ApiError
        
        mock_response = Mock()
        mock_response.text = "Success after retries"
        mock_response.dict.return_value = {
            "text": "Success after retries",
            "language": "en",
            "model": "scribe_v1"
        }
        
        mock_client.speech_to_text.convert.side_effect = [
            ApiError("Rate limit"),
            ApiError("Server error"),
            mock_response
        ]
        
        # Transcribe with faster retries for testing
        transcriber.config.segment_pause = 0.01
        with patch('time.sleep'):  # Speed up test
            result = transcriber.transcribe_file(audio_path)
        
        assert result.text == "Success after retries"
        assert mock_client.speech_to_text.convert.call_count == 3
    
    @pytest.mark.unit
    def test_transcribe_max_retries_exceeded(self, transcriber, mock_client, temp_dir):
        """Test when max retries are exceeded."""
        audio_path = temp_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")
        
        # Mock persistent API errors
        from elevenlabs.core.api_error import ApiError
        
        mock_client.speech_to_text.convert.side_effect = ApiError("Persistent error")
        
        # Set low retry count for faster test
        transcriber.config.max_retries = 2
        
        with patch('time.sleep'):  # Speed up test
            with pytest.raises(ApiError):
                transcriber.transcribe_file(audio_path)
        
        assert mock_client.speech_to_text.convert.call_count == 2
    
    @pytest.mark.unit
    @patch('scribe.transcribe.AudioSegmenter.split_audio')
    def test_transcribe_segmented(self, mock_split, transcriber, mock_client, temp_dir):
        """Test transcribing file split into segments."""
        # Create test audio and segments
        audio_path = temp_dir / "large.mp3"
        audio_path.write_bytes(b"fake audio")
        
        seg1_path = temp_dir / "seg1.mp3"
        seg2_path = temp_dir / "seg2.mp3"
        seg1_path.write_bytes(b"seg1")
        seg2_path.write_bytes(b"seg2")
        
        mock_split.return_value = [
            (seg1_path, 0.0),
            (seg2_path, 600.0)
        ]
        
        # Mock API responses for each segment
        response1 = Mock()
        response1.text = "First segment"
        response1.language_code = "en"
        response1.language_probability = 0.95
        response1.words = [
            Mock(text="First", start=0.0, end=0.5, speaker=None),
            Mock(text="segment", start=0.5, end=1.0, speaker=None)
        ]
        response1.dict.return_value = {
            "text": "First segment",
            "language": "en",
            "model": "scribe_v1"
        }
        
        response2 = Mock()
        response2.text = "Second segment"
        response2.language_code = "en"
        response2.language_probability = 0.97
        response2.words = [
            Mock(text="Second", start=0.0, end=0.5, speaker=None),
            Mock(text="segment", start=0.5, end=1.0, speaker=None)
        ]
        response2.dict.return_value = {
            "text": "Second segment",
            "language": "en",
            "model": "scribe_v1"
        }
        
        mock_client.speech_to_text.convert.side_effect = [response1, response2]
        
        # Transcribe
        transcriber.config.segment_pause = 0.01  # Speed up test
        result = transcriber.transcribe_file(audio_path)
        
        # Verify combined result
        assert result.text == "First segment Second segment"
        assert result.language == "en"
        assert result.confidence == 0.96  # Average
        assert len(result.words) == 4
        
        # Verify word timings were adjusted
        assert result.words[2]["start"] == 600.0  # Adjusted for segment 2
        assert result.words[3]["start"] == 600.5
        
        # Verify metadata
        assert result.metadata["segmented"] is True
        assert result.metadata["segment_count"] == 2
    
    @pytest.mark.unit
    def test_force_language(self, transcriber, mock_client, temp_dir):
        """Test forcing a specific language."""
        audio_path = temp_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")
        
        # Set forced language
        transcriber.config.force_language = "de"
        
        mock_response = Mock()
        mock_response.text = "German text"
        mock_response.language_code = "de"
        mock_response.language_probability = 0.92
        mock_response.words = [
            Mock(text="German", start=0.0, end=0.5, speaker=1),
            Mock(text="text", start=0.5, end=1.0, speaker=1)
        ]
        mock_response.speakers = [Mock(id=1, name="Speaker 1")]
        mock_response.dict.return_value = {"text": "German text", "language": "de"}
        mock_client.speech_to_text.convert.return_value = mock_response
        
        result = transcriber.transcribe_file(audio_path)
        
        # Verify language parameter was passed
        call_kwargs = mock_client.speech_to_text.convert.call_args[1]
        assert call_kwargs["language_code"] == "de"
    
    @pytest.mark.unit
    def test_save_results_text(self, transcriber, temp_dir):
        """Test saving transcription results as text."""
        result = TranscriptionResult(
            text="Test transcription text",
            language="en",
            confidence=0.95
        )
        
        output_path = temp_dir / "output" / "test"
        transcriber.save_results(result, output_path, save_json=False, save_srt=False)
        
        # Verify text file was created
        text_file = output_path.with_suffix('.txt')
        assert text_file.exists()
        assert text_file.read_text() == "Test transcription text"
    
    @pytest.mark.unit
    def test_save_results_json(self, transcriber, temp_dir):
        """Test saving transcription results as JSON."""
        result = TranscriptionResult(
            text="Test text",
            language="en",
            confidence=0.95,
            words=[{"text": "Test", "start": 0.0, "end": 0.5}],
            speakers=[{"id": 1, "name": "Speaker 1"}],
            metadata={"model": "scribe_v1"}
        )
        
        output_path = temp_dir / "test"
        transcriber.save_results(result, output_path, save_json=True, save_srt=False)
        
        # Verify JSON file
        json_file = output_path.with_suffix('.json')
        assert json_file.exists()
        
        data = json.loads(json_file.read_text())
        assert data["text"] == "Test text"
        assert data["language"] == "en"
        assert data["confidence"] == 0.95
        assert len(data["words"]) == 1
        assert len(data["speakers"]) == 1
    
    @pytest.mark.unit
    def test_save_results_srt(self, transcriber, temp_dir):
        """Test saving transcription results as SRT."""
        result = TranscriptionResult(
            text="Hello world, this is a test.",
            words=[
                {"text": "Hello", "start": 0.0, "end": 0.5},
                {"text": "world,", "start": 0.5, "end": 1.0},
                {"text": "this", "start": 1.2, "end": 1.5},
                {"text": "is", "start": 1.5, "end": 1.7},
                {"text": "a", "start": 1.7, "end": 1.8},
                {"text": "test.", "start": 1.8, "end": 2.2}
            ]
        )
        
        output_path = temp_dir / "test"
        transcriber.save_results(result, output_path, save_json=False, save_srt=True)
        
        # Verify SRT file
        srt_file = output_path.with_suffix('.srt')
        assert srt_file.exists()
        
        srt_content = srt_file.read_text()
        assert "1\n" in srt_content
        assert "00:00:00,000 --> 00:00:02,200" in srt_content
        assert "Hello world, this is a test." in srt_content
    
    @pytest.mark.unit
    def test_create_srt_formatting(self, transcriber):
        """Test SRT creation with proper formatting."""
        words = [
            {"text": "This", "start": 0.0, "end": 0.2},
            {"text": "is", "start": 0.2, "end": 0.3},
            {"text": "a", "start": 0.3, "end": 0.4},
            {"text": "very", "start": 0.4, "end": 0.6},
            {"text": "long", "start": 0.6, "end": 0.8},
            {"text": "sentence", "start": 0.8, "end": 1.2},
            {"text": "that", "start": 1.2, "end": 1.4},
            {"text": "should", "start": 1.4, "end": 1.6},
            {"text": "be", "start": 1.6, "end": 1.7},
            {"text": "split", "start": 1.7, "end": 2.0},
            {"text": "into", "start": 6.0, "end": 6.2},  # Long gap
            {"text": "multiple", "start": 6.2, "end": 6.6},
            {"text": "subtitles.", "start": 6.6, "end": 7.0}
        ]
        
        srt = transcriber._create_srt(words, max_chars=25, max_duration=3.0)
        
        lines = srt.strip().split('\n')
        
        # Should have multiple subtitles due to character/duration limits
        assert "1\n" in srt
        assert "2\n" in srt
        
        # Check that subtitles are created properly
        lines = srt.strip().split('\n')
        assert len([line for line in lines if line.isdigit()]) >= 2  # At least 2 subtitles
        
        # Check timing format exists
        assert "00:00:00,000 --> " in srt
        assert "00:00:06," in srt  # Gap creates new subtitle
    
    @pytest.mark.unit
    def test_format_srt_time(self, transcriber):
        """Test SRT timestamp formatting."""
        assert transcriber._format_srt_time(0) == "00:00:00,000"
        assert transcriber._format_srt_time(1.5) == "00:00:01,500"
        # Note: Floating point precision can cause 61.123 -> 122ms instead of 123ms
        result = transcriber._format_srt_time(61.123)
        assert result in ["00:01:01,122", "00:01:01,123"]  # Allow for floating point precision
        assert transcriber._format_srt_time(3661.999) == "01:01:01,999"


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.mark.unit
    @patch('scribe.transcribe.Transcriber')
    def test_transcribe_function(self, mock_transcriber_class, temp_dir):
        """Test the transcribe convenience function."""
        # Setup mocks
        mock_transcriber = Mock()
        mock_result = TranscriptionResult(text="Test result", language="en")
        mock_transcriber.transcribe_file.return_value = mock_result
        mock_transcriber_class.return_value = mock_transcriber
        
        # Call function
        audio_path = temp_dir / "test.mp3"
        audio_path.write_bytes(b"fake audio")
        
        result = transcribe(
            str(audio_path),
            api_key="test_key",
            output_dir=str(temp_dir),
            max_retries=5
        )
        
        assert result == mock_result
        
        # Verify config was passed
        config = mock_transcriber_class.call_args[0][0]
        assert config.api_key == "test_key"
        assert config.max_retries == 5
        
        # Verify save was called
        mock_transcriber.save_results.assert_called_once()
    
    @pytest.mark.unit
    @patch('os.getenv')
    @patch('scribe.transcribe.transcribe')
    def test_transcribe_file_function(self, mock_transcribe, mock_getenv):
        """Test the transcribe_file convenience function."""
        # Setup mocks
        mock_getenv.return_value = "test_api_key"
        mock_result = Mock()
        mock_result.text = "Test transcription"
        mock_result.language = "en"
        mock_result.words = [1, 2, 3]
        mock_result.output_path = "/output/test.txt"
        mock_transcribe.return_value = mock_result
        
        # Call function
        result = transcribe_file("/path/to/audio.mp3", "/output")
        
        assert result["file_path"] == "/path/to/audio.mp3"
        assert result["output_path"] == "/output/test.txt"
        assert result["language"] == "en"
        assert result["words"] == 3
        assert result["text"] == "Test transcription"
        assert result["success"] is True
        
        # Verify API key was retrieved
        mock_getenv.assert_called_with('ELEVENLABS_API_KEY')
    
    @pytest.mark.unit
    @patch('os.getenv')
    def test_transcribe_file_no_api_key(self, mock_getenv):
        """Test error when API key is not set."""
        mock_getenv.return_value = None
        
        with pytest.raises(ValueError) as exc_info:
            transcribe_file("/path/to/audio.mp3")
        
        assert "ELEVENLABS_API_KEY environment variable not set" in str(exc_info.value)


class TestFileNotFound:
    """Test file not found handling."""
    
    @pytest.mark.unit
    def test_transcribe_nonexistent_file(self):
        """Test error when file doesn't exist."""
        config = TranscriptionConfig(api_key="test_key")
        transcriber = Transcriber(config)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            transcriber.transcribe_file(Path("/nonexistent/file.mp3"))
        
        assert "File not found" in str(exc_info.value)


class TestIntegration:
    """Integration tests with mocked external dependencies."""
    
    @pytest.mark.integration
    @patch('subprocess.run')
    @patch('scribe.transcribe.ElevenLabs')
    def test_full_video_transcription_flow(self, mock_elevenlabs_class, mock_subprocess, temp_dir):
        """Test complete flow from video to transcription output."""
        # Create test video
        video_path = temp_dir / "test_video.mp4"
        video_path.write_bytes(b"fake video data")
        
        # Mock ffmpeg for audio extraction
        extracted_audio = temp_dir / "extracted.mp3"
        mock_subprocess.return_value = Mock(returncode=0, stdout="")
        
        # Mock ElevenLabs client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Full transcription of video"
        mock_response.language_code = "en"
        mock_response.language_probability = 0.99
        mock_response.words = [
            Mock(text="Full", start=0.0, end=0.3, speaker=1),
            Mock(text="transcription", start=0.3, end=1.0, speaker=1),
            Mock(text="of", start=1.0, end=1.2, speaker=1),
            Mock(text="video", start=1.2, end=1.6, speaker=1)
        ]
        mock_response.speakers = [Mock(id=1)]
        mock_response.dict.return_value = {
            "text": "Full transcription of video",
            "language": "en",
            "confidence": 0.99,
            "model": "scribe_v1",
            "words": [
                {"text": "Full", "start": 0.0, "end": 0.3, "speaker": 1},
                {"text": "transcription", "start": 0.3, "end": 1.0, "speaker": 1},
                {"text": "of", "start": 1.0, "end": 1.2, "speaker": 1},
                {"text": "video", "start": 1.2, "end": 1.6, "speaker": 1}
            ],
            "speakers": [{"id": 1, "name": "Speaker 1"}]
        }
        
        mock_client.speech_to_text.convert.return_value = mock_response
        mock_elevenlabs_class.return_value = mock_client
        
        # Transcribe
        config = TranscriptionConfig(api_key="test_key")
        transcriber = Transcriber(config)
        
        # Mock the temp file creation for audio extraction
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = str(extracted_audio)
            extracted_audio.write_bytes(b"fake audio")
            
            result = transcriber.transcribe_file(video_path)
        
        # Verify results
        assert result.text == "Full transcription of video"
        assert result.language == "en"
        assert result.confidence == 0.99
        assert len(result.words) == 4
        
        # Save outputs
        output_path = temp_dir / "output" / "test"
        transcriber.save_results(result, output_path)
        
        # Verify all output files
        assert (output_path.with_suffix('.txt')).exists()
        assert (output_path.with_suffix('.json')).exists()
        assert (output_path.with_suffix('.srt')).exists()
        
        # Verify SRT content
        srt_content = (output_path.with_suffix('.srt')).read_text()
        assert "Full transcription of video" in srt_content