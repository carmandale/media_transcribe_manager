# Maintenance Directory

This directory contains scripts for monitoring, maintaining, and troubleshooting the Scribe system. These scripts are critical for keeping the pipeline running smoothly.

## Key Maintenance Scripts

### Monitoring Scripts
- **monitor_and_restart.py**: Automated pipeline monitoring
  - Continuously monitors for stuck processes
  - Automatically restarts stalled files
  - Use: `--check-interval 10` (seconds between checks)
  - Runs indefinitely until stopped

- **check_status.py**: Quick status overview
  - Shows recent file updates
  - Counts in-progress translations
  - Checks for stalled processes

### File Recovery Scripts
- **check_stuck_files.py**: Find and fix stuck files
  - Identifies files stuck in "in-progress" state
  - Use `--reset` to reset stuck files to pending
  - Critical for recovering from crashes

- **find_all_missing_transcripts.py**: Locate files without transcripts
  - Finds database entries with missing transcript files
  - Helps identify incomplete processing

- **check_transcript_file.py**: Verify specific transcript
  - Takes a file_id as argument
  - Checks both database and filesystem

### Database Maintenance
- **fix_path_issues.py**: Resolve file path problems
  - Handles unicode normalization
  - Fixes path encoding issues
  - Updates database with corrected paths

- **verify_file_paths.py**: Validate all file paths
  - Checks if files exist on disk
  - Reports missing or moved files

## Standard Import Pattern

Like all Scribe scripts, maintenance scripts should use:

```python
import sys
from pathlib import Path

# Add core_modules to path
sys.path.append(str(Path(__file__).parent.parent / 'core_modules'))

# Import modules
from db_manager import DatabaseManager
```

Note: Some older maintenance scripts may use direct imports without the `core_modules` prefix.

## Common Maintenance Tasks

### Daily Monitoring
```bash
# Start continuous monitoring
uv run python maintenance/monitor_and_restart.py --check-interval 10

# Quick status check
uv run python maintenance/check_status.py
```

### Handling Stuck Files
```bash
# Find stuck files
uv run python maintenance/check_stuck_files.py

# Reset stuck files
uv run python maintenance/check_stuck_files.py --reset
```

### Database Health
```bash
# Verify all file paths
uv run python maintenance/verify_file_paths.py

# Fix path encoding issues
uv run python maintenance/fix_path_issues.py
```

## Monitoring Best Practices

1. **Run monitor_and_restart.py continuously** during batch processing
2. **Check status regularly** with check_status.py
3. **Reset stuck files promptly** to maintain throughput
4. **Verify paths** after moving files or directories

## Troubleshooting Guide

### Files Stuck in "in-progress"
1. Run `check_stuck_files.py` to identify them
2. Check if processing is actually running: `ps -ef | grep python`
3. Use `--reset` flag to reset to pending
4. Monitor logs for error patterns

### Missing Transcripts
1. Run `find_all_missing_transcripts.py`
2. Check output directory permissions
3. Verify disk space availability
4. Re-run transcription for affected files

### Database Locked Errors
1. Stop all running processes
2. Wait a moment for locks to clear
3. Use monitor_and_restart.py instead of multiple scripts

## Integration with Pipeline

These maintenance scripts work alongside the main pipeline:
- **monitor_and_restart.py** keeps pipeline running
- **check_stuck_files.py** recovers from failures
- Status scripts provide visibility

Always run monitoring when processing large batches to ensure reliability.

## Script Execution Pattern

All maintenance scripts follow this pattern:
1. Connect to database
2. Query for problematic states
3. Report findings
4. Optionally fix issues (with flags)
5. Log all actions

This ensures consistency and traceability across maintenance operations.