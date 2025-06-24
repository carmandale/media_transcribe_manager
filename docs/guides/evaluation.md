# Translation Evaluation Guide

## Overview

Scribe uses GPT-4 to evaluate translation quality with a focus on historical accuracy and speech pattern preservation. This is crucial for maintaining the authenticity of historical testimonies.

**Enhanced Hebrew Evaluation**: Hebrew translations now include sanity checks, language detection, and specialized evaluation criteria using GPT-4.1 by default.

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
# Evaluate Hebrew translations with enhanced mode (recommended)
uv run python scribe_cli.py evaluate he --sample 20 --enhanced --model gpt-4.1

# Basic Hebrew evaluation
uv run python scribe_cli.py evaluate he --sample 20

# Evaluate German translations
uv run python scribe_cli.py evaluate de --sample 50

# Evaluate English translations
uv run python scribe_cli.py evaluate en --sample 100
```

### Enhanced Hebrew Evaluation

The `--enhanced` flag for Hebrew provides:

- **Sanity Checks**: Verifies Hebrew characters are present
- **Language Detection**: Prevents English/placeholder content from being marked as valid
- **Hebrew-specific Analysis**: Specialized evaluation criteria for Hebrew text
- **Detailed Reporting**: Hebrew-specific warnings and recommendations

```bash
# Enhanced Hebrew evaluation with custom model
uv run python scribe_cli.py evaluate he --sample 30 --enhanced --model gpt-4.1

# Enhanced evaluation results include:
# - Hebrew character ratio analysis
# - Sanity check failures
# - Language detection warnings
# - Hebrew-specific quality metrics
```

### Legacy Hebrew Evaluation Scripts

**Note**: These scripts are now superseded by the enhanced evaluation mode in the main CLI.

For compatibility, the legacy script is still available:

```bash
# Legacy Hebrew evaluation script (deprecated)
uv run python evaluate_hebrew.py --limit 50
```

**Recommended**: Use enhanced mode instead:
```bash
uv run python scribe_cli.py evaluate he --sample 50 --enhanced
```

The enhanced mode provides all the features of the legacy script plus:
- Better integration with the main CLI
- Improved Hebrew validation
- Consistent reporting format
- Better error handling

### Check Individual Translation

```bash
# Evaluate a specific file's Hebrew translation
uv run python scribe_cli.py check-translation <file_id> he
```

## Enhanced Hebrew Features

### Sanity Checks

The enhanced Hebrew evaluation includes automatic sanity checks:

- **Hebrew Character Detection**: Ensures translations contain Hebrew text
- **Language Validation**: Detects English text masquerading as Hebrew
- **Character Ratio Analysis**: Warns about low Hebrew character ratios
- **Placeholder Detection**: Identifies template or error text

### Hebrew-Specific Analysis

Enhanced mode provides specialized Hebrew evaluation:

- **RTL Text Handling**: Proper right-to-left text evaluation
- **Hebrew Linguistics**: Understanding of Hebrew grammar and structure
- **Cultural Context**: Recognition of Hebrew cultural and historical references
- **Transliteration Quality**: Assessment of name and place transliterations

### Reporting

Detailed Hebrew reporting includes:

```
Evaluated 20 translations:
Average score: 7.8/10
Range: 6.2 - 9.1

Quality breakdown:
Excellent (8.5+): 8
Good (7.0-8.4): 10
Needs improvement (<7.0): 2

Hebrew-specific analysis:
⚠️  Files with no Hebrew characters: 1
⚠️  Files with low Hebrew ratio: 3
Common issues: {'NO_HEBREW_CHARACTERS': 1, 'LOW_HEBREW_RATIO': 3}
Common warnings: {'HEBREW_RATIO_LOW': 3}
```

## Evaluation Process

### Standard Evaluation

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

### Enhanced Hebrew Evaluation Process

1. **Pre-validation**
   - Hebrew character presence check
   - Language detection validation
   - Character ratio analysis

2. **Enhanced GPT Analysis**
   - Uses GPT-4.1 model for better Hebrew understanding
   - Hebrew-specific prompts and criteria
   - Cultural and linguistic context awareness

3. **Hebrew-Specific Reporting**
   - Detailed validation results
   - Hebrew-specific warnings and recommendations
   - Sanity check outcomes

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

2. **Hebrew Specific (Enhanced Mode Detects)**
   - **NO_HEBREW_CHARACTERS**: Translation contains no Hebrew text
   - **LOW_HEBREW_RATIO**: Less than 50% Hebrew characters
   - **ENGLISH_DETECTED**: English text instead of Hebrew translation
   - **PLACEHOLDER_TEXT**: Template or error messages
   - **RTL_FORMATTING**: Right-to-left formatting issues
   - **TRANSLITERATION**: Inconsistent name/place transliterations

3. **Enhanced Mode Warnings**
   - **HEBREW_RATIO_LOW**: Hebrew character ratio below optimal threshold
   - **MIXED_LANGUAGE**: Contains significant non-Hebrew text
   - **ENCODING_ISSUES**: Character encoding problems

## Best Practices

1. **Sample Size**: Evaluate at least 20 files for reliable averages
2. **Review Low Scores**: Manually check translations scoring <7.0
3. **Model Consistency**: Use same GPT-4 model version for comparability
4. **Regular Evaluation**: Run evaluations after each translation batch
5. **Enhanced Mode for Hebrew**: Always use `--enhanced` flag for Hebrew evaluations
6. **Monitor Sanity Checks**: Address files flagged with Hebrew validation issues
7. **Use GPT-4.1 for Hebrew**: Recommended model for Hebrew language understanding

## Troubleshooting

### "No translations to evaluate"
- Check if translations are marked as completed in database
- Verify files exist in output directory

### Hebrew Validation Failures

**No Hebrew Characters Found**:
```bash
# Check the specific file
uv run python scribe_cli.py check-translation <file_id> he

# Re-translate if needed
uv run python scribe_cli.py translate he --limit 1
```

**Low Hebrew Character Ratio**:
- May indicate translation quality issues
- Consider re-translating problematic files
- Check if original transcript contains significant non-Hebrew content

**"AttributeError: execute_query"**:
- This issue has been fixed!
- See [Hebrew Evaluation Fix PRD](../PRDs/hebrew-evaluation-fix.md) for details

### Inconsistent Scores
- Ensure using same evaluation model
- Check for API rate limits
- Verify transcript quality