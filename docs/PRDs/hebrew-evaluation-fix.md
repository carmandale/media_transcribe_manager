# PRD: Hebrew Translation Evaluation Fix

**Status**: Completed  
**Created**: 2025-06-15  
**Author**: System Assessment

## Problem Statement

After the codebase cleanup (commit 413dad5), the Hebrew translation evaluation functionality is broken. The system successfully translated 727 files to Hebrew, but the evaluation command fails due to missing database methods and SQL query mismatches.

### Specific Issues:
1. Missing `execute_query` method in Database class (referenced in scribe_cli.py:227 and pipeline.py:227)
2. SQL queries reference non-existent `files` table (actual tables are `media_files` and `processing_status`)
3. Code expects columns like `quality_score_he` that don't exist in current schema
4. Mismatch between expected database interface and actual implementation

## Current State

### Data Status:
- **Total files**: 728
- **Hebrew translations completed**: 727 (99.9%)
- **Hebrew translations evaluated**: 208 
  - 97 unique Hebrew evaluations
  - Average score: 7.51/10
  - Using models: gpt-4.1 (avg 8.65) and historical-gpt-4 (avg 6.25)
- **Remaining to evaluate**: 519

### Working Components:
- Database with all translations intact
- Output files properly structured in `output/{file_id}/`
- Quality evaluations table functioning
- Previous evaluation data preserved

### Broken Components:
- CLI `status` command (KeyError: 'transcribed')
- CLI `evaluate` command (AttributeError: 'Database' object has no attribute 'execute_query')
- Pipeline evaluation methods
- Database query interface

## Requirements

### Functional Requirements:
1. Restore ability to evaluate Hebrew translations without data loss
2. Maintain compatibility with existing database schema
3. Resume evaluation from where it stopped (519 remaining files)
4. Preserve evaluation scoring methodology (speech pattern fidelity weighted at 30%)

### Technical Requirements:
1. Add missing database methods to match CLI expectations
2. Fix SQL queries to use correct table and column names
3. Ensure thread-safe database operations
4. Use existing evaluation logic from previous commits

### Non-Functional Requirements:
1. No changes to existing evaluated scores
2. Maintain backwards compatibility with stored data
3. Clear error messages for debugging
4. Consistent with project's historical preservation goals

## Technical Solution

### 1. Database Interface Fix
Add `execute_query` method to `scribe/database.py`:
```python
def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """Execute a SELECT query and return results as list of dicts."""
    with self.transaction() as cursor:
        cursor.execute(query, params or ())
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

### 2. SQL Query Corrections
Update queries in `scribe_cli.py` and `pipeline.py`:
- Change `FROM files` to appropriate table (`media_files` or `processing_status`)
- Remove references to `quality_score_{language}` columns
- Use proper joins between tables when needed

### 3. Evaluation Script
Create evaluation functionality based on working code from commit 8e34bd9:
- Read transcript from `output/{file_id}/{file_id}_transcript.txt`
- Read Hebrew translation from `output/{file_id}/{file_id}_he.txt`
- Use OpenAI API for quality evaluation
- Store results in `quality_evaluations` table

### 4. Integration Points
- Ensure `uv` package manager compatibility (not standard pip/venv)
- Update import statements to use `from scribe import ...` pattern
- Maintain existing database connection pooling

## Success Criteria

1. **Functionality Restored**:
   - `uv run python scribe_cli.py status` shows accurate counts
   - `uv run python scribe_cli.py evaluate he --sample 5` completes without errors
   - Evaluation scores are saved to database

2. **Data Integrity**:
   - All 208 existing evaluations remain unchanged
   - New evaluations follow same schema and scoring

3. **Performance**:
   - Evaluation of 5 files completes within 2 minutes
   - Database operations remain thread-safe

4. **Documentation**:
   - CLAUDE.md updated with working commands
   - This PRD marked as completed

## Implementation Plan

### Phase 1: Database Fix (Day 1)
1. Add `execute_query` method to database.py
2. Test with simple queries
3. Verify thread safety

### Phase 2: Query Corrections (Day 1)
1. Audit all SQL queries in codebase
2. Update to match actual schema
3. Test each CLI command

### Phase 3: Evaluation Restoration (Day 2)
1. Extract working evaluation code from git history
2. Adapt to current file structure
3. Test on 5 sample files

### Phase 4: Full Testing (Day 2)
1. Run evaluation on 20 files
2. Verify scores match expected range
3. Check database integrity

### Phase 5: Documentation (Day 3)
1. Update CLAUDE.md
2. Create evaluation guide
3. Document any gotchas

## Risks and Mitigations

### Risk: Further breaking changes
**Mitigation**: Create git branch, test thoroughly before merging

### Risk: Inconsistent evaluation scores
**Mitigation**: Compare new scores with existing 208 evaluations

### Risk: Performance degradation
**Mitigation**: Maintain batch processing, use connection pooling

## Alternative Approaches Considered

1. **Revert to previous commit**: Would lose cleanup benefits
2. **Complete rewrite**: Too risky, might introduce new bugs
3. **External evaluation script**: Would bypass existing infrastructure

## Decision

Proceed with minimal changes to restore functionality while preserving the benefits of the cleanup. Use existing working code from git history to avoid reinventing solutions.

## Implementation Results

**Completed**: 2025-06-15

### Changes Made:

1. **Added execute_query method** to database.py
   - Provides compatibility layer for legacy code
   - Returns results as list of dictionaries

2. **Fixed SQL queries** in scribe_cli.py
   - Changed `FROM files` to `FROM processing_status`
   - Updated quality score queries to use `quality_evaluations` table
   - Added missing summary keys to get_summary method

3. **Fixed SQL queries** in pipeline.py
   - Updated file selection query with proper JOIN
   - Changed INSERT to use quality_evaluations table
   - Fixed filename patterns (`.txt` instead of `_transcript.txt`)

4. **Added text truncation** to evaluate.py
   - Prevents token limit errors (max 3000 chars per text)
   - Adds truncation notice when text is cut

5. **Created evaluate_hebrew.py** script
   - Simple batch evaluation tool
   - Progress tracking and statistics
   - Handles file path variations

### Test Results:

- ✅ Status command working: Shows 727/728 Hebrew translations complete
- ✅ Detailed status working: Shows 113 Hebrew evaluations (avg 6.84/10)
- ✅ Hebrew evaluation working: Successfully evaluated 18 files
- ✅ CLI evaluate command working: Processes files with truncation

### Current State:

- Total Hebrew translations: 727
- Already evaluated: 113
- Remaining to evaluate: 614
- Average score: 6.84/10

### Usage:

```bash
# Check status
uv run python scribe_cli.py status --detailed

# Evaluate using CLI
uv run python scribe_cli.py evaluate he --sample 20

# Evaluate using script
uv run python evaluate_hebrew.py --limit 50
```

### Known Limitations:

1. Long transcripts are truncated to 3000 characters for evaluation
2. Evaluation scores may vary due to truncation
3. Some files score 0.0 when API calls fail

### Next Steps:

1. Run full evaluation on remaining 614 files
2. Review low-scoring translations (< 7.0)
3. Consider using GPT-4 Turbo for longer context window