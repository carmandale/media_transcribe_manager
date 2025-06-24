# Phase 2, Task 5 Implementation Prompt for Claude

## Critical Update from Review

Before starting, please address these CRITICAL issues:

1. **URGENT Model Updates Required**:
   - **Current system uses GPT-4.5 for evaluation at $213.75 for 379 files!**
   - **GPT-4.5 is retiring July 14, 2025 (less than a month!)**
   - **Recommended**: Use `gpt-4.1` for both translation and evaluation
   
2. **Actual Model Pricing** (as of June 20, 2025):
   ```
   Model         Input/Output per 1M tokens    379 files cost
   --------------------------------------------------------
   GPT-4.5      $75/$150                      $213.75 (DO NOT USE)
   GPT-4-Turbo  $10/$30                       $38.00 (current)
   GPT-4.1      $2/$8                         $9.50 (RECOMMENDED)
   GPT-4.1-mini $0.40/$1.60                   $1.90
   GPT-4o       $5/$20                        $23.75
   GPT-4o-mini  $0.60/$2.40                   $2.85
   ```

3. **Cost Optimization**:
   - Current approach: $251.75 (Turbo translation + GPT-4.5 evaluation)
   - Recommended: $19.00 (GPT-4.1 for both) - **92% savings!**
   - Budget option: $3.15 (GPT-4.1-mini translation + spot evaluation)

3. **Update Task 4 Status**:
   ```bash
   # Update all Task 4 subtasks
   task-master set-status --id=4.1 --status=done
   task-master set-status --id=4.2 --status=done
   task-master set-status --id=4.3 --status=done
   task-master set-status --id=4.4 --status=done
   task-master set-status --id=4.5 --status=done
   task-master set-status --id=4 --status=done
   ```

## Your Assignment: Task 5 - Implement Parallel Hebrew Translation Pipeline

### Context
With the OpenAI integration complete, we now need to process 379 Hebrew files:
- 328 files with "[HEBREW TRANSLATION]" placeholders  
- 51 completely missing Hebrew files

The audit report (`audit_report.json`) contains the exact list of files needing translation.

### Task 5 Goal
Create an efficient parallel processing pipeline that:
1. Reads the 379 problematic files from the audit
2. Loads English source texts
3. Translates to Hebrew using the OpenAI integration
4. Saves new Hebrew files
5. Updates database status
6. Provides detailed progress and error reporting

### Subtask Breakdown

#### Subtask 5.1: Design Pipeline Architecture
1. Create `HebrewTranslationPipeline` class that orchestrates:
   - Loading audit results
   - Managing file I/O
   - Coordinating translation workers
   - Tracking progress
   - Handling errors
2. Design for resumability (skip already completed)
3. Plan database update strategy

#### Subtask 5.2: Implement File Reading and Queuing
1. Parse `audit_report.json` to get file lists:
   - `discrepancies.placeholder_file` (328 files)
   - `discrepancies.missing_file` (51 files)
2. For each file:
   - Build path: `output/{file_id}/{file_id}.en.txt`
   - Read English content
   - Queue for translation
3. Handle missing English source files gracefully

#### Subtask 5.3: Integrate Translation API Calls
1. Use existing `HebrewTranslator` from `openai_integration.py`
2. Update model to `gpt-4.1` (recommended) or keep `gpt-4-turbo-preview` if quality proven
3. Update evaluation model from `gpt-4.5-preview` to `gpt-4.1` (URGENT - 4.5 retiring!)
4. Implement batch processing with progress callbacks
5. Add quality checks for Hebrew output

#### Subtask 5.4: Handle Concurrency and Rate Limiting
1. Use asyncio with controlled concurrency:
   - `gpt-4.1`: 10-15 concurrent requests (good rate limits)
   - `gpt-4.1-mini`: 15-20 concurrent requests  
   - `gpt-4-turbo-preview`: 5-10 concurrent requests (more expensive tier)
2. Monitor rate limits and adjust dynamically
3. Implement graceful backoff on rate limit errors

#### Subtask 5.5: Save Translated Files
1. Save Hebrew translations to: `output/{file_id}/{file_id}.he.txt`
2. Ensure proper UTF-8 encoding
3. Verify file was written successfully
4. Create backup of original if replacing

#### Subtask 5.6: Monitor Progress and Handle Errors
1. Real-time progress display
2. Detailed error logging with recovery options
3. Summary report at completion
4. Update database status for successful translations

### Required Deliverables

1. **Main Pipeline**: `hebrew_translation_pipeline.py`
   ```python
   import asyncio
   import json
   from pathlib import Path
   from typing import List, Dict, Tuple
   import aiofiles
   from datetime import datetime
   
   from openai_integration import HebrewTranslator
   from audit_system import FileStatus
   from fix_database_status import DatabaseStatusFixer
   
   class HebrewTranslationPipeline:
       def __init__(
           self,
           audit_report_path: Path,
           output_dir: Path,
           translator: HebrewTranslator,
           max_concurrent: int = 10
       ):
           # Implementation here
   ```

