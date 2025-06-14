# Handoff Document: Translation Quality Improvement Test

## Context Summary

The Scribe project processes oral history interviews (Holocaust survivors) through:
1. Transcription (using ElevenLabs)
2. Translation to English, German, and Hebrew
3. Quality evaluation (1-10 scale)

**Problem**: Hebrew translations average 7.51/10 (below 8.0 target). Investigation revealed the translation prompts were NOT instructing to preserve authentic speech patterns (hesitations, "um", "uh", repetitions) despite the quality evaluation expecting these (30% weight on "Speech Pattern Fidelity").

**Solution Applied**: Updated translation prompts in `core_modules/translation.py` to explicitly preserve verbatim speech patterns.

## Your Task

Run a validation test on 10 Hebrew translation files to verify the fix improves quality scores.

## Step-by-Step Instructions

### 1. Navigate to Project
```bash
cd "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe"
```

### 2. Run the Validation Test
```bash
uv run python scripts/translation_improvement_validator.py --language he --sample-size 10
```

This will:
- Select 10 files with lowest Hebrew translation scores
- Backup current translations to `validation_backups/[timestamp]/`
- Re-translate each file with the updated system using `--formality less`
- Re-evaluate quality scores
- Compare speech pattern preservation
- Generate reports in `reports/`

### 3. Expected Timeline
- ~2-3 minutes per file (20-30 minutes total)
- Watch for progress indicators showing score changes

### 4. Review Results

After completion, check:

1. **JSON Report**: `reports/translation_validation_he_[timestamp].json`
   - Look for `summary.avg_score_before` vs `summary.avg_score_after`
   - Target: improvement from ~7.5 to 8.0+

2. **HTML Verification**: `reports/verification_he_[timestamp].html`
   - Open in browser
   - Review side-by-side comparisons
   - Check if hesitations/repetitions are preserved

### 5. Run Independent Verification

Pick one file from the results and verify independently:
```bash
# Get a file ID from the results, then:
uv run python scripts/independent_quality_check.py --file-id [FILE_ID] --language he --output-format html
```

This provides statistical validation without relying on GPT scores.

### 6. Report Back

Summarize:
1. **Score improvement**: Did average go from 7.51 → 8.0+?
2. **Speech preservation**: Are "um", "uh", repetitions now in translations?
3. **Files improved**: How many of 10 showed improvement?
4. **Red flags**: Any files that got worse or look suspicious?

## Key Files to Know

- `scripts/translation_improvement_validator.py` - Main test runner
- `scripts/independent_quality_check.py` - Statistical verification
- `core_modules/translation.py` - Contains the fixed translation prompts
- `reports/` - Where results are saved

## What Success Looks Like

- Average Hebrew score improves to 8.0+
- Translations contain more hesitations/filler words
- Statistical metrics show higher similarity to source
- No loss of historical content accuracy

## If Something Goes Wrong

1. **Import errors**: Ensure you're in project root and using `uv run python`
2. **API errors**: Check `.env` has ELEVENLABS_API_KEY and OPENAI_API_KEY
3. **No improvement**: The fix might need adjustment - check if translations actually have more "אה", "אמ" (Hebrew hesitations)

## Background (Optional Reading)

- See `docs/HISTORICAL_ACCURACY_VERIFICATION.md` for full investigation
- See `docs/TRANSLATION_ACCURACY_FIX.md` for what was changed
- Quality criteria in `scripts/historical_evaluate_quality.py`

Good luck! The test should demonstrate whether explicitly instructing the AI to preserve speech patterns improves the historical accuracy scores.