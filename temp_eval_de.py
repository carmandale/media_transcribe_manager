#!/usr/bin/env python3
"""
Temporary script to run German quality evaluation
"""
import sys
import logging
import json
import os
from db_manager import DatabaseManager

# Import directly from the scripts module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
try:
    from evaluate_german_quality import evaluate as eval_german
except ImportError as e:
    print(f"Error importing German evaluator: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Get completed German translations
db = DatabaseManager("media_tracking.db")
rows = db.execute_query(
    "SELECT file_id FROM processing_status WHERE translation_de_status = ? AND transcription_status = ? LIMIT 3",
    ("completed", "completed"),
)
fids = [r["file_id"] for r in rows]

# Evaluate each file
for fid in fids:
    try:
        logger.info(f"Evaluating German translation for file {fid}")
        result = eval_german(fid, "gpt-4.1")
        score = result.get("score_0_to_10")
        issues = result.get("issues", [])
        comment = result.get("overall_comment", "")
        
        # Log the result
        logger.info(f"Score: {score}/10, Issues: {issues}")
        logger.info(f"Comment: {comment}")
        
        # Save to database
        status = "qa_completed" if score >= 8.5 else "qa_failed"
        db.add_quality_evaluation(fid, "de", "gpt-4.1", score, issues, comment)
        db.update_translation_status(fid, "de", status)
        logger.info(f"Updated database: {fid}[de] → score {score} → {status}")
        
    except Exception as e:
        logger.error(f"Error evaluating {fid} [de]: {e}")

logging.info("German quality evaluation complete!")