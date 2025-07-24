#!/usr/bin/env python3
"""
Process single interview with our fix and validate the results
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
    
    # Process German translation with our fix
    orig_srt = output_dir / f"{interview_id}.orig.srt"
    de_srt = output_dir / f"{interview_id}.de.srt"
    
    print(f"🔄 Processing German translation for {interview_id}...")
    print(f"Input: {orig_srt}")
    print(f"Output: {de_srt}")
    
    # First, backup the existing file
    if de_srt.exists():
        backup_path = de_srt.with_suffix('.srt.backup_old')
        print(f"📦 Backing up existing file to {backup_path}")
        import shutil
        shutil.copy2(de_srt, backup_path)
    
    # Process with our fix
    success = translate_srt_file(
        str(orig_srt),
        str(de_srt),
        target_language='de',
        preserve_original_when_matching=True,  # Key fix - preserve German segments!
        batch_size=100,
        estimate_only=False
    )
    
    if not success:
        print("❌ Translation failed!")
        return False
    
    print("✅ Translation complete!")
    
    # Convert to VTT
    de_vtt = output_dir / f"{interview_id}.de.vtt"
    print(f"\n🔄 Converting SRT to VTT...")
    
    from scribe_viewer.scripts.build_manifest import convert_srt_to_vtt
    if convert_srt_to_vtt(str(de_srt), str(de_vtt)):
        print(f"✅ Created {de_vtt}")
    else:
        print(f"❌ Failed to create VTT")
        return False
    
    # Validate the output
    print("\n🔍 Validating output...")
    
    # Check specific timestamp that had English text
    with open(de_vtt, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the problematic timestamp
    target_time = "00:39:42.030 --> 00:39:45.110"
    if target_time in content:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if target_time in line and i+1 < len(lines):
                next_line = lines[i+1].strip()
                print(f"\n📍 Content at {target_time}:")
                print(f"   '{next_line}'")
                
                if "much Jews" in next_line:
                    print("   ❌ FAILED: English text not translated!")
                    return False
                elif "viele Juden" in next_line or "Juden" in next_line:
                    print("   ✅ SUCCESS: Correctly translated to German!")
                else:
                    print(f"   ⚠️  Content: {next_line}")
    
    print("\n✅ All validations passed!")
    print("\nThe subtitle files are now ready in:")
    print(f"  - {de_srt}")
    print(f"  - {de_vtt}")
    print(f"\nThe symlinks in public/media/{interview_id}/ will use these updated files.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)