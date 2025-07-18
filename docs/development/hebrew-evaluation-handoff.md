# Hebrew Translation Evaluation Handoff Document

**Created**: 2025-06-15  
**Updated**: 2025-06-17  
**Purpose**: Enable continuation of Hebrew translation evaluation task

> **Environment Note**: Run all commands from the repository root. The `uv` package manager uses `.venv/` for cached dependencies.

## Current Situation

### Overview
The Scribe system has successfully translated 727 historical interview transcripts to Hebrew. However, a major issue was discovered: **432 of these "Hebrew" translations are actually in English** (59% of total). Only ~295 files contain actual Hebrew text.

### Progress Status

To get current statistics, run:
```bash
# Get real-time counts
uv run python scribe_cli.py status --detailed

# Or use SQL directly
sqlite3 media_tracking.db "
  SELECT 
    (SELECT COUNT(*) FROM processing_status WHERE translation_he_status = 'completed') as total_hebrew,
    (SELECT COUNT(*) FROM quality_evaluations WHERE language = 'he' AND model != 'sanity-check') as evaluated_hebrew,
    (SELECT COUNT(*) FROM quality_evaluations WHERE language = 'he' AND model = 'sanity-check') as english_detected,
    (SELECT AVG(score) FROM quality_evaluations WHERE language = 'he' AND score > 0) as avg_score
"
```

## Task: Evaluate Remaining Hebrew Translations

### Primary Goal
Evaluate the quality of the ~175 Hebrew translations that are actually in Hebrew, while identifying and marking the 432 English files for re-translation.

### Available Tools

#### 1. Main Evaluation Script
**File**: `evaluate_hebrew_improved.py`
```bash
# Evaluate 50 files at a time
uv run python evaluate_hebrew_improved.py --limit 50

# Specify different model (accepts any OpenAI model string)
uv run python evaluate_hebrew_improved.py --limit 20 --model gpt-4.5-preview
```

**Features**:
- Uses GPT-4.1 by default (128k context window)
- Automatically detects English files and marks them with score 0 (model='sanity-check')
- Evaluates on 4 criteria: content accuracy (40%), speech patterns (30%), cultural context (15%), reliability (15%)
- Processes up to 40,000 characters per file (avoiding context limits)

#### 2. Sanity Check Script
**File**: `check_hebrew_sanity.py`
```bash
# Quick scan to identify all English files
uv run python check_hebrew_sanity.py
```
This identified 432 files that contain English instead of Hebrew.

#### 3. Original Evaluation Script
**File**: `evaluate_hebrew.py` (uses smaller context, kept for reference)

## Database Information

### Schema
- **Table**: `quality_evaluations`
- **Key columns**: file_id, language, model, score, issues, comment, evaluated_at

### Query Examples
```sql
-- Check evaluation progress
SELECT COUNT(*), AVG(score) FROM quality_evaluations WHERE language = 'he';

-- Find English files marked by sanity check
SELECT COUNT(*) FROM quality_evaluations 
WHERE language = 'he' AND model = 'sanity-check' AND score = 0.0;

-- Find unevaluated files
SELECT COUNT(*) FROM processing_status p
LEFT JOIN quality_evaluations q ON p.file_id = q.file_id AND q.language = 'he'
WHERE p.translation_he_status = 'completed' AND q.eval_id IS NULL;
```

## File Structure
```
output/
└── {file_id}/
    ├── {file_id}.txt           # Original transcript
    ├── {file_id}.he.txt        # Hebrew translation (may be English!)
    ├── {file_id}.en.txt        # English translation
    └── {file_id}.de.txt        # German translation
```

## Recommended Approach

### Step 1: Evaluate Actual Hebrew Files
Run evaluations in batches:
```bash
# Run multiple times until no more Hebrew files to evaluate
uv run python evaluate_hebrew_improved.py --limit 50
```

The script will:
- Skip files already evaluated
- Detect and mark English files (score 0.0)
- Evaluate actual Hebrew files (scores 1-10)
- Show progress statistics

### Step 2: Monitor Progress
```bash
# Check overall status
uv run python scribe_cli.py status --detailed

# Check English file detection specifically
sqlite3 media_tracking.db "
  SELECT 
    COUNT(CASE WHEN model = 'sanity-check' THEN 1 END) as english_files,
    COUNT(CASE WHEN model != 'sanity-check' THEN 1 END) as hebrew_evaluated,
    AVG(CASE WHEN score > 0 THEN score END) as avg_hebrew_score
  FROM quality_evaluations 
  WHERE language = 'he'
"
```

### Step 3: Handle English Files
After evaluation, files marked as English will need re-translation:
```bash
# Export list of English files to text file
sqlite3 media_tracking.db \
"SELECT file_id FROM quality_evaluations WHERE language='he' AND model='sanity-check'" \
> english_files.txt

# Count them
wc -l english_files.txt

# Re-translate specific files (recommended: process in batches)
uv run python scribe_cli.py translate he --limit 50 --workers 8
```

## Important Notes

1. **Always use `uv run python`** - The project uses uv package manager, not standard pip/venv

2. **API Key Required**: Ensure `OPENAI_API_KEY` is set in `.env` file

3. **Model Options**:
   - `gpt-4.1` - Default, good balance
   - `gpt-4.5-preview` - Newest, may be better
   - `gpt-4.1-mini` - Faster/cheaper

4. **Quality Thresholds**:
   - 8.5+ = Excellent
   - 7.0-8.4 = Good
   - <7.0 = Needs improvement

5. **Known Issues**:
   - Many files contain English instead of Hebrew (detected automatically)
   - Timeouts are rare with 40k character limit
   - Scores of 0.0 indicate English file (model='sanity-check')

## Expected Timeline
- ~175 Hebrew files to evaluate
- At 50 files per batch: ~4 batches
- Estimated time: 1-2 hours of processing

## Next Steps After Evaluation
1. Review files scoring <7.0 for quality issues
2. Re-translate the 432 English files to Hebrew
3. Evaluate the newly translated files
4. Generate final quality report

## Contact & Documentation
- Full documentation: [`docs/`](../README.md)
- Hebrew evaluation fix details: [`docs/PRDs/hebrew-evaluation-fix.md`](PRDs/hebrew-evaluation-fix.md)
- Original PRD explains the historical preservation goals