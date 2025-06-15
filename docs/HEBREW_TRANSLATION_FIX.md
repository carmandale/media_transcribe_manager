# Hebrew Translation Provider Fix Documentation

## Issue Summary
Hebrew translations were failing because the system was using DeepL as the default provider, but DeepL doesn't support Hebrew as a target language. This resulted in English translations with a "[HEBREW TRANSLATION]" prefix instead of actual Hebrew text.

## Solution Implemented (2025-06-14)
Modified the translation system to automatically detect Hebrew translation requests and switch to a Hebrew-capable provider (Microsoft Translator or OpenAI).

### Code Changes
Location: `core_modules/translation.py`

1. **In translate_file method**: Added provider selection logic for Hebrew
```python
# For Hebrew, use Microsoft or OpenAI provider instead of DeepL
if target_language.lower() in ['he', 'heb', 'hebrew']:
    if 'microsoft' in self.providers:
        hebrew_provider = 'microsoft'
    elif 'openai' in self.providers:
        hebrew_provider = 'openai'
    else:
        hebrew_provider = provider  # Fallback
```

2. **In translate_text method**: Updated DeepL Hebrew handling
```python
# Automatically switch to a Hebrew-capable provider
if target_language.lower() in ['he', 'heb', 'hebrew'] and provider == 'deepl':
    if 'microsoft' in self.providers:
        return self.translate_text(text, target_language, source_language, 'microsoft', formality)
    elif 'openai' in self.providers:
        return self.translate_text(text, target_language, source_language, 'openai', formality)
```

## Provider Comparison: Microsoft vs OpenAI

### Microsoft Translator
**Pros:**
- Native Hebrew support with proper RTL handling
- Fast processing (typically 5-15 seconds per file)
- Good preservation of punctuation and formatting
- Lower cost per character

**Cons:**
- May be more literal in translations
- Less context awareness for nuanced speech

**Cost:** ~$10 per million characters

### OpenAI (GPT-4)
**Pros:**
- Superior context understanding
- Better at preserving speech patterns and hesitations
- More natural-sounding translations
- Handles idioms and cultural references well

**Cons:**
- Slower processing (20-60 seconds per file)
- Higher cost
- Token limits may require chunking long texts

**Cost:** ~$30-60 per million tokens (roughly 4 chars/token)

## Recommendation
Use a hybrid approach:
1. **Microsoft Translator** as the primary provider for speed and cost
2. **OpenAI** for files that fail quality evaluation or need re-translation

## Configuration
Ensure these environment variables are set:
```bash
# For Microsoft Translator
MS_TRANSLATOR_KEY=your_key_here
MS_TRANSLATOR_LOCATION=global

# For OpenAI
OPENAI_API_KEY=your_key_here
```

## Testing Hebrew Translations
```bash
# Test a single file with Hebrew translation
uv run python scripts/parallel_translation.py --language he --workers 1 --batch-size 1

# Compare providers for quality and cost
uv run python scripts/compare_hebrew_providers.py --file-id FILE_ID
uv run python scripts/compare_hebrew_providers.py --sample-text "Test text here"

# Check if translation contains Hebrew characters
uv run python -c "
import sys
text = open('output/FILE_ID/FILE_ID.he.txt', 'r', encoding='utf-8').read()
has_hebrew = any('\u0590' <= c <= '\u05FF' for c in text)
print(f'Contains Hebrew: {has_hebrew}')
"
```

## Troubleshooting
1. If Hebrew translations show English text, check:
   - Provider availability in logs
   - API keys are correctly set
   - The file wasn't already processed with old system

2. To force re-translation:
   ```bash
   # Reset status in database
   sqlite3 media_tracking.db "UPDATE processing_status SET translation_he_status = 'not_started' WHERE file_id = 'FILE_ID'"
   
   # Delete old translation files
   rm output/FILE_ID/FILE_ID.he.*
   ```

## Quality Validation
Hebrew translations should preserve:
- Hesitations: "אה", "אמ", "ממ" 
- Repetitions: "אני... אני חושב"
- Incomplete sentences with "..."
- Natural speech flow

Target quality score: 8.0+ out of 10