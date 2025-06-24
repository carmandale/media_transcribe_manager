# Utilities Directory Guide

Guide to the one-off scripts and maintenance utilities in the `utilities/` directory.

## Important Safety Notice

**⚠️ Always backup your system before running any utilities scripts**

```bash
# Create backup before using utilities
uv run python scribe_cli.py backup create
```

These scripts are **not part of the main application workflow** and should be used with caution. Many were created for specific one-time fixes or investigations and may not be maintained with the same rigor as the core application.

## Directory Structure

```
utilities/
├── README.md                    # Overview of utilities
├── backup/                      # Backup-related scripts
│   ├── create_backup.py         # Legacy backup script
│   └── create_backup_optimized.py # Optimized backup script
├── database/                    # Database maintenance utilities
│   ├── audit_system.py          # Database audit script
│   ├── fix_database_status.py   # Status fix script
│   └── check_retranslation_status.py # Hebrew retranslation status
├── hebrew_fixes/                # Hebrew-specific utilities
│   ├── evaluate_hebrew.py       # Original Hebrew evaluation
│   ├── evaluate_hebrew_improved.py # Improved Hebrew evaluation
│   ├── check_hebrew_sanity.py   # Hebrew sanity checks
│   ├── retranslate_hebrew_batch.py # Batch Hebrew retranslation
│   └── fix_hebrew_translations.py # Hebrew translation fixes
└── validate_all_translations.py # Cross-language validation
```

## Backup Utilities

### Legacy Backup Scripts

**Note**: These are superseded by the main CLI backup commands.

```bash
# Legacy backup script (use CLI backup instead)
cd utilities/backup/
uv run python create_backup.py

# Optimized version
uv run python create_backup_optimized.py
```

**Recommended**: Use main CLI instead:
```bash
uv run python scribe_cli.py backup create
uv run python scribe_cli.py backup create --quick
```

## Database Utilities

### Database Audit System

**Note**: This is superseded by the main CLI audit command.

```bash
# Legacy audit script (use CLI audit instead)
cd utilities/database/
uv run python audit_system.py
```

**Recommended**: Use main CLI instead:
```bash
uv run python scribe_cli.py db audit
```

### Database Status Fixes

**Note**: This is superseded by the main CLI fix-status command.

```bash
# Legacy status fix (use CLI fix-status instead)
cd utilities/database/
uv run python fix_database_status.py
```

**Recommended**: Use main CLI instead:
```bash
uv run python scribe_cli.py db fix-status
```

### Hebrew Retranslation Status

Check status of Hebrew retranslation processes:

```bash
cd utilities/database/
uv run python check_retranslation_status.py
```

This script provides insights into Hebrew retranslation progress and issues.

## Hebrew-Specific Utilities

### Enhanced Hebrew Evaluation (Legacy)

**Note**: Enhanced Hebrew evaluation is now built into the main CLI.

```bash
# Legacy Hebrew evaluation scripts
cd utilities/hebrew_fixes/

# Original evaluation script
uv run python evaluate_hebrew.py --limit 50

# Improved version with GPT-4.1 and English detection
uv run python evaluate_hebrew_improved.py --limit 50
```

**Recommended**: Use main CLI enhanced mode instead:
```bash
uv run python scribe_cli.py evaluate he --sample 50 --enhanced --model gpt-4.1
```

### Hebrew Sanity Checks

Specialized sanity checking for Hebrew translations:

```bash
cd utilities/hebrew_fixes/
uv run python check_hebrew_sanity.py
```

This script:
- Checks for Hebrew character presence
- Validates character ratios
- Detects placeholder content
- Reports language detection issues

### Batch Hebrew Retranslation

For large-scale Hebrew retranslation operations:

```bash
cd utilities/hebrew_fixes/
uv run python retranslate_hebrew_batch.py
```

**Caution**: This script processes many files. Always backup first.

### Hebrew Translation Fixes

Targeted fixes for specific Hebrew translation issues:

```bash
cd utilities/hebrew_fixes/
uv run python fix_hebrew_translations.py
```

This script addresses known Hebrew translation problems and inconsistencies.

## Cross-Language Validation

### Validate All Translations

Comprehensive validation across all language translations:

```bash
cd utilities/
uv run python validate_all_translations.py
```

This script:
- Validates translations across English, German, and Hebrew
- Checks for consistency issues
- Reports quality metrics
- Identifies files needing attention

## Usage Guidelines

### When to Use Utilities

1. **Investigation**: When main CLI tools don't provide enough detail
2. **Specialized Fixes**: For specific issues not covered by main CLI
3. **Batch Operations**: For large-scale maintenance tasks
4. **Legacy Compatibility**: When working with older data or processes

### When NOT to Use Utilities

1. **Regular Operations**: Use main CLI commands instead
2. **First-Time Issues**: Try main CLI troubleshooting first
3. **Production Systems**: Utilities are for maintenance, not production
4. **Without Backup**: Never run utilities without backing up first

### Safety Checklist

Before running any utility script:

1. ✅ **Create Backup**: `uv run python scribe_cli.py backup create`
2. ✅ **Read Script**: Understand what the script does
3. ✅ **Test Environment**: Run on a small subset first if possible
4. ✅ **Validate System**: `uv run python scribe_cli.py db validate`
5. ✅ **Monitor Logs**: Watch logs during execution

## Migration to Main CLI

Many utilities have been superseded by main CLI features:

| Utility Script | Main CLI Replacement |
|----------------|---------------------|
| `backup/create_backup.py` | `backup create` |
| `database/audit_system.py` | `db audit` |
| `database/fix_database_status.py` | `db fix-status` |
| `hebrew_fixes/evaluate_hebrew_improved.py` | `evaluate he --enhanced` |

**Recommendation**: Use main CLI commands whenever possible for better integration and support.

## Common Use Cases

### Hebrew Quality Investigation

```bash
# 1. Backup first
uv run python scribe_cli.py backup create

# 2. Use enhanced evaluation from main CLI
uv run python scribe_cli.py evaluate he --sample 20 --enhanced

# 3. If needed, use specialized utility for deeper analysis
cd utilities/hebrew_fixes/
uv run python check_hebrew_sanity.py
```

### Database Inconsistency Investigation

```bash
# 1. Backup first
uv run python scribe_cli.py backup create

# 2. Use main CLI audit
uv run python scribe_cli.py db audit --output detailed_audit.json

# 3. If needed, use specialized utility
cd utilities/database/
uv run python check_retranslation_status.py
```

### Cross-Language Validation

```bash
# 1. Backup first
uv run python scribe_cli.py backup create

# 2. Run comprehensive validation
cd utilities/
uv run python validate_all_translations.py

# 3. Address issues found
uv run python scribe_cli.py db fix-status
```

## Maintenance and Updates

### Script Status

- **Active**: Scripts still useful for specialized tasks
- **Legacy**: Scripts superseded by main CLI but kept for compatibility
- **Deprecated**: Scripts that should not be used (marked in script comments)

### Contributing to Utilities

When adding new utility scripts:

1. **Document Purpose**: Clear comments explaining what the script does
2. **Add Safety Checks**: Backup reminders and validation
3. **Update This Guide**: Add documentation here
4. **Consider CLI Integration**: Could this be a main CLI feature instead?

## Getting Help

If you need to use utilities:

1. **Read the Script**: Always review the code before running
2. **Start Small**: Test on limited data first
3. **Monitor Execution**: Watch logs and output
4. **Backup First**: Always create backups
5. **Ask for Help**: If unsure, don't proceed

For most tasks, the main CLI provides safer, more integrated solutions than these utility scripts.