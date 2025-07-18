#!/usr/bin/env python3
"""
Comprehensive test suite for the transcribe module.
Tests cover all functionality including audio extraction, segmentation, and transcription.
"""

import unittest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock, call
import subprocess

from scribe.transcribe import (
    TranscriptionConfig,
    TranscriptionResult,
    AudioExtractor,
    AudioSegmenter,
    Transcriber,
    transcribe,
    transcribe_file
)


class TestTranscriptionConfig(unittest.TestCase):
    """Test TranscriptionConfig dataclass."""
    
    def test_config_default_values(self):
        """Test default configuration values."""
        config = TranscriptionConfig(api_key="test_key")
        
        self.assertEqual(config.api_key, "test_key")
        self.assertEqual(config.model, "scribe_v1")
        self.assertTrue(config.speaker_detection)
        self.assertEqual(config.speaker_count, 32)
        self.assertEqual(config.max_file_size_mb, 25)
        self.assertEqual(config.max_segment_duration, 600)
        self.assertEqual(config.api_timeout, 300)
        self.assertEqual(config.max_retries, 8)
        self.assertEqual(config.segment_pause, 1.0)
        self.assertTrue(config.auto_detect_language)
        self.assertIsNone(config.force_language)
    
    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = TranscriptionConfig(
            api_key="custom_key",
            model="custom_model",
            speaker_detection=False,
            speaker_count=16,
            max_file_size_mb=50,
            max_segment_duration=300,
            api_timeout=180,
            max_retries=5,
            segment_pause=2.0,
            auto_detect_language=False,
            force_language="en"
        )
        
        self.assertEqual(config.api_key, "custom_key")
        self.assertEqual(config.model, "custom_model")
        self.assertFalse(config.speaker_detection)
        self.assertEqual(config.speaker_count, 16)
        self.assertEqual(config.max_file_size_mb, 50)
        self.assertEqual(config.max_segment_duration, 300)
        self.assertEqual(config.api_timeout, 180)
        self.assertEqual(config.max_retries, 5)
        self.assertEqual(config.segment_pause, 2.0)
        self.assertFalse(config.auto_detect_language)
        self.assertEqual(config.force_language, "en")


class TestTranscriptionResult(unittest.TestCase):
    """Test TranscriptionResult dataclass."""
    
    def test_result_default_values(self):
        """Test default result values."""
        result = TranscriptionResult(text="Test transcription")
        
        self.assertEqual(result.text, "Test transcription")
        self.assertIsNone(result.language)
        self.assertIsNone(result.confidence)
        self.assertEqual(result.words, [])
        self.assertEqual(result.segments, [])
        self.assertEqual(result.speakers, [])
        self.assertIsNone(result.duration)
        self.assertEqual(result.metadata, {})
    
    def test_result_with_data(self):
        """Test result with complete data."""
        words = [{"word": "Hello", "start": 0.0, "end": 0.5}]
        segments = [{"text": "Hello world", "start": 0.0, "end": 1.0}]
        speakers = [{"speaker": "Speaker 1", "segments": [0]}]
        metadata = {"file_size": 1024, "duration": 120.0}
        
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            confidence=0.95,
            words=words,
            segments=segments,
            speakers=speakers,
            duration=120.0,
            metadata=metadata
        )
        
        self.assertEqual(result.text, "Hello world")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.words, words)
        self.assertEqual(result.segments, segments)
        self.assertEqual(result.speakers, speakers)
        self.assertEqual(result.duration, 120.0)
        self.assertEqual(result.metadata, metadata)


