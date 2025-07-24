#!/usr/bin/env python3
"""
Test segment boundary preservation with mocked translation.
"""

import sys
import os
sys.path.append('.')

from scribe.srt_translator import SRTTranslator
from scribe.translate import HistoricalTranslator
from unittest.mock import Mock, patch

def test_boundary_preservation_with_mock():
    """Test boundary preservation with mocked translation API."""
    
    print("🧪 Testing Segment Boundary Preservation with Mock Translation")
    
    # Create translator with mocked API
    translator = HistoricalTranslator()
    srt_translator = SRTTranslator(translator)
    
    # Parse test file
    input_file = "test_mixed_language.srt"
    segments = srt_translator.parse_srt(input_file)
    
    print(f"\n📊 Original file has {len(segments)} segments:")
    for seg in segments:
        detected = srt_translator.detect_segment_language(seg)
        should_translate = srt_translator.should_translate_segment(seg, 'de')
        print(f"  {seg.index}: {seg.start_time} --> {seg.end_time}")
        print(f"    Text: '{seg.text}'")
        print(f"    Language: {detected} → {'TRANSLATE' if should_translate else 'PRESERVE'}")
    
    # Mock the batch_translate method to return predictable translations
    def mock_batch_translate(texts, target_language, source_language=None):
        """Mock translation that preserves segment boundaries."""
        translations = []
        for text in texts:
            # Simple mock: add [TRANSLATED] prefix to English text
            if any(word in text.lower() for word in ['hello', 'what', 'how', 'are', 'you', 'today', 'name']):
                translations.append(f"[TRANSLATED] {text}")
            else:
                translations.append(text)  # Keep German as-is
        return translations
    
    # Patch the batch_translate method
    with patch.object(srt_translator, 'batch_translate', side_effect=mock_batch_translate):
        # Perform translation
        translated_segments = srt_translator.translate_srt(
            input_file,
            target_language='de',
            preserve_original_when_matching=True
        )
    
    print(f"\n📊 Translated file has {len(translated_segments)} segments:")
    for seg in translated_segments:
        print(f"  {seg.index}: {seg.start_time} --> {seg.end_time}")
        print(f"    Text: '{seg.text}'")
    
    # Validate boundaries
    print(f"\n🔍 Boundary Validation:")
    
    if len(segments) != len(translated_segments):
        print(f"❌ SEGMENT COUNT MISMATCH: {len(segments)} → {len(translated_segments)}")
        return False
    
    boundary_errors = 0
    for orig, trans in zip(segments, translated_segments):
        if orig.index != trans.index:
            print(f"❌ INDEX MISMATCH: Segment {orig.index} → {trans.index}")
            boundary_errors += 1
        elif orig.start_time != trans.start_time:
            print(f"❌ START TIME MISMATCH: Segment {orig.index}: {orig.start_time} → {trans.start_time}")
            boundary_errors += 1
        elif orig.end_time != trans.end_time:
            print(f"❌ END TIME MISMATCH: Segment {orig.index}: {orig.end_time} → {trans.end_time}")
            boundary_errors += 1
        else:
            print(f"✅ Segment {orig.index}: Boundaries preserved")
    
    if boundary_errors == 0:
        print(f"\n✅ All segment boundaries preserved correctly!")
        
        # Check translation logic
        print(f"\n🎯 Translation Logic Validation:")
        for orig, trans in zip(segments, translated_segments):
            if orig.text == trans.text:
                print(f"  ✅ Segment {orig.index}: Preserved (German)")
            else:
                print(f"  ✅ Segment {orig.index}: Translated (English → German)")
                print(f"    '{orig.text}' → '{trans.text}'")
        
        return True
    else:
        print(f"\n❌ Found {boundary_errors} boundary violations!")
        return False

if __name__ == "__main__":
    success = test_boundary_preservation_with_mock()
    print(f"\n{'🎉 Test passed!' if success else '💥 Test failed!'}")
