#!/usr/bin/env python3
"""
Database Migration Script: Subtitle-First Architecture
======================================================

This script migrates an existing Scribe database to support the subtitle-first
architecture by adding the subtitle_segments table and related views.

This is a SAFE, ADDITIVE migration that:
- Preserves all existing data
- Maintains backward compatibility
- Adds new subtitle_segments table for enhanced processing
- Creates views for seamless integration

Usage:
    python migrate_to_subtitle_segments.py [--db-path path/to/database.db]
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from scribe.database import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_database(db_path: Optional[str] = None) -> bool:
    """
    Migrate database to subtitle-first architecture.
    
    Args:
        db_path: Path to database file (defaults to media_tracking.db)
        
    Returns:
        True if migration successful, False otherwise
    """
    if db_path is None:
        db_path = "media_tracking.db"
    
    db_path = Path(db_path)
    
    # Check if database exists
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return False
    
    logger.info(f"Starting migration of database: {db_path}")
    
    try:
        # Create database instance
        db = Database(db_path)
        
        # Check current state
        conn = db._get_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        logger.info(f"Current tables: {sorted(tables)}")
        
        # Check if already migrated
        if 'subtitle_segments' in tables:
            logger.info("Database already migrated to subtitle-first architecture")
            db.close()
            return True
        
        # Backup existing data counts
        media_count = conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]
        status_count = conn.execute("SELECT COUNT(*) FROM processing_status").fetchone()[0]
        error_count = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        
        logger.info(f"Pre-migration data: {media_count} media files, {status_count} status records, {error_count} errors")
        
        # Perform migration
        logger.info("Applying subtitle-first architecture migration...")
        db._migrate_to_subtitle_segments()
        
        # Verify migration
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        new_tables = {row[0] for row in cursor.fetchall()}
        
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {row[0] for row in cursor.fetchall()}
        
        logger.info(f"Post-migration tables: {sorted(new_tables)}")
        logger.info(f"Created views: {sorted(views)}")
        
        # Verify data integrity
        new_media_count = conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]
        new_status_count = conn.execute("SELECT COUNT(*) FROM processing_status").fetchone()[0]
        new_error_count = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        
        if (new_media_count != media_count or 
            new_status_count != status_count or 
            new_error_count != error_count):
            logger.error("Data integrity check failed - record counts changed!")
            return False
        
        logger.info(f"Post-migration data integrity verified: {new_media_count} media files, {new_status_count} status records, {new_error_count} errors")
        
        # Test new functionality
        logger.info("Testing new subtitle segments functionality...")
        
        # Test that we can query the new table (should be empty initially)
        segment_count = conn.execute("SELECT COUNT(*) FROM subtitle_segments").fetchone()[0]
        logger.info(f"Subtitle segments table created with {segment_count} records")
        
        # Test views
        try:
            conn.execute("SELECT * FROM transcripts LIMIT 0")
            conn.execute("SELECT * FROM segment_quality LIMIT 0") 
            logger.info("Backward compatibility views working correctly")
        except Exception as e:
            logger.error(f"View testing failed: {e}")
            return False
        
        db.close()
        logger.info("Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(description="Migrate Scribe database to subtitle-first architecture")
    parser.add_argument(
        "--db-path", 
        type=str,
        help="Path to database file (default: media_tracking.db)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check migration status without applying changes"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        db_path = Path(args.db_path or "media_tracking.db")
        if not db_path.exists():
            print(f"❌ Database not found: {db_path}")
            return 1
        
        db = Database(db_path)
        conn = db._get_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subtitle_segments'")
        already_migrated = cursor.fetchone() is not None
        db.close()
        
        if already_migrated:
            print("✅ Database already migrated to subtitle-first architecture")
        else:
            print("📝 Database needs migration to subtitle-first architecture")
            print("Run without --dry-run to apply migration")
        
        return 0
    
    # Perform migration
    success = migrate_database(args.db_path)
    
    if success:
        print("✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Test that existing functionality still works") 
        print("2. Begin using subtitle-first processing")
        print("3. Monitor for any issues and report them")
        return 0
    else:
        print("❌ Migration failed - check logs for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())