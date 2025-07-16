#!/usr/bin/env python3
"""
Simple test of SRT translation - one file at a time with detailed logging.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import logging

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from scribe.srt_translator import SRTTranslator

def test_single_file(srt_path, target_lang, output_dir):
    """Test translation of a single SRT file."""
    translator = SRTTranslator()
    
    print(f"\nProcessing: {Path(srt_path).name}")
    print("-" * 40)
    
    # Parse and analyze
    segments = translator.parse_srt(srt_path)
    print(f"Total segments: {len(segments)}")
    
    # Language detection sample
    print("\nFirst 5 segments:")
    for i, seg in enumerate(segments[:5]):
        lang = translator.detect_segment_language(seg)
        print(f"  {i+1}. '{seg.text[:50]}...' → Lang: {lang}")
    
    # Cost estimation
    cost_info = translator.estimate_cost(srt_path, target_lang)
    print(f"\nCost estimation for {target_lang.upper()}:")
    print(f"  Segments to translate: {cost_info['segments_to_translate']}")
    print(f"  Unique texts: {cost_info['unique_texts']}")
    print(f"  Cost: ${cost_info['cost_with_optimization']:.4f}")
    
    # Translate
    file_id = Path(srt_path).parent.name
    output_file = output_dir / f"{file_id}_test_{target_lang}.srt"
    
    print(f"\nTranslating to {target_lang.upper()}...")
    start_time = datetime.now()
    
    try:
        # Use the translate_srt method directly for more control
        translated_segments = translator.translate_srt(
            srt_path,
            target_lang,
            preserve_original_when_matching=True,
            batch_size=50  # Smaller batches to avoid issues
        )
        
        if translated_segments:
            # Save the results
            success = translator.save_translated_srt(translated_segments, str(output_file))
            duration = (datetime.now() - start_time).total_seconds()
            
            if success:
                print(f"✓ Success! Translation took {duration:.1f}s")
                print(f"  Output: {output_file}")
                
                # Show sample of translated content
                print("\nSample translations:")
                for i, seg in enumerate(translated_segments[:3]):
                    orig = segments[i].text if i < len(segments) else ""
                    print(f"  Original: '{orig[:50]}...'")
                    print(f"  Translated: '{seg.text[:50]}...'")
                    print()
                
                return True
            else:
                print("✗ Failed to save translated SRT")
                return False
        else:
            print("✗ No translated segments returned")
            return False
            
    except Exception as e:
        print(f"✗ Translation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Test SRT translation with a few files."""
    
    # Create output directory
    output_dir = Path("srt_translation_test_results")
    output_dir.mkdir(exist_ok=True)
    
    print("SRT Translation Test - Simple Version")
    print("=" * 60)
    
    # Test 1: One German file to English
    test_files_en = [
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/6f35bef7-fce6-485e-84c8-79115e793548/6f35bef7-fce6-485e-84c8-79115e793548.orig.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/225f0880-e414-43cd-b3a5-2bd6e5642f07/225f0880-e414-43cd-b3a5-2bd6e5642f07.orig.srt"
    ]
    
    # Test 2: One English file to German  
    test_files_de = [
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/23b9f306-af84-4d1f-a0fa-71869f61eb28/23b9f306-af84-4d1f-a0fa-71869f61eb28.en.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/33b006bd-80aa-4616-9f40-9d7225415863/33b006bd-80aa-4616-9f40-9d7225415863.en.srt"
    ]
    
    # Test English translations
    print("\nTEST: German → English Translation")
    print("=" * 60)
    
    for srt_file in test_files_en:
        if os.path.exists(srt_file):
            test_single_file(srt_file, 'en', output_dir)
        else:
            print(f"File not found: {srt_file}")
    
    # Test German translations
    print("\n\nTEST: English → German Translation")
    print("=" * 60)
    
    for srt_file in test_files_de:
        if os.path.exists(srt_file):
            test_single_file(srt_file, 'de', output_dir)
        else:
            print(f"File not found: {srt_file}")
    
    print(f"\n\nResults saved to: {output_dir}/")

if __name__ == "__main__":
    main()