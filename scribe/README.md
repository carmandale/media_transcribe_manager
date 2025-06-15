# Scribe Translation Module

A clean, focused translation module optimized for historical interview transcripts. This module preserves authentic speech patterns and includes critical Hebrew routing logic.

## Key Features

- **Authentic Voice Preservation**: Maintains hesitations, repetitions, and natural speech patterns
- **Hebrew Auto-Routing**: Automatically routes Hebrew translations to capable providers (Microsoft/OpenAI)
- **Multi-Provider Support**: DeepL, Microsoft Translator, and OpenAI
- **Historical Focus**: Optimized for verbatim interview transcripts
- **Smart Chunking**: Handles long texts intelligently

## Installation

```python
# The module has minimal dependencies
pip install deepl  # Optional: for DeepL support
pip install openai  # Optional: for OpenAI support
pip install requests  # Required for Microsoft Translator
pip install langdetect  # Optional: for language detection
```

## Quick Start

```python
from scribe.translate import translate_text, validate_hebrew

# Simple translation
translated = translate_text(
    text="I was... I was born in Berlin in 1925.",
    target_language="de"
)

# Hebrew translation (auto-routes to Microsoft/OpenAI)
hebrew = translate_text(
    text="My father was a doctor.",
    target_language="he"
)

# Validate Hebrew content
is_hebrew = validate_hebrew(hebrew)
```

## Configuration

Set environment variables for the providers you want to use:

```bash
# DeepL (for non-Hebrew translations)
export DEEPL_API_KEY="your-key-here"

# Microsoft Translator (recommended for Hebrew)
export MS_TRANSLATOR_KEY="your-key-here"
export MS_TRANSLATOR_LOCATION="global"

# OpenAI (best quality, higher cost)
export OPENAI_API_KEY="your-key-here"
```

## Advanced Usage

```python
from scribe.translate import HistoricalTranslator

# Initialize with custom config
translator = HistoricalTranslator({
    'deepl_api_key': 'your-key',
    'ms_translator_key': 'your-key',
    'openai_api_key': 'your-key'
})

# Translate with specific provider
german = translator.translate(
    text="This is a test.",
    target_language="de",
    provider="deepl"  # Force specific provider
)

# Check language equivalence
same = translator.is_same_language("en", "eng")  # True
```

## Hebrew Translation Logic

The module includes critical logic to handle Hebrew translations correctly:

1. **DeepL doesn't support Hebrew** as a target language
2. **Automatic routing**: When Hebrew is requested, the module automatically switches to:
   - Microsoft Translator (fast, good quality)
   - OpenAI (best quality, slower)
3. **Validation**: Use `validate_hebrew()` to ensure translations contain Hebrew characters

## Speech Pattern Preservation

The module is specifically designed to preserve:

- **Hesitations**: "um", "uh", "ah", "hmm"
- **Repetitions**: "I was... I was born"
- **Self-corrections**: Natural speech corrections
- **Incomplete sentences**: Trailing thoughts with "..."
- **Natural pauses**: Indicated by ellipses or dashes

## Provider Comparison

| Provider | Hebrew Support | Speed | Quality | Cost |
|----------|---------------|-------|---------|------|
| DeepL | ❌ No | Fast | Excellent | Low |
| Microsoft | ✅ Yes | Fast | Good | Low |
| OpenAI | ✅ Yes | Slow | Excellent | High |

## Testing

Run the test script to verify your configuration:

```bash
python test_translate.py
```

This will test:
- Provider availability
- Hebrew auto-routing
- Speech pattern preservation
- Hebrew character validation

## Important Notes

1. **Historical Accuracy**: This module is optimized for historical interview transcripts where preserving authentic speech is critical
2. **No Polishing**: Translations maintain grammatical "errors" that reflect natural speech
3. **Verbatim**: All hesitations and speech patterns are preserved
4. **Hebrew Fix**: The module includes the critical fix for Hebrew translations that was failing in the original system