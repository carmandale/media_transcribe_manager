# Scribe - Historical Interview Preservation System

A clean, modern system for preserving historical interviews through accurate transcription and translation.

## Documentation

For comprehensive documentation, see the [`docs/`](docs/) directory:
- [Setup Guide](docs/guides/setup.md)
- [Usage Guide](docs/guides/usage.md) 
- [Architecture Overview](docs/architecture/)
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

# Translate to specific language
uv run python scribe_cli.py translate en --workers 8
uv run python scribe_cli.py translate de --workers 8
uv run python scribe_cli.py translate he --workers 8

# Evaluate translation quality
uv run python scribe_cli.py evaluate he --sample 20

# Alternative: Use dedicated Hebrew evaluation script
uv run python evaluate_hebrew.py --limit 50
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
│   ├── translate.py     # Multi-provider translation
│   ├── evaluate.py      # Quality scoring
│   ├── pipeline.py      # Workflow orchestration
│   └── utils.py         # Helper functions
│
├── scribe_cli.py        # Command-line interface
├── evaluate_hebrew.py   # Dedicated Hebrew evaluation script
├── requirements.txt     # Python dependencies
├── .env                 # API keys and settings
│
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

## Hebrew Translation Note

Hebrew translations automatically use Microsoft Translator or OpenAI instead of DeepL (which doesn't support Hebrew). This routing happens automatically - just ensure you have either `MS_TRANSLATOR_KEY` or `OPENAI_API_KEY` configured.

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

### Test Hebrew Translation
```bash
# Verify Hebrew routing is working
uv run python test_hebrew_fix.py
```

## Support

This system is designed for preserving historical interviews with maximum fidelity. The focus is on authentic preservation over polished output.