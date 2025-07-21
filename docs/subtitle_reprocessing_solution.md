# Subtitle Reprocessing Solution - Issue #56

## Problem Summary

**Issue #56: Subtitle Translation Issue: Original Language Preservation Not Applied to 728 Interviews**

The problem: 728 interviews have **completely broken subtitles** that are unusable because they contain inaccurate paraphrases with wrong timing. This occurred because the old translation system treated translation as a text-to-text operation instead of segment-by-segment language-aware translation.

### What Was Wrong

**Example of the problem:**
- **German speaker says:** "Ich war in Berlin" (at 00:01:30)
- **Old system German subtitle:** "I was in the city" (at 00:01:35, wrong language, wrong timing, inaccurate)
- **Result:** Completely unusable - German speaker talking but subtitles show different German text at wrong times

**Root Cause:**
1. **Lost timing context** - API returned paraphrased text without timing
2. **Lost language context** - Translated everything regardless of source language  
3. **Lost transcription accuracy** - Replaced precise speech-to-text with loose translation

### What Should Happen

**With language preservation:**
- **German speaker says:** "Ich war in Berlin" (at 00:01:30)
- **German subtitle:** "Ich war in Berlin" (at 00:01:30, exact match, perfect timing)
- **English subtitle:** "I was in Berlin" (at 00:01:30, accurate translation, preserved timing)

## Solution Architecture

### Core Algorithm

```python
def reprocess_interview_subtitles(file_id, target_languages=['en', 'de', 'he']):
    """
    For each interview:
    1. Load original accurate transcription (.orig.srt)
    2. For each target language:
       - Parse segments with timing
       - Detect segment language 
       - IF segment.language == target_language: PRESERVE (keep original)
       - ELSE: TRANSLATE (but keep timing)
       - Save as .{target_language}.srt
    """
```

### Key Components

1. **Language Detection** - Segment-level detection using pattern matching + langdetect
2. **Preservation Logic** - `preserve_original_when_matching=True` parameter
3. **Timing Preservation** - Every millisecond must be preserved exactly
4. **Batch Processing** - Handle 728 interviews in manageable chunks
5. **Validation Framework** - Automated checks for timing and accuracy

## Implementation Scripts

### 1. Validation Scripts

#### Mock Validation (No API Keys Required)
```bash
python3 scripts/validate_preservation_logic_mock.py
```
- Tests preservation logic with simulated translations
- Validates timing preservation and language detection
- Generates detailed reports

#### Real API Validation (Requires API Keys)
```bash
# Set API keys first
export OPENAI_API_KEY="your-key-here"
export DEEPL_API_KEY="your-key-here"

python3 scripts/validate_with_real_api.py
```
- Tests with actual translation APIs
- Validates real translation quality
- Confirms preservation works with live APIs

### 2. Identification Script

```bash
python3 scripts/identify_interviews_for_reprocessing.py
```
- Scans output directory for interviews needing reprocessing
- Identifies files created before 2025-01-07 (before preservation fix)
- Generates detailed reprocessing plan

### 3. Batch Reprocessing Script

```bash
python3 scripts/batch_reprocess_subtitles.py
```
- Processes interviews in batches of 50
- Automatic backup before reprocessing
- Validation after each batch
- Rollback capability if issues occur

## Execution Plan

### Phase 1: Validation (Days 1-2)
1. **Run mock validation** to verify preservation logic
2. **Test with real APIs** (if available) on sample interviews
3. **Identify interviews** needing reprocessing
4. **Review generated plan** and validate sample results

### Phase 2: Batch Processing (Days 3-7)
1. **Start with pilot batch** (10-20 interviews) to validate workflow
2. **Process in phases** of 50-100 interviews at a time
3. **Validate each batch** before proceeding to next
4. **Monitor progress** and handle any errors

### Phase 3: Final Validation (Days 8-10)
1. **Comprehensive validation** of all reprocessed interviews
2. **Update web viewer** manifests and VTT files
3. **Generate final report** with statistics and results
4. **Close Issue #56** with documentation

