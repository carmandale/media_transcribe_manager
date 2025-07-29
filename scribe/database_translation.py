#!/usr/bin/env python3
"""
Database Translation Coordinator for Subtitle-First Architecture
---------------------------------------------------------------
Coordinates translation directly from database segments, preserving
exact timing boundaries and enabling 1:1 segment mapping.

This module is part of the subtitle-first architecture that ensures
translations maintain perfect synchronization with original segments.
It coordinates existing translation timing mechanisms with database segments.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .database import Database
from .translate import HistoricalTranslator
from .batch_language_detection import detect_languages_batch
from .srt_translator import SRTSegment, SRTTranslator
from .evaluate import HistoricalEvaluator, validate_hebrew_translation

logger = logging.getLogger(__name__)


class DatabaseTranslator:
    """
    Coordinates translation of segments directly from the database.
    
    This class replaces file-based translation with database-driven translation,
    ensuring segment boundaries are preserved and translations are stored
    atomically for each segment.
    """
    
    def __init__(self, db: Database, translator: Optional[HistoricalTranslator] = None, evaluator: Optional[HistoricalEvaluator] = None):
        """
        Initialize the database translator.
        
        Args:
            db: Database instance for segment storage
            translator: Optional HistoricalTranslator instance (creates one if not provided)
            evaluator: Optional HistoricalEvaluator instance for quality validation (creates one if not provided)
        """
        self.db = db
        self.translator = translator or HistoricalTranslator()
        self.evaluator = evaluator
        
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
        
    def validate_translations(self, interview_id: str, target_language: str, enhanced_quality_check: bool = False) -> Dict[str, Any]:
        """
        Validate translations for an interview, building upon existing quality validation framework.
        
        This method leverages the proven HistoricalEvaluator and Hebrew validation mechanisms
        while adding database-specific validation capabilities.
        
        Args:
            interview_id: ID of the interview
            target_language: Language to validate
            enhanced_quality_check: Whether to perform comprehensive AI-based quality evaluation
            
        Returns:
            Validation results including existing and enhanced quality metrics
        """
        validation_results = {
            'valid': True,
            'total_segments': 0,
            'validated': 0,
            'issues': [],
            'quality_scores': {},  # Enhanced: Add quality scoring
            'validation_method': 'enhanced_database_validation'
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
            
            # Enhanced: Collect segments for batch quality evaluation
            quality_check_segments = []
            
            # Validate each segment (preserving existing logic while adding enhancements)
            for segment in segments:
                translation = segment.get(column)
                
                # Skip non-verbal segments
                if self._is_non_verbal(segment['original_text']):
                    continue
                    
                validation_results['validated'] += 1
                
                # Check for missing translation (existing logic preserved)
                if not translation:
                    validation_results['issues'].append(
                        f"Segment {segment['segment_index']} missing {target_language} translation"
                    )
                    validation_results['valid'] = False
                    continue
                
                # Enhanced Hebrew validation (builds upon existing logic)
                if target_language == 'he':
                    # Use existing translator validation first
                    if not self.translator.validate_hebrew_translation(translation):
                        validation_results['issues'].append(
                            f"Segment {segment['segment_index']} has invalid Hebrew translation"
                        )
                        validation_results['valid'] = False
                        continue
                    
                    # Enhanced: Use existing comprehensive Hebrew validation from evaluate.py
                    try:
                        hebrew_validation = validate_hebrew_translation(translation)
                        if not hebrew_validation['is_valid']:
                            validation_results['issues'].extend([
                                f"Segment {segment['segment_index']}: {issue}" 
                                for issue in hebrew_validation['issues']
                            ])
                            # Don't mark as invalid for warnings, only for critical issues
                            if any(issue in ['NO_HEBREW_CHARACTERS', 'TRANSLATION_PLACEHOLDER_DETECTED'] 
                                   for issue in hebrew_validation['issues']):
                                validation_results['valid'] = False
                        
                        # Store Hebrew-specific quality metrics
                        validation_results['quality_scores'][f'segment_{segment["segment_index"]}_hebrew_quality'] = {
                            'hebrew_ratio': hebrew_validation['hebrew_ratio'],
                            'word_count': hebrew_validation['word_count'],
                            'warnings': hebrew_validation['warnings']
                        }
                    except Exception as e:
                        logger.warning(f"Enhanced Hebrew validation failed for segment {segment['segment_index']}: {e}")
                
                # Enhanced: Collect segments for comprehensive quality evaluation if requested
                if enhanced_quality_check and len(quality_check_segments) < 5:  # Sample first 5 segments
                    quality_check_segments.append({
                        'segment_index': segment['segment_index'],
                        'original': segment['original_text'],
                        'translation': translation
                    })
            
            # Enhanced: Perform comprehensive quality evaluation using existing HistoricalEvaluator
            if enhanced_quality_check and quality_check_segments and self.evaluator:
                try:
                    total_quality_score = 0
                    evaluated_segments = 0
                    
                    for seg in quality_check_segments:
                        try:
                            # Use existing HistoricalEvaluator for comprehensive quality check
                            evaluation_result = self.evaluator.evaluate(
                                seg['original'], 
                                seg['translation'], 
                                language=target_language,
                                enhanced=True
                            )
                            
                            if evaluation_result:
                                score = self.evaluator.get_score(evaluation_result)
                                total_quality_score += score
                                evaluated_segments += 1
                                
                                # Store detailed quality metrics
                                validation_results['quality_scores'][f'segment_{seg["segment_index"]}_comprehensive'] = {
                                    'score': score,
                                    'evaluation': evaluation_result
                                }
                                
                                # Mark as invalid if quality is too low
                                if score < 6.0:  # Quality threshold
                                    validation_results['issues'].append(
                                        f"Segment {seg['segment_index']} quality score too low: {score:.1f}/10"
                                    )
                                    validation_results['valid'] = False
                                    
                        except Exception as e:
                            logger.warning(f"Quality evaluation failed for segment {seg['segment_index']}: {e}")
                    
                    # Calculate average quality score
                    if evaluated_segments > 0:
                        avg_quality = total_quality_score / evaluated_segments
                        validation_results['quality_scores']['average_quality'] = avg_quality
                        logger.info(f"Average translation quality for {target_language}: {avg_quality:.1f}/10")
                        
                except Exception as e:
                    logger.warning(f"Enhanced quality evaluation failed: {e}")
                    # Don't fail validation if enhanced checking fails
            
            # Summary logging (preserving existing patterns)
            if validation_results['valid']:
                logger.info(f"✅ Translation validation passed for {target_language}: {validation_results['validated']} segments")
            else:
                logger.warning(f"⚠️ Translation validation issues in {target_language}: {len(validation_results['issues'])} issues found")
                    
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            validation_results['valid'] = False
            validation_results['issues'].append(str(e))
            
        return validation_results
        
    def evaluate_translation_quality(self, interview_id: str, target_languages: List[str] = None, sample_size: int = 5) -> Dict[str, Any]:
        """
        Evaluate translation quality using existing HistoricalEvaluator framework.
        
        This method builds upon the proven quality evaluation infrastructure,
        providing comprehensive assessment of translation quality for database segments.
        
        Args:
            interview_id: ID of the interview to evaluate
            target_languages: Languages to evaluate (default: ['en', 'de', 'he'])
            sample_size: Number of segments to sample for quality evaluation
            
        Returns:
            Quality evaluation results leveraging existing evaluation framework
        """
        if target_languages is None:
            target_languages = ['en', 'de', 'he']
            
        quality_results = {
            'interview_id': interview_id,
            'languages': {},
            'overall_quality': 0.0,
            'evaluation_method': 'enhanced_database_quality_evaluation'
        }
        
        try:
            # Initialize evaluator if not already available
            if not self.evaluator and self.translator.openai_client:
                self.evaluator = HistoricalEvaluator()
                logger.info("Initialized HistoricalEvaluator for quality assessment")
            
            if not self.evaluator:
                logger.warning("No evaluator available - enhanced quality evaluation skipped")
                return quality_results
            
            # Get segments for evaluation
            segments = self.db.get_subtitle_segments(interview_id)
            if not segments:
                logger.warning(f"No segments found for interview {interview_id}")
                return quality_results
            
            # Sample segments for evaluation (preserving existing sampling patterns)
            sample_segments = segments[:sample_size] if len(segments) >= sample_size else segments
            logger.info(f"Evaluating quality for {len(sample_segments)} segments from {len(segments)} total")
            
            total_scores = []
            
            # Evaluate each target language
            for lang in target_languages:
                lang_results = {
                    'language': lang,
                    'segments_evaluated': 0,
                    'average_score': 0.0,
                    'segment_scores': [],
                    'validation_issues': []
                }
                
                language_column_map = {
                    'en': 'english_text',
                    'de': 'german_text', 
                    'he': 'hebrew_text'
                }
                
                if lang not in language_column_map:
                    lang_results['validation_issues'].append(f"Unsupported language: {lang}")
                    quality_results['languages'][lang] = lang_results
                    continue
                
                column = language_column_map[lang]
                segment_scores = []
                
                # Evaluate sample segments (building upon existing evaluation patterns)
                for segment in sample_segments:
                    translation = segment.get(column)
                    
                    if not translation or self._is_non_verbal(segment['original_text']):
                        continue
                    
                    try:
                        # Use existing HistoricalEvaluator with enhanced Hebrew support
                        evaluation_result = self.evaluator.evaluate(
                            segment['original_text'],
                            translation,
                            language=lang,
                            enhanced=True  # Use enhanced evaluation for better accuracy
                        )
                        
                        if evaluation_result:
                            score = self.evaluator.get_score(evaluation_result)
                            segment_scores.append(score)
                            
                            # Store detailed segment evaluation
                            lang_results['segment_scores'].append({
                                'segment_index': segment['segment_index'],
                                'score': score,
                                'original_text': segment['original_text'][:100] + '...' if len(segment['original_text']) > 100 else segment['original_text'],
                                'evaluation_details': evaluation_result
                            })
                            
                            lang_results['segments_evaluated'] += 1
                            
                        else:
                            lang_results['validation_issues'].append(
                                f"Evaluation failed for segment {segment['segment_index']}"
                            )
                            
                    except Exception as e:
                        logger.warning(f"Quality evaluation failed for segment {segment['segment_index']} in {lang}: {e}")
                        lang_results['validation_issues'].append(
                            f"Segment {segment['segment_index']}: {str(e)}"
                        )
                
                # Calculate language-specific average (preserving existing calculation patterns)
                if segment_scores:
                    lang_results['average_score'] = sum(segment_scores) / len(segment_scores)
                    total_scores.extend(segment_scores)
                    logger.info(f"Quality evaluation for {lang}: {lang_results['average_score']:.1f}/10 ({len(segment_scores)} segments)")
                else:
                    logger.warning(f"No valid evaluations for {lang}")
                
                quality_results['languages'][lang] = lang_results
            
            # Calculate overall quality score
            if total_scores:
                quality_results['overall_quality'] = sum(total_scores) / len(total_scores)
                logger.info(f"Overall translation quality: {quality_results['overall_quality']:.1f}/10")
            
        except Exception as e:
            logger.error(f"Quality evaluation failed: {e}")
            quality_results['error'] = str(e)
        
        return quality_results

    def convert_segments_to_srt_format(self, interview_id: str, language: str = 'original') -> List[SRTSegment]:
        """
        Convert database segments to SRTSegment format for timing coordination.
        
        This method bridges database segments with the existing SRTTranslator
        timing mechanisms, ensuring perfect timing preservation.
        
        Args:
            interview_id: ID of the interview
            language: Language to extract ('original', 'en', 'de', 'he')
            
        Returns:
            List of SRTSegment objects with exact timing from database
        """
        segments = self.db.get_subtitle_segments(interview_id)
        srt_segments = []
        
        # Language column mapping
        text_column_map = {
            'original': 'original_text',
            'en': 'english_text', 
            'de': 'german_text',
            'he': 'hebrew_text'
        }
        
        if language not in text_column_map:
            raise ValueError(f"Unsupported language: {language}")
            
        text_column = text_column_map[language]
        
        for segment in segments:
            # Convert database timestamp (float seconds) to SRT format (HH:MM:SS,mmm)
            start_srt = self._seconds_to_srt_time(segment['start_time'])
            end_srt = self._seconds_to_srt_time(segment['end_time'])
            
            # Get text for specified language
            text = segment.get(text_column) or segment['original_text']
            
            srt_segment = SRTSegment(
                index=segment['segment_index'] + 1,  # SRT indices are 1-based
                start_time=start_srt,
                end_time=end_srt,
                text=text
            )
            
            srt_segments.append(srt_segment)
            
        logger.info(f"Converted {len(srt_segments)} database segments to SRT format for {language}")
        return srt_segments
        
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """
        Convert seconds to SRT timestamp format (HH:MM:SS,mmm).
        
        Args:
            seconds: Time in seconds
            
        Returns:
            SRT formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = round((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
        
    def _srt_time_to_seconds(self, srt_time: str) -> float:
        """
        Convert SRT timestamp format to seconds.
        
        Args:
            srt_time: SRT formatted timestamp (HH:MM:SS,mmm)
            
        Returns:
            Time in seconds as float
        """
        time_part, ms_part = srt_time.split(',')
        hours, minutes, seconds = map(int, time_part.split(':'))
        milliseconds = int(ms_part)
        
        total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
        return total_seconds
        
    def validate_timing_coordination(self, interview_id: str, target_language: str) -> Dict[str, Any]:
        """
        Enhanced timing coordination validation that builds upon SRTTranslator's proven validation.
        
        This validation adds database-specific checks while preserving all existing
        SRTTranslator boundary validation mechanisms. It extends rather than replaces
        the proven timing validation framework.
        
        Args:
            interview_id: ID of the interview to validate
            target_language: Language to validate timing for
            
        Returns:
            Comprehensive validation results with timing analysis
        """
        validation_results = {
            'timing_valid': True,
            'segment_count': 0,
            'timing_issues': [],
            'boundary_validation': True,
            'database_consistency': True,
            'srt_compatibility': True,
            'total_duration': 0.0,
            'database_validation_details': {}
        }
        
        try:
            # Get original segments from database
            original_segments = self.convert_segments_to_srt_format(interview_id, 'original')
            
            # Get translated segments
            translated_segments = self.convert_segments_to_srt_format(interview_id, target_language)
            
            validation_results['segment_count'] = len(original_segments)
            
            # 1. FOUNDATION: Use SRTTranslator's proven boundary validation
            srt_translator = SRTTranslator(self.translator)
            boundary_valid = srt_translator._validate_segment_boundaries(
                original_segments, 
                translated_segments
            )
            
            validation_results['boundary_validation'] = boundary_valid
            validation_results['srt_compatibility'] = boundary_valid
            
            if not boundary_valid:
                validation_results['timing_valid'] = False
                validation_results['timing_issues'].append("SRTTranslator boundary validation failed")
                
            # 2. ENHANCEMENT: Database-specific segment boundary validation
            db_validation = self._validate_database_segment_boundaries(interview_id, target_language)
            validation_results['database_validation_details'] = db_validation
            validation_results['database_consistency'] = db_validation['valid']
            
            if not db_validation['valid']:
                validation_results['timing_valid'] = False
                validation_results['timing_issues'].extend(db_validation['issues'])
                
            # 3. ENHANCEMENT: Cross-validation between database and SRT format
            srt_db_consistency = self._validate_srt_database_consistency(
                original_segments, translated_segments, interview_id, target_language
            )
            
            if not srt_db_consistency['consistent']:
                validation_results['timing_valid'] = False
                validation_results['timing_issues'].extend(srt_db_consistency['issues'])
                validation_results['srt_compatibility'] = False
                
            # 4. EXISTING: Enhanced timing gap analysis (preserved from original)
            if original_segments:
                first_segment_start = self._srt_time_to_seconds(original_segments[0].start_time)
                last_segment_end = self._srt_time_to_seconds(original_segments[-1].end_time)
                validation_results['total_duration'] = last_segment_end - first_segment_start
                
                # Enhanced gap detection with database coordination
                gap_analysis = self._analyze_timing_gaps_with_database(
                    original_segments, interview_id
                )
                validation_results['timing_issues'].extend(gap_analysis['issues'])
                
                if gap_analysis['critical_overlaps']:
                    validation_results['timing_valid'] = False
                    
            logger.info(f"Enhanced timing coordination validation: {'✅ PASSED' if validation_results['timing_valid'] else '❌ FAILED'}")
            logger.info(f"  SRT Boundary Validation: {'✅' if boundary_valid else '❌'}")
            logger.info(f"  Database Consistency: {'✅' if db_validation['valid'] else '❌'}")
            logger.info(f"  Cross-validation: {'✅' if srt_db_consistency['consistent'] else '❌'}")
            
        except Exception as e:
            logger.error(f"Enhanced timing validation failed: {e}")
            validation_results['timing_valid'] = False
            validation_results['timing_issues'].append(f"Validation exception: {str(e)}")
            
        return validation_results
        
    def _validate_database_segment_boundaries(self, interview_id: str, target_language: str) -> Dict[str, Any]:
        """
        Database-specific segment boundary validation that complements SRTTranslator validation.
        
        This method validates database integrity while building upon existing patterns.
        """
        validation = {
            'valid': True,
            'issues': [],
            'segment_integrity': True,
            'timestamp_consistency': True,
            'translation_alignment': True
        }
        
        try:
            # Check database segment integrity
            conn = self.db._get_connection()
            
            # Validate segment sequence continuity
            cursor = conn.execute("""
                SELECT segment_index, start_time, end_time, original_text
                FROM subtitle_segments 
                WHERE interview_id = ?
                ORDER BY segment_index
            """, (interview_id,))
            
            segments = cursor.fetchall()
            
            # Check for missing segments in sequence
            expected_indices = set(range(len(segments)))
            actual_indices = set(seg[0] for seg in segments)
            
            if expected_indices != actual_indices:
                missing = expected_indices - actual_indices
                validation['issues'].append(f"Missing segment indices: {sorted(missing)}")
                validation['segment_integrity'] = False
                validation['valid'] = False
                
            # Check for timestamp consistency
            for i, segment in enumerate(segments):
                start_time, end_time = segment[1], segment[2]
                
                if start_time >= end_time:
                    validation['issues'].append(
                        f"Invalid timing in segment {segment[0]}: start ({start_time}) >= end ({end_time})"
                    )
                    validation['timestamp_consistency'] = False
                    validation['valid'] = False
                    
                # Check for negative timestamps
                if start_time < 0 or end_time < 0:
                    validation['issues'].append(
                        f"Negative timestamp in segment {segment[0]}: start={start_time}, end={end_time}"
                    )
                    validation['timestamp_consistency'] = False
                    validation['valid'] = False
                    
            # Validate translation alignment if target language segments exist
            if target_language != 'original':
                # Check if target language column exists and has data
                language_column_map = {
                    'de': 'german_text',
                    'en': 'english_text', 
                    'he': 'hebrew_text'
                }
                
                target_column = language_column_map.get(target_language)
                if target_column:
                    # Check for non-null translated text in target language
                    translation_cursor = conn.execute(f"""
                        SELECT segment_index, start_time, end_time, {target_column}
                        FROM subtitle_segments 
                        WHERE interview_id = ? AND {target_column} IS NOT NULL AND {target_column} != ''
                        ORDER BY segment_index
                    """, (interview_id,))
                    
                    translated_segments = translation_cursor.fetchall()
                    
                    if translated_segments:
                        # Check alignment with original segments  
                        if len(segments) != len(translated_segments):
                            validation['issues'].append(
                                f"Segment count mismatch: original={len(segments)}, {target_language}={len(translated_segments)}"
                            )
                            validation['translation_alignment'] = False
                            validation['valid'] = False
                            
                        # Check timing preservation
                        for orig, trans in zip(segments, translated_segments):
                            if orig[1] != trans[1] or orig[2] != trans[2]:  # start_time, end_time
                                validation['issues'].append(
                                    f"Timing mismatch in segment {orig[0]}: "
                                    f"original=({orig[1]}, {orig[2]}), {target_language}=({trans[1]}, {trans[2]})"
                                )
                                validation['translation_alignment'] = False
                                validation['valid'] = False
                            
        except Exception as e:
            validation['issues'].append(f"Database validation error: {str(e)}")
            validation['valid'] = False
            
        return validation
        
    def _validate_srt_database_consistency(self, original_segments: List[SRTSegment], 
                                         translated_segments: List[SRTSegment],
                                         interview_id: str, target_language: str) -> Dict[str, Any]:
        """
        Cross-validate consistency between SRT format and database storage.
        
        This ensures the database segments exactly match what SRTTranslator expects.
        """
        consistency = {
            'consistent': True,
            'issues': [],
            'format_alignment': True,
            'content_alignment': True
        }
        
        try:
            # Get database segments for comparison
            conn = self.db._get_connection()
            cursor = conn.execute("""
                SELECT segment_index, start_time, end_time, original_text
                FROM subtitle_segments 
                WHERE interview_id = ?
                ORDER BY segment_index
            """, (interview_id,))
            
            db_original_segments = cursor.fetchall()
            
            # Validate format alignment
            if len(original_segments) != len(db_original_segments):
                consistency['issues'].append(
                    f"Format mismatch: SRT has {len(original_segments)} segments, "
                    f"database has {len(db_original_segments)}"
                )
                consistency['format_alignment'] = False
                consistency['consistent'] = False
                
            # Validate content alignment
            for i, (srt_seg, db_seg) in enumerate(zip(original_segments, db_original_segments)):
                # Convert database timestamps to SRT format for comparison
                db_start_srt = self._seconds_to_srt_time(db_seg[1])
                db_end_srt = self._seconds_to_srt_time(db_seg[2])
                
                if srt_seg.start_time != db_start_srt:
                    consistency['issues'].append(
                        f"Start time mismatch in segment {i}: "
                        f"SRT={srt_seg.start_time}, DB={db_start_srt}"
                    )
                    consistency['content_alignment'] = False
                    consistency['consistent'] = False
                    
                if srt_seg.end_time != db_end_srt:
                    consistency['issues'].append(
                        f"End time mismatch in segment {i}: "
                        f"SRT={srt_seg.end_time}, DB={db_end_srt}"
                    )
                    consistency['content_alignment'] = False
                    consistency['consistent'] = False
                    
                if srt_seg.text.strip() != db_seg[3].strip():
                    consistency['issues'].append(
                        f"Text mismatch in segment {i}: content differs between SRT and database"
                    )
                    consistency['content_alignment'] = False
                    consistency['consistent'] = False
                    
        except Exception as e:
            consistency['issues'].append(f"Cross-validation error: {str(e)}")
            consistency['consistent'] = False
            
        return consistency
        
    def _analyze_timing_gaps_with_database(self, segments: List[SRTSegment], 
                                         interview_id: str) -> Dict[str, Any]:
        """
        Enhanced timing gap analysis that leverages database segment information.
        
        Builds upon existing gap detection with database-backed insights.
        """
        analysis = {
            'issues': [],
            'critical_overlaps': False,
            'gap_count': 0,
            'overlap_count': 0,
            'database_insights': {}
        }
        
        try:
            # Existing gap detection logic (preserved)
            for i in range(len(segments) - 1):
                current_end = self._srt_time_to_seconds(segments[i].end_time)
                next_start = self._srt_time_to_seconds(segments[i + 1].start_time)
                
                gap = next_start - current_end
                if abs(gap) > 0.001:  # More than 1ms difference
                    if gap > 0:
                        analysis['issues'].append(
                            f"Gap of {gap:.3f}s between segments {i+1} and {i+2}"
                        )
                        analysis['gap_count'] += 1
                    else:
                        analysis['issues'].append(
                            f"Overlap of {abs(gap):.3f}s between segments {i+1} and {i+2}"
                        )
                        analysis['overlap_count'] += 1
                        
                        # Critical overlaps compromise subtitle readability
                        if abs(gap) > 0.1:  # More than 100ms overlap
                            analysis['critical_overlaps'] = True
                            
            # Database-enhanced insights
            if self.db:
                db_timing_validation = self.db.validate_subtitle_timing(interview_id)
                analysis['database_insights'] = {
                    'database_gaps': len(db_timing_validation.get('gaps', [])),
                    'database_overlaps': len(db_timing_validation.get('overlaps', [])),
                    'cross_validation': True
                }
                
                # Cross-validate findings
                db_gap_count = len(db_timing_validation.get('gaps', []))
                if db_gap_count != analysis['gap_count']:
                    analysis['issues'].append(
                        f"Gap count mismatch: SRT analysis found {analysis['gap_count']}, "
                        f"database found {db_gap_count}"
                    )
                    
        except Exception as e:
            analysis['issues'].append(f"Gap analysis error: {str(e)}")
            
        return analysis
        
    def generate_coordinated_srt(self, interview_id: str, target_language: str, output_path: Path) -> bool:
        """
        Generate an SRT file from database segments using existing SRTTranslator logic.
        
        This coordinates database segments with the existing SRT generation logic,
        preserving all timing validation from the proven SRTTranslator workflow.
        
        Args:
            interview_id: ID of the interview
            target_language: Language to generate SRT for
            output_path: Path where to save the SRT file
            
        Returns:
            True if SRT generation successful, False otherwise
        """
        try:
            # Convert database segments to SRT format
            srt_segments = self.convert_segments_to_srt_format(interview_id, target_language)
            
            if not srt_segments:
                logger.warning(f"No segments found for {interview_id} in {target_language}")
                return False
                
            # Validate timing using existing SRTTranslator coordination
            timing_validation = self.validate_timing_coordination(interview_id, target_language)
            if not timing_validation['timing_valid']:
                logger.error(f"Timing validation failed: {timing_validation['timing_issues']}")
                return False
                
            # Use existing SRTTranslator save logic to ensure complete compatibility
            from .srt_translator import SRTTranslator
            srt_translator = SRTTranslator(self.translator)
            
            # Generate SRT using existing proven save method
            success = srt_translator.save_translated_srt(srt_segments, str(output_path))
            
            if success:
                logger.info(f"Generated coordinated SRT file using existing SRTTranslator logic: {output_path}")
            else:
                logger.error(f"Failed to generate SRT using existing SRTTranslator logic")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to generate coordinated SRT: {e}")
            return False
    
    def coordinate_with_srt_workflow(self, interview_id: str, target_languages: List[str]) -> Dict[str, Any]:
        """
        Coordinate database segments with the complete existing SRT workflow.
        
        This method ensures that database segments work seamlessly with all existing
        SRT generation logic while preserving timing validation and compatibility.
        
        Args:
            interview_id: ID of the interview to coordinate
            target_languages: List of languages to coordinate
            
        Returns:
            Dictionary with coordination results for each language
        """
        coordination_results = {
            'overall_success': True,
            'languages': {},
            'workflow_compatibility': True,
            'timing_preservation': True
        }
        
        try:
            from .srt_translator import SRTTranslator
            srt_translator = SRTTranslator(self.translator)
            
            for language in target_languages:
                lang_results = {
                    'srt_conversion_success': False,
                    'timing_validation_success': False,
                    'boundary_validation_success': False,
                    'workflow_integration_success': False,
                    'segment_count': 0,
                    'issues': []
                }
                
                try:
                    # Step 1: Convert database segments to SRT format
                    srt_segments = self.convert_segments_to_srt_format(interview_id, language)
                    lang_results['segment_count'] = len(srt_segments)
                    
                    if srt_segments:
                        lang_results['srt_conversion_success'] = True
                        
                        # Step 2: Validate timing coordination using existing logic
                        timing_validation = self.validate_timing_coordination(interview_id, language)
                        lang_results['timing_validation_success'] = timing_validation['timing_valid']
                        
                        if not timing_validation['timing_valid']:
                            lang_results['issues'].extend(timing_validation['timing_issues'])
                            coordination_results['timing_preservation'] = False
                        
                        # Step 3: Test boundary validation using existing SRTTranslator method
                        original_segments = self.convert_segments_to_srt_format(interview_id, 'original')
                        boundary_valid = srt_translator._validate_segment_boundaries(
                            original_segments, srt_segments
                        )
                        lang_results['boundary_validation_success'] = boundary_valid
                        
                        if not boundary_valid:
                            lang_results['issues'].append("Segment boundaries not preserved")
                            coordination_results['workflow_compatibility'] = False
                        
                        # Step 4: Test workflow integration with existing SRT methods
                        try:
                            # Test that segments work with existing estimate_cost method
                            # (This validates format compatibility)
                            temp_path = f"/tmp/test_{interview_id}_{language}.srt"
                            save_success = srt_translator.save_translated_srt(srt_segments, temp_path)
                            
                            if save_success:
                                # Test parsing the generated file
                                parsed_segments = srt_translator.parse_srt(temp_path)
                                if len(parsed_segments) == len(srt_segments):
                                    lang_results['workflow_integration_success'] = True
                                else:
                                    lang_results['issues'].append("SRT round-trip parsing failed")
                                
                                # Clean up temp file
                                import os
                                if os.path.exists(temp_path):
                                    os.remove(temp_path)
                            else:
                                lang_results['issues'].append("Failed to save SRT using existing workflow")
                        
                        except Exception as workflow_e:
                            lang_results['issues'].append(f"Workflow integration error: {workflow_e}")
                    
                    else:
                        lang_results['issues'].append(f"No segments found for {language}")
                
                except Exception as lang_e:
                    lang_results['issues'].append(f"Language processing error: {lang_e}")
                    logger.error(f"Error coordinating {language} for {interview_id}: {lang_e}")
                
                coordination_results['languages'][language] = lang_results
                
                # Update overall success
                if not (lang_results['srt_conversion_success'] and 
                       lang_results['timing_validation_success'] and 
                       lang_results['boundary_validation_success'] and
                       lang_results['workflow_integration_success']):
                    coordination_results['overall_success'] = False
            
            logger.info(
                f"SRT workflow coordination: "
                f"{'✅ SUCCESS' if coordination_results['overall_success'] else '❌ FAILED'} "
                f"for {len(target_languages)} languages"
            )
            
        except Exception as e:
            logger.error(f"SRT workflow coordination failed: {e}")
            coordination_results['overall_success'] = False
            coordination_results['workflow_compatibility'] = False
            coordination_results['timing_preservation'] = False
            
        return coordination_results
    
    def preserve_srt_timing_validation(self, interview_id: str, target_language: str) -> Dict[str, Any]:
        """
        Preserve existing SRT timing validation mechanisms for database segments.
        
        This method ensures that database segments maintain the exact same timing
        validation standards as the existing SRTTranslator, preventing any timing
        issues that could break video synchronization.
        
        Args:
            interview_id: ID of the interview
            target_language: Language to validate
            
        Returns:
            Dictionary with comprehensive timing validation results
        """
        validation_results = {
            'timing_preserved': True,
            'srt_compatibility': True,
            'validation_method': 'existing_srt_translator_logic',
            'timing_metrics': {},
            'validation_details': [],
            'issues': []
        }
        
        try:
            from .srt_translator import SRTTranslator
            srt_translator = SRTTranslator(self.translator)
            
            # Get segments in SRT format
            original_segments = self.convert_segments_to_srt_format(interview_id, 'original')
            target_segments = self.convert_segments_to_srt_format(interview_id, target_language)
            
            if not original_segments or not target_segments:
                validation_results['timing_preserved'] = False
                validation_results['issues'].append("Missing segments for validation")
                return validation_results
            
            # Use existing SRTTranslator boundary validation (the proven method)
            boundary_validation = srt_translator._validate_segment_boundaries(
                original_segments, target_segments
            )
            validation_results['srt_compatibility'] = boundary_validation
            
            if not boundary_validation:
                validation_results['timing_preserved'] = False
                validation_results['issues'].append("Failed existing SRTTranslator boundary validation")
            
            # Additional timing metrics for analysis
            timing_metrics = {
                'segment_count': len(original_segments),
                'total_duration': 0.0,
                'average_segment_length': 0.0,
                'timing_precision': 'millisecond',
                'gap_analysis': []
            }
            
            if original_segments:
                # Calculate duration metrics
                start_seconds = self._srt_time_to_seconds(original_segments[0].start_time)
                end_seconds = self._srt_time_to_seconds(original_segments[-1].end_time)
                timing_metrics['total_duration'] = end_seconds - start_seconds
                timing_metrics['average_segment_length'] = timing_metrics['total_duration'] / len(original_segments)
                
                # Analyze segment gaps using existing precision standards
                for i in range(len(original_segments) - 1):
                    current_end = self._srt_time_to_seconds(original_segments[i].end_time)
                    next_start = self._srt_time_to_seconds(original_segments[i + 1].start_time)
                    gap = next_start - current_end
                    
                    timing_metrics['gap_analysis'].append({
                        'segment_pair': f"{i+1}-{i+2}",
                        'gap_seconds': gap,
                        'gap_type': 'gap' if gap > 0 else 'overlap' if gap < 0 else 'perfect'
                    })
                    
                    # Flag timing issues using existing standards
                    if abs(gap) > 0.001:  # Same 1ms threshold as existing validation
                        validation_results['issues'].append(
                            f"Timing {'gap' if gap > 0 else 'overlap'} of {abs(gap):.3f}s "
                            f"between segments {i+1} and {i+2}"
                        )
                        if gap < 0:  # Overlaps are more serious
                            validation_results['timing_preserved'] = False
            
            validation_results['timing_metrics'] = timing_metrics
            validation_results['validation_details'].append(
                f"Validated {len(original_segments)} segments using existing SRTTranslator logic"
            )
            validation_results['validation_details'].append(
                f"Boundary validation: {'PASSED' if boundary_validation else 'FAILED'}"
            )
            
            logger.info(
                f"SRT timing validation: {'✅ PRESERVED' if validation_results['timing_preserved'] else '❌ VIOLATED'} "
                f"({len(original_segments)} segments)"
            )
            
        except Exception as e:
            logger.error(f"SRT timing validation failed: {e}")
            validation_results['timing_preserved'] = False
            validation_results['srt_compatibility'] = False
            validation_results['issues'].append(f"Validation error: {e}")
            
        return validation_results


# SRT Workflow Coordination Functions
def coordinate_database_srt_generation(db: Database,
                                      interview_id: str,
                                      target_languages: List[str],
                                      output_dir: Path,
                                      translator: Optional[HistoricalTranslator] = None) -> Dict[str, Any]:
    """
    Coordinate database segments with existing SRT generation logic.
    
    This function ensures that SRT files generated from database segments
    maintain full compatibility with the existing SRTTranslator workflow
    while preserving all timing validation mechanisms.
    
    Args:
        db: Database instance
        interview_id: ID of the interview to process
        target_languages: List of languages to generate SRT files for
        output_dir: Directory to save SRT files
        translator: Optional HistoricalTranslator instance
        
    Returns:
        Dictionary with generation results and timing validation
    """
    coordination_results = {
        'overall_success': True,
        'srt_files_generated': {},
        'timing_validation': {},
        'workflow_coordination': {},
        'preservation_of_existing_logic': True
    }
    
    try:
        # Create DatabaseTranslator instance
        db_translator = DatabaseTranslator(db, translator)
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for language in target_languages:
            lang_results = {
                'srt_file_path': None,
                'generation_success': False,
                'timing_preserved': False,
                'workflow_compatible': False,
                'issues': []
            }
            
            try:
                # Generate SRT file using coordinated logic
                srt_filename = f"{interview_id}_{language}.srt"
                srt_path = output_dir / srt_filename
                
                generation_success = db_translator.generate_coordinated_srt(
                    interview_id, language, srt_path
                )
                
                lang_results['generation_success'] = generation_success
                lang_results['srt_file_path'] = str(srt_path) if generation_success else None
                
                if generation_success:
                    # Validate timing preservation
                    timing_validation = db_translator.preserve_srt_timing_validation(
                        interview_id, language
                    )
                    lang_results['timing_preserved'] = timing_validation['timing_preserved']
                    
                    if not timing_validation['timing_preserved']:
                        lang_results['issues'].extend(timing_validation['issues'])
                        coordination_results['preservation_of_existing_logic'] = False
                    
                    # Test full workflow coordination
                    workflow_coordination = db_translator.coordinate_with_srt_workflow(
                        interview_id, [language]
                    )
                    lang_results['workflow_compatible'] = workflow_coordination['overall_success']
                    
                    if not workflow_coordination['overall_success']:
                        if language in workflow_coordination['languages']:
                            lang_results['issues'].extend(
                                workflow_coordination['languages'][language]['issues']
                            )
                        coordination_results['preservation_of_existing_logic'] = False
                
                else:
                    lang_results['issues'].append("SRT generation failed")
                    coordination_results['overall_success'] = False
                
            except Exception as lang_e:
                lang_results['issues'].append(f"Language processing error: {lang_e}")
                logger.error(f"Error generating SRT for {language}: {lang_e}")
                coordination_results['overall_success'] = False
            
            coordination_results['srt_files_generated'][language] = lang_results
        
        # Generate overall coordination summary
        successful_languages = [
            lang for lang, results in coordination_results['srt_files_generated'].items()
            if results['generation_success'] and results['timing_preserved'] and results['workflow_compatible']
        ]
        
        coordination_results['timing_validation'] = {
            'all_languages_preserved': len(successful_languages) == len(target_languages),
            'successful_languages': successful_languages,
            'validation_method': 'existing_srt_translator_logic'
        }
        
        coordination_results['workflow_coordination'] = {
            'full_compatibility': coordination_results['preservation_of_existing_logic'],
            'generated_files': len([r for r in coordination_results['srt_files_generated'].values() 
                                  if r['generation_success']]),
            'total_requested': len(target_languages)
        }
        
        logger.info(
            f"Database-SRT coordination: "
            f"{'✅ SUCCESS' if coordination_results['overall_success'] else '❌ FAILED'} "
            f"({len(successful_languages)}/{len(target_languages)} languages)"
        )
        
    except Exception as e:
        logger.error(f"Database-SRT coordination failed: {e}")
        coordination_results['overall_success'] = False
        coordination_results['preservation_of_existing_logic'] = False
        
    return coordination_results


# Integration functions for pipeline compatibility
def validate_interview_translation_quality(db: Database,
                                          interview_id: str,
                                          target_languages: List[str] = None,
                                          enhanced_validation: bool = False,
                                          translator: Optional[HistoricalTranslator] = None,
                                          evaluator: Optional[HistoricalEvaluator] = None) -> Dict[str, Any]:
    """
    Validate translation quality for an interview using enhanced database validation.
    
    This function builds upon the existing quality validation framework,
    providing a simple interface for comprehensive translation quality assessment.
    
    Args:
        db: Database instance
        interview_id: ID of the interview to validate
        target_languages: List of target language codes (default: ['en', 'de', 'he'])
        enhanced_validation: Whether to perform comprehensive AI-based quality evaluation
        translator: Optional HistoricalTranslator instance
        evaluator: Optional HistoricalEvaluator instance
        
    Returns:
        Dictionary with validation results for each language
    """
    if target_languages is None:
        target_languages = ['en', 'de', 'he']
        
    db_translator = DatabaseTranslator(db, translator, evaluator)
    validation_results = {
        'interview_id': interview_id,
        'languages': {},
        'overall_valid': True,
        'validation_method': 'enhanced_database_validation_pipeline'
    }
    
    for lang in target_languages:
        logger.info(f"Validating {lang} translation quality for interview {interview_id}")
        
        # Use enhanced validation method that builds upon existing framework
        lang_validation = db_translator.validate_translations(
            interview_id,
            lang,
            enhanced_quality_check=enhanced_validation
        )
        
        validation_results['languages'][lang] = lang_validation
        
        # Update overall validity
        if not lang_validation['valid']:
            validation_results['overall_valid'] = False
            
        # Log summary
        if lang_validation['valid']:
            logger.info(f"✅ {lang} validation passed: {lang_validation['validated']} segments validated")
        else:
            logger.warning(f"⚠️ {lang} validation issues: {len(lang_validation['issues'])} issues found")
    
    return validation_results


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


def coordinate_translation_timing(db: Database,
                                interview_id: str,
                                target_languages: List[str] = None,
                                validate_timing: bool = True) -> Dict[str, Any]:
    """
    Coordinate existing translation timing mechanisms with database segments.
    
    This function implements Task 3.4 from the subtitle-first architecture spec,
    ensuring that database translation maintains perfect timing coordination
    with the existing SRTTranslator mechanisms.
    
    Args:
        db: Database instance
        interview_id: ID of the interview to coordinate
        target_languages: Languages to coordinate (default: ['en', 'de', 'he'])
        validate_timing: Whether to run timing validation
        
    Returns:
        Dictionary with coordination results for each language
    """
    if target_languages is None:
        target_languages = ['en', 'de', 'he']
        
    logger.info(f"Coordinating translation timing for interview {interview_id}")
    
    db_translator = DatabaseTranslator(db)
    coordination_results = {
        'interview_id': interview_id,
        'languages': {},
        'overall_success': True,
        'timing_coordination_active': True
    }
    
    try:
        # First verify that segments exist in database
        segments = db.get_subtitle_segments(interview_id)
        if not segments:
            logger.error(f"No segments found for interview {interview_id}")
            coordination_results['overall_success'] = False
            coordination_results['error'] = "No segments found in database"
            return coordination_results
            
        logger.info(f"Found {len(segments)} segments to coordinate")
        
        # Coordinate timing for each target language
        for lang in target_languages:
            lang_results = {
                'timing_valid': False,
                'boundary_validation': False,
                'segment_count': 0,
                'timing_issues': [],
                'coordination_method': 'database_to_srt_bridge'
            }
            
            try:
                # Validate timing coordination using existing SRTTranslator mechanisms
                if validate_timing:
                    timing_validation = db_translator.validate_timing_coordination(interview_id, lang)
                    lang_results.update(timing_validation)
                    
                    if timing_validation['timing_valid']:
                        logger.info(f"✅ Timing coordination validated for {lang}")
                    else:
                        logger.warning(f"⚠️ Timing issues detected in {lang}: {timing_validation['timing_issues']}")
                        coordination_results['overall_success'] = False
                        
                # Test SRT segment conversion
                try:
                    srt_segments = db_translator.convert_segments_to_srt_format(interview_id, lang)
                    lang_results['srt_conversion_success'] = True
                    lang_results['converted_segments'] = len(srt_segments)
                    
                    # Verify that conversion maintains timing precision
                    if srt_segments:
                        original_srt = db_translator.convert_segments_to_srt_format(interview_id, 'original')
                        if len(srt_segments) == len(original_srt):
                            lang_results['segment_count_match'] = True
                            logger.info(f"✅ Segment count matches for {lang}: {len(srt_segments)}")
                        else:
                            lang_results['segment_count_match'] = False
                            logger.warning(f"⚠️ Segment count mismatch in {lang}: {len(srt_segments)} vs {len(original_srt)}")
                            
                except Exception as e:
                    logger.error(f"SRT conversion failed for {lang}: {e}")
                    lang_results['srt_conversion_success'] = False
                    lang_results['srt_conversion_error'] = str(e)
                    coordination_results['overall_success'] = False
                    
            except Exception as e:
                logger.error(f"Timing coordination failed for {lang}: {e}")
                lang_results['error'] = str(e)
                coordination_results['overall_success'] = False
                
            coordination_results['languages'][lang] = lang_results
            
        # Summary logging
        successful_languages = [
            lang for lang, results in coordination_results['languages'].items()
            if results.get('timing_valid', False)
        ]
        
        logger.info(f"Timing coordination complete: {len(successful_languages)}/{len(target_languages)} languages successful")
        
        if coordination_results['overall_success']:
            logger.info("✅ All timing coordination checks passed")
        else:
            logger.warning("⚠️ Some timing coordination issues detected - check individual language results")
            
    except Exception as e:
        logger.error(f"Critical timing coordination failure: {e}")
        coordination_results['overall_success'] = False
        coordination_results['critical_error'] = str(e)
        
    return coordination_results