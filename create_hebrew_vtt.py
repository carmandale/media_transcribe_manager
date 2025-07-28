#!/usr/bin/env python3
"""Convert Hebrew SRT to VTT for web viewer."""

srt_path = "output/25af0f9c-8f96-44c9-be5e-e92cb462a41f/25af0f9c-8f96-44c9-be5e-e92cb462a41f.he.srt"
vtt_path = "output/25af0f9c-8f96-44c9-be5e-e92cb462a41f/25af0f9c-8f96-44c9-be5e-e92cb462a41f.he.vtt"

with open(srt_path, 'r', encoding='utf-8') as f:
    srt_content = f.read()

vtt_content = "WEBVTT\n\n" + srt_content.replace(',', '.')

with open(vtt_path, 'w', encoding='utf-8') as f:
    f.write(vtt_content)

print(f"✅ Created Hebrew VTT file: {vtt_path}")