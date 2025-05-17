#!/usr/bin/env python3
"""
Temporary script to run English quality evaluation
"""
import sys
import logging
import json
import os
from db_manager import DatabaseManager

# Import directly from the scripts module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
try:
    from evaluate_english_quality import evaluate as eval_english
except ImportError as e:
    print(f"Error importing English evaluator: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Get completed English translations
db = DatabaseManager("media_tracking.db")
rows = db.execute_query(
    "SELECT file_id FROM processing_status WHERE translation_en_status = ? AND transcription_status = ? LIMIT 3",
    ("completed", "completed"),
)
fids = [r["file_id"] for r in rows]

# Evaluate each file
for fid in fids:
    try:
        logger.info(f"Evaluating English translation for file {fid}")
        result = eval_english(fid, "gpt-4.1")
        score = result.get("score_0_to_10")
        issues = result.get("issues", [])
        comment = result.get("overall_comment", "")
        
        # Log the result
        logger.info(f"Score: {score}/10, Issues: {issues}")
        logger.info(f"Comment: {comment}")
        
        # Save to database
        status = "qa_completed" if score >= 8.5 else "qa_failed"
        db.add_quality_evaluation(fid, "en", "gpt-4.1", score, issues, comment)
        db.update_translation_status(fid, "en", status)
        logger.info(f"Updated database: {fid}[en] → score {score} → {status}")
        
    except Exception as e:
        logger.error(f"Error evaluating {fid} [en]: {e}")

logging.info("English quality evaluation complete!")