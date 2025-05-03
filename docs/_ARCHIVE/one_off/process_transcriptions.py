#!/usr/bin/env python3
"""
Process transcriptions for new or failed media
--------------------------------------------
Combines the former `process_untranscribed.py` (for never‑started files) and
`retry_extraction.py` (for previously failed files) into one configurable
entry‑point.

Usage examples
--------------
# Process backlog (default behaviour, i.e. transcription_status = 'not_started')
python process_transcriptions.py --batch-size 10

# Retry failures only
python process_transcriptions.py --status failed --batch-size 5

# Handle everything that still needs work (both failed and not_started)
python process_transcriptions.py --status all

# Force a single UUID regardless of current status
python process_transcriptions.py --file-id <uuid>
"""

from __future__ import annotations

import os
import sys
import logging
import yaml
import json
import argparse
import datetime
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from tqdm import tqdm

# Ensure project root on PYTHONPATH so "scripts/one_off" can be executed directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)))

from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGER_NAME = "process_transcriptions"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"{LOGGER_NAME}.log"),
    ],
)
logger = logging.getLogger(LOGGER_NAME)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """Load YAML/JSON config or return sensible defaults."""
    default_config: Dict[str, Any] = {
        "output_directory": "./output",
        "database_file": "./media_tracking.db",
        "log_level": "INFO",
        "workers": 4,
        "extract_audio_format": "mp3",
        "extract_audio_quality": "192k",
        "elevenlabs": {
            "api_key": os.getenv("ELEVENLABS_API_KEY"),
            "model": "scribe_v1",
            "speaker_detection": True,
            "speaker_count": 32,
        },
        "deepl": {
            "api_key": os.getenv("DEEPL_API_KEY"),
            "formality": "default",
            "batch_size": 5000,
        },
        "google_translate": {
            "credentials_file": "./google_credentials.json",
            "location": "global",
            "batch_size": 5000,
        },
        "microsoft_translator": {
            "api_key": os.getenv("MS_TRANSLATOR_KEY"),
            "location": "global",
            "batch_size": 5000,
        },
        "media_extensions": {
            "audio": [".mp3", ".wav", ".m4a", ".aac", ".flac"],
            "video": [".mp4", ".avi", ".mov", ".mkv", ".webm"],
        },
    }

    if config_file and Path(config_file).exists():
        try:
            with open(config_file, "r") as fp:
                loaded = yaml.safe_load(fp) if config_file.lower().endswith((".yml", ".yaml")) else json.load(fp)
            # Merge with default_config (nested‑dict aware)
            for k, v in loaded.items():
                if isinstance(v, dict) and isinstance(default_config.get(k), dict):
                    default_config[k].update(v)
                else:
                    default_config[k] = v
            logger.info("Configuration loaded from %s", config_file)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load config %s: %s", config_file, exc)
            logger.info("Falling back to defaults")
    return default_config

# ---------------------------------------------------------------------------
# Core workers
# ---------------------------------------------------------------------------

