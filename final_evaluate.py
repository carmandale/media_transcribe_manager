#!/usr/bin/env python3
"""
Final script to evaluate translation quality for multiple files
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
import openai
from db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("final-evaluator")

def get_translation_path(file_id, language):
    """Get path to translation file."""
    base_dir = Path(f"./output/translations/{language}")
    # Find translation file that matches file_id
    files = list(base_dir.glob(f"{file_id}*_{language}.txt"))
    if not files:
        return None
    return files[0]

def evaluate_quality(text, language):
    """Evaluate text quality using OpenAI."""
    language_names = {
        "en": "English",
        "de": "German",
        "he": "Hebrew"
    }
    
    lang_name = language_names.get(language, language)
    
    prompt = (
        f"You are a professional {lang_name} linguist and translator. "
        f"Evaluate the following {lang_name} text for quality, grammar, style, and clarity.\n\n"
        f"Give a holistic score from 0 to 10. Return a JSON object with these fields only:\n"
        f"{{\"score_0_to_10\": <int>, \"issues\": [<strings>], \"overall_comment\": <string>}}\n\n"
        f"Text to evaluate:\n{text[:2000]}"
    )
    
    client = openai.OpenAI()
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    result = completion.choices[0].message.content
    
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown
        import re
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', result, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # Try direct regex as last resort
        try:
            match = re.search(r'{\s*"score_0_to_10":\s*(\d+),\s*"issues":\s*\[(.*?)\],\s*"overall_comment":\s*"(.*?)"\s*}', result, re.DOTALL)
            if match:
                score = int(match.group(1))
                issues_text = match.group(2)
                issues = [i.strip().strip('"\'') for i in issues_text.split(",")]
                comment = match.group(3)
                return {
                    "score_0_to_10": score,
                    "issues": issues,
                    "overall_comment": comment
                }
        except:
            pass
            
    logger.error(f"Failed to parse API response: {result[:100]}...")
    return None

def main():
    parser = argparse.ArgumentParser(description="Evaluate translation quality")
    parser.add_argument("--language", required=True, choices=["en", "de", "he"], 
                        help="Language to evaluate")
    parser.add_argument("--limit", type=int, default=3, 
                        help="Maximum number of files to process")
    parser.add_argument("--threshold", type=float, default=8.5,
                        help="Quality threshold (0-10)")
    args = parser.parse_args()
    
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize database
    db = DatabaseManager("./media_tracking.db")
    
    # Get files with completed translations
    query = f"SELECT file_id FROM processing_status WHERE translation_{args.language}_status = ? LIMIT ?"
    rows = db.execute_query(query, ("completed", args.limit))
    
    if not rows:
        logger.info(f"No files found with completed {args.language} translations")
        return
    
    file_ids = [row["file_id"] for row in rows]
    logger.info(f"Evaluating {len(file_ids)} {args.language} translations")
    
    # Evaluate each file
    for file_id in file_ids:
        logger.info(f"Processing {file_id}")
        
        # Get translation file
        trans_path = get_translation_path(file_id, args.language)
        if not trans_path:
            logger.error(f"Translation file not found for {file_id}")
            continue
        
        # Read file
        try:
            with open(trans_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read(3000)  # Read up to 3000 chars
            
            if len(text) < 100:
                logger.warning(f"Translation text too short for {file_id}")
                continue
                
            # Evaluate quality
            result = evaluate_quality(text, args.language)
            
            if not result:
                logger.error(f"Failed to evaluate {file_id}")
                continue
            
            # Extract results
            score = result.get("score_0_to_10")
            issues = result.get("issues", [])
            comment = result.get("overall_comment", "")
            
            logger.info(f"Score: {score}/10")
            if issues:
                logger.info(f"Issues: {', '.join(issues)}")
            logger.info(f"Comment: {comment}")
            
            # Determine status
            status = "qa_completed" if score >= args.threshold else "qa_failed"
            
            # Update database
            db.add_quality_evaluation(file_id, args.language, "gpt-4", score, issues, comment)
            db.update_translation_status(file_id, args.language, status)
            logger.info(f"Updated status to: {status}")
            
        except Exception as e:
            logger.error(f"Error processing {file_id}: {e}")
        
        # Wait to avoid rate limits
        time.sleep(1)
    
    logger.info(f"Evaluation complete for {args.language}")

if __name__ == "__main__":
    main()