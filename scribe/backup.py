"""
Backup and restore functionality for the Scribe system.
Handles database and translation file backup with integrity verification.
"""

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
import subprocess

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages backup and restore operations for the Scribe system."""
    
    def __init__(self, project_root: Path):
        """
        Initialize backup manager.
        
        Args:
            project_root: Path to the scribe project root
        """
        self.project_root = Path(project_root).resolve()
        self.database_path = self.project_root / "media_tracking.db"
        self.output_dir = self.project_root / "output"
        self.backups_dir = self.project_root / "backups"
        self.interrupted = False
        
        # Handle interruption gracefully
        signal.signal(signal.SIGINT, self._handle_interrupt)
        
        # Create backups directory if it doesn't exist
        self.backups_dir.mkdir(exist_ok=True)
    
    def _handle_interrupt(self, signum, frame):
        """Handle keyboard interrupt."""
        logger.warning("Backup operation interrupted by user")
        self.interrupted = True
    
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
    
    def create_backup(self, quick: bool = False) -> Tuple[Path, Dict]:
        """
        Create a backup of the system.
        
        Args:
            quick: If True, use tar compression for faster backup
            
        Returns:
            Tuple of (backup_dir, manifest_data)
        """
        logger.info("Starting Scribe system backup...")
        
        # Create timestamped directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backups_dir / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created backup directory: {backup_dir}")
        
        try:
            # Step 1: Backup database
            logger.info("Backing up database...")
            db_info = self._backup_database(backup_dir)
            
            # Step 2: Backup translation files
            logger.info("Backing up translation files...")
            if quick:
                translation_info = self._backup_translations_quick(backup_dir)
            else:
                translation_info = self._backup_translations_full(backup_dir)
            
            # Step 3: Generate manifest
            logger.info("Generating manifest...")
            manifest = self._generate_manifest(backup_dir, db_info, translation_info, quick)
            
            # Save manifest
            manifest_path = backup_dir / "manifest.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            logger.info(f"Manifest created: {manifest_path}")
            
            logger.info("Backup completed successfully!")
            return backup_dir, manifest
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Clean up partial backup
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            raise
    
    def _backup_database(self, backup_dir: Path) -> Dict[str, str]:
        """
        Backup the database file with verification.
        
        Args:
            backup_dir: Directory to store the backup
            
        Returns:
            Dictionary with backup info
        """
        if not self.database_path.exists():
            raise FileNotFoundError(f"Database not found: {self.database_path}")
        
        db_backup_path = backup_dir / "media_tracking.db"
        
        # Calculate original checksum
        original_checksum = self.calculate_file_checksum(self.database_path)
        
        # Copy database file
        shutil.copy2(self.database_path, db_backup_path)
        logger.info(f"Backed up database: {db_backup_path}")
        
        # Verify backup checksum
        backup_checksum = self.calculate_file_checksum(db_backup_path)
        
        if original_checksum != backup_checksum:
            raise ValueError("Database backup verification failed")
        
        logger.info("Database backup verified successfully")
        
        return {
            "original_path": str(self.database_path),
            "backup_path": str(db_backup_path),
            "size": self.database_path.stat().st_size,
            "checksum": original_checksum
        }
    
    def _backup_translations_quick(self, backup_dir: Path) -> Dict[str, any]:
        """
        Create a quick backup using tar compression.
        
        Args:
            backup_dir: Directory to store the backup
            
        Returns:
            Dictionary with backup info
        """
        if not self.output_dir.exists():
            logger.warning(f"Output directory not found: {self.output_dir}")
            return {"method": "quick", "status": "output_dir_not_found"}
        
        # Count files first
        file_count = sum(1 for _ in self.output_dir.rglob('*') if _.is_file())
        logger.info(f"Archiving {file_count} files...")
        
        # Create tar archive
        archive_path = backup_dir / "output.tar.gz"
        
        # Use tar command for speed
        cmd = ["tar", "-czf", str(archive_path), "-C", str(self.project_root), "output/"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Archive creation failed: {result.stderr}")
        
        archive_size = archive_path.stat().st_size
        logger.info(f"Archive created successfully ({archive_size:,} bytes)")
        
        return {
            "method": "quick",
            "archive_path": str(archive_path),
            "file_count": file_count,
            "archive_size": archive_size,
            "extraction_note": "Use 'tar -xzf output.tar.gz' to extract"
        }
    
    def _backup_translations_full(self, backup_dir: Path) -> Dict[str, any]:
        """
        Create a full backup preserving directory structure.
        
        Args:
            backup_dir: Directory to store the backup
            
        Returns:
            Dictionary with backup info
        """
        if not self.output_dir.exists():
            logger.warning(f"Output directory not found: {self.output_dir}")
            return {"method": "full", "status": "output_dir_not_found"}
        
        output_backup_dir = backup_dir / "output"
        
        # Copy entire output directory
        logger.info("Copying translation files...")
        shutil.copytree(self.output_dir, output_backup_dir)
        
        # Gather statistics
        file_count = 0
        total_size = 0
        
        for item in output_backup_dir.rglob('*'):
            if item.is_file():
                file_count += 1
                total_size += item.stat().st_size
        
        logger.info(f"Backed up {file_count} files ({total_size:,} bytes)")
        
        return {
            "method": "full",
            "backup_path": str(output_backup_dir),
            "file_count": file_count,
            "total_size": total_size
        }
    
    def _generate_manifest(self, backup_dir: Path, db_info: Dict, translation_info: Dict, quick: bool) -> Dict:
        """Generate a manifest file with backup information."""
        # Load validation results if available
        hebrew_issues = self._load_hebrew_issues()
        
        manifest = {
            "backup_timestamp": datetime.now().isoformat(),
            "backup_directory": str(backup_dir),
            "backup_type": "quick" if quick else "full",
            "project_root": str(self.project_root),
            "database": db_info,
            "translations": translation_info,
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
    
    def list_backups(self) -> List[Dict]:
        """
        List all available backups.
        
        Returns:
            List of backup information dictionaries
        """
        backups = []
        
        if not self.backups_dir.exists():
            return backups
        
        for backup_dir in self.backups_dir.iterdir():
            if not backup_dir.is_dir():
                continue
            
            manifest_path = backup_dir / "manifest.json"
            if not manifest_path.exists():
                # Legacy backup without manifest
                backups.append({
                    "id": backup_dir.name,
                    "timestamp": backup_dir.name,
                    "path": str(backup_dir),
                    "has_manifest": False,
                    "size": self._get_directory_size(backup_dir)
                })
                continue
            
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                backups.append({
                    "id": backup_dir.name,
                    "timestamp": manifest.get("backup_timestamp", backup_dir.name),
                    "path": str(backup_dir),
                    "has_manifest": True,
                    "type": manifest.get("backup_type", "unknown"),
                    "database_size": manifest.get("database", {}).get("size", 0),
                    "translation_files": manifest.get("translations", {}).get("file_count", 0),
                    "hebrew_issues": manifest.get("validation_status", {}).get("total_hebrew_issues", 0),
                    "size": self._get_directory_size(backup_dir)
                })
                
            except Exception as e:
                logger.warning(f"Error reading manifest for {backup_dir.name}: {e}")
                backups.append({
                    "id": backup_dir.name,
                    "timestamp": backup_dir.name,
                    "path": str(backup_dir),
                    "has_manifest": False,
                    "error": str(e),
                    "size": self._get_directory_size(backup_dir)
                })
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups
    
    def _get_directory_size(self, directory: Path) -> int:
        """Get total size of a directory."""
        total = 0
        for item in directory.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
        return total
    
    def restore_backup(self, backup_id: str) -> Dict:
        """
        Restore from a backup.
        
        Args:
            backup_id: ID of the backup to restore
            
        Returns:
            Dictionary with restore information
        """
        backup_dir = self.backups_dir / backup_id
        
        if not backup_dir.exists():
            raise FileNotFoundError(f"Backup not found: {backup_id}")
        
        logger.info(f"Restoring from backup: {backup_id}")
        
        # Create backup of current state first
        current_backup_id = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        current_backup_dir, _ = self.create_backup(quick=True)
        logger.info(f"Current state backed up to: {current_backup_dir}")
        
        try:
            # Restore database
            db_backup_path = backup_dir / "media_tracking.db"
            if db_backup_path.exists():
                logger.info("Restoring database...")
                shutil.copy2(db_backup_path, self.database_path)
                logger.info("Database restored")
            else:
                logger.warning("No database backup found")
            
            # Restore translations
            output_backup_dir = backup_dir / "output"
            output_archive = backup_dir / "output.tar.gz"
            
            if output_backup_dir.exists():
                # Full backup restore
                logger.info("Restoring translation files (full backup)...")
                if self.output_dir.exists():
                    shutil.rmtree(self.output_dir)
                shutil.copytree(output_backup_dir, self.output_dir)
                logger.info("Translation files restored")
                
            elif output_archive.exists():
                # Quick backup restore
                logger.info("Restoring translation files (archive)...")
                if self.output_dir.exists():
                    shutil.rmtree(self.output_dir)
                
                # Extract archive
                cmd = ["tar", "-xzf", str(output_archive), "-C", str(self.project_root)]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"Archive extraction failed: {result.stderr}")
                
                logger.info("Translation files restored from archive")
            else:
                logger.warning("No translation backup found")
            
            logger.info("Restore completed successfully!")
            
            return {
                "success": True,
                "backup_id": backup_id,
                "current_state_backup": str(current_backup_dir),
                "restored_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {
                "success": False,
                "backup_id": backup_id,
                "error": str(e),
                "current_state_backup": str(current_backup_dir)
            }