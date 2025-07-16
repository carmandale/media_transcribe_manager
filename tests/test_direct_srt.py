#!/usr/bin/env python3
"""
Direct test of SRT translation on known files.
"""

import os
import sys
from pathlib import Path

# Add the scribe package to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scribe.srt_translator import translate_srt_file

def test_file(file_id, target_lang):
    """Test translation of a single file."""
    output_dir = Path("output")
    file_dir = output_dir / file_id
    
    # Input and output paths
    orig_srt = file_dir / f"{file_id}.orig.srt"
    if not orig_srt.exists():
        orig_srt = file_dir / f"{file_id}.srt"
    
    output_srt = file_dir / f"{file_id}.{target_lang}.srt"
    
    print(f"\nProcessing {file_id} → {target_lang}:")
    print(f"  Input: {orig_srt}")
    print(f"  Output: {output_srt}")
    
    if not orig_srt.exists():
        print(f"  ✗ Original SRT not found!")
        return False
    
    # Show first few segments of original
    print(f"\n  Original SRT preview:")
    with open(orig_srt, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines[:20]):
            if i < 20:
                print(f"    {line.rstrip()}")
    
    # Translate
    print(f"\n  Translating to {target_lang.upper()}...")
    
    try:
        # Use environment variables for API keys
        config = {
            'openai_model': 'gpt-4.1-mini'
        }
        
        success = translate_srt_file(
            str(orig_srt),
            str(output_srt),
            target_language=target_lang,
            preserve_original_when_matching=True,
            config=config
        )
        
        if success:
            print(f"  ✓ Translation successful!")
            
            # Show preview of result
            print(f"\n  Translated SRT preview:")
            with open(output_srt, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[:20]):
                    if i < 20:
                        print(f"    {line.rstrip()}")
            
            return True
        else:
            print(f"  ✗ Translation failed!")
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("Direct SRT Translation Test")
    print("=" * 50)
    
    # Test files we backed up
    test_files = [
        "4499e44a-7a67-4af8-b66f-c50a6a4570ba",
        "eae1965d-761b-4553-bca2-167290792a96",
        "367a7254-133c-45f4-ba45-8805980a7b5f",
        "3e4125f1-e600-465d-b782-8e53e6699129",
        "f5972be6-6904-4977-bce1-df848acfd9ae"
    ]
    
    # Test English translations
    print("\n\nENGLISH TRANSLATIONS")
    print("=" * 50)
    
    en_success = 0
    for file_id in test_files[:5]:
        if test_file(file_id, 'en'):
            en_success += 1
    
    # Test German translations
    print("\n\nGERMAN TRANSLATIONS")
    print("=" * 50)
    
    de_success = 0
    for file_id in test_files[:5]:
        if test_file(file_id, 'de'):
            de_success += 1
    
    print("\n" + "=" * 50)
    print(f"SUMMARY:")
    print(f"  English translations: {en_success}/5 successful")
    print(f"  German translations: {de_success}/5 successful")

if __name__ == "__main__":
    main()