class TestAudioExtractor(unittest.TestCase):
    """Test AudioExtractor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('subprocess.run')
    def test_extract_audio_success(self, mock_run):
        """Test successful audio extraction."""
        # Mock successful subprocess run
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        video_path = self.temp_path / "test_video.mp4"
        video_path.write_bytes(b"fake video content")
        
        # Extract audio
        audio_path = AudioExtractor.extract_audio(video_path)
        
        # Verify subprocess was called with correct arguments
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], 'ffmpeg')
        self.assertEqual(call_args[1], '-i')
        self.assertEqual(call_args[2], str(video_path))
        self.assertIn('-vn', call_args)
        self.assertIn('-acodec', call_args)
        self.assertIn('libmp3lame', call_args)
        self.assertIn('-ab', call_args)
        self.assertIn('192k', call_args)
        
        # Verify audio path exists and has correct extension
        self.assertTrue(audio_path.suffix == '.mp3')
    
    @patch('subprocess.run')
    def test_extract_audio_custom_format(self, mock_run):
        """Test audio extraction with custom format."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        video_path = self.temp_path / "test_video.mp4"
        video_path.write_bytes(b"fake video content")
        
        # Extract audio with custom format
        audio_path = AudioExtractor.extract_audio(video_path, output_format="wav", bitrate="256k")
        
        # Verify subprocess was called with correct arguments
        call_args = mock_run.call_args[0][0]
        self.assertIn('pcm_s16le', call_args)
        self.assertIn('-ab', call_args)
        self.assertIn('256k', call_args)
        
        # Verify audio path has correct extension
        self.assertTrue(audio_path.suffix == '.wav')
    
    @patch('subprocess.run')
    def test_extract_audio_ffmpeg_error(self, mock_run):
        """Test audio extraction with ffmpeg error."""
        # Mock ffmpeg error
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffmpeg', stderr="ffmpeg error")
        
        video_path = self.temp_path / "test_video.mp4"
        video_path.write_bytes(b"fake video content")
        
        # Should raise exception
        with self.assertRaises(subprocess.CalledProcessError):
            AudioExtractor.extract_audio(video_path)
    
    @patch('subprocess.run')
    def test_get_duration_success(self, mock_run):
        """Test successful duration detection."""
        # Mock ffprobe output
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"format": {"duration": "120.5"}}',
            stderr=""
        )
        
        media_path = self.temp_path / "test_media.mp4"
        media_path.write_bytes(b"fake media content")
        
        duration = AudioExtractor.get_duration(media_path)
        
        # Verify duration is correct
        self.assertEqual(duration, 120.5)
        
        # Verify ffprobe was called with correct arguments
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], 'ffprobe')
        self.assertIn('-v', call_args)
        self.assertIn('quiet', call_args)
        self.assertIn('-print_format', call_args)
        self.assertIn('json', call_args)
        self.assertIn('-show_format', call_args)
        self.assertIn(str(media_path), call_args)
    
    @patch('subprocess.run')
    def test_get_duration_ffprobe_error(self, mock_run):
        """Test duration detection with ffprobe error."""
        # Mock ffprobe error
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffprobe', stderr="ffprobe error")
        
        media_path = self.temp_path / "test_media.mp4"
        media_path.write_bytes(b"fake media content")
        
        # Should raise exception
        with self.assertRaises(subprocess.CalledProcessError):
            AudioExtractor.get_duration(media_path)
    
    @patch('subprocess.run')
    def test_get_duration_invalid_json(self, mock_run):
        """Test duration detection with invalid JSON."""
        # Mock ffprobe with invalid JSON
        mock_run.return_value = Mock(
            returncode=0,
            stdout='invalid json',
            stderr=""
        )
        
        media_path = self.temp_path / "test_media.mp4"
        media_path.write_bytes(b"fake media content")
        
        # Should raise exception
        with self.assertRaises(Exception):
            AudioExtractor.get_duration(media_path)


