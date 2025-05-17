# Migration Roadmap: Phasing Out Legacy Scripts

This document outlines the plan for phasing out legacy scripts in favor of the new consolidated modules with connection pooling.

## Overview

The Scribe project has accumulated numerous small scripts for specific tasks, leading to code duplication, inconsistent error handling, and resource leaks. Our refactoring has consolidated functionality into core modules:

- **db_connection_pool.py**: Thread-safe connection pooling for SQLite
- **db_manager.py**: Unified database access layer with pooled connections
- **db_maintenance.py**: Database maintenance and repair operations
- **pipeline_manager.py**: Pipeline orchestration and monitoring
- **scribe_manager.py**: Unified command-line interface

The migration strategy involves gradually replacing direct usage of legacy scripts with calls to the new unified modules.

## Migration Phases

### Phase 1: Connection Pooling (Completed)

- [x] Create `db_connection_pool.py` for thread-safe database access
- [x] Update `db_manager.py` to use the connection pool
- [x] Add unit and integration tests for the connection pool
- [x] Fix ResourceWarnings for unclosed database connections

### Phase 2: Script Aliasing (Current)

Create shell script aliases to map legacy scripts to their consolidated counterparts:

1. Create a `legacy_scripts` directory to store original scripts for reference
2. Create shell script aliases in the project root that forward calls to new modules
3. Update documentation to point to new commands while maintaining backward compatibility

**Example alias scripts:**
```bash
#!/bin/bash
# fix_stalled_files.py alias
echo "NOTE: fix_stalled_files.py is deprecated. Please use 'python scribe_manager.py fix stalled' instead."
python scribe_manager.py fix stalled "$@"
```

### Phase 3: Code Analysis and Dependency Updates

Systematically analyze each legacy script to:

1. Identify unique functionality that might not be covered by consolidated modules
2. Map dependencies between scripts
3. Update any external tools/scripts that call these scripts
4. Document any special cases or custom behaviors

### Phase 4: Incremental Replacement

Replace legacy scripts in the following order:

#### Group 1: Database Maintenance Scripts

| Legacy Script | Replacement Command |
|---------------|---------------------|
| fix_stalled_files.py | scribe_manager.py fix stalled |
| fix_path_issues.py | scribe_manager.py fix paths |
| fix_transcript_status.py | scribe_manager.py fix transcripts |
| fix_missing_transcripts.py | scribe_manager.py fix transcripts |
| fix_problem_translations.py | scribe_manager.py fix mark |
| fix_hebrew_translations.py | scribe_manager.py fix hebrew |

#### Group 2: Pipeline Monitoring Scripts

| Legacy Script | Replacement Command |
|---------------|---------------------|
| monitor_and_restart.py | scribe_manager.py monitor |
| check_status.py | scribe_manager.py status |
| check_stuck_files.py | scribe_manager.py restart |
| check_errors.py | scribe_manager.py status --detailed |
| monitor_progress.sh | scribe_manager.py monitor |

#### Group 3: Processing Scripts

| Legacy Script | Replacement Command |
|---------------|---------------------|
| run_parallel_processing.py | scribe_manager.py start --transcription --translation |
| parallel_transcription.py | scribe_manager.py start --transcription |
| parallel_translation.py | scribe_manager.py start --translation |
| transcribe_problematic_files.py | scribe_manager.py retry |
| translate_all_remaining.py | scribe_manager.py start --translation |
| process_remaining_files.py | scribe_manager.py start |
| process_remaining_translations.py | scribe_manager.py start --translation |

#### Group 4: Specialized Processing Scripts

These scripts may require more careful analysis before replacement:

- evaluate_quality.py
- evaluate_historical_accuracy.py
- batch_evaluate_quality.py
- direct_transcribe.py
- check_retranscription.py
- check_transcript_file.py

### Phase 5: Final Migration

1. Move all original scripts to an `_archive` directory
2. Update all documentation to reference new consolidated commands
3. Remove aliases after a transition period
4. Update CI/CD pipelines and automation scripts to use new commands

## Testing Strategy

For each script being replaced:

1. Create a test data set that exercises the script's functionality
2. Run both old and new scripts on the test data
3. Compare outputs and verify identical results
4. Document any differences or issues
5. Create automated tests for the new functionality

## User Communication

1. Update README.md with new commands and migration notice
2. Create MIGRATION_GUIDE.md with examples of old vs. new commands
3. Add deprecation warnings to aliased scripts
4. Document new functionalities that weren't available in legacy scripts

## Timeline

- **Week 1**: Finish connection pooling implementation (COMPLETED)
- **Week 2**: Create aliases and documentation for Group 1 scripts
- **Week 3**: Migrate Group 2 scripts
- **Week 4**: Migrate Group 3 scripts
- **Week 5**: Analyze and plan migration for Group 4 scripts
- **Week 6**: Complete migration and testing
- **Week 7**: Cleanup, documentation updates, and final testing

## Script-Specific Migration Notes

### fix_stalled_files.py

**Legacy behavior:**
- Resets files stuck in 'in-progress' state
- Checks if output files exist to determine appropriate status

**Migration approach:**
- Already implemented in `db_maintenance.fix_stalled_files()`
- Accessible via `scribe_manager.py fix stalled`
- Enhanced with better transaction support and error handling

### monitor_and_restart.py

**Legacy behavior:**
- Periodically checks database for stuck processes
- Can automatically restart stalled processes

**Migration approach:**
- Implemented in `pipeline_manager.PipelineMonitor`
- Accessible via `scribe_manager.py monitor`
- Enhanced with configurable check and restart intervals

[More script-specific notes will be added as analysis progresses]

## Potential Challenges

1. **Edge Cases**: Some legacy scripts may handle edge cases in ways not fully captured in consolidated modules
2. **Custom Parameters**: Legacy scripts might support unique parameters that need to be mapped to new commands
3. **External Dependencies**: Scripts used in automated workflows or called by external tools will need special attention
4. **Backward Compatibility**: Ensuring no disruption to existing workflows during transition

## Success Criteria

1. All functionality from legacy scripts is available in consolidated modules
2. No ResourceWarnings or connection leaks in the codebase
3. Reduced overall code complexity and duplication
4. All tests pass with the new implementation
5. Documentation is updated to reflect new workflow
6. No performance regression compared to legacy scripts