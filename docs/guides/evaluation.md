# Translation Evaluation Guide

## Overview

Scribe uses GPT-4 to evaluate translation quality with a focus on historical accuracy and speech pattern preservation. This is crucial for maintaining the authenticity of historical testimonies.

## Evaluation Criteria

### Scoring Components (0-10 scale)

1. **Content Accuracy** (40%)
   - Factual correctness
   - No omissions or additions
   - Proper names and dates

2. **Speech Pattern Fidelity** (30%)
   - Preserves hesitations and pauses
   - Maintains speaker's rhythm
   - Keeps emotional inflections

3. **Cultural Context** (15%)
   - Historical terminology
   - Idiomatic expressions
   - Cultural references

4. **Overall Reliability** (15%)
   - Suitability for research
   - Academic quality
   - Documentation value

### Quality Thresholds

- **8.5+**: Excellent - Publication ready
- **7.0-8.4**: Good - Minor improvements needed
- **<7.0**: Needs improvement - Review required

## Running Evaluations

### Evaluate Specific Language

```bash
# Evaluate 20 Hebrew translations
uv run python scribe_cli.py evaluate he --sample 20

# Evaluate 50 German translations
uv run python scribe_cli.py evaluate de --sample 50

# Evaluate all pending English translations
uv run python scribe_cli.py evaluate en --sample 100
```

### Hebrew Evaluation Script

For batch Hebrew evaluation, use the dedicated script:

```bash
# Evaluate 50 Hebrew translations
uv run python evaluate_hebrew.py --limit 50

# Default is 10 files
uv run python evaluate_hebrew.py
```

This script:
- Automatically truncates long texts to avoid token limits
- Shows progress and statistics
- Handles various file naming patterns
- Saves results to the quality_evaluations table

### Check Individual Translation

```bash
# Evaluate a specific file's Hebrew translation
uv run python scribe_cli.py check-translation <file_id> he
```

## Current Status

As of last assessment:
- **German**: 53 evaluated, avg score 7.75
- **English**: 58 evaluated, avg score 8.58
- **Hebrew**: 113 evaluated, avg score 6.84

### Hebrew Evaluation Status
- Total Hebrew translations: 727
- Already evaluated: 113
- Remaining to evaluate: 614

**Update**: Hebrew evaluation has been fixed! (see [Hebrew Evaluation Fix PRD](../PRDs/hebrew-evaluation-fix.md))

## Evaluation Process

1. **Load Files**
   - Original transcript: `output/{file_id}/{file_id}_transcript.txt`
   - Translation: `output/{file_id}/{file_id}_{language}.txt`

2. **GPT-4 Analysis**
   - Compares translation against original
   - Checks for accuracy and completeness
   - Evaluates speech pattern preservation

3. **Score Storage**
   - Saved to `quality_evaluations` table
   - Includes issues list and comments
   - Timestamped for tracking

## Interpreting Results

### Database Query
```sql
-- View Hebrew evaluation scores
SELECT file_id, score, comment, evaluated_at 
FROM quality_evaluations 
WHERE language = 'he' 
ORDER BY evaluated_at DESC 
LIMIT 10;

-- Average scores by language
SELECT language, COUNT(*) as count, AVG(score) as avg_score 
FROM quality_evaluations 
GROUP BY language;
```

### Common Issues

1. **Low Scores (<7.0)**
   - Missing cultural context
   - Over-polished speech
   - Lost emotional markers

2. **Hebrew Specific**
   - RTL punctuation errors
   - Modern vs. historical terms
   - Transliteration inconsistencies

## Best Practices

1. **Sample Size**: Evaluate at least 20 files for reliable averages
2. **Review Low Scores**: Manually check translations scoring <7.0
3. **Model Consistency**: Use same GPT-4 model version for comparability
4. **Regular Evaluation**: Run evaluations after each translation batch

## Troubleshooting

### "No translations to evaluate"
- Check if translations are marked as completed in database
- Verify files exist in output directory

### "AttributeError: execute_query"
- This issue has been fixed!
- See [Hebrew Evaluation Fix PRD](../PRDs/hebrew-evaluation-fix.md) for details

### Inconsistent Scores
- Ensure using same evaluation model
- Check for API rate limits
- Verify transcript quality