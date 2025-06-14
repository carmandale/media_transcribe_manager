# Scripts Directory

This directory contains executable scripts for various Scribe operations. All scripts should be run using `uv run python` from the project root.

## Script Categories

### Main Processing Scripts
- **media_processor.py**: Primary entry point for media processing
  - Handles single files or directories
  - Supports various processing modes (transcribe-only, translate-only)
  - Use `--help` for all options

- **run_full_pipeline.py**: Automated pipeline execution
  - Runs transcription and translation in sequence
  - Handles retries and error recovery
  - Best for batch processing

### Parallel Processing Scripts
- **parallel_transcription.py**: High-speed parallel transcription
  - Default: 5 workers, adjust with `--workers N`
  - Processes pending files automatically
  
- **parallel_translation.py**: Parallel translation processing
  - Specify language: `--language en|de|he`
  - Adjust workers: `--workers N`

- **run_parallel_processing.py**: Combined parallel processing
  - Runs both transcription and translation in parallel
  - Specify workers for each: `--transcription-workers N --translation-workers N`

### Single File Operations
- **transcribe_single_file.py**: Process one specific file
  - Use: `-f /path/to/file.mp3`
  - Useful for testing or priority files

### Database and Query Scripts
- **db_query.py**: Direct database queries
  - Use `--format table` for readable output
  - Supports any SQL query
  - Connection pooling built-in

- **verify_setup.py**: Verify project setup
  - Checks dependencies, API keys, database
  - Run this first when troubleshooting

### Translation Management
- **process_missing_translations.py**: Fill in missing translations
  - Specify languages: `--languages en,de,he`
  - Batch processing: `--batch-size N`

- **process_translations.py**: General translation processing
- **retry_failed_transcriptions.py**: Retry failed transcription attempts

### Quality and Evaluation
- **historical_evaluate_quality.py**: Evaluate translation quality
  - For interview content accuracy
  - Generates quality scores

- **batch_evaluate_quality.py**: Batch quality evaluation

### Utility Scripts
- **generate_report.py**: Generate processing reports
  - Use `--summary` for overview
  - Outputs detailed statistics

- **debug_transcription.py**: Debug specific transcription issues
  - Use `--file-id FILE_ID`

## Standard Import Pattern

All scripts MUST include this import setup:

```python
import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

# Now import from core_modules
from core_modules.module_name import ClassName
```

## Running Scripts

Always use UV from the project root:
```bash
cd /path/to/scribe
uv run python scripts/script_name.py [options]
```

## Common Patterns

### Processing New Files
```bash
# Single file
uv run python scripts/transcribe_single_file.py -f /path/to/file.mp3

# Directory of files
uv run python scripts/media_processor.py -d /path/to/media/

# Parallel processing (fastest)
uv run python scripts/run_parallel_processing.py --transcription-workers 10
```

### Checking Status
```bash
# Quick status
uv run python scripts/db_query.py --format table "SELECT COUNT(*) FROM processing_status"

# Detailed status
uv run python scripts/generate_report.py --summary
```

### Handling Errors
```bash
# Find stuck files
uv run python scripts/db_query.py "SELECT * FROM processing_status WHERE status = 'in-progress'"

# Retry failed files
uv run python scripts/retry_failed_transcriptions.py
```

## Script Development Guidelines

1. **Always include proper imports** - Use the standard pattern above
2. **Add comprehensive help** - Use argparse with detailed descriptions
3. **Handle errors gracefully** - Log errors, don't crash
4. **Use core_modules** - Don't duplicate functionality
5. **Test with --dry-run** - Add dry-run mode for safety
6. **Log appropriately** - Use the logging module

## Troubleshooting Scripts

If a script fails with import errors:
1. Check it includes the standard import pattern
2. Run from project root with `uv run python`
3. Verify with `scripts/verify_setup.py`

For database errors:
1. Check if another process is running
2. Use db_query.py to inspect state
3. Never access the .db file directly