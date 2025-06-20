# Phase 1 Implementation Prompt for Claude

## Context
You are Claude, acting as the developer to fix critical data integrity issues in the Scribe system. The database incorrectly reports 100% Hebrew translation completion when only ~48% are actually complete (328 files have placeholders, 51 are missing).

## Your Assignment: Phase 1 - Emergency Stabilization

Begin with Task 1: Create Comprehensive System Backup

### Current Situation
- The system has 728 total files
- Hebrew translations: 349 valid, 328 with placeholders, 51 missing
- Database cannot be trusted
- We need to protect against data loss before making changes

### Task 1 Details
**Title**: Create Comprehensive System Backup
**Priority**: High
**Goal**: Create a complete, verifiable backup of the current system state

### Subtasks to Complete:

1. **Prepare Backup Directory and Timestamping** (1.1)
   - Create a backup directory structure (e.g., `backups/YYYYMMDD_HHMMSS/`)
   - Use datetime for unique timestamp
   - Ensure directory is created with proper permissions

2. **Backup Database File** (1.2)
   - Locate and backup `media_tracking.db`
   - Use atomic operations to prevent corruption
   - Verify the backup with checksum

3. **Backup Translation Directories** (1.3)
   - Backup all files in `output/` directory
   - Preserve directory structure
   - Handle large directory trees efficiently

4. **Generate and Verify Manifest File** (1.4)
   - Create a manifest.json with:
     - Total file counts per language
     - File sizes and checksums
     - Backup timestamp and system state
   - Include the validation findings (328 placeholders, 51 missing)
   - Verify manifest accuracy

### Implementation Requirements

1. **Use Python best practices**:
   - Handle exceptions properly
   - Use pathlib for cross-platform paths
   - Implement progress logging
   - Create reusable backup functions

2. **Create a backup script** (`create_backup.py`):
   - Should be runnable standalone
   - Include dry-run mode
   - Show progress for large operations
   - Generate detailed logs

3. **Testing**:
   - Create unit tests for backup functions
   - Test with corrupted/missing files
   - Verify restore capability

### Workflow Instructions

1. **For each subtask**:
   - Implement the solution
   - Test thoroughly
   - Use `update_subtask` to log your progress and findings
   - Mark subtask complete with `set_task_status`

2. **Progress Logging Example**:
   ```
   update_subtask --id=1.1 --prompt="Implemented backup directory creation with timestamp. 
   Used pathlib for cross-platform compatibility. Added error handling for permission issues.
   Tested with various timestamps to ensure uniqueness."
   ```

3. **After completing all subtasks**, prepare a summary including:
   - What was implemented
   - Key decisions made
   - Test results
   - Location of backup and manifest
   - Any issues encountered
   - Verification steps for supervisor

### Expected Deliverables

1. `create_backup.py` - Main backup script
2. `test_backup.py` - Test suite
3. A successful backup in `backups/[timestamp]/`
4. `manifest.json` with complete system state
5. Implementation summary for supervisor review

### Important Notes

- The current validation script (`validate_all_translations.py`) exists and can be referenced
- Existing validation results are in `validation_report.txt` and `validation_issues.json`
- Be extra careful with the database - it's our only source of truth (even if incorrect)
- Document any anomalies you discover during backup

Begin implementation now. Start with subtask 1.1 and work through them sequentially. 