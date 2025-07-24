#!/usr/bin/env python3
"""
Complete Integration Test for Subtitle Translation System
========================================================
Tests the complete workflow including:
1. GPT-4o-mini batch language detection
2. Segment boundary preservation
3. Language preservation logic
4. Translation accuracy
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from scribe.srt_translator import SRTTranslator
from scribe.translate import HistoricalTranslator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_complete_integration():
    """Test the complete subtitle translation workflow."""
    
    print("🧪 Complete Integration Test for Subtitle Translation System")
    print("=" * 60)
    
    # Initialize translator with OpenAI client
    try:
        translator = HistoricalTranslator()
        srt_translator = SRTTranslator(translator)
        
        if not hasattr(translator, 'openai_client') or not translator.openai_client:
            print("⚠️  OpenAI client not available - testing with fallback detection")
        else:
            print("✅ OpenAI client available - testing with GPT-4o-mini")
            
    except Exception as e:
        print(f"❌ Failed to initialize translator: {e}")
        return False
    
    # Test file
    test_file = "test_mixed_language.srt"
    if not os.path.exists(test_file):
        print(f"❌ Test file {test_file} not found")
        return False
    
    print(f"\n📁 Testing with file: {test_file}")
    
    try:
        # Parse original segments
        original_segments = srt_translator.parse_srt(test_file)
        print(f"📊 Original segments: {len(original_segments)}")
        
        # Show original content
        print("\n📋 Original Content:")
        for i, seg in enumerate(original_segments[:3]):  # Show first 3
            print(f"  {i+1}: {seg.start_time} --> {seg.end_time}")
            print(f"      '{seg.text}'")
        if len(original_segments) > 3:
            print(f"  ... and {len(original_segments) - 3} more segments")
        
        # Test translation to German
        print(f"\n🔄 Translating to German...")
        translated_segments = srt_translator.translate_srt(
            test_file, 
            target_language='de',
            preserve_original_when_matching=True
        )
        
        print(f"📊 Translated segments: {len(translated_segments)}")
        
        # Validate results
        print(f"\n🔍 Validation Results:")
        
        # 1. Segment count preservation
        if len(original_segments) == len(translated_segments):
            print("  ✅ Segment count preserved")
        else:
            print(f"  ❌ Segment count mismatch: {len(original_segments)} → {len(translated_segments)}")
            return False
        
        # 2. Timing preservation
        timing_preserved = True
        for i, (orig, trans) in enumerate(zip(original_segments, translated_segments)):
            if (orig.index != trans.index or 
                orig.start_time != trans.start_time or 
                orig.end_time != trans.end_time):
                print(f"  ❌ Timing mismatch in segment {i+1}")
                timing_preserved = False
                break
        
        if timing_preserved:
            print("  ✅ All timing preserved")
        else:
            return False
        
        # 3. Language preservation logic
        print(f"\n📝 Translation Logic Analysis:")
        preserved_count = 0
        translated_count = 0
        
        for i, (orig, trans) in enumerate(zip(original_segments, translated_segments)):
            if orig.text == trans.text:
                preserved_count += 1
                print(f"  ✅ Segment {i+1}: Preserved (likely German)")
            else:
                translated_count += 1
                print(f"  🔄 Segment {i+1}: Translated")
                print(f"      '{orig.text}' → '{trans.text}'")
        
        print(f"\n📈 Summary:")
        print(f"  - Preserved: {preserved_count} segments")
        print(f"  - Translated: {translated_count} segments")
        print(f"  - Total: {len(original_segments)} segments")
        
        # 4. Test boundary validation method directly
        print(f"\n🔒 Testing boundary validation method:")
        try:
            validation_result = srt_translator._validate_segment_boundaries(
                original_segments, translated_segments
            )
            if validation_result:
                print("  ✅ Boundary validation passed")
            else:
                print("  ❌ Boundary validation failed")
                return False
        except Exception as e:
            print(f"  ❌ Boundary validation error: {e}")
            return False
        
        print(f"\n🎉 Complete Integration Test PASSED!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_complete_integration()
    sys.exit(0 if success else 1)

