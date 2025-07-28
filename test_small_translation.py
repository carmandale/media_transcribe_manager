#!/usr/bin/env python3
"""
Test translation on a small subset to verify optimizations and language detection.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator, SRTSegment
from scribe.translate import HistoricalTranslator

def test_small_translation():
    """Test translation on first 50 segments."""
    
    # Test file path
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    srt_path = f"output/{interview_id}/{interview_id}.orig.srt"
    
    print("🧪 Small Translation Test (First 50 Segments)")
    print("=" * 50)
    
    # Initialize translator
    translator = HistoricalTranslator()
    srt_translator = SRTTranslator(translator)
    
    # Parse all segments and take first 50
    print("📊 Parsing segments...")
    all_segments = srt_translator.parse_srt(srt_path)
    test_segments = all_segments[:50]
    
    print(f"  Testing {len(test_segments)} segments out of {len(all_segments)} total")
    
    # Create a temporary SRT file with just these segments
    temp_srt_path = f"output/{interview_id}/temp_test_50.srt"
    with open(temp_srt_path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(test_segments):
            f.write(f"{segment.index}\n")
            f.write(f"{segment.start_time} --> {segment.end_time}\n")
            f.write(f"{segment.text}\n")
            if i < len(test_segments) - 1:
                f.write("\n")
    
    print(f"  Created temp file: {temp_srt_path}")
    
    # Run translation with timing
    print("\n🚀 Running optimized translation...")
    start_time = time.time()
    
    try:
        translated_segments = srt_translator.translate_srt(
            temp_srt_path,
            target_language='de',
            preserve_original_when_matching=True,
            batch_size=50  # Perfect for our test size
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Translation completed in {duration:.1f} seconds")
        
        # Analyze results
        print(f"\n🔍 Language Detection Results:")
        german_detected = 0
        english_detected = 0
        unknown_detected = 0
        
        for segment in translated_segments[:10]:  # Show first 10
            lang = segment.detected_language
            if lang == 'de':
                german_detected += 1
            elif lang == 'en':
                english_detected += 1
            else:
                unknown_detected += 1
            
            print(f"  '{segment.text[:40]}...' → {lang}")
        
        print(f"\n📊 Detection Summary (first 10):")
        print(f"  German: {german_detected}")
        print(f"  English: {english_detected}")
        print(f"  Unknown/None: {unknown_detected}")
        
        # Check for the problematic segment specifically
        print(f"\n🎯 Checking for problematic patterns:")
        found_wehrmacht = False
        for segment in translated_segments:
            if "Wehrmacht" in segment.text:
                print(f"  Wehrmacht segment: '{segment.text[:50]}...'")
                print(f"    Language detected: {segment.detected_language}")
                print(f"    Correct detection: {'✅' if segment.detected_language == 'de' else '❌'}")
                found_wehrmacht = True
                break
        
        if not found_wehrmacht:
            print("  No Wehrmacht segments in first 50 segments")
        
        # Performance extrapolation
        print(f"\n📈 Performance Analysis:")
        print(f"  50 segments took: {duration:.1f} seconds")
        estimated_full = (duration / 50) * 1835
        print(f"  Estimated for full file (1835 segments): {estimated_full:.1f} seconds ({estimated_full/60:.1f} minutes)")
        print(f"  Previous time was ~10+ minutes")
        print(f"  Estimated improvement: {((600 - estimated_full) / 600) * 100:.0f}% faster")
        
        # Clean up temp file
        Path(temp_srt_path).unlink()
        print(f"\n🧹 Cleaned up temp file")
        
        return True
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ Translation failed after {duration:.1f} seconds")
        print(f"Error: {e}")
        # Clean up temp file
        if Path(temp_srt_path).exists():
            Path(temp_srt_path).unlink()
        return False

if __name__ == "__main__":
    success = test_small_translation()
    sys.exit(0 if success else 1)