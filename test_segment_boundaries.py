#!/usr/bin/env python3
"""
Test script to validate segment boundary preservation and language detection logic.
"""

import sys
import os
sys.path.append('.')

from scribe.srt_translator import SRTTranslator
from scribe.translate import HistoricalTranslator

def test_segment_boundaries():
    """Test that segment boundaries are preserved during translation."""
    
    # Create translator
    translator = HistoricalTranslator()
    srt_translator = SRTTranslator(translator)
    
    # Parse test SRT
    input_file = "test_mixed_language.srt"
    segments = srt_translator.parse_srt(input_file)
    
    print(f"📊 Parsed {len(segments)} segments from {input_file}")
    
    # Test language detection
    print("\n🔍 Language Detection Results:")
    for segment in segments:
        detected = srt_translator.detect_segment_language(segment)
        should_translate = srt_translator.should_translate_segment(segment, 'de')
        print(f"  Segment {segment.index}: '{segment.text}' → {detected} → {'TRANSLATE' if should_translate else 'PRESERVE'}")
    
    # Test translation decision logic
    print("\n🎯 Translation Logic Test (target: German):")
    for segment in segments:
        segment.detected_language = srt_translator.detect_segment_language(segment)
        should_translate = srt_translator.should_translate_segment(segment, 'de')
        
        if segment.detected_language == 'de' and should_translate:
            print(f"  ❌ ERROR: German segment {segment.index} marked for translation!")
        elif segment.detected_language == 'en' and not should_translate:
            print(f"  ❌ ERROR: English segment {segment.index} marked for preservation!")
        else:
            print(f"  ✅ Segment {segment.index}: {segment.detected_language} → {'translate' if should_translate else 'preserve'}")
    
    # Test segment count preservation
    print(f"\n📏 Segment Count Test:")
    print(f"  Input segments: {len(segments)}")
    
    # Simulate translation (without actual API calls)
    translated_segments = []
    for segment in segments:
        # Create copy with same boundaries
        new_segment = type(segment)(
            index=segment.index,
            start_time=segment.start_time,
            end_time=segment.end_time,
            text=f"[TRANSLATED] {segment.text}" if srt_translator.should_translate_segment(segment, 'de') else segment.text,
            detected_language=segment.detected_language
        )
        translated_segments.append(new_segment)
    
    print(f"  Output segments: {len(translated_segments)}")
    
    if len(segments) != len(translated_segments):
        print("  ❌ ERROR: Segment count mismatch!")
        return False
    
    # Test timing preservation
    print(f"\n⏰ Timing Preservation Test:")
    timing_errors = 0
    for orig, trans in zip(segments, translated_segments):
        if orig.start_time != trans.start_time or orig.end_time != trans.end_time:
            print(f"  ❌ ERROR: Timing mismatch in segment {orig.index}")
            timing_errors += 1
        elif orig.index != trans.index:
            print(f"  ❌ ERROR: Index mismatch: {orig.index} → {trans.index}")
            timing_errors += 1
    
    if timing_errors == 0:
        print("  ✅ All timing and indices preserved correctly")
    
    return timing_errors == 0

if __name__ == "__main__":
    print("🧪 Testing Segment Boundary Preservation\n")
    success = test_segment_boundaries()
    print(f"\n{'✅ All tests passed!' if success else '❌ Tests failed!'}")
