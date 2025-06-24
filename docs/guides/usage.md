# Usage Guide

Complete guide to using Scribe for processing historical interviews.

## Important Note

**Always use `uv run` prefix**: This project uses `uv` package manager, not standard Python.

```bash
# Correct
uv run python scribe_cli.py status

# Incorrect (will fail with import errors)
python scribe_cli.py status
```

## Basic Workflow

1. **Add files** to the processing queue
2. **Transcribe** audio to text
3. **Translate** to target languages
4. **Evaluate** translation quality
5. **Review** results
6. **Backup** completed work

## System Maintenance

Before starting large operations, ensure system health:

```bash
# Validate system configuration
uv run python scribe_cli.py db validate

# Create backup before major processing
uv run python scribe_cli.py backup create
```

## Commands Reference

### Adding Files

Add media files to the processing queue:

```bash
# Add single file
uv run python scribe_cli.py add /path/to/interview.mp4

# Add directory (non-recursive)
uv run python scribe_cli.py add /path/to/media/

# Add directory recursively
uv run python scribe_cli.py add /path/to/media/ --recursive
```

Supported formats: `.mp3`, `.mp4`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.avi`, `.mov`

### Transcription

Convert audio to text using ElevenLabs Scribe:

```bash
# Transcribe all pending files with 10 workers
uv run python scribe_cli.py transcribe --workers 10

# Transcribe limited number of files
uv run python scribe_cli.py transcribe --limit 5
```

Output: `output/{file_id}/{file_id}_transcript.txt`

### Translation

Translate transcripts to target languages:

```bash
# Translate to English
uv run python scribe_cli.py translate en --workers 8

# Translate to German
uv run python scribe_cli.py translate de --workers 8

# Translate to Hebrew (uses gpt-4.1-mini by default)
uv run python scribe_cli.py translate he --workers 8

# Translate with custom model
uv run python scribe_cli.py translate he --workers 8 --model gpt-4.1-mini

# Translate with file limit
uv run python scribe_cli.py translate en --limit 10
```

Output: `output/{file_id}/{file_id}_{language}.txt`

**Note**: Hebrew translations automatically use Microsoft Translator or OpenAI instead of DeepL (which doesn't support Hebrew).

### Quality Evaluation

Evaluate translation quality with enhanced Hebrew support:

```bash
# Evaluate Hebrew translations with enhanced mode (includes sanity checks)
uv run python scribe_cli.py evaluate he --sample 20 --enhanced --model gpt-4.1

# Evaluate German translations
uv run python scribe_cli.py evaluate de --sample 50

# Evaluate English translations
uv run python scribe_cli.py evaluate en --sample 30

# Basic Hebrew evaluation (without enhanced features)
uv run python scribe_cli.py evaluate he --sample 20
```

**Enhanced Hebrew Evaluation Features**:
- Sanity checks for Hebrew character presence
- Language detection to prevent English/placeholder content
- Detailed Hebrew-specific analysis
- GPT-4.1 model for better accuracy

### Status Monitoring

Check processing status:

```bash
# Basic status
uv run python scribe_cli.py status

# Detailed status with quality scores
uv run python scribe_cli.py status --detailed
```

### Managing Stuck Files

Reset files stuck in processing:

```bash
# View stuck files
uv run python scribe_cli.py fix-stuck

# Reset all stuck files
uv run python scribe_cli.py fix-stuck --reset-all
```

### Full Pipeline

Run complete processing pipeline:

```bash
# Process all languages
uv run python scribe_cli.py process

# Process specific languages
uv run python scribe_cli.py process --languages en,de

# Custom worker counts
uv run python scribe_cli.py process --transcription-workers 10 --translation-workers 8
```

### Checking Individual Files

Inspect specific translations:

```bash
# Check Hebrew translation quality
uv run python scribe_cli.py check-translation <file_id> he

