"""
Database audit and validation functionality for the Scribe system.
Provides comprehensive checking of database integrity and file system consistency.
"""

import asyncio
import json
import sqlite3
import hashlib
import logging
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

from .database import Database

logger = logging.getLogger(__name__)


class FileStatus(Enum):
    """Status of a translation file."""
    VALID = "valid"
    PLACEHOLDER = "placeholder"
    MISSING = "missing"
    ORPHANED = "orphaned"
    CORRUPTED = "corrupted"
    EMPTY = "empty"


@dataclass
class FileMetadata:
    """Metadata for a translation file."""
    file_id: str
    language: str
    file_path: Optional[Path]
    exists: bool
    size: int
    checksum: Optional[str]
    status: FileStatus
    has_hebrew: bool = False
    has_placeholder: bool = False
    content_preview: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AuditResult:
    """Result of database audit."""
    timestamp: str
    total_files: int
    issues_found: int
    language_stats: Dict[str, Dict]
    issues_by_type: Dict[str, List]
    recommendations: List[str]


class DatabaseAuditor:
    """Audits database integrity and file system consistency."""
    
    def __init__(self, project_root: Path):
        """
        Initialize auditor.
        
        Args:
            project_root: Path to the scribe project root
        """
        self.project_root = Path(project_root).resolve()
        self.db_path = self.project_root / "media_tracking.db"
        self.output_dir = self.project_root / "output"
        self.db = Database()
        
        # Placeholder patterns
        self.placeholder_patterns = [
            r'\[HEBREW TRANSLATION\]',
            r'\[GERMAN TRANSLATION\]',
            r'\[ENGLISH TRANSLATION\]',
            r'<<<PLACEHOLDER>>>',
            r'Translation pending',
            r'TO BE TRANSLATED'
        ]
        self.placeholder_regex = re.compile('|'.join(self.placeholder_patterns), re.IGNORECASE)
    
    def contains_hebrew(self, text: str) -> bool:
        """Check if text contains Hebrew characters."""
        return any('\u0590' <= c <= '\u05FF' for c in text)
    
    def has_placeholder(self, text: str) -> bool:
        """Check if text contains placeholder patterns."""
        return bool(self.placeholder_regex.search(text))
    
    def analyze_file(self, file_path: Path, file_id: str, expected_language: str) -> FileMetadata:
        """
        Analyze a single translation file.
        
        Args:
            file_path: Path to the file
            file_id: ID of the file
            expected_language: Expected language code
            
        Returns:
            FileMetadata with analysis results
        """
        metadata = FileMetadata(
            file_id=file_id,
            language=expected_language,
            file_path=file_path,
            exists=file_path.exists(),
            size=0,
            checksum=None,
            status=FileStatus.MISSING
        )
        
        if not file_path.exists():
            return metadata
        
        try:
            # Get file size
            metadata.size = file_path.stat().st_size
            
            # Handle empty files
            if metadata.size == 0:
                metadata.status = FileStatus.EMPTY
                return metadata
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Calculate checksum
            metadata.checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # Extract preview (first 200 chars)
            metadata.content_preview = content[:200].replace('\n', ' ')
            
            # Check for Hebrew characters
            metadata.has_hebrew = self.contains_hebrew(content)
            
            # Check for placeholders
            metadata.has_placeholder = self.has_placeholder(content)
            
            # Determine status
            if metadata.has_placeholder:
                metadata.status = FileStatus.PLACEHOLDER
            elif expected_language == 'he' and not metadata.has_hebrew:
                metadata.status = FileStatus.PLACEHOLDER
            else:
                metadata.status = FileStatus.VALID
                
        except UnicodeDecodeError:
            metadata.status = FileStatus.CORRUPTED
            metadata.error = "Unicode decode error"
        except Exception as e:
            metadata.status = FileStatus.CORRUPTED
            metadata.error = str(e)
            logger.error(f"Error analyzing {file_path}: {e}")
        
        return metadata
    
    def audit_database(self) -> AuditResult:
        """
        Run comprehensive database audit.
        
        Returns:
            AuditResult with findings
        """
        logger.info("Starting database audit...")
        start_time = datetime.now()
        
        # Get all files from database
        all_files = self.db.execute_query("SELECT file_id FROM media_files ORDER BY file_id")
        total_files = len(all_files)
        
        logger.info(f"Auditing {total_files} files...")
        
        # Initialize stats
        language_stats = {
            'en': {'expected': 0, 'found': 0, 'valid': 0, 'placeholder': 0, 'missing': 0, 'corrupted': 0, 'empty': 0},
            'de': {'expected': 0, 'found': 0, 'valid': 0, 'placeholder': 0, 'missing': 0, 'corrupted': 0, 'empty': 0},
            'he': {'expected': 0, 'found': 0, 'valid': 0, 'placeholder': 0, 'missing': 0, 'corrupted': 0, 'empty': 0}
        }
        
        issues_by_type = defaultdict(list)
        
        # Analyze each file
        for i, file_record in enumerate(all_files):
            file_id = file_record['file_id']
            
            if i % 100 == 0:
                logger.info(f"Progress: {i}/{total_files}")
            
            # Get status from database
            status = self.db.get_status(file_id)
            if not status:
                issues_by_type['no_database_record'].append({
                    'file_id': file_id,
                    'issue': 'No processing status record'
                })
                continue
            
            # Check each language
            for lang in ['en', 'de', 'he']:
                language_stats[lang]['expected'] += 1
                
                # Get database status
                db_status = status.get(f'translation_{lang}_status')
                
                # Expected file path
                file_path = self.output_dir / file_id / f"{file_id}.{lang}.txt"
                
                # Analyze file
                metadata = self.analyze_file(file_path, file_id, lang)
                
                # Update stats
                if metadata.exists:
                    language_stats[lang]['found'] += 1
                    
                    if metadata.status == FileStatus.VALID:
                        language_stats[lang]['valid'] += 1
                    elif metadata.status == FileStatus.PLACEHOLDER:
                        language_stats[lang]['placeholder'] += 1
                        issues_by_type['placeholder_file'].append({
                            'file_id': file_id,
                            'language': lang,
                            'database_status': db_status,
                            'file_path': str(file_path),
                            'preview': metadata.content_preview
                        })
                    elif metadata.status == FileStatus.CORRUPTED:
                        language_stats[lang]['corrupted'] += 1
                        issues_by_type['corrupted_file'].append({
                            'file_id': file_id,
                            'language': lang,
                            'error': metadata.error
                        })
                    elif metadata.status == FileStatus.EMPTY:
                        language_stats[lang]['empty'] += 1
                        issues_by_type['empty_file'].append({
                            'file_id': file_id,
                            'language': lang
                        })
                else:
                    language_stats[lang]['missing'] += 1
                    if db_status == 'completed':
                        issues_by_type['missing_file'].append({
                            'file_id': file_id,
                            'language': lang,
                            'database_status': db_status,
                            'expected_path': str(file_path)
                        })
                
                # Check for status mismatches
                if metadata.exists and metadata.status == FileStatus.VALID and db_status != 'completed':
                    issues_by_type['status_mismatch'].append({
                        'file_id': file_id,
                        'language': lang,
                        'database_status': db_status,
                        'file_status': 'valid',
                        'issue': 'File exists and is valid but not marked complete'
                    })
        
        # Check for orphaned files
        if self.output_dir.exists():
            logger.info("Checking for orphaned files...")
            db_file_ids = {record['file_id'] for record in all_files}
            
            for item_dir in self.output_dir.iterdir():
                if not item_dir.is_dir():
                    continue
                
                file_id = item_dir.name
                if file_id not in db_file_ids:
                    for file_path in item_dir.iterdir():
                        if file_path.is_file() and file_path.suffix == '.txt':
                            issues_by_type['orphaned_file'].append({
                                'file_id': file_id,
                                'file_path': str(file_path),
                                'issue': 'File exists but no database record'
                            })
        
        # Generate recommendations
        recommendations = self._generate_recommendations(language_stats, issues_by_type)
        
        # Calculate completion percentages
        for lang in language_stats:
            stats = language_stats[lang]
            if stats['expected'] > 0:
                stats['completion_rate'] = f"{(stats['valid'] / stats['expected'] * 100):.1f}%"
            else:
                stats['completion_rate'] = "0%"
        
        total_issues = sum(len(issues) for issues in issues_by_type.values())
        
        result = AuditResult(
            timestamp=datetime.now().isoformat(),
            total_files=total_files,
            issues_found=total_issues,
            language_stats=language_stats,
            issues_by_type=dict(issues_by_type),
            recommendations=recommendations
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Audit completed in {duration:.1f} seconds. Found {total_issues} issues.")
        
        return result
    
    def _generate_recommendations(self, language_stats: Dict, issues_by_type: Dict) -> List[str]:
        """Generate actionable recommendations based on audit results."""
        recommendations = []
        
        # Check Hebrew translation issues
        he_stats = language_stats['he']
        placeholder_count = len(issues_by_type.get('placeholder_file', []))
        missing_count = len([i for i in issues_by_type.get('missing_file', []) if i['language'] == 'he'])
        
        if placeholder_count > 0:
            recommendations.append(f"Fix {placeholder_count} Hebrew files with placeholder text using 'uv run python scribe_cli.py translate he'")
        
        if missing_count > 0:
            recommendations.append(f"Re-translate {missing_count} missing Hebrew files")
        
        # Check status mismatches
        status_mismatches = len(issues_by_type.get('status_mismatch', []))
        if status_mismatches > 0:
            recommendations.append(f"Fix {status_mismatches} database status inconsistencies using 'uv run python scribe_cli.py db fix-status'")
        
        # Check orphaned files
        orphaned_count = len(issues_by_type.get('orphaned_file', []))
        if orphaned_count > 0:
            recommendations.append(f"Review {orphaned_count} orphaned files - they may need to be added to database")
        
        # Check corrupted files
        corrupted_count = len(issues_by_type.get('corrupted_file', []))
        if corrupted_count > 0:
            recommendations.append(f"Investigate {corrupted_count} corrupted files - they may need re-processing")
        
        return recommendations
    
    def validate_system(self) -> Dict:
        """
        Run system validation checks.
        
        Returns:
            Dictionary with validation results
        """
        logger.info("Running system validation...")
        
        validation_results = {
            "database_accessible": False,
            "output_directory_exists": False,
            "api_keys_configured": {},
            "disk_space": {},
            "recommendations": []
        }
        
        # Check database accessibility
        try:
            self.db.execute_query("SELECT COUNT(*) FROM media_files")
            validation_results["database_accessible"] = True
        except Exception as e:
            validation_results["database_accessible"] = False
            validation_results["recommendations"].append(f"Database inaccessible: {e}")
        
        # Check output directory
        validation_results["output_directory_exists"] = self.output_dir.exists()
        if not self.output_dir.exists():
            validation_results["recommendations"].append("Output directory missing - create it or check configuration")
        
        # Check API keys
        api_keys = {
            'ELEVENLABS_API_KEY': 'ElevenLabs (transcription)',
            'DEEPL_API_KEY': 'DeepL (EN/DE translation)',
            'MS_TRANSLATOR_KEY': 'Microsoft Translator (Hebrew)',
            'OPENAI_API_KEY': 'OpenAI (Hebrew translation alternative)'
        }
        
        for key, description in api_keys.items():
            configured = bool(os.getenv(key))
            validation_results["api_keys_configured"][key] = configured
            if not configured:
                validation_results["recommendations"].append(f"Configure {description}: {key}")
        
        # Check disk space
        try:
            statvfs = os.statvfs(self.project_root)
            free_bytes = statvfs.f_frsize * statvfs.f_bavail
            total_bytes = statvfs.f_frsize * statvfs.f_blocks
            
            validation_results["disk_space"] = {
                "free_gb": free_bytes / (1024**3),
                "total_gb": total_bytes / (1024**3),
                "usage_percent": ((total_bytes - free_bytes) / total_bytes) * 100
            }
            
            if validation_results["disk_space"]["usage_percent"] > 90:
                validation_results["recommendations"].append("Disk space is running low (>90% used)")
            
        except Exception as e:
            validation_results["recommendations"].append(f"Could not check disk space: {e}")
        
        return validation_results
    
    def fix_status_issues(self, audit_result: AuditResult, dry_run: bool = False) -> Dict:
        """
        Fix database status issues found during audit.
        
        Args:
            audit_result: Result from audit_database()
            dry_run: If True, show what would be fixed without doing it
            
        Returns:
            Dictionary with fix results
        """
        logger.info(f"Fixing status issues {'(dry run)' if dry_run else ''}...")
        
        fixes_applied = 0
        errors = []
        
        # Fix placeholder files (set to pending)
        placeholder_issues = audit_result.issues_by_type.get('placeholder_file', [])
        for issue in placeholder_issues:
            file_id = issue['file_id']
            language = issue['language']
            
            if dry_run:
                logger.info(f"[DRY RUN] Would reset {file_id} {language} to pending (placeholder)")
            else:
                try:
                    status_field = f'translation_{language}_status'
                    self.db.update_status(file_id, **{status_field: 'pending'})
                    logger.info(f"Reset {file_id} {language} to pending (placeholder)")
                    fixes_applied += 1
                except Exception as e:
                    error_msg = f"Failed to fix {file_id} {language}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        # Fix missing files (set to failed)
        missing_issues = audit_result.issues_by_type.get('missing_file', [])
        for issue in missing_issues:
            file_id = issue['file_id']
            language = issue['language']
            
            if dry_run:
                logger.info(f"[DRY RUN] Would reset {file_id} {language} to failed (missing)")
            else:
                try:
                    status_field = f'translation_{language}_status'
                    self.db.update_status(file_id, **{status_field: 'failed'})
                    logger.info(f"Reset {file_id} {language} to failed (missing)")
                    fixes_applied += 1
                except Exception as e:
                    error_msg = f"Failed to fix {file_id} {language}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        # Fix status mismatches (set to completed)
        mismatch_issues = audit_result.issues_by_type.get('status_mismatch', [])
        for issue in mismatch_issues:
            file_id = issue['file_id']
            language = issue['language']
            
            if dry_run:
                logger.info(f"[DRY RUN] Would set {file_id} {language} to completed (valid file exists)")
            else:
                try:
                    status_field = f'translation_{language}_status'
                    self.db.update_status(file_id, **{status_field: 'completed'})
                    logger.info(f"Set {file_id} {language} to completed (valid file exists)")
                    fixes_applied += 1
                except Exception as e:
                    error_msg = f"Failed to fix {file_id} {language}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        return {
            "fixes_applied": fixes_applied,
            "errors": errors,
            "dry_run": dry_run,
            "timestamp": datetime.now().isoformat()
        }