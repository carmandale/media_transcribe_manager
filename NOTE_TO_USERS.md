# Important Note to Users

## Project Reorganization

We've implemented comprehensive improvements to the Scribe codebase:

1. **Connection Pooling**: Fixed ResourceWarnings for unclosed database connections
2. **Consolidated Commands**: Unified many single-purpose scripts into core modules
3. **Clean Directory Structure**: Organized all scripts into logical directories

### New Directory Structure

The project has been completely reorganized for better maintainability:

- **`core_modules/`**: Core functionality modules
- **`scripts/`**: Utility scripts
- **`maintenance/`**: Database and system maintenance scripts  
- **`legacy_scripts/`**: Original versions of legacy scripts
- **`alias_scripts/`**: Alias scripts for backward compatibility

### Updated Command Paths

All scripts are now in their respective directories. You'll need to use the new paths when running scripts:

```bash
# OLD WAY (no longer works):
python media_processor.py -d /path/to/media

# NEW WAY:
python scripts/media_processor.py -d /path/to/media
```

### Unified Interface

For most operations, you can now use the new unified interface:

```bash
# Use the main Scribe Manager interface
python core_modules/scribe_manager.py [command] [options]

# Examples:
python core_modules/scribe_manager.py status
python core_modules/scribe_manager.py fix stalled
python core_modules/scribe_manager.py monitor --check-interval 10
```

The following legacy fix_* scripts have been replaced with consolidated commands:

- `fix_stalled_files.py` ➡ `scribe_manager.py fix stalled`
- `fix_path_issues.py` ➡ `scribe_manager.py fix paths`
- `fix_transcript_status.py` ➡ `scribe_manager.py fix transcripts`
- `fix_missing_transcripts.py` ➡ `scribe_manager.py fix transcripts`
- `fix_problem_translations.py` ➡ `scribe_manager.py fix mark`
- `fix_hebrew_translations.py` ➡ `scribe_manager.py fix hebrew`

### Path Handling Best Practices

When working with paths in this codebase, follow these guidelines:

1. **In Python Code**:
   - ALWAYS use `pathlib.Path` for path manipulation
   - Never use string concatenation for paths
   - Always check if paths exist before operations

2. **In Bash Commands**:
   - Always quote paths with double quotes in commands: `cd "/path with spaces"`
   - Use absolute paths when possible
   - For file operations, prefer Python's pathlib.Path or os functions over Bash commands

### Documentation

For complete details on the migration and new command structure, see:
- `docs/MIGRATION_GUIDE.md`: Mapping between old and new commands
- `README.md`: Updated documentation on the unified interface
- `CLAUDE.md`: Both legacy and new consolidated commands

For any questions or issues, please refer to these documents or contact the maintainers.
