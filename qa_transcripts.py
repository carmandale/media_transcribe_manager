#!/usr/bin/env python3
"""QA helper to validate transcripts and subtitle files.

Checks that for each media file the transcript and subtitle files for the
requested languages exist and are non‑empty.  Reports summary counts and lists
missing items.

Usage examples
--------------
python qa_transcripts.py                # default orig transcripts only
python qa_transcripts.py --languages orig,en,de --check-subtitles
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple, Dict, Any

# Ensure project root on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from scripts.one_off.process_transcriptions import _load_config  # type: ignore
from db_manager import DatabaseManager
from file_manager import FileManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QA transcripts and subtitles")
    parser.add_argument(
        "--languages",
        type=str,
        default="orig",
        help="Comma‑separated list of language codes to check (default: orig)",
    )
    parser.add_argument(
        "--check-subtitles",
        action="store_true",
        help="Also check that the corresponding .srt subtitle exists and is non‑empty",
    )
    return parser.parse_args()


def human_size(bytes_: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024:
            return f"{bytes_:,.1f}{unit}"
        bytes_ //= 1024
    return f"{bytes_:,.1f}TB"


def main() -> None:
    args = parse_args()
    langs = [l.strip() for l in args.languages.split(",") if l.strip()]

    cfg = _load_config()
    db = DatabaseManager(cfg.get("database_file", "media_tracking.db"))
    fm = FileManager(db, cfg)

    files: List[Dict[str, Any]] = db.execute_query(
        "SELECT file_id, safe_filename FROM media_files", ()
    )
    total_files = len(files)

    missing_items: List[str] = []
    bad_size_items: List[Tuple[str, str, str]] = []  # file_id, lang, path

    for row in files:
        fid = row["file_id"]
        for lang in langs:
            # Transcript path
            t_path = (
                fm.get_transcript_path(fid, None if lang == "orig" else lang)
            )
            if not t_path or not os.path.exists(t_path):
                missing_items.append(f"TRANSCRIPT {fid} {lang}: {t_path}")
            else:
                if os.path.getsize(t_path) == 0:
                    bad_size_items.append((fid, lang, t_path))
            if args.check_subtitles:
                s_path = fm.get_subtitle_path(fid, lang if lang != "orig" else "orig")
                if not s_path or not os.path.exists(s_path):
                    missing_items.append(f"SUBTITLE   {fid} {lang}: {s_path}")
                else:
                    if os.path.getsize(s_path) == 0:
                        bad_size_items.append((fid, lang, s_path))

    # Report
    print("QA SUMMARY")
    print("==========")
    print(f"Total media files: {total_files}")
    print(f"Languages checked: {', '.join(langs)}")
    print()
    print(f"Missing files: {len(missing_items)}")
    if missing_items:
        for item in missing_items[:20]:
            print(" -", item)
        if len(missing_items) > 20:
            print(" ... (truncated)")
    print(f"Zero‑byte files: {len(bad_size_items)}")
    if bad_size_items:
        for fid, lang, p in bad_size_items[:20]:
            print(f" - {fid} {lang}: {p}")
        if len(bad_size_items) > 20:
            print(" ... (truncated)")

    if not missing_items and not bad_size_items:
        print("\nAll checks passed ✅")


if __name__ == "__main__":
    main()
