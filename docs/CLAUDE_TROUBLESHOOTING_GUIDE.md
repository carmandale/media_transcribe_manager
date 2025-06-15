# Claude Troubleshooting Guide

This guide helps Claude (and other AI assistants) quickly get up to speed and avoid common issues when working with the Scribe project.

## Quick Orientation Checklist

When starting a session, Claude should:

1. **Check the current state**:
   ```bash
   # Check git status and branch
   git status
   git branch --show-current
   
   # Check recent commits
   git log --oneline -10
   
   # Verify setup
   uv run python scripts/verify_setup.py
   ```

2. **Read key documentation**:
   - `/CLAUDE.md` - Project-specific instructions
   - `/docs/SETUP_AND_USAGE.md` - Setup guide
   - Recent handoff documents in `/docs/`

3. **Check for in-progress work**:
   ```bash
   # Check processing status
   uv run python core_modules/scribe_manager.py status
   
   # Look for stuck files
   uv run python scripts/db_query.py --format table "SELECT COUNT(*) as count, status FROM processing_status GROUP BY status"
   ```

## Common Issues and Solutions

### 1. Import Errors
**Problem**: `ModuleNotFoundError: No module named 'core_modules'`

**Solution**: All scripts must add project root to Python path:
```python
import sys
from pathlib import Path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))
```

### 2. Database Query Errors
**Problem**: `no such column` or `no such table`

**Solution**: Check the actual schema:
```bash
# List all tables
sqlite3 media_tracking.db ".tables"

# Show table schema
sqlite3 media_tracking.db ".schema TABLE_NAME"

# Use db_query.py for safe queries
uv run python scripts/db_query.py --format table "SELECT * FROM TABLE_NAME LIMIT 5"
```

### 3. Translation Provider Issues
**Problem**: Hebrew/other translations failing or showing wrong language

**Solution**: 
- Check provider configuration in translation.py
- Verify API keys are set correctly
- Hebrew requires Microsoft or OpenAI (not DeepL)
- Always check logs for provider selection

### 4. File Path Issues
**Problem**: Commands fail with "file not found" errors

**Solution**:
- Always use absolute paths
- Quote paths with spaces: `"/path with spaces/file.mp3"`
- Use pathlib.Path for Python scripts
- Check file exists before processing

### 5. Command Syntax Confusion
**Problem**: Wrong arguments for scripts

**Solution**: Always check help first:
```bash
uv run python scripts/script_name.py --help
```

Common patterns:
- `media_processor.py -f /path/to/file.mp3` (not --file-id)
- `parallel_translation.py --language he` (not --lang)
- `historical_evaluate_quality.py --file-id FILE_ID` (not -f)

## Best Practices for Claude

### 1. Always Test First
- Run commands on single files before batch processing
- Check output/logs before proceeding
- Verify changes with `git diff`

### 2. Use Built-in Tools
- Prefer `scribe_manager.py` commands over individual scripts
- Use `db_query.py` instead of direct SQLite access
- Let Task tool handle complex searches

### 3. Check Documentation
- Read error messages completely
- Check if issue is already documented
- Look for recent fixes in git history

### 4. Parallel Processing
When possible, run multiple operations concurrently:
```bash
# Good - runs in parallel
uv run python scripts/run_parallel_processing.py --transcription-workers 10 --translation-workers 8

# Less efficient - sequential
uv run python scripts/media_processor.py -d /path/to/files/
```

### 5. State Management
- Use TodoWrite/TodoRead tools consistently
- Document what was changed and why
- Leave clear notes for next session

## Environment Variables Reference

Critical environment variables:
```bash
# Translation APIs
DEEPL_API_KEY=xxx          # For English/German
OPENAI_API_KEY=xxx         # For Hebrew/quality evaluation  
MS_TRANSLATOR_KEY=xxx      # For Hebrew (alternative)
MS_TRANSLATOR_LOCATION=global

# Transcription
ELEVENLABS_API_KEY=xxx     # For audio transcription

# Optional
ANTHROPIC_API_KEY=xxx      # For quality evaluation
```

## Quick Status Commands

```bash
# Overall system status
uv run python core_modules/scribe_manager.py status --detailed

# Translation progress by language
uv run python scripts/db_query.py --format table "
SELECT 
    SUM(CASE WHEN translation_en_status = 'completed' THEN 1 ELSE 0 END) as English,
    SUM(CASE WHEN translation_de_status = 'completed' THEN 1 ELSE 0 END) as German,
    SUM(CASE WHEN translation_he_status = 'completed' THEN 1 ELSE 0 END) as Hebrew,
    COUNT(*) as Total
FROM processing_status"

# Find problematic files
uv run python scripts/db_query.py "
SELECT file_id, status, last_updated 
FROM processing_status 
WHERE status = 'in-progress' 
AND last_updated < datetime('now', '-30 minutes')"
```

## Getting Help

1. Check existing documentation first
2. Look for similar issues in git history
3. Test with a single file before batch operations
4. When stuck, provide:
   - Exact command run
   - Full error message
   - Current working directory
   - Relevant log entries