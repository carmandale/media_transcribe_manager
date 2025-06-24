# CLAUDE.md - Scribe Project Guide

This file provides guidance to Claude Code when working with the Scribe historical interview preservation system.

## Documentation
Comprehensive documentation is available in the `docs/` directory:
- [Documentation Overview](docs/README.md)
- [Architecture Guide](docs/architecture/)
- [Setup & Usage Guides](docs/guides/)
- [PRDs & Decisions](docs/PRDs/)
- [Current Issue: Hebrew Evaluation Fix](docs/PRDs/hebrew-evaluation-fix.md)

## Project Overview
Scribe processes historical interview recordings (Bryan Rigg Archive) to create accurate transcriptions and translations while preserving authentic speech patterns for historical research.

## Actual Current Structure
```
scribe/
├── docs/                # Documentation
│   ├── architecture/    # System design docs
│   ├── guides/         # How-to guides
│   ├── PRDs/           # Product requirements
│   ├── api/            # API reference
│   └── decisions/      # ADRs
│
├── scribe/              # Core modules
│   ├── __init__.py      # Package initialization
│   ├── database.py      # Thread-safe SQLite operations
│   ├── transcribe.py    # ElevenLabs Scribe integration
│   ├── translate.py     # Multi-provider translation (WITH HEBREW FIX)
│   ├── evaluate.py      # Quality scoring (enhanced Hebrew evaluation)
│   ├── pipeline.py      # Workflow orchestration
│   ├── backup.py        # Backup and restore system
│   ├── audit.py         # Database auditing and validation
│   ├── utils.py         # Helper functions
│   ├── README.md        # Module documentation
│   └── DATABASE_README.md # Database documentation
│
├── utilities/           # One-off scripts and maintenance tools
│   ├── backup/         # Backup utilities
│   ├── database/       # Database maintenance scripts
│   ├── hebrew_fixes/   # Hebrew-specific utilities
│   └── validate_all_translations.py
│
├── tests/               # Test suite
├── scripts/             # Processing scripts
├── scribe_cli.py        # Single CLI entry point
├── test_hebrew_fix.py   # Hebrew routing test
├── README.md            # User documentation
├── requirements.txt     # Python dependencies
├── media_tracking.db    # SQLite database
├── .env                 # API keys
├── .gitignore          # Git configuration
│
├── backups/             # System backups
├── output/              # Processed results (700+ files)
└── logs/                # Application logs
```

## Critical Code to Preserve

### Hebrew Translation Fix (in scribe/translate.py)
```python
# Hebrew requires special handling - DeepL doesn't support it
if target_language.lower() in ['he', 'hebrew', 'heb']:
    return self._translate_hebrew(text, source_lang)
```
This fix ensures Hebrew translations use Microsoft/OpenAI instead of DeepL.

### Async Translation Improvements (December 2024)
- **Timeout Configuration**: OpenAI client configured with 60s timeout and 3 retries
- **Retry Logic**: Exponential backoff decorator for handling transient failures
- **Worker Pool Enhancements**: Timeout handling prevents indefinite blocking
- **Progress Persistence**: Database commits after each successful translation

### Enhanced Hebrew Evaluation (in scribe/evaluate.py)
- Enhanced evaluation mode with sanity checks for Hebrew translations
- Detects missing Hebrew characters and low Hebrew character ratios
- Uses GPT-4.1 model by default for Hebrew evaluation
- Provides detailed Hebrew-specific analysis and recommendations

### Speech Pattern Preservation (in scribe/evaluate.py)
- Quality evaluation weights speech pattern fidelity at 30%
- Essential for maintaining authentic historical testimony

## Available Commands (via scribe_cli.py)

### File Management
```bash
# Add files to process
uv run python scribe_cli.py add path/to/file.mp4
uv run python scribe_cli.py add output/ --recursive  # Add directory
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
uv run python scribe_cli.py evaluate en --sample 20
uv run python scribe_cli.py evaluate de --sample 20

# Run full pipeline
uv run python scribe_cli.py process
```

### Monitoring
```bash
# Check status
uv run python scribe_cli.py status
uv run python scribe_cli.py status --detailed

# Fix stuck files
uv run python scribe_cli.py fix-stuck
uv run python scribe_cli.py fix-stuck --reset-all

# Check specific translation
uv run python scribe_cli.py check-translation <file_id> he

# Show version and config
uv run python scribe_cli.py version
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

# Preview changes before applying
uv run python scribe_cli.py db fix-status --dry-run

# Validate system health
uv run python scribe_cli.py db validate
```

## Development Guidelines

1. **Clean Structure**: This is the cleaned up version - no legacy code
2. **Single Entry Point**: All operations go through scribe_cli.py
3. **Import Pattern**: Use `from scribe import module_name`
4. **Testing**: Run `uv run python test_hebrew_fix.py` to verify Hebrew routing
5. **Focus**: Historical preservation - accuracy over polish
6. **Package Manager**: Use `uv` not `pip` or `venv` (e.g., `uv run python scribe_cli.py`)
7. **Documentation**: Update docs/ when making changes
8. **Backup First**: Always create backups before major operations
9. **Audit Regularly**: Use `db audit` to maintain system health
10. **Enhanced Hebrew**: Use `--enhanced` flag for Hebrew evaluation

## Environment Setup
Required in .env:
- ELEVENLABS_API_KEY (transcription)
- DEEPL_API_KEY (EN/DE translation)
- MS_TRANSLATOR_KEY or OPENAI_API_KEY (Hebrew translation - GPT-4.1-mini recommended)

## New Features

### Enhanced Hebrew Evaluation
- Automatic sanity checks for Hebrew character presence
- Language detection to prevent English/placeholder text
- GPT-4.1 model for more accurate Hebrew assessment
- Detailed Hebrew-specific analysis and warnings

### Backup System
- Comprehensive backup of database and translation files
- Quick backup mode using tar compression
- Restore functionality with safety backups
- Backup validation and manifest tracking

### Database Auditing
- Complete database integrity checks
- File system consistency validation
- Automated status fix recommendations
- System health monitoring

### Utilities Directory
- One-off maintenance scripts organized by category
- Hebrew-specific troubleshooting tools
- Database repair utilities
- Legacy backup scripts for reference

## Important Notes

1. **No input directory needed** - Add files from their current location
2. **Output structure**: Files are processed to `output/{file_id}/`
3. **Database**: All state tracked in `media_tracking.db`
4. **Logs**: Check `logs/` for debugging
5. **Backups**: Stored in `backups/` directory with timestamps
6. **Utilities**: Use scripts in `utilities/` directory with caution - always backup first
7. **Hebrew Enhancements**: Enhanced mode provides better quality assessment
8. **GPT-4.1-mini**: Default model for Hebrew translations, balances quality and cost

## Historical Context
This system preserves Holocaust survivor testimonies and WWII accounts. Every hesitation, pause, and emotional inflection matters for historical accuracy.