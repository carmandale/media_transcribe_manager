# Remote Agent Setup Guide - Subtitle Translation Fix

## Overview
You are tasked with fixing a critical subtitle translation system that affects 728 interview videos. The system currently has broken language detection causing:
1. German text being detected as English
2. English segments not being translated in German interviews  
3. Segments being over-translated when already in target language

## Quick Start

### 1. Environment Setup
```bash
cd scribe
pip install -r requirements.txt
export OPENAI_API_KEY="your-openai-api-key"
```

### 2. Test the Fix
```bash
cd test_sample/scripts
python process_test_interview.py
python validate_fix.py
```

### 3. If Tests Pass
```bash
cd ../..
python scripts/batch_reprocess_subtitles.py
```

## The Problem in Detail

### Current Broken Behavior
- Interview: German speaker with some English phrases
- Target: German subtitles
- Current output: English phrases remain in English (NOT translated)
- Example: At 00:39:42.030, "much Jews. We know that one" appears in German subtitle file

### Root Cause
The `langdetect` library catastrophically fails on German text:
- "In die Wehrmacht gekommen?" → Detected as English (99.99% confidence!)
- ~40% of German text misidentified as English
- This breaks the entire translation logic

## The Solution

### 1. Replace Language Detection
- Remove `langdetect` 
- Use GPT-4o-mini for accurate language detection
- Batch process 50 segments per API call for efficiency

### 2. Fix Preservation Logic
```python
# OLD (broken):
if segment.detected_language and segment.detected_language != target_language:
    should_translate = True

# NEW (fixed):
should_translate = self.should_translate_segment(segment, target_language)
```

### 3. Key Files to Modify
- `scribe/srt_translator.py` - Main translation logic
- `scribe/batch_language_detection.py` - Batch detection implementation

## Test Sample Structure
```
test_sample/
├── source_files/          # Original subtitle files  
├── expected_output/       # Validation checklist
├── scripts/              # Processing & validation scripts
└── test_data.json        # Test metadata & expectations
```

## Validation Checklist

### Must Pass ALL:
- [ ] Segment count preserved (1835 in = 1835 out)
- [ ] English "much Jews" translated to German "viele Juden"  
- [ ] German "Wehrmacht" remains unchanged
- [ ] All timestamps identical to original
- [ ] No API timeouts (batch processing working)
- [ ] Process completes in < 2 minutes

## Implementation Steps

### Step 1: Verify Current Broken State
```bash
grep "much Jews" test_sample/source_files/*.de.srt
# Should show the English text in German subtitle
```

### Step 2: Run the Fix
```bash
python test_sample/scripts/process_test_interview.py
```

### Step 3: Validate Fix Worked
```bash
python test_sample/scripts/validate_fix.py
# All tests should pass
```

### Step 4: Test with Viewer (Optional)
```bash
cd scribe-viewer
npm run dev
# Visit http://localhost:3000/interviews/25af0f9c-8f96-44c9-be5e-e92cb462a41f
# Check subtitles at 39:42 - should show German translation
```

### Step 5: Process All Interviews
```bash
python scripts/batch_reprocess_subtitles.py
# This will process all 728 interviews
```

## Critical Code Sections

### Language Detection (batch_language_detection.py)
```python
def detect_languages_for_segments(segments, openai_client, batch_size=50):
    """Detect languages for all segments efficiently using batching."""
    # Groups segments and sends to GPT-4o-mini in batches
```

### Preservation Logic (srt_translator.py)
```python
def should_translate_segment(self, segment: SRTSegment, target_language: str) -> bool:
    """Universal rule: Only translate if NOT already in target language"""
    if segment.detected_language == target_language:
        return False  # Preserve
    return True  # Translate
```

## Expected Outcomes

### Per Interview:
- API calls: ~50 (vs 1835 without batching)
- Processing time: 1-2 minutes
- Cost: ~$0.02

### For All 728 Interviews:
- Total time: ~20 hours
- Total cost: ~$15
- All subtitles correctly translated and preserved

## Troubleshooting

### "API Key Not Set"
```bash
export OPENAI_API_KEY="sk-..."
```

### "Import Error"
```bash
cd scribe  # Must run from scribe directory
pip install -r requirements.txt
```

### "File Not Found"  
Check you're in the right directory. All paths are relative to `scribe/`

### "Tests Failing"
1. Check API key has GPT-4o-mini access
2. Ensure no local modifications to the fix
3. Review error messages in detail

## Final Verification

After processing all interviews:
1. Spot check 5-10 random interviews
2. Verify German segments remain German
3. Verify English segments are translated
4. Check timing synchronization
5. Confirm no empty/missing subtitles

## Questions?

Refer to:
- `CONSOLIDATED_SUBTITLE_ISSUE.md` - Detailed issue description
- `test_sample/expected_output/validation_points.md` - What to check
- Source code comments in modified files

Good luck! The fix has been validated and is ready for production use.