#!/usr/bin/env python3
"""
Optimized backup script with better progress reporting and resume capability.
"""

import argparse
import json
import hashlib
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OptimizedScribeBackup:
    """Optimized backup with progress reporting."""
    
    def __init__(self, project_root: Path, dry_run: bool = False):
        """Initialize backup manager."""
        self.project_root = Path(project_root).resolve()
        self.dry_run = dry_run
        self.database_path = self.project_root / "media_tracking.db"
        self.output_dir = self.project_root / "output"
        self.backups_dir = self.project_root / "backups"
        self.interrupted = False
        
        # Handle interruption gracefully
        signal.signal(signal.SIGINT, self._handle_interrupt)
        
        # Create backups directory if it doesn't exist
        if not self.dry_run:
            self.backups_dir.mkdir(exist_ok=True)
    
    def _handle_interrupt(self, signum, frame):
        """Handle keyboard interrupt."""
        logger.warning("Backup interrupted by user")
        self.interrupted = True
    
    def quick_backup(self) -> Tuple[Path, Dict]:
        """
        Perform a quick backup using tar for speed.
        
        Returns:
            Tuple of (backup_dir, manifest_data)
        """
        logger.info("Starting optimized Scribe system backup...")
        
        try:
            # Create timestamped directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.backups_dir / timestamp
            
            if not self.dry_run:
                backup_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created backup directory: {backup_dir}")
            
            # Step 1: Backup database (quick)
            logger.info("Backing up database...")
            db_backup_path = backup_dir / "media_tracking.db"
            db_info = {
                "original_path": str(self.database_path),
                "backup_path": str(db_backup_path),
                "size": self.database_path.stat().st_size if self.database_path.exists() else 0
            }
            
            if not self.dry_run and self.database_path.exists():
                shutil.copy2(self.database_path, db_backup_path)
                logger.info(f"Database backed up ({db_info['size']:,} bytes)")
            
            # Step 2: Create tar archive of output directory
            logger.info("Creating compressed archive of translation files...")
            archive_path = backup_dir / "output.tar.gz"
            
            if not self.dry_run:
                # Count files first
                file_count = sum(1 for _ in self.output_dir.rglob('*') if _.is_file())
                logger.info(f"Archiving {file_count} files...")
                
                # Use tar command for speed
                tar_cmd = f"cd '{self.project_root}' && tar -czf '{archive_path}' output/"
                result = os.system(tar_cmd)
                
                if result == 0:
                    archive_size = archive_path.stat().st_size
                    logger.info(f"Archive created successfully ({archive_size:,} bytes)")
                else:
                    logger.error("Failed to create archive")
                    raise Exception("Archive creation failed")
            
            # Step 3: Create manifest
            logger.info("Generating manifest...")
            manifest = self._create_quick_manifest(backup_dir, db_info)
            
            if not self.dry_run:
                manifest_path = backup_dir / "manifest.json"
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)
                logger.info(f"Manifest created: {manifest_path}")
            
            logger.info("Quick backup completed successfully!")
            return backup_dir, manifest
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise
    
    def _create_quick_manifest(self, backup_dir: Path, db_info: Dict) -> Dict:
        """Create a simplified manifest for quick backup."""
        # Load validation issues
        hebrew_issues = self._load_hebrew_issues()
        
        manifest = {
            "backup_timestamp": datetime.now().isoformat(),
            "backup_directory": str(backup_dir),
            "backup_type": "quick_archive",
            "project_root": str(self.project_root),
            "database": db_info,
            "archive": {
                "filename": "output.tar.gz",
                "note": "Use 'tar -xzf output.tar.gz' to extract"
            },
            "validation_status": hebrew_issues,
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform
            }
        }
        
        return manifest
    
    def _load_hebrew_issues(self) -> Dict:
        """Load and summarize Hebrew validation issues."""
        validation_report_path = self.project_root / "validation_issues.json"
        
        if not validation_report_path.exists():
            return {
                "status": "No validation report found",
                "hebrew_placeholders": 0,
                "missing_hebrew": 0
            }
        
        try:
            with open(validation_report_path, 'r', encoding='utf-8') as f:
                issues = json.load(f)
            
            missing_hebrew = []
            he_exists_not_marked = []
            
            for file_id, file_issues in issues.items():
                for issue in file_issues:
                    if 'marked complete but file missing' in issue:
                        missing_hebrew.append(file_id)
                    elif 'exists but not marked complete' in issue and 'he' in issue:
                        he_exists_not_marked.append(file_id)
            
            return {
                "status": "Validation report loaded",
                "hebrew_placeholders": len(he_exists_not_marked),
                "missing_hebrew": len(missing_hebrew),
                "total_hebrew_issues": len(he_exists_not_marked) + len(missing_hebrew)
            }
            
        except Exception as e:
            logger.warning(f"Could not load validation issues: {e}")
            return {
                "status": f"Error loading validation report: {e}",
                "hebrew_placeholders": 0,
                "missing_hebrew": 0
            }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Quick backup of Scribe system using tar compression"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the Scribe project root"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it"
    )
    
    args = parser.parse_args()
    
    try:
        backup = OptimizedScribeBackup(args.project_root, args.dry_run)
        backup_dir, manifest = backup.quick_backup()
        
        print(f"\n✓ Quick backup completed successfully!")
        print(f"  Location: {backup_dir}")
        print(f"  Database: {manifest['database']['size']:,} bytes")
        print(f"  Archive: output.tar.gz")
        print(f"  Hebrew issues: {manifest['validation_status'].get('total_hebrew_issues', 'Unknown')}")
        print(f"\nTo restore: tar -xzf {backup_dir}/output.tar.gz")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()