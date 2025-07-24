# Subtitle System Test Sample

This directory contains everything needed to test and validate the subtitle translation fix end-to-end.

## Test Interview
- ID: `25af0f9c-8f96-44c9-be5e-e92cb462a41f`
- Name: Friedrich Schlesinger interview (German with some English)
- Duration: ~45 minutes
- Contains mixed German/English content perfect for testing

## Directory Structure
```
test_sample/
├── README.md (this file)
├── source_files/
│   ├── 25af0f9c-8f96-44c9-be5e-e92cb462a41f.orig.srt  # Original subtitles
│   ├── 25af0f9c-8f96-44c9-be5e-e92cb462a41f.de.srt    # Current BROKEN German translation
│   └── 25af0f9c-8f96-44c9-be5e-e92cb462a41f.en.srt    # English translation
├── expected_output/
│   └── validation_points.md                             # What to check
├── scripts/
│   ├── process_test_interview.py                        # Process single interview
│   └── validate_fix.py                                  # Validate the output
└── test_data.json                                       # Metadata for test
```

## Known Issues to Fix

### 1. Language Detection Failure
- Current: langdetect identifies German text as English
- Example: "In die Wehrmacht gekommen?" detected as English (99.99% confidence!)
- Fix: Use GPT-4o-mini for accurate detection

### 2. English Not Translated
- Timestamp: 00:39:42.030
- Current: "much Jews. We know that one" (English in German subtitle)
- Expected: "viele Juden. Wir wissen das" (or similar German translation)

### 3. German Over-Translation
- German segments being unnecessarily translated to German
- Should preserve original when already in target language

## How to Test

1. **Setup Environment**
```bash
cd scribe
pip install -r requirements.txt
export OPENAI_API_KEY="your-key-here"
```

2. **Run the Fix**
```bash
python test_sample/scripts/process_test_interview.py
```

3. **Validate Results**
```bash
python test_sample/scripts/validate_fix.py
```

4. **Check with Playwright** (if viewer is running)
```bash
cd scribe-viewer
npm run test:e2e -- --grep "Subtitle System Validation"
```

## Success Criteria

✅ German segments preserved when target is German
✅ English segments translated to German
✅ Timing remains perfectly synchronized
✅ All 1835 segments processed correctly
✅ No API timeouts (batch processing working)

## API Keys Required
- OpenAI API key with access to GPT-4o-mini

## Important Files from Main Codebase
- `scribe/srt_translator.py` - Main translation logic
- `scribe/batch_language_detection.py` - Batch detection logic
- `scribe/translate.py` - Translation providers