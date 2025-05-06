#!/usr/bin/env python3
"""
Full Translation and Evaluation Pipeline

This script runs the complete translation and evaluation pipeline:
1. Process missing translations for all languages
2. Fix Hebrew translations that have placeholder text
3. Evaluate the quality of translations using historical criteria
4. Generate a comprehensive report 

Usage:
python run_full_pipeline.py [--batch-size N] [--languages LANGS]
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pipeline")

def run_command(cmd: List[str], description: str) -> bool:
    """Run a command and log the result."""
    logger.info(f"Running: {description}")
    logger.info(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        logger.info(f"Success: {description}")
        if result.stdout:
            for line in result.stdout.splitlines():
                if "ERROR" in line or "FAIL" in line:
                    logger.error(line)
                elif "WARNING" in line:
                    logger.warning(line)
                elif "INFO" in line:
                    logger.info(line)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed: {description}")
        logger.error(f"Exit code: {e.returncode}")
        if e.stdout:
            logger.info(f"Output: {e.stdout}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False

def process_translations(languages: List[str], batch_size: int, db_path: str) -> bool:
    """Process missing translations for specified languages."""
    cmd = [
        "python", "process_missing_translations.py",
        "--languages", ",".join(languages),
        "--batch-size", str(batch_size),
        "--db-path", db_path
    ]
    return run_command(cmd, f"Processing translations for {', '.join(languages)}")

def fix_hebrew_translations(batch_size: int, db_path: str) -> bool:
    """Fix Hebrew translations with placeholder text."""
    cmd = [
        "python", "fix_hebrew_translations.py",
        "--batch-size", str(batch_size),
        "--db-path", db_path
    ]
    return run_command(cmd, "Fixing Hebrew translations")

def evaluate_translations(languages: List[str], batch_size: int, db_path: str) -> bool:
    """Evaluate translations for specified languages."""
    success = True
    for lang in languages:
        cmd = [
            "python", "historical_evaluate_quality.py",
            "--language", lang,
            "--limit", str(batch_size),
            "--db-path", db_path
        ]
        if not run_command(cmd, f"Evaluating {lang} translations"):
            success = False
    return success

def generate_report(db_path: str) -> bool:
    """Generate a comprehensive report."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_path = f"reports/processing_summary_{timestamp}.md"
    
    cmd = [
        "python", "generate_report.py",
        "--output", report_path,
        "--summary",
        "--db-path", db_path
    ]
    return run_command(cmd, "Generating processing summary report")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run the full translation and evaluation pipeline")
    parser.add_argument("--batch-size", type=int, default=20, 
                        help="Batch size for processing (default: 20)")
    parser.add_argument("--languages", type=str, default="en,de,he",
                        help="Languages to process (comma-separated, default: en,de,he)")
    parser.add_argument("--skip-translation", action="store_true",
                        help="Skip the translation step")
    parser.add_argument("--skip-hebrew-fix", action="store_true",
                        help="Skip the Hebrew fix step")
    parser.add_argument("--skip-evaluation", action="store_true",
                        help="Skip the evaluation step")
    parser.add_argument("--db-path", type=str, default="media_tracking.db",
                        help="Path to the database file (default: media_tracking.db)")
    args = parser.parse_args()
    
    languages = args.languages.split(",")
    
    # Validate languages
    valid_langs = ["en", "de", "he"]
    for lang in languages:
        if lang not in valid_langs:
            logger.error(f"Invalid language: {lang}. Must be one of {', '.join(valid_langs)}")
            return 1
    
    # Run steps unless skipped
    if not args.skip_translation:
        if not process_translations(languages, args.batch_size, args.db_path):
            logger.warning("Translation processing had issues, continuing with next steps")
    
    if "he" in languages and not args.skip_hebrew_fix:
        if not fix_hebrew_translations(args.batch_size, args.db_path):
            logger.warning("Hebrew fix had issues, continuing with next steps")
    
    if not args.skip_evaluation:
        if not evaluate_translations(languages, args.batch_size, args.db_path):
            logger.warning("Evaluation had issues, continuing with next steps")
    
    # Generate report in all cases
    if not generate_report(args.db_path):
        logger.error("Failed to generate report")
        return 1
    
    logger.info("Pipeline completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())