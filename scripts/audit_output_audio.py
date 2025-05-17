#!/usr/bin/env python3
"""
Audit the contents of the legacy output/audio directory.
Lists total .mp3 files and a sample list with sizes.
"""
import argparse
from pathlib import Path

def main(audio_dir: Path, sample: int):
    audio_dir = Path(audio_dir)
    if not audio_dir.is_dir():
        print(f"Audio directory does not exist: {audio_dir}")
        return
    files = list(audio_dir.rglob("*.mp3"))
    print(f"Found {len(files)} .mp3 files in {audio_dir}")
    if sample > 0 and files:
        print(f"Sample files (up to {sample}):")
        for f in files[:sample]:
            size_kb = f.stat().st_size // 1024
            print(f"  {f.relative_to(audio_dir)} ({size_kb} KB)")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Audit legacy output/audio directory'
    )
    parser.add_argument(
        '--dir', '-d', default='output/audio',
        help='Path to the output/audio directory'
    )
    parser.add_argument(
        '--sample', '-n', type=int, default=20,
        help='Number of sample files to display'
    )
    args = parser.parse_args()
    main(args.dir, args.sample)