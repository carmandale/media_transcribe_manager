# Hebrew Translation Fix Guide

## Problem Summary

The system is experiencing issues with Hebrew translations where:

1. Many files are tagged as having Hebrew translations but actually contain English text with a placeholder "[HEBREW TRANSLATION]"
2. When these files are evaluated for historical accuracy, they receive very low scores (often 1/10)
3. Proper RTL formatting and Hebrew-specific considerations are not being consistently applied

## Root Cause Analysis

The issues stem from:

1. **Translation Pipeline Issue**: When DeepL is the provider and Hebrew is the target language, a fallback mechanism simply adds "[HEBREW TRANSLATION]" to the English text instead of actually translating. This occurs because **DeepL doesn't support Hebrew as a target language**
2. **Proper RTL Formatting**: Hebrew requires special right-to-left text formatting, which isn't being consistently applied
3. **Missing Glossary Integration**: Historical terms and proper nouns need consistent Hebrew translations

## Implementation Details

The implementation in `translation.py` shows the root cause:

```python
# DeepL doesn't support Hebrew as a target language
if target_language.lower() in ['he', 'heb', 'hebrew'] and provider == 'deepl':
    logger.info(f"DeepL doesn't support Hebrew as a target language. Using DeepL to translate to English first.")
    
    # Translate to English first
    english_text = self.translate_text(
        text=text,
        target_language='en',
        source_language=source_language,
        provider='deepl',
        formality=formality
    )
    
    # Mark the English text as Hebrew
    if english_text:
        return f"[HEBREW TRANSLATION] {english_text}"
    else:
        return None
```

This code was modified to use OpenAI for direct translation to Hebrew instead of adding a placeholder.

## Solution Approach

Two scripts have been created to address these issues:

1. `fix_hebrew_translations.py` - Identifies and fixes Hebrew translations with placeholder text by:
   - Finding files with the "[HEBREW TRANSLATION]" placeholder
   - Using OpenAI directly for proper Hebrew translation
   - Applying Hebrew-specific post-processing and glossary terms
   - Updating subtitle files and database status

2. `run_full_pipeline.py` - Orchestrates the complete translation and evaluation process:
   - Processes missing translations for all languages
   - Fixes Hebrew translations with placeholder text
   - Evaluates translation quality using historical criteria
   - Generates comprehensive reports

3. `historical_evaluate_quality.py` - Evaluates translations based on historical accuracy:
   - Uses OpenAI to evaluate translations based on specialized historical criteria
   - Focuses on content accuracy rather than fluency
   - Maintains historical voice and terminological accuracy
   - Scores translations on a 1-10 scale with detailed feedback

Additionally, we've updated other components:

1. `process_missing_translations.py` - Now accepts a `--db-path` parameter for consistent database access
2. Debug improvements in file path handling for transcript and translation files

## Usage Instructions

### Fix Hebrew Translations

To identify and fix Hebrew translations with placeholder text:

```bash
python fix_hebrew_translations.py --batch-size 20
```

Options:
- `--batch-size N`: Number of files to process (default: 20)
- `--dry-run`: Show what would be fixed without making changes
- `--db-path PATH`: Path to the database file (default: media_tracking.db)

### Run Full Pipeline

To run the complete translation and evaluation pipeline:

```bash
python run_full_pipeline.py --batch-size 20
```

Options:
- `--batch-size N`: Batch size for processing (default: 20)
- `--languages LANGS`: Languages to process (comma-separated, default: en,de,he)
- `--skip-translation`: Skip the translation step
- `--skip-hebrew-fix`: Skip the Hebrew fix step
- `--skip-evaluation`: Skip the evaluation step
- `--db-path PATH`: Path to the database file (default: media_tracking.db)

## Hebrew Glossary

A Hebrew glossary has been created at `docs/glossaries/he_seed.csv` to ensure consistent translation of historical terms and proper nouns. This glossary is used during both translation and post-processing steps.

The glossary contains common historical terms related to the subject matter, including:
- Historical events (World War II, Holocaust, etc.)
- Organizations (Wehrmacht, SS, etc.)
- People and places (Hitler, Auschwitz, etc.)
- Specialized terminology (Antisemitism, Concentration Camp, etc.)

## Monitoring and Verification

After running the pipeline, the quality of Hebrew translations should be evaluated using:

```bash
python historical_evaluate_quality.py --language he --limit 20
```

This will apply historical accuracy criteria specifically tailored for Hebrew translations and score them on:
1. Content Accuracy (40% weight)
2. Speech Pattern Fidelity (30% weight)
3. Cultural Context (15% weight)
4. Historical Reliability (15% weight)

### Current Progress (May 2025)

We've made significant progress with the Hebrew translation fixes:

- Total files: 728
- Transcribed: 728/728 files (100%)
- English translations: 555/728 completed (76%)
- German translations: 494/728 completed (68%)
- Hebrew translations: 360/728 completed (49%)

From our sample evaluations, we're seeing:
- English translations: 8.5-9.75/10 average quality score
- German translations: 9.0-10/10 average quality score
- Hebrew translations (fixed): 8.5-9.0/10 average quality score
- Hebrew translations (unfixed): 1.0-3.0/10 average quality score

The full pipeline is continuing to process remaining translations and evaluate their quality.

## Future Improvements

Future enhancements could include:
1. Expanding the Hebrew glossary with more specialized terms
2. Adding a dedicated RTL formatting post-processor for all Hebrew output
3. Implementing an automatic verification step that checks for common Hebrew formatting issues
4. Creating a specialized model fine-tuned for historical Hebrew translations
5. Improving parallelization of the processing pipeline to increase throughput
6. Enhancing the reporting system to provide more detailed quality metrics