#!/usr/bin/env python3
"""
Migrate legacy flat output into per-media folders named by DB file_id.
Moves audio, transcripts, translations, and subtitles into output/<file_id>/
and renames them to <file_id>.<ext>. Updates safe_filename in DB accordingly.
"""
import argparse
import sqlite3
from pathlib import Path
import shutil

def migrate(db_path, output_dir, dry_run=False, cleanup=False):
    """
    Migrate flat output into per-media folders.
    If cleanup=True, remove legacy flat dirs and top-level symlinks.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Fetch unique ID, original source path, safe filename, and media type
    cursor.execute("SELECT file_id, original_path, safe_filename, media_type FROM media_files")
    rows = cursor.fetchall()
    print(f"Migrating {len(rows)} media entries into {output_dir}")
    out_root = Path(output_dir)
    audio_root = out_root / 'audio'
    transcripts_root = out_root / 'transcripts'
    translations_root = out_root / 'translations'
    subtitles_root = out_root / 'subtitles'
    langs = ['en', 'de', 'he']

    for file_id, original_path, safe_fn, media_type in rows:
        stem = Path(safe_fn).stem
        ext = Path(safe_fn).suffix
        new_fn = f"{file_id}{ext}"
        target_dir = out_root / file_id
        print(f"-- {file_id}: mkdir {target_dir}")
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        # Move any transcripts whose flat name begins with this file_id
        for suffix in ('.txt', '.txt.json'):
            for src in transcripts_root.glob(f"{file_id}*{suffix}"):
                dst = target_dir / f"{file_id}{suffix}"
                print(f"   Move transcript: {src.name} -> {dst.name}")
                if not dry_run:
                    src.rename(dst)

        # Move any translations whose flat name begins with this file_id
        # Move any translations in per-language subdirs for this file_id
        for lang in langs:
            lang_dir = translations_root / lang
            if lang_dir.exists():
                for src in lang_dir.glob(f"{file_id}*_{lang}.txt"):
                    dst = target_dir / f"{file_id}.{lang}.txt"
                    print(f"   Move translation [{lang}]: {src.name} -> {dst.name}")
                    if not dry_run:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        src.rename(dst)

        # Move any subtitles whose flat name begins with this file_id
        # Move any subtitles in per-language subdirs for this file_id
        for lang in langs:
            subdir = subtitles_root / lang
            if subdir.exists():
                # support .srt and .vtt subtitle formats
                for suffix in ('.srt', '.vtt'):
                    for src in subdir.glob(f"{file_id}*_{lang}{suffix}"):
                        dst = target_dir / f"{file_id}.{lang}{suffix}"
                        print(f"   Move subtitle [{lang}]: {src.name} -> {dst.name}")
                        if not dry_run:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            src.rename(dst)
        # Move original ('orig') subtitles into <file_id>.orig.srt/vtt
        orig_subdir = subtitles_root / 'orig'
        if orig_subdir.exists():
            for suffix in ('.srt', '.vtt'):
                for src in orig_subdir.glob(f"{file_id}*{suffix}"):
                    dst = target_dir / f"{file_id}.orig{suffix}"
                    print(f"   Move original subtitle: {src.name} -> {dst.name}")
                    if not dry_run:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        src.rename(dst)



        print(f"   Update DB safe_filename -> {new_fn}")
        if not dry_run:
            cursor.execute(
                "UPDATE media_files SET safe_filename = ? WHERE file_id = ?",
                (new_fn, file_id)
            )
        # Symlink original source file into its per-media folder
        src_media = Path(original_path)
        dst_media = target_dir / new_fn
        if src_media.exists():
            print(f"   Symlink source: {dst_media.name} -> {src_media}")
            if not dry_run:
                if dst_media.exists() or dst_media.is_symlink():
                    dst_media.unlink()
                dst_media.symlink_to(src_media)
        # Move translation-comparison artifacts into per-media folder
        tc_root = out_root / 'translation_comparison'
        if tc_root.exists():
            for src in tc_root.glob(f"{file_id}_*.json"):
                new_name = src.name.replace(f"{file_id}_", f"{file_id}.")
                dst = target_dir / new_name
                print(f"   Move translation-comparison: {src.name} -> {dst.name}")
                if not dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    src.rename(dst)

    if not dry_run:
        conn.commit()
    conn.close()
    print("Migration complete.")
    # Cleanup legacy directories and top-level symlinks
    if cleanup:
        print("Cleaning up legacy flat directories and symlinks...")
        # Remove old flat directories
        legacy_dirs = ['audio', 'transcripts', 'translations', 'subtitles', 'translation_comparison']
        for d in legacy_dirs:
            path = out_root / d
            if path.exists():
                print(f"  Remove directory: {path}")
                if not dry_run:
                    shutil.rmtree(path)
        # Remove any remaining top-level media symlinks (*.mp4, *.mp3)
        for suffix in ('.mp4', '.mp3'):
            for link in out_root.glob(f"*{suffix}"):
                if link.is_symlink():
                    print(f"  Remove symlink: {link}")
                    if not dry_run:
                        link.unlink()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Migrate flat output/ into per-media folders by DB file_id"
    )
    parser.add_argument('--db',   '-d', required=True, help='media_tracking.db path')
    parser.add_argument('--output','-o', default='output', help='root output dir')
    parser.add_argument('--dry-run', action='store_true', help='Show actions without moving files or updating DB')
    parser.add_argument('--cleanup', action='store_true', help='Remove legacy flat dirs and top-level symlinks after migration')
    args = parser.parse_args()
    migrate(args.db, args.output, args.dry_run, args.cleanup)
