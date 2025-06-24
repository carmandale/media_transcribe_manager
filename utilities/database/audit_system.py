#!/usr/bin/env python3
"""
Comprehensive audit system for Scribe database and filesystem integrity.
Uses async/await for high performance file analysis.
"""

import asyncio
import json
import sqlite3
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import aiofiles
import re
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# SUBTASK 2.1: Design Audit Data Structures
# ============================================================================

class FileStatus(Enum):
    """Status of a translation file."""
    VALID = "valid"
    PLACEHOLDER = "placeholder"
    MISSING = "missing"
    ORPHANED = "orphaned"
    CORRUPTED = "corrupted"
    EMPTY = "empty"


class LanguageCode(Enum):
    """Supported language codes."""
    ENGLISH = "en"
    GERMAN = "de"
    HEBREW = "he"
    ORIGINAL = "original"


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
class DatabaseRecord:
    """Record from the database for a translation."""
    file_id: str
    filename: str
    language: str
    status: str  # Database status (e.g., 'completed', 'pending')
    created_at: Optional[str]
    updated_at: Optional[str]
    evaluated: bool = False
    evaluation_score: Optional[float] = None


@dataclass
class Discrepancy:
    """A discrepancy between database and filesystem."""
    file_id: str
    language: str
    discrepancy_type: str  # 'missing', 'placeholder', 'status_mismatch', etc.
    database_status: Optional[str]
    file_status: Optional[FileStatus]
    details: Dict[str, any]


