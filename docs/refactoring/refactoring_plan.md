# Scribe Codebase Refactoring Plan

## Overview

Based on the comprehensive improvement plan and codebase analysis, this document outlines a detailed approach for the cleanup and refactoring phase. The current codebase has completed nearly all processing (99%+) but suffers from script proliferation, inconsistent path handling, ad hoc error recovery, and database inconsistencies.

## Core Issues Identified

1. **Script Proliferation**: Over 15 small "fix-it" scripts with duplicated functionality
2. **Path Handling**: Inconsistent handling of spaces and special characters in paths
3. **Error Recovery**: Ad-hoc approach to recovering from failures
4. **Database Inconsistencies**: Status tracking in database sometimes out of sync with file system 
5. **Limited Modularity**: Long monolithic functions in core modules

## Refactoring Plan

### 1. Create New Module Structure

#### 1.1 Core Modules (Keep and Improve)
- `media_processor.py` - Break down main() function into smaller components
- `db_manager.py` - Improve transaction support and thread safety
- `file_manager.py` - Standardize path handling with pathlib
- `transcription.py` - Refactor retry logic and audio splitting
- `translation.py` - Standardize provider interfaces
- `worker_pool.py` - Enhance error recovery and monitoring

#### 1.2 New Consolidated Modules

**Create `db_maintenance.py`**
```python
# Key functions:
def fix_stalled_files(timeout_minutes=30, reset_all=False)
def fix_path_issues(path_mapping=None, verify=True)
def fix_missing_transcripts(reset_to_failed=True, batch_size=20)
def mark_problem_files(file_ids=None, status='qa_failed', reason='')
def verify_consistency(auto_fix=False, report_only=False)
def fix_hebrew_translations(batch_size=20, language_model='gpt-4o')
```

**Create `pipeline_manager.py`**
```python
# Main classes:
class PipelineMonitor:
    def check_status(self, detailed=False)
    def generate_report(self, output_format='text')
    def restart_stalled_processes(self)

class ProblemFileHandler:
    def retry_problematic_files(self, timeout_multiplier=2)
    def special_case_processing(self, file_ids=None)
    
class CommandLineInterface:
    def parse_arguments()
    def run_command(cmd, args)
    def start_parallel_pipeline(transcription_workers, translation_workers, languages)
```

### 2. Path Handling Standardization

1. **Convert to pathlib**
   - Replace all string-based path operations with `pathlib.Path`
   - Consistently use raw strings for Windows paths
   - Create path utility functions for common operations

2. **Unicode Normalization**
   - Add `unicodedata.normalize()` for paths with special characters
   - Standardize filename sanitization

3. **Shell Escaping**
   - Ensure proper escaping for all external commands
   - Use subprocess.list arguments instead of shell=True

### 3. Error Handling Improvements

1. **Centralized Error Tracking**
   - Create an `ErrorTracker` class to log and categorize errors
   - Implement tiered error types (transient, persistent, fatal)

2. **Retry Mechanisms**
   - Implement exponential backoff with proper limits
   - Add circuit breaker for API rate limiting

3. **Transaction Management**
   - Add proper transaction boundaries for database operations
   - Implement savepoints for partial batch success

### 4. Database Consistency

1. **Verification Tools**
   - Create automated database-to-filesystem verification
   - Add reconciliation functions to fix inconsistencies

2. **Status Management**
   - Standardize status transitions and validation
   - Implement proper locking for concurrent updates

3. **Query Optimization**
   - Create indexed views for common queries
   - Add batch operations for performance

### 5. Implementation Schedule

#### Week 1: Core Infrastructure

1. **Days 1-2**
   - Create `db_maintenance.py` module and core functions
   - Standardize path handling with pathlib

2. **Days 3-4**
   - Create `pipeline_manager.py` basic structure
   - Implement error tracking improvements

3. **Day 5**
   - Database consistency verification tools
   - Update documentation with new module structure

#### Week 2: Consolidation & Debugging

1. **Days 1-2**
   - Migrate all "fix-it" script functionality to new modules
   - Standardize CLI argument parsing

2. **Days 3-4**
   - Test the refactored components with problematic files
   - Address any issues found during testing

3. **Day 5**
   - Update documentation with usage examples
   - Prepare release notes for refactored codebase

## Questions for Project Clarity

1. **Resource Limitations**
   - Are there memory/CPU constraints for the processing servers?
   - What is the maximum allowed API usage rate for ElevenLabs and translation services?

2. **Priority Clarification**
   - Which language translations should be prioritized if resources are limited?
   - Are there specific files that require immediate attention?

3. **Integration Requirements**
   - Will the output files be used by other systems that require specific formats?
   - Are there strict naming conventions that must be preserved?

4. **Quality Thresholds**
   - What specific criteria determine if a file needs manual review?
   - Is there a minimum quality score for different language translations?

5. **Recovery Protocol**
   - What's the protocol for files that persistently fail processing?
   - Should problematic files be flagged for human review or skipped entirely?

## Metrics for Success

1. **Codebase Reduction**
   - Reduce total line count by 15-20% through consolidation
   - Eliminate at least 10 redundant scripts

2. **Error Reduction**
   - Decrease processing failures by 50%+
   - Eliminate path-related errors completely

3. **Consistency Improvement**
   - Database and filesystem should be 100% in sync
   - All status fields should accurately reflect processing state

4. **Documentation Quality**
   - Every module should have clear docstrings and examples
   - Create comprehensive troubleshooting guide

By implementing this plan, we aim to create a more maintainable, reliable codebase that can complete the remaining processing tasks and serve as a foundation for future enhancements.