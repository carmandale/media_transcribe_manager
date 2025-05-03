# Translation Process Guide

This document outlines the translation process for the Rigg historical interviews project, focusing on generating historically accurate translations while preserving speech patterns and maintaining subtitle synchronization.

## Overview

The translation pipeline processes interview transcripts and produces:
1. Translated text files 
2. Synchronized subtitle files (.srt format)
3. Historical accuracy evaluations

## Processing Missing Translations

Use the `process_missing_translations.py` script to efficiently process files with completed transcriptions but missing translations:

```bash
# Process English translations
python process_missing_translations.py --languages en --batch-size 10

# Process German translations 
python process_missing_translations.py --languages de --batch-size 10

# Process Hebrew translations
python process_missing_translations.py --languages he --batch-size 10

# Process all languages at once
python process_missing_translations.py --languages en,de,he --batch-size 10
```

### Options

- `--languages`: Comma-separated list of languages to process (en, de, he)
- `--batch-size`: Number of files to process in each batch
- `--limit`: Maximum number of files to process 
- `--evaluate`: Evaluate historical accuracy after translation
- `--provider`: Choose translation provider (deepl, microsoft, google, openai)
- `--sleep`: Seconds to sleep between batches
- `--dry-run`: Show what would be processed without actually processing

## Historical Accuracy Evaluation

The historical accuracy evaluation analyzes translations based on criteria specific to historical interviews:

```bash
# Evaluate English translations
python historical_evaluate_quality.py --language en --limit 10

# Evaluate with different thresholds
python historical_evaluate_quality.py --language de --threshold 8.0 --limit 5
```

### Evaluation Criteria

1. **Content Accuracy (40%)**: Preservation of historical facts, names, dates, events
2. **Speech Pattern Fidelity (30%)**: Preservation of speaker's natural voice, hesitations, filler words 
3. **Cultural Context (15%)**: Appropriate handling of cultural references and idioms
4. **Historical Reliability (15%)**: Overall suitability for historical research

### Quality Thresholds

- **Excellent (8.5-10)**: Translation meets highest standards for historical research
- **Acceptable (8.0-8.4)**: Translation is suitable for research with minor reservations
- **Needs Improvement (<8.0)**: Translation requires revision before use in historical research

For detailed guidelines, see [QUALITY_EVALUATION_GUIDE.md](docs/QUALITY_EVALUATION_GUIDE.md)

## Translation/Subtitle File Locations

- **Translations**: `./output/translations/[language]/[file_id]_[filename]_[language].txt`
- **Subtitles**: `./output/subtitles/[language]/[file_id]_[filename]_[language].srt`

## Translation Providers

The system supports multiple translation providers, with different strengths:

1. **DeepL** (default): High-quality machine translation for European languages
2. **OpenAI**: Strong for context-aware translations and Hebrew
3. **Microsoft**: Good fallback for many language pairs
4. **Google**: Additional backup for language support

For Hebrew translations, the system uses a specialized two-step process with GPT-4 polish.

## Checking Status

To check translation status in the database:

```bash
python media_processor.py --list-files
```

## Historical Accuracy Results Query

To view historical accuracy evaluation results:

```bash
python -c "from db_manager import DatabaseManager; db = DatabaseManager('./media_tracking.db'); results = db.execute_query('SELECT file_id, language, score, custom_data FROM quality_evaluations WHERE model LIKE \"historical-%\" ORDER BY created_at DESC LIMIT 10'); print('\n'.join(str(r) for r in results))"
```