#!/usr/bin/env python3
"""
Complete Subtitle Processing Workflow
=====================================
Handles multilingual subtitle generation and format conversion for the Scribe system.

This module ensures all interviews have complete subtitle sets:
- Original language (orig.srt/vtt)
- English translation (en.srt/vtt)
- German translation (de.srt/vtt)
- Hebrew translation (he.srt/vtt)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import concurrent.futures
from datetime import datetime

from .srt_translator import SRTTranslator, translate_srt_file
from .translate import HistoricalTranslator

logger = logging.getLogger(__name__)


class SubtitleProcessor:
    """Handles complete subtitle processing workflow."""
    
    REQUIRED_LANGUAGES = ['en', 'de', 'he']
    REQUIRED_FILES = ['orig'] + REQUIRED_LANGUAGES
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize subtitle processor.
        
        Args:
            output_dir: Base output directory for processed files
        """
        self.output_dir = Path(output_dir)
        self.translator = HistoricalTranslator()
        self.srt_translator = SRTTranslator(self.translator)
        
    def convert_srt_to_vtt(self, srt_path: Path) -> bool:
        """
        Convert SRT file to VTT format.
        
        Args:
            srt_path: Path to SRT file
            
        Returns:
            True if successful, False otherwise
        """
        vtt_path = srt_path.with_suffix('.vtt')
        
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            # VTT format: add header and convert timestamps
            vtt_content = "WEBVTT\n\n" + srt_content.replace(',', '.')
            
            with open(vtt_path, 'w', encoding='utf-8') as f:
                f.write(vtt_content)
            
            logger.info(f"Converted {srt_path.name} to VTT")
            return True
            
        except Exception as e:
            logger.error(f"Failed to convert {srt_path} to VTT: {e}")
            return False
    
    def validate_subtitle_files(self, file_id: str) -> Dict[str, bool]:
        """
        Validate that all required subtitle files exist.
        
        Args:
            file_id: Interview file ID
            
        Returns:
            Dictionary mapping file type to existence status
        """
        interview_dir = self.output_dir / file_id
        validation = {}
        
        for lang in self.REQUIRED_FILES:
            srt_file = interview_dir / f"{file_id}.{lang}.srt"
            vtt_file = interview_dir / f"{file_id}.{lang}.vtt"
            
            validation[f"{lang}.srt"] = srt_file.exists()
            validation[f"{lang}.vtt"] = vtt_file.exists()
        
        return validation
    
    def translate_subtitle(self, file_id: str, source_lang: str, target_lang: str) -> bool:
        """
        Translate subtitle to target language.
        
        Args:
            file_id: Interview file ID
            source_lang: Source language code ('orig' for original)
            target_lang: Target language code ('en', 'de', 'he')
            
        Returns:
            True if successful, False otherwise
        """
        interview_dir = self.output_dir / file_id
        source_srt = interview_dir / f"{file_id}.{source_lang}.srt"
        target_srt = interview_dir / f"{file_id}.{target_lang}.srt"
        
        if not source_srt.exists():
            logger.error(f"Source SRT not found: {source_srt}")
            return False
        
        try:
            logger.info(f"Translating {file_id} to {target_lang}")
            
            # Use optimized translation with language preservation
            success = translate_srt_file(
                str(source_srt),
                str(target_srt),
                target_lang,
                preserve_original_when_matching=True,
                batch_size=200,  # Use optimized batch size
                config=self.translator.config
            )
            
            if success:
                # Convert to VTT immediately
                self.convert_srt_to_vtt(target_srt)
                
            return success
            
        except Exception as e:
            logger.error(f"Translation failed for {file_id} to {target_lang}: {e}")
            return False
    
    def process_subtitles(self, file_id: str, force: bool = False) -> Dict[str, bool]:
        """
        Process all subtitles for an interview.
        
        This is the main entry point that ensures all subtitle files are generated:
        1. Validates orig.srt exists
        2. Converts orig.srt to orig.vtt
        3. Translates to all three languages
        4. Converts all translations to VTT
        5. Validates all files exist
        
        Args:
            file_id: Interview file ID
            force: If True, regenerate even if files exist
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing subtitles for {file_id}")
        start_time = datetime.now()
        
        results = {
            'file_id': file_id,
            'success': False,
            'languages': {},
            'validation': {},
            'duration': 0
        }
        
        interview_dir = self.output_dir / file_id
        orig_srt = interview_dir / f"{file_id}.orig.srt"
        
        # Step 1: Validate source file exists
        if not orig_srt.exists():
            logger.error(f"Original SRT not found: {orig_srt}")
            results['error'] = "Original SRT file not found"
            return results
        
        # Step 2: Convert original to VTT
        orig_vtt = orig_srt.with_suffix('.vtt')
        if force or not orig_vtt.exists():
            if not self.convert_srt_to_vtt(orig_srt):
                results['error'] = "Failed to convert original SRT to VTT"
                return results
        
        # Step 3: Process each language
        for lang in self.REQUIRED_LANGUAGES:
            target_srt = interview_dir / f"{file_id}.{lang}.srt"
            
            # Skip if already exists and not forcing
            if not force and target_srt.exists():
                logger.info(f"Skipping {lang} - already exists")
                results['languages'][lang] = 'exists'
                # Ensure VTT exists too
                if not target_srt.with_suffix('.vtt').exists():
                    self.convert_srt_to_vtt(target_srt)
                continue
            
            # Translate
            success = self.translate_subtitle(file_id, 'orig', lang)
            results['languages'][lang] = 'success' if success else 'failed'
        
        # Step 4: Validate all files exist
        results['validation'] = self.validate_subtitle_files(file_id)
        
        # Step 5: Determine overall success
        all_files_exist = all(results['validation'].values())
        all_translations_ok = all(
            status in ['success', 'exists'] 
            for status in results['languages'].values()
        )
        
        results['success'] = all_files_exist and all_translations_ok
        results['duration'] = (datetime.now() - start_time).total_seconds()
        
        # Log summary
        if results['success']:
            logger.info(f"✅ Successfully processed all subtitles for {file_id} in {results['duration']:.1f}s")
        else:
            missing = [f for f, exists in results['validation'].items() if not exists]
            logger.error(f"❌ Failed to process subtitles for {file_id}. Missing: {missing}")
        
        return results
    
    def process_multiple(self, file_ids: List[str], workers: int = 1, force: bool = False) -> List[Dict]:
        """
        Process multiple interviews in parallel.
        
        Args:
            file_ids: List of interview file IDs
            workers: Number of parallel workers
            force: If True, regenerate even if files exist
            
        Returns:
            List of processing results
        """
        results = []
        
        if workers == 1:
            # Sequential processing
            for file_id in file_ids:
                result = self.process_subtitles(file_id, force)
                results.append(result)
        else:
            # Parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(self.process_subtitles, file_id, force)
                    for file_id in file_ids
                ]
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Worker failed: {e}")
        
        # Summary statistics
        successful = sum(1 for r in results if r['success'])
        logger.info(f"Processed {len(results)} interviews: {successful} successful")
        
        return results
    
    def get_missing_files_report(self, file_id: str) -> str:
        """
        Generate a report of missing subtitle files.
        
        Args:
            file_id: Interview file ID
            
        Returns:
            Human-readable report
        """
        validation = self.validate_subtitle_files(file_id)
        interview_dir = self.output_dir / file_id
        
        report = f"Subtitle Status for {file_id}:\n"
        report += f"Directory: {interview_dir}\n\n"
        
        for file_type in self.REQUIRED_FILES:
            srt_key = f"{file_type}.srt"
            vtt_key = f"{file_type}.vtt"
            
            srt_status = "✅" if validation.get(srt_key, False) else "❌"
            vtt_status = "✅" if validation.get(vtt_key, False) else "❌"
            
            report += f"{file_type.upper()}:\n"
            report += f"  {srt_status} {srt_key}\n"
            report += f"  {vtt_status} {vtt_key}\n"
        
        missing_count = sum(1 for exists in validation.values() if not exists)
        if missing_count == 0:
            report += "\n✅ All subtitle files present!"
        else:
            report += f"\n❌ Missing {missing_count} files"
        
        return report


def process_interview_subtitles(file_id: str, output_dir: str = "output", 
                               force: bool = False) -> bool:
    """
    Convenience function to process all subtitles for an interview.
    
    Args:
        file_id: Interview file ID
        output_dir: Output directory
        force: If True, regenerate even if files exist
        
    Returns:
        True if successful, False otherwise
    """
    processor = SubtitleProcessor(output_dir)
    result = processor.process_subtitles(file_id, force)
    return result['success']