# Example
uv run python scribe_cli.py check-translation 225f0880-e414-43cd-b3a5-2bd6e5642f07 he
```

## Output Structure

All processed files are saved to:

```
output/
└── {file_id}/
    ├── {file_id}_transcript.txt    # Original transcription
    ├── {file_id}_transcript.srt    # Subtitle format
    ├── {file_id}_en.txt           # English translation
    ├── {file_id}_de.txt           # German translation
    └── {file_id}_he.txt           # Hebrew translation
```

## Processing Tips

1. **Start Small**: Test with 5-10 files first
2. **Monitor Progress**: Check `logs/` directory for detailed logs
3. **Parallel Processing**: Use multiple workers for speed
   - Transcription: 10 workers recommended
   - Translation: 8 workers recommended
4. **Check Quality**: Review first few outputs manually

## Common Workflows

### Process New Interview Batch

```bash
# 1. Add files
uv run python scribe_cli.py add /media/interviews/ --recursive

# 2. Check what was added
uv run python scribe_cli.py status

# 3. Transcribe
uv run python scribe_cli.py transcribe --workers 10

# 4. Translate to all languages
uv run python scribe_cli.py translate en --workers 8
uv run python scribe_cli.py translate de --workers 8
uv run python scribe_cli.py translate he --workers 8

# 5. Evaluate quality (enhanced mode for Hebrew)
uv run python scribe_cli.py evaluate he --sample 20 --enhanced
uv run python scribe_cli.py evaluate en --sample 20
uv run python scribe_cli.py evaluate de --sample 20

# 6. Create backup of completed work
uv run python scribe_cli.py backup create
```

### Resume Interrupted Processing

```bash
# 1. Check current status
uv run python scribe_cli.py status

# 2. Fix any stuck files
uv run python scribe_cli.py fix-stuck --reset-all

# 3. Continue processing
uv run python scribe_cli.py transcribe --workers 10
```

## Backup and Restore

Regularly backup your work:

```bash
# Create full backup
uv run python scribe_cli.py backup create

# Create quick backup (faster, uses compression)
uv run python scribe_cli.py backup create --quick

# List available backups
uv run python scribe_cli.py backup list

# Restore from backup
uv run python scribe_cli.py backup restore <backup_id>
```

See [Backup Guide](backup.md) for complete documentation.

## Database Maintenance

Maintain database health:

```bash
# Audit database for issues
uv run python scribe_cli.py db audit

# Fix status inconsistencies
uv run python scribe_cli.py db fix-status

# Preview fixes without applying
uv run python scribe_cli.py db fix-status --dry-run

# Validate system health
uv run python scribe_cli.py db validate
```

See [Database Maintenance Guide](database-maintenance.md) for complete documentation.

## Database Queries

For advanced users, you can query the SQLite database directly:

```bash
# Open database
sqlite3 media_tracking.db

# Example queries
SELECT COUNT(*) FROM processing_status WHERE translation_he_status = 'completed';
SELECT file_id, score FROM quality_evaluations WHERE language = 'he' ORDER BY score DESC LIMIT 10;
```

## Advanced Workflows

### System Recovery

If you encounter issues:

```bash
# 1. Create emergency backup
uv run python scribe_cli.py backup create --quick

# 2. Audit database
uv run python scribe_cli.py db audit

# 3. Fix issues
uv run python scribe_cli.py db fix-status

# 4. Validate system
uv run python scribe_cli.py db validate
```

### Hebrew Translation Issues

For Hebrew-specific problems:

```bash
# Enhanced evaluation with detailed reporting
uv run python scribe_cli.py evaluate he --sample 50 --enhanced

# Check specific translation
uv run python scribe_cli.py check-translation <file_id> he
```

### Maintenance Schedule

Recommended maintenance routine:

```bash
# Daily: Quick backup
uv run python scribe_cli.py backup create --quick

# Weekly: Full audit and cleanup
uv run python scribe_cli.py backup create
uv run python scribe_cli.py db audit
uv run python scribe_cli.py db fix-status
```

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues and solutions.