@dataclass
class LanguageStatistics:
    """Statistics for a specific language."""
    expected_count: int = 0
    found_count: int = 0
    valid_count: int = 0
    placeholder_count: int = 0
    missing_count: int = 0
    corrupted_count: int = 0
    empty_count: int = 0
    orphaned_count: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary with calculated percentages."""
        return {
            "expected": self.expected_count,
            "found": self.found_count,
            "valid": self.valid_count,
            "placeholders": self.placeholder_count,
            "missing": self.missing_count,
            "corrupted": self.corrupted_count,
            "empty": self.empty_count,
            "orphaned": self.orphaned_count,
            "completion_rate": (
                f"{(self.valid_count / self.expected_count * 100):.1f}%" 
                if self.expected_count > 0 else "0%"
            )
        }


@dataclass
class AuditReport:
    """Complete audit report structure."""
    audit_timestamp: str
    project_root: str
    database_path: str
    output_directory: str
    summary: Dict[str, any]
    language_statistics: Dict[str, LanguageStatistics]
    discrepancies: Dict[str, List[Discrepancy]]
    validation_results: Dict[str, any]
    performance_metrics: Dict[str, float]


# ============================================================================
# SUBTASK 2.2: Implement Async File Reading and Analysis
# ============================================================================

class FileAnalyzer:
    """Async file analyzer for translation files."""
    
    # Placeholder patterns
    PLACEHOLDER_PATTERNS = [
        r'\[HEBREW TRANSLATION\]',
        r'\[GERMAN TRANSLATION\]',
        r'\[ENGLISH TRANSLATION\]',
        r'<<<PLACEHOLDER>>>',
        r'Translation pending',
        r'TO BE TRANSLATED'
    ]
    
    def __init__(self):
        self.placeholder_regex = re.compile('|'.join(self.PLACEHOLDER_PATTERNS), re.IGNORECASE)
    
    @staticmethod
    def contains_hebrew(text: str) -> bool:
        """Check if text contains Hebrew characters."""
        return any('\u0590' <= c <= '\u05FF' for c in text)
    
    def has_placeholder(self, text: str) -> bool:
        """Check if text contains placeholder patterns."""
        return bool(self.placeholder_regex.search(text))
    
    @staticmethod
    def detect_language(text: str) -> Optional[str]:
        """Detect the primary language of the text."""
        # Hebrew detection
        if FileAnalyzer.contains_hebrew(text):
            return LanguageCode.HEBREW.value
        
        # German detection (common words)
        german_words = ['der', 'die', 'das', 'und', 'ist', 'ich', 'nicht', 'ein', 'zu']
        text_lower = text.lower()
        german_count = sum(1 for word in german_words if f' {word} ' in text_lower)
        
        if german_count >= 3:
            return LanguageCode.GERMAN.value
        
        # Default to English
        return LanguageCode.ENGLISH.value
    
    @staticmethod
    async def calculate_checksum(file_path: Path) -> str:
        """Calculate SHA256 checksum of a file asynchronously."""
        sha256_hash = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    async def analyze_translation_file(self, file_path: Path, file_id: str, expected_language: str) -> FileMetadata:
        """Analyze a single translation file asynchronously."""
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
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Calculate checksum
            metadata.checksum = await self.calculate_checksum(file_path)
            
            # Extract preview (first 200 chars)
            metadata.content_preview = content[:200].replace('\n', ' ')
            
            # Check for Hebrew characters
            metadata.has_hebrew = self.contains_hebrew(content)
            
            # Check for placeholders
            metadata.has_placeholder = self.has_placeholder(content)
            
            # Determine status
            if metadata.has_placeholder:
                metadata.status = FileStatus.PLACEHOLDER
            else:
                # Verify language matches expected
                detected_lang = self.detect_language(content)
                
                # Special case: Hebrew files should contain Hebrew
                if expected_language == LanguageCode.HEBREW.value and not metadata.has_hebrew:
                    metadata.status = FileStatus.PLACEHOLDER
                elif expected_language == LanguageCode.GERMAN.value and detected_lang != LanguageCode.GERMAN.value:
                    # Log warning but still mark as valid (may need manual review)
                    logger.warning(f"File {file_id} expected German but detected {detected_lang}")
                    metadata.status = FileStatus.VALID
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


# ============================================================================
# SUBTASK 2.3: Compare Database and Filesystem
# ============================================================================

class DatabaseAnalyzer:
    """Analyze database records and compare with filesystem."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """Connect to the database."""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
    
    def get_all_translation_records(self) -> Dict[str, Dict[str, DatabaseRecord]]:
        """
        Get all translation records from database.
        Returns: Dict[file_id, Dict[language, DatabaseRecord]]
        """
        cursor = self.connection.cursor()
        
        # Query for all files and their processing status
        query = """
        SELECT 
            mf.file_id,
            mf.safe_filename as filename,
            ps.translation_en_status,
            ps.translation_de_status,
            ps.translation_he_status,
            ps.started_at,
            ps.completed_at
        FROM media_files mf
        LEFT JOIN processing_status ps ON mf.file_id = ps.file_id
        ORDER BY mf.file_id
        """
        
        cursor.execute(query)
        records = defaultdict(dict)
        
        for row in cursor.fetchall():
            file_id = row['file_id']
            
            # Create record for each language
            for lang, status_field in [
                ('en', 'translation_en_status'),
                ('de', 'translation_de_status'),
                ('he', 'translation_he_status')
            ]:
                status = row[status_field] or 'not_started'
                # Map database status to expected status
                if status == 'completed':
                    mapped_status = 'completed'
                elif status == 'failed':
                    mapped_status = 'failed'
                else:
                    mapped_status = 'pending'
                
                record = DatabaseRecord(
                    file_id=file_id,
                    filename=row['filename'],
                    language=lang,
                    status=mapped_status,
                    created_at=row['started_at'],
                    updated_at=row['completed_at']
                )
                records[file_id][lang] = record
        
        # Also get evaluation data
        eval_query = """
        SELECT file_id, language, score
        FROM quality_evaluations
        WHERE language IN ('en', 'de', 'he')
        """
        
        try:
            cursor.execute(eval_query)
            for row in cursor.fetchall():
                file_id = row['file_id']
                language = row['language']
                if file_id in records and language in records[file_id]:
                    records[file_id][language].evaluated = True
                    records[file_id][language].evaluation_score = row['score']
        except sqlite3.OperationalError:
            # Table might not exist in older databases
            logger.warning("quality_evaluations table not found")
        
        return dict(records)
    
    def get_total_file_count(self) -> int:
        """Get total number of media files in database."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM media_files")
        return cursor.fetchone()[0]


