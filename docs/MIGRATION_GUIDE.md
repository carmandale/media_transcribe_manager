# Migration Guide: Legacy Scripts to Consolidated Commands

This document provides guidance on the transition from legacy scripts to the new consolidated command structure in the Scribe project.

## Overview

The Scribe project is being refactored to improve maintainability, reduce code duplication, and fix resource management issues. As part of this effort, functionality from multiple single-purpose scripts is being consolidated into a few core modules:

- **db_connection_pool.py**: Thread-safe connection pooling for SQLite
- **db_manager.py**: Unified database access layer with pooled connections
- **db_maintenance.py**: Database maintenance and repair operations
- **pipeline_manager.py**: Pipeline orchestration and monitoring
- **scribe_manager.py**: Unified command-line interface for all operations

## Legacy Script Mapping

The following legacy scripts have been replaced with new consolidated commands. Both old and new commands are currently supported for backward compatibility, but the legacy scripts will be deprecated in the future.

### Group 1: Database Maintenance Scripts (Migration Complete)

| Legacy Script | New Command |
|---------------|------------|
| fix_stalled_files.py | `python scribe_manager.py fix stalled` |
| fix_path_issues.py | `python scribe_manager.py fix paths` |
| fix_transcript_status.py | `python scribe_manager.py fix transcripts` |
| fix_missing_transcripts.py | `python scribe_manager.py fix transcripts` |
| fix_problem_translations.py | `python scribe_manager.py fix mark` |
| fix_hebrew_translations.py | `python scribe_manager.py fix hebrew` |

### Group 2: Pipeline Monitoring Scripts (Next Migration Phase)

| Legacy Script | New Command |
|---------------|------------|
| monitor_and_restart.py | `python scribe_manager.py monitor` |
| check_status.py | `python scribe_manager.py status` |
| check_stuck_files.py | `python scribe_manager.py restart` |
| check_errors.py | `python scribe_manager.py status --detailed` |
| monitor_progress.sh | `python scribe_manager.py monitor` |

### Group 3: Processing Scripts (Future Migration Phase)

| Legacy Script | New Command |
|---------------|------------|
| run_parallel_processing.py | `python scribe_manager.py start --transcription --translation` |
| parallel_transcription.py | `python scribe_manager.py start --transcription` |
| parallel_translation.py | `python scribe_manager.py start --translation` |
| transcribe_problematic_files.py | `python scribe_manager.py retry` |
| translate_all_remaining.py | `python scribe_manager.py start --translation` |
| process_remaining_files.py | `python scribe_manager.py start` |
| process_remaining_translations.py | `python scribe_manager.py start --translation` |

## Example Command Mappings

### Example 1: Fixing Stalled Files

**Legacy Command:**
```
python fix_stalled_files.py --timeout 60 --reset-all
```

**New Command:**
```
python scribe_manager.py fix stalled --timeout 60 --reset-all
```

### Example 2: Monitoring Pipeline

**Legacy Command:**
```
python monitor_and_restart.py --check-interval 30
```

**New Command:**
```
python scribe_manager.py monitor --check-interval 30
```

### Example 3: Processing Files

**Legacy Command:**
```
python parallel_processing.py --transcription-workers 10 --translation-workers 8 --languages en,de,he
```

**New Command:**
```
python scribe_manager.py start --transcription --translation en,de,he --transcription-workers 10 --translation-workers 8
```

## Additional Features in New Commands

The new consolidated commands offer several improvements beyond the legacy scripts:

1. **Consistent Error Handling**: All error handling is standardized
2. **Database Connection Pooling**: Efficient reuse of database connections
3. **Resource Management**: Proper cleanup of connections and resources
4. **Status Reporting**: Unified reporting format
5. **Improved Logging**: Better log organization and formatting
6. **Thread Safety**: Safe operation in concurrent environments

## Transition Timeline

- **Phase 1**: Connection pooling implementation (COMPLETED)
- **Phase 2**: Script aliasing for Group 1 (COMPLETED)
  - Created backward-compatible aliases for Database Maintenance Scripts
  - Original scripts preserved in the `legacy_scripts/` directory
  - Alias scripts stored in the `alias_scripts/` directory with symlinks in root
  - Added deprecation notices to guide users to new commands
- **Phase 3**: Script aliasing for Group 2 (NEXT)
- **Phase 4**: Script aliasing for Group 3
- **Phase 5**: Final migration and removal of aliases

## Questions and Support

For questions about the migration or assistance transitioning to the new command structure, please refer to the documentation in the `docs/refactoring/` directory.

---

**Note**: This migration is part of a broader refactoring effort detailed in `docs/refactoring/MIGRATION_ROADMAP.md`.