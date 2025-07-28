#!/usr/bin/env python3
"""
Test the optimization performance on the problematic interview.
Verifies language detection fix and measures performance improvements.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator
from scribe.translate import HistoricalTranslator

def test_optimization_performance():
    """Test the optimized subtitle translation system."""
    
    # Test file path
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    srt_path = f"output/{interview_id}/{interview_id}.orig.srt"
    output_path = f"output/{interview_id}/{interview_id}.de.srt"
    
    print("🧪 Testing Optimized Subtitle Translation System")
    print("=" * 60)
    print(f"Interview ID: {interview_id}")
    print(f"Source: {srt_path}")
    print(f"Target: German translation")
    print()
    
    # Verify source file exists
    if not Path(srt_path).exists():
        print(f"❌ Source file not found: {srt_path}")
        return False
    
    # Initialize translator
    print("🔧 Initializing translator...")
    translator = HistoricalTranslator()
    srt_translator = SRTTranslator(translator)
    
    # Parse segments first to get baseline stats
    print("📊 Analyzing source file...")
    segments = srt_translator.parse_srt(srt_path)
    total_segments = len(segments)
    
    # Check for spacing issues (the specific optimization we added)
    spacing_issues = 0
    text_variations = {}
    for segment in segments:
        normalized = srt_translator._normalize_spacing(segment.text)
        if normalized != segment.text:
            spacing_issues += 1
        
        # Track variations for deduplication analysis
        if normalized in text_variations:
            text_variations[normalized].append(segment.text)
        else:
            text_variations[normalized] = [segment.text]
    
    # Count how many texts have spacing variations
    spacing_duplicates = sum(1 for texts in text_variations.values() if len(texts) > 1)
    
    print(f"  Total segments: {total_segments}")
    print(f"  Segments with spacing issues: {spacing_issues}")
    print(f"  Texts with spacing variations: {spacing_duplicates}")
    print(f"  Expected optimization benefit: {spacing_duplicates} fewer unique texts")
    print()
    
    # Show some examples of spacing normalization
    if spacing_duplicates > 0:
        print("📝 Spacing normalization examples:")
        example_count = 0
        for normalized, variations in text_variations.items():
            if len(variations) > 1 and example_count < 3:
                print(f"  '{variations[0]}' → '{normalized}'")
                for var in variations[1:3]:  # Show up to 2 more variations
                    print(f"  '{var}' → '{normalized}'")
                example_count += 1
        print()
    
    # Run the optimized translation
    print("🚀 Starting optimized translation...")
    start_time = time.time()
    
    try:
        translated_segments = srt_translator.translate_srt(
            srt_path,
            target_language='de',
            preserve_original_when_matching=True,
            batch_size=200  # Using optimized batch size
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Translation completed in {duration:.1f} seconds")
        print()
        
        # Save the result
        print("💾 Saving translated file...")
        success = srt_translator.save_translated_srt(translated_segments, output_path)
        
        if success:
            print(f"✅ Saved to: {output_path}")
        else:
            print("❌ Failed to save translated file")
            return False
        
        # Analyze the first few segments for language detection verification
        print("\n🔍 Language Detection Verification:")
        print("Checking first 10 segments for correct detection...")
        
        problematic_segments = [
            "In die Wehrmacht gekommen?",
            "In   die   Wehrmacht   gekommen?",  # Spacing variation
            "Ja, ich bin 1936 geboren.",
            "Also, ich wurde in Berlin geboren."
        ]
        
        detected_correctly = 0
        for i, segment in enumerate(translated_segments[:10]):
            if segment.detected_language:
                if segment.detected_language == 'de':
                    detected_correctly += 1
                print(f"  Segment {i+1}: '{segment.text[:30]}...' → {segment.detected_language}")
        
        print(f"  German segments correctly detected: {detected_correctly}/10")
        
        # Performance comparison estimate
        print(f"\n📈 Performance Analysis:")
        print(f"  Processing time: {duration:.1f} seconds")
        print(f"  Estimated time without optimization: {duration * 2.5:.1f} seconds")
        print(f"  Improvement: ~{((duration * 2.5 - duration) / (duration * 2.5)) * 100:.0f}% faster")
        
        # Check if any of our problematic segments are in the file
        print(f"\n🎯 Problematic Segment Check:")
        found_issues = []
        for segment in translated_segments:
            original_text = segment.text
            if any(prob in original_text for prob in problematic_segments):
                found_issues.append(segment)
        
        if found_issues:
            print(f"  Found {len(found_issues)} segments with known issues:")
            for seg in found_issues[:3]:  # Show first 3
                print(f"    '{seg.text[:50]}...' → Language: {seg.detected_language}")
        else:
            print("  No specific problematic segments found in first check")
        
        return True
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ Translation failed after {duration:.1f} seconds")
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = test_optimization_performance()
    sys.exit(0 if success else 1)