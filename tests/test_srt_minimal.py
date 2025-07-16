#!/usr/bin/env python3
"""
Minimal SRT translation test - translate just a few segments.
"""

import tempfile
from pathlib import Path
from scribe.srt_translator import SRTTranslator

# Create a simple test SRT
test_srt = """1
00:00:00,000 --> 00:00:03,000
Guten Tag, wie geht es Ihnen?

2
00:00:03,500 --> 00:00:06,000
Mir geht es gut, danke.

3
00:00:06,500 --> 00:00:09,000
Hello, how are you today?

4
00:00:09,500 --> 00:00:12,000
Ich bin sehr glücklich.

5
00:00:12,500 --> 00:00:15,000
Thank you for coming.
"""

def test_minimal():
    """Test with a minimal SRT file."""
    print("Minimal SRT Translation Test")
    print("=" * 40)
    
    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
        f.write(test_srt)
        test_file = f.name
    
    try:
        translator = SRTTranslator()
        
        # Parse
        segments = translator.parse_srt(test_file)
        print(f"Parsed {len(segments)} segments")
        
        # Detect languages
        print("\nLanguage detection:")
        for seg in segments:
            lang = translator.detect_segment_language(seg)
            print(f"  Segment {seg.index}: '{seg.text}' → {lang}")
        
        # Cost estimation
        cost_info = translator.estimate_cost(test_file, 'en')
        print(f"\nCost for English translation:")
        print(f"  Segments to translate: {cost_info['segments_to_translate']}")
        print(f"  Unique texts: {cost_info['unique_texts']}")
        
        # Create output directory
        output_dir = Path("srt_test_minimal")
        output_dir.mkdir(exist_ok=True)
        
        # Test individual translation first
        print("\nTesting individual segment translation:")
        for seg in segments[:2]:
            if translator.should_translate_segment(seg, 'en'):
                print(f"  Translating: '{seg.text}'")
                # Use the translator's translate method directly
                result = translator.translator.translate(seg.text, 'en', provider='deepl')
                print(f"  Result: '{result}'")
        
        print("\nTranslating full file to English...")
        output_file = output_dir / "test_en.srt"
        
        # Use translate_srt with very small batch size
        translated_segments = translator.translate_srt(
            test_file,
            'en',
            preserve_original_when_matching=True,
            batch_size=2  # Very small batches
        )
        
        if translated_segments:
            translator.save_translated_srt(translated_segments, str(output_file))
            print(f"✓ Saved to: {output_file}")
            
            # Show results
            print("\nTranslation results:")
            for i, (orig, trans) in enumerate(zip(segments, translated_segments)):
                print(f"  {i+1}. Original: '{orig.text}'")
                print(f"      Translated: '{trans.text}'")
        else:
            print("✗ No translations returned")
            
    finally:
        import os
        os.unlink(test_file)

if __name__ == "__main__":
    test_minimal()