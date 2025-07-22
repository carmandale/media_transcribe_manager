#!/usr/bin/env python3
"""
SRT Translation Module with Language Detection and Batch Optimization
-------------------------------------------------------------------
Translates SRT subtitle files while preserving timing and original language segments.
For mixed-language interviews, only translates segments not already in the target language.

Features:
- Batch translation reduces API calls by 50-100x
- Deduplication of repeated phrases
- Preserves segments already in target language
- Maintains exact timing synchronization
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from .translate import HistoricalTranslator

# Try to import langdetect for language detection
try:
    from langdetect import detect, detect_langs, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    logging.warning("langdetect not available - will use basic language detection")

logger = logging.getLogger(__name__)


@dataclass
class SRTSegment:
    """Represents a single subtitle segment."""
    index: int
    start_time: str
    end_time: str
    text: str
    detected_language: Optional[str] = None


class SRTTranslator:
    """Handles SRT file translation with language detection."""
    
    # Regular expressions for parsing SRT
    RE_TIMING = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})')
    RE_INDEX = re.compile(r'^\d+$')
    
    # Enhanced language detection patterns
    LANGUAGE_PATTERNS = {
        'en': {
            'words': {'the', 'and', 'of', 'to', 'in', 'is', 'was', 'that', 'have', 'has', 
                     'had', 'will', 'would', 'could', 'should', 'yes', 'no', 'okay', 
                     'yeah', 'well', 'so', 'but', 'what', 'how', 'are', 'you', 'hello',
                     'today', 'name', 'your', 'my', 'this', 'with', 'for', 'on', 'at'},
            'pattern': re.compile(r'\b(the|and|of|to|in|is|was|that|have|has|had|will|would|could|should|how|are|you|hello)\b', re.I)
        },
        'de': {
            'words': {'der', 'die', 'das', 'und', 'von', 'zu', 'ist', 'war', 'haben', 
                     'hat', 'hatte', 'werden', 'wurde', 'ja', 'nein', 'aber', 'was', 'dass',
                     'mein', 'meine', 'ich', 'wir', 'sie', 'er', 'es', 'wie', 'geht'},
            'pattern': re.compile(r'\b(der|die|das|und|von|zu|ist|war|haben|hat|hatte|werden|wurde|mein|ich|wie|geht)\b', re.I)
        },
        'he': {
            'words': {'של', 'את', 'על', 'עם', 'הוא', 'היא', 'כן', 'לא', 'מה', 'זה'},
            'pattern': re.compile(r'[\u0590-\u05FF]+')  # Hebrew character range
        }
    }
    
    # Non-verbal sounds that should not be translated
    NON_VERBAL_SOUNDS = {'♪', '♪♪', '[Music]', '[Applause]', '[Laughter]', '[Silence]', '...', '***', '--'}
    
    def __init__(self, translator: Optional[HistoricalTranslator] = None):
        """
        Initialize SRT translator.
        
        Args:
            translator: HistoricalTranslator instance (creates new if not provided)
        """
        self.translator = translator or HistoricalTranslator()
        self._detection_cache = {}  # Cache for language detection results
    
    def parse_srt(self, srt_path: str) -> List[SRTSegment]:
        """
        Parse an SRT file into structured segments.
        
        Args:
            srt_path: Path to the SRT file
            
        Returns:
            List of SRTSegment objects
        """
        segments = []
        
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read SRT file {srt_path}: {e}")
            return segments
        
        # Split by double newline to get subtitle blocks
        blocks = content.strip().split('\n\n')
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            # Parse index
            if not self.RE_INDEX.match(lines[0]):
                continue
            index = int(lines[0])
            
            # Parse timing
            timing_match = self.RE_TIMING.match(lines[1])
            if not timing_match:
                logger.warning(f"Invalid timing in segment {index}: {lines[1]}")
                continue
            
            start_time = timing_match.group(1)
            end_time = timing_match.group(2)
            
            # Join remaining lines as text
            text = '\n'.join(lines[2:])
            
            # Create segment
            segment = SRTSegment(
                index=index,
                start_time=start_time,
                end_time=end_time,
                text=text
            )
            
            segments.append(segment)
        
        logger.info(f"Parsed {len(segments)} segments from {srt_path}")
        return segments
    
    def detect_segment_language(self, segment: SRTSegment) -> Optional[str]:
        """
        Detect the language of a subtitle segment with caching.
        
        Args:
            segment: SRTSegment to analyze
            
        Returns:
            Detected language code ('en', 'de', 'he') or None
        """
        text = segment.text.strip()
        if not text:
            return None
            
        # Check cache first
        if text in self._detection_cache:
            return self._detection_cache[text]
        
        # Skip very short texts or non-verbal sounds
        if len(text) < 3 or text in self.NON_VERBAL_SOUNDS:
            return None
            
        # Clean text for detection
        clean_text = text.lower()
        
        # Fast pattern matching for common languages - use scoring to handle overlaps
        words = set(clean_text.split())
        lang_scores = {}
        
        for lang, data in self.LANGUAGE_PATTERNS.items():
            if lang == 'he':
                # Hebrew detection by character range
                if data['pattern'].search(text):
                    self._detection_cache[text] = lang
                    return lang
            else:
                # Word-based detection for other languages
                matches = words & data['words']
                if matches:
                    lang_scores[lang] = len(matches)
        
        # Return language with most matches
        if lang_scores:
            best_lang = max(lang_scores, key=lang_scores.get)
            self._detection_cache[text] = best_lang
            return best_lang
        
        # Try langdetect for ambiguous cases
        if HAS_LANGDETECT:
            try:
                # Get probabilities for each language
                langs = detect_langs(text)
                if langs and langs[0].prob > 0.4:  # Confidence threshold (lowered for short texts)
                    detected = langs[0].lang
                    # Map langdetect codes to our codes
                    lang_map = {'en': 'en', 'de': 'de', 'he': 'he', 'iw': 'he'}  # iw is old code for Hebrew
                    result = lang_map.get(detected)
                    if result:
                        self._detection_cache[text] = result
                        return result
            except LangDetectException:
                pass
        
        return None
    
    def _validate_segment_boundaries(self, original_segments: List[SRTSegment], translated_segments: List[SRTSegment]) -> bool:
        """
        Validate that translated segments maintain exact same boundaries as original.
        
        This is CRITICAL for subtitle files - any boundary violation breaks video synchronization.
        
        Args:
            original_segments: Original SRT segments
            translated_segments: Translated SRT segments
            
        Returns:
            True if all boundaries are preserved, False if any violations found
        """
        if len(original_segments) != len(translated_segments):
            logger.error(f"Segment count mismatch: {len(original_segments)} → {len(translated_segments)}")
            return False
        
        for i, (orig, trans) in enumerate(zip(original_segments, translated_segments)):
            if orig.index != trans.index:
                logger.error(f"Index mismatch at position {i}: {orig.index} → {trans.index}")
                return False
            
            if orig.start_time != trans.start_time:
                logger.error(f"Start time mismatch in segment {orig.index}: {orig.start_time} → {trans.start_time}")
                return False
                
            if orig.end_time != trans.end_time:
                logger.error(f"End time mismatch in segment {orig.index}: {orig.end_time} → {trans.end_time}")
                return False
        
        logger.info("✅ Segment boundary validation passed - all timing preserved")
        return True
    
    def should_translate_segment(self, segment: SRTSegment, target_language: str) -> bool:
        """
        Determine if a segment should be translated.
        
        Args:
            segment: SRTSegment to check
            target_language: Target language code
            
        Returns:
            True if segment should be translated, False if it should be preserved
        """
        # Skip empty or non-verbal segments
        text = segment.text.strip()
        if not text or text in self.NON_VERBAL_SOUNDS:
            return False
            
        # Detect language if not already done
        if segment.detected_language is None:
            segment.detected_language = self.detect_segment_language(segment)
        
        # Don't translate if already in target language
        if segment.detected_language == target_language:
            logger.debug(f"Segment {segment.index} already in {target_language}: {text[:50]}...")
            return False
        
        # Don't translate very short segments (likely just punctuation or numbers)
        if len(text) < 3:
            return False
        
        return True
    
    def batch_translate(self, texts: List[str], target_language: str, 
                       source_language: Optional[str] = None) -> List[str]:
        """
        Translate multiple texts in a single API call for efficiency.
        
        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Source language code (optional)
            
        Returns:
            List of translated texts in same order as input
        """
        if not texts:
            return []
            
        # For single text, just use regular translate
        if len(texts) == 1:
            result = self.translator.translate(texts[0], target_language, source_language)
            return [result] if result else ['']
            
        # Join texts with a unique separator that won't appear in subtitles
        separator = "\n<<<SEP>>>\n"
        combined_text = separator.join(texts)
        
        # Translate using batch_translate (provider selected automatically)
        try:
            logger.info(f"Batch translating {len(texts)} texts to {target_language}")
            # Use the HistoricalTranslator's batch_translate method
            translated_texts = self.translator.batch_translate(
                texts,
                target_language, 
                source_language
                # No provider specified - let HistoricalTranslator choose the best one
            )
            
            return translated_texts
            
        except Exception as e:
            logger.error(f"Batch translation failed: {e}")
            # Fall back to individual translation
            return [self.translator.translate(text, target_language, source_language) or '' 
                    for text in texts]
    
    def translate_srt(self, 
                      srt_path: str, 
                      target_language: str,
                      source_language: Optional[str] = None,
                      preserve_original_when_matching: bool = True,
                      batch_size: int = 100) -> List[SRTSegment]:
        """
        Translate an SRT file using batch optimization for 50-100x efficiency.
        
        This implementation:
        - Deduplicates repeated phrases (translate once, apply everywhere)
        - Batches translations to minimize API calls
        - Preserves segments already in target language
        - Maintains exact timing synchronization
        
        Args:
            srt_path: Path to source SRT file
            target_language: Target language code ('en', 'de', 'he')
            source_language: Source language code (optional, will auto-detect)
            preserve_original_when_matching: If True, preserve segments already in target language
            batch_size: Number of unique texts to translate per API call
            
        Returns:
            List of translated SRTSegment objects
        """
        logger.info(f"Translating {srt_path} to {target_language}")
        start_time = datetime.now()
        
        # Parse the SRT file
        segments = self.parse_srt(srt_path)
        if not segments:
            return []
        
        total_segments = len(segments)
        logger.info(f"Parsed {total_segments} segments from {srt_path}")
        
        # Build translation map - only unique texts that need translation
        texts_to_translate = {}  # {original_text: translated_text}
        segment_indices = {}  # Track which segments use each text
        
        for i, segment in enumerate(segments):
            if not preserve_original_when_matching or self.should_translate_segment(segment, target_language):
                text = segment.text
                if text not in texts_to_translate:
                    texts_to_translate[text] = None
                    segment_indices[text] = []
                segment_indices[text].append(i)
                
        unique_count = len(texts_to_translate)
        logger.info(f"Found {unique_count} unique texts to translate out of {total_segments} segments")
        
        # Batch translate unique texts
        if texts_to_translate:
            unique_texts = list(texts_to_translate.keys())
            translated_count = 0
            
            # Process in batches
            for i in range(0, len(unique_texts), batch_size):
                batch = unique_texts[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(unique_texts) + batch_size - 1) // batch_size
                
                logger.info(f"Translating batch {batch_num}/{total_batches} ({len(batch)} texts)")
                
                # Use batch translation
                translations = self.batch_translate(batch, target_language, source_language)
                
                # Update translation map
                for original, translated in zip(batch, translations):
                    texts_to_translate[original] = translated
                    translated_count += 1
                    
                logger.info(f"Progress: {translated_count}/{unique_count} unique texts translated")
        
        # Apply translations to segments
        translated_segments = []
        translated_segment_count = 0
        preserved_count = 0
        
        for segment in segments:
            # Create a copy to avoid modifying original
            new_segment = SRTSegment(
                index=segment.index,
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=segment.text,
                detected_language=segment.detected_language
            )
            
            # Apply translation if available
            if segment.text in texts_to_translate and texts_to_translate[segment.text]:
                new_segment.text = texts_to_translate[segment.text]
                translated_segment_count += 1
            else:
                preserved_count += 1
                
            translated_segments.append(new_segment)
        
        # Calculate statistics
        duration = (datetime.now() - start_time).total_seconds()
        efficiency = (1 - (unique_count / total_segments)) * 100 if total_segments > 0 else 0
        
        logger.info(f"Translation complete:")
        logger.info(f"  - Total segments: {total_segments}")
        logger.info(f"  - Unique texts: {unique_count}")
        logger.info(f"  - Segments translated: {translated_segment_count}")
        logger.info(f"  - Segments preserved: {preserved_count}")
        logger.info(f"  - Deduplication efficiency: {efficiency:.1f}%")
        logger.info(f"  - Duration: {duration:.1f}s")
        if unique_count > 0:
            api_call_reduction = total_segments / unique_count
            logger.info(f"  - API call reduction: {api_call_reduction:.1f}x")
        
        # CRITICAL: Validate segment boundaries before returning
        if not self._validate_segment_boundaries(segments, translated_segments):
            logger.error("CRITICAL: Segment boundary validation failed! Translation aborted.")
            raise RuntimeError("Segment boundaries were violated during translation - this would break video synchronization")
        
        return translated_segments
    
    def save_translated_srt(self, segments: List[SRTSegment], output_path: str) -> bool:
        """
        Save translated segments to an SRT file.
        
        Args:
            segments: List of SRTSegment objects
            output_path: Path where to save the SRT file
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments):
                    # Write index
                    f.write(f"{segment.index}\n")
                    
                    # Write timing
                    f.write(f"{segment.start_time} --> {segment.end_time}\n")
                    
                    # Write text
                    f.write(f"{segment.text}\n")
                    
                    # Add blank line between segments (except last)
                    if i < len(segments) - 1:
                        f.write("\n")
            
            logger.info(f"Saved translated SRT to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save SRT file {output_path}: {e}")
            return False
    
    def estimate_cost(self, srt_path: str, target_language: str) -> Dict[str, float]:
        """
        Estimate translation cost for an SRT file.
        
        Args:
            srt_path: Path to SRT file
            target_language: Target language code
            
        Returns:
            Dictionary with cost analysis
        """
        segments = self.parse_srt(srt_path)
        
        # Count unique texts that need translation
        unique_texts = set()
        total_chars = 0
        segments_to_translate = 0
        
        for segment in segments:
            if self.should_translate_segment(segment, target_language):
                unique_texts.add(segment.text)
                total_chars += len(segment.text)
                segments_to_translate += 1
                
        # Estimate tokens (rough: 4 chars per token)
        total_tokens = total_chars / 4
        unique_tokens = sum(len(text) for text in unique_texts) / 4
        
        # Cost estimates (OpenAI GPT-4.1-mini pricing)
        cost_per_million = 0.15  # $0.15 per 1M input tokens for GPT-4.1-mini
        
        return {
            'total_segments': len(segments),
            'segments_to_translate': segments_to_translate,
            'unique_texts': len(unique_texts),
            'total_tokens': total_tokens,
            'unique_tokens': unique_tokens,
            'cost_without_optimization': (total_tokens / 1_000_000) * cost_per_million,
            'cost_with_optimization': (unique_tokens / 1_000_000) * cost_per_million,
            'savings_factor': total_tokens / unique_tokens if unique_tokens > 0 else 1
        }


