#!/usr/bin/env python3
"""
Test script to generate 5 English and 5 German subtitle files using the new optimized SRT translation system.
This demonstrates the batch translation, deduplication, and language preservation features.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path to import scribe modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scribe.srt_translator import SRTTranslator

def generate_subtitles():
    """Generate 5 English and 5 German subtitle files using the new system."""
    
    # Create output directory
    output_dir = Path(__file__).parent / "srt_test_output"
    output_dir.mkdir(exist_ok=True)
    
    # Files for English translation (German originals)
    files_for_english = [
        {
            "id": "eae1965d-761b-4553-bca2-167290792a96",
            "name": "Interview 1 (German original)"
        },
        {
            "id": "367a7254-133c-45f4-ba45-8805980a7b5f", 
            "name": "Interview 2 (German original)"
        },
        {
            "id": "3e4125f1-e600-465d-b782-8e53e6699129",
            "name": "Interview 3 (German original)"
        },
        {
            "id": "f5972be6-6904-4977-bce1-df848acfd9ae",
            "name": "Interview 4 (German original)"
        },
        {
            "id": "81a9e7d8-d8c8-4c21-b4b5-1dd05fdb25f0",
            "name": "Interview 5 (German original)"
        }
    ]
    
    # Files for German translation (English translations)
    files_for_german = [
        {
            "id": "4499e44a-7a67-4af8-b66f-c50a6a4570ba",
            "name": "Interview 1 (English version)"
        },
        {
            "id": "ccfbd8b4-08f8-4773-9ecc-99b28c11726e",
            "name": "Interview 2 (English version)"
        },
        {
            "id": "b379c4a6-c0f9-4135-b2cc-48d7f766a785",
            "name": "Interview 3 (English version)"
        },
        {
            "id": "5e582813-388e-483d-882b-fb04e380dea4",
            "name": "Interview 4 (English version)"
        },
        {
            "id": "828cebcb-da6c-4c78-9a15-9b3cf8148877",
            "name": "Interview 5 (English version)"
        }
    ]
    
    # Initialize translator
    translator = SRTTranslator()
    
    # Results for comparison report
    results = {
        "test_date": datetime.now().isoformat(),
        "english_translations": [],
        "german_translations": []
    }
    
    print("SRT Translation Test - Optimized Batch System")
    print("=" * 60)
    print(f"Output directory: {output_dir}")
    print()
    
    # Process English translations
    print("PART 1: Translating German originals to English")
    print("-" * 60)
    
    for i, file_info in enumerate(files_for_english, 1):
        file_id = file_info["id"]
        base_path = Path(__file__).parent.parent / "output" / file_id
        orig_srt = base_path / f"{file_id}.orig.srt"
        
        if not orig_srt.exists():
            print(f"{i}. File not found: {orig_srt}")
            continue
            
        print(f"\n{i}. Processing {file_info['name']} ({file_id})")
        
        try:
            # Cost estimation
            cost_info = translator.estimate_cost(str(orig_srt), 'en')
            print(f"   Total segments: {cost_info['total_segments']}")
            print(f"   Segments to translate: {cost_info['segments_to_translate']}")
            print(f"   Unique texts: {cost_info['unique_texts']}")
            print(f"   Deduplication rate: {(1 - cost_info['unique_texts']/cost_info['total_segments'])*100:.1f}%")
            print(f"   Cost savings: {cost_info['savings_factor']:.1f}x")
            
            # Translate
            print(f"   Translating to English...")
            start_time = datetime.now()
            
            translated_segments = translator.translate_srt(
                str(orig_srt),
                'en',
                preserve_original_when_matching=True,
                batch_size=50
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Save result
            output_file = output_dir / f"{file_id}_new_en.srt"
            success = translator.save_translated_srt(translated_segments, str(output_file))
            
            if success:
                print(f"   ✓ Success! Translation took {duration:.1f}s")
                print(f"   Output: {output_file.name}")
                
                # Add to results
                results["english_translations"].append({
                    "file_id": file_id,
                    "name": file_info["name"],
                    "total_segments": cost_info['total_segments'],
                    "segments_translated": cost_info['segments_to_translate'],
                    "unique_texts": cost_info['unique_texts'],
                    "deduplication_rate": (1 - cost_info['unique_texts']/cost_info['total_segments'])*100,
                    "cost_savings_factor": cost_info['savings_factor'],
                    "duration_seconds": duration,
                    "output_file": output_file.name
                })
            else:
                print(f"   ✗ Failed to save translation")
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    # Process German translations
    print("\n\nPART 2: Translating English files to German")
    print("-" * 60)
    
    for i, file_info in enumerate(files_for_german, 1):
        file_id = file_info["id"]
        base_path = Path(__file__).parent.parent / "output" / file_id
        
        # Use English translation if it exists, otherwise use original
        en_srt = base_path / f"{file_id}.en.srt"
        if not en_srt.exists():
            en_srt = base_path / f"{file_id}.orig.srt"
            
        if not en_srt.exists():
            print(f"{i}. File not found: {en_srt}")
            continue
            
        print(f"\n{i}. Processing {file_info['name']} ({file_id})")
        
        try:
            # Cost estimation
            cost_info = translator.estimate_cost(str(en_srt), 'de')
            print(f"   Total segments: {cost_info['total_segments']}")
            print(f"   Segments to translate: {cost_info['segments_to_translate']}")
            print(f"   Unique texts: {cost_info['unique_texts']}")
            print(f"   Deduplication rate: {(1 - cost_info['unique_texts']/cost_info['total_segments'])*100:.1f}%")
            print(f"   Cost savings: {cost_info['savings_factor']:.1f}x")
            
            # Translate
            print(f"   Translating to German...")
            start_time = datetime.now()
            
            translated_segments = translator.translate_srt(
                str(en_srt),
                'de',
                preserve_original_when_matching=True,
                batch_size=50
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Save result
            output_file = output_dir / f"{file_id}_new_de.srt"
            success = translator.save_translated_srt(translated_segments, str(output_file))
            
            if success:
                print(f"   ✓ Success! Translation took {duration:.1f}s")
                print(f"   Output: {output_file.name}")
                
                # Add to results
                results["german_translations"].append({
                    "file_id": file_id,
                    "name": file_info["name"],
                    "source_file": en_srt.name,
                    "total_segments": cost_info['total_segments'],
                    "segments_translated": cost_info['segments_to_translate'],
                    "unique_texts": cost_info['unique_texts'],
                    "deduplication_rate": (1 - cost_info['unique_texts']/cost_info['total_segments'])*100,
                    "cost_savings_factor": cost_info['savings_factor'],
                    "duration_seconds": duration,
                    "output_file": output_file.name
                })
            else:
                print(f"   ✗ Failed to save translation")
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    # Save results report
    report_file = output_dir / "translation_report.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\n\nSUMMARY")
    print("=" * 60)
    print(f"English translations: {len(results['english_translations'])} files")
    print(f"German translations: {len(results['german_translations'])} files")
    
    if results['english_translations']:
        avg_dedup = sum(r['deduplication_rate'] for r in results['english_translations']) / len(results['english_translations'])
        avg_savings = sum(r['cost_savings_factor'] for r in results['english_translations']) / len(results['english_translations'])
        print(f"\nEnglish translation stats:")
        print(f"  Average deduplication rate: {avg_dedup:.1f}%")
        print(f"  Average cost savings: {avg_savings:.1f}x")
    
    if results['german_translations']:
        avg_dedup = sum(r['deduplication_rate'] for r in results['german_translations']) / len(results['german_translations'])
        avg_savings = sum(r['cost_savings_factor'] for r in results['german_translations']) / len(results['german_translations'])
        print(f"\nGerman translation stats:")
        print(f"  Average deduplication rate: {avg_dedup:.1f}%")
        print(f"  Average cost savings: {avg_savings:.1f}x")
    
    print(f"\nResults saved to: {output_dir}/")
    print(f"Report saved to: {report_file.name}")
    
    # Show sample of first translated file
    if results['english_translations']:
        sample_file = output_dir / results['english_translations'][0]['output_file']
        if sample_file.exists():
            print(f"\nSample from {sample_file.name}:")
            print("-" * 40)
            with open(sample_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:20]
                print(''.join(lines))


if __name__ == "__main__":
    generate_subtitles()