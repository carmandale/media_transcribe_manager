# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run: `python media_processor.py [options]`
- Transcribe single file: `python transcribe_single_file.py -f [file_path]`
- Generate report: `python generate_report.py --summary`
- Process translations: `python process_missing_translations.py --languages en,de,he --batch-size 20 --db-path media_tracking.db`
- Evaluate historical accuracy: `python historical_evaluate_quality.py --language en --limit 20`
- Fix Hebrew translations: `python fix_hebrew_translations.py --batch-size 20 --db-path media_tracking.db`
- Run full pipeline: `python run_full_pipeline.py --batch-size 20 --languages en,de,he`
- Run test: `python media_processor.py -d [test_directory] --test`

## Monitoring Commands
- Check status: `python check_status.py`
- Reset stuck processes: `python check_stuck_files.py --reset`
- Start automated monitoring: `python monitor_and_restart.py --check-interval 10`
- Start monitoring with custom settings: `python monitor_and_restart.py --check-interval 10 --batch-size 20 --languages en,de,he`
- Check transcript for a specific file: `python check_transcript_file.py <file_id>`
- Fix files with missing transcripts: `python fix_missing_transcripts.py --reset`
- Find all files with missing transcripts: `python find_all_missing_transcripts.py`
- Debug transcription issues: `python debug_transcription.py --file-id <file_id>`
- Check if monitoring is running: `ps -ef | grep monitor_and_restart.py | grep -v grep`
- Check if pipeline is running: `ps -ef | grep run_full_pipeline.py | grep -v grep`

## Database Query Commands
- Use the database query utility for all SQL queries: `python db_query.py "SQL QUERY"`
- Check Hebrew translations: `python db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_he_status = 'completed'"`
- Check English translations: `python db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_en_status = 'completed'"`
- Check German translations: `python db_query.py "SELECT COUNT(*) as count FROM processing_status WHERE translation_de_status = 'completed'"`
- Show results in table format: `python db_query.py --format table "SELECT * FROM processing_status LIMIT 5"`
- Get completion summary: `python db_query.py --format table "SELECT SUM(CASE WHEN translation_en_status = 'completed' THEN 1 ELSE 0 END) as en_done, SUM(CASE WHEN translation_de_status = 'completed' THEN 1 ELSE 0 END) as de_done, SUM(CASE WHEN translation_he_status = 'completed' THEN 1 ELSE 0 END) as he_done, COUNT(*) as total FROM processing_status"`
- See docs/DB_QUERIES.md for a comprehensive list of useful queries

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

## Project Structure
- Core modules: media_processor.py, db_manager.py, file_manager.py, transcription.py, translation.py
- Helper modules: worker_pool.py, reporter.py
- Evaluation tools: historical_evaluate_quality.py, process_missing_translations.py
- All scripts honor command-line arguments documented in README.md