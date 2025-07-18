# Phase 1, Task 2 Implementation Prompt for Claude

## Pre-Task Actions

Before starting Task 2, please update the Taskmaster status for Task 1:

```bash
# Update subtask statuses
task-master set-status --id=1.1 --status=done
task-master set-status --id=1.2 --status=done
task-master set-status --id=1.3 --status=done
task-master set-status --id=1.4 --status=done

# Update main task status
task-master set-status --id=1 --status=done
```

## Your Assignment: Task 2 - Implement Comprehensive Audit Script

### Context
Task 1 is complete and approved. The backup captured 379 Hebrew translation issues. Now we need to create a comprehensive audit script that can systematically identify all discrepancies between the database and filesystem.

### Current Situation
- Database reports 100% completion for Hebrew translations
- Reality: Only ~48% actually complete (349 valid, 328 with placeholders, 51 missing)
- The existing `validate_all_translations.py` script has limitations
- We need a more robust audit system with async performance

### Task 2 Details
**Title**: Implement Comprehensive Audit Script
**Priority**: High
**Goal**: Create an audit system that accurately identifies all data integrity issues

### Subtasks to Complete:

1. **Design Audit Data Structures** (2.1)
   - Define schemas for file metadata
   - Structure for database records
   - Format for discrepancy tracking
   - Ensure efficient comparison capabilities

2. **Implement Async File Reading and Analysis** (2.2)
   - Use Python asyncio for performance
   - Read files asynchronously
   - Detect placeholders and language
   - Calculate checksums for verification

3. **Compare Database and Filesystem** (2.3)
   - Cross-reference all database entries with files
   - Identify missing files
   - Find orphaned files (exist but not in DB)
   - Track status mismatches

4. **Generate JSON Report with Statistics** (2.4)
   - Comprehensive statistics per language
   - Detailed discrepancy lists
   - Summary counts and percentages
   - Machine-readable format for downstream processing

5. **Validate Against Known Issues** (2.5)
   - Must find exactly 328 Hebrew files with placeholders
   - Must identify exactly 51 missing Hebrew files
   - Verify against the existing validation results

### Implementation Requirements

1. **Create `audit_system.py`** with:
   - Async/await patterns for file I/O
   - Progress reporting for long operations
   - Comprehensive error handling
   - Memory-efficient processing for 7,000+ files

2. **Key Features to Implement**:
   ```python
   # Hebrew character detection
   def contains_hebrew(text):
       return any('\u0590' <= c <= '\u05FF' for c in text)
   
   # Placeholder detection
   def has_placeholder(text):
       return '[HEBREW TRANSLATION]' in text or '[GERMAN TRANSLATION]' in text
   
   # Async file analysis
   async def analyze_translation_file(file_path):
       # Read file content
       # Check language
       # Detect placeholders
       # Calculate metrics
       # Return structured data
   ```

3. **Database Analysis**:
   - Connect to `media_tracking.db`
   - Query translation status for all files
   - Build lookup structures for efficient comparison

4. **Output Format** (audit_report.json):
   ```json
   {
     "audit_timestamp": "2025-06-20T14:00:00",
     "summary": {
       "total_files_in_db": 728,
       "total_files_on_disk": 677,
       "languages": {
         "en": {"expected": 728, "found": 728, "valid": 728},
         "de": {"expected": 728, "found": 728, "valid": 728},
         "he": {"expected": 728, "found": 677, "valid": 349, "placeholders": 328}
       }
     },
     "discrepancies": {
       "missing_files": [...],
       "placeholder_files": [...],
       "orphaned_files": [...],
       "status_mismatches": [...]
     }
   }
   ```

### Testing Requirements

1. **Create `test_audit_system.py`**:
   - Test with known good/bad files
   - Verify placeholder detection
   - Test Hebrew character detection
   - Ensure async performance

2. **Validation Criteria**:
   - Must identify all 328 placeholder files
   - Must find all 51 missing Hebrew files
   - Total Hebrew issues must equal 379
   - Performance: Complete audit in < 30 seconds

### Workflow Instructions

1. **Start with subtask 2.1**: Design the data structures first
2. **Use `update_subtask`** to log progress on each subtask
3. **Test incrementally** - don't wait until the end
4. **Compare results** with existing validation files
5. **Mark subtasks complete** as you finish them

### Expected Deliverables

1. `audit_system.py` - Main audit script
2. `test_audit_system.py` - Comprehensive test suite
3. `audit_report.json` - Generated audit report
4. Verification that findings match known issues (379 total)
5. Performance metrics showing < 30 second execution

### Important Notes

- The existing `validate_all_translations.py` can be referenced but has limitations
- Focus on accuracy first, then optimize for performance
- The audit must be repeatable and deterministic
- Progress reporting is essential for user feedback
- Handle edge cases (corrupted files, permission errors, etc.)

Begin implementation now. Start with subtask 2.1: Design Audit Data Structures.

### Success Criteria

Your audit system will be considered successful when:
1. It correctly identifies all 328 Hebrew placeholder files
2. It correctly identifies all 51 missing Hebrew files  
3. It provides detailed, actionable information about each discrepancy
4. It completes the full audit in under 30 seconds
5. The output can be used to fix the database in Task 3 