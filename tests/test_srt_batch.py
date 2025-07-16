#!/usr/bin/env python3
"""
Test SRT translation on a small batch of files.
"""

import os
import sys
from pathlib import Path

# Add the scribe package to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scribe.srt_translator import translate_srt_file
from scribe.database import Database

def main():
    print("Testing SRT Translation on Small Batch")
    print("=" * 50)
    
    # Get some files to test
    db = Database()
    
    # Get files with transcription completed
    files = db.get_files_by_status('completed', limit=5)
    
    if not files:
        print("No completed files found!")
        return
    
    output_dir = Path("output")
    
    # Test English translation
    print("\nTesting English translations:")
    print("-" * 30)
    
    en_count = 0
    for file_info in files[:5]:
        file_id = file_info['file_id']
        file_dir = output_dir / file_id
        
        # Check for original SRT
        orig_srt = file_dir / f"{file_id}.orig.srt"
        if not orig_srt.exists():
            orig_srt = file_dir / f"{file_id}.srt"
            if not orig_srt.exists():
                print(f"✗ {file_id}: No original SRT found")
                continue
        
        # Output path
        en_srt = file_dir / f"{file_id}.en.srt"
        
        # Skip if already exists (unless backed up)
        if en_srt.exists():
            print(f"✓ {file_id}: English SRT already exists")
            continue
        
        print(f"→ Translating {file_id} to English...")
        
        try:
            success = translate_srt_file(
                str(orig_srt),
                str(en_srt),
                target_language='en',
                preserve_original_when_matching=True
            )
            
            if success:
                print(f"✓ {file_id}: Successfully translated to English")
                en_count += 1
            else:
                print(f"✗ {file_id}: Translation failed")
                
        except Exception as e:
            print(f"✗ {file_id}: Error - {e}")
    
    # Test German translation
    print("\n\nTesting German translations:")
    print("-" * 30)
    
    de_count = 0
    for file_info in files[:5]:
        file_id = file_info['file_id']
        file_dir = output_dir / file_id
        
        # Check for original SRT
        orig_srt = file_dir / f"{file_id}.orig.srt"
        if not orig_srt.exists():
            orig_srt = file_dir / f"{file_id}.srt"
            if not orig_srt.exists():
                print(f"✗ {file_id}: No original SRT found")
                continue
        
        # Output path
        de_srt = file_dir / f"{file_id}.de.srt"
        
        # Skip if already exists (unless backed up)
        if de_srt.exists():
            print(f"✓ {file_id}: German SRT already exists")
            continue
        
        print(f"→ Translating {file_id} to German...")
        
        try:
            success = translate_srt_file(
                str(orig_srt),
                str(de_srt),
                target_language='de',
                preserve_original_when_matching=True
            )
            
            if success:
                print(f"✓ {file_id}: Successfully translated to German")
                de_count += 1
            else:
                print(f"✗ {file_id}: Translation failed")
                
        except Exception as e:
            print(f"✗ {file_id}: Error - {e}")
    
    print("\n" + "=" * 50)
    print(f"Summary:")
    print(f"- English translations completed: {en_count}")
    print(f"- German translations completed: {de_count}")
    
    # Show a sample of what was preserved vs translated
    if en_count > 0:
        print("\nSample English translation (first file):")
        sample_file = None
        for file_info in files[:5]:
            file_id = file_info['file_id']
            en_srt = output_dir / file_id / f"{file_id}.en.srt"
            if en_srt.exists() and not (output_dir / file_id / f"{file_id}.en.srt.backup").exists():
                sample_file = en_srt
                break
        
        if sample_file:
            print(f"File: {sample_file}")
            with open(sample_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Show first 30 lines
                for line in lines[:30]:
                    print(line.rstrip())

if __name__ == "__main__":
    main()