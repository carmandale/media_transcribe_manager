# Scribe Manager Usage Guide

This document provides instructions for using the refactored Scribe Manager tool to manage the entire media processing pipeline.

## Overview

The Scribe Manager is a unified command-line tool that consolidates all pipeline operations into a single interface. It replaces multiple small scripts with a more organized and consistent approach.

## Installation

No additional installation is required. The Scribe Manager uses the same dependencies as the original scripts.

## Basic Usage

```bash
python scribe_manager.py [command] [options]
```

## Common Commands

### Check Status

View the current status of the processing pipeline:

```bash
# Basic status check
python scribe_manager.py status

# Get detailed status
python scribe_manager.py status --detailed

# Get status in markdown format
python scribe_manager.py status --format markdown

# Get status in JSON format
python scribe_manager.py status --format json
```

### Start Monitoring

Start continuous monitoring of the pipeline:

```bash
# Start monitoring with default settings
python scribe_manager.py monitor

# Set custom check interval and restart interval
python scribe_manager.py monitor --check-interval 30 --restart-interval 300

# Monitor without auto-restart
python scribe_manager.py monitor --no-auto-restart
```

### Start Processing

Start processing operations:

```bash
# Start transcription
python scribe_manager.py start --transcription --transcription-workers 10

# Start translation for specific languages
python scribe_manager.py start --translation en,de,he --translation-workers 8

# Start both with custom batch size
python scribe_manager.py start --transcription --translation en,de,he --batch-size 20
```

### Restart Stalled Processes

Reset and restart processes that have stalled:

```bash
# Restart stalled processes with default timeout
python scribe_manager.py restart

# Custom timeout threshold
python scribe_manager.py restart --timeout 60
```

### Fix Database Issues

Fix various issues with the database:

```bash
# Reset stalled files
python scribe_manager.py fix stalled

# Fix path issues
python scribe_manager.py fix paths

# Fix missing transcripts
python scribe_manager.py fix transcripts

# Mark problematic files
python scribe_manager.py fix mark --file-ids "file1,file2" --status qa_failed --reason "Corrupt audio"

# Fix Hebrew translations with placeholder text
python scribe_manager.py fix hebrew --batch-size 10
```

### Verify Database Consistency

Check database consistency against filesystem:

```bash
# Report consistency issues
python scribe_manager.py verify

# Auto-fix inconsistencies
python scribe_manager.py verify --auto-fix
```

### Handle Problematic Files

Special handling for problematic files:

```bash
# Retry problematic files
python scribe_manager.py retry

# Apply special case processing
python scribe_manager.py special
```

## Command Structure

The Scribe Manager is organized around these main command groups:

- **status**: View pipeline progress and statistics
- **monitor**: Run continuous monitoring and automatic recovery
- **restart**: Reset and restart stalled processes
- **start**: Start transcription and translation processing
- **fix**: Fix various database and file issues
- **verify**: Check database consistency
- **retry**: Retry failed files with extended timeouts
- **special**: Apply special case processing for difficult files

## Configuration

You can provide a configuration file to customize behavior:

```bash
python scribe_manager.py --config config.json [command] [options]
```

Example configuration file (`config.json`):

```json
{
  "output_directory": "./output",
  "transcription_workers": 10,
  "translation_workers": 8,
  "batch_size": 20,
  "check_interval": 60,
  "restart_interval": 600,
  "stalled_timeout_minutes": 30
}
```

## Migration from Previous Scripts

The following table shows how to migrate from previous scripts to the new Scribe Manager:

| Old Command | New Command |
|-------------|-------------|
| `python check_status.py` | `python scribe_manager.py status` |
| `python monitor_and_restart.py` | `python scribe_manager.py monitor` |
| `python check_stuck_files.py --reset` | `python scribe_manager.py fix stalled` |
| `python fix_path_issues.py` | `python scribe_manager.py fix paths` |
| `python fix_missing_transcripts.py` | `python scribe_manager.py fix transcripts` |
| `python fix_hebrew_translations.py` | `python scribe_manager.py fix hebrew` |
| `python run_parallel_processing.py` | `python scribe_manager.py start --transcription --translation en,de,he` |
| `python transcribe_problematic_files.py` | `python scribe_manager.py retry` |

## Examples

### Complete Pipeline with Monitoring

To start a complete pipeline with transcription, translation, and monitoring:

```bash
# Start transcription and translation for all languages
python scribe_manager.py start --transcription --translation en,de,he --transcription-workers 10 --translation-workers 8

# Start monitoring in a separate terminal
python scribe_manager.py monitor --check-interval 30
```

### Fixing Database Issues

To clean up the database and ensure consistency:

```bash
# Reset stalled processes
python scribe_manager.py fix stalled --reset-all

# Fix path issues
python scribe_manager.py fix paths

# Verify consistency and auto-fix issues
python scribe_manager.py verify --auto-fix
```

### Weekly Maintenance Routine

For regular maintenance, you might run:

```bash
# Check status
python scribe_manager.py status --detailed

# Fix stalled files
python scribe_manager.py fix stalled

# Verify consistency
python scribe_manager.py verify

# Retry any problem files
python scribe_manager.py retry
```

## Troubleshooting

If you encounter issues:

1. Check the logs in `scribe_manager.log`
2. Verify database consistency with `python scribe_manager.py verify`
3. Try running with `--log-level DEBUG` for more verbose output

For persistent issues, try resetting stalled processes and restarting:

```bash
python scribe_manager.py fix stalled --reset-all
python scribe_manager.py start --transcription --translation en,de,he
```