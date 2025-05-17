# Media Transcription and Translation Tool PRD
**Version:** 1.0  
**Date:** April 7, 2025  
**Project:** Bryan Rigg Media Archive Transcription System  

## 1. Executive Summary

This tool will process a large collection of audio and video files (700+ items) by automatically transcribing content using ElevenLabs Scribe, translating transcripts from German to English and Hebrew, and producing organized outputs with comprehensive tracking. The system emphasizes reliability, recoverability, and efficient batch processing to handle complex media collections with Unicode filenames and special characters.

## 2. System Overview

### 2.1 Core Functionality
- Recursively scan directories for audio/video files
- Handle and sanitize complex filenames (Unicode, special characters, spaces)
- Extract audio from video files when necessary
- Transcribe content using ElevenLabs Scribe v1
- Translate German transcripts to English (DeepL) and Hebrew (Google/Microsoft)
- Generate SRT subtitle files for all languages
- Track processing states in a database
- Produce detailed reports
- Support resumption of interrupted processes

### 2.2 Key Workflow
1. **Discovery & Preparation**
   - Find and validate media files
   - Sanitize filenames
   - Extract audio when needed
   - Store metadata
  
2. **Transcription**
   - Process audio through ElevenLabs Scribe
   - Generate transcript text and SRT files
   - Store results with appropriate metadata

3. **Translation**
   - Translate German transcripts to English via DeepL
   - Translate German transcripts to Hebrew via Google Cloud/Microsoft
   - Generate translated SRT files
   - Store translations in organized structure

4. **Reporting**
   - Track success/failure status for each file
   - Generate detailed CSV and Markdown reports
   - Provide command-line progress indicators

## 3. Technical Requirements

### 3.1 Database Schema

```sql
-- Media Files Table
CREATE TABLE media_files (
    file_id TEXT PRIMARY KEY,     -- Unique ID for the file
    original_path TEXT NOT NULL,  -- Full original path to the file
    safe_filename TEXT NOT NULL,  -- Sanitized filename
    file_size INTEGER,            -- Size in bytes
    duration REAL,                -- Duration in seconds
    checksum TEXT,                -- File checksum
    media_type TEXT,              -- 'audio' or 'video'
    detected_language TEXT,       -- Detected language code
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processing Status Table
CREATE TABLE processing_status (
    file_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,         -- 'pending', 'in-progress', 'completed', 'failed'
    transcription_status TEXT,    -- 'not_started', 'completed', 'failed'
    translation_en_status TEXT,   -- 'not_started', 'completed', 'failed'
    translation_he_status TEXT,   -- 'not_started', 'completed', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    last_updated TIMESTAMP,
    attempts INTEGER DEFAULT 0,
    FOREIGN KEY (file_id) REFERENCES media_files(file_id)
);

-- Error Tracking Table
CREATE TABLE errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    process_stage TEXT NOT NULL,  -- 'discovery', 'extraction', 'transcription', 'translation_en', 'translation_he'
    error_message TEXT,
    error_details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES media_files(file_id)
);
```

### 3.2 Directory Structure

```
output/
  ├── {file_id_1}/
  │   ├── metadata.json          # Original filename, path, duration, etc.
  │   ├── audio/                 # Extracted audio (if from video)
  │   │   └── audio.mp3          # Extracted audio file
  │   ├── original/              # Original language content
  │   │   ├── transcript.txt     # Full transcript
  │   │   └── subtitles.srt      # SRT subtitles
  │   ├── en/                    # English translation
  │   │   ├── transcript.txt     # Translated transcript
  │   │   └── subtitles.srt      # Translated subtitles
  │   └── he/                    # Hebrew translation
  │       ├── transcript.txt     # Translated transcript
  │       └── subtitles.srt      # Translated subtitles
  ├── {file_id_2}/
  │   ├── ...
  ...
```

### 3.3 API Dependencies

1. **Transcription:**
   - ElevenLabs Scribe v1 API
   - Authentication: API key
   - Rate limits: [To be determined]

2. **Translation:**
   - DeepL API Pro (German → English)
     - Authentication: API key
     - Rate limits: Character-based pricing
   - Google Cloud Translation API or Microsoft Translator (German → Hebrew)
     - Authentication: API key/credentials
     - Rate limits: Character-based pricing

### 3.4 External Dependencies

- Python 3.9+
- FFmpeg (for audio extraction)
- SQLite (for state tracking)
- Common Python libraries:
  - requests / aiohttp
  - tqdm (progress bars)
  - pyyaml (configuration)
  - moviepy (optional alternative for ffmpeg)

## 4. Command-Line Interface

```
python media_processor.py [options]

Input Options:
  -d, --directory DIR      Process media in this directory (recursive)
  -f, --file FILE          Process a single file
  -r, --retry              Retry previously failed files
  --status STATUS          Filter by status (pending/in-progress/failed/completed)

Processing Options:
  --extract-only           Only extract audio, don't transcribe
  --transcribe-only        Only transcribe, don't translate
  --translate-only LANG    Only translate to specified language(s)
  --workers N              Number of parallel workers (default: auto-detect)
  --source-lang LANG       Source language code (default: auto-detect)
  --formality {default|more|less}  Formality level for translations
  
Control Options:
  --limit N                Process only first N files found
  --test                   Quick test with only 3 files
  --dry-run                Show what would be processed without processing
  --force                  Force reprocessing of already completed items
  
Output Options:
  -o, --output DIR         Base output directory (default: ./output)
  --report FILE            Save processing report to file
  --log FILE               Log file location
  --log-level LEVEL        Logging level (DEBUG/INFO/WARNING/ERROR)
  
Configuration:
  --config FILE            Load configuration from YAML/JSON file
  --save-config FILE       Save current settings to config file
  
Database Options:
  --db FILE                SQLite database file (default: ./media_tracking.db)
  --reset-db               Reset the database (caution!)
  --list-files             List all tracked files and status
  --file-status ID         Show detailed status for a specific file ID
```

