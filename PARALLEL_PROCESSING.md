# Parallel Processing System

This document explains how to use the parallel processing system for transcription and translation.

## Overview

The parallel processing system significantly increases throughput by:

1. Processing multiple files simultaneously in worker threads
2. Using a thread pool to manage concurrent operations
3. Implementing thread-safe database access
4. Providing monitoring and automatic restart capabilities

## Components

The system consists of the following components:

- `parallel_transcription.py`: Transcribe multiple files in parallel
- `parallel_translation.py`: Translate transcripts to multiple languages in parallel
- `monitor_and_restart.py`: Continuously monitor and restart processes as needed
- `fix_stalled_files.py`: Fix database inconsistencies and stalled files

## Usage

### Parallel Transcription

```bash
python parallel_transcription.py --workers 5 --batch-size 10
```

Options:
- `--workers`: Number of concurrent workers (default: 5)
- `--batch-size`: Number of files to process in a batch (default: all pending files)

### Parallel Translation

```bash
python parallel_translation.py --language en --workers 5 --batch-size 10
```

Required options:
- `--language`: Target language code (en, de, he)

Additional options:
- `--workers`: Number of concurrent workers (default: 5)
- `--batch-size`: Number of files to process in a batch (default: all pending files)

### Monitoring and Auto-Restart

The `monitor_and_restart.py` script continuously checks for files that need processing and automatically starts the appropriate processes:

```bash
python monitor_and_restart.py --check-interval 60 --batch-size 10
```

Options:
- `--check-interval`: Seconds between status checks (default: 60)
- `--batch-size`: Batch size for processing (default: 5)
- `--languages`: Comma-separated list of languages to monitor (default: en,de,he)

This script will:
1. Check for files that need transcription
2. Start transcription process if needed
3. Check for files that need translation for each language
4. Start translation processes for each language as needed
5. Continue monitoring until all files are processed

### Fixing Stalled Files

If you encounter database inconsistencies or files stuck in certain statuses, use the fix script:

```bash
python fix_stalled_files.py
```

This script will:
1. Find files marked as 'in-progress' for transcription but with no transcript file, and mark them as 'failed'
2. Find files with translation 'in-progress' but no translation file, and mark them as 'failed'
3. Find files with transcripts or translations that exist on disk but are not marked as 'completed' in the database

## Performance Considerations

- **Worker Count**: Start with 5 workers and adjust based on your system's CPU and memory resources. More workers increase throughput but also increase resource usage.
- **Batch Size**: A batch size of 5-10 is generally a good balance between performance and resource usage.
- **API Rate Limits**: Be aware of the rate limits for ElevenLabs, DeepL, and OpenAI APIs. Adjust worker count and batch size accordingly.
- **Memory Usage**: Monitor memory usage when processing large batches. If you encounter memory issues, reduce the batch size.

## Troubleshooting

### "Recursive use of cursors not allowed"

This error is related to SQLite concurrent access and is handled by the database manager with thread-specific connections. However, if you see this error repeatedly:

1. Ensure the fix in `db_manager.py` regarding thread-specific connections is present
2. Restart the process with a smaller number of workers
3. If the error persists, run `python fix_stalled_files.py` to resolve any database inconsistencies

### "No files found for translation"

This usually means one of the following:

1. All files that need translation have already been processed
2. Files that need translation don't have completed transcriptions
3. The database status doesn't match the actual file state

Run `python fix_stalled_files.py` to address these issues.

### Monitor Shows No Progress

If the monitoring script is running but shows no progress:

1. Check the status of running processes with `ps -ef | grep python`
2. Look at the log files: `parallel_transcription.log`, `en_translation.log`, etc.
3. Check database status with `sqlite3 media_tracking.db "SELECT status, COUNT(*) FROM processing_status GROUP BY status"`
4. If processes are stuck, kill them and let the monitor restart them

## Workflow for Processing All Files

1. Fix any stalled files: `python fix_stalled_files.py`
2. Start the monitor: `python monitor_and_restart.py --check-interval 30 --batch-size 10`
3. Monitor will automatically process all files, starting with transcription and then proceeding to translations
4. Periodically check progress: `sqlite3 media_tracking.db "SELECT transcription_status, COUNT(*) FROM processing_status GROUP BY transcription_status"`