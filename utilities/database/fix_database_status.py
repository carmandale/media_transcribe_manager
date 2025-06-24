#!/usr/bin/env python3
"""
Fix database status accuracy based on audit results.
Updates incorrect Hebrew translation statuses to reflect actual state.
"""

import sqlite3
import json
import shutil
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from contextlib import contextmanager
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class UpdateRecord:
    """Record of a database update."""
    file_id: str
    old_status: str
    new_status: str
    reason: str
    timestamp: str


@dataclass
class FixReport:
    """Report of database fixes applied."""
    backup_path: str
    records_updated: int
    placeholder_files_fixed: int
    missing_files_fixed: int
    before_stats: Dict[str, Dict[str, any]]
    after_stats: Dict[str, Dict[str, any]]
    update_records: List[UpdateRecord]
    errors: List[str]
    duration_seconds: float


class DatabaseStatusFixer:
    """Fixes incorrect database status based on audit results."""
    
    def __init__(self, db_path: Path, audit_report_path: Path, dry_run: bool = False):
        """
        Initialize the database fixer.
        
        Args:
            db_path: Path to the SQLite database
            audit_report_path: Path to the audit report JSON
            dry_run: If True, preview changes without applying them
        """
        self.db_path = Path(db_path)
        self.audit_report_path = Path(audit_report_path)
        self.dry_run = dry_run
        self.update_records = []
        self.errors = []
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        if not self.audit_report_path.exists():
            raise FileNotFoundError(f"Audit report not found: {self.audit_report_path}")
    
    def backup_database(self) -> Path:
        """
        Create a timestamped backup of the database.
        
        Returns:
            Path to the backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.db_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        backup_path = backup_dir / f"media_tracking_before_fix_{timestamp}.db"
        
        if not self.dry_run:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Created database backup: {backup_path}")
        else:
            logger.info(f"[DRY RUN] Would create backup: {backup_path}")
        
        return backup_path
    
    def parse_audit_report(self) -> Tuple[List[str], List[str]]:
        """
        Parse the audit report to extract file IDs that need fixing.
        
        Returns:
            Tuple of (placeholder_file_ids, missing_file_ids)
        """
        with open(self.audit_report_path, 'r', encoding='utf-8') as f:
            audit_data = json.load(f)
        
        # Extract placeholder files
        placeholder_files = []
        if 'placeholder_file' in audit_data.get('discrepancies', {}):
            for item in audit_data['discrepancies']['placeholder_file']:
                if item['language'] == 'he':
                    placeholder_files.append(item['file_id'])
        
        # Extract missing files
        missing_files = []
        if 'missing_file' in audit_data.get('discrepancies', {}):
            for item in audit_data['discrepancies']['missing_file']:
                if item['language'] == 'he':
                    missing_files.append(item['file_id'])
        
        logger.info(f"Found {len(placeholder_files)} placeholder files and {len(missing_files)} missing files")
        
        # Verify counts match expected
        expected_placeholders = 328
        expected_missing = 51
        
        if len(placeholder_files) != expected_placeholders:
            logger.warning(f"Expected {expected_placeholders} placeholder files, found {len(placeholder_files)}")
        if len(missing_files) != expected_missing:
            logger.warning(f"Expected {expected_missing} missing files, found {len(missing_files)}")
        
        return placeholder_files, missing_files
    
    def get_database_stats(self, conn: sqlite3.Connection) -> Dict[str, Dict[str, any]]:
        """
        Get current database statistics for all languages.
        
        Returns:
            Dictionary with stats per language
        """
        cursor = conn.cursor()
        
        # Count total files
        cursor.execute("SELECT COUNT(*) FROM media_files")
        total_files = cursor.fetchone()[0]
        
        stats = {}
        
        # Get stats for each language
        for lang, column in [
            ('en', 'translation_en_status'),
            ('de', 'translation_de_status'), 
            ('he', 'translation_he_status')
        ]:
            # Count by status
            cursor.execute(f"""
                SELECT {column}, COUNT(*) 
                FROM processing_status 
                WHERE {column} IS NOT NULL
                GROUP BY {column}
            """)
            
            status_counts = dict(cursor.fetchall())
            completed = status_counts.get('completed', 0)
            
            stats[lang] = {
                'total': total_files,
                'completed': completed,
                'failed': status_counts.get('failed', 0),
                'pending': status_counts.get('pending', 0),
                'completion_percentage': f"{(completed / total_files * 100):.1f}%"
            }
        
        return stats
    
    @contextmanager
    def db_transaction(self):
        """
        Context manager for safe database transactions.
        Automatically rolls back on error.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            yield conn
            if not self.dry_run:
                conn.commit()
                logger.info("Transaction committed successfully")
            else:
                conn.rollback()
                logger.info("[DRY RUN] Transaction rolled back")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed, rolling back: {e}")
            raise
        finally:
            conn.close()
    
    def fix_placeholder_files(self, conn: sqlite3.Connection, file_ids: List[str]) -> int:
        """
        Update status for files with placeholders.
        
        Args:
            conn: Database connection
            file_ids: List of file IDs to update
            
        Returns:
            Number of records updated
        """
        cursor = conn.cursor()
        updated = 0
        
        for file_id in file_ids:
            # Get current status
            cursor.execute(
                "SELECT translation_he_status FROM processing_status WHERE file_id = ?",
                (file_id,)
            )
            result = cursor.fetchone()
            
            if result:
                old_status = result[0]
                
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would update {file_id}: {old_status} -> pending (placeholder file)")
                else:
                    cursor.execute("""
                        UPDATE processing_status 
                        SET translation_he_status = 'pending',
                            last_updated = CURRENT_TIMESTAMP
                        WHERE file_id = ?
                    """, (file_id,))
                    logger.info(f"Updated {file_id}: {old_status} -> pending (placeholder file)")
                
                self.update_records.append(UpdateRecord(
                    file_id=file_id,
                    old_status=old_status,
                    new_status='pending',
                    reason='File contains placeholder text',
                    timestamp=datetime.now().isoformat()
                ))
                
                updated += 1
            else:
                error_msg = f"File {file_id} not found in processing_status table"
                logger.error(error_msg)
                self.errors.append(error_msg)
        
        return updated
    
    def fix_missing_files(self, conn: sqlite3.Connection, file_ids: List[str]) -> int:
        """
        Update status for missing files.
        
        Args:
            conn: Database connection
            file_ids: List of file IDs to update
            
        Returns:
            Number of records updated
        """
        cursor = conn.cursor()
        updated = 0
        
        for file_id in file_ids:
            # Get current status
            cursor.execute(
                "SELECT translation_he_status FROM processing_status WHERE file_id = ?",
                (file_id,)
            )
            result = cursor.fetchone()
            
            if result:
                old_status = result[0]
                
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would update {file_id}: {old_status} -> failed (file missing)")
                else:
                    cursor.execute("""
                        UPDATE processing_status 
                        SET translation_he_status = 'failed',
                            last_updated = CURRENT_TIMESTAMP
                        WHERE file_id = ?
                    """, (file_id,))
                    logger.info(f"Updated {file_id}: {old_status} -> failed (file missing)")
                
                self.update_records.append(UpdateRecord(
                    file_id=file_id,
                    old_status=old_status,
                    new_status='failed',
                    reason='Translation file missing',
                    timestamp=datetime.now().isoformat()
                ))
                
                updated += 1
            else:
                error_msg = f"File {file_id} not found in processing_status table"
                logger.error(error_msg)
                self.errors.append(error_msg)
        
        return updated
    
    def run(self) -> FixReport:
        """
        Run the complete database fix process.
        
        Returns:
            FixReport with details of all changes
        """
        start_time = datetime.now()
        logger.info(f"Starting database fix process {'[DRY RUN]' if self.dry_run else ''}")
        
        # Create backup
        backup_path = self.backup_database()
        
        # Parse audit report
        placeholder_files, missing_files = self.parse_audit_report()
        
        # Get before stats
        with sqlite3.connect(self.db_path) as conn:
            before_stats = self.get_database_stats(conn)
            logger.info("Before stats:")
            for lang, stats in before_stats.items():
                logger.info(f"  {lang.upper()}: {stats['completion_percentage']} complete "
                           f"({stats['completed']}/{stats['total']})")
        
        # Apply fixes
        placeholder_fixed = 0
        missing_fixed = 0
        
        with self.db_transaction() as conn:
            # Fix placeholder files
            if placeholder_files:
                logger.info(f"Fixing {len(placeholder_files)} placeholder files...")
                placeholder_fixed = self.fix_placeholder_files(conn, placeholder_files)
            
            # Fix missing files
            if missing_files:
                logger.info(f"Fixing {len(missing_files)} missing files...")
                missing_fixed = self.fix_missing_files(conn, missing_files)
            
            # Get after stats (within transaction)
            after_stats = self.get_database_stats(conn)
        
        # Log after stats
        logger.info("After stats:")
        for lang, stats in after_stats.items():
            logger.info(f"  {lang.upper()}: {stats['completion_percentage']} complete "
                       f"({stats['completed']}/{stats['total']})")
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Create report
        report = FixReport(
            backup_path=str(backup_path),
            records_updated=placeholder_fixed + missing_fixed,
            placeholder_files_fixed=placeholder_fixed,
            missing_files_fixed=missing_fixed,
            before_stats=before_stats,
            after_stats=after_stats,
            update_records=self.update_records,
            errors=self.errors,
            duration_seconds=duration
        )
        
        logger.info(f"Database fix completed in {duration:.1f} seconds")
        logger.info(f"Total records updated: {report.records_updated}")
        
        return report
    
    def save_report(self, report: FixReport, output_path: Path):
        """Save the fix report to a JSON file."""
        report_dict = asdict(report)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Fix report saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fix database status accuracy based on audit results"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("media_tracking.db"),
        help="Path to the SQLite database"
    )
    parser.add_argument(
        "--audit-report",
        type=Path,
        default=Path("audit_report.json"),
        help="Path to the audit report JSON"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("fix_report.json"),
        help="Path for the fix report output"
    )
    
    args = parser.parse_args()
    
    try:
        # Create fixer instance
        fixer = DatabaseStatusFixer(
            db_path=args.database,
            audit_report_path=args.audit_report,
            dry_run=args.dry_run
        )
        
        # Run fixes
        report = fixer.run()
        
        # Save report
        fixer.save_report(report, args.output)
        
        # Print summary
        print("\n" + "="*60)
        print("DATABASE FIX SUMMARY")
        print("="*60)
        print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLIED'}")
        print(f"Backup: {report.backup_path}")
        print(f"Records updated: {report.records_updated}")
        print(f"  - Placeholder files: {report.placeholder_files_fixed}")
        print(f"  - Missing files: {report.missing_files_fixed}")
        print(f"Errors: {len(report.errors)}")
        
        print("\nCompletion percentages:")
        print("Before:")
        for lang in ['en', 'de', 'he']:
            before = report.before_stats[lang]
            print(f"  {lang.upper()}: {before['completion_percentage']}")
        
        print("After:")
        for lang in ['en', 'de', 'he']:
            after = report.after_stats[lang]
            print(f"  {lang.upper()}: {after['completion_percentage']}")
        
        if report.errors:
            print(f"\nErrors encountered: {len(report.errors)}")
            for error in report.errors[:5]:
                print(f"  - {error}")
            if len(report.errors) > 5:
                print(f"  ... and {len(report.errors) - 5} more")
        
        if args.dry_run:
            print("\nThis was a DRY RUN. No changes were applied.")
            print("Run without --dry-run to apply changes.")
        
    except Exception as e:
        logger.error(f"Failed to fix database: {e}")
        raise


if __name__ == "__main__":
    main()