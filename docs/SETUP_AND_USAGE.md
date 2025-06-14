# Scribe Setup and Usage Guide

This guide provides clear instructions for setting up and using the Scribe media processing system.

## Quick Start

1. **Ensure you have UV installed** (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the repository and navigate to it**:
   ```bash
   cd /path/to/scribe
   ```

3. **Install dependencies** (UV will automatically create a virtual environment):
   ```bash
   uv pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root with your API keys:
   ```
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   DEEPL_API_KEY=your_deepl_api_key_here  # Optional
   MS_TRANSLATOR_KEY=your_ms_key_here     # Optional
   ```

5. **Verify setup**:
   ```bash
   uv run python scripts/verify_setup.py
   ```

## Understanding the Import System

The Scribe project uses a specific import pattern due to its module structure. Scripts need to add the project root to Python's path before importing from `core_modules`.

### Standard Import Pattern

All scripts in the `scripts/` directory should use this pattern:

```python
import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

# Now import from core_modules
from core_modules.db_manager import DatabaseManager
from core_modules.file_manager import FileManager
```

## Common Commands

### Check System Status
```bash
# View database statistics
uv run python scripts/db_query.py --format table "SELECT COUNT(*) as total FROM processing_status"

# Check translation progress
uv run python scripts/db_query.py --format table "SELECT 
    SUM(CASE WHEN translation_en_status = 'completed' THEN 1 ELSE 0 END) as en_done,
    SUM(CASE WHEN translation_de_status = 'completed' THEN 1 ELSE 0 END) as de_done,
    SUM(CASE WHEN translation_he_status = 'completed' THEN 1 ELSE 0 END) as he_done,
    COUNT(*) as total 
FROM processing_status"

# Check for stuck files
uv run python scripts/db_query.py "SELECT * FROM processing_status WHERE status = 'in-progress' AND last_updated < strftime('%s', 'now') - 1800"
```

### Process Media Files
```bash
# Process a single file
uv run python scripts/transcribe_single_file.py -f /path/to/file.mp3

# Run parallel transcription
uv run python scripts/parallel_transcription.py --workers 10 --batch-size 20

# Run parallel translation
uv run python scripts/parallel_translation.py --language en --workers 8

# Run full pipeline
uv run python scripts/run_full_pipeline.py --batch-size 20 --languages en,de,he
```

### Monitoring and Maintenance
```bash
# Monitor pipeline (runs continuously)
uv run python maintenance/monitor_and_restart.py --check-interval 10

# Check for stuck files
uv run python maintenance/check_stuck_files.py

# Reset stuck files
uv run python maintenance/check_stuck_files.py --reset
```

## Troubleshooting

### ModuleNotFoundError Issues

If you encounter `ModuleNotFoundError: No module named 'core_modules'` or similar:

1. **Always use `uv run`** to execute scripts - this ensures the virtual environment is active
2. **Run from the project root directory**
3. **Check that the script includes the proper import setup** (see "Standard Import Pattern" above)

### Database Issues

If the database is not found:
- The database (`media_tracking.db`) is created automatically on first use
- It should be located in the project root directory
- Check file permissions if you get access errors

### Path Issues with Spaces

The project handles paths with spaces, but when using Bash commands:
- Always quote paths: `cd "/path with spaces"`
- Use Python's pathlib.Path for file operations when possible

## Project Structure

```
scribe/
├── core_modules/         # Core functionality (db_manager, file_manager, etc.)
├── scripts/             # Executable scripts for various tasks
├── maintenance/         # Monitoring and maintenance scripts
├── docs/               # Documentation
├── output/             # Processed files (organized by file ID)
├── logs/               # Log files
└── media_tracking.db   # SQLite database tracking processing status
```

## Best Practices

1. **Always use UV**: Run all Python scripts with `uv run python` to ensure proper environment
2. **Work from project root**: Change to the scribe directory before running commands
3. **Check status first**: Use db_query.py to understand current state before processing
4. **Monitor long runs**: Use monitor_and_restart.py for batch processing
5. **Review logs**: Check the logs/ directory for detailed processing information

## Getting Help

- Check existing documentation in the `docs/` directory
- Review script help: `uv run python [script_name] --help`
- Check CLAUDE.md for command examples
- Review recent git commits for usage patterns