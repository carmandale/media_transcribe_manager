# Troubleshooting Guide

Common issues and solutions for the Scribe system.

## Installation Issues

### "ModuleNotFoundError: No module named 'click'"
**Cause**: Using standard Python instead of uv environment  
**Solution**: Always use `uv run python` prefix:
```bash
# Wrong
python scribe_cli.py status

# Correct
uv run python scribe_cli.py status
```

### "uv: command not found"
**Cause**: uv package manager not installed  
**Solution**: Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Processing Issues

### Files Stuck in "in-progress"
**Cause**: Process interrupted or crashed  
**Solution**: Reset stuck files:
```bash
# View stuck files
uv run python scribe_cli.py fix-stuck

# Reset all stuck files
uv run python scribe_cli.py fix-stuck --reset-all
```

### "No pending files" but files exist
**Cause**: Files already processed or in wrong status  
**Solution**: Check database status:
```bash
# Check overall status
uv run python scribe_cli.py status --detailed

# Query database directly
sqlite3 media_tracking.db "SELECT file_id, translation_he_status FROM processing_status WHERE translation_he_status != 'completed' LIMIT 10;"
```

## Evaluation Issues

### Token Limit Errors
**Cause**: Transcripts too long for GPT-4 context window  
**Solution**: Use evaluate_hebrew.py script which automatically truncates:
```bash
uv run python evaluate_hebrew.py --limit 10
```

### Score of 0.0
**Cause**: API call failed but was recorded as successful  
**Solution**: Check for files with 0.0 scores and re-evaluate:
```bash
sqlite3 media_tracking.db "DELETE FROM quality_evaluations WHERE score = 0.0 AND language = 'he';"
```

### Inconsistent Scores
**Cause**: Different evaluation models or truncation  
**Solution**: Ensure consistent model usage and check if texts were truncated

## API Issues

### "OPENAI_API_KEY not set"
**Solution**: Add to .env file:
```bash
echo "OPENAI_API_KEY=your_key_here" >> .env
```

### Rate Limit Errors
**Cause**: Too many API calls  
**Solution**: Reduce batch size or add delays between calls

### "Invalid API key"
**Solution**: Verify API key is correct and has proper permissions

## Database Issues

### "database is locked"
**Cause**: Multiple processes accessing database  
**Solution**: Wait and retry, or use single process

### Missing Data
**Solution**: Check database integrity:
```bash
sqlite3 media_tracking.db "PRAGMA integrity_check;"
```

## File Path Issues

### "Transcript not found"
**Cause**: Different file naming conventions  
**Solution**: Check actual filenames:
```bash
ls output/[file_id]/
```

Files should be named:
- Transcript: `{file_id}.txt`
- Hebrew: `{file_id}.he.txt`
- German: `{file_id}.de.txt`
- English: `{file_id}.en.txt`

## Hebrew-Specific Issues

### Hebrew Not Routing to Microsoft/OpenAI
**Solution**: Test Hebrew routing:
```bash
uv run python test_hebrew_fix.py
```

### RTL Display Issues
**Cause**: Text editor doesn't support RTL  
**Solution**: Use RTL-compatible editor or viewer

## Getting Help

1. Check logs in `logs/` directory
2. Enable debug logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```
3. Review [documentation](../README.md)
4. Check [Hebrew Evaluation Fix PRD](../PRDs/hebrew-evaluation-fix.md) for recent fixes