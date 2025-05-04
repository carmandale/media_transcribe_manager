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
- Reset stuck processes: `python check_stuck_files.py`
- Start automated monitoring: `python monitor_and_restart.py --check-interval 10`
- Start monitoring with custom settings: `python monitor_and_restart.py --check-interval 10 --batch-size 20 --languages en,de,he`

## Status Check Commands
- Check Hebrew translations: `python -c "from db_manager import DatabaseManager; db = DatabaseManager('media_tracking.db'); query='SELECT COUNT(*) as count FROM processing_status WHERE translation_he_status = \"completed\"'; result = db.execute_query(query)[0]['count']; print(f'Hebrew translations completed: {result}')"`
- Check English translations: `python -c "from db_manager import DatabaseManager; db = DatabaseManager('media_tracking.db'); query='SELECT COUNT(*) as count FROM processing_status WHERE translation_en_status = \"completed\"'; result = db.execute_query(query)[0]['count']; print(f'English translations completed: {result}')"`
- Check German translations: `python -c "from db_manager import DatabaseManager; db = DatabaseManager('media_tracking.db'); query='SELECT COUNT(*) as count FROM processing_status WHERE translation_de_status = \"completed\"'; result = db.execute_query(query)[0]['count']; print(f'German translations completed: {result}')"`

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