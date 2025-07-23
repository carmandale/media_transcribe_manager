#!/usr/bin/env python3
"""
Batch language detection for efficient processing.
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def detect_languages_batch(texts: List[str], openai_client) -> List[Optional[str]]:
    """
    Detect languages for multiple texts in a single API call.
    
    Args:
        texts: List of texts to detect
        openai_client: OpenAI client instance
        
    Returns:
        List of language codes ('en', 'de', 'he', or None) in same order as input
    """
    if not texts or not openai_client:
        return [None] * len(texts)
    
    # Create a numbered list for the prompt
    numbered_texts = []
    for i, text in enumerate(texts, 1):
        # Truncate very long texts for efficiency
        display_text = text[:100] + "..." if len(text) > 100 else text
        numbered_texts.append(f"{i}. {display_text}")
    
    prompt = """For each numbered text below, identify the language. Reply with a list in the exact format:
1: English
2: German
3: English
etc.

Only use: English, German, or Hebrew

Texts:
""" + "\n".join(numbered_texts)
    
    try:
        response = openai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=len(texts) * 20  # Enough for responses
        )
        
        # Parse the response
        result_text = response.choices[0].message.content.strip()
        results = [None] * len(texts)
        
        # Parse lines like "1: English"
        for line in result_text.split('\n'):
            line = line.strip()
            if ':' in line:
                try:
                    num_part, lang_part = line.split(':', 1)
                    num = int(num_part.strip())
                    lang = lang_part.strip().lower()
                    
                    # Map to our codes
                    lang_map = {'english': 'en', 'german': 'de', 'hebrew': 'he'}
                    if 1 <= num <= len(texts):
                        results[num - 1] = lang_map.get(lang)
                except:
                    continue
        
        return results
        
    except Exception as e:
        logger.error(f"Batch language detection failed: {e}")
        return [None] * len(texts)


def detect_languages_for_segments(segments, openai_client, batch_size=50):
    """
    Detect languages for all segments efficiently using batching.
    
    Args:
        segments: List of SRTSegment objects
        openai_client: OpenAI client instance
        batch_size: Number of segments to process per API call
        
    Returns:
        Dict mapping segment index to detected language
    """
    results = {}
    
    # Process in batches
    for i in range(0, len(segments), batch_size):
        batch_segments = segments[i:i + batch_size]
        batch_texts = [seg.text for seg in batch_segments]
        
        # Detect languages for this batch
        batch_results = detect_languages_batch(batch_texts, openai_client)
        
        # Store results
        for j, lang in enumerate(batch_results):
            segment_idx = i + j
            if lang:
                results[segment_idx] = lang
                segments[segment_idx].detected_language = lang
        
        logger.info(f"Detected languages for segments {i+1}-{min(i+batch_size, len(segments))}")
    
    return results