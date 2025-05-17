#!/usr/bin/env python3
"""
Debug script to check why evaluators are failing
"""
import sys
import logging
import json
import os
import traceback
from pathlib import Path
from db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Get a file ID with a completed German translation
db = DatabaseManager("media_tracking.db")
rows = db.execute_query(
    "SELECT file_id FROM processing_status WHERE translation_de_status = ? AND transcription_status = ? LIMIT 1",
    ("completed", "completed"),
)

if not rows:
    logger.error("No files found with completed German translations")
    sys.exit(1)

file_id = rows[0]["file_id"]
logger.info(f"Using file ID: {file_id}")

# Get file paths
base_trans = Path("./output/transcripts")
base_de = Path("./output/translations/de")

# Original transcript
trans_matches = list(base_trans.glob(f"{file_id}*.txt"))
if not trans_matches:
    logger.error(f"No transcript file found for {file_id}")
    sys.exit(1)
src_path = trans_matches[0]

# German translation
de_matches = list(base_de.glob(f"{file_id}*_de.txt"))
if not de_matches:
    logger.error(f"No German translation file found for {file_id}")
    sys.exit(1)
de_path = de_matches[0]

logger.info(f"Found source path: {src_path}")
logger.info(f"Found German path: {de_path}")

# Check file contents
try:
    with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
        src_text = f.read(500)  # Just read a sample
    
    with open(de_path, "r", encoding="utf-8", errors="ignore") as f:
        de_text = f.read(500)  # Just read a sample
    
    logger.info(f"Source text sample: {src_text[:100]}...")
    logger.info(f"German text sample: {de_text[:100]}...")
    
except Exception as e:
    logger.error(f"Error reading files: {e}")
    traceback.print_exc()
    sys.exit(1)

logger.info("File checks completed successfully!")