2. **Test Suite**: `test_translation_pipeline.py`
   - Test file reading/writing
   - Test error handling
   - Test progress tracking
   - Test database updates

3. **Execution Script**: `run_hebrew_translation.py`
   - Command-line interface
   - Model selection (gpt-4.1 recommended, gpt-4.1-mini for budget, gpt-4-turbo-preview current)
   - Dry-run mode
   - Cost estimation before starting with urgent GPT-4.5 retirement warning

### Implementation Requirements

1. **File Processing**:
   ```python
   async def process_file(self, file_id: str, issue_type: str) -> bool:
       """Process a single file translation."""
       try:
           # Build paths
           en_path = self.output_dir / file_id / f"{file_id}.en.txt"
           he_path = self.output_dir / file_id / f"{file_id}.he.txt"
           
           # Read English source
           async with aiofiles.open(en_path, 'r', encoding='utf-8') as f:
               english_text = await f.read()
           
           # Skip if empty
           if not english_text.strip():
               logger.warning(f"Empty English file: {file_id}")
               return False
           
           # Translate
           hebrew_text = await self.translator.translate(
               english_text,
               file_id
           )
           
           # Save Hebrew
           async with aiofiles.open(he_path, 'w', encoding='utf-8') as f:
               await f.write(hebrew_text)
           
           return True
       except Exception as e:
           logger.error(f"Failed to process {file_id}: {e}")
           return False
   ```

2. **Progress Tracking**:
   - Display: `[===>    ] 125/379 (33.0%) - 2.5 files/min - ETA: 1h 42m`
   - Log every 10 files
   - Save checkpoint every 25 files

3. **Error Recovery**:
   - Automatic retry for transient errors
   - Skip and log permanently failed files
   - Generate error report at end

4. **Database Updates**:
   - Update `translation_he_status` to 'completed' for successful translations
   - Keep 'failed' status for files that couldn't be translated
   - Update timestamps

### Cost Management

```python
# Before starting, show cost estimate
def estimate_pipeline_cost(file_count: int, avg_file_size: int) -> Dict:
    models = {
        "gpt-4.5": {"input": 75/1000, "output": 150/1000},  # RETIRING JULY 14!
        "gpt-4-turbo-preview": {"input": 10/1000, "output": 30/1000},
        "gpt-4.1": {"input": 2/1000, "output": 8/1000},
        "gpt-4.1-mini": {"input": 0.40/1000, "output": 1.60/1000},
        "gpt-4o": {"input": 5/1000, "output": 20/1000}
    }
    
    # Calculate for each model
    for model, pricing in models.items():
        # ... calculation logic
    
    return estimates

# Example output:
# Model gpt-4.5: 379 files, $213.75 (RETIRING JULY 14!)
# Model gpt-4-turbo-preview: 379 files, $38.00 (current)
# Model gpt-4.1: 379 files, $9.50 (RECOMMENDED)
# Model gpt-4.1-mini: 379 files, $1.90 (budget option)
# Proceed with gpt-4.1? [Y/n]:
```

### Testing Approach

1. **Dry Run Test**:
   - Process 5 files without saving
   - Verify translation quality
   - Check cost tracking

2. **Small Batch Test**:
   - Process 10 real files
   - Verify all components work
   - Check database updates

3. **Full Run**:
   - Process all 379 files
   - Monitor for issues
   - Generate final report

### Success Criteria

1. All 379 files successfully translated or logged as failed
2. Hebrew files created with proper UTF-8 encoding
3. Database updated to reflect true completion status
4. Total cost within estimates
5. Detailed report generated with:
   - Success/failure counts
   - Total API costs
   - Time taken
   - Any files requiring manual review

### Example Usage

```bash
# Estimate costs
python run_hebrew_translation.py --estimate

# Dry run with 5 files
python run_hebrew_translation.py --dry-run --limit 5

# Run with recommended model (best value)
python run_hebrew_translation.py --model gpt-4.1

# Run with budget model
python run_hebrew_translation.py --model gpt-4.1-mini

# Run with current expensive model (not recommended)
python run_hebrew_translation.py --model gpt-4-turbo-preview

# Resume from interruption
python run_hebrew_translation.py --resume
```

### After Completion

Provide a comprehensive summary including:
1. Total files processed successfully
2. Failed files (if any) with reasons
3. Total API cost
4. Processing time and rate
5. Database update confirmation
6. Final Hebrew completion percentage
7. Recommendations for any manual review needed

Remember to update Taskmaster with progress on each subtask as you complete them. 