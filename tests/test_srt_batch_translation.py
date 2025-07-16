#!/usr/bin/env python3
"""
Test the optimized SRT translation system with real files.
Translates 5 files to English and 5 files to German.
"""

import os
from pathlib import Path
from datetime import datetime
from scribe.srt_translator import SRTTranslator, translate_srt_file

def test_srt_translations():
    """Test SRT translations with real files."""
    
    # Files to translate to English (German originals)
    files_for_english = [
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/6f35bef7-fce6-485e-84c8-79115e793548/6f35bef7-fce6-485e-84c8-79115e793548.orig.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/225f0880-e414-43cd-b3a5-2bd6e5642f07/225f0880-e414-43cd-b3a5-2bd6e5642f07.orig.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/25af0f9c-8f96-44c9-be5e-e92cb462a41f/25af0f9c-8f96-44c9-be5e-e92cb462a41f.orig.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/4a28be33-bdd8-4803-b47e-2e069239d343/4a28be33-bdd8-4803-b47e-2e069239d343.orig.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/9dce7175-f755-4ef4-a5f0-7fbe3410d042/9dce7175-f755-4ef4-a5f0-7fbe3410d042.orig.srt"
    ]
    
    # Files to translate to German (English translations)
    files_for_german = [
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/23b9f306-af84-4d1f-a0fa-71869f61eb28/23b9f306-af84-4d1f-a0fa-71869f61eb28.en.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/33b006bd-80aa-4616-9f40-9d7225415863/33b006bd-80aa-4616-9f40-9d7225415863.en.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/1ac7fba3-bcdf-43a2-a995-f727eba38d4a/1ac7fba3-bcdf-43a2-a995-f727eba38d4a.en.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/930f7d18-4c0a-4cc5-af22-7ebc54077a65/930f7d18-4c0a-4cc5-af22-7ebc54077a65.en.srt",
        "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe/output/339fb0cb-3830-4374-8ad6-2626a26eb0b8/339fb0cb-3830-4374-8ad6-2626a26eb0b8.en.srt"
    ]
    
    print("SRT Translation System Test")
    print("=" * 60)
    print(f"Testing optimized batch translation with deduplication")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create results directory
    results_dir = Path("srt_translation_test_results")
    results_dir.mkdir(exist_ok=True)
    
    # Initialize translator
    translator = SRTTranslator()
    
    # Test 1: Translate to English
    print("TEST 1: Translating 5 German files to English")
    print("-" * 60)
    
    english_results = []
    for i, srt_file in enumerate(files_for_english, 1):
        if not os.path.exists(srt_file):
            print(f"{i}. File not found: {srt_file}")
            continue
            
        print(f"\n{i}. Processing: {Path(srt_file).name}")
        
        # First show cost estimation
        cost_info = translator.estimate_cost(srt_file, 'en')
        print(f"   Total segments: {cost_info['total_segments']}")
        print(f"   Segments to translate: {cost_info['segments_to_translate']}")
        print(f"   Unique texts: {cost_info['unique_texts']}")
        print(f"   Estimated cost: ${cost_info['cost_with_optimization']:.4f}")
        print(f"   Savings vs traditional: {cost_info['savings_factor']:.1f}x")
        
        # Generate output filename
        file_id = Path(srt_file).parent.name
        output_file = results_dir / f"{file_id}_test_en.srt"
        
        # Translate
        print(f"   Translating to English...")
        start_time = datetime.now()
        
        success = translate_srt_file(
            srt_file,
            str(output_file),
            target_language='en',
            preserve_original_when_matching=True
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if success:
            print(f"   ✓ Success! Translation took {duration:.1f}s")
            print(f"   Output: {output_file}")
            english_results.append((file_id, duration))
        else:
            print(f"   ✗ Failed to translate")
    
    # Test 2: Translate to German
    print("\n\nTEST 2: Translating 5 English files to German")
    print("-" * 60)
    
    german_results = []
    for i, srt_file in enumerate(files_for_german, 1):
        if not os.path.exists(srt_file):
            print(f"{i}. File not found: {srt_file}")
            continue
            
        print(f"\n{i}. Processing: {Path(srt_file).name}")
        
        # First show cost estimation
        cost_info = translator.estimate_cost(srt_file, 'de')
        print(f"   Total segments: {cost_info['total_segments']}")
        print(f"   Segments to translate: {cost_info['segments_to_translate']}")
        print(f"   Unique texts: {cost_info['unique_texts']}")
        print(f"   Estimated cost: ${cost_info['cost_with_optimization']:.4f}")
        print(f"   Savings vs traditional: {cost_info['savings_factor']:.1f}x")
        
        # Generate output filename
        file_id = Path(srt_file).parent.name
        output_file = results_dir / f"{file_id}_test_de.srt"
        
        # Translate
        print(f"   Translating to German...")
        start_time = datetime.now()
        
        success = translate_srt_file(
            srt_file,
            str(output_file),
            target_language='de',
            preserve_original_when_matching=True
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if success:
            print(f"   ✓ Success! Translation took {duration:.1f}s")
            print(f"   Output: {output_file}")
            german_results.append((file_id, duration))
        else:
            print(f"   ✗ Failed to translate")
    
    # Summary
    print("\n\nSUMMARY")
    print("=" * 60)
    print(f"English translations: {len(english_results)}/5 successful")
    if english_results:
        avg_time = sum(r[1] for r in english_results) / len(english_results)
        print(f"Average time per file: {avg_time:.1f}s")
    
    print(f"\nGerman translations: {len(german_results)}/5 successful")
    if german_results:
        avg_time = sum(r[1] for r in german_results) / len(german_results)
        print(f"Average time per file: {avg_time:.1f}s")
    
    print(f"\nResults saved to: {results_dir}/")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    test_srt_translations()