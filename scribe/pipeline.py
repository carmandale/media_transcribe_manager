#!/usr/bin/env python3
"""
Pipeline orchestration for the full transcription → translation → evaluation workflow.
This module coordinates all processing steps for historical interview preservation.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .database import Database
from .transcribe import transcribe_file
from .translate import translate_text, validate_hebrew
from .evaluate import evaluate_translation
from .utils import ensure_directory, ProgressTracker, SimpleWorkerPool

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for pipeline processing"""
    input_dir: Path = Path("input")
    output_dir: Path = Path("output")
    languages: List[str] = field(default_factory=lambda: ["en", "de", "he"])
    transcription_workers: int = 10
    translation_workers: int = 8
    evaluation_sample_size: int = 100
    batch_size: int = 50


@dataclass
class PipelineResult:
    """Result of processing a single file through the pipeline"""
    file_id: str
    file_path: Path
    transcribed: bool = False
    translations: Dict[str, bool] = field(default_factory=dict)
    evaluations: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    processing_time: float = 0.0


class Pipeline:
    """Orchestrates the full processing pipeline"""
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.db = Database()
        ensure_directory(self.config.output_dir)
        
    def scan_input_files(self) -> List[Path]:
        """Scan input directory for media files"""
        extensions = {'.mp3', '.mp4', '.wav', '.m4a', '.flac', '.ogg', '.avi', '.mov'}
        files = []
        
        for ext in extensions:
            files.extend(self.config.input_dir.rglob(f"*{ext}"))
            
        logger.info(f"Found {len(files)} media files in {self.config.input_dir}")
        return sorted(files)
    
    def add_files_to_database(self, files: List[Path]) -> int:
        """Add new files to the database"""
        added = 0
        
        for file_path in files:
            file_id = self.db.add_file_simple(str(file_path))
            if file_id:
                added += 1
                
        logger.info(f"Added {added} new files to database")
        return added
    
    def process_transcriptions(self, limit: Optional[int] = None) -> List[PipelineResult]:
        """Process pending transcriptions"""
        pending = self.db.get_pending_files('transcription', limit=limit)
        
        if not pending:
            logger.info("No pending transcriptions")
            return []
        
        logger.info(f"Processing {len(pending)} transcriptions")
        tracker = ProgressTracker(total=len(pending), task="Transcription")
        
        def process_one(file_info: Dict) -> PipelineResult:
            result = PipelineResult(
                file_id=file_info['file_id'],
                file_path=Path(file_info['file_path'])
            )
            
            try:
                # Update status to in-progress
                self.db.update_status(
                    file_info['file_id'], 
                    'transcription', 
                    'in-progress'
                )
                
                # Transcribe
                output_dir = self.config.output_dir / file_info['file_id']
                transcript_result = transcribe_file(
                    str(result.file_path),
                    str(output_dir)
                )
                
                # Update database
                self.db.update_status(
                    file_info['file_id'],
                    'transcription',
                    'completed'
                )
                
                result.transcribed = True
                tracker.success()
                
            except Exception as e:
                logger.error(f"Transcription failed for {file_info['file_id']}: {e}")
                self.db.update_status(
                    file_info['file_id'],
                    'transcription',
                    'failed',
                    error=str(e)
                )
                result.errors.append(f"Transcription: {str(e)}")
                tracker.failure()
                
            return result
        
        # Process in parallel
        with SimpleWorkerPool(max_workers=self.config.transcription_workers) as pool:
            results = pool.map(process_one, pending)
            
        tracker.finish()
        return results
    
    def process_translations(self, language: str, limit: Optional[int] = None) -> List[PipelineResult]:
        """Process pending translations for a specific language"""
        pending = self.db.get_pending_files(f'translation_{language}', limit=limit)
        
        if not pending:
            logger.info(f"No pending {language} translations")
            return []
            
        logger.info(f"Processing {len(pending)} {language} translations")
        tracker = ProgressTracker(total=len(pending), task=f"{language.upper()} Translation")
        
        def process_one(file_info: Dict) -> PipelineResult:
            result = PipelineResult(
                file_id=file_info['file_id'],
                file_path=Path(file_info['file_path'])
            )
            
            try:
                # Update status
                self.db.update_status(
                    file_info['file_id'],
                    f'translation_{language}',
                    'in-progress'
                )
                
                # Read transcript
                transcript_path = self.config.output_dir / file_info['file_id'] / f"{file_info['file_id']}_transcript.txt"
                if not transcript_path.exists():
                    raise FileNotFoundError(f"Transcript not found: {transcript_path}")
                    
                transcript_text = transcript_path.read_text(encoding='utf-8')
                
                # Translate
                translation = translate_text(
                    transcript_text,
                    target_language=language,
                    source_language='de'  # Assuming German source
                )
                
                # Validate Hebrew if applicable
                if language == 'he' and not validate_hebrew(translation):
                    raise ValueError("Hebrew translation does not contain Hebrew characters")
                
                # Save translation
                output_path = self.config.output_dir / file_info['file_id'] / f"{file_info['file_id']}_{language}.txt"
                output_path.write_text(translation, encoding='utf-8')
                
                # Update database
                self.db.update_status(
                    file_info['file_id'],
                    f'translation_{language}',
                    'completed'
                )
                
                result.translations[language] = True
                tracker.success()
                
            except Exception as e:
                logger.error(f"{language} translation failed for {file_info['file_id']}: {e}")
                self.db.update_status(
                    file_info['file_id'],
                    f'translation_{language}',
                    'failed',
                    error=str(e)
                )
                result.errors.append(f"Translation {language}: {str(e)}")
                tracker.failure()
                
            return result
        
        # Process in parallel
        with SimpleWorkerPool(max_workers=self.config.translation_workers) as pool:
            results = pool.map(process_one, pending)
            
        tracker.finish()
        return results
    
    def evaluate_translations(self, language: str, sample_size: Optional[int] = None) -> List[Tuple[str, float]]:
        """Evaluate translation quality for a language"""
        # Get completed translations without scores
        query = """
            SELECT file_id, file_path 
            FROM files 
            WHERE translation_{}_status = 'completed'
            AND quality_score_{} IS NULL
            LIMIT ?
        """.format(language, language)
        
        to_evaluate = self.db.execute_query(query, (sample_size or self.config.evaluation_sample_size,))
        
        if not to_evaluate:
            logger.info(f"No {language} translations to evaluate")
            return []
            
        logger.info(f"Evaluating {len(to_evaluate)} {language} translations")
        scores = []
        
        for file_info in to_evaluate:
            try:
                # Get file paths
                transcript_path = self.config.output_dir / file_info['file_id'] / f"{file_info['file_id']}_transcript.txt"
                translation_path = self.config.output_dir / file_info['file_id'] / f"{file_info['file_id']}_{language}.txt"
                
                # Evaluate
                score, _ = evaluate_translation(
                    transcript_path.read_text(encoding='utf-8'),
                    translation_path.read_text(encoding='utf-8')
                )
                
                # Update database
                update_query = f"UPDATE files SET quality_score_{language} = ? WHERE file_id = ?"
                self.db.execute_query(update_query, (score, file_info['file_id']))
                
                scores.append((file_info['file_id'], score))
                logger.info(f"Evaluated {file_info['file_id']}: {score:.1f}/10")
                
            except Exception as e:
                logger.error(f"Evaluation failed for {file_info['file_id']}: {e}")
                
        return scores
    
    def run_full_pipeline(self):
        """Run the complete pipeline: scan → transcribe → translate → evaluate"""
        logger.info("Starting full pipeline processing")
        start_time = datetime.now()
        
        # Step 1: Scan and add new files
        files = self.scan_input_files()
        self.add_files_to_database(files)
        
        # Step 2: Process transcriptions
        logger.info("Phase 1: Transcription")
        self.process_transcriptions()
        
        # Step 3: Process translations for each language
        logger.info("Phase 2: Translation")
        for language in self.config.languages:
            self.process_translations(language)
        
        # Step 4: Evaluate quality (sample)
        logger.info("Phase 3: Quality Evaluation")
        for language in self.config.languages:
            scores = self.evaluate_translations(language, sample_size=20)
            if scores:
                avg_score = sum(s[1] for s in scores) / len(scores)
                logger.info(f"{language.upper()} average score: {avg_score:.1f}/10")
        
        # Summary
        elapsed = (datetime.now() - start_time).total_seconds()
        summary = self.db.get_summary()
        
        logger.info(f"\nPipeline completed in {elapsed:.1f} seconds")
        logger.info(f"Total files: {summary['total_files']}")
        logger.info(f"Transcribed: {summary['transcribed']}")
        for lang in self.config.languages:
            logger.info(f"{lang.upper()} translated: {summary.get(f'{lang}_translated', 0)}")


def run_pipeline(config: Optional[PipelineConfig] = None):
    """Convenience function to run the full pipeline"""
    pipeline = Pipeline(config)
    pipeline.run_full_pipeline()


def process_single_file(file_path: str, languages: Optional[List[str]] = None) -> PipelineResult:
    """Process a single file through the entire pipeline"""
    pipeline = Pipeline()
    
    # Add file to database
    file_info = pipeline.db.add_file(file_path)
    if not file_info:
        # File already exists, get its info
        from .utils import generate_file_id
        file_id = generate_file_id(Path(file_path))
        file_info = {'file_id': file_id, 'file_path': file_path}
    
    result = PipelineResult(
        file_id=file_info['file_id'],
        file_path=Path(file_path)
    )
    
    # Transcribe
    transcription_results = pipeline.process_transcriptions(limit=1)
    if transcription_results:
        result.transcribed = transcription_results[0].transcribed
    
    # Translate
    languages = languages or pipeline.config.languages
    for language in languages:
        translation_results = pipeline.process_translations(language, limit=1)
        if translation_results:
            result.translations[language] = translation_results[0].translations.get(language, False)
    
    return result