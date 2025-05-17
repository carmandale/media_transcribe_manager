#!/usr/bin/env python3
"""
Evaluate translation quality using OpenAI's GPT-4 API.

This script identifies files that have completed translations and evaluates them
for quality, giving a score from 0-10 and identifying any issues.

Usage:
    python evaluate_quality_openai.py --language en --limit 3
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import traceback

import pathlib
import sys
# Ensure project root is on Python path for core_modules
script_dir = pathlib.Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))
from core_modules.db_manager import DatabaseManager
from core_modules.file_manager import FileManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("quality-evaluator")

# Load environment variables from .env (do not override existing OS environment)
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
except ImportError:
    logger.warning("python-dotenv not installed; relying on existing environment variables")
# Import OpenAI API
try:
    import openai  # type: ignore
except ImportError:
    logger.error("OpenAI package not installed. Please run: pip install openai")
    sys.exit(1)

# Language prompt templates
PROMPT_TEMPLATES = {
    "en": (
        "You are a professional English linguist and translator. "
        "Evaluate the English text for quality.\n\n"
        "Give a holistic score from 0 (unintelligible) to 10 (publication quality). "
        "Focus on grammar, style, clarity, and naturalness.\n\n"
        "Return a JSON object exactly in this form (no additional keys):\n"
        "{\n  \"score_0_to_10\": <int>,\n  \"issues\": [\"issue 1\", ...],\n  \"overall_comment\": \"<concise summary>\"\n}\n\n"
        "Text to evaluate:\n<<<\n{text}\n>>>"
    ),
    "de": (
        "You are a professional German linguist and translator. "
        "Evaluate the German text for quality.\n\n"
        "Give a holistic score from 0 (unintelligible) to 10 (publication quality). "
        "Focus on grammar, style, clarity, and naturalness.\n\n"
        "Return a JSON object exactly in this form (no additional keys):\n"
        "{\n  \"score_0_to_10\": <int>,\n  \"issues\": [\"issue 1\", ...],\n  \"overall_comment\": \"<concise summary>\"\n}\n\n"
        "Text to evaluate:\n<<<\n{text}\n>>>"
    ),
    "he": (
        "You are a professional Hebrew linguist and translator. "
        "Evaluate the Hebrew text for quality.\n\n"
        "Give a holistic score from 0 (unintelligible) to 10 (publication quality). "
        "Focus on grammar, style, clarity, and naturalness.\n\n"
        "Return a JSON object exactly in this form (no additional keys):\n"
        "{\n  \"score_0_to_10\": <int>,\n  \"issues\": [\"issue 1\", ...],\n  \"overall_comment\": \"<concise summary>\"\n}\n\n"
        "Text to evaluate:\n<<<\n{text}\n>>>"
    )
}

def load_text(path: Path, max_chars: int = 3000) -> str:
    """Load text from file with truncation for very large files."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read(max_chars * 2)  # Read a bit more than we need
        
        if len(text) <= max_chars:
            return text
        
        # Truncate to last complete sentence near max_chars
        cutoff = text.rfind(". ", 0, max_chars)
        if cutoff == -1:
            cutoff = text.rfind(" ", 0, max_chars)
        if cutoff == -1:
            cutoff = max_chars
            
        return text[:cutoff] + "\n[… truncated …]"
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        return "[Error reading file]"

