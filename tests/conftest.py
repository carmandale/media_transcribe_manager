"""
Pytest configuration and shared fixtures for Scribe test suite.

This module provides common test fixtures, utilities, and configuration
for all tests in the Scribe project.
"""
import os
import sys
import shutil
import tempfile
import asyncio
from pathlib import Path
from typing import Generator, Dict, Any
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

import pytest
import sqlite3

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scribe.database import DatabaseOperations


# Test data constants
SAMPLE_AUDIO_METADATA = {
    "file_name": "test_interview.mp4",
    "file_path": "/test/path/test_interview.mp4",
    "file_size": 1024 * 1024 * 50,  # 50MB
    "duration": 3600.0,  # 1 hour
    "format": "mp4",
    "codec": "aac",
    "sample_rate": 44100,
    "channels": 2,
    "bit_rate": 128000
}

SAMPLE_TRANSCRIPT = {
    "text": "This is a test transcript with historical content.",
    "segments": [
        {
            "start": 0.0,
            "end": 5.0,
            "text": "This is a test transcript",
            "words": []
        },
        {
            "start": 5.0,
            "end": 10.0,
            "text": "with historical content.",
            "words": []
        }
    ],
    "language": "en",
    "confidence": 0.95
}

SAMPLE_TRANSLATION = {
    "en": "This is a test transcript with historical content.",
    "de": "Dies ist ein Testtranskript mit historischem Inhalt.",
    "he": "זהו תמליל בדיקה עם תוכן היסטורי."
}

SAMPLE_EVALUATION = {
    "language": "en",
    "accuracy_score": 0.92,
    "completeness_score": 0.95,
    "speech_pattern_score": 0.88,
    "overall_score": 0.91,
    "evaluation_text": "High quality translation with good preservation of speech patterns.",
    "warnings": [],
    "suggestions": ["Consider reviewing technical terms for accuracy"]
}


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test isolation."""
    temp_path = Path(tempfile.mkdtemp(prefix="scribe_test_"))
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture(scope="function")
def test_db_path(temp_dir: Path) -> Path:
    """Provide a path for test database."""
    return temp_dir / "test_media_tracking.db"


@pytest.fixture(scope="function")
def db_operations(test_db_path: Path) -> Generator[DatabaseOperations, None, None]:
    """Create a DatabaseOperations instance with test database."""
    db = DatabaseOperations(str(test_db_path))
    yield db
    # Cleanup
    db.close()
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture(scope="function")
def populated_db(db_operations: DatabaseOperations) -> DatabaseOperations:
    """Create a database with sample data."""
    # Add sample file
    file_id = db_operations.add_file(
        file_path=SAMPLE_AUDIO_METADATA["file_path"],
        file_name=SAMPLE_AUDIO_METADATA["file_name"],
        file_size=SAMPLE_AUDIO_METADATA["file_size"],
        duration=SAMPLE_AUDIO_METADATA["duration"],
        format=SAMPLE_AUDIO_METADATA["format"],
        codec=SAMPLE_AUDIO_METADATA["codec"],
        sample_rate=SAMPLE_AUDIO_METADATA["sample_rate"],
        channels=SAMPLE_AUDIO_METADATA["channels"],
        bit_rate=SAMPLE_AUDIO_METADATA["bit_rate"]
    )
    
    # Add transcript
    db_operations.save_transcription(
        file_id=file_id,
        transcription_text=SAMPLE_TRANSCRIPT["text"],
        language_code=SAMPLE_TRANSCRIPT["language"],
        confidence_score=SAMPLE_TRANSCRIPT["confidence"],
        segments=SAMPLE_TRANSCRIPT["segments"],
        provider="elevenlabs",
        cost=0.50
    )
    
    # Add translations
    for lang, text in SAMPLE_TRANSLATION.items():
        if lang != "en":
            db_operations.save_translation(
                file_id=file_id,
                language_code=lang,
                translated_text=text,
                provider="deepl" if lang == "de" else "openai",
                model="deepl" if lang == "de" else "gpt-4-mini",
                cost=0.10
            )
    
    return db_operations


@pytest.fixture(scope="function")
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    test_env = {
        "ELEVENLABS_API_KEY": "test_elevenlabs_key",
        "DEEPL_API_KEY": "test_deepl_key",
        "OPENAI_API_KEY": "test_openai_key",
        "MS_TRANSLATOR_KEY": "test_ms_key",
        "ANTHROPIC_API_KEY": "test_anthropic_key"
    }
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)
    return test_env


@pytest.fixture(scope="function")
def mock_audio_file(temp_dir: Path) -> Path:
    """Create a mock audio file for testing."""
    audio_path = temp_dir / "test_audio.mp4"
    # Create a small file with some content
    with open(audio_path, "wb") as f:
        f.write(b"FAKE_AUDIO_DATA" * 1000)
    return audio_path


@pytest.fixture(scope="function")
def mock_transcript_response():
    """Mock response from transcription service."""
    return Mock(
        text=SAMPLE_TRANSCRIPT["text"],
        segments=SAMPLE_TRANSCRIPT["segments"],
        language=SAMPLE_TRANSCRIPT["language"],
        confidence=SAMPLE_TRANSCRIPT["confidence"]
    )


@pytest.fixture(scope="function")
def mock_translation_response():
    """Mock response from translation service."""
    def _mock_translate(text: str, target_lang: str, source_lang: str = "en"):
        if target_lang in SAMPLE_TRANSLATION:
            return SAMPLE_TRANSLATION[target_lang]
        return f"Mock translation to {target_lang}"
    return _mock_translate


@pytest.fixture(scope="function")
def mock_evaluation_response():
    """Mock response from evaluation service."""
    return Mock(
        choices=[Mock(
            message=Mock(
                content=str(SAMPLE_EVALUATION)
            )
        )]
    )


@pytest.fixture(scope="function")
async def async_mock_client():
    """Create an async mock client for API testing."""
    client = AsyncMock()
    client.transcribe = AsyncMock(return_value=SAMPLE_TRANSCRIPT)
    client.translate = AsyncMock(return_value=SAMPLE_TRANSLATION["de"])
    client.evaluate = AsyncMock(return_value=SAMPLE_EVALUATION)
    return client


@pytest.fixture(scope="function")
def capture_logs(caplog):
    """Fixture to capture and assert on log messages."""
    with caplog.at_level("INFO"):
        yield caplog


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset any singleton instances between tests."""
    # Reset DatabaseOperations singleton if it exists
    if hasattr(DatabaseOperations, '_instances'):
        DatabaseOperations._instances = {}
    yield


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Helper functions for tests

