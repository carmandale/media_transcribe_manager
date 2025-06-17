#!/usr/bin/env python3
"""Test script to process just one file from the batch"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from retranslate_hebrew_batch import HebrewRetranslator

if __name__ == "__main__":
    processor = HebrewRetranslator()
    
    # Get first file from TSV
    entries = processor.read_tsv()
    if entries:
        file_id = entries[0][0]
        print(f"Testing with file: {file_id}")
        
        success = processor.translate_file(file_id)
        
        if success:
            print("✓ Test successful!")
            # Don't update TSV for test
        else:
            print("✗ Test failed!")
    else:
        print("No entries in TSV")