# Media Transcribe Manager - Product Requirements Document

**Date:** April 7, 2025  
**Project:** Bryan Rigg Media Archive  
**Author:** Cascade AI  

## Overview

Media Transcribe Manager is a robust media processing system designed to transcribe large collections of audio and video files using the ElevenLabs API, with support for future translation capabilities. The system emphasizes reliability, state management, and recoverability to handle complex media collections with special characters and Unicode in filenames.

## Background

The Bryan Rigg Media Archive contains over 700 media files (audio and video) with complex filenames containing special characters, spaces, parentheses, and Unicode. The existing `video_to_text.py` script has proven capable of transcribing individual files, but lacks the state management and batch processing capabilities needed for efficiently processing the entire collection.

## Objectives

1. Create a reliable batch processing system for audio and video transcription
2. Implement robust state tracking to handle interruptions and failures
3. Establish an organized output structure for current transcriptions and future translations
4. Provide detailed progress reporting and error handling
5. Support concurrent processing to leverage modern hardware

## Requirements

### Core Functionality

1. **Media Processing**
   - Process both audio and video files
   - Support recursive directory traversal
   - Handle input filenames with Unicode, spaces, and special characters
   - Leverage ElevenLabs API for transcription
   - Generate both plain text transcripts and SRT subtitle files

2. **State Management**
   - Use SQLite to track all file processing
   - Assign unique IDs to each media file
   - Record processing status (pending, in-progress, completed, failed)
   - Store detailed error information when failures occur
   - Enable resuming interrupted jobs

3. **Output Organization**
   - Create standardized folder structure: `output/{fileID}/`
   - Use language code subfolders: `output/{fileID}/{lang}/`
   - Store original transcription: `output/{fileID}/original/{filename}.txt|.srt`
   - Reserve structure for future translations: `output/{fileID}/{lang_code}/{filename}.txt|.srt`
   - Maintain mapping between original filenames and IDs
   - Sanitize output filenames for cross-platform compatibility

4. **Recovery Workflow**
   - Implement retry capability for failed files
   - Include file change detection via checksums
   - Provide comprehensive error reporting
   - Allow selective processing by status

5. **Translation Preparation**
   - Identify original language
   - Store intermediate data for future translation
   - Design extensible schema for tracking translation status

6. **Progress Visualization**
   - Show real-time processing status
   - Provide ETA for completion
   - Generate summary reports

### Performance Requirements

1. **Concurrency**
   - Process multiple files in parallel
   - Auto-scale based on available CPU cores
   - Manage memory usage during parallel processing

2. **Efficiency**
   - Avoid redundant API calls
   - Minimize disk I/O during batch processing
   - Optimize database operations

### Testing & Validation

1. **Test Mode**
   - Provide ability to limit processing to first N files
   - Include quick test mode (process 3 files)
   - Support dry run to preview what would be processed

2. **File Identification**
   - Utilities to check status of specific files
   - Look up original file from generated ID
   - Quick status overview

## Command-Line Interface

```
python media_transcribe_manager.py [options]

Input Options:
  -f, --file FILE          Process a single media file
  -d, --directory DIR      Process all media in a directory (recursive)
  -r, --retry              Retry all previously failed files
  -s, --status STATUS      Only process files with specified status (pending/failed)

Processing Options:
  --language LANG          Language code for transcription (default: auto)
  --subtitles              Generate SRT subtitle files
  --workers N              Number of parallel workers (default: auto-detect)

Testing Options:
  --limit N                Process only the first N files found (for testing)
  --test                   Equivalent to --limit 3 (quick test mode)
  --dry-run                Scan and show what would be processed without processing

Identification:
  --identify FILE          Show processing status for a specific file
  --lookup ID              Look up original file from an ID
  
Output Options:
  -o, --output DIR         Base output directory (default: ./output)
  --report FILE            Save processing report to specified file
  
Database Options:
  --db FILE                SQLite database file location (default: ./media_tracking.db)
  --reset-db               Reset the database (use with caution)
```

## Database Schema

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
    error_message TEXT,
    error_details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES media_files(file_id)
);

-- Translation Tracking Table (for future use)
CREATE TABLE translations (
    translation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    source_language TEXT NOT NULL,
    target_language TEXT NOT NULL,
    status TEXT NOT NULL,         -- 'pending', 'in-progress', 'completed', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES media_files(file_id)
);
```

## Output Directory Structure

```
output/
  ├── {file_id_1}/
  │   ├── metadata.json          # Contains original filename, path, and metadata
  │   ├── original/              # Original language content
  │   │   ├── transcript.txt     # Full transcript
  │   │   └── subtitles.srt      # SRT subtitles
  │   └── {target_lang}/         # Future translation (e.g., 'eng', 'deu', etc.)
  │       ├── transcript.txt     # Translated transcript
  │       └── subtitles.srt      # Translated subtitles
  ├── {file_id_2}/
  │   ├── ...
  ...
```

## Implementation Approach

1. **Module Structure**
   - `media_transcribe_manager.py`: Main script and CLI
   - `file_handler.py`: Media file discovery and path normalization
   - `db_manager.py`: Database interactions
   - `transcription.py`: ElevenLabs API integration
   - `worker_pool.py`: Concurrent processing
   - `output_manager.py`: File output organization
   - `reporter.py`: Progress and status reporting

2. **Development Phases**
   - Phase 1: Core file processing, database schema, and basic CLI
   - Phase 2: Concurrent processing and status management
   - Phase 3: Error handling, recovery, and reporting
   - Phase 4: Testing and optimization

## Success Criteria

1. Successfully process all valid media files in the Bryan Rigg collection
2. Generate accurate transcripts and SRT files for all processed media
3. Recover gracefully from any interruptions or API failures
4. Provide detailed reporting on processing status and errors
5. Create a foundation for future translation capabilities

## Dependencies

- Python 3.9+
- SQLite
- ElevenLabs SDK
- FFmpeg (via MoviePy)
- tqdm (for progress visualization)
- concurrent.futures (standard library, for parallelism)
