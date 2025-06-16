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

# Translate to Hebrew
uv run python scribe_cli.py translate he --workers 8

# Translate with file limit
uv run python scribe_cli.py translate en --limit 10
```

Output: `output/{file_id}/{file_id}_{language}.txt`

### Quality Evaluation

Evaluate translation quality (currently broken - see [fix PRD](../PRDs/hebrew-evaluation-fix.md)):

```bash
# Evaluate Hebrew translations (sample of 20)
uv run python scribe_cli.py evaluate he --sample 20

# Evaluate German translations
uv run python scribe_cli.py evaluate de --sample 50
```

### Status Monitoring

Check processing status:

```bash
# Basic status
uv run python scribe_cli.py status

# Detailed status (currently has issues)
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

# 5. Evaluate quality (when fixed)
uv run python scribe_cli.py evaluate he --sample 20
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

## Database Queries

For advanced users, you can query the SQLite database directly:

```bash
# Open database
sqlite3 media_tracking.db

# Example queries
SELECT COUNT(*) FROM processing_status WHERE translation_he_status = 'completed';
SELECT file_id, score FROM quality_evaluations WHERE language = 'he' ORDER BY score DESC LIMIT 10;
```

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues and solutions.