#!/usr/bin/env python3
"""
Cleanup and rename existing output folders/files to use DB file_id as basename.
Also updates media_files.safe_filename in the database.
"""
import argparse
import sqlite3
from pathlib import Path

def main(db_path: str, output_dir: str, dry_run: bool):
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, safe_filename FROM media_files")
    rows = cursor.fetchall()
    if not rows:
        print("No media_files entries found. Nothing to do.")
        return

    out_root = Path(output_dir)
    print(f"Processing {len(rows)} folders under {out_root}")
    for file_id, safe_fn in rows:
        old_stem = Path(safe_fn).stem
        ext = Path(safe_fn).suffix
        new_fn = f"{file_id}{ext}"
        old_dir = out_root / old_stem
        new_dir = out_root / file_id
        if not old_dir.exists():
            print(f"[WARN] Missing directory for {file_id}: {old_dir}")
            continue
        print(f"Renaming directory: {old_dir} -> {new_dir}")
        if not dry_run:
            old_dir.rename(new_dir)
        # Rename contained files
        for fpath in new_dir.iterdir():
            name = fpath.name
            if name == safe_fn:
                target = new_fn
            elif name.startswith(f"{old_stem}."):
                suffix = name[len(old_stem):]
                target = f"{file_id}{suffix}"
            else:
                continue
            src = new_dir / name
            dst = new_dir / target
            print(f"  {name} -> {target}")
            if not dry_run:
                src.rename(dst)
        # Update DB safe_filename
        print(f"Updating DB safe_filename -> {new_fn} for {file_id}")
        if not dry_run:
            cursor.execute(
                "UPDATE media_files SET safe_filename = ? WHERE file_id = ?",
                (new_fn, file_id)
            )
    if not dry_run:
        conn.commit()
    conn.close()
    print("Cleanup complete.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Rename output folders/files to DB file_id.'
    )
    parser.add_argument(
        '--db', '-d', required=True,
        help='Path to the SQLite database file (e.g. media_tracking.db)'
    )
    parser.add_argument(
        '--output', '-o', default='output',
        help='Path to the output directory'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show actions without performing renames or DB updates'
    )
    args = parser.parse_args()
    main(args.db, args.output, args.dry_run)