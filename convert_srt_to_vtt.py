#!/usr/bin/env python3
"""
Convert the new German SRT file to VTT format for web viewer.
"""

import sys
from pathlib import Path

def convert_srt_to_vtt(srt_path, vtt_path):
    """Convert SRT to VTT format."""
    
    print(f"Converting {srt_path} to {vtt_path}")
    
    with open(srt_path, 'r', encoding='utf-8') as srt_file:
        srt_content = srt_file.read()
    
    # VTT format starts with "WEBVTT"
    vtt_content = "WEBVTT\n\n"
    
    # Replace SRT timestamps (00:00:00,000) with VTT format (00:00:00.000)
    vtt_content += srt_content.replace(',', '.')
    
    with open(vtt_path, 'w', encoding='utf-8') as vtt_file:
        vtt_file.write(vtt_content)
    
    print(f"✅ Converted successfully")
    return True

def main():
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    srt_path = f"output/{interview_id}/{interview_id}.de.srt"
    vtt_path = f"output/{interview_id}/{interview_id}.de.vtt"
    
    print("🔄 Converting SRT to VTT for Web Viewer")
    print("=" * 40)
    
    if not Path(srt_path).exists():
        print(f"❌ SRT file not found: {srt_path}")
        return False
    
    # Backup existing VTT if it exists
    if Path(vtt_path).exists():
        backup_path = f"{vtt_path}.backup"
        Path(vtt_path).rename(backup_path)
        print(f"📦 Backed up existing VTT to {backup_path}")
    
    success = convert_srt_to_vtt(srt_path, vtt_path)
    
    if success:
        # Check file sizes
        srt_size = Path(srt_path).stat().st_size
        vtt_size = Path(vtt_path).stat().st_size
        print(f"📊 File sizes:")
        print(f"  SRT: {srt_size:,} bytes")
        print(f"  VTT: {vtt_size:,} bytes")
        print(f"✅ Ready for web viewer testing")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)