#!/usr/bin/env python3
"""
Improved Hebrew evaluation script with:
- GPT-4 Turbo for larger context window
- Sanity check for English text in Hebrew translations
- Better error handling and statistics
"""
import os
import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime
import sqlite3
from collections import Counter

# Add scribe module to path
sys.path.insert(0, str(Path(__file__).parent))

from scribe.database import Database
from scribe.evaluate import evaluate_translation

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Hebrew character detection
def contains_hebrew(text):
    """Check if text contains Hebrew characters"""
    hebrew_pattern = re.compile(r'[\u0590-\u05FF\uFB1D-\uFB4F]')
    return bool(hebrew_pattern.search(text))

def detect_language_ratio(text):
    """Detect ratio of Hebrew vs Latin characters"""
    hebrew_chars = len(re.findall(r'[\u0590-\u05FF\uFB1D-\uFB4F]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    total_alpha = hebrew_chars + latin_chars
    
    if total_alpha == 0:
        return 0.0
    
    return hebrew_chars / total_alpha

def evaluate_hebrew_batch_improved(limit: int = 10, model: str = "gpt-4.1"):
    """
    Evaluate Hebrew translations with improved model and sanity checks
    
    Args:
        limit: Number of files to evaluate
        model: GPT model to use (default: gpt-4-turbo-preview for 128k context)
    """
    
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
    logger.info(f"Using model: {model}")
    
    # Statistics
    successful = 0
    failed = 0
    english_detected = 0
    low_hebrew_ratio = 0
    
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
            
            # Sanity check: Is this actually Hebrew?
            if not contains_hebrew(hebrew_text):
                logger.error(f"❌ {file_id}: No Hebrew characters detected! File appears to be in English.")
                english_detected += 1
                
                # Save with score 0 and note the issue
                conn = db._get_connection()
                insert_query = """
                    INSERT INTO quality_evaluations 
                    (file_id, language, model, score, issues, comment, evaluated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                
                issues = ["NO HEBREW CHARACTERS DETECTED - Translation appears to be in English"]
                comment = "Failed sanity check: No Hebrew characters found in translation"
                
                conn.execute(insert_query, (
                    file_id,
                    'he',
                    'sanity-check',
                    0.0,
                    json.dumps(issues, ensure_ascii=False),
                    comment,
                    datetime.now()
                ))
                conn.commit()
                failed += 1
                continue
            
            # Check Hebrew ratio
            hebrew_ratio = detect_language_ratio(hebrew_text)
            if hebrew_ratio < 0.5:
                logger.warning(f"⚠️  {file_id}: Low Hebrew ratio: {hebrew_ratio:.2%}")
                low_hebrew_ratio += 1
            
            # For newer models, we can use much larger context
            # gpt-4.1, gpt-4.5, gpt-4o, gpt-4-turbo all have 128k context
            # Using 40k chars to stay well within limits while getting good coverage
            max_chars = 40000 if any(x in model for x in ["gpt-4", "turbo"]) else 3000
            
            if len(transcript_text) > max_chars:
                transcript_text = transcript_text[:max_chars] + "\n[...truncated for evaluation...]"
            if len(hebrew_text) > max_chars:
                hebrew_text = hebrew_text[:max_chars] + "\n[...truncated for evaluation...]"
            
            # Evaluate
            logger.info(f"Evaluating {file_id} (Hebrew ratio: {hebrew_ratio:.1%})...")
            try:
                score, evaluation_results = evaluate_translation(transcript_text, hebrew_text, model=model)
            except Exception as eval_error:
                logger.error(f"Evaluation error: {eval_error}")
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
            
            # Add Hebrew ratio to comment
            if hebrew_ratio < 0.8:
                comment += f" [Hebrew character ratio: {hebrew_ratio:.1%}]"
            
            conn.execute(insert_query, (
                file_id,
                'he',
                model,
                score,
                json.dumps(issues, ensure_ascii=False),
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
    logger.info(f"  English files detected: {english_detected}")
    logger.info(f"  Low Hebrew ratio warnings: {low_hebrew_ratio}")
    
    # Show current statistics
    conn = db._get_connection()
    
    # Check for files marked as English
    english_count = conn.execute("""
        SELECT COUNT(*) 
        FROM quality_evaluations 
        WHERE language = 'he' 
        AND model = 'sanity-check'
        AND score = 0.0
    """).fetchone()[0]
    
    if english_count > 0:
        logger.warning(f"\n⚠️  Total files with English instead of Hebrew: {english_count}")
    
    # Overall stats
    stats = conn.execute("""
        SELECT COUNT(*) as count, AVG(score) as avg_score
        FROM quality_evaluations
        WHERE language = 'he'
        AND model != 'sanity-check'
    """).fetchone()
    
    logger.info(f"\nTotal Hebrew evaluations: {stats[0]}")
    logger.info(f"Average score: {stats[1]:.2f}/10")
    
    # Remaining
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
    
    parser = argparse.ArgumentParser(description="Evaluate Hebrew translations with sanity checks")
    parser.add_argument('--limit', '-l', type=int, default=10, 
                       help='Number of files to evaluate (default: 10)')
    parser.add_argument('--model', '-m', type=str, default='gpt-4.1',
                       help='GPT model to use (default: gpt-4.1, alternatives: gpt-4.5-preview, gpt-4.1-mini)')
    args = parser.parse_args()
    
    # Check API key
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not set in environment")
        sys.exit(1)
    
    evaluate_hebrew_batch_improved(args.limit, args.model)