class TestAudioSegmenter(unittest.TestCase):
    """Test AudioSegmenter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('subprocess.run')
    @patch('scribe.transcribe.AudioExtractor.get_duration')
    def test_split_audio_no_split_needed(self, mock_get_duration, mock_run):
        """Test audio splitting when no split is needed."""
        # Mock duration less than max segment duration
        mock_get_duration.return_value = 300.0  # 5 minutes
        
        audio_path = self.temp_path / "test_audio.mp3"
        audio_path.write_bytes(b"fake audio content")
        
        segments = AudioSegmenter.split_audio(audio_path, max_size_mb=25, max_segment_duration=600)
        
        # Should return single segment
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], audio_path)
        self.assertEqual(segments[0][1], 0.0)
        
        # ffmpeg should not be called for splitting
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    @patch('scribe.transcribe.AudioExtractor.get_duration')
    def test_split_audio_duration_split(self, mock_get_duration, mock_run):
        """Test audio splitting by duration."""
        # Mock duration longer than max segment duration
        mock_get_duration.return_value = 1200.0  # 20 minutes
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        audio_path = self.temp_path / "test_audio.mp3"
        audio_path.write_bytes(b"fake audio content")
        
        segments = AudioSegmenter.split_audio(audio_path, max_size_mb=25, max_segment_duration=600)
        
        # Should return multiple segments
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0][1], 0.0)
        self.assertEqual(segments[1][1], 600.0)
        
        # ffmpeg should be called for splitting
        self.assertEqual(mock_run.call_count, 2)
    
    @patch('subprocess.run')
    @patch('os.path.getsize')
    @patch('scribe.transcribe.AudioExtractor.get_duration')
    def test_split_audio_file_size_split(self, mock_get_duration, mock_get_size, mock_run):
        """Test audio splitting by file size."""
        # Mock file size larger than max size
        mock_get_duration.return_value = 300.0  # 5 minutes
        mock_get_size.return_value = 30 * 1024 * 1024  # 30MB
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        audio_path = self.temp_path / "test_audio.mp3"
        audio_path.write_bytes(b"fake audio content")
        
        segments = AudioSegmenter.split_audio(audio_path, max_size_mb=25, max_segment_duration=600)
        
        # Should return multiple segments
        self.assertGreater(len(segments), 1)
        
        # ffmpeg should be called for splitting
        self.assertGreater(mock_run.call_count, 0)
    
    @patch('subprocess.run')
    @patch('scribe.transcribe.AudioExtractor.get_duration')
    def test_split_audio_ffmpeg_error(self, mock_get_duration, mock_run):
        """Test audio splitting with ffmpeg error."""
        # Mock duration longer than max segment duration
        mock_get_duration.return_value = 1200.0  # 20 minutes
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffmpeg', stderr="ffmpeg error")
        
        audio_path = self.temp_path / "test_audio.mp3"
        audio_path.write_bytes(b"fake audio content")
        
        # Should raise exception
        with self.assertRaises(subprocess.CalledProcessError):
            AudioSegmenter.split_audio(audio_path, max_size_mb=25, max_segment_duration=600)


class TestTranscriber(unittest.TestCase):
    """Test Transcriber class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = TranscriptionConfig(api_key="test_key")
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('scribe.transcribe.ElevenLabs')
    def test_transcriber_initialization(self, mock_elevenlabs):
        """Test Transcriber initialization."""
        mock_client = Mock()
        mock_elevenlabs.return_value = mock_client
        
        transcriber = Transcriber(self.config)
        
        self.assertEqual(transcriber.config, self.config)
        self.assertEqual(transcriber.client, mock_client)
        mock_elevenlabs.assert_called_once_with(api_key="test_key")
    
    @patch('scribe.transcribe.ElevenLabs')
    def test_transcriber_initialization_error(self, mock_elevenlabs):
        """Test Transcriber initialization with error."""
        mock_elevenlabs.side_effect = Exception("API key error")
        
        with self.assertRaises(Exception):
            Transcriber(self.config)
    
    @patch('scribe.transcribe.AudioExtractor.extract_audio')
    @patch('scribe.transcribe.AudioSegmenter.split_audio')
    def test_transcribe_file_video(self, mock_split, mock_extract):
        """Test transcribing video file."""
        # Mock audio extraction
        audio_path = self.temp_path / "extracted_audio.mp3"
        audio_path.write_bytes(b"fake audio content")
        mock_extract.return_value = audio_path
        
        # Mock audio segmentation
        mock_split.return_value = [(audio_path, 0.0)]
        
        # Mock transcription
        with patch.object(Transcriber, '_transcribe_single') as mock_transcribe:
            mock_result = TranscriptionResult(
                text="Test transcription",
                language="en",
                confidence=0.95,
                duration=120.0
            )
            mock_transcribe.return_value = mock_result
            
            transcriber = Transcriber(self.config)
            transcriber.client = Mock()
            
            video_path = self.temp_path / "test_video.mp4"
            video_path.write_bytes(b"fake video content")
            
            result = transcriber.transcribe_file(video_path)
            
            # Verify result
            self.assertEqual(result.text, "Test transcription")
            self.assertEqual(result.language, "en")
            self.assertEqual(result.confidence, 0.95)
            self.assertEqual(result.duration, 120.0)
            
            # Verify audio extraction was called
            mock_extract.assert_called_once_with(video_path)
            mock_split.assert_called_once()
            mock_transcribe.assert_called_once()
    
    @patch('scribe.transcribe.AudioSegmenter.split_audio')
    def test_transcribe_file_audio(self, mock_split):
        """Test transcribing audio file."""
        # Mock audio segmentation
        audio_path = self.temp_path / "test_audio.mp3"
        audio_path.write_bytes(b"fake audio content")
        mock_split.return_value = [(audio_path, 0.0)]
        
        # Mock transcription
        with patch.object(Transcriber, '_transcribe_single') as mock_transcribe:
            mock_result = TranscriptionResult(
                text="Test transcription",
                language="en",
                confidence=0.95,
                duration=120.0
            )
            mock_transcribe.return_value = mock_result
            
            transcriber = Transcriber(self.config)
            transcriber.client = Mock()
            
            result = transcriber.transcribe_file(audio_path)
            
            # Verify result
            self.assertEqual(result.text, "Test transcription")
            
            # Verify audio segmentation was called
            mock_split.assert_called_once()
            mock_transcribe.assert_called_once()
    
    @patch('scribe.transcribe.AudioSegmenter.split_audio')
    def test_transcribe_file_multiple_segments(self, mock_split):
        """Test transcribing file with multiple segments."""
        # Mock multiple audio segments
        audio_path1 = self.temp_path / "segment1.mp3"
        audio_path2 = self.temp_path / "segment2.mp3"
        audio_path1.write_bytes(b"fake audio content 1")
        audio_path2.write_bytes(b"fake audio content 2")
        
        mock_split.return_value = [(audio_path1, 0.0), (audio_path2, 300.0)]
        
        # Mock transcription
        with patch.object(Transcriber, '_transcribe_segments') as mock_transcribe:
            mock_result = TranscriptionResult(
                text="Segment 1 text. Segment 2 text.",
                language="en",
                confidence=0.95,
                duration=600.0
            )
            mock_transcribe.return_value = mock_result
            
            transcriber = Transcriber(self.config)
            transcriber.client = Mock()
            
            audio_path = self.temp_path / "test_audio.mp3"
            audio_path.write_bytes(b"fake audio content")
            
            result = transcriber.transcribe_file(audio_path)
            
            # Verify result
            self.assertEqual(result.text, "Segment 1 text. Segment 2 text.")
            
            # Verify segments transcription was called
            mock_transcribe.assert_called_once()
    
    def test_transcribe_single_success(self):
        """Test successful single file transcription."""
        # Mock ElevenLabs client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Test transcription"
        mock_response.language_code = "en"
        mock_response.language_probability = 0.95
        mock_response.words = []
        mock_response.segments = []
        mock_response.speakers = []
        mock_client.speech_to_text.convert.return_value = mock_response
        
        transcriber = Transcriber(self.config)
        transcriber.client = mock_client
        
        audio_path = self.temp_path / "test_audio.mp3"
        audio_path.write_bytes(b"fake audio content")
        
        result = transcriber._transcribe_single(audio_path)
        
        # Verify result
        self.assertEqual(result.text, "Test transcription")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.confidence, 0.95)
        
        # Verify API call
        mock_client.speech_to_text.convert.assert_called_once()
    
    def test_transcribe_single_api_error(self):
        """Test single file transcription with API error."""
        # Mock ElevenLabs client with error
        mock_client = Mock()
        mock_client.speech_to_text.transcribe.side_effect = Exception("API Error")
        
        transcriber = Transcriber(self.config)
        transcriber.client = mock_client
        
        audio_path = self.temp_path / "test_audio.mp3"
        audio_path.write_bytes(b"fake audio content")
        
        # Should raise exception
        with self.assertRaises(Exception):
            transcriber._transcribe_single(audio_path)
    
    def test_transcribe_segments_success(self):
        """Test successful segments transcription."""
        # Mock ElevenLabs client
        mock_client = Mock()
        
        # Mock responses for two segments
        mock_response1 = Mock()
        mock_response1.text = "Segment 1 text."
        mock_response1.language = "en"
        mock_response1.confidence = 0.95
        mock_response1.words = [{"word": "Segment", "start": 0.0, "end": 0.5}]
        mock_response1.segments = [{"text": "Segment 1 text.", "start": 0.0, "end": 5.0}]
        mock_response1.speakers = []
        
        mock_response2 = Mock()
        mock_response2.text = "Segment 2 text."
        mock_response2.language = "en"
        mock_response2.confidence = 0.90
        mock_response2.words = [{"word": "Segment", "start": 300.0, "end": 300.5}]
        mock_response2.segments = [{"text": "Segment 2 text.", "start": 300.0, "end": 305.0}]
        mock_response2.speakers = []
        
        mock_client.speech_to_text.transcribe.side_effect = [mock_response1, mock_response2]
        
        transcriber = Transcriber(self.config)
        transcriber.client = mock_client
        
        # Create test segments
        audio_path1 = self.temp_path / "segment1.mp3"
        audio_path2 = self.temp_path / "segment2.mp3"
        audio_path1.write_bytes(b"fake audio content 1")
        audio_path2.write_bytes(b"fake audio content 2")
        
        segments = [(audio_path1, 0.0), (audio_path2, 300.0)]
        
        result = transcriber._transcribe_segments(segments)
        
        # Verify result
        self.assertEqual(result.text, "Segment 1 text. Segment 2 text.")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.confidence, 0.925)  # Average of 0.95 and 0.90
        self.assertEqual(len(result.words), 2)
        self.assertEqual(len(result.segments), 2)
        
        # Verify API calls
        self.assertEqual(mock_client.speech_to_text.transcribe.call_count, 2)
    
    def test_parse_response_complete(self):
        """Test parsing complete response."""
        # Mock complete response
        mock_response = Mock()
        mock_response.text = "Test transcription"
        mock_response.language_code = "en"
        mock_response.language_probability = 0.95
        # Create mock word objects
        mock_word = Mock()
        mock_word.text = "Test"
        mock_word.start = 0.0
        mock_word.end = 0.5
        mock_word.speaker = None
        mock_response.words = [mock_word]
        
        # Create mock speaker objects  
        mock_speaker = Mock()
        mock_speaker.id = "speaker_1"
        mock_speaker.name = "Speaker 1"
        mock_response.speakers = [mock_speaker]
        
        transcriber = Transcriber(self.config)
        result = transcriber._parse_response(mock_response)
        
        # Verify result
        self.assertEqual(result.text, "Test transcription")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(len(result.words), 1)
        self.assertEqual(result.words[0]['text'], "Test")
        self.assertEqual(result.words[0]['start'], 0.0)
        self.assertEqual(result.words[0]['end'], 0.5)
        self.assertEqual(len(result.speakers), 1)
        self.assertEqual(result.speakers[0]['id'], "speaker_1")
        self.assertEqual(result.speakers[0]['name'], "Speaker 1")
    
    def test_parse_response_minimal(self):
        """Test parsing minimal response."""
        # Create minimal response object (not Mock to avoid hasattr issues)
        class MinimalResponse:
            def __init__(self):
                self.text = "Test transcription"
        
        mock_response = MinimalResponse()
        
        transcriber = Transcriber(self.config)
        result = transcriber._parse_response(mock_response)
        
        # Verify result
        self.assertEqual(result.text, "Test transcription")
        self.assertIsNone(result.language)
        self.assertIsNone(result.confidence)
        self.assertEqual(result.words, [])
        self.assertEqual(result.segments, [])
        self.assertEqual(result.speakers, [])
    
    def test_save_results_text_only(self):
        """Test saving results with text only."""
        result = TranscriptionResult(
            text="Test transcription",
            language="en",
            confidence=0.95,
            duration=120.0
        )
        
        transcriber = Transcriber(self.config)
        output_path = self.temp_path / "output.txt"
        
        transcriber.save_results(result, output_path, save_json=False, save_srt=False)
        
        # Verify text file was created
        self.assertTrue(output_path.exists())
        content = output_path.read_text()
        self.assertEqual(content, "Test transcription")
    
    def test_save_results_with_json(self):
        """Test saving results with JSON metadata."""
        result = TranscriptionResult(
            text="Test transcription",
            language="en",
            confidence=0.95,
            duration=120.0,
            metadata={"test": "value"}
        )
        
        transcriber = Transcriber(self.config)
        output_path = self.temp_path / "output.txt"
        
        transcriber.save_results(result, output_path, save_json=True, save_srt=False)
        
        # Verify JSON file was created
        json_path = output_path.with_suffix('.json')
        self.assertTrue(json_path.exists())
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(data['text'], "Test transcription")
        self.assertEqual(data['language'], "en")
        self.assertEqual(data['confidence'], 0.95)
        self.assertEqual(data['duration'], 120.0)
        self.assertEqual(data['metadata']['test'], "value")
    
    def test_save_results_with_srt(self):
        """Test saving results with SRT subtitles."""
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.5, "end": 1.0}
        ]
        
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            words=words,
            duration=120.0
        )
        
        transcriber = Transcriber(self.config)
        output_path = self.temp_path / "output.txt"
        
        transcriber.save_results(result, output_path, save_json=False, save_srt=True)
        
        # Verify SRT file was created
        srt_path = output_path.with_suffix('.srt')
        self.assertTrue(srt_path.exists())
        
        content = srt_path.read_text()
        self.assertIn("Hello world", content)
        self.assertIn("00:00:00,000", content)
        self.assertIn("00:00:01,000", content)
    
    def test_format_srt_time(self):
        """Test SRT time formatting."""
        transcriber = Transcriber(self.config)
        
        # Test various time formats
        self.assertEqual(transcriber._format_srt_time(0.0), "00:00:00,000")
        self.assertEqual(transcriber._format_srt_time(1.5), "00:00:01,500")
        self.assertEqual(transcriber._format_srt_time(60.0), "00:01:00,000")
        self.assertEqual(transcriber._format_srt_time(3661.5), "01:01:01,500")


