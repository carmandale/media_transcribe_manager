# Database Maintenance Guide

Complete guide to maintaining and troubleshooting the Scribe database system.

## Overview

Scribe uses SQLite for tracking file processing status, quality scores, and metadata. The database maintenance commands help you:

- Audit database integrity
- Fix status inconsistencies
- Validate system health
- Monitor system performance

## Commands Overview

```bash
# Audit database for issues
uv run python scribe_cli.py db audit

# Fix database status inconsistencies
uv run python scribe_cli.py db fix-status

# Validate system health
uv run python scribe_cli.py db validate
```

## Database Audit

### Running an Audit

```bash
# Basic audit
uv run python scribe_cli.py db audit

# Save detailed report to file
uv run python scribe_cli.py db audit --output audit_report.json
```

### What Gets Audited

#### File System Consistency
- Missing translation files that should exist
- Placeholder files (empty or corrupted)
- Files marked as completed but missing
- Orphaned files in output directory

#### Database Integrity
- Status mismatches between database and files
- Inconsistent processing states
- Missing required metadata
- Duplicate entries

#### Language Statistics
- Completion rates by language
- Valid vs. placeholder files
- Missing translations
- Quality score distribution

### Audit Report

The audit provides:

```
=============================================================
DATABASE AUDIT RESULTS
=============================================================
Total files: 1,247
Issues found: 23
Audit completed: 2025-06-23T14:30:22

Language Statistics:

ENGLISH:
  Expected: 1,247
  Valid: 1,230
  Placeholders: 12
  Missing: 5
  Completion: 98.6%

GERMAN:
  Expected: 1,247
  Valid: 1,198
  Placeholders: 8
  Missing: 41
  Completion: 96.1%

HEBREW:
  Expected: 1,247
  Valid: 1,156
  Placeholders: 15
  Missing: 76
  Completion: 92.7%

Top Issues:
  Missing Files: 122
  Placeholder Files: 35
  Status Mismatches: 8

Recommendations:
  1. Fix status inconsistencies with 'db fix-status'
  2. Re-translate missing Hebrew files
  3. Review placeholder files for corruption
```

## Status Fixes

### Fixing Status Issues

```bash
# Preview changes without applying them
uv run python scribe_cli.py db fix-status --dry-run

# Apply status fixes
uv run python scribe_cli.py db fix-status

# Use existing audit results
uv run python scribe_cli.py db fix-status --audit-file audit_report.json
```

### What Gets Fixed

#### Placeholder Files
- Files marked as completed but contain placeholder content
- Reset to "pending" status for re-processing

#### Missing Files
- Files marked as completed but don't exist on disk
- Marked as "failed" status

#### Status Mismatches
- Valid translation files not marked as completed
- Updated to "completed" status

### Fix Process

1. **Analysis**: Identifies issues to fix
2. **Preview**: Shows what will be changed (if `--dry-run`)
3. **Confirmation**: Asks for permission to proceed
4. **Application**: Applies fixes to database
5. **Summary**: Reports results and any errors

Example output:
```
Found 23 status issues to fix:
  Placeholder file: 15 (Reset to pending)
  Missing file: 5 (Mark as failed)
  Status mismatch: 3 (Mark as completed)

Apply 23 status fixes? [y/N]: y

Applying status fixes...
✓ Applied 23 status fixes
```

## System Validation

### Running Validation

```bash
uv run python scribe_cli.py db validate
```

### What Gets Validated

#### Database Connectivity
- SQLite database accessibility
- Schema integrity
- Connection pooling health

#### Directory Structure
- Output directory exists and is writable
- Backup directory accessibility
- Log directory permissions

#### API Configuration
- All required API keys present
- Keys format validation
- Service availability

#### System Resources
- Available disk space
- Memory usage
- File system permissions

### Validation Report

```
==================================================
SYSTEM VALIDATION RESULTS
==================================================
Database: ✓ Connected
Output directory: ✓ Exists

API Keys:
  ElevenLabs: ✓ Configured
  DeepL: ✓ Configured
  Microsoft Translator: ✓ Configured
  OpenAI: ✓ Configured

Disk Space:
  Free: 45.2 GB
  Total: 250.0 GB
  Usage: 82.0%

✓ All validation checks passed
```

## Maintenance Workflows

