#!/usr/bin/env python3
"""
Run translation with conservative settings to ensure success.
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

def run_conservative_translation():
    """Run translation with conservative batch size."""
    
    # Test file path
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    srt_path = f"output/{interview_id}/{interview_id}.orig.srt"
    output_path = f"output/{interview_id}/{interview_id}.de.srt"
    
    print("🔧 Conservative Optimized Translation")
    print("=" * 45)
    print(f"Interview: {interview_id}")
    print(f"Using smaller batch size for reliability")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    # Initialize translator
    translator = HistoricalTranslator()
    srt_translator = SRTTranslator(translator)
    
    # Parse segments
    print("📊 Analyzing source...")
    segments = srt_translator.parse_srt(srt_path)
    print(f"  Total segments: {len(segments)}")
    
    # Test spacing normalization
    spacing_fixes = sum(1 for seg in segments 
                       if seg.text != srt_translator._normalize_spacing(seg.text))
    print(f"  Spacing fixes: {spacing_fixes} ({spacing_fixes/len(segments)*100:.1f}%)")
    print()
    
    # Run translation with conservative batch size
    print("🎯 Running translation with conservative settings...")
    print("  - Batch size: 100 (reduced for reliability)")
    print("  - Spacing normalization: enabled")
    print("  - GPT-4o-mini only: enabled")
    print()
    
    start_time = time.time()
    
    try:
        translated_segments = srt_translator.translate_srt(
            srt_path,
            target_language='de',
            preserve_original_when_matching=True,
            batch_size=100  # Conservative batch size
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Translation completed in {duration:.1f} seconds ({duration/60:.1f} minutes)")
        
        # Save result
        success = srt_translator.save_translated_srt(translated_segments, output_path)
        
        if success:
            print(f"✅ Saved to: {output_path}")
            
            # Quick verification
            german_detected = sum(1 for seg in translated_segments[:20] 
                                if seg.detected_language == 'de')
            print(f"  German detection in first 20: {german_detected}/20")
            
            # Check for Wehrmacht segments
            wehrmacht_count = sum(1 for seg in translated_segments 
                                if "Wehrmacht" in seg.text and seg.detected_language == 'de')
            total_wehrmacht = sum(1 for seg in translated_segments if "Wehrmacht" in seg.text)
            
            if total_wehrmacht > 0:
                print(f"  Wehrmacht segments correctly detected: {wehrmacht_count}/{total_wehrmacht}")
            
            # Performance summary
            improvement = ((600 - duration) / 600) * 100 if duration < 600 else 0
            print(f"\n📈 Performance Summary:")
            print(f"  Duration: {duration:.1f}s ({duration/60:.1f} min)")
            print(f"  Improvement vs original: ~{improvement:.0f}% faster")
            print(f"  Processing rate: {len(segments)/duration:.1f} segments/second")
            
            return True
        else:
            print("❌ Failed to save file")
            return False
            
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ Failed after {duration:.1f} seconds: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_conservative_translation()
    sys.exit(0 if success else 1)