# Database Queries Reference Guide

This document provides common database queries for the media transcription and translation pipeline, 
using the `db_query.py` utility for simplified database interaction.

## Using the Database Query Utility

The `db_query.py` utility makes it easy to execute SQL queries without complex quoting issues:

```bash
# Basic query format
python db_query.py "YOUR SQL QUERY HERE"

# Choose output format (json, table, or raw)
python db_query.py --format table "SELECT * FROM processing_status LIMIT 5"
```

## Common Status Queries

### Translation Completion Status

Check completion counts for each language:

```bash
# Check English translations completed
python db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_en_status = 'completed'"

# Check German translations completed
python db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_de_status = 'completed'"

# Check Hebrew translations completed
python db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_he_status = 'completed'"

# Get all completion statistics in one query
python db_query.py --format table "
SELECT 
    SUM(CASE WHEN transcription_status = 'completed' THEN 1 ELSE 0 END) as transcription_completed,
    SUM(CASE WHEN translation_en_status = 'completed' THEN 1 ELSE 0 END) as english_completed,
    SUM(CASE WHEN translation_de_status = 'completed' THEN 1 ELSE 0 END) as german_completed,
    SUM(CASE WHEN translation_he_status = 'completed' THEN 1 ELSE 0 END) as hebrew_completed,
    COUNT(*) as total_files
FROM processing_status
"
```

### Processing Status

Check files by their current processing status:

```bash
# Count files by status
python db_query.py --format table "
SELECT 
    status, 
    COUNT(*) as count 
FROM processing_status 
GROUP BY status 
ORDER BY count DESC
"

# Count files by transcription status
python db_query.py --format table "
SELECT 
    transcription_status, 
    COUNT(*) as count 
FROM processing_status 
GROUP BY transcription_status 
ORDER BY count DESC
"

# Count in-progress files by translation type
python db_query.py --format table "
SELECT 
    'English' as language, COUNT(*) as in_progress 
FROM processing_status 
WHERE translation_en_status = 'in-progress'
UNION
SELECT 
    'German' as language, COUNT(*) as in_progress 
FROM processing_status 
WHERE translation_de_status = 'in-progress'
UNION
SELECT 
    'Hebrew' as language, COUNT(*) as in_progress 
FROM processing_status 
WHERE translation_he_status = 'in-progress'
"
```

### Error Analysis

Analyze errors in the database:

```bash
# Count errors by process stage
python db_query.py --format table "
SELECT 
    process_stage, 
    COUNT(*) as error_count 
FROM errors 
GROUP BY process_stage 
ORDER BY error_count DESC
"

# Get recent errors (last 24 hours)
python db_query.py --format table "
SELECT 
    file_id, 
    process_stage, 
    error_message, 
    timestamp 
FROM errors 
WHERE timestamp > datetime('now', '-24 hours') 
ORDER BY timestamp DESC
"

# Count error messages by type
python db_query.py --format table "
SELECT 
    error_message, 
    COUNT(*) as count 
FROM errors 
GROUP BY error_message 
ORDER BY count DESC 
LIMIT 10
"
```

### File Information

Get information about specific files:

```bash
# Look up file by ID
python db_query.py "
SELECT * 
FROM processing_status 
WHERE file_id = 'your-file-id-here'
"

# Find files by original path (partial match)
python db_query.py --format table "
SELECT 
    file_id, 
    original_path, 
    transcription_status,
    translation_en_status,
    translation_de_status,
    translation_he_status
FROM processing_status 
WHERE original_path LIKE '%keyword%'
"

# Find the largest files
python db_query.py --format table "
SELECT 
    file_id, 
    original_path, 
    file_size / (1024*1024) as size_mb, 
    media_type 
FROM processing_status 
ORDER BY file_size DESC 
LIMIT 10
"
```

### Quality Evaluation

Check quality evaluation status:

```bash
# Count quality evaluations by language and result
python db_query.py --format table "
SELECT 
    language, 
    SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed,
    COUNT(*) as total,
    ROUND(SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pass_rate
FROM quality_evaluations
GROUP BY language
"

# Get files with failed quality evaluations
python db_query.py --format table "
SELECT 
    file_id, 
    language, 
    score, 
    timestamp 
FROM quality_evaluations 
WHERE passed = 0 
ORDER BY timestamp DESC
"
```

### Timestamps and Progress Tracking

Track progress over time:

```bash
# Check last updated timestamps
python db_query.py --format table "
SELECT 
    file_id, 
    last_updated,
    datetime('now') as current_time,
    (julianday('now') - julianday(last_updated)) * 24 * 60 as minutes_since_update
FROM processing_status 
ORDER BY last_updated DESC 
LIMIT 5
"

# Check oldest in-progress items
python db_query.py --format table "
SELECT 
    file_id, 
    last_updated,
    datetime('now') as current_time,
    ROUND((julianday('now') - julianday(last_updated)) * 24 * 60, 1) as minutes_in_progress
FROM processing_status 
WHERE translation_en_status = 'in-progress' 
    OR translation_de_status = 'in-progress' 
    OR translation_he_status = 'in-progress'
ORDER BY last_updated ASC
LIMIT 10
"
```

## Troubleshooting Queries

### Check for Missing Transcripts

Find files with "completed" status but missing transcript files:

```bash
# First gather file IDs with completed transcription
python db_query.py "
SELECT file_id 
FROM processing_status 
WHERE transcription_status = 'completed' 
LIMIT 100
" > completed_transcripts.json

# Then check these files with the check_transcript_file.py tool
```

### Check for Duplicate Files

Find potential duplicate files in the database:

```bash
python db_query.py --format table "
SELECT 
    original_path, 
    COUNT(*) as count 
FROM processing_status 
GROUP BY original_path 
HAVING COUNT(*) > 1
"
```

## Data Modification Queries

⚠️ **Warning**: These queries modify the database. Use with caution! ⚠️

For safety, we recommend using the specialized tools instead, but these queries are provided for reference:

```bash
# Reset stuck translations (DO NOT RUN DIRECTLY - use check_stuck_files.py instead)
python db_query.py "
UPDATE processing_status
SET status = 'pending',
    translation_en_status = 'not_started',
    translation_de_status = 'not_started',
    translation_he_status = 'not_started'
WHERE file_id = 'specific-file-id-here'
"

# Reset errors for a specific file
python db_query.py "
DELETE FROM errors 
WHERE file_id = 'specific-file-id-here'
"
```