def evaluate_text(text: str, language: str, model: str) -> Dict:
    """Evaluate text quality using OpenAI's GPT API."""
    if language not in PROMPT_TEMPLATES:
        raise ValueError(f"Unsupported language: {language}")
    
    # Safely substitute the text into the prompt template (avoid Python format braces conflicts)
    template = PROMPT_TEMPLATES[language]
    prompt = template.replace('{text}', text)
    
    # Make the API call
    if hasattr(openai, "OpenAI"):
        # New client interface (OpenAI >= 1.0.0)
        client = openai.OpenAI()
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = completion.choices[0].message.content
    else:
        # Legacy client interface
        completion = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = completion.choices[0].message.content
    
    # Process the response to extract the JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try cleaning and parsing again
        try:
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            return json.loads(content)
        except json.JSONDecodeError:
            # Last attempt - search for JSON block
            import re
            m = re.search(r"(\{.*?\})", content, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except:
                    pass
            raise ValueError(f"Could not parse JSON from model response: {content[:100]}...")

def evaluate_file(file_id: str, language: str, model: str, db: DatabaseManager, fm: FileManager) -> Tuple[Optional[Dict], Optional[str]]:
    """Evaluate a single file's translation quality."""
    try:
        # Get translation path
        translation_path = fm.get_translation_path(file_id, language)
        if not translation_path or not os.path.exists(translation_path):
            logger.warning(f"Translation file not found for {file_id} [{language}]")
            return None, f"translation_file_missing"
        
        # Load text
        text = load_text(Path(translation_path))
        if not text or len(text) < 100:
            logger.warning(f"Translation text too short for {file_id} [{language}]")
            return None, f"translation_too_short"
        
        # Evaluate translation
        result = evaluate_text(text, language, model)
        return result, None
        
    except Exception as e:
        logger.error(f"Error evaluating {file_id} [{language}]: {e}")
        traceback.print_exc()
        return None, str(e)

def main():
    parser = argparse.ArgumentParser(description="Evaluate translation quality using OpenAI API")
    parser.add_argument("--language", required=True, choices=["en", "de", "he"], 
                        help="Language to evaluate")
    parser.add_argument("--model", default="gpt-4.1", 
                        help="OpenAI model to use (default: gpt-4.1)")
    parser.add_argument("--limit", type=int, default=3,
                        help="Maximum number of files to evaluate (default: 3)")
    parser.add_argument("--threshold", type=float, default=8.5,
                        help="Minimum score for passing (default: 8.5)")
    parser.add_argument("--db", default="media_tracking.db",
                        help="Path to database (default: media_tracking.db)")
    args = parser.parse_args()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize managers
    db = DatabaseManager(args.db)
    fm = FileManager(db, {"output_directory": "./output"})
    
    # Get files with completed translations
    status_column = f"translation_{args.language}_status"
    rows = db.execute_query(
        f"SELECT file_id FROM processing_status WHERE {status_column} = ? AND transcription_status = ? LIMIT ?",
        ("completed", "completed", args.limit)
    )
    
    if not rows:
        logger.info(f"No files found with completed {args.language} translations")
        return
    
    file_ids = [row["file_id"] for row in rows]
    logger.info(f"Evaluating {len(file_ids)} files for {args.language} translation quality")
    
    success_count = 0
    fail_count = 0
    
    for file_id in file_ids:
        logger.info(f"Evaluating {file_id} [{args.language}]")
        
        result, error = evaluate_file(file_id, args.language, args.model, db, fm)
        
        if result and "score_0_to_10" in result:
            score = result["score_0_to_10"]
            issues = result.get("issues", [])
            comment = result.get("overall_comment", "")
            
            # Determine pass/fail
            status = "qa_completed" if score >= args.threshold else "qa_failed"
            
            # Log result
            logger.info(f"{file_id} [{args.language}] score: {score}/10 → {status}")
            if issues:
                logger.info(f"Issues: {issues}")
            if comment:
                logger.info(f"Comment: {comment}")
            
            # Update database
            db.add_quality_evaluation(file_id, args.language, args.model, score, issues, comment)
            db.update_translation_status(file_id, args.language, status)
            
            success_count += 1
        else:
            logger.error(f"Evaluation failed for {file_id} [{args.language}]: {error}")
            fail_count += 1
        
        # Small delay to avoid rate limiting
        time.sleep(1)
    
    logger.info(f"Evaluation completed. Success: {success_count}, Fail: {fail_count}")

if __name__ == "__main__":
    main()