class TestModuleFunctions(unittest.TestCase):
    """Test module-level functions."""
    
    def test_transcribe_function(self):
        """Test transcribe function."""
        with patch('scribe.transcribe.Transcriber') as mock_transcriber_class:
            mock_transcriber = Mock()
            mock_result = TranscriptionResult(
                text="Test transcription",
                language="en",
                confidence=0.95,
                duration=120.0
            )
            mock_transcriber.transcribe_file.return_value = mock_result
            mock_transcriber_class.return_value = mock_transcriber
            
            result = transcribe(
                file_path="/test/file.mp4",
                api_key="test_key",
                output_dir="/test/output"
            )
            
            # Verify result
            self.assertEqual(result['text'], "Test transcription")
            self.assertEqual(result['language'], "en")
            self.assertEqual(result['confidence'], 0.95)
            self.assertEqual(result['duration'], 120.0)
            
            # Verify transcriber was called correctly
            mock_transcriber_class.assert_called_once()
            mock_transcriber.transcribe_file.assert_called_once()
    
    def test_transcribe_function_with_options(self):
        """Test transcribe function with options."""
        with patch('scribe.transcribe.Transcriber') as mock_transcriber_class:
            mock_transcriber = Mock()
            mock_result = TranscriptionResult(text="Test transcription")
            mock_transcriber.transcribe_file.return_value = mock_result
            mock_transcriber_class.return_value = mock_transcriber
            
            result = transcribe(
                file_path="/test/file.mp4",
                api_key="test_key",
                output_dir="/test/output",
                speaker_detection=False,
                force_language="en",
                max_retries=5
            )
            
            # Verify transcriber was initialized with correct config
            mock_transcriber_class.assert_called_once()
            config = mock_transcriber_class.call_args[0][0]
            self.assertEqual(config.api_key, "test_key")
            self.assertFalse(config.speaker_detection)
            self.assertEqual(config.force_language, "en")
            self.assertEqual(config.max_retries, 5)
    
    @patch('scribe.transcribe.transcribe')
    def test_transcribe_file_function(self, mock_transcribe):
        """Test transcribe_file function."""
        # Mock transcribe function
        mock_transcribe.return_value = {
            'text': 'Test transcription',
            'language': 'en',
            'confidence': 0.95,
            'duration': 120.0
        }
        
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test_key'}):
            result = transcribe_file("/test/file.mp4", "/test/output")
            
            # Verify result
            self.assertEqual(result['text'], 'Test transcription')
            
            # Verify transcribe was called
            mock_transcribe.assert_called_once_with(
                file_path="/test/file.mp4",
                api_key="test_key",
                output_dir="/test/output"
            )
    
    @patch('scribe.transcribe.transcribe')
    def test_transcribe_file_function_no_api_key(self, mock_transcribe):
        """Test transcribe_file function without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                transcribe_file("/test/file.mp4", "/test/output")
    
    @patch('scribe.transcribe.transcribe')
    def test_transcribe_file_function_error(self, mock_transcribe):
        """Test transcribe_file function with error."""
        mock_transcribe.side_effect = Exception("Transcription error")
        
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test_key'}):
            result = transcribe_file("/test/file.mp4", "/test/output")
            
            # Should return error result
            self.assertIn('error', result)
            self.assertEqual(result['success'], False)


if __name__ == "__main__":
    unittest.main()
