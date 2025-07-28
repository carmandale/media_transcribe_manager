#!/usr/bin/env python3
"""
Database Translation Coordinator for Subtitle-First Architecture
---------------------------------------------------------------
Coordinates translation directly from database segments, preserving
exact timing boundaries and enabling 1:1 segment mapping.

This module is part of the subtitle-first architecture that ensures
translations maintain perfect synchronization with original segments.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .database import Database
from .translate import HistoricalTranslator
from .batch_language_detection import detect_languages_batch

logger = logging.getLogger(__name__)


class DatabaseTranslator:
    """
    Coordinates translation of segments directly from the database.
    
    This class replaces file-based translation with database-driven translation,
    ensuring segment boundaries are preserved and translations are stored
    atomically for each segment.
    """
    
    def __init__(self, db: Database, translator: Optional[HistoricalTranslator] = None):
        """
        Initialize the database translator.
        
        Args:
            db: Database instance for segment storage
            translator: Optional HistoricalTranslator instance (creates one if not provided)
        """
        self.db = db
        self.translator = translator or HistoricalTranslator()
        
    def translate_interview(self, 
                          interview_id: str, 
                          target_language: str,
                          batch_size: int = 50,
                          detect_source_language: bool = True) -> Dict[str, Any]:
        """
        Translate all segments for an interview to the target language.
        
        Args:
            interview_id: ID of the interview to translate
            target_language: Target language code ('en', 'de', 'he')
            batch_size: Number of segments to process in each batch
            detect_source_language: Whether to detect source language first
            
        Returns:
            Dictionary with translation results:
            {
                'total_segments': int,
                'translated': int,
                'skipped': int,
                'failed': int,
                'errors': List[str]
            }
        """
        results = {
            'total_segments': 0,
            'translated': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            # Get segments needing translation
            segments = self.db.get_segments_for_translation(interview_id, target_language)
            results['total_segments'] = len(segments)
            
            if not segments:
                logger.info(f"No segments need translation for {target_language}")
                return results
                
            logger.info(f"Translating {len(segments)} segments to {target_language}")
            
            # Process in batches
            for i in range(0, len(segments), batch_size):
                batch = segments[i:i + batch_size]
                batch_results = self._translate_batch(
                    batch, 
                    target_language,
                    detect_source_language
                )
                
                # Update results
                results['translated'] += batch_results['translated']
                results['skipped'] += batch_results['skipped']
                results['failed'] += batch_results['failed']
                results['errors'].extend(batch_results['errors'])
                
                logger.info(f"Processed batch {i//batch_size + 1}: "
                          f"{batch_results['translated']} translated, "
                          f"{batch_results['skipped']} skipped, "
                          f"{batch_results['failed']} failed")
                
        except Exception as e:
            logger.error(f"Translation failed for interview {interview_id}: {e}")
            results['errors'].append(str(e))
            
        return results
        
    def _translate_batch(self,
                        segments: List[Dict[str, Any]],
                        target_language: str,
                        detect_source_language: bool) -> Dict[str, Any]:
        """
        Translate a batch of segments.
        
        Args:
            segments: List of segment dictionaries
            target_language: Target language code
            detect_source_language: Whether to detect source language
            
        Returns:
            Batch translation results
        """
        batch_results = {
            'translated': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }
        
        # Extract texts for processing
        texts = [seg['original_text'] for seg in segments]
        
        # Detect languages if needed
        if detect_source_language and self.translator.openai_client:
            try:
                detected_languages = detect_languages_batch(texts, self.translator.openai_client)
            except Exception as e:
                logger.warning(f"Language detection failed: {e}")
                detected_languages = [None] * len(texts)
        else:
            detected_languages = [None] * len(texts)
            
        # Group segments by detected language for efficient translation
        language_groups = {}
        for i, (segment, detected_lang) in enumerate(zip(segments, detected_languages)):
            # Skip if same language as target
            if detected_lang and self.translator.is_same_language(detected_lang, target_language):
                batch_results['skipped'] += 1
                continue
                
            # Skip non-verbal segments
            if self._is_non_verbal(segment['original_text']):
                batch_results['skipped'] += 1
                continue
                
            # Group by source language
            lang_key = detected_lang or 'unknown'
            if lang_key not in language_groups:
                language_groups[lang_key] = []
            language_groups[lang_key].append((i, segment))
            
        # Translate each language group
        for source_lang, segment_group in language_groups.items():
            group_texts = [seg[1]['original_text'] for seg in segment_group]
            
            try:
                # Use batch translation for efficiency
                translations = self.translator.batch_translate(
                    group_texts,
                    target_language,
                    source_lang if source_lang != 'unknown' else None
                )
                
                # Prepare updates
                updates = []
                for (idx, segment), translation in zip(segment_group, translations):
                    if translation:
                        updates.append({
                            'segment_id': segment['id'],
                            'language': target_language,
                            'text': translation
                        })
                        batch_results['translated'] += 1
                    else:
                        batch_results['failed'] += 1
                        batch_results['errors'].append(
                            f"Failed to translate segment {segment['id']}"
                        )
                        
                # Batch update database
                if updates:
                    success = self.db.batch_update_segment_translations(updates)
                    if not success:
                        batch_results['errors'].append(
                            f"Failed to save {len(updates)} translations to database"
                        )
                        
            except Exception as e:
                logger.error(f"Batch translation failed for {source_lang}: {e}")
                batch_results['failed'] += len(segment_group)
                batch_results['errors'].append(str(e))
                
        return batch_results
        
    def _is_non_verbal(self, text: str) -> bool:
        """
        Check if text is non-verbal content.
        
        Args:
            text: Text to check
            
        Returns:
            True if text is non-verbal
        """
        if not text:
            return True
            
        # Common non-verbal patterns
        non_verbal_patterns = [
            r'^\s*$',  # Empty or whitespace
            r'^\s*\.+\s*$',  # Only dots
            r'^\s*♪+\s*$',  # Music notation
            r'^\s*\[.*\]\s*$',  # Bracketed content like [inaudible]
            r'^\s*\(.*\)\s*$',  # Parenthetical content
        ]
        
        import re
        for pattern in non_verbal_patterns:
            if re.match(pattern, text):
                return True
                
        return False
        
    def get_translation_status(self, interview_id: str) -> Dict[str, Dict[str, int]]:
        """
        Get translation status for an interview.
        
        Args:
            interview_id: ID of the interview
            
        Returns:
            Translation status by language
        """
        return self.db.get_segment_translation_status(interview_id)
        
    def validate_translations(self, interview_id: str, target_language: str) -> Dict[str, Any]:
        """
        Validate translations for an interview.
        
        Args:
            interview_id: ID of the interview
            target_language: Language to validate
            
        Returns:
            Validation results including any issues found
        """
        validation_results = {
            'valid': True,
            'total_segments': 0,
            'validated': 0,
            'issues': []
        }
        
        try:
            # Get all segments
            segments = self.db.get_subtitle_segments(interview_id)
            validation_results['total_segments'] = len(segments)
            
            # Map target language to column
            language_column_map = {
                'en': 'english_text',
                'de': 'german_text',
                'he': 'hebrew_text'
            }
            
            if target_language not in language_column_map:
                validation_results['valid'] = False
                validation_results['issues'].append(f"Unsupported language: {target_language}")
                return validation_results
                
            column = language_column_map[target_language]
            
            # Validate each segment
            for segment in segments:
                translation = segment.get(column)
                
                # Skip non-verbal segments
                if self._is_non_verbal(segment['original_text']):
                    continue
                    
                validation_results['validated'] += 1
                
                # Check for missing translation
                if not translation:
                    validation_results['issues'].append(
                        f"Segment {segment['segment_index']} missing {target_language} translation"
                    )
                    validation_results['valid'] = False
                    continue
                    
                # Special validation for Hebrew
                if target_language == 'he' and not self.translator.validate_hebrew_translation(translation):
                    validation_results['issues'].append(
                        f"Segment {segment['segment_index']} has invalid Hebrew translation"
                    )
                    validation_results['valid'] = False
                    
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            validation_results['valid'] = False
            validation_results['issues'].append(str(e))
            
        return validation_results


# Integration functions for pipeline compatibility
def translate_interview_from_database(db: Database,
                                    interview_id: str,
                                    target_languages: List[str] = None,
                                    translator: Optional[HistoricalTranslator] = None) -> Dict[str, Any]:
    """
    Translate an interview using the database-first approach.
    
    This function provides a simple interface for the pipeline to use
    database-coordinated translation.
    
    Args:
        db: Database instance
        interview_id: ID of the interview to translate
        target_languages: List of target language codes (default: ['en', 'de', 'he'])
        translator: Optional HistoricalTranslator instance
        
    Returns:
        Dictionary with results for each language
    """
    if target_languages is None:
        target_languages = ['en', 'de', 'he']
        
    db_translator = DatabaseTranslator(db, translator)
    results = {}
    
    for lang in target_languages:
        logger.info(f"Translating interview {interview_id} to {lang}")
        results[lang] = db_translator.translate_interview(
            interview_id,
            lang,
            batch_size=50,
            detect_source_language=True
        )
        
        # Log summary
        lang_result = results[lang]
        logger.info(f"Translation to {lang} complete: "
                   f"{lang_result['translated']} translated, "
                   f"{lang_result['skipped']} skipped, "
                   f"{lang_result['failed']} failed")
                   
    return results