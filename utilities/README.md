# Utilities Directory

This directory contains one-off scripts and utilities that may be deprecated or used infrequently for maintenance and troubleshooting tasks.

## Directory Structure

### backup/
- `create_backup.py` - Creates backups of the database and output files
- `create_backup_optimized.py` - Optimized version of the backup script

### database/
- `audit_system.py` - Audits the database for consistency and issues
- `fix_database_status.py` - Fixes stuck or inconsistent database statuses
- `check_retranslation_status.py` - Checks the status of Hebrew retranslations

### hebrew_fixes/
- `evaluate_hebrew.py` - Original Hebrew evaluation script
- `evaluate_hebrew_improved.py` - Improved version with GPT-4.1 and English detection
- `check_hebrew_sanity.py` - Sanity checks for Hebrew translations
- `retranslate_hebrew_batch.py` - Batch retranslation of Hebrew files
- `fix_hebrew_translations.py` - Fixes specific Hebrew translation issues

### Root utilities/
- `validate_all_translations.py` - Validates all translations across languages

## Important Note

These scripts are not part of the main application workflow and should be used with caution. Many of these were created for specific one-time fixes or investigations and may not be maintained with the same rigor as the core application.

Always backup your database and files before running any of these utilities.