## Expected Results

### Before (Broken)
```
German speaker: "Ich war in Berlin"
German subtitle: "I was in the city" (wrong language, wrong timing, inaccurate)
```

### After (Fixed)
```
German speaker: "Ich war in Berlin"
German subtitle: "Ich war in Berlin" (exact match, perfect timing)
English subtitle: "I was in Berlin" (accurate translation, preserved timing)
```

### Success Metrics
- **Timing Preservation**: 100% - Every millisecond preserved exactly
- **Language Preservation**: Segments in target language unchanged
- **Translation Quality**: Non-target segments properly translated
- **Format Integrity**: Valid SRT structure maintained

## Safety Features

### Backup System
- **Automatic backups** before any reprocessing
- **Batch-level organization** for easy rollback
- **Metadata tracking** for each backup

### Validation Framework
- **Timing validation** - Ensure no timing drift
- **Format validation** - Verify SRT structure integrity
- **Content validation** - Check preservation logic worked correctly

### Rollback Capability
```bash
# If issues are discovered, rollback a batch
python3 scripts/batch_reprocess_subtitles.py --rollback batch_001_20250721_120000
```

## File Structure

```
scripts/
├── validate_preservation_logic_mock.py     # Mock validation (no APIs needed)
├── validate_with_real_api.py              # Real API validation
├── identify_interviews_for_reprocessing.py # Find interviews to reprocess
└── batch_reprocess_subtitles.py           # Main batch processing script

validation_results/                         # Validation outputs
├── mock_validation_YYYYMMDD_HHMMSS/
└── real_api_validation_results/

reprocessing_backups/                       # Backup storage
├── batch_001_YYYYMMDD_HHMMSS/
├── batch_002_YYYYMMDD_HHMMSS/
└── reprocessing_report_YYYYMMDD_HHMMSS.md
```

## Usage Examples

### Quick Start (Mock Validation)
```bash
# 1. Test the preservation logic
python3 scripts/validate_preservation_logic_mock.py

# 2. Identify interviews needing reprocessing  
python3 scripts/identify_interviews_for_reprocessing.py

# 3. Review the generated plan
cat reprocessing_plan_*.json

# 4. Run batch reprocessing (when ready)
python3 scripts/batch_reprocess_subtitles.py
```

### With Real APIs
```bash
# 1. Set up API keys
export OPENAI_API_KEY="your-openai-key"
export DEEPL_API_KEY="your-deepl-key"

# 2. Validate with real APIs
python3 scripts/validate_with_real_api.py

# 3. Proceed with batch processing
python3 scripts/batch_reprocess_subtitles.py
```

## Monitoring Progress

### Log Files
- **Detailed logging** to console and files
- **Progress tracking** with batch statistics
- **Error reporting** with specific failure details

### Reports Generated
- **Validation reports** (markdown + JSON)
- **Reprocessing plans** (JSON with interview details)
- **Final summary report** (markdown with statistics)

## Troubleshooting

### Common Issues

**No API Keys Available**
- Use mock validation to test logic
- Set environment variables for real APIs
- Check API key permissions and quotas

**Database Empty**
- Scripts can work with filesystem scanning
- Use `identify_interviews_for_reprocessing.py` to scan output directory
- Database integration is optional

**Batch Processing Failures**
- Check logs for specific errors
- Use rollback functionality if needed
- Process smaller batches if issues persist

### Recovery Procedures

**If Batch Fails**
1. Check error logs for root cause
2. Use rollback script to restore backups
3. Fix underlying issue
4. Resume processing from failed batch

**If Validation Fails**
1. Review preservation logic implementation
2. Test with smaller sample files
3. Check language detection accuracy
4. Verify timing preservation

## Next Steps

1. **Run validation scripts** to confirm solution works
2. **Review generated plans** to understand scope
3. **Execute batch processing** in phases
4. **Validate final results** and update web viewer
5. **Document lessons learned** and close Issue #56

This solution will restore 728 interviews from "completely unusable" to "perfectly accurate and synchronized" subtitles.

