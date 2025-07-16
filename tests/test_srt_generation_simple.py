#!/usr/bin/env python3
"""
Simplified test to generate SRT files without batch translation.
This will process files individually to avoid the separator issues.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scribe.srt_translator import translate_srt_file

def generate_subtitles_simple():
    """Generate subtitle samples using the translate_srt_file function."""
    
    # Create output directory
    output_dir = Path(__file__).parent / "srt_test_output" 
    output_dir.mkdir(exist_ok=True)
    
    # Just process 2 files for each language to demonstrate
    test_files = [
        {
            "id": "eae1965d-761b-4553-bca2-167290792a96",
            "target": "en",
            "name": "German Interview to English"
        },
        {
            "id": "367a7254-133c-45f4-ba45-8805980a7b5f",
            "target": "en", 
            "name": "German Interview to English"
        },
        {
            "id": "4499e44a-7a67-4af8-b66f-c50a6a4570ba",
            "target": "de",
            "name": "English Interview to German",
            "use_en_file": True
        },
        {
            "id": "ccfbd8b4-08f8-4773-9ecc-99b28c11726e",
            "target": "de",
            "name": "English Interview to German",
            "use_en_file": True
        }
    ]
    
    print("SRT Translation Test - Simple Version")
    print("=" * 60)
    print(f"Output directory: {output_dir}")
    print()
    
    results = []
    
    for i, file_info in enumerate(test_files, 1):
        file_id = file_info["id"]
        target_lang = file_info["target"]
        base_path = Path(__file__).parent.parent / "output" / file_id
        
        # Choose source file
        if file_info.get("use_en_file"):
            source_file = base_path / f"{file_id}.en.srt"
            if not source_file.exists():
                source_file = base_path / f"{file_id}.orig.srt"
        else:
            source_file = base_path / f"{file_id}.orig.srt"
            
        if not source_file.exists():
            print(f"{i}. File not found: {source_file}")
            continue
            
        output_file = output_dir / f"{file_id}_new_{target_lang}.srt"
        
        print(f"\n{i}. Processing {file_info['name']}")
        print(f"   Source: {source_file.name}")
        print(f"   Target language: {target_lang.upper()}")
        print(f"   Translating...")
        
        start_time = datetime.now()
        
        try:
            # Use the simple translate_srt_file function
            success = translate_srt_file(
                str(source_file),
                str(output_file),
                target_language=target_lang,
                preserve_original_when_matching=True,
                batch_size=10  # Small batch size to avoid issues
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if success:
                print(f"   ✓ Success! Translation took {duration:.1f}s")
                print(f"   Output: {output_file.name}")
                
                results.append({
                    "file_id": file_id,
                    "name": file_info["name"],
                    "target_language": target_lang,
                    "duration_seconds": duration,
                    "output_file": output_file.name,
                    "success": True
                })
                
                # Show first few lines of output
                with open(output_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:15]
                    print("\n   Sample output:")
                    print("   " + "-" * 40)
                    for line in lines:
                        print(f"   {line.rstrip()}")
                        
            else:
                print(f"   ✗ Translation failed")
                results.append({
                    "file_id": file_id,
                    "name": file_info["name"],
                    "target_language": target_lang,
                    "success": False
                })
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "file_id": file_id,
                "name": file_info["name"],
                "target_language": target_lang,
                "success": False,
                "error": str(e)
            })
    
    # Save results
    report_file = output_dir / "simple_translation_report.json"
    with open(report_file, 'w') as f:
        json.dump({
            "test_date": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)
    
    print("\n\nSUMMARY")
    print("=" * 60)
    successful = sum(1 for r in results if r.get('success'))
    print(f"Successfully translated: {successful}/{len(results)} files")
    print(f"Output directory: {output_dir}/")
    print(f"Report: {report_file.name}")


if __name__ == "__main__":
    generate_subtitles_simple()