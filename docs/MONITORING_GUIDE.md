# Translation Pipeline Monitoring Guide

This document provides instructions for monitoring and maintaining the translation pipeline.

## Overview

The translation pipeline processes hundreds of audio/video files through multiple stages:
1. Transcription
2. Translation (English, German, Hebrew)
3. Quality evaluation
4. Reporting

During processing, some translations may stall in the 'in-progress' state. This guide explains how to monitor and recover from such issues.

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

## Troubleshooting Stalled Translations

If translations appear to be stalled:

1. **Check Status**: Run `python check_status.py` to verify the status
   - Look at "Last database update" - if >30 minutes, translations are stalled
   - Check how many translations are still in progress

2. **Reset Stuck Processes**: Run `python check_stuck_files.py` to reset any stuck processes

3. **Restart Pipeline**: Run `python run_full_pipeline.py --batch-size 10 --languages en,de,he` to restart processing

4. **Start Monitoring**: For continued monitoring, use `python monitor_and_restart.py`

## Common Issues and Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Stalled translations | No database updates for >30 minutes | Run `check_stuck_files.py` and restart pipeline |
| Process crashes | No Python processes running | Restart pipeline with `run_full_pipeline.py` |
| Database errors | SQLite errors in logs | Check database file permissions and integrity |
| API rate limiting | Many API errors in error log | Reduce batch size, increase sleep between calls |
| Quality failure pattern | Many files failing quality checks | Review quality evaluation criteria |

## Monitoring Best Practices

1. **Regular Status Checks**: Check status at least daily
2. **Automated Monitoring**: Keep `monitor_and_restart.py` running for long processes
3. **Error Review**: Regularly review error logs to catch patterns
4. **Database Backups**: Make regular backups of the database file
5. **Batch Size Management**: Adjust batch size based on API limits and system capacity