## 5. Implementation Plan

### 5.1 Core Modules

1. **Main Controller (`media_processor.py`)**
   - CLI argument parsing
   - Orchestration of workflow
   - Configuration loading

2. **File Manager (`file_manager.py`)**
   - File discovery
   - Filename sanitization
   - Audio extraction
   - Checksum calculation

3. **Database Manager (`db_manager.py`)**
   - Schema creation
   - State tracking
   - Status updates
   - Error logging

4. **Transcription Engine (`transcription.py`)**
   - ElevenLabs API integration
   - Transcription request handling
   - SRT generation
   - Error handling

5. **Translation Engine (`translation.py`)**
   - DeepL integration
   - Google/Microsoft integration
   - Translation formatting
   - SRT timestamp preservation

6. **Concurrency Manager (`worker_pool.py`)**
   - Worker pool management
   - Task distribution
   - Resource monitoring

7. **Reporter (`reporter.py`)**
   - Progress visualization
   - CSV/Markdown report generation
   - Summary statistics

### 5.2 Development Phases

1. **Phase 1: Core Infrastructure (2 weeks)**
   - Database schema implementation
   - File discovery and sanitization
   - Basic CLI arguments
   - Initial test framework

2. **Phase 2: Transcription Pipeline (3 weeks)**
   - Audio extraction
   - ElevenLabs integration
   - SRT generation
   - State management

3. **Phase 3: Translation Pipeline (2 weeks)**
   - DeepL integration
   - Google/Microsoft integration
   - Translation formatting
   - Multilingual SRT generation

4. **Phase 4: Concurrency & Recovery (2 weeks)**
   - Worker pool implementation
   - Error handling & recovery
   - Performance optimization
   - Memory management

5. **Phase 5: Reporting & Finalization (1 week)**
   - Report generation
   - Documentation
   - Final testing
   - Deployment preparation

## 6. Error Handling Strategy

1. **Categorized Error Types**
   - File System Errors
   - Network/API Errors
   - Content Processing Errors
   - System Resource Errors

2. **Retry Mechanism**
   - Exponential backoff for transient errors
   - Maximum retry attempts configurable
   - Different retry strategies by error category

3. **Recovery Process**
   - Checkpoint system for long-running operations
   - Detailed error logging for debugging
   - Ability to resume at various stages

## 7. Security Considerations

1. **API Credential Management**
   - Environment variables for secrets
   - Support for credential files with appropriate permissions
   - No hardcoded credentials in code

2. **Data Handling**
   - Secure handling of potentially sensitive audio content
   - Cleanup of temporary files
   - Optional encryption of transcription results

## 8. Testing Plan

1. **Unit Tests**
   - File sanitization functions
   - Database operations
   - API client wrappers

2. **Integration Tests**
   - End-to-end workflow with sample files
   - API integration verification
   - Error handling verification

3. **Performance Tests**
   - Concurrency optimization
   - Memory usage profiling
   - Long-running stability tests

## 9. Configuration Template

```yaml
# Main configuration
output_directory: "./output"
database_file: "./media_tracking.db"
log_file: "./media_processor.log"
log_level: "INFO"

# Processing options
workers: 4
extract_audio_format: "mp3"  # mp3 or wav
extract_audio_quality: "192k"

# API configuration
elevenlabs:
  api_key: "${ELEVENLABS_API_KEY}"  # Uses environment variable
  model: "scribe-v1"
  speaker_detection: true
  speaker_count: 32  # Max speakers to detect

deepl:
  api_key: "${DEEPL_API_KEY}"
  formality: "default"  # default, more, less
  batch_size: 5000  # characters per batch

google_translate:
  credentials_file: "./google_credentials.json"
  location: "global"
  batch_size: 5000  # characters per batch

microsoft_translator:
  api_key: "${MS_TRANSLATOR_KEY}"
  location: "global"
  batch_size: 5000  # characters per batch

# File extensions to process
media_extensions:
  audio:
    - ".mp3"
    - ".wav"
    - ".m4a"
    - ".aac"
    - ".flac"
  video:
    - ".mp4"
    - ".avi"
    - ".mov"
    - ".mkv"
    - ".webm"
```

## 10. Key Metrics and Success Criteria

1. **Performance Metrics**
   - Average processing time per minute of audio
   - API cost per hour of content
   - Failure rate (per process stage)
   - Resource utilization

2. **Success Criteria**
   - All 700+ media files successfully processed
   - 95%+ transcription accuracy for German content
   - 90%+ translation quality based on sampling
   - System recoverable from all major interruption types

## 11. Known Limitations and Constraints

1. **API Rate Limits**
   - ElevenLabs: [TBD based on subscription]
   - DeepL: Character-based billing
   - Google/Microsoft: Character-based billing

2. **Processing Challenges**
   - Large files (>2 hours) may require special handling
   - Low-quality audio may reduce transcription accuracy
   - Heavy accents may impact transcription quality
   - Specialized terminology may affect translation accuracy

3. **System Requirements**
   - Minimum 8GB RAM recommended
   - SSD storage for database and processing files
   - Stable internet connection for API access