### Regular Maintenance (Weekly)

```bash
# 1. Create backup first
uv run python scribe_cli.py backup create --quick

# 2. Run system validation
uv run python scribe_cli.py db validate

# 3. Run audit
uv run python scribe_cli.py db audit

# 4. Fix any issues found
uv run python scribe_cli.py db fix-status
```

### Problem Investigation

```bash
# 1. Create diagnostic backup
uv run python scribe_cli.py backup create

# 2. Run comprehensive audit
uv run python scribe_cli.py db audit --output problem_audit.json

# 3. Review audit results
cat problem_audit.json

# 4. Fix issues with dry run first
uv run python scribe_cli.py db fix-status --dry-run

# 5. Apply fixes if safe
uv run python scribe_cli.py db fix-status
```

### Pre-Processing Check

```bash
# Before large batch processing
uv run python scribe_cli.py db validate
uv run python scribe_cli.py backup create
```

## Common Issues and Solutions

### High Number of Placeholder Files

**Symptoms**: Audit shows many placeholder files
**Causes**: Network interruptions, API failures, disk full
**Solution**:
```bash
# Fix status to retry these files
uv run python scribe_cli.py db fix-status

# Check system health
uv run python scribe_cli.py db validate

# Retry processing
uv run python scribe_cli.py translate he --limit 50
```

### Status Mismatches

**Symptoms**: Files exist but marked as pending/failed
**Causes**: Processing interruptions, manual file operations
**Solution**:
```bash
# Let status fix detect and correct these
uv run python scribe_cli.py db fix-status
```

### Missing Translation Files

**Symptoms**: Files marked complete but don't exist
**Causes**: File system operations, accidental deletion
**Solution**:
```bash
# Mark as failed to retry
uv run python scribe_cli.py db fix-status

# Or restore from backup
uv run python scribe_cli.py backup restore <backup_id>
```

### Database Corruption

**Symptoms**: Database validation fails
**Solution**:
```bash
# Restore from recent backup
uv run python scribe_cli.py backup restore <backup_id>

# If no backup available, check logs/
tail -f logs/scribe_database.log
```

## Performance Monitoring

### Database Statistics

Check database size and growth:
```bash
ls -lh media_tracking.db
```

### Quality Trends

Monitor evaluation scores:
```bash
uv run python scribe_cli.py status --detailed
```

### File System Usage

Monitor disk space:
```bash
du -sh output/
du -sh backups/
df -h .
```

## Automation

### Scheduled Maintenance

Add to cron for automated maintenance:

```bash
# Daily backup and validation
0 2 * * * cd /path/to/scribe && uv run python scribe_cli.py backup create --quick
0 3 * * * cd /path/to/scribe && uv run python scribe_cli.py db validate

# Weekly audit and fixes
0 4 * * 0 cd /path/to/scribe && uv run python scribe_cli.py db audit
0 5 * * 0 cd /path/to/scribe && uv run python scribe_cli.py db fix-status --audit-file audit_report.json
```

### Health Monitoring Script

Create a monitoring script:
```bash
#!/bin/bash
cd /path/to/scribe

# Run validation
if ! uv run python scribe_cli.py db validate > validation.log 2>&1; then
    echo "Validation failed - check validation.log"
    exit 1
fi

# Check for critical issues
ISSUES=$(uv run python scribe_cli.py db audit | grep "Issues found:" | cut -d: -f2 | tr -d ' ')
if [ "$ISSUES" -gt 50 ]; then
    echo "Critical: $ISSUES database issues found"
    exit 1
fi

echo "System health check passed"
```

## Integration with Processing

Database maintenance integrates with normal processing:

### Before Large Operations
```bash
uv run python scribe_cli.py db validate
uv run python scribe_cli.py backup create
```

### After Processing Issues
```bash
uv run python scribe_cli.py db audit
uv run python scribe_cli.py db fix-status
```

### Monitoring Progress
```bash
uv run python scribe_cli.py status --detailed
```

## Safety Considerations

1. **Always backup first** before running fixes
2. **Use dry-run** to preview changes
3. **Monitor logs** during maintenance operations
4. **Test restore** procedures periodically
5. **Keep multiple backup copies** for safety

The database maintenance system is designed to be safe and conservative, but always backup your data before making changes.