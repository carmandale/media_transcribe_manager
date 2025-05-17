# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run: `python scripts/media_processor.py [options]`
- Transcribe single file: `python scripts/transcribe_single_file.py -f [file_path]`
- Generate report: `python scripts/generate_report.py --summary`
- Process translations: `python scripts/process_missing_translations.py --languages en,de,he --batch-size 20 --db-path media_tracking.db`
- Evaluate historical accuracy: `python scripts/historical_evaluate_quality.py --language en --limit 20`
- Unified interface: `python core_modules/scribe_manager.py [command] [options]`
- Fix Hebrew translations: `python core_modules/scribe_manager.py fix hebrew --batch-size 20 --db-path media_tracking.db`
- Run full pipeline: `python scripts/run_full_pipeline.py --batch-size 20 --languages en,de,he`
- Run test: `python scripts/media_processor.py -d [test_directory] --test`

## Parallel Processing Commands
- Run parallel processing (all languages): `python scripts/run_parallel_processing.py --transcription-workers 10 --translation-workers 8`
- Run parallel processing (specific languages): `python scripts/run_parallel_processing.py --languages en,de --transcription-workers 10 --translation-workers 8`
- Run parallel transcription only: `python scripts/parallel_transcription.py --workers 10 --batch-size 20`
- Run parallel translation (English): `python scripts/parallel_translation.py --language en --workers 8 --batch-size 20`
- Run parallel translation (German): `python scripts/parallel_translation.py --language de --workers 8 --batch-size 20`
- Run parallel translation (Hebrew): `python scripts/parallel_translation.py --language he --workers 8 --batch-size 20`
- For full documentation: See docs/PARALLEL_PROCESSING.md

## Monitoring Commands
### Unified Interface (Recommended)
- Check status: `python core_modules/scribe_manager.py status [--detailed]`
- Reset stuck processes: `python core_modules/scribe_manager.py fix stalled [--reset-all]`
- Start automated monitoring: `python core_modules/scribe_manager.py monitor [--check-interval 10]`
- Start monitoring with custom settings: `python core_modules/scribe_manager.py monitor --check-interval 10 --restart-interval 600`
- Fix files with missing transcripts: `python core_modules/scribe_manager.py fix transcripts`
- Verify database consistency: `python core_modules/scribe_manager.py verify [--auto-fix]`
- Check if monitoring is running: `ps -ef | grep scribe_manager.py | grep monitor | grep -v grep`

### Maintenance Scripts
- Check status: `python maintenance/check_status.py`
- Reset stuck processes: `python maintenance/check_stuck_files.py --reset`
- Start automated monitoring: `python maintenance/monitor_and_restart.py --check-interval 10`
- Start monitoring with custom settings: `python maintenance/monitor_and_restart.py --check-interval 10 --batch-size 20 --languages en,de,he`
- Check transcript for a specific file: `python maintenance/check_transcript_file.py <file_id>`
- Find all files with missing transcripts: `python maintenance/find_all_missing_transcripts.py`
- Debug transcription issues: `python scripts/debug_transcription.py --file-id <file_id>`
- Check if monitoring is running: `ps -ef | grep monitor_and_restart.py | grep -v grep`
- Check if pipeline is running: `ps -ef | grep run_full_pipeline.py | grep -v grep`

## Database Query Commands
### Recommended Method (Connection Pooling)
- Use the database query utility: `python scripts/db_query.py "SQL QUERY"`
- Show results in table format: `python scripts/db_query.py --format table "SELECT * FROM processing_status LIMIT 5"`
- Get completion summary: `python scripts/db_query.py --format table "SELECT SUM(CASE WHEN translation_en_status = 'completed' THEN 1 ELSE 0 END) as en_done, SUM(CASE WHEN translation_de_status = 'completed' THEN 1 ELSE 0 END) as de_done, SUM(CASE WHEN translation_he_status = 'completed' THEN 1 ELSE 0 END) as he_done, COUNT(*) as total FROM processing_status"`

### Common Status Queries
- Check Hebrew translations: `python scripts/db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_he_status = 'completed'"`
- Check English translations: `python scripts/db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_en_status = 'completed'"`
- Check German translations: `python scripts/db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_de_status = 'completed'"`
- Check transcription progress: `python scripts/db_query.py "SELECT transcription_status, COUNT(*) as count FROM processing_status GROUP BY transcription_status"`
- Find stuck files: `python scripts/db_query.py "SELECT * FROM processing_status WHERE status = 'in-progress' AND last_updated < strftime('%s', 'now') - 1800"` 

See docs/DB_QUERIES.md for a comprehensive list of useful queries

## Quality Evaluation
- For interview transcripts, use historical accuracy evaluation via `historical_evaluate_quality.py`
- Prioritize content accuracy and speech pattern preservation
- Quality thresholds: Excellent (8.5-10), Acceptable (8.0-8.4), Needs Improvement (<8.0)
- See docs/QUALITY_EVALUATION_GUIDE.md for detailed guidelines

## Code Style
- Use Python 3.6+ features
- Imports: standard library first, third-party next, local modules last
- Type hints: Use typing module for function parameters and return values
- Documentation: Use docstrings in Google format
- Error handling: Use try/except blocks with specific error types
- Naming: snake_case for variables/functions, PascalCase for classes
- Log errors with the logging module at appropriate levels

## Path Handling (CRITICAL)
- ALWAYS use pathlib.Path for path manipulation (never string concatenation)
- ALWAYS use proper quoting for paths in shell commands
- ALWAYS use subprocess.run with command args as list (not shell=True) for external processes
- Use raw strings (r"path/with/spaces") when writing path literals
- Implement unicode normalization for paths with special characters 
- Verify paths exist before operations
- Never assume directory structure - check existence and create directories as needed
- When using Bash with spaces in paths:
  - ALWAYS quote paths with double quotes in commands: `cd "/path with spaces"`
  - ALWAYS use `cd "/path with spaces"` before executing other commands that use relative paths
  - Use absolute paths whenever possible
  - For file operations, prefer Python's pathlib.Path or os functions over Bash commands
  - Test file operations on a single example before attempting batch operations

## Project Structure
### Core Modules
- **media_processor.py**: Main entry point for processing media files
- **db_connection_pool.py**: Thread-safe connection pooling for SQLite
- **db_manager.py**: Database access layer with connection pooling
- **db_maintenance.py**: Database maintenance and repair operations
- **file_manager.py**: File path and metadata management
- **transcription.py**: Audio transcription services
- **translation.py**: Text translation between languages
- **pipeline_manager.py**: Pipeline monitoring and orchestration
- **scribe_manager.py**: Unified command-line interface

### Helper Modules
- **worker_pool.py**: Parallel processing framework
- **reporter.py**: Report generation utilities

### Legacy Scripts
- Most legacy scripts are now aliases to `scribe_manager.py` commands
- All legacy functionality is maintained through backward compatibility
- See `docs/MIGRATION_GUIDE.md` for mapping between old and new commands

All scripts honor command-line arguments documented in README.md