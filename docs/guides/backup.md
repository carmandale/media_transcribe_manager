# Backup and Restore Guide

Complete guide to backing up and restoring your Scribe system data.

## Overview

The Scribe backup system provides comprehensive protection for your database and translation files. It creates timestamped backups that can be used to restore your system to a previous state.

## Backup Types

### Full Backup (Default)
- Creates individual copies of all translation files
- Preserves directory structure
- Includes complete database backup
- Best for maximum data integrity
- Slower but most reliable

### Quick Backup
- Uses tar compression for translation files
- Faster backup process
- Smaller backup size
- Good for routine backups

## Commands

### Creating Backups

```bash
# Create a full backup
uv run python scribe_cli.py backup create

# Create a quick backup (faster)
uv run python scribe_cli.py backup create --quick
```

### Listing Backups

```bash
# List all available backups
uv run python scribe_cli.py backup list
```

Output includes:
- Backup ID (timestamp-based)
- Creation timestamp
- Backup type (full/quick)
- Total size
- Number of translation files
- Hebrew validation issues (if any)

### Restoring from Backup

```bash
# Restore from a specific backup
uv run python scribe_cli.py backup restore <backup_id>

# Force restore without confirmation
uv run python scribe_cli.py backup restore <backup_id> --force
```

## Backup Contents

Each backup includes:

### Database
- Complete `media_tracking.db` copy
- All processing status information
- Quality evaluation scores
- File metadata

### Translation Files
- All files in the `output/` directory
- Preserves directory structure
- Includes all language translations

### Validation Status
- Hebrew translation quality assessment
- Issue counts and summaries
- Validation timestamps

## Backup Storage

Backups are stored in the `backups/` directory:

```
backups/
├── 20250623_123456/
│   ├── manifest.json        # Backup metadata
│   ├── media_tracking.db    # Database backup
│   └── output.tar.gz        # Translation files (quick backup)
└── 20250623_134567/
    ├── manifest.json
    ├── media_tracking.db
    └── output/              # Individual files (full backup)
        └── [file_id]/
            ├── *.txt
            └── *.srt
```

## Manifest File

Each backup includes a `manifest.json` file with:

```json
{
  "backup_id": "20250623_123456",
  "timestamp": "2025-06-23T12:34:56",
  "backup_type": "quick",
  "database": {
    "size": 1048576,
    "path": "media_tracking.db"
  },
  "translations": {
    "type": "archive",
    "file_count": 2847,
    "archive_size": 52428800
  },
  "validation_status": {
    "total_hebrew_issues": 3,
    "last_validation": "2025-06-23T12:30:00"
  }
}
```

## Safety Features

### Pre-Restore Backup
- Before restoring, your current state is automatically backed up
- Ensures you can recover if restore fails
- Current state backup is clearly labeled

### Validation
- Backup integrity is verified before creation
- Missing files are detected and reported
- Corrupt backups are flagged during listing

## Best Practices

### Regular Backups
```bash
# Create daily backups (add to cron/scheduled task)
uv run python scribe_cli.py backup create --quick
```

### Before Major Operations
```bash
# Always backup before:
# - Large batch processing
# - Database maintenance
# - System updates
# - Hebrew retranslations

uv run python scribe_cli.py backup create
```

### Backup Verification
```bash
# List backups to verify recent backups exist
uv run python scribe_cli.py backup list

# Check for any errors or issues
```

## Troubleshooting

### Backup Fails
1. Check disk space
2. Verify output directory permissions
3. Ensure database is not locked by other processes

### Restore Fails
1. Check backup ID exists (`backup list`)
2. Verify backup integrity
3. Ensure sufficient disk space
4. Current state backup is always created for safety

### Large Backup Sizes
- Use `--quick` mode for routine backups
- Consider cleaning up old translation files if needed
- Monitor disk space usage

## Recovery Scenarios

### System Corruption
```bash
# Find latest good backup
uv run python scribe_cli.py backup list

# Restore from backup
uv run python scribe_cli.py backup restore <backup_id>
```

### Database Issues
```bash
# Create emergency backup first
uv run python scribe_cli.py backup create --quick

# Try database maintenance
uv run python scribe_cli.py db fix-status

# If needed, restore from backup
uv run python scribe_cli.py backup restore <backup_id>
```

### Translation Loss
```bash
# Restore specific backup with translations
uv run python scribe_cli.py backup restore <backup_id>
```

## Storage Management

### Cleanup Old Backups
Backups are not automatically deleted. Manually remove old backups:

```bash
# Remove old backup directory
rm -rf backups/20250601_120000/
```

### Backup Size Optimization
- Quick backups use compression (smaller size)
- Full backups preserve individual files (larger size)
- Choose based on your needs and available storage

## Integration with Database Maintenance

Backups work seamlessly with database maintenance:

```bash
# Create backup, audit, and fix issues
uv run python scribe_cli.py backup create
uv run python scribe_cli.py db audit
uv run python scribe_cli.py db fix-status
```

This ensures you always have a recovery point before making changes to your system.