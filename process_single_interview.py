#!/usr/bin/env python3
"""
Process a single interview using the exact same method that worked for 728 interviews.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scribe.srt_translator import translate_srt_file

def main():
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    output_dir = Path(f"output/{interview_id}")
    orig_srt = output_dir / f"{interview_id}.orig.srt"
    output_srt = output_dir / f"{interview_id}.de.srt"
    
    print(f"Processing {interview_id}...")
    print(f"Input: {orig_srt}")
    print(f"Output: {output_srt}")
    
    # Use EXACTLY what worked for 728 interviews
    success = translate_srt_file(
        str(orig_srt),
        str(output_srt),
        target_language='de',
        preserve_original_when_matching=True,  # This is the key fix!
        batch_size=100,
        estimate_only=False
    )
    
    if success:
        print(f"\n✅ SUCCESS! Interview processed.")
        print(f"\nNext steps:")
        print("1. Run: python scribe-viewer/scripts/build_manifest.py")
        print("2. Start viewer: cd scribe-viewer && npm run dev")
        print(f"3. Open: http://localhost:3000/viewer/{interview_id}")
    else:
        print(f"\n❌ Failed to process interview")

if __name__ == "__main__":
    main()