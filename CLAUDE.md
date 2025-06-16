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
│   ├── evaluate.py      # Quality scoring (30% speech patterns)
│   ├── pipeline.py      # Workflow orchestration
│   ├── utils.py         # Helper functions
│   ├── README.md        # Module documentation
│   └── DATABASE_README.md # Database documentation
│
├── scribe_cli.py        # Single CLI entry point
├── test_hebrew_fix.py   # Hebrew routing test
├── README.md            # User documentation
├── requirements.txt     # Python dependencies
├── media_tracking.db    # SQLite database
├── .env                 # API keys
├── .gitignore          # Git configuration
│
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

# Translate to specific language
uv run python scribe_cli.py translate en --workers 8
uv run python scribe_cli.py translate de --workers 8
uv run python scribe_cli.py translate he --workers 8

# Evaluate translation quality
uv run python scribe_cli.py evaluate he --sample 20

# Alternative Hebrew evaluation script
uv run python evaluate_hebrew.py --limit 50

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

## Development Guidelines

1. **Clean Structure**: This is the cleaned up version - no legacy code
2. **Single Entry Point**: All operations go through scribe_cli.py
3. **Import Pattern**: Use `from scribe import module_name`
4. **Testing**: Run `uv run python test_hebrew_fix.py` to verify Hebrew routing
5. **Focus**: Historical preservation - accuracy over polish
6. **Package Manager**: Use `uv` not `pip` or `venv` (e.g., `uv run python scribe_cli.py`)
7. **Documentation**: Update docs/ when making changes

## Environment Setup
Required in .env:
- ELEVENLABS_API_KEY (transcription)
- DEEPL_API_KEY (EN/DE translation)
- MS_TRANSLATOR_KEY or OPENAI_API_KEY (Hebrew translation)

## Important Notes

1. **No input directory needed** - Add files from their current location
2. **Output structure**: Files are processed to `output/{file_id}/`
3. **Database**: All state tracked in `media_tracking.db`
4. **Logs**: Check `logs/` for debugging
5. **Known Issues**: See [Hebrew Evaluation Fix PRD](docs/PRDs/hebrew-evaluation-fix.md)

## Historical Context
This system preserves Holocaust survivor testimonies and WWII accounts. Every hesitation, pause, and emotional inflection matters for historical accuracy.