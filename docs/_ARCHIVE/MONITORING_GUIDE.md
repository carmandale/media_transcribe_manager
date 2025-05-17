# Translation Pipeline Monitoring Guide

This document provides instructions for monitoring and maintaining the translation pipeline.

## Overview

The translation pipeline processes hundreds of audio/video files through multiple stages:
1. Transcription
2. Translation (English, German, Hebrew)
3. Quality evaluation
4. Reporting

During processing, issues may arise such as stalled translations or missing transcript files. This guide explains how to monitor and recover from such issues.

## Status Checking Tools

### Check Translation Status

The `check_status.py` script provides a comprehensive view of the current translation status:

```bash
python check_status.py
```

This shows:
- Most recently updated files
- Number of translations in progress
- Time since last database update
- Completion status for each language
- Quality evaluation results
- Recent errors

### Identify and Fix Stuck Processes

The `check_stuck_files.py` script identifies and resets files stuck in the 'in-progress' state:

```bash
python check_stuck_files.py
```

This will:
1. Find files that have been in the 'in-progress' state for over 30 minutes
2. Reset them to 'not_started' state so they can be processed again
3. Show which files were reset

To automatically reset stuck files:

```bash
python check_stuck_files.py --reset
```

### Identify and Fix Missing Transcripts

Several tools are available to address "Transcript text not found" errors:

```bash
# Check transcript details for a specific file
python check_transcript_file.py <file_id>

# Find and fix files with "Transcript text not found" errors
python fix_missing_transcripts.py --reset

# Identify any files marked as completed but with missing transcript files
python find_all_missing_transcripts.py
```

### Debug Transcription Issues

For troubleshooting specific transcription problems:

```bash
# Debug transcription for a specific file
python debug_transcription.py --file-id <file_id>
```

This script:
- Checks file integrity and format
- Tests API connectivity
- Attempts to transcribe a small sample
- Identifies potential issues

## Automated Monitoring

For continuous monitoring, the `monitor_and_restart.py` script provides automated checking and recovery:

```bash
# Basic usage (10-minute check interval)
python monitor_and_restart.py

# Custom configuration
python monitor_and_restart.py --check-interval 15 --batch-size 20 --languages en,de,he

# Run for a limited number of cycles
python monitor_and_restart.py --max-runs 5
```

### Features

- **Periodic Status Checks**: Automatically checks translation status at specified intervals
- **Stuck Process Detection**: Identifies and resets processes stuck for >30 minutes
- **Automatic Pipeline Restart**: Restarts the translation pipeline when needed
- **Regular Status Reports**: Generates comprehensive status reports
- **Error Handling**: Continues monitoring even if errors occur
- **Configurable Parameters**:
  - `--check-interval`: Minutes between checks (default: 30)
  - `--batch-size`: Batch size for processing (default: 10)
  - `--languages`: Languages to process (default: en,de,he)
  - `--max-runs`: Maximum number of monitoring cycles (0 = unlimited)

### Running in Background

To run the monitoring script in the background:

```bash
# Linux/MacOS
python monitor_and_restart.py > monitoring.log 2>&1 &

# To view monitoring output
tail -f monitoring.log
```

### Verifying Monitoring is Running

To check if the monitoring script is running:

```bash
ps -ef | grep monitor_and_restart.py | grep -v grep
```

To check if the pipeline is running:

```bash
ps -ef | grep run_full_pipeline.py | grep -v grep
```

## Troubleshooting Common Issues

### Stalled Translations

If translations appear to be stalled:

1. **Check Status**: Run `python check_status.py` to verify the status
   - Look at "Last database update" - if >30 minutes, translations are stalled
   - Check how many translations are still in progress

2. **Reset Stuck Processes**: Run `python check_stuck_files.py --reset` to reset any stuck processes

3. **Restart Pipeline**: Run `python run_full_pipeline.py --batch-size 10 --languages en,de,he` to restart processing

4. **Start Monitoring**: For continued monitoring, use `python monitor_and_restart.py`

### Missing Transcript Files

If translations fail with "Transcript text not found" errors:

1. **Identify Files**: Run `python fix_missing_transcripts.py` to identify affected files

2. **Reset for Retranscription**: Run `python fix_missing_transcripts.py --reset` to mark files for retranscription

3. **Verify Reset**: Use `python check_transcript_file.py <file_id>` to verify status was reset correctly

4. **Monitor Progress**: Check status regularly to ensure files are being retranscribed

### Persistent Transcription Failures

If certain files repeatedly fail to transcribe:

1. **Debug Specific File**: Run `python debug_transcription.py --file-id <file_id>` to diagnose issues

2. **Check File Format**: Verify audio format and integrity using the debug script

3. **Check API Access**: Ensure the ElevenLabs API key is valid and has sufficient quota

4. **Try Manual Splitting**: For large files, consider manually splitting into smaller segments

## Common Issues and Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Stalled translations | No database updates for >30 minutes | Run `check_stuck_files.py --reset` and restart pipeline |
| Missing transcript files | "Transcript text not found" errors | Run `fix_missing_transcripts.py --reset` |
| Process crashes | No Python processes running | Restart pipeline with `run_full_pipeline.py` |
| Database errors | SQLite errors in logs | Check database file permissions and integrity |
| API rate limiting | Many API errors in error log | Reduce batch size, increase sleep between calls |
| Quality failure pattern | Many files failing quality checks | Review quality evaluation criteria |
| Large file failures | Transcription timeouts on large files | Ensure the file splitting logic is working correctly |

## Regular Maintenance Tasks

To ensure the pipeline runs smoothly:

1. **Daily Status Checks**:
   ```bash
   python check_status.py
   ```

2. **Monitor Running Processes**:
   ```bash
   ps -ef | grep monitor_and_restart.py
   ps -ef | grep run_full_pipeline.py
   ```

3. **Check Recent Errors**:
   ```bash
   python -c "import sqlite3; conn = sqlite3.connect('media_tracking.db'); cursor = conn.cursor(); cursor.execute('SELECT process_stage, COUNT(*) FROM errors WHERE timestamp > datetime(\"now\", \"-24 hours\") GROUP BY process_stage'); print('\n'.join([f'{row[0]}: {row[1]}' for row in cursor.fetchall()]))"
   ```

4. **Verify File Integrity**:
   - Check for missing original files
   - Verify transcript files exist for completed transcriptions
   - Ensure translations are being completed for all languages

## Monitoring Best Practices

1. **Regular Status Checks**: Check status at least daily
2. **Automated Monitoring**: Keep `monitor_and_restart.py` running for long processes
3. **Error Review**: Regularly review error logs to catch patterns
4. **Database Backups**: Make regular backups of the database file
5. **Batch Size Management**: Adjust batch size based on API limits and system capacity
6. **Verify Completed Files**: Periodically check that completed files have all necessary outputs