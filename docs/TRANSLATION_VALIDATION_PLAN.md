# Translation Quality Validation Plan

## Objective
Validate that the updated translation system properly preserves authentic speech patterns and improves quality scores, especially for Hebrew translations (currently 7.51 average).

## Validation Approach

### Phase 1: Small Sample Test (10 Files)

1. **Select Test Files**
   ```bash
   # Find 10 Hebrew files with lowest scores
   uv run python scripts/translation_improvement_validator.py --language he --sample-size 10
   ```

2. **Process will:**
   - Backup current translations
   - Re-translate with new speech-preserving system
   - Re-evaluate quality scores
   - Compare before/after speech pattern metrics
   - Generate verification reports

3. **Expected Outcomes:**
   - Quality scores should improve (target: 7.51 → 8.0+)
   - Speech patterns (hesitations, repetitions) should increase
   - Translations should sound more natural/spoken

### Phase 2: Independent Verification

Since you don't speak Hebrew or German, we'll use multiple verification methods:

#### A. Statistical Verification
```bash
# Run independent metrics check
uv run python scripts/independent_quality_check.py --file-id FILE_ID --language he
```

This checks:
- Structural similarity (length ratios, punctuation density)
- Speech characteristics (fragment ratio, repetition score)
- Pause preservation (ellipses, dashes)

#### B. Native Speaker Review
The validator generates HTML reports with:
- Side-by-side source/translation excerpts
- Specific things to check (hesitations, natural flow)
- Evaluation forms for native speakers

Share these with Hebrew/German speakers for verification.

#### C. Cross-Validation Metrics
Compare:
- GPT-4 evaluation scores (before/after)
- Statistical similarity metrics
- Manual spot checks of known patterns

### Phase 3: Full Rollout

If Phase 1 shows improvement:

1. **Re-translate all low-scoring files**
   ```bash
   # Get all files scoring below 8.0
   uv run python scripts/db_query.py --format csv "SELECT file_id FROM quality_evaluations WHERE score < 8.0" > low_scores.csv
   
   # Process in batches
   uv run python scripts/process_missing_translations.py --file-list low_scores.csv --formality less --force
   ```

2. **Re-evaluate all translations**
   ```bash
   uv run python scripts/run_missing_evaluations.py --continue-on-error
   ```

3. **Generate final quality report**
   ```bash
   uv run python scripts/generate_quality_report.py --format html
   ```

## Sanity Checks

### 1. Known Pattern Test
Create test file with obvious patterns:
```
Interviewer: So, um, when did you arrive?
Survivor: I... I don't... well, it was March, March 1943.
```

Verify translation preserves:
- "um" → "ähm" (German) or "אמ" (Hebrew)
- "I... I don't..." structure
- Repeated "March, March"

### 2. Statistical Checks
Good translations should show:
- Similar punctuation density (±20%)
- Similar sentence length distribution
- Preserved paragraph structure
- Higher repetition score than polished text

### 3. Quality Score Components
Check that improved scores specifically show:
- Higher "Speech Pattern Fidelity" (was problematic)
- Maintained "Content Accuracy" (was already good)

## Red Flags to Watch For

1. **Over-improvement**: If scores jump too high (9.5+), system might be gaming the evaluation
2. **Degraded readability**: Ensure preserving speech doesn't make text incomprehensible  
3. **Lost content**: Verify no historical information is lost in pursuit of authenticity
4. **Technical errors**: Watch for RTL issues in Hebrew, character encoding problems

## Timeline

- **Day 1**: Run Phase 1 test on 10 files
- **Day 2**: Review results, get native speaker feedback
- **Day 3-4**: If successful, process remaining low-scoring files
- **Day 5**: Generate comprehensive quality report

## Success Criteria

1. **Primary**: Hebrew average score improves from 7.51 to 8.0+
2. **Secondary**: All languages maintain or improve scores
3. **Validation**: Independent metrics confirm speech preservation
4. **Sanity**: Native speakers confirm translations sound natural

## Commands Summary

```bash
# Test 10 files
uv run python scripts/translation_improvement_validator.py --language he --sample-size 10

# Check specific file independently  
uv run python scripts/independent_quality_check.py --file-id FILE_ID --language he

# Test speech preservation
uv run python scripts/test_speech_preservation.py

# Re-translate with new system
uv run python scripts/media_processor.py --file-id FILE_ID --translate-only he --formality less --force

# Check results
uv run python scripts/generate_quality_report.py
```

## Next Step
Start with the 10-file Hebrew test to validate the approach works before processing all 630+ files.