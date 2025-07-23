# Consolidated Issue: Complete Subtitle Translation System Fix and Reprocessing

## Summary
This issue consolidates #56, #71, and #72 - all related to critical problems in the subtitle translation system that must be fixed before reprocessing 728 interviews.

## Current Problems

### 1. Language Detection Failures (from #72)
- **Issue**: Pattern matching incorrectly identifies 40% of German text as English
- **Example**: "In die Wehrmacht gekommen?" detected as English with 99.99% confidence
- **Impact**: German segments being unnecessarily translated to German, English segments not translated

### 2. Segment Boundary Violations (from #71)
- **Issue**: Translation system merges segments, causing timing desynchronization
- **Impact**: Subtitles progressively drift out of sync with audio
- **Root Cause**: Segment boundaries not preserved during translation

### 3. Language Preservation Logic (from #56)
- **Issue**: System translates ALL segments regardless of whether they're already in target language
- **Impact**: 728 interviews have over-translated subtitles
- **Example**: German interviews with English questions have English unnecessarily translated

## Solution Status

### ✅ Completed
1. Replaced `langdetect` with GPT-4o-mini for accurate language detection
2. Implemented batch language detection (50 segments per API call)
3. Fixed preservation logic to correctly handle segments already in target language
4. Added original subtitles to viewer
5. Created comprehensive test suite

### ❌ Still Needed
1. Clean up git status (remove test files, commit changes)
2. Merge segment boundary preservation from PR #70
3. Final validation with Playwright
4. Reprocess all 728 interviews
5. Close original issues

## Implementation Details

### Language Detection (GPT-4o-mini)
```python
# Batch detection for efficiency
language_map = detect_languages_for_segments(
    segments, 
    translator.openai_client,
    batch_size=50
)
```

### Preservation Logic
- Target: German
  - German segments → Keep as-is ✅
  - English segments → Translate to German ✅
  - Hebrew segments → Translate to German ✅

- Target: English
  - English segments → Keep as-is ✅
  - German segments → Translate to English ✅
  - Hebrew segments → Translate to English ✅

### Files Modified
- `scribe/srt_translator.py` - Core translation logic with GPT-4o-mini detection
- `scribe/batch_language_detection.py` - Efficient batch processing
- `scribe/translate.py` - Fixed OpenAI batch translation
- `scribe-viewer/scripts/build_manifest.py` - Added original subtitle support

## Validation Results
- Test interview: `25af0f9c-8f96-44c9-be5e-e92cb462a41f`
- Segments: 1835 total
- Timing: ✅ Perfect synchronization maintained
- German preservation: ✅ German segments kept as German
- English translation: ✅ English segments translated to German
- Example: "much Jews. We know that one" → "viele Juden. Wir wissen, dass einer"

## Next Steps
1. Clean git workspace
2. Create final commit with all changes
3. Run batch reprocessing script on all 728 interviews
4. Validate random sample of reprocessed interviews
5. Close issues #56, #71, #72

## Scripts Ready for Use
- `scripts/batch_reprocess_subtitles.py` - Reprocess all 728 interviews
- `scripts/identify_interviews_for_reprocessing.py` - Identify affected interviews

## Success Criteria
- [ ] All 728 interviews reprocessed with correct language preservation
- [ ] No timing desynchronization issues
- [ ] German segments stay German when target is German
- [ ] English segments translated when not matching target language
- [ ] All tests passing
- [ ] Clean git status

## References
- Closes #56
- Closes #71 
- Closes #72
- Incorporates fixes from PR #70