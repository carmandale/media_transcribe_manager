#!/usr/bin/env python3
"""Create English SRT from existing translation."""

import json
from pathlib import Path

file_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
output_dir = Path("output") / file_id

# Read the original SRT for timing
orig_srt_path = output_dir / f"{file_id}.orig.srt"
en_txt_path = output_dir / f"{file_id}.en.txt"
raw_translations_path = output_dir / f"{file_id}.raw_translations.json"
en_srt_path = output_dir / f"{file_id}.en.srt"

# Read raw translations if available
if raw_translations_path.exists():
    with open(raw_translations_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    if 'english_translations' in raw_data and 'segments' in raw_data['english_translations']:
        print(f"Found English segments in raw translations")
        en_segments = raw_data['english_translations']['segments']
        
        # Read original SRT for timing
        with open(orig_srt_path, 'r', encoding='utf-8') as f:
            orig_content = f.read()
            
        # Parse original SRT
        segments = []
        for block in orig_content.strip().split('\n\n'):
            lines = block.split('\n')
            if len(lines) >= 3:
                segment_num = lines[0]
                timing = lines[1]
                text = '\n'.join(lines[2:])
                segments.append((segment_num, timing, text))
        
        # Create English SRT
        srt_content = []
        for i, (seg_num, timing, orig_text) in enumerate(segments):
            if i < len(en_segments):
                en_text = en_segments[i].get('translation', orig_text)
            else:
                en_text = orig_text
            
            srt_content.append(f"{seg_num}\n{timing}\n{en_text}")
        
        # Write English SRT
        with open(en_srt_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(srt_content) + '\n')
            
        print(f"✅ Created English SRT: {en_srt_path}")
        
        # Convert to VTT
        vtt_path = en_srt_path.with_suffix('.vtt')
        with open(en_srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        vtt_content = "WEBVTT\n\n" + srt_content.replace(',', '.')
        
        with open(vtt_path, 'w', encoding='utf-8') as f:
            f.write(vtt_content)
            
        print(f"✅ Created English VTT: {vtt_path}")
    else:
        print("❌ No English segments found in raw translations")
else:
    print("❌ Raw translations file not found")