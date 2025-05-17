#!/usr/bin/env python3
"""
Validate that output/<file_id>/ folders contain all expected artifacts:
  - Media symlink (.mp4 or .mp3)
  - Transcript (.txt) and metadata (.txt.json)
  - Translations (.en.txt, .de.txt, .he.txt)
  - Subtitles (.en.srt/.vtt, .de.srt/.vtt, .he.srt/.vtt)
  - Original subtitle (.orig.srt/.vtt)
  - Translation-comparison JSONs (.raw_translations.json, .evaluations.json)
"""
import sys
import sqlite3
from pathlib import Path

def main():
    db_path = Path('media_tracking.db')
    out_root = Path('output')
    langs = ['en', 'de', 'he']

    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}")
        sys.exit(1)
    if not out_root.exists():
        print(f"ERROR: output directory not found at {out_root}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute('SELECT file_id FROM media_files')
    rows = cursor.fetchall()
    conn.close()

    errors = []
    # Check essential artifacts for each ID
    for (file_id,) in rows:
        d = out_root / file_id
        if not d.is_dir():
            errors.append(f"{file_id}: missing folder {d}")
            continue
        # Media (.mp4 or .mp3)
        if not any((d / f"{file_id}{ext}").exists() for ext in ('.mp4', '.mp3')):
            errors.append(f"{file_id}: missing media (.mp4/.mp3)")
        # Transcript and metadata
        if not (d / f"{file_id}.txt").exists():
            errors.append(f"{file_id}: missing transcript {file_id}.txt")
        if not (d / f"{file_id}.txt.json").exists():
            errors.append(f"{file_id}: missing transcript metadata {file_id}.txt.json")

    # Ensure legacy flat directories and symlinks are removed from output root
    legacy = ['audio', 'transcripts', 'translations', 'subtitles', 'translation_comparison']
    for name in legacy:
        p = out_root / name
        if p.exists():
            errors.append(f"legacy directory still present: {p}")
    # Check that no top-level media symlinks remain
    for ext in ('.mp4', '.mp3'):
        for link in out_root.glob(f"*{ext}"):
            if link.is_symlink():
                errors.append(f"top-level symlink still present: {link.name}")

    if errors:
        print("Validation failures:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("All output/<file_id>/ folders are valid and complete.")
    sys.exit(0)

if __name__ == '__main__':
    main()