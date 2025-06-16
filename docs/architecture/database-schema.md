# Database Schema Documentation

**Database**: SQLite (`media_tracking.db`)  
**Last Updated**: 2025-06-15

## Overview

The Scribe system uses SQLite with four main tables to track media files, processing status, quality evaluations, and errors. The database uses thread-safe connection pooling for concurrent operations.

## Tables

### 1. media_files
Stores information about source media files.

| Column | Type | Description |
|--------|------|-------------|
| file_id | TEXT PRIMARY KEY | UUID for the file |
| original_path | TEXT NOT NULL | Full original path to the file |
| safe_filename | TEXT NOT NULL | Sanitized filename |
| file_size | INTEGER | Size in bytes |
| duration | REAL | Duration in seconds |
| checksum | TEXT | File checksum |
| media_type | TEXT | 'audio' or 'video' |
| detected_language | TEXT | Detected language code |
| created_at | TIMESTAMP | When record was created |

### 2. processing_status
Tracks the processing state of each file through the pipeline.

| Column | Type | Description |
|--------|------|-------------|
| file_id | TEXT PRIMARY KEY | Foreign key to media_files |
| status | TEXT NOT NULL | Overall status: 'pending', 'in-progress', 'completed', 'failed' |
| transcription_status | TEXT | Status: 'not_started', 'completed', 'failed' |
| translation_en_status | TEXT | English translation status |
| translation_de_status | TEXT | German translation status |
| translation_he_status | TEXT | Hebrew translation status |
| started_at | TIMESTAMP | When processing started |
| completed_at | TIMESTAMP | When processing completed |
| last_updated | TIMESTAMP | Last status update |
| attempts | INTEGER DEFAULT 0 | Number of processing attempts |

### 3. quality_evaluations
Stores quality evaluation scores for translations.

| Column | Type | Description |
|--------|------|-------------|
| eval_id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| file_id | TEXT NOT NULL | Foreign key to media_files |
| language | TEXT NOT NULL | Language code: 'en', 'de', 'he' |
| model | TEXT NOT NULL | Evaluation model used (e.g., 'gpt-4.1') |
| score | REAL NOT NULL | Quality score (0-10) |
| issues | TEXT | JSON array of identified issues |
| comment | TEXT | Overall evaluation comment |
| evaluated_at | TIMESTAMP | When evaluation was performed |
| custom_data | TEXT | Additional evaluation data |

### 4. errors
Logs processing errors for debugging.

| Column | Type | Description |
|--------|------|-------------|
| error_id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| file_id | TEXT NOT NULL | Foreign key to media_files |
| process_stage | TEXT NOT NULL | Stage where error occurred |
| error_message | TEXT | Error message |
| error_details | TEXT | Detailed error information |
| timestamp | TIMESTAMP | When error occurred |

## Current Data Summary

As of the last assessment:
- **Total files**: 728
- **Transcribed**: 728 (100%)
- **Translated to English**: 727 (99.9%)
- **Translated to German**: 728 (100%)
- **Translated to Hebrew**: 727 (99.9%)
- **Quality evaluations**: 208 total
  - German: 53 evaluations (avg score: 7.75)
  - English: 58 evaluations (avg score: 8.58)
  - Hebrew: 97 evaluations (avg score: 7.51)

## Schema Considerations

### Foreign Key Relationships
- `processing_status.file_id` → `media_files.file_id`
- `quality_evaluations.file_id` → `media_files.file_id`
- `errors.file_id` → `media_files.file_id`

### Indexes
The schema uses default SQLite indexes on primary keys. Additional indexes could be added for:
- `processing_status.transcription_status`
- `processing_status.translation_*_status`
- `quality_evaluations.language`

### Thread Safety
The database uses a thread-local connection pool with:
- 30-second timeout for locks
- Row factory for dict-like access
- Foreign key constraints enabled

## Migration Notes

The current schema differs from what some code expects:
- Code references a `files` table that doesn't exist
- Code expects `quality_score_*` columns in a single table
- Actual schema separates concerns into multiple tables

This mismatch is being addressed in the Hebrew Evaluation Fix PRD.