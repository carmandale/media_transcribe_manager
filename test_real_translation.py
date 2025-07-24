#!/usr/bin/env python3
"""
Test real translation to check for segment boundary violations.
"""

import sys
import os
sys.path.append('.')

from scribe.srt_translator import translate_srt_file

def test_real_translation():
    """Test actual translation with API calls to check for boundary violations."""
    
    input_file = "test_mixed_language.srt"
    output_file = "test_mixed_language_translated.srt"
    
    print("🧪 Testing Real Translation with Boundary Validation")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    
    # Parse original file to get baseline
    from scribe.srt_translator import SRTTranslator
    srt_translator = SRTTranslator()
    original_segments = srt_translator.parse_srt(input_file)
    
    print(f"\n📊 Original file has {len(original_segments)} segments:")
    for seg in original_segments:
        print(f"  {seg.index}: {seg.start_time} --> {seg.end_time} | '{seg.text}'")
    
    # Translate using OpenAI (to avoid DeepL issues)
    print(f"\n🔄 Translating to German using OpenAI...")
    config = {'openai_model': 'gpt-4o-mini'}
    
    success = translate_srt_file(
        input_file,
        output_file, 
        target_language='de',
        preserve_original_when_matching=True,
        config=config
    )
    
    if not success:
        print("❌ Translation failed!")
        return False
    
    # Parse translated file
    translated_segments = srt_translator.parse_srt(output_file)
    
    print(f"\n📊 Translated file has {len(translated_segments)} segments:")
    for seg in translated_segments:
        print(f"  {seg.index}: {seg.start_time} --> {seg.end_time} | '{seg.text}'")
    
    # Validate boundaries
    print(f"\n🔍 Boundary Validation:")
    
    if len(original_segments) != len(translated_segments):
        print(f"❌ SEGMENT COUNT MISMATCH: {len(original_segments)} → {len(translated_segments)}")
        return False
    
    boundary_errors = 0
    for orig, trans in zip(original_segments, translated_segments):
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
        for orig, trans in zip(original_segments, translated_segments):
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
    success = test_real_translation()
    print(f"\n{'🎉 Test passed!' if success else '💥 Test failed!'}")
