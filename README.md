# Scribe - Historical Interview Preservation System

A comprehensive system for preserving historical interviews through accurate transcription, multi-language translation, and accessible digital presentation.

## 🎯 System Overview

Scribe consists of **two integrated components**:
- **Core Processing Engine** (`scribe/`): Python-based transcription and translation pipeline
- **Scribe Viewer Web Application** (`scribe-viewer/`): Modern web interface for research and quality control

## 📊 Current Status
- **728 files** processed through transcription and translation pipeline
- **Multi-language support**: English, German, and Hebrew with specialized handling
- **Web viewer**: Modern React interface with video synchronization (in development)
- **Production readiness**: Currently stabilizing for production deployment

## 📚 Documentation
- **[Project Vision](PROJECT_VISION.md)**: Mission, goals, and system overview
- **[Architecture Guide](ARCHITECTURE.md)**: Technical design and component relationships  
- **[Development Guide](DEVELOPMENT_GUIDE.md)**: Setup instructions and workflows for developers

## Documentation

For comprehensive documentation, see the [`docs/`](docs/) directory:
- [Setup Guide](docs/guides/setup.md)
- [Usage Guide](docs/guides/usage.md) 
- [Architecture Overview](docs/architecture/)
- [Backup Guide](docs/guides/backup.md)
- [Database Maintenance Guide](docs/guides/database-maintenance.md)
- [Current Issues](docs/PRDs/hebrew-evaluation-fix.md)

## Overview

Scribe processes audio and video recordings to create:
- Verbatim transcriptions with speaker identification
- Translations to English, German, and Hebrew
- Quality-evaluated output suitable for historical research

The system emphasizes preserving authentic speech patterns, including hesitations, repetitions, and emotional context.

## Quick Start

```bash
# Install dependencies (requires uv)
uv pip install -r requirements.txt

# Add files to process (from any location)
uv run python scribe_cli.py add /path/to/media/files/

# Run full pipeline
uv run python scribe_cli.py process

# Check status
uv run python scribe_cli.py status
```

## Core Commands

### Adding Files
```bash
# Add single file
uv run python scribe_cli.py add path/to/interview.mp4

# Add directory recursively
uv run python scribe_cli.py add input/ --recursive
```

### Processing
```bash
# Transcribe audio to text
uv run python scribe_cli.py transcribe --workers 10

# Translate to specific language (Hebrew uses gpt-4.1-mini by default)
uv run python scribe_cli.py translate en --workers 8
uv run python scribe_cli.py translate de --workers 8
uv run python scribe_cli.py translate he --workers 8 --model gpt-4.1-mini

# Evaluate translation quality (enhanced mode for Hebrew)
uv run python scribe_cli.py evaluate he --sample 20 --enhanced --model gpt-4.1
```

### Management
```bash
# View processing status
uv run python scribe_cli.py status --detailed

# Fix stuck files
uv run python scribe_cli.py fix-stuck

# Check specific translation
uv run python scribe_cli.py check-translation <file_id> he
```

### Backup & Restore
```bash
# Create system backup
uv run python scribe_cli.py backup create

# Create quick backup (faster, uses tar compression)
uv run python scribe_cli.py backup create --quick

# List available backups
uv run python scribe_cli.py backup list

# Restore from backup
uv run python scribe_cli.py backup restore <backup_id>
```

### Database Maintenance
```bash
# Audit database for issues
uv run python scribe_cli.py db audit

# Fix database status inconsistencies
uv run python scribe_cli.py db fix-status

# Validate system health
uv run python scribe_cli.py db validate
```

## Configuration

Create a `.env` file with your API keys:

```env
# Required for transcription
ELEVENLABS_API_KEY=your_key_here

# Required for translation
DEEPL_API_KEY=your_key_here
MS_TRANSLATOR_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Optional settings
DATABASE_PATH=media_tracking.db
INPUT_PATH=input/
OUTPUT_PATH=output/
```

## Project Structure

```
scribe/
├── docs/                # Documentation
│   ├── architecture/    # System design
│   ├── guides/         # User guides
│   └── PRDs/           # Product requirements
│
├── scribe/              # Core modules
│   ├── database.py      # SQLite with thread-safe pooling
│   ├── transcribe.py    # ElevenLabs Scribe integration
│   ├── translate.py     # Multi-provider translation (Hebrew fix)
│   ├── evaluate.py      # Quality scoring (enhanced Hebrew support)
│   ├── pipeline.py      # Workflow orchestration
│   ├── backup.py        # Backup and restore system
│   ├── audit.py         # Database auditing and validation
│   └── utils.py         # Helper functions
│
├── utilities/           # One-off scripts and maintenance tools
│   ├── backup/         # Backup utilities
│   ├── database/       # Database maintenance scripts
│   ├── hebrew_fixes/   # Hebrew-specific utilities
│   └── validate_all_translations.py
│
├── tests/               # Test suite
├── scripts/             # Processing scripts
├── scribe_cli.py        # Command-line interface
├── requirements.txt     # Python dependencies
├── .env                 # API keys and settings
│
├── backups/             # System backups
├── output/              # Processed results
└── logs/                # Application logs
```

## Output Structure

```
output/
└── {file_id}/
    ├── {file_id}_transcript.txt    # Original transcription
    ├── {file_id}_transcript.srt    # Subtitles
    ├── {file_id}_en.txt           # English translation
    ├── {file_id}_de.txt           # German translation
    └── {file_id}_he.txt           # Hebrew translation
```

## Hebrew Translation Features

Hebrew translations have special handling:

- **Automatic Provider Routing**: Uses Microsoft Translator or OpenAI instead of DeepL (which doesn't support Hebrew)
- **Enhanced Evaluation**: Includes sanity checks for Hebrew character presence and language detection
- **GPT-4.1-mini Default**: Optimized model selection for Hebrew translation quality
- **Validation Checks**: Automatically detects and flags translations with issues

Just ensure you have either `MS_TRANSLATOR_KEY` or `OPENAI_API_KEY` configured.

## Quality Standards

Translations are evaluated on:
- **Content Accuracy** (40%) - Factual correctness
- **Speech Pattern Fidelity** (30%) - Preserving authentic voice
- **Cultural Context** (15%) - Historical nuance
- **Overall Reliability** (15%) - Research suitability

Target scores:
- 8.5+ Excellent
- 7.0-8.4 Good
- <7.0 Needs improvement

## Processing Tips

1. **Start with a small batch** to verify quality settings
2. **Use parallel workers** for faster processing (10 for transcription, 8 for translation)
3. **Monitor the first few outputs** to ensure quality meets standards
4. **Run evaluation** on samples to track quality

## Troubleshooting

### Stuck Files
```bash
# Reset stuck files to pending
uv run python scribe_cli.py fix-stuck --reset-all
```

### Check API Keys
```bash
# Show configuration status
uv run python scribe_cli.py version
```

### Database Issues
```bash
# Run comprehensive audit
uv run python scribe_cli.py db audit

# Fix status inconsistencies
uv run python scribe_cli.py db fix-status
```

### System Recovery
```bash
# Create emergency backup before troubleshooting
uv run python scribe_cli.py backup create --quick

# Restore from backup if needed
uv run python scribe_cli.py backup restore <backup_id>
```

### Test Hebrew Translation
```bash
# Verify Hebrew routing is working
uv run python test_hebrew_fix.py
```

## Support

This system is designed for preserving historical interviews with maximum fidelity. The focus is on authentic preservation over polished output.
