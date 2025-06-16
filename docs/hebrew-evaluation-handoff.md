# Hebrew Translation Evaluation Handoff Document

**Created**: 2025-06-15  
**Purpose**: Enable continuation of Hebrew translation evaluation task

## Current Situation

### Overview
The Scribe system has successfully translated 727 historical interview transcripts to Hebrew. However, a major issue was discovered: **432 of these "Hebrew" translations are actually in English** (59% of total). Only ~295 files contain actual Hebrew text.

### Progress Status
- **Total Hebrew translations**: 727
- **Already evaluated**: 120 (as of last check)
- **Remaining to evaluate**: 607
  - **Actually in English**: 432 files (need re-translation)
  - **Actually in Hebrew**: ~175 files (need evaluation)
- **Average quality score**: 6.76/10

## Task: Evaluate Remaining Hebrew Translations

### Primary Goal
Evaluate the quality of the ~175 Hebrew translations that are actually in Hebrew, while identifying and marking the 432 English files for re-translation.

### Available Tools

#### 1. Main Evaluation Script
**File**: `evaluate_hebrew_improved.py`
```bash
# Evaluate 50 files at a time
uv run python evaluate_hebrew_improved.py --limit 50

# Specify different model
uv run python evaluate_hebrew_improved.py --limit 20 --model gpt-4.5-preview
```

**Features**:
- Uses GPT-4.1 by default (128k context window)
- Automatically detects English files and marks them with score 0
- Evaluates on 4 criteria: content accuracy (40%), speech patterns (30%), cultural context (15%), reliability (15%)
- Processes up to 40,000 characters per file

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

# Check evaluation progress
sqlite3 media_tracking.db "SELECT COUNT(*), AVG(score) FROM quality_evaluations WHERE language = 'he' AND score > 0;"
```

### Step 3: Handle English Files
After evaluation, 432 files will need re-translation to Hebrew:
```bash
# Get list of English files
sqlite3 media_tracking.db "SELECT file_id FROM quality_evaluations WHERE language = 'he' AND model = 'sanity-check';"

# These will need to be re-translated using:
uv run python scribe_cli.py translate he --workers 8
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
   - 432 files contain English instead of Hebrew
   - Some evaluations may timeout on very long files
   - Scores of 0.0 indicate either English file or API error

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
- Full documentation: `docs/`
- Hebrew evaluation fix details: `docs/PRDs/hebrew-evaluation-fix.md`
- Original PRD explains the historical preservation goals