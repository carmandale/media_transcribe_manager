#!/usr/bin/env python3
"""
Quick sanity check to find Hebrew translation files that might actually be in English
"""
import re
from pathlib import Path
import sys

def contains_hebrew(text):
    """Check if text contains Hebrew characters"""
    hebrew_pattern = re.compile(r'[\u0590-\u05FF\uFB1D-\uFB4F]')
    return bool(hebrew_pattern.search(text))

def check_all_hebrew_files():
    """Scan all Hebrew translation files for English text"""
    output_dir = Path('output')
    english_files = []
    hebrew_files = 0
    errors = 0
    
    print("Scanning Hebrew translation files...")
    
    # Find all .he.txt files
    for file_path in output_dir.glob('*/*.he.txt'):
        try:
            text = file_path.read_text(encoding='utf-8')
            if not contains_hebrew(text[:1000]):  # Check first 1000 chars
                file_id = file_path.parent.name
                english_files.append(file_id)
                print(f"❌ {file_id}: No Hebrew detected - appears to be English!")
            else:
                hebrew_files += 1
        except Exception as e:
            errors += 1
            print(f"Error reading {file_path}: {e}")
    
    print(f"\nSummary:")
    print(f"  Hebrew files: {hebrew_files}")
    print(f"  English files: {len(english_files)}")
    print(f"  Errors: {errors}")
    
    if english_files:
        print(f"\nFiles that need re-translation to Hebrew:")
        for file_id in english_files[:20]:  # Show first 20
            print(f"  - {file_id}")
        if len(english_files) > 20:
            print(f"  ... and {len(english_files) - 20} more")
    
    return english_files

if __name__ == "__main__":
    check_all_hebrew_files()