class FilesystemScanner:
    """Scan filesystem for translation files."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
    
    async def scan_output_directory(self) -> Dict[str, Dict[str, Path]]:
        """
        Scan output directory for translation files.
        Returns: Dict[file_id, Dict[language, Path]]
        """
        files_map = defaultdict(dict)
        
        if not self.output_dir.exists():
            logger.warning(f"Output directory does not exist: {self.output_dir}")
            return dict(files_map)
        
        # Scan all subdirectories
        for item_dir in self.output_dir.iterdir():
            if not item_dir.is_dir():
                continue
            
            file_id = item_dir.name
            
            # Look for translation files
            for file_path in item_dir.iterdir():
                if not file_path.is_file():
                    continue
                
                filename = file_path.name
                
                # Match pattern: {file_id}.{lang}.txt
                if filename.endswith('.txt') and file_id in filename:
                    # Extract language code
                    if filename == f"{file_id}.en.txt":
                        files_map[file_id]['en'] = file_path
                    elif filename == f"{file_id}.de.txt":
                        files_map[file_id]['de'] = file_path
                    elif filename == f"{file_id}.he.txt":
                        files_map[file_id]['he'] = file_path
                    elif filename == f"{file_id}.txt":
                        files_map[file_id]['original'] = file_path
        
        return dict(files_map)


# ============================================================================
# SUBTASK 2.4: Generate JSON Report with Statistics
# ============================================================================

class AuditReportGenerator:
    """Generate comprehensive audit reports."""
    
    @staticmethod
    def generate_summary(
        total_db_files: int,
        language_stats: Dict[str, LanguageStatistics],
        discrepancies: Dict[str, List[Discrepancy]]
    ) -> Dict[str, any]:
        """Generate summary statistics."""
        total_discrepancies = sum(len(items) for items in discrepancies.values())
        
        return {
            "total_files_in_db": total_db_files,
            "total_expected_translations": total_db_files * 3,  # en, de, he
            "total_discrepancies": total_discrepancies,
            "languages": {
                lang: stats.to_dict() 
                for lang, stats in language_stats.items()
            }
        }
    
    @staticmethod
    def categorize_discrepancies(discrepancies: List[Discrepancy]) -> Dict[str, List[Dict]]:
        """Categorize discrepancies by type."""
        categorized = defaultdict(list)
        
        for disc in discrepancies:
            categorized[disc.discrepancy_type].append({
                "file_id": disc.file_id,
                "language": disc.language,
                "database_status": disc.database_status,
                "file_status": disc.file_status.value if disc.file_status else None,
                "details": disc.details
            })
        
        return dict(categorized)
    
    @staticmethod
    def save_report(report: AuditReport, output_path: Path):
        """Save audit report to JSON file."""
        report_dict = {
            "audit_timestamp": report.audit_timestamp,
            "project_root": report.project_root,
            "database_path": report.database_path,
            "output_directory": report.output_directory,
            "summary": report.summary,
            "discrepancies": {
                k: [asdict(d) for d in v] 
                for k, v in report.discrepancies.items()
            },
            "validation_results": report.validation_results,
            "performance_metrics": report.performance_metrics
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False, default=str)


# ============================================================================
# MAIN AUDIT SYSTEM
# ============================================================================

class ScribeAuditSystem:
    """Main audit system orchestrator."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.db_path = project_root / "media_tracking.db"
        self.output_dir = project_root / "output"
        self.file_analyzer = FileAnalyzer()
        self.db_analyzer = DatabaseAnalyzer(self.db_path)
        self.fs_scanner = FilesystemScanner(self.output_dir)
        self.start_time = None
        self.progress_counter = 0
        self.total_files_to_analyze = 0
    
    def _report_progress(self, increment: int = 1):
        """Report progress during analysis."""
        self.progress_counter += increment
        if self.progress_counter % 100 == 0:
            elapsed = datetime.now().timestamp() - self.start_time
            rate = self.progress_counter / elapsed
            eta = (self.total_files_to_analyze - self.progress_counter) / rate
            logger.info(
                f"Progress: {self.progress_counter}/{self.total_files_to_analyze} files "
                f"({self.progress_counter/self.total_files_to_analyze*100:.1f}%) "
                f"- Rate: {rate:.0f} files/sec - ETA: {eta:.0f}s"
            )
    
    async def analyze_files_batch(self, batch: List[Tuple[str, str, Path]]) -> List[FileMetadata]:
        """Analyze a batch of files concurrently."""
        tasks = []
        for file_id, language, file_path in batch:
            task = self.file_analyzer.analyze_translation_file(file_path, file_id, language)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        self._report_progress(len(results))
        return results
    
    async def run_audit(self) -> AuditReport:
        """Run the complete audit process."""
        self.start_time = datetime.now().timestamp()
        logger.info("Starting Scribe system audit...")
        
        # Connect to database
        self.db_analyzer.connect()
        
        try:
            # Get database records
            logger.info("Loading database records...")
            db_records = self.db_analyzer.get_all_translation_records()
            total_db_files = self.db_analyzer.get_total_file_count()
            logger.info(f"Found {total_db_files} files in database with {len(db_records)} having translations")
            
            # Scan filesystem
            logger.info("Scanning filesystem...")
            fs_files = await self.fs_scanner.scan_output_directory()
            logger.info(f"Found {len(fs_files)} directories in output folder")
            
            # Prepare file analysis tasks
            file_analysis_tasks = []
            for file_id, languages in db_records.items():
                for language, db_record in languages.items():
                    # Expected file path using actual naming convention
                    expected_path = self.output_dir / file_id / f"{file_id}.{language}.txt"
                    file_analysis_tasks.append((file_id, language, expected_path))
            
            # Add orphaned files (in filesystem but not in database)
            for file_id, fs_langs in fs_files.items():
                if file_id not in db_records:
                    for language, file_path in fs_langs.items():
                        if language in ['en', 'de', 'he']:
                            file_analysis_tasks.append((file_id, language, file_path))
            
            self.total_files_to_analyze = len(file_analysis_tasks)
            logger.info(f"Analyzing {self.total_files_to_analyze} translation files...")
            
            # Analyze files in batches
            batch_size = 100
            all_metadata = []
            
            for i in range(0, len(file_analysis_tasks), batch_size):
                batch = file_analysis_tasks[i:i + batch_size]
                batch_results = await self.analyze_files_batch(batch)
                all_metadata.extend(batch_results)
            
            # Process results
            logger.info("Processing analysis results...")
            language_stats, discrepancies = self._process_results(
                db_records, fs_files, all_metadata
            )
            
            # Validate against known issues
            validation_results = self._validate_known_issues(language_stats, discrepancies)
            
            # Calculate performance metrics
            end_time = datetime.now().timestamp()
            total_time = end_time - self.start_time
            
            performance_metrics = {
                "total_execution_time": total_time,
                "files_analyzed": len(all_metadata),
                "analysis_rate": len(all_metadata) / total_time,
                "avg_time_per_file": total_time / len(all_metadata) if all_metadata else 0
            }
            
            # Generate report
            summary = AuditReportGenerator.generate_summary(
                total_db_files, language_stats, discrepancies
            )
            
            report = AuditReport(
                audit_timestamp=datetime.now().isoformat(),
                project_root=str(self.project_root),
                database_path=str(self.db_path),
                output_directory=str(self.output_dir),
                summary=summary,
                language_statistics=language_stats,
                discrepancies=discrepancies,
                validation_results=validation_results,
                performance_metrics=performance_metrics
            )
            
            logger.info(f"Audit completed in {total_time:.1f} seconds")
            return report
            
        finally:
            self.db_analyzer.close()
    
    def _process_results(
        self, 
        db_records: Dict[str, Dict[str, DatabaseRecord]],
        fs_files: Dict[str, Dict[str, Path]],
        file_metadata: List[FileMetadata]
    ) -> Tuple[Dict[str, LanguageStatistics], Dict[str, List[Discrepancy]]]:
        """Process analysis results to generate statistics and discrepancies."""
        # Initialize language statistics
        language_stats = {
            'en': LanguageStatistics(),
            'de': LanguageStatistics(),
            'he': LanguageStatistics()
        }
        
        # Count expected files from database
        for file_id, languages in db_records.items():
            for language in languages:
                if language in language_stats:
                    language_stats[language].expected_count += 1
        
        # Track all discrepancies
        all_discrepancies = []
        
        # Process each analyzed file
        metadata_map = {(m.file_id, m.language): m for m in file_metadata}
        
        # Check database records against filesystem
        for file_id, languages in db_records.items():
            for language, db_record in languages.items():
                if language not in ['en', 'de', 'he']:
                    continue
                
                metadata = metadata_map.get((file_id, language))
                
                if not metadata or not metadata.exists:
                    # File missing
                    language_stats[language].missing_count += 1
                    all_discrepancies.append(Discrepancy(
                        file_id=file_id,
                        language=language,
                        discrepancy_type='missing_file',
                        database_status=db_record.status,
                        file_status=FileStatus.MISSING,
                        details={
                            'expected_path': str(self.output_dir / file_id / f"{file_id}.{language}.txt"),
                            'database_shows_completed': db_record.status == 'completed'
                        }
                    ))
                else:
                    # File exists
                    language_stats[language].found_count += 1
                    
                    # Check file status
                    if metadata.status == FileStatus.PLACEHOLDER:
                        language_stats[language].placeholder_count += 1
                        all_discrepancies.append(Discrepancy(
                            file_id=file_id,
                            language=language,
                            discrepancy_type='placeholder_file',
                            database_status=db_record.status,
                            file_status=metadata.status,
                            details={
                                'file_path': str(metadata.file_path),
                                'has_placeholder': metadata.has_placeholder,
                                'has_hebrew': metadata.has_hebrew,
                                'preview': metadata.content_preview,
                                'database_shows_completed': db_record.status == 'completed'
                            }
                        ))
                    elif metadata.status == FileStatus.VALID:
                        language_stats[language].valid_count += 1
                        
                        # Check for status mismatch
                        if db_record.status != 'completed':
                            all_discrepancies.append(Discrepancy(
                                file_id=file_id,
                                language=language,
                                discrepancy_type='status_mismatch',
                                database_status=db_record.status,
                                file_status=metadata.status,
                                details={
                                    'file_exists_and_valid': True,
                                    'database_status': db_record.status
                                }
                            ))
                    elif metadata.status == FileStatus.EMPTY:
                        language_stats[language].empty_count += 1
                        all_discrepancies.append(Discrepancy(
                            file_id=file_id,
                            language=language,
                            discrepancy_type='empty_file',
                            database_status=db_record.status,
                            file_status=metadata.status,
                            details={'file_size': 0}
                        ))
                    elif metadata.status == FileStatus.CORRUPTED:
                        language_stats[language].corrupted_count += 1
                        all_discrepancies.append(Discrepancy(
                            file_id=file_id,
                            language=language,
                            discrepancy_type='corrupted_file',
                            database_status=db_record.status,
                            file_status=metadata.status,
                            details={'error': metadata.error}
                        ))
        
        # Check for orphaned files
        for file_id, fs_langs in fs_files.items():
            if file_id not in db_records:
                for language, file_path in fs_langs.items():
                    if language in ['en', 'de', 'he']:
                        language_stats[language].orphaned_count += 1
                        all_discrepancies.append(Discrepancy(
                            file_id=file_id,
                            language=language,
                            discrepancy_type='orphaned_file',
                            database_status=None,
                            file_status=FileStatus.ORPHANED,
                            details={
                                'file_path': str(file_path),
                                'not_in_database': True
                            }
                        ))
        
        # Categorize discrepancies
        discrepancies_by_type = defaultdict(list)
        for disc in all_discrepancies:
            discrepancies_by_type[disc.discrepancy_type].append(disc)
        
        return language_stats, dict(discrepancies_by_type)
    
    def _validate_known_issues(
        self, 
        language_stats: Dict[str, LanguageStatistics],
        discrepancies: Dict[str, List[Discrepancy]]
    ) -> Dict[str, any]:
        """Validate findings against known issues."""
        # Expected values from requirements
        expected_he_placeholders = 328
        expected_he_missing = 51
        expected_total_he_issues = 379
        
        # Actual findings
        actual_he_placeholders = language_stats['he'].placeholder_count
        actual_he_missing = language_stats['he'].missing_count
        actual_total_he_issues = actual_he_placeholders + actual_he_missing
        
        # Count discrepancies
        placeholder_discrepancies = len(discrepancies.get('placeholder_file', []))
        missing_discrepancies = len(discrepancies.get('missing_file', []))
        
        validation_passed = (
            actual_he_placeholders == expected_he_placeholders and
            actual_he_missing == expected_he_missing
        )
        
        return {
            "validation_passed": validation_passed,
            "expected": {
                "hebrew_placeholders": expected_he_placeholders,
                "hebrew_missing": expected_he_missing,
                "total_hebrew_issues": expected_total_he_issues
            },
            "actual": {
                "hebrew_placeholders": actual_he_placeholders,
                "hebrew_missing": actual_he_missing,
                "total_hebrew_issues": actual_total_he_issues
            },
            "matches": {
                "placeholders_match": actual_he_placeholders == expected_he_placeholders,
                "missing_match": actual_he_missing == expected_he_missing,
                "total_match": actual_total_he_issues == expected_total_he_issues
            }
        }


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scribe system audit")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("audit_report.json"),
        help="Output file for audit report"
    )
    
    args = parser.parse_args()
    
    # Run audit
    audit_system = ScribeAuditSystem(args.project_root)
    report = await audit_system.run_audit()
    
    # Save report
    AuditReportGenerator.save_report(report, args.output)
    logger.info(f"Audit report saved to: {args.output}")
    
    # Print summary
    print("\n" + "="*60)
    print("AUDIT SUMMARY")
    print("="*60)
    print(f"Total files in database: {report.summary['total_files_in_db']}")
    print(f"Total discrepancies: {report.summary['total_discrepancies']}")
    print("\nLanguage Statistics:")
    for lang, stats in report.summary['languages'].items():
        print(f"\n{lang.upper()}:")
        print(f"  Expected: {stats['expected']}")
        print(f"  Found: {stats['found']}")
        print(f"  Valid: {stats['valid']}")
        print(f"  Placeholders: {stats['placeholders']}")
        print(f"  Missing: {stats['missing']}")
        print(f"  Completion: {stats['completion_rate']}")
    
    print(f"\nValidation Results:")
    validation = report.validation_results
    print(f"  Validation Passed: {validation['validation_passed']}")
    print(f"  Hebrew Placeholders: {validation['actual']['hebrew_placeholders']} "
          f"(expected {validation['expected']['hebrew_placeholders']})")
    print(f"  Hebrew Missing: {validation['actual']['hebrew_missing']} "
          f"(expected {validation['expected']['hebrew_missing']})")
    
    print(f"\nPerformance:")
    print(f"  Total time: {report.performance_metrics['total_execution_time']:.1f}s")
    print(f"  Files analyzed: {report.performance_metrics['files_analyzed']}")
    print(f"  Rate: {report.performance_metrics['analysis_rate']:.0f} files/second")


if __name__ == "__main__":
    asyncio.run(main())