def _select_files(db: DatabaseManager, statuses: Tuple[str, ...], limit: int) -> List[Dict[str, Any]]:
    placeholders = ",".join(["?"] * len(statuses))
    query = f"""
        SELECT m.file_id, m.original_path, m.safe_filename, m.file_size, m.duration, m.media_type
        FROM media_files m
        JOIN processing_status p ON m.file_id = p.file_id
        WHERE p.transcription_status IN ({placeholders})
        ORDER BY m.file_size ASC
        LIMIT ?
    """
    params: Tuple[Any, ...] = (*statuses, limit)
    return db.execute_query(query, params)

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Extract audio and transcribe media files that are new or previously failed")
    parser.add_argument("--file-id", type=str, help="Process a specific file regardless of current status")
    parser.add_argument("--status", choices=["not_started", "failed", "all"], default="not_started", help="Which transcription_status rows to pick when --file-id is not supplied")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of rows to consider (default 1000)")
    parser.add_argument("--batch-size", type=int, default=10, help="How many files to process concurrently in one batch")
    parser.add_argument("--config", type=str, help="Optional YAML/JSON config file")
    parser.add_argument("--dry-run", action="store_true", help="List targets without any processing")
    args = parser.parse_args()

    cfg = _load_config(args.config)

    db = DatabaseManager(cfg.get("database_file", "media_tracking.db"))
    file_mgr = FileManager(db, cfg)
    trans_mgr = TranscriptionManager(db, cfg)
    trans_mgr.set_file_manager(file_mgr)

    # ---------------------------------------------------------------------
    # Single‑file short‑circuit
    # ---------------------------------------------------------------------
    if args.file_id:
        _process_single_file(args.file_id, db, file_mgr, trans_mgr)
        return

    # ---------------------------------------------------------------------
    # Bulk selection based on --status
    # ---------------------------------------------------------------------
    statuses: Tuple[str, ...]
    if args.status == "all":
        statuses = ("not_started", "failed")
    else:
        statuses = (args.status,)

    targets = _select_files(db, statuses, args.limit)
    total_files = len(targets)
    logger.info("Found %s files (status=%s) to process", total_files, ",".join(statuses))

    if total_files == 0:
        logger.info("Nothing to do – exiting")
        return

    if args.dry_run:
        for i, row in enumerate(targets, 1):
            size_mb = (row["file_size"] or 0) / (1024 * 1024)
            logger.info("[%d/%d] %s (%.2f MB)", i, total_files, row["original_path"], size_mb)
        logger.info("--dry-run complete; no changes made")
        return

    # ---------------------------------------------------------------------
    # Batch loop
    # ---------------------------------------------------------------------
    batch_size = max(1, min(args.batch_size, total_files))
    num_batches = (total_files + batch_size - 1) // batch_size

    overall_ok = 0
    overall_fail = 0
    start_time = time.time()

    avg_extract = 30
    avg_transcribe = 60
    total_eta = total_files * (avg_extract + avg_transcribe)
    logger.info("Estimated total time: %s", datetime.timedelta(seconds=total_eta))

    with tqdm(total=total_files, desc="Overall", unit="file") as overall_pb:
        for b in range(num_batches):
            batch_rows = targets[b * batch_size : (b + 1) * batch_size]
            logger.info("Batch %d/%d – %d files", b + 1, num_batches, len(batch_rows))
            batch_ok = batch_fail = 0

            with tqdm(total=len(batch_rows), desc=f"Batch {b + 1}", unit="file", leave=False) as batch_pb:
                for idx, row in enumerate(batch_rows, 1):
                    file_id = row["file_id"]
                    media_type = row["media_type"]
                    size_mb = (row["file_size"] or 0) / (1024 * 1024)
                    short_name = os.path.basename(row["original_path"])
                    if len(short_name) > 30:
                        short_name = short_name[:27] + "..."
                    batch_pb.set_postfix_str(f"{short_name} ({size_mb:.2f} MB)")

                    # Reset processing_status so downstream modules behave consistently
                    db.update_status(file_id=file_id, status="pending", transcription_status="not_started")

                    # -----------------------------------------------------------------
                    # Audio extraction
                    # -----------------------------------------------------------------
                    try:
                        extraction_ok: bool
                        if media_type == "audio":
                            logger.info("%s is audio; skipping extraction", file_id)
                            extraction_ok = True
                        else:
                            extraction_ok = file_mgr.extract_audio_from_video(file_id)

                        if not extraction_ok:
                            logger.error("Audio extraction failed for %s", file_id)
                            batch_fail += 1
                            _advance_progress(batch_pb, overall_pb)
                            continue
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Extraction exception for %s: %s", file_id, exc)
                        batch_fail += 1
                        _advance_progress(batch_pb, overall_pb)
                        continue

                    # -----------------------------------------------------------------
                    # Transcription
                    # -----------------------------------------------------------------
                    audio_path = file_mgr.get_audio_path(file_id) if media_type != "audio" else row["original_path"]
                    if not audio_path or not os.path.exists(audio_path):
                        logger.error("Audio file not found for %s", file_id)
                        batch_fail += 1
                        _advance_progress(batch_pb, overall_pb)
                        continue

                    try:
                        if trans_mgr.transcribe_audio(file_id, audio_path, row):
                            logger.info("Transcription OK for %s", file_id)
                            db.clear_file_errors(file_id)
                            batch_ok += 1
                        else:
                            logger.error("Transcription failed for %s", file_id)
                            batch_fail += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Transcription exception for %s: %s", file_id, exc)
                        batch_fail += 1

                    _advance_progress(batch_pb, overall_pb)

            overall_ok += batch_ok
            overall_fail += batch_fail
            logger.info("Batch %d done – success %d, failed %d", b + 1, batch_ok, batch_fail)

    elapsed = time.time() - start_time
    success_rate = overall_ok * 100 / max(1, overall_ok + overall_fail)
    logger.info("All done – OK %d, Fail %d (%.2f%%)", overall_ok, overall_fail, success_rate)
    logger.info("Total time: %s", datetime.timedelta(seconds=int(elapsed)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _advance_progress(batch_pb: "tqdm", overall_pb: "tqdm") -> None:  # noqa: D401
    """Tick both progress bars once."""
    batch_pb.update(1)
    overall_pb.update(1)


def _process_single_file(file_id: str, db: DatabaseManager, file_mgr: FileManager, trans_mgr: TranscriptionManager) -> None:  # noqa: C901
    info = db.get_file_status(file_id)
    if not info:
        logger.error("File %s not found in database", file_id)
        return

    logger.info("Processing single file %s", file_id)

    # Reset status so downstream pipeline behaves as expected
    db.update_status(file_id=file_id, status="pending", transcription_status="not_started")

    # Extraction (skip when already audio)
    extraction_ok = True
    if info["media_type"] != "audio":
        extraction_ok = file_mgr.extract_audio_from_video(file_id)
        if not extraction_ok:
            logger.error("Audio extraction failed for %s", file_id)
            return

    audio_path = file_mgr.get_audio_path(file_id) if info["media_type"] != "audio" else info["original_path"]
    if not audio_path or not os.path.exists(audio_path):
        logger.error("Audio path missing for %s", file_id)
        return

    if trans_mgr.transcribe_audio(file_id, audio_path, info):
        logger.info("Transcription completed for %s", file_id)
        db.clear_file_errors(file_id)
    else:
        logger.error("Transcription failed for %s", file_id)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