def translate_srt_file(srt_path: str,
                       output_path: str,
                       target_language: str,
                       source_language: Optional[str] = None,
                       preserve_original_when_matching: bool = True,
                       batch_size: int = 100,
                       estimate_only: bool = False,
                       config: Optional[Dict] = None) -> bool:
    """
    Convenience function to translate an SRT file with batch optimization.
    
    Args:
        srt_path: Path to source SRT file
        output_path: Path where to save translated SRT
        target_language: Target language code ('en', 'de', 'he')
        source_language: Source language code (optional)
        preserve_original_when_matching: If True, preserve segments already in target language
        batch_size: Number of unique texts to translate per API call
        estimate_only: If True, only estimate cost without translating
        config: Translation configuration with API keys
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create translator instances
        translator = HistoricalTranslator(config)
        srt_translator = SRTTranslator(translator)
        
        # If only estimating cost
        if estimate_only:
            cost_info = srt_translator.estimate_cost(srt_path, target_language)
            logger.info(f"Cost estimation for {srt_path}:")
            logger.info(f"  - Total segments: {cost_info['total_segments']}")
            logger.info(f"  - Segments to translate: {cost_info['segments_to_translate']}")
            logger.info(f"  - Unique texts: {cost_info['unique_texts']}")
            logger.info(f"  - Cost without optimization: ${cost_info['cost_without_optimization']:.4f}")
            logger.info(f"  - Cost with optimization: ${cost_info['cost_with_optimization']:.4f}")
            logger.info(f"  - Savings factor: {cost_info['savings_factor']:.1f}x")
            return True
        
        # Translate the SRT with batch optimization
        translated_segments = srt_translator.translate_srt(
            srt_path,
            target_language,
            source_language,
            preserve_original_when_matching,
            batch_size
        )
        
        if not translated_segments:
            return False
        
        # Save the result
        return srt_translator.save_translated_srt(translated_segments, output_path)
        
    except Exception as e:
        logger.error(f"Failed to translate SRT file: {e}")
        return False
