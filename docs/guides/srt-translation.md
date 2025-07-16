# SRT Translation with Language Preservation Guide

## Overview

The SRT translation feature intelligently translates subtitle files while preserving segments that are already in the target language. This is particularly useful for mixed-language interviews where interviewers and interviewees speak different languages.

## Key Features

- **Language Detection**: Automatically detects the language of each subtitle segment
- **Selective Translation**: Only translates segments not already in the target language
- **Timing Preservation**: Maintains exact subtitle timing from the original
- **Mixed-Language Support**: Handles interviews with multiple languages seamlessly

## Usage

### Basic Translation Command

```bash
# Translate SRT files to English (preserves English segments)
uv run python scribe_cli.py translate-srt en --workers 8

# Translate to German (preserves German segments)
uv run python scribe_cli.py translate-srt de --workers 8

# Translate to Hebrew
uv run python scribe_cli.py translate-srt he --workers 8
```

### Options

- `--workers, -w`: Number of parallel workers (default: 8)
- `--limit, -l`: Maximum files to process
- `--model, -m`: Specify OpenAI model (default: gpt-4.1-mini)
- `--no-preserve`: Translate all segments (don't preserve target language)

### Force Full Translation

If you need to translate all segments regardless of language:

```bash
uv run python scribe_cli.py translate-srt en --no-preserve
```

## Example Scenario

For a German interview with English questions:

**Original SRT:**
```
1
00:00:00,000 --> 00:00:03,000
Good morning. How are you today?

2
00:00:03,500 --> 00:00:07,000
Guten Morgen. Mir geht es gut, danke.

3
00:00:07,500 --> 00:00:10,000
Can you tell me about your experience?

4
00:00:10,500 --> 00:00:15,000
Ja, es war eine sehr schwierige Zeit.
```

**English Translation Result:**
```
1
00:00:00,000 --> 00:00:03,000
Good morning. How are you today?  [PRESERVED]

2
00:00:03,500 --> 00:00:07,000
Good morning. I'm doing well, thank you.  [TRANSLATED]

3
00:00:07,500 --> 00:00:10,000
Can you tell me about your experience?  [PRESERVED]

4
00:00:10,500 --> 00:00:15,000
Yes, it was a very difficult time.  [TRANSLATED]
```

## Cost Estimates

Using GPT-4.1-mini (recommended):
- **Input**: $0.15 per 1M tokens
- **Output**: $0.60 per 1M tokens
- **Total for 726 files**: ~$3-5 with language preservation

## Best Practices

1. **Use Language Preservation**: Reduces costs by 30-40% and maintains authenticity
2. **Process in Batches**: Use `--limit` to process files incrementally
3. **Monitor Progress**: Check logs for any failed translations
4. **Consistent Model**: Use the same model (gpt-4.1-mini) for all languages

## Technical Details

The system uses:
- Pattern matching for basic language detection
- `langdetect` library when available for more accurate detection
- Preserves exact timing from original SRT files
- Handles multi-line subtitles correctly
- Routes Hebrew translations to OpenAI (DeepL doesn't support Hebrew)

## Troubleshooting

If translations are not preserving segments correctly:
1. Check that the original SRT has proper formatting
2. Verify language detection is working (check logs)
3. Use `--no-preserve` flag to force full translation
4. Ensure sufficient API credits for your chosen provider