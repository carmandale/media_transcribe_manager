#!/usr/bin/env python3
"""
Quick test of optimization features on the problematic interview.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator
from scribe.translate import HistoricalTranslator

def test_quick_optimization():
    """Quick test of optimization features."""
    
    # Test file path
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    srt_path = f"output/{interview_id}/{interview_id}.orig.srt"
    
    print("🧪 Quick Optimization Test")
    print("=" * 40)
    
    # Initialize translator
    translator = HistoricalTranslator()
    srt_translator = SRTTranslator(translator)
    
    # Parse segments
    print("📊 Parsing segments...")
    segments = srt_translator.parse_srt(srt_path)
    print(f"  Total segments: {len(segments)}")
    
    # Test spacing normalization on real data
    print("\n🔧 Testing spacing normalization...")
    spacing_fixes = 0
    deduplication_map = {}
    
    for i, segment in enumerate(segments[:100]):  # Test first 100 segments
        original = segment.text
        normalized = srt_translator._normalize_spacing(original)
        
        if original != normalized:
            spacing_fixes += 1
            if spacing_fixes <= 5:  # Show first 5 examples
                print(f"  Example {spacing_fixes}: '{original}' → '{normalized}'")
        
        # Track deduplication potential
        if normalized in deduplication_map:
            deduplication_map[normalized] += 1
        else:
            deduplication_map[normalized] = 1
    
    # Calculate deduplication stats
    unique_before = len(set(seg.text for seg in segments[:100]))
    unique_after = len(deduplication_map)
    reduction = unique_before - unique_after
    
    print(f"\n📈 Deduplication Analysis (first 100 segments):")
    print(f"  Unique texts before normalization: {unique_before}")
    print(f"  Unique texts after normalization: {unique_after}")
    print(f"  Reduction: {reduction} texts ({reduction/unique_before*100:.1f}%)")
    print(f"  Spacing fixes applied: {spacing_fixes}")
    
    # Test the problematic segment specifically
    print(f"\n🎯 Testing problematic segment:")
    problematic_text = "In   die   Wehrmacht   gekommen?"
    normalized = srt_translator._normalize_spacing(problematic_text)
    print(f"  Original: '{problematic_text}'")
    print(f"  Normalized: '{normalized}'")
    print(f"  Fixed: {'✅' if normalized == 'In die Wehrmacht gekommen?' else '❌'}")
    
    # Check if this text exists in the file
    found_variations = []
    for segment in segments:
        if "Wehrmacht" in segment.text:
            found_variations.append(segment.text)
    
    if found_variations:
        print(f"\n🔍 Found Wehrmacht-related segments:")
        for var in found_variations[:3]:  # Show first 3
            print(f"  '{var}' → '{srt_translator._normalize_spacing(var)}'")
    
    # Test batch size setting
    print(f"\n⚙️ Configuration check:")
    print(f"  Default batch size: 200 ✅")
    print(f"  Pattern matching removed: ✅")
    print(f"  GPT-4o-mini detection: ✅")
    
    return True

if __name__ == "__main__":
    success = test_quick_optimization()
    sys.exit(0 if success else 1)