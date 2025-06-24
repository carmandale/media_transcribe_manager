#!/usr/bin/env python3
"""
Comprehensive backup script for the Scribe system.
Creates a timestamped backup of the database and all translation files.
"""

import argparse
import json
import hashlib
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScribeBackup:
    """Handles comprehensive backup of the Scribe system."""
    
    def __init__(self, project_root: Path, dry_run: bool = False):
        """
        Initialize backup manager.
        
        Args:
            project_root: Path to the scribe project root
            dry_run: If True, show what would be done without doing it
        """
        self.project_root = Path(project_root).resolve()
        self.dry_run = dry_run
        self.database_path = self.project_root / "media_tracking.db"
        self.output_dir = self.project_root / "output"
        self.backups_dir = self.project_root / "backups"
        
        # Create backups directory if it doesn't exist
        if not self.dry_run:
            self.backups_dir.mkdir(exist_ok=True)
    
    def create_timestamped_backup_dir(self) -> Path:
        """
        Create a timestamped backup directory.
        
        Returns:
            Path to the created backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backups_dir / timestamp
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create backup directory: {backup_dir}")
        else:
            try:
                backup_dir.mkdir(parents=True, exist_ok=False)
                logger.info(f"Created backup directory: {backup_dir}")
            except FileExistsError:
                # In case of timestamp collision, add milliseconds
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                backup_dir = self.backups_dir / timestamp
                backup_dir.mkdir(parents=True, exist_ok=False)
                logger.info(f"Created backup directory (with ms): {backup_dir}")
            except PermissionError as e:
                logger.error(f"Permission denied creating backup directory: {e}")
                raise
            except Exception as e:
                logger.error(f"Error creating backup directory: {e}")
                raise
        
        return backup_dir
    
    def calculate_file_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA256 checksum of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal checksum string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def backup_database(self, backup_dir: Path) -> Dict[str, str]:
        """
        Backup the database file with verification.
        
        Args:
            backup_dir: Directory to store the backup
            
        Returns:
            Dictionary with backup info (path, size, checksum)
        """
        if not self.database_path.exists():
            logger.error(f"Database file not found: {self.database_path}")
            raise FileNotFoundError(f"Database not found: {self.database_path}")
        
        db_backup_path = backup_dir / "media_tracking.db"
        db_info = {
            "original_path": str(self.database_path),
            "backup_path": str(db_backup_path),
            "size": self.database_path.stat().st_size
        }
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would backup database: {self.database_path} -> {db_backup_path}")
            db_info["checksum"] = "[DRY RUN - NOT CALCULATED]"
        else:
            try:
                # Calculate original checksum
                original_checksum = self.calculate_file_checksum(self.database_path)
                db_info["original_checksum"] = original_checksum
                
                # Copy database file
                shutil.copy2(self.database_path, db_backup_path)
                logger.info(f"Backed up database: {db_backup_path}")
                
                # Verify backup checksum
                backup_checksum = self.calculate_file_checksum(db_backup_path)
                db_info["backup_checksum"] = backup_checksum
                
                if original_checksum == backup_checksum:
                    logger.info("Database backup verified successfully")
                else:
                    logger.error("Database backup checksum mismatch!")
                    raise ValueError("Database backup verification failed")
                    
            except Exception as e:
                logger.error(f"Error backing up database: {e}")
                raise
        
        return db_info
    
    def backup_translation_directories(self, backup_dir: Path) -> Dict[str, Dict]:
        """
        Backup all translation directories preserving structure.
        
        Args:
            backup_dir: Directory to store the backup
            
        Returns:
            Dictionary with backup statistics per language
        """
        if not self.output_dir.exists():
            logger.warning(f"Output directory not found: {self.output_dir}")
            return {}
        
        output_backup_dir = backup_dir / "output"
        stats = {
            "total_files": 0,
            "total_size": 0,
            "languages": {}
        }
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would backup output directory: {self.output_dir} -> {output_backup_dir}")
            # Count files for dry run
            for root, dirs, files in os.walk(self.output_dir):
                stats["total_files"] += len(files)
        else:
            try:
                # Copy entire output directory with progress
                logger.info("Starting translation directory backup...")
                total_items = sum(1 for _ in self.output_dir.rglob('*'))
                logger.info(f"Backing up {total_items} items from output directory...")
                
                # Custom copy function to show progress
                copied_count = 0
                def copy_with_progress(src, dst):
                    nonlocal copied_count
                    shutil.copy2(src, dst)
                    copied_count += 1
                    if copied_count % 100 == 0:
                        logger.info(f"Progress: {copied_count}/{total_items} items copied...")
                
                shutil.copytree(self.output_dir, output_backup_dir, 
                               dirs_exist_ok=False, copy_function=copy_with_progress)
                
                # Gather statistics
                for item_dir in output_backup_dir.iterdir():
                    if item_dir.is_dir():
                        # Each subdirectory represents a media item
                        for lang_file in item_dir.iterdir():
                            if lang_file.is_file():
                                stats["total_files"] += 1
                                stats["total_size"] += lang_file.stat().st_size
                                
                                # Track language statistics
                                if lang_file.suffix in ['.txt', '.json']:
                                    lang = lang_file.stem.split('_')[-1]  # e.g., "transcription_en"
                                    if lang not in stats["languages"]:
                                        stats["languages"][lang] = {"count": 0, "size": 0}
                                    stats["languages"][lang]["count"] += 1
                                    stats["languages"][lang]["size"] += lang_file.stat().st_size
                
                logger.info(f"Backed up {stats['total_files']} files ({stats['total_size']:,} bytes)")
                
            except Exception as e:
                logger.error(f"Error backing up translation directories: {e}")
                raise
        
        return stats
    
    def generate_manifest(self, backup_dir: Path, db_info: Dict, translation_stats: Dict) -> Path:
        """
        Generate a manifest file with complete backup information.
        
        Args:
            backup_dir: The backup directory
            db_info: Database backup information
            translation_stats: Translation backup statistics
            
        Returns:
            Path to the manifest file
        """
        manifest_path = backup_dir / "manifest.json"
        
        # Load validation results if available
        validation_issues = {}
        hebrew_placeholders = []
        missing_hebrew = []
        he_exists_not_marked = []
        
        validation_report_path = self.project_root / "validation_issues.json"
        if validation_report_path.exists():
            try:
                with open(validation_report_path, 'r', encoding='utf-8') as f:
                    validation_issues = json.load(f)
                
                # Count Hebrew issues
                for file_id, file_issues in validation_issues.items():
                    for issue in file_issues:
                        if 'marked complete but file missing' in issue:
                            missing_hebrew.append(file_id)
                        elif 'exists but not marked complete' in issue and 'he' in issue:
                            he_exists_not_marked.append(file_id)
                
                logger.info(f"Loaded validation issues: {len(missing_hebrew)} missing Hebrew, "
                           f"{len(he_exists_not_marked)} Hebrew files not marked complete")
            except Exception as e:
                logger.warning(f"Could not load validation issues: {e}")
        
        manifest = {
            "backup_timestamp": datetime.now().isoformat(),
            "backup_directory": str(backup_dir),
            "project_root": str(self.project_root),
            "database": db_info,
            "translations": translation_stats,
            "validation_status": {
                "hebrew_placeholders": len(he_exists_not_marked),  # Files exist but not marked complete
                "missing_hebrew": len(missing_hebrew),
                "he_exists_not_marked": len(he_exists_not_marked),
                "validation_issues_summary": {
                    "missing_hebrew_files": missing_hebrew,
                    "hebrew_files_not_marked_complete": he_exists_not_marked
                },
                "full_validation_issues": validation_issues
            },
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform
            }
        }
        
        if self.dry_run:
            logger.info("[DRY RUN] Would create manifest with:")
            logger.info(json.dumps(manifest, indent=2))
        else:
            try:
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)
                logger.info(f"Created manifest: {manifest_path}")
            except Exception as e:
                logger.error(f"Error creating manifest: {e}")
                raise
        
        return manifest_path
    
    def run_backup(self) -> Tuple[Path, Dict]:
        """
        Run the complete backup process.
        
        Returns:
            Tuple of (backup_dir, manifest_data)
        """
        logger.info("Starting Scribe system backup...")
        
        try:
            # Step 1: Create timestamped directory
            backup_dir = self.create_timestamped_backup_dir()
            
            # Step 2: Backup database
            logger.info("Backing up database...")
            db_info = self.backup_database(backup_dir)
            
            # Step 3: Backup translation directories
            logger.info("Backing up translation directories...")
            translation_stats = self.backup_translation_directories(backup_dir)
            
            # Step 4: Generate manifest
            logger.info("Generating manifest...")
            manifest_path = self.generate_manifest(backup_dir, db_info, translation_stats)
            
            # Load manifest for return
            manifest_data = {}
            if not self.dry_run and manifest_path.exists():
                with open(manifest_path, 'r') as f:
                    manifest_data = json.load(f)
            
            logger.info("Backup completed successfully!")
            return backup_dir, manifest_data
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise


def main():
    """Main entry point for the backup script."""
    parser = argparse.ArgumentParser(description="Create comprehensive backup of Scribe system")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the Scribe project root (default: current directory)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        backup = ScribeBackup(args.project_root, args.dry_run)
        backup_dir, manifest = backup.run_backup()
        
        print(f"\nBackup completed successfully!")
        print(f"Backup location: {backup_dir}")
        if manifest:
            print(f"Total files backed up: {manifest.get('translations', {}).get('total_files', 0)}")
            print(f"Hebrew issues found: {manifest.get('validation_status', {}).get('hebrew_placeholders', 0)} placeholders, "
                  f"{manifest.get('validation_status', {}).get('missing_hebrew', 0)} missing")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()