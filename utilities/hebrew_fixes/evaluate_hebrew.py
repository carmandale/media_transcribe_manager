#!/usr/bin/env python3
"""
Simple script to evaluate Hebrew translations
Based on the working evaluation logic from previous commits
"""
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
import sqlite3

# Add scribe module to path
sys.path.insert(0, str(Path(__file__).parent))

from scribe.database import Database
from scribe.evaluate import evaluate_translation

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def evaluate_hebrew_batch(limit: int = 10):
    """Evaluate a batch of Hebrew translations"""
    
    # Initialize database
    db = Database()
    
    # Get unevaluated Hebrew translations
    query = """
        SELECT DISTINCT p.file_id
        FROM processing_status p
        LEFT JOIN quality_evaluations q 
            ON p.file_id = q.file_id AND q.language = 'he'
        WHERE p.translation_he_status = 'completed'
        AND q.eval_id IS NULL
        LIMIT ?
    """
    
    to_evaluate = db.execute_query(query, (limit,))
    
    if not to_evaluate:
        logger.info("No Hebrew translations to evaluate")
        return
    
    logger.info(f"Found {len(to_evaluate)} Hebrew translations to evaluate")
    
    successful = 0
    failed = 0
    
    for file_info in to_evaluate:
        file_id = file_info['file_id']
        
        try:
            # Get file paths
            transcript_path = Path('output') / file_id / f"{file_id}.txt"
            hebrew_path = Path('output') / file_id / f"{file_id}.he.txt"
            
            # Check files exist
            if not transcript_path.exists():
                logger.warning(f"Transcript not found: {transcript_path}")
                failed += 1
                continue
                
            if not hebrew_path.exists():
                logger.warning(f"Hebrew translation not found: {hebrew_path}")
                failed += 1
                continue
            
            # Read files
            transcript_text = transcript_path.read_text(encoding='utf-8')
            hebrew_text = hebrew_path.read_text(encoding='utf-8')
            
            # Truncate texts to avoid token limits (roughly 3000 chars each for ~6000 total)
            max_chars = 3000
            if len(transcript_text) > max_chars:
                transcript_text = transcript_text[:max_chars] + "\n[...truncated for evaluation...]"
            if len(hebrew_text) > max_chars:
                hebrew_text = hebrew_text[:max_chars] + "\n[...truncated for evaluation...]"
            
            # Evaluate
            logger.info(f"Evaluating {file_id}...")
            try:
                score, evaluation_results = evaluate_translation(transcript_text, hebrew_text)
            except Exception as eval_error:
                logger.error(f"Evaluation error: {eval_error}")
                logger.debug(f"Transcript length: {len(transcript_text)}, Hebrew length: {len(hebrew_text)}")
                failed += 1
                continue
            
            # Save to database
            conn = db._get_connection()
            insert_query = """
                INSERT INTO quality_evaluations 
                (file_id, language, model, score, issues, comment, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            issues = evaluation_results.get('issues', []) if evaluation_results else []
            comment = evaluation_results.get('feedback', '') if evaluation_results else ''
            
            conn.execute(insert_query, (
                file_id,
                'he',
                'gpt-4',
                score,
                json.dumps(issues, ensure_ascii=False),  # Proper JSON encoding
                comment,
                datetime.now()
            ))
            conn.commit()
            
            logger.info(f"✓ Evaluated {file_id}: {score:.1f}/10")
            successful += 1
            
        except Exception as e:
            logger.error(f"✗ Failed to evaluate {file_id}: {e}")
            failed += 1
    
    # Summary
    logger.info(f"\nEvaluation complete:")
    logger.info(f"  Successful: {successful}")
    logger.info(f"  Failed: {failed}")
    
    # Show current statistics
    conn = db._get_connection()
    stats = conn.execute("""
        SELECT COUNT(*) as count, AVG(score) as avg_score
        FROM quality_evaluations
        WHERE language = 'he'
    """).fetchone()
    
    logger.info(f"\nTotal Hebrew evaluations: {stats[0]}")
    logger.info(f"Average score: {stats[1]:.2f}/10")
    
    remaining = conn.execute("""
        SELECT COUNT(*)
        FROM processing_status p
        LEFT JOIN quality_evaluations q 
            ON p.file_id = q.file_id AND q.language = 'he'
        WHERE p.translation_he_status = 'completed'
        AND q.eval_id IS NULL
    """).fetchone()[0]
    
    logger.info(f"Remaining to evaluate: {remaining}")
    
    db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate Hebrew translations")
    parser.add_argument('--limit', '-l', type=int, default=10, 
                       help='Number of files to evaluate (default: 10)')
    args = parser.parse_args()
    
    # Check API key
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not set in environment")
        sys.exit(1)
    
    evaluate_hebrew_batch(args.limit)