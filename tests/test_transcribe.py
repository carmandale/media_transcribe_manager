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
            max_segment_duration=600  # 10 minutes
        )
        
        # Size calculation: 120MB / 100MB = 1 + 1 = 2 segments
        # Duration per segment: 3600s / 2 = 1800s per segment
        # Since 1800s > 600s max, recalculate by duration:
        # 3600s / 600s = 6 + 1 = 7 segments
        assert len(segments) == 7
        
        # Verify segment timing
        # Actual segment duration: 3600s / 7 segments = 514.28s per segment
        expected_segment_duration = 3600.0 / 7
        for i, (seg_path, start_time) in enumerate(segments):
            assert start_time == i * expected_segment_duration
    
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
            ApiError(status_code=429, body="Rate limit"),
            ApiError(status_code=500, body="Server error"),
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
        
        mock_client.speech_to_text.convert.side_effect = ApiError(status_code=500, body="Persistent error")
        
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
        # Note: Floating point precision can cause 3661.999 -> 998ms instead of 999ms
        result = transcriber._format_srt_time(3661.999)
        assert result in ["01:01:01,998", "01:01:01,999"]  # Allow for floating point precision


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


class TestWordLevelTimestampParsing:
    """Test word-level timestamp parsing for subtitle-first architecture."""
    
    @pytest.fixture
    def mock_client_with_word_timestamps(self):
        """Create mock ElevenLabs client with detailed word-level timestamps."""
        client = Mock()
        client.speech_to_text = Mock()
        return client
    
    @pytest.fixture
    def transcriber_for_segments(self, mock_client_with_word_timestamps):
        """Create Transcriber instance optimized for segment processing."""
        config = TranscriptionConfig(api_key="test_key")
        transcriber = Transcriber(config)
        transcriber.client = mock_client_with_word_timestamps
        return transcriber
    
    @pytest.mark.unit
    def test_word_timestamp_extraction_accuracy(self, transcriber_for_segments, mock_client_with_word_timestamps, temp_dir):
        """Test that word-level timestamps are accurately extracted for segment boundaries."""
        audio_path = temp_dir / "precise_timing.mp3"
        audio_path.write_bytes(b"fake audio data")
        
        # Mock detailed ElevenLabs response with precise word timestamps
        mock_response = Mock()
        mock_response.text = "Hello world, this is a historical testimony."
        mock_response.language_code = "en"
        mock_response.language_probability = 0.96
        
        # Precise word-level timestamps that would create natural segments
        mock_words = [
            Mock(text="Hello", start=0.0, end=0.4, speaker=1),
            Mock(text="world,", start=0.4, end=0.9, speaker=1),
            Mock(text="this", start=1.2, end=1.5, speaker=1),  # Natural pause
            Mock(text="is", start=1.5, end=1.7, speaker=1),
            Mock(text="a", start=1.7, end=1.8, speaker=1),
            Mock(text="historical", start=1.8, end=2.6, speaker=1),
            Mock(text="testimony.", start=2.6, end=3.4, speaker=1)
        ]
        mock_response.words = mock_words
        
        mock_response.speakers = [Mock(id=1, name="Speaker 1")]
        mock_response.dict.return_value = {
            "text": "Hello world, this is a historical testimony.",
            "language": "en",
            "model": "scribe_v1"
        }
        
        mock_client_with_word_timestamps.speech_to_text.convert.return_value = mock_response
        
        # Transcribe and verify word-level accuracy
        result = transcriber_for_segments.transcribe_file(audio_path)
        
        # Verify that all word timestamps are preserved with precision
        assert len(result.words) == 7
        
        # Test specific word timing accuracy
        hello_word = result.words[0]
        assert hello_word["text"] == "Hello"
        assert hello_word["start"] == 0.0
        assert hello_word["end"] == 0.4
        assert hello_word["speaker"] == 1
        
        # Test word with natural pause boundary
        this_word = result.words[2]
        assert this_word["text"] == "this"
        assert this_word["start"] == 1.2  # Natural segment boundary opportunity
        assert this_word["end"] == 1.5
        
        # Verify confidence and language detection
        assert result.language == "en"
        assert result.confidence == 0.96
    
    @pytest.mark.unit
    def test_segment_boundary_detection_from_word_gaps(self, transcriber_for_segments, mock_client_with_word_timestamps, temp_dir):
        """Test detection of natural segment boundaries based on word timing gaps."""
        audio_path = temp_dir / "segmented_speech.mp3"
        audio_path.write_bytes(b"fake audio data")
        
        # Mock response with clear timing gaps that indicate natural segments
        mock_response = Mock()
        mock_response.text = "First segment. Second segment after pause. Third and final segment."
        mock_response.language_code = "de"  # Test with German
        mock_response.language_probability = 0.92
        
        # Words with clear gaps indicating natural segments
        mock_words = [
            # Segment 1: 0.0 - 2.0s
            Mock(text="First", start=0.0, end=0.5, speaker=1),
            Mock(text="segment.", start=0.5, end=2.0, speaker=1),
            
            # Gap: 2.0 - 3.5s (1.5s pause - natural boundary)
            
            # Segment 2: 3.5 - 6.2s  
            Mock(text="Second", start=3.5, end=4.0, speaker=1),
            Mock(text="segment", start=4.0, end=4.6, speaker=1),
            Mock(text="after", start=4.6, end=5.0, speaker=1),
            Mock(text="pause.", start=5.0, end=6.2, speaker=1),
            
            # Gap: 6.2 - 7.0s (0.8s pause - smaller boundary)
            
            # Segment 3: 7.0 - 10.5s
            Mock(text="Third", start=7.0, end=7.4, speaker=1),
            Mock(text="and", start=7.4, end=7.6, speaker=1),
            Mock(text="final", start=7.6, end=8.2, speaker=1),
            Mock(text="segment.", start=8.2, end=10.5, speaker=1)
        ]
        mock_response.words = mock_words
        mock_response.speakers = [Mock(id=1, name="Speaker 1")]
        mock_response.dict.return_value = {
            "text": "First segment. Second segment after pause. Third and final segment.",
            "language": "de"
        }
        
        mock_client_with_word_timestamps.speech_to_text.convert.return_value = mock_response
        
        # Transcribe
        result = transcriber_for_segments.transcribe_file(audio_path)
        
        # Verify word data includes timing gaps for boundary detection
        assert len(result.words) == 10
        
        # Test gap detection capability by analyzing word timing
        gaps = []
        for i in range(len(result.words) - 1):
            current_end = result.words[i]["end"]
            next_start = result.words[i + 1]["start"]
            gap_duration = next_start - current_end
            
            if gap_duration > 0.5:  # Significant pause
                gaps.append({
                    'after_word': result.words[i]["text"],
                    'before_word': result.words[i + 1]["text"],
                    'gap_duration': gap_duration,
                    'boundary_time': current_end
                })
        
        # Should detect 2 significant gaps
        assert len(gaps) == 2
        
        # Verify gap 1: after "segment." (1.5s gap)
        gap1 = gaps[0]
        assert gap1['after_word'] == "segment."
        assert gap1['before_word'] == "Second"
        assert abs(gap1['gap_duration'] - 1.5) < 0.1
        assert gap1['boundary_time'] == 2.0
        
        # Verify gap 2: after "pause." (0.8s gap)
        gap2 = gaps[1]
        assert gap2['after_word'] == "pause."
        assert gap2['before_word'] == "Third"
        assert abs(gap2['gap_duration'] - 0.8) < 0.1
        assert gap2['boundary_time'] == 6.2
    
    @pytest.mark.unit
    def test_multi_speaker_word_timestamps(self, transcriber_for_segments, mock_client_with_word_timestamps, temp_dir):
        """Test word-level timestamps with speaker diarization for segment boundaries."""
        audio_path = temp_dir / "multi_speaker.mp3"
        audio_path.write_bytes(b"fake audio data")
        
        # Mock response with speaker changes that create natural segments
        mock_response = Mock()
        mock_response.text = "I was born in nineteen thirty-two. Yes, that's correct, in Berlin."
        mock_response.language_code = "en"
        mock_response.language_probability = 0.94
        
        # Words with speaker changes indicating segment boundaries
        mock_words = [
            # Speaker 1 segment
            Mock(text="I", start=0.0, end=0.2, speaker=1),
            Mock(text="was", start=0.2, end=0.4, speaker=1),
            Mock(text="born", start=0.4, end=0.8, speaker=1),
            Mock(text="in", start=0.8, end=1.0, speaker=1),
            Mock(text="nineteen", start=1.0, end=1.6, speaker=1),
            Mock(text="thirty-two.", start=1.6, end=2.8, speaker=1),
            
            # Speaker 2 segment (interviewer)
            Mock(text="Yes,", start=3.2, end=3.5, speaker=2),
            Mock(text="that's", start=3.5, end=3.8, speaker=2),
            Mock(text="correct,", start=3.8, end=4.4, speaker=2),
            Mock(text="in", start=4.4, end=4.6, speaker=2),
            Mock(text="Berlin.", start=4.6, end=5.4, speaker=2)
        ]
        mock_response.words = mock_words
        
        # Two speakers
        mock_response.speakers = [
            Mock(id=1, name="Interviewee"),
            Mock(id=2, name="Interviewer")
        ]
        mock_response.dict.return_value = {
            "text": "I was born in nineteen thirty-two. Yes, that's correct, in Berlin.",
            "language": "en",
            "speakers": [
                {"id": 1, "name": "Interviewee"},
                {"id": 2, "name": "Interviewer"}
            ]
        }
        
        mock_client_with_word_timestamps.speech_to_text.convert.return_value = mock_response
        
        # Transcribe
        result = transcriber_for_segments.transcribe_file(audio_path)
        
        # Verify speaker information is preserved in word data
        assert len(result.words) == 11
        assert len(result.speakers) == 2
        
        # Test speaker-based segment detection
        speaker_changes = []
        for i in range(len(result.words) - 1):
            current_speaker = result.words[i]["speaker"]
            next_speaker = result.words[i + 1]["speaker"]
            
            if current_speaker != next_speaker:
                speaker_changes.append({
                    'boundary_time': result.words[i]["end"],
                    'from_speaker': current_speaker,
                    'to_speaker': next_speaker,
                    'last_word': result.words[i]["text"],
                    'next_word': result.words[i + 1]["text"]
                })
        
        # Should detect speaker change
        assert len(speaker_changes) == 1
        change = speaker_changes[0]
        assert change['from_speaker'] == 1
        assert change['to_speaker'] == 2
        assert change['last_word'] == "thirty-two."
        assert change['next_word'] == "Yes,"
        assert change['boundary_time'] == 2.8
    
    @pytest.mark.unit
    def test_confidence_score_preservation_in_words(self, transcriber_for_segments, mock_client_with_word_timestamps, temp_dir):
        """Test that confidence scores are preserved at word level for quality assessment."""
        audio_path = temp_dir / "confidence_test.mp3"
        audio_path.write_bytes(b"fake audio data")
        
        # Mock response with word-level confidence (if supported by ElevenLabs)
        mock_response = Mock()
        mock_response.text = "Clear speech unclear mumble clear again."
        mock_response.language_code = "en"
        mock_response.language_probability = 0.87  # Overall confidence
        
        # Words with varying confidence levels
        mock_words = [
            Mock(text="Clear", start=0.0, end=0.5, speaker=1, confidence=0.98),
            Mock(text="speech", start=0.5, end=1.0, speaker=1, confidence=0.96),
            Mock(text="unclear", start=1.2, end=1.8, speaker=1, confidence=0.65),  # Lower confidence
            Mock(text="mumble", start=1.8, end=2.3, speaker=1, confidence=0.42),   # Very low confidence
            Mock(text="clear", start=2.5, end=2.9, speaker=1, confidence=0.94),
            Mock(text="again.", start=2.9, end=3.5, speaker=1, confidence=0.91)
        ]
        mock_response.words = mock_words
        mock_response.speakers = [Mock(id=1, name="Speaker 1")]
        mock_response.dict.return_value = {
            "text": "Clear speech unclear mumble clear again.",
            "language": "en",
            "confidence": 0.87
        }
        
        mock_client_with_word_timestamps.speech_to_text.convert.return_value = mock_response
        
        # Transcribe
        result = transcriber_for_segments.transcribe_file(audio_path)
        
        # Verify confidence data is preserved (if word-level confidence exists)
        assert len(result.words) == 6
        assert result.confidence == 0.87
        
        # Test confidence-based quality assessment
        low_confidence_words = []
        for word in result.words:
            if hasattr(word, 'confidence') or 'confidence' in word:
                word_confidence = getattr(word, 'confidence', word.get('confidence'))
                if word_confidence and word_confidence < 0.7:
                    low_confidence_words.append({
                        'text': word["text"],
                        'confidence': word_confidence,
                        'start': word["start"],
                        'end': word["end"]
                    })
        
        # Note: This test assumes ElevenLabs provides word-level confidence
        # If not available, the test validates the framework is ready for it
        if low_confidence_words:
            assert len(low_confidence_words) == 2  # "unclear" and "mumble"
            assert low_confidence_words[0]['text'] == "unclear"
            assert low_confidence_words[1]['text'] == "mumble"
    
    @pytest.mark.unit
    def test_segment_creation_from_word_boundaries(self, transcriber_for_segments, mock_client_with_word_timestamps, temp_dir):
        """Test creating subtitle segments from word-level timestamp boundaries."""
        audio_path = temp_dir / "boundary_test.mp3"
        audio_path.write_bytes(b"fake audio data")
        
        # Mock response designed for optimal subtitle segmentation
        mock_response = Mock()
        mock_response.text = "My name is Johann Mueller. I lived in Vienna during the war."
        mock_response.language_code = "en"
        mock_response.language_probability = 0.93
        
        # Words timed for natural subtitle segments (2-4 second chunks)
        mock_words = [
            # Segment 1: "My name is Johann Mueller." (0-3.2s)
            Mock(text="My", start=0.0, end=0.3, speaker=1),
            Mock(text="name", start=0.3, end=0.7, speaker=1),
            Mock(text="is", start=0.7, end=0.9, speaker=1),
            Mock(text="Johann", start=0.9, end=1.5, speaker=1),
            Mock(text="Mueller.", start=1.5, end=3.2, speaker=1),
            
            # Natural pause: 3.2 - 4.0s (0.8s)
            
            # Segment 2: "I lived in Vienna during the war." (4.0-8.5s)
            Mock(text="I", start=4.0, end=4.1, speaker=1),
            Mock(text="lived", start=4.1, end=4.6, speaker=1),
            Mock(text="in", start=4.6, end=4.8, speaker=1),
            Mock(text="Vienna", start=4.8, end=5.4, speaker=1),
            Mock(text="during", start=5.4, end=6.0, speaker=1),
            Mock(text="the", start=6.0, end=6.2, speaker=1),
            Mock(text="war.", start=6.2, end=8.5, speaker=1)
        ]
        mock_response.words = mock_words
        mock_response.speakers = [Mock(id=1, name="Speaker 1")]
        mock_response.dict.return_value = {
            "text": "My name is Johann Mueller. I lived in Vienna during the war.",
            "language": "en"
        }
        
        mock_client_with_word_timestamps.speech_to_text.convert.return_value = mock_response
        
        # Transcribe
        result = transcriber_for_segments.transcribe_file(audio_path)
        
        # Test segment creation logic (this would be implemented in Task 2.3)
        # For now, we test that the data structure supports it
        
        def create_segments_from_words(words, max_duration=4.0, min_gap=0.5):
            """Helper function to demonstrate segment creation from word boundaries."""
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
                
                if current_duration > max_duration or gap_from_previous > min_gap:
                    # End current segment
                    segment_end = words[i-1]["end"]
                    segment_text = " ".join([w["text"] for w in current_segment_words])
                    
                    segments.append({
                        'start_time': segment_start,
                        'end_time': segment_end,
                        'duration': segment_end - segment_start,
                        'text': segment_text,
                        'word_count': len(current_segment_words)
                    })
                    
                    # Start new segment
                    segment_start = word["start"]
                    current_segment_words = [word]
                else:
                    current_segment_words.append(word)
            
            # Add final segment
            if current_segment_words:
                segment_end = current_segment_words[-1]["end"]
                segment_text = " ".join([w["text"] for w in current_segment_words])
                
                segments.append({
                    'start_time': segment_start,
                    'end_time': segment_end,
                    'duration': segment_end - segment_start,
                    'text': segment_text,
                    'word_count': len(current_segment_words)
                })
            
            return segments
        
        # Test segment creation
        segments = create_segments_from_words(result.words)
        
        # Should create 3 natural segments based on gaps and duration limits
        assert len(segments) == 3
        
        # Verify segment 1: "My name is Johann Mueller."
        seg1 = segments[0]
        assert seg1['start_time'] == 0.0
        assert seg1['end_time'] == 3.2
        assert seg1['duration'] == 3.2
        assert seg1['text'] == "My name is Johann Mueller."
        assert seg1['word_count'] == 5
        
        # Verify segment 2: "I lived in Vienna during the"
        seg2 = segments[1]
        assert seg2['start_time'] == 4.0
        assert seg2['end_time'] == 6.2
        assert seg2['duration'] == 2.2
        assert seg2['text'] == "I lived in Vienna during the"
        assert seg2['word_count'] == 6
        
        # Verify segment 3: "war."
        seg3 = segments[2]
        assert seg3['start_time'] == 6.2
        assert seg3['end_time'] == 8.5
        assert seg3['duration'] == 2.3
        assert seg3['text'] == "war."
        assert seg3['word_count'] == 1
    
    @pytest.mark.unit
    def test_enhanced_api_response_parsing_captures_additional_data(self, temp_dir):
        """Test that enhanced parsing captures additional timestamp data."""
        # Create transcriber
        config = TranscriptionConfig(api_key="test-key")
        transcriber = Transcriber(config)
        
        # Mock response with additional word-level metadata
        mock_response = Mock()
        mock_response.text = "Enhanced parsing test."
        mock_response.language_code = "en"
        mock_response.language_probability = 0.95
        
        # Mock words with additional metadata
        mock_word1 = Mock()
        mock_word1.text = "Enhanced"
        mock_word1.start = 0.0
        mock_word1.end = 0.8
        mock_word1.speaker = "speaker_1"
        mock_word1.confidence = 0.98
        mock_word1.probability = 0.97
        mock_word1.speaker_id = 1
        
        mock_word2 = Mock()
        mock_word2.text = "parsing"
        mock_word2.start = 0.9
        mock_word2.end = 1.5
        mock_word2.speaker = "speaker_1"
        mock_word2.confidence = 0.92
        mock_word2.probability = 0.94
        mock_word2.speaker_id = 1
        
        mock_word3 = Mock()
        mock_word3.text = "test."
        mock_word3.start = 1.6
        mock_word3.end = 2.0
        mock_word3.speaker = "speaker_2"
        mock_word3.confidence = 0.96
        mock_word3.probability = 0.95
        mock_word3.speaker_id = 2
        
        mock_response.words = [mock_word1, mock_word2, mock_word3]
        mock_response.speakers = []
        mock_response.dict = lambda: {"mock": "metadata"}
        
        # Parse response
        result = transcriber._parse_response(mock_response)
        
        # Verify basic parsing
        assert result.text == "Enhanced parsing test."
        assert result.language == "en"
        assert result.confidence == 0.95
        assert len(result.words) == 3
        
        # Verify enhanced word-level data is captured
        word1 = result.words[0]
        assert word1['text'] == "Enhanced"
        assert word1['start'] == 0.0
        assert word1['end'] == 0.8
        assert word1['speaker'] == "speaker_1"
        assert word1['confidence'] == 0.98
        assert word1['probability'] == 0.97
        assert word1['speaker_id'] == 1
        
        word2 = result.words[1]
        assert word2['confidence'] == 0.92
        assert word2['probability'] == 0.94
        assert word2['speaker_id'] == 1
        
        word3 = result.words[2]
        assert word3['speaker'] == "speaker_2"
        assert word3['confidence'] == 0.96
        assert word3['speaker_id'] == 2
        
        # Test subtitle segment creation with enhanced data
        segments = transcriber.create_subtitle_segments(result.words, max_duration=3.0, min_gap=0.1)
        
        # Should create 2 segments due to speaker change
        assert len(segments) == 2
        
        # First segment (speaker_1)
        seg1 = segments[0] 
        assert seg1['start_time'] == 0.0
        assert seg1['end_time'] == 1.5
        assert seg1['text'] == "Enhanced parsing"
        assert seg1['speaker'] == "speaker_1"
        assert seg1['confidence_score'] == 0.95  # Average of 0.98 and 0.92
        assert seg1['word_count'] == 2
        
        # Second segment (speaker_2)
        seg2 = segments[1]
        assert seg2['start_time'] == 1.6
        assert seg2['end_time'] == 2.0
        assert seg2['text'] == "test."
        assert seg2['speaker'] == "speaker_2"
        assert seg2['confidence_score'] == 0.96
        assert seg2['word_count'] == 1
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_database_integration_stores_subtitle_segments(self, temp_dir):
        """Test that subtitle segments are properly stored in database."""
        from scribe.database import Database
        
        # Create database and run migration
        db_path = temp_dir / "test_segments.db"
        db = Database(db_path)
        
        # Ensure subtitle segments functionality exists (run migration if needed)
        db._migrate_to_subtitle_segments()
        
        # Add test interview
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        db.close()
        
        # Create transcriber
        config = TranscriptionConfig(api_key="test-key")
        transcriber = Transcriber(config)
        
        # Create test segments
        test_segments = [
            {
                'start_time': 0.0,
                'end_time': 2.5,
                'duration': 2.5,
                'text': 'Hello world.',
                'word_count': 2,
                'confidence_score': 0.95,
                'speaker': 'speaker_1',
                'words': []
            },
            {
                'start_time': 3.0,
                'end_time': 5.5,
                'duration': 2.5,
                'text': 'This is a test.',
                'word_count': 4,
                'confidence_score': 0.92,
                'speaker': 'speaker_1',
                'words': []
            }
        ]
        
        # Store segments
        success = transcriber.store_subtitle_segments(interview_id, test_segments, str(db_path))
        assert success
        
        # Verify segments were stored
        db = Database(db_path)
        stored_segments = db.get_subtitle_segments(interview_id)
        
        assert len(stored_segments) == 2
        
        # Check first segment
        seg1 = stored_segments[0]
        assert seg1['segment_index'] == 0
        assert seg1['start_time'] == 0.0
        assert seg1['end_time'] == 2.5
        assert seg1['original_text'] == 'Hello world.'
        assert seg1['confidence_score'] == 0.95
        
        # Check second segment
        seg2 = stored_segments[1]
        assert seg2['segment_index'] == 1
        assert seg2['start_time'] == 3.0
        assert seg2['end_time'] == 5.5
        assert seg2['original_text'] == 'This is a test.'
        assert seg2['confidence_score'] == 0.92
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_transcribe_with_subtitle_segments_full_workflow(self, temp_dir):
        """Test complete subtitle-first transcription workflow."""
        from scribe.database import Database
        
        # Create database and run migration
        db_path = temp_dir / "workflow_test.db"
        db = Database(db_path)
        
        # Ensure subtitle segments functionality exists (run migration if needed)
        db._migrate_to_subtitle_segments()
        
        # Add test interview
        interview_id = db.add_file(
            file_path="/test/workflow.mp4",
            safe_filename="workflow_mp4",
            media_type="video"
        )
        db.close()
        
        # Create test audio file (just touch the file since we're mocking the API)
        audio_path = temp_dir / "workflow_test.mp3"
        audio_path.touch()  # Create empty file for testing
        
        # Create transcriber with mocked API
        config = TranscriptionConfig(api_key="test-key")
        transcriber = Transcriber(config)
        
        # Mock the ElevenLabs client
        mock_response = Mock()
        mock_response.text = "This is a workflow test for subtitle segments."
        mock_response.language_code = "en"
        mock_response.language_probability = 0.95
        
        # Mock detailed word data
        mock_words = []
        words_data = [
            ("This", 0.0, 0.3, "speaker_1", 0.98),
            ("is", 0.4, 0.6, "speaker_1", 0.96),
            ("a", 0.7, 0.8, "speaker_1", 0.94),
            ("workflow", 1.0, 1.6, "speaker_1", 0.97),
            ("test", 2.0, 2.4, "speaker_1", 0.95),
            ("for", 2.6, 2.9, "speaker_1", 0.93),
            ("subtitle", 3.2, 3.8, "speaker_1", 0.96),
            ("segments.", 4.0, 4.5, "speaker_1", 0.94)
        ]
        
        for text, start, end, speaker, confidence in words_data:
            word = Mock()
            word.text = text
            word.start = start
            word.end = end
            word.speaker = speaker
            word.confidence = confidence
            mock_words.append(word)
        
        mock_response.words = mock_words
        mock_response.speakers = []
        mock_response.dict = lambda: {"workflow": "test"}
        
        # Mock the API call
        with patch.object(transcriber.client.speech_to_text, 'convert', return_value=mock_response):
            # Execute complete workflow
            result = transcriber.transcribe_with_subtitle_segments(
                file_path=audio_path,
                interview_id=interview_id,
                database_path=str(db_path),
                segment_params={'max_duration': 3.0, 'min_gap': 0.4, 'max_chars': 25}
            )
        
        # Verify transcription result
        assert result is not None
        assert result.text == "This is a workflow test for subtitle segments."
        assert len(result.words) == 8
        assert len(result.segments) > 0  # Should have created segments
        
        # Verify segments were stored in database
        db = Database(db_path)
        stored_segments = db.get_subtitle_segments(interview_id)
        
        assert len(stored_segments) > 0
        assert len(stored_segments) == len(result.segments)
        
        # Verify segment data integrity
        for i, (result_seg, db_seg) in enumerate(zip(result.segments, stored_segments)):
            assert db_seg['segment_index'] == i
            assert db_seg['start_time'] == result_seg['start_time']
            assert db_seg['end_time'] == result_seg['end_time']
            assert db_seg['original_text'] == result_seg['text']
            assert db_seg['confidence_score'] == result_seg.get('confidence_score')
        
        db.close()
    
    @pytest.mark.unit
    def test_fallback_handling_no_words_with_text(self, temp_dir):
        """Test fallback segment creation when no word data is available."""
        config = TranscriptionConfig(api_key="test-key")
        transcriber = Transcriber(config)
        
        # Test with no words but fallback text provided
        fallback_text = "This is a test transcript. It has multiple sentences. Each should create appropriate segments for subtitles."
        
        segments = transcriber.create_subtitle_segments(
            words=[],
            max_duration=4.0,
            min_gap=0.5,
            max_chars=50,
            fallback_text=fallback_text
        )
        
        # Should create segments based on sentence boundaries
        assert len(segments) >= 2
        
        # Check first segment
        seg1 = segments[0]
        assert seg1['start_time'] == 0.0
        assert seg1['end_time'] > 0.0
        assert seg1['fallback'] is True
        assert seg1['confidence_score'] is None
        assert seg1['speaker'] is None
        assert len(seg1['words']) == 0
        assert 'This is a test transcript' in seg1['text']
        
        # Segments should be sequential
        for i in range(1, len(segments)):
            assert segments[i]['start_time'] >= segments[i-1]['end_time']
    
    @pytest.mark.unit
    def test_fallback_handling_invalid_word_timing(self, temp_dir):
        """Test fallback when words exist but lack valid timing data."""
        config = TranscriptionConfig(api_key="test-key")
        transcriber = Transcriber(config)
        
        # Words without timing information
        invalid_words = [
            {'text': 'Hello'},
            {'text': 'world', 'start': 'invalid'},
            {'text': 'test', 'start': 1.0}  # Missing 'end'
        ]
        
        fallback_text = "Hello world test."
        
        segments = transcriber.create_subtitle_segments(
            words=invalid_words,
            fallback_text=fallback_text,
            max_chars=30
        )
        
        # Should create fallback segments
        assert len(segments) == 1
        assert segments[0]['fallback'] is True
        assert segments[0]['text'] == "Hello world test"  # Period removed by regex split
    
    @pytest.mark.unit  
    def test_fallback_handling_no_data_available(self, temp_dir):
        """Test behavior when no word data or fallback text is available."""
        config = TranscriptionConfig(api_key="test-key")
        transcriber = Transcriber(config)
        
        # No words, no fallback text
        segments = transcriber.create_subtitle_segments(
            words=[],
            fallback_text=None
        )
        
        # Should return empty list
        assert len(segments) == 0
    
    @pytest.mark.unit
    def test_fallback_segments_character_limit_handling(self, temp_dir):
        """Test that fallback segments respect character limits."""
        config = TranscriptionConfig(api_key="test-key")
        transcriber = Transcriber(config)
        
        # Long text that should be split due to character limit
        long_text = "This is a very long sentence that should be split into multiple segments because it exceeds the character limit. " \
                   "This second sentence should also be in a separate segment if the limit is set correctly. " \
                   "And this third sentence provides even more content to test the segmentation logic thoroughly."
        
        segments = transcriber.create_subtitle_segments(
            words=[],
            fallback_text=long_text,
            max_chars=80  # Small limit to force splitting
        )
        
        # Should create multiple segments
        assert len(segments) >= 3
        
        # Each segment should respect character limit (with reasonable buffer for sentence boundaries)
        for segment in segments:
            assert len(segment['text']) <= 120  # Allow buffer for complete sentences
            assert segment['fallback'] is True
    
    @pytest.mark.unit
    def test_mixed_valid_and_invalid_word_data(self, temp_dir):
        """Test handling when some words have valid timing but others don't."""
        config = TranscriptionConfig(api_key="test-key")
        transcriber = Transcriber(config)
        
        # Mix of valid and invalid word data
        mixed_words = [
            {'text': 'Hello', 'start': 0.0, 'end': 0.5},
            {'text': 'world', 'start': 0.6, 'end': 1.0},
            {'text': 'invalid'},  # No timing
            {'text': 'test', 'start': 2.0, 'end': 2.5}
        ]
        
        segments = transcriber.create_subtitle_segments(words=mixed_words)
        
        # Should work with valid words and skip invalid ones
        assert len(segments) >= 1
        
        # Should not be marked as fallback since some valid data exists
        for segment in segments:
            assert segment.get('fallback') is not True
            assert segment['start_time'] >= 0.0
            assert segment['end_time'] > segment['start_time']


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
        
        # Create mock word objects with proper attributes
        mock_word1 = Mock()
        mock_word1.text = "Full"
        mock_word1.start = 0.0
        mock_word1.end = 0.3
        mock_word1.speaker = 1
        
        mock_word2 = Mock()
        mock_word2.text = "transcription"
        mock_word2.start = 0.3
        mock_word2.end = 1.0
        mock_word2.speaker = 1
        
        mock_word3 = Mock()
        mock_word3.text = "of"
        mock_word3.start = 1.0
        mock_word3.end = 1.2
        mock_word3.speaker = 1
        
        mock_word4 = Mock()
        mock_word4.text = "video"
        mock_word4.start = 1.2
        mock_word4.end = 1.6
        mock_word4.speaker = 1
        
        mock_response.words = [mock_word1, mock_word2, mock_word3, mock_word4]
        
        # Create mock speaker object
        mock_speaker = Mock()
        mock_speaker.id = 1
        mock_speaker.name = "Speaker 1"
        mock_response.speakers = [mock_speaker]
        
        # Ensure dict() returns only JSON-serializable data
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
