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
**Solution**: Use database maintenance tools:
```bash
# Run comprehensive audit
uv run python scribe_cli.py db audit

# Fix status inconsistencies
uv run python scribe_cli.py db fix-status

# Check overall status
uv run python scribe_cli.py status --detailed
```

### System Recovery After Crashes
**Solution**: Use systematic recovery approach:
```bash
# 1. Create emergency backup
uv run python scribe_cli.py backup create --quick

# 2. Audit system for issues
uv run python scribe_cli.py db audit

# 3. Fix identified problems
uv run python scribe_cli.py db fix-status

# 4. Validate system health
uv run python scribe_cli.py db validate
```

## Evaluation Issues

### Hebrew Evaluation Failures
**Cause**: Missing Hebrew characters or language validation issues  
**Solution**: Use enhanced Hebrew evaluation:
```bash
# Enhanced Hebrew evaluation with sanity checks
uv run python scribe_cli.py evaluate he --sample 20 --enhanced --model gpt-4.1

# Check specific problematic file
uv run python scribe_cli.py check-translation <file_id> he
```

### Token Limit Errors
**Cause**: Transcripts too long for GPT-4 context window  
**Solution**: Enhanced mode handles truncation automatically:
```bash
# Recommended approach (handles truncation)
uv run python scribe_cli.py evaluate he --sample 20 --enhanced

# Legacy script (still available)
uv run python evaluate_hebrew.py --limit 10
```

### Score of 0.0
**Cause**: API call failed but was recorded as successful  
**Solution**: Check for files with 0.0 scores and re-evaluate:
```bash
sqlite3 media_tracking.db "DELETE FROM quality_evaluations WHERE score = 0.0 AND language = 'he';"
```

### Hebrew Sanity Check Failures
**Symptoms**: "NO_HEBREW_CHARACTERS" or "LOW_HEBREW_RATIO" warnings  
**Solution**: 
```bash
# Identify problematic files
uv run python scribe_cli.py evaluate he --sample 50 --enhanced

# Re-translate problematic files
uv run python scribe_cli.py translate he --limit 10

# Verify improvements
uv run python scribe_cli.py evaluate he --sample 10 --enhanced
```

### Inconsistent Scores
**Cause**: Different evaluation models or truncation  
**Solution**: Use consistent model and enhanced mode:
```bash
# Always use same model for comparability
uv run python scribe_cli.py evaluate he --sample 20 --enhanced --model gpt-4.1
```

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

## Backup and Recovery

### System Corruption
**Solution**: Restore from backup:
```bash
# List available backups
uv run python scribe_cli.py backup list

# Restore from specific backup
uv run python scribe_cli.py backup restore <backup_id>
```

### Preventive Measures
**Best Practice**: Regular backups and maintenance:
```bash
# Daily quick backup
uv run python scribe_cli.py backup create --quick

# Weekly maintenance
uv run python scribe_cli.py backup create
uv run python scribe_cli.py db audit
uv run python scribe_cli.py db fix-status
```

### Emergency Recovery
If system is severely corrupted:
```bash
# 1. Create emergency backup of current state
uv run python scribe_cli.py backup create --quick

# 2. Find most recent good backup
uv run python scribe_cli.py backup list

# 3. Restore from backup
uv run python scribe_cli.py backup restore <backup_id>

# 4. Validate restoration
uv run python scribe_cli.py db validate
```

## Utilities Directory

### One-off Scripts
For specialized troubleshooting, scripts are available in `utilities/`:

```bash
# Hebrew-specific utilities
ls utilities/hebrew_fixes/

# Database maintenance utilities
ls utilities/database/

# Backup utilities
ls utilities/backup/
```

**Warning**: Always backup before using utilities scripts.

## Getting Help

1. **System Validation**: `uv run python scribe_cli.py db validate`
2. **Database Audit**: `uv run python scribe_cli.py db audit`
3. **Check logs** in `logs/` directory
4. **Review backups**: `uv run python scribe_cli.py backup list`
5. **Enable debug logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```
6. **Review documentation**:
   - [Backup Guide](backup.md)
   - [Database Maintenance Guide](database-maintenance.md)
   - [Evaluation Guide](evaluation.md)
7. **Check recent fixes**: [Hebrew Evaluation Fix PRD](../PRDs/hebrew-evaluation-fix.md)