# Database Schema Documentation

**Database**: SQLite (`media_tracking.db`)  
**Last Updated**: 2025-07-30

## Overview

The Scribe system uses SQLite with five main tables to track media files, processing status, subtitle segments, quality evaluations, and errors. The database uses thread-safe connection pooling for concurrent operations. The subtitle-first architecture stores word-level segments with precise timestamps for improved synchronization.

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

### 5. subtitle_segments
Stores word-level subtitle segments with precise timestamps for each interview.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| interview_id | TEXT NOT NULL | Foreign key to media_files |
| segment_index | INTEGER NOT NULL | Sequential segment number |
| start_time | REAL NOT NULL | Start time in seconds |
| end_time | REAL NOT NULL | End time in seconds |
| duration | REAL GENERATED | Calculated duration (end_time - start_time) |
| original_text | TEXT NOT NULL | Original transcribed text |
| german_text | TEXT | German translation |
| english_text | TEXT | English translation |
| hebrew_text | TEXT | Hebrew translation |
| confidence_score | REAL | Transcription confidence (0-1) |
| processing_timestamp | DATETIME | When segment was processed |

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

## Database Views

### 1. transcripts
Provides backward-compatible access to full transcripts by aggregating subtitle segments.

| Column | Type | Description |
|--------|------|-------------|
| interview_id | TEXT | Interview identifier |
| original_transcript | TEXT | Concatenated original text |
| german_transcript | TEXT | Concatenated German translation |
| english_transcript | TEXT | Concatenated English translation |
| hebrew_transcript | TEXT | Concatenated Hebrew translation |
| total_segments | INTEGER | Number of segments |
| avg_confidence | REAL | Average confidence score |
| transcript_start | REAL | First segment start time |
| transcript_end | REAL | Last segment end time |

### 2. segment_quality
Provides quality metrics for subtitle segments.

| Column | Type | Description |
|--------|------|-------------|
| interview_id | TEXT | Interview identifier |
| total_segments | INTEGER | Total number of segments |
| avg_segment_duration | REAL | Average segment length |
| min_segment_duration | REAL | Shortest segment |
| max_segment_duration | REAL | Longest segment |
| avg_confidence | REAL | Average confidence score |
| low_confidence_segments | INTEGER | Segments with confidence < 0.8 |
| short_segments | INTEGER | Segments shorter than 1 second |
| long_segments | INTEGER | Segments longer than 10 seconds |

## Schema Considerations

### Foreign Key Relationships
- `processing_status.file_id` → `media_files.file_id`
- `quality_evaluations.file_id` → `media_files.file_id`
- `errors.file_id` → `media_files.file_id`
- `subtitle_segments.interview_id` → `media_files.file_id`

### Indexes
The schema uses default SQLite indexes on primary keys. Additional indexes have been created for:
- `subtitle_segments(interview_id, segment_index)` - For ordered segment retrieval
- `processing_status.transcription_status`
- `processing_status.translation_*_status`
- `quality_evaluations.language`

### Thread Safety
The database uses a thread-local connection pool with:
- 30-second timeout for locks
- Row factory for dict-like access
- Foreign key constraints enabled

## Migration Notes

### Subtitle-First Architecture Migration (2025-07-30)
The database has been enhanced with the subtitle-first architecture:
- New `subtitle_segments` table stores word-level segments with precise timestamps
- Database views maintain backward compatibility with existing code
- Existing transcript data is preserved and accessible through views
- Migration script available: `migrate_to_subtitle_segments.py`

### Legacy Schema Issues (Resolved)
Previous schema mismatches have been addressed:
- The `files` table reference has been corrected to `media_files`
- Quality scores are properly stored in `quality_evaluations` table
- All code now uses the correct table structure

### Backward Compatibility
The `transcripts` view provides seamless access to full transcript text by aggregating segments, ensuring existing code continues to function without modification.