#!/usr/bin/env python3
"""
manage_source_material.py

Create symlinks for all source material (video + audio) under:
    output/source_material/{video,audio}/

Naming: <file_id>_<shortName>.<ext> (first 3 tokens of safe_filename)
Supports --force (remake existing links) and --dry-run (preview only).
"""
import argparse
import os
import logging
import re
import sys
import shutil
# ensure project root in PYTHONPATH for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from db_manager import DatabaseManager

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x


def shorten_name(base: str, tokens: int = 3) -> str:
    parts = re.split(r'[_\-\s]+', base)
    return '_'.join(parts[:tokens]) if parts else base


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage source material symlinks for video and audio."
    )
    parser.add_argument(
        '--db', default='media_tracking.db', help='Path to SQLite DB file'
    )
    parser.add_argument(
        '--output-dir', default='./output/source_material',
        help='Base directory for source_material outputs'
    )
    parser.add_argument(
        '--force', action='store_true', help='Force recreate existing links'
    )
    parser.add_argument(
        '--dry-run', action='store_true', help='Preview actions without changes'
    )
    parser.add_argument('--clean', action='store_true', help='Remove non-video/audio content under output_dir')
    parser.add_argument('--verify', action='store_true', help='Verify symlinks against DB entries')
    parser.add_argument('--export', metavar='DEST', help='Copy source_material and pipelines to DEST as real files')
    parser.add_argument('--main-output', default='./output', help='Root directory for transcripts/subtitles/translations (default: ./output)')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Prevent using the main output directory
    root_dir = os.path.abspath('output')
    out_dir = os.path.abspath(args.output_dir)
    if out_dir == root_dir:
        logger.error("Invalid --output-dir: refusing to use the main output directory ('output'). Please specify a subfolder such as './output/source_material'.")
        sys.exit(1)

    db = DatabaseManager(args.db)
    # Only create source_material subdirs (video, audio)
    video_dir = os.path.join(args.output_dir, 'videos')
    audio_dir = os.path.join(args.output_dir, 'audio')
    if not args.dry_run:
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)

    # Clean non-video/audio if requested
    if args.clean:
        logger.info("Cleaning source_material directory...")
        if os.path.isdir(args.output_dir):
            for entry in os.listdir(args.output_dir):
                if entry not in ('videos', 'audio'):
                    full = os.path.join(args.output_dir, entry)
                    try:
                        if os.path.isdir(full):
                            shutil.rmtree(full)
                            logger.info(f"Removed folder: {full}")
                        else:
                            os.remove(full)
                            logger.info(f"Removed file: {full}")
                    except Exception as e:
                        logger.error(f"Error removing {full}: {e}")
        else:
            logger.warning(f"Cannot clean; directory not found: {args.output_dir}")

    # Query both video and audio entries
    rows = db.execute_query(
        "SELECT file_id, original_path, safe_filename, media_type "
        "FROM media_files WHERE media_type IN (?,?)",
        ('video', 'audio')
    )

    created = 0
    errors = 0

    for row in tqdm(rows, desc="Linking source", unit="file"):
        file_id = row['file_id']
        media_type = row['media_type']
        orig = row['original_path']
        safe = row['safe_filename']
        ext = os.path.splitext(orig)[1].lower()
        base = os.path.splitext(safe)[0]
        short = shorten_name(base, tokens=3)
        link_name = f"{file_id}_{short}{ext}"
        target_dir = video_dir if media_type == 'video' else audio_dir
        link_path = os.path.join(target_dir, link_name)

        if not os.path.exists(orig):
            logger.warning(f"Original missing: {orig}")
            errors += 1
            continue

        if os.path.exists(link_path):
            if args.force:
                try:
                    os.unlink(link_path)
                    logger.debug(f"Removed existing: {link_path}")
                except Exception as e:
                    logger.error(f"Failed to remove {link_path}: {e}")
                    errors += 1
                    continue
            else:
                logger.info(f"Exists, skipping: {link_path}")
                continue

        if args.dry_run:
            logger.info(f"[DRY RUN] Would link {link_path} -> {orig}")
            created += 1
        else:
            try:
                os.symlink(orig, link_path)
                logger.info(f"Created: {link_path} -> {orig}")
                created += 1
            except Exception as e:
                logger.error(f"Error linking {file_id}: {e}")
                errors += 1

    # Verify symlinks if requested
    if args.verify:
        logger.info("Verifying symlinks against database entries...")
        rows = db.execute_query(
            "SELECT file_id, media_type FROM media_files WHERE media_type IN (?,?)",
            ('video','audio')
        )
        db_video = {r['file_id'] for r in rows if r['media_type']=='video'}
        db_audio = {r['file_id'] for r in rows if r['media_type']=='audio'}
        fs_video = {fn.split('_',1)[0] for fn in os.listdir(video_dir)}
        fs_audio = {fn.split('_',1)[0] for fn in os.listdir(audio_dir)}
        missing_v = db_video - fs_video
        extra_v = fs_video - db_video
        missing_a = db_audio - fs_audio
        extra_a = fs_audio - db_audio
        logger.info(f" Video - missing: {len(missing_v)}, extra: {len(extra_v)}")
        for m in missing_v: logger.warning(f"Missing video symlink: {m}")
        for x in extra_v: logger.warning(f"Extra video symlink: {x}")
        logger.info(f" Audio - missing: {len(missing_a)}, extra: {len(extra_a)}")
        for m in missing_a: logger.warning(f"Missing audio symlink: {m}")
        for x in extra_a: logger.warning(f"Extra audio symlink: {x}")

    # Export real files if requested
    if args.export:
        dest = args.export
        main_out = os.path.abspath(args.main_output)
        logger.info(f"Exporting files to {dest} ...")
        os.makedirs(dest, exist_ok=True)
        for sub in ('videos','audio'):
            src = os.path.join(args.output_dir, sub)
            dst = os.path.join(dest, sub)
            shutil.copytree(src, dst, dirs_exist_ok=True)
        for sub in ('transcripts','translations','subtitles'):
            src = os.path.join(main_out, sub)
            dst = os.path.join(dest, sub)
            if os.path.exists(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                logger.warning(f"Skipping missing: {src}")

    logger.info(f"Complete: created={created}, errors={errors}")


if __name__ == '__main__':
    main()