def create_test_file_record(db: DatabaseOperations, **kwargs) -> int:
    """Helper to create a test file record with defaults."""
    defaults = SAMPLE_AUDIO_METADATA.copy()
    defaults.update(kwargs)
    return db.add_file(**defaults)


def assert_db_file_count(db: DatabaseOperations, expected: int):
    """Assert the number of files in database."""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM media_files")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == expected, f"Expected {expected} files, found {count}"


def assert_translation_exists(db: DatabaseOperations, file_id: int, language: str):
    """Assert a translation exists for given file and language."""
    translations = db.get_translations(file_id)
    assert any(t['language_code'] == language for t in translations), \
        f"No translation found for language {language}"


def create_mock_api_response(status_code: int = 200, json_data: Dict[str, Any] = None):
    """Create a mock API response object."""
    response = Mock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.text = str(json_data or {})
    return response


# Pytest hooks

def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Ensure test output directory exists
    test_output = Path("test_output")
    test_output.mkdir(exist_ok=True)
    
    # Set test environment
    os.environ["SCRIBE_TEST_MODE"] = "1"


def pytest_unconfigure(config):
    """Clean up after test run."""
    # Remove test environment variable
    os.environ.pop("SCRIBE_TEST_MODE", None)
    
    # Clean up test output if empty
    test_output = Path("test_output")
    if test_output.exists() and not any(test_output.iterdir()):
        test_output.rmdir()


# Custom markers

pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.external = pytest.mark.external
pytest.mark.database = pytest.mark.database
pytest.mark.async = pytest.mark.asyncio
pytest.mark.hebrew = pytest.mark.hebrew