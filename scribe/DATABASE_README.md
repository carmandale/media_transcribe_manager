# Consolidated Database Module

## Overview

The `scribe.database` module provides a clean, thread-safe interface for tracking media files and their processing status. It combines the best features from the legacy database modules into a single, modern implementation.

## Key Features

- **Thread-safe**: Each thread gets its own database connection
- **Connection pooling**: Efficient connection reuse
- **Transaction support**: Context manager for atomic operations
- **Type hints**: Full type annotations for better IDE support
- **Simple API**: Clean, intuitive methods for common operations

## Basic Usage

```python
from scribe.database import Database

# Initialize database
db = Database("media_tracking.db")

# Add a file
file_id = db.add_file(
    file_path="/path/to/audio.mp3",
    safe_filename="audio_001.mp3",
    media_type="audio",
    duration=300.5
)

# Update status
db.update_status(file_id, status='in-progress')
db.update_status(file_id, transcription_status='completed')

# Query files
pending = db.get_pending_files('translation_en', limit=10)
stuck = db.get_stuck_files(timeout_minutes=30)

# Get summary
summary = db.get_summary()
```

## Database Schema

### Tables

1. **media_files**: Stores file metadata
   - `file_id` (PRIMARY KEY): UUID for the file
   - `original_path`: Full path to original file
   - `safe_filename`: Sanitized filename
   - `file_size`, `duration`, `checksum`: File metadata
   - `media_type`: 'audio' or 'video'
   - `detected_language`: ISO language code

2. **processing_status**: Tracks processing state
   - `file_id` (FOREIGN KEY): Links to media_files
   - `status`: Overall status (pending/in-progress/completed/failed)
   - `transcription_status`: Transcription state
   - `translation_[en|de|he]_status`: Translation states
   - `started_at`, `completed_at`, `last_updated`: Timestamps
   - `attempts`: Retry counter

3. **errors**: Error logging
   - `error_id`: Auto-incrementing ID
   - `file_id`: File that had the error
   - `process_stage`: Where error occurred
   - `error_message`, `error_details`: Error information
   - `timestamp`: When error occurred

## API Reference

### File Management

- `add_file(file_path, safe_filename, media_type, **metadata)` → file_id
- `get_file_by_path(file_path)` → file record or None
- `get_file_by_id(file_id)` → file record or None

### Status Management

- `get_status(file_id)` → full status record
- `update_status(file_id, status=None, **stage_statuses)` → success bool
- `increment_attempts(file_id)` → success bool

### Queries

- `get_pending_files(stage, limit=None)` → list of files
- `get_files_by_status(status, limit=None)` → list of files
- `get_stuck_files(timeout_minutes=30)` → list of stuck files

### Error Handling

- `log_error(file_id, process_stage, error_message, error_details=None)` → success bool
- `get_errors(file_id=None)` → list of errors

### Statistics

- `get_summary()` → dict with counts and statistics

## Thread Safety

The module is fully thread-safe. Each thread automatically gets its own database connection:

```python
import threading
from scribe.database import Database

def worker(db, file_id):
    # Each thread can safely use the same Database instance
    db.update_status(file_id, transcription_status='in-progress')
    # ... do work ...
    db.update_status(file_id, transcription_status='completed')

# Single database instance
db = Database()

# Multiple threads can use it safely
threads = []
for file_id in file_ids:
    t = threading.Thread(target=worker, args=(db, file_id))
    threads.append(t)
    t.start()
```

## Transactions

Use the transaction context manager for atomic operations:

```python
with db.transaction() as conn:
    # Multiple operations that must succeed together
    conn.execute("INSERT INTO media_files ...")
    conn.execute("UPDATE processing_status ...")
    # Automatically committed on success, rolled back on error
```

## Migration from Legacy Code

If migrating from the old `db_manager.py`:

```python
# Old way
from core_modules.db_manager import DatabaseManager
db = DatabaseManager("media_tracking.db")
db.add_media_file(...)

# New way
from scribe.database import Database
db = Database("media_tracking.db")
db.add_file(...)
```

Key differences:
- Simpler method names (`add_file` vs `add_media_file`)
- Returns actual dict objects instead of Row objects
- No need to manage connections manually
- Automatic thread safety