#!/usr/bin/env python3
"""
Hebrew Translation Pipeline for batch processing problematic Hebrew files.
Orchestrates loading audit results, managing file I/O, coordinating translation workers,
tracking progress, and handling errors.
"""

import os
import json
import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass, asdict

from openai_integration import HebrewTranslator, APIUsageStats

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FileProcessingResult:
    """Result of processing a single file."""
    
    file_id: str
    issue_type: str  # 'placeholder' or 'missing'
    success: bool
    processing_time: float = 0.0
    hebrew_char_count: int = 0
    error: Optional[str] = None


@dataclass 
class PipelineStatistics:
    """Overall pipeline processing statistics."""
    
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    total_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.successful / self.total_files) * 100.0
    
    @property
    def average_time_per_file(self) -> float:
        """Calculate average processing time per file."""
        processed = self.successful + self.failed
        if processed == 0:
            return 0.0
        return self.total_time / processed
    
    @property
    def estimated_time_remaining(self) -> float:
        """Estimate time remaining for unprocessed files."""
        remaining = self.total_files - self.successful - self.failed - self.skipped
        if remaining <= 0 or self.average_time_per_file == 0:
            return 0.0
        return remaining * self.average_time_per_file


class HebrewTranslationPipeline:
    """
    Orchestrates the Hebrew translation pipeline for processing problematic files.
    """
    
    def __init__(
        self,
        audit_report_path: Path = None,
        output_dir: Path = None,
        database_path: Path = None,
        translator_config: Dict = None,
        progress_file: Path = None
    ):
        """
        Initialize the Hebrew translation pipeline.
        
        Args:
            audit_report_path: Path to audit_report.json
            output_dir: Path to output directory 
            database_path: Path to SQLite database
            translator_config: Configuration for HebrewTranslator
            progress_file: Path to save progress
        """
        self.audit_report_path = audit_report_path or Path("audit_report.json")
        self.output_dir = output_dir or Path("output")
        self.database_path = database_path or Path("media_tracking.db")
        self.progress_file = progress_file or Path("hebrew_pipeline_progress.json")
        
        # Initialize translator
        translator_config = translator_config or {}
        translator_config.setdefault('model', 'gpt-4.1-mini')  # Cost-effective default
        translator_config.setdefault('max_concurrent', 10)
        translator_config.setdefault('progress_file', Path("hebrew_translation_progress.json"))
        
        self.translator = HebrewTranslator(**translator_config)
        self.statistics = PipelineStatistics()
        
        # Load problematic files
        self.problematic_files = self._load_problematic_files()
        self.statistics.total_files = len(self.problematic_files)
        
        logger.info(f"Pipeline initialized with {self.statistics.total_files} problematic files")
    
    def _load_problematic_files(self) -> List[Tuple[str, str]]:
        """
        Load problematic files from audit report.
        
        Returns:
            List of (file_id, issue_type) tuples
        """
        if not self.audit_report_path.exists():
            logger.error(f"Audit report not found: {self.audit_report_path}")
            return []
        
        try:
            with open(self.audit_report_path, 'r', encoding='utf-8') as f:
                audit_data = json.load(f)
            
            problematic_files = []
            
            # Add placeholder files (328 files with "[HEBREW TRANSLATION]")
            placeholder_files = audit_data.get('discrepancies', {}).get('placeholder_file', [])
            for file_id in placeholder_files:
                problematic_files.append((file_id, 'placeholder'))
            
            # Add missing files (51 completely missing Hebrew files)
            missing_files = audit_data.get('discrepancies', {}).get('missing_file', [])
            for file_id in missing_files:
                problematic_files.append((file_id, 'missing'))
            
            logger.info(f"Loaded {len(placeholder_files)} placeholder files and {len(missing_files)} missing files")
            return problematic_files
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse audit report: {e}")
            return []
    
    def _load_english_text(self, file_id: str) -> Optional[str]:
        """
        Load English source text for a file.
        
        Args:
            file_id: File identifier
            
        Returns:
            English text content or None if not found
        """
        english_file = self.output_dir / file_id / f"{file_id}.en.txt"
        
        if not english_file.exists():
            logger.warning(f"English source file not found: {english_file}")
            return None
        
        try:
            with open(english_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                logger.warning(f"Empty English source file: {english_file}")
                return None
            
            return content
            
        except (IOError, UnicodeDecodeError) as e:
            logger.error(f"Failed to read English file {english_file}: {e}")
            return None
    
    def _save_hebrew_translation(self, file_id: str, hebrew_text: str) -> bool:
        """
        Save Hebrew translation to file.
        
        Args:
            file_id: File identifier
            hebrew_text: Hebrew translation
            
        Returns:
            True if saved successfully
        """
        output_file_dir = self.output_dir / file_id
        output_file_dir.mkdir(parents=True, exist_ok=True)
        
        hebrew_file = output_file_dir / f"{file_id}.he.txt"
        
        # Create backup if file exists
        if hebrew_file.exists():
            backup_file = hebrew_file.with_suffix('.txt.backup')
            try:
                hebrew_file.rename(backup_file)
                logger.info(f"Created backup: {backup_file}")
            except OSError as e:
                logger.warning(f"Failed to create backup for {hebrew_file}: {e}")
        
        try:
            with open(hebrew_file, 'w', encoding='utf-8') as f:
                f.write(hebrew_text)
            
            logger.info(f"Saved Hebrew translation: {hebrew_file}")
            return True
            
        except (IOError, UnicodeEncodeError) as e:
            logger.error(f"Failed to save Hebrew file {hebrew_file}: {e}")
            return False
    
    def _update_database_status(self, file_id: str, success: bool):
        """
        Update database status for processed file.
        
        Args:
            file_id: File identifier
            success: Whether translation was successful
        """
        if not self.database_path.exists():
            logger.warning(f"Database not found: {self.database_path}")
            return
        
        try:
            conn = sqlite3.connect(str(self.database_path))
            cursor = conn.cursor()
            
            # Update translation status
            new_status = 'completed' if success else 'failed'
            cursor.execute("""
                UPDATE processing_status 
                SET translation_he_status = ?, translation_he_updated = ?
                WHERE file_id = ?
            """, (new_status, datetime.now().isoformat(), file_id))
            
            if cursor.rowcount == 0:
                logger.warning(f"No database record found for file_id: {file_id}")
            else:
                logger.info(f"Updated database status for {file_id}: {new_status}")
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"Database update failed for {file_id}: {e}")
    
    async def _process_single_file(self, file_id: str, issue_type: str) -> FileProcessingResult:
        """
        Process a single file through the translation pipeline.
        
        Args:
            file_id: File identifier
            issue_type: Type of issue ('placeholder' or 'missing')
            
        Returns:
            Processing result
        """
        start_time = datetime.now()
        
        try:
            # Load English source text
            english_text = self._load_english_text(file_id)
            if not english_text:
                return FileProcessingResult(
                    file_id=file_id,
                    issue_type=issue_type,
                    success=False,
                    processing_time=0.0,
                    error="English source text not found or empty"
                )
            
            # Translate to Hebrew
            hebrew_text = await self.translator.translate(english_text, file_id)
            if not hebrew_text:
                return FileProcessingResult(
                    file_id=file_id,
                    issue_type=issue_type,
                    success=False,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    error="Translation failed or returned empty"
                )
            
            # Save Hebrew translation
            saved = self._save_hebrew_translation(file_id, hebrew_text)
            if not saved:
                return FileProcessingResult(
                    file_id=file_id,
                    issue_type=issue_type,
                    success=False,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    error="Failed to save Hebrew translation"
                )
            
            # Update database
            self._update_database_status(file_id, True)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            hebrew_char_count = len(hebrew_text)
            
            return FileProcessingResult(
                file_id=file_id,
                issue_type=issue_type,
                success=True,
                processing_time=processing_time,
                hebrew_char_count=hebrew_char_count
            )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {e}"
            logger.error(f"Failed to process {file_id}: {error_msg}")
            
            self._update_database_status(file_id, False)
            
            return FileProcessingResult(
                file_id=file_id,
                issue_type=issue_type,
                success=False,
                processing_time=(datetime.now() - start_time).total_seconds(),
                error=error_msg
            )
    
    async def process_files(
        self, 
        progress_callback: Callable[[int, int, PipelineStatistics], None] = None,
        max_files: int = None
    ) -> List[FileProcessingResult]:
        """
        Process all problematic files through the translation pipeline.
        
        Args:
            progress_callback: Optional callback for progress updates
            max_files: Optional limit on number of files to process
            
        Returns:
            List of processing results
        """
        logger.info(f"Starting Hebrew translation pipeline for {len(self.problematic_files)} files")
        
        files_to_process = self.problematic_files
        if max_files:
            files_to_process = files_to_process[:max_files]
            logger.info(f"Limited processing to {max_files} files")
        
        results = []
        
        async def process_with_stats(file_id: str, issue_type: str) -> FileProcessingResult:
            result = await self._process_single_file(file_id, issue_type)
            
            # Update statistics
            if result.success:
                self.statistics.successful += 1
            else:
                self.statistics.failed += 1
            
            self.statistics.total_time += result.processing_time
            
            # Call progress callback
            if progress_callback:
                completed = len(results) + 1
                progress_callback(completed, len(files_to_process), self.statistics)
            
            return result
        
        # Process files with controlled concurrency
        tasks = [
            process_with_stats(file_id, issue_type) 
            for file_id, issue_type in files_to_process
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions in results
        clean_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                file_id, issue_type = files_to_process[i]
                logger.error(f"Task failed for {file_id}: {result}")
                clean_results.append(FileProcessingResult(
                    file_id=file_id,
                    issue_type=issue_type,
                    success=False,
                    error=f"Task exception: {result}"
                ))
                self.statistics.failed += 1
            else:
                clean_results.append(result)
        
        logger.info(f"Pipeline completed: {self.statistics.successful} successful, {self.statistics.failed} failed")
        
        # Save final progress
        self.translator.save_progress()
        self._save_pipeline_results(clean_results)
        
        return clean_results
    
    def _save_pipeline_results(self, results: List[FileProcessingResult]):
        """Save pipeline results to file."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': asdict(self.statistics),
            'translator_stats': asdict(self.translator.get_usage_stats()),
            'results': [asdict(result) for result in results]
        }
        
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Pipeline results saved to {self.progress_file}")
    
    def estimate_cost(self) -> Dict:
        """
        Estimate total cost for processing all problematic files.
        
        Returns:
            Cost estimation details
        """
        # Load sample texts to estimate
        sample_texts = []
        for file_id, _ in self.problematic_files[:min(10, len(self.problematic_files))]:
            text = self._load_english_text(file_id)
            if text:
                sample_texts.append(text)
        
        if not sample_texts:
            return {
                'error': 'No sample texts found for estimation'
            }
        
        # Estimate based on sample
        sample_estimate = self.translator.estimate_cost(sample_texts)
        
        # Scale to full dataset
        scale_factor = len(self.problematic_files) / len(sample_texts)
        
        return {
            'total_files': len(self.problematic_files),
            'sample_size': len(sample_texts),
            'sample_estimate': sample_estimate,
            'total_estimated_cost': sample_estimate['estimated_total_cost'] * scale_factor,
            'cost_per_file': sample_estimate['cost_per_file'],
            'model': self.translator.model
        }
    
    def get_statistics(self) -> PipelineStatistics:
        """Get current pipeline statistics."""
        return self.statistics


# Convenience function for cost estimation
def estimate_translation_cost(
    audit_report_path: Path = None, 
    output_dir: Path = None,
    model: str = "gpt-4.1-mini"
) -> Dict:
    """
    Estimate cost for translating all problematic files.
    
    Args:
        audit_report_path: Path to audit report
        output_dir: Path to output directory
        model: OpenAI model to use
        
    Returns:
        Cost estimation details
    """
    pipeline = HebrewTranslationPipeline(
        audit_report_path=audit_report_path,
        output_dir=output_dir,
        translator_config={'model': model}
    )
    
    return pipeline.estimate_cost()


# Main execution example
async def main():
    """Example usage of the Hebrew translation pipeline."""
    pipeline = HebrewTranslationPipeline()
    
    # Estimate cost first
    cost_estimate = pipeline.estimate_cost()
    print(f"Estimated cost: ${cost_estimate.get('total_estimated_cost', 0):.2f}")
    
    # Process files with progress callback
    def progress_callback(completed: int, total: int, stats: PipelineStatistics):
        print(f"Progress: {completed}/{total} ({stats.success_rate:.1f}% success)")
    
    results = await pipeline.process_files(progress_callback=progress_callback)
    
    # Print final statistics
    stats = pipeline.get_statistics()
    print(f"\nFinal Results:")
    print(f"- Total files: {stats.total_files}")
    print(f"- Successful: {stats.successful}")
    print(f"- Failed: {stats.failed}")
    print(f"- Success rate: {stats.success_rate:.1f}%")
    print(f"- Total time: {stats.total_time:.1f}s")
    print(f"- Average time per file: {stats.average_time_per_file:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())