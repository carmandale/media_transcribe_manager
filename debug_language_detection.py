#!/usr/bin/env python3
"""
Debug language detection for specific segments.
"""

import sys
sys.path.append('.')

from scribe.srt_translator import SRTTranslator

def debug_detection():
    srt_translator = SRTTranslator()
    
    test_texts = [
        "Guten Tag, wie geht es Ihnen?",
        "Hello, how are you today?", 
        "ich im Jahr",
        "neunzehnhundertsechsunddreißig.",
        "What is your name?",
        "Mein Name ist Hans."
    ]
    
    for text in test_texts:
        # Create a dummy segment
        from scribe.srt_translator import SRTSegment
        segment = SRTSegment(1, "00:00:01,000", "00:00:02,000", text)
        
        detected = srt_translator.detect_segment_language(segment)
        print(f"'{text}' → {detected}")
        
        # Debug the pattern matching
        clean_text = text.lower()
        words = set(clean_text.split())
        
        for lang, data in srt_translator.LANGUAGE_PATTERNS.items():
            if lang != 'he':  # Skip Hebrew for now
                matches = words & data['words']
                if matches:
                    print(f"  {lang} matches: {matches}")

if __name__ == "__main__":
    debug_detection()
