#!/usr/bin/env python3
"""
Historical Accuracy Evaluation for Interview Translations

This script evaluates translations based on historical accuracy criteria rather than
standard language quality metrics. It is designed specifically for evaluating historical
interview translations where preserving speech patterns and content accuracy are more
important than producing polished text.

Usage:
    python historical_evaluate_quality.py --language en --limit 10

Results are saved to the database and can be queried with:
    SELECT * FROM quality_evaluations WHERE model LIKE 'historical-%';
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from db_manager import DatabaseManager
from file_manager import FileManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("historical-evaluator")

try:
    import openai
except ImportError:
    logger.error("OpenAI package not installed. Run 'pip install openai'")
    sys.exit(1)

HISTORICAL_PROMPT = """
You are a bilingual historian specializing in oral histories and interview transcripts.
Evaluate how well this translation preserves the historical content and speech characteristics of the original.

EVALUATION CRITERIA:
1. Content Accuracy: 1-10 (10 = perfect preservation of all historical facts, names, dates, events)
2. Speech Pattern Fidelity: 1-10 (10 = perfectly maintains the speaker's natural voice, hesitations, filler words)
3. Cultural Context: 1-10 (10 = perfectly preserves cultural references and idioms)
4. Overall Historical Reliability: 1-10 (10 = completely reliable for historical research purposes)

IMPORTANT: Return your evaluation as a JSON object with this exact structure:
{{
  "scores": {{
    "content_accuracy": <number 1-10>,
    "speech_pattern_fidelity": <number 1-10>,
    "cultural_context": <number 1-10>,
    "overall_historical_reliability": <number 1-10>
  }},
  "composite_score": <number 1-10>,
  "strengths": [<list of strengths>],
  "issues": [<list of issues, if any>],
  "suitability": "<statement on suitability for historical research>"
}}

Original text:
{original}

Translation:
{translation}

Be sure to format your response as a strict JSON object with the exact structure specified above.
"""


def load_text(path: Path, max_chars: int = 2500) -> str:
    """Load text from a file with truncation."""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read(max_chars * 2)
        
        if len(text) <= max_chars:
            return text
        
        # Truncate at sentence boundary
        end = text.rfind('.', 0, max_chars)
        if end == -1:
            end = max_chars
        
        return text[:end+1]
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        return None


def evaluate_historical_accuracy(original: str, translation: str, model: str = "gpt-4"):
    """Evaluate historical accuracy using OpenAI."""
    prompt = HISTORICAL_PROMPT.format(
        original=original,
        translation=translation
    )
    
    client = openai.OpenAI()
    try:
        # Try with JSON response format for compatible models
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
    except Exception as e:
        if "response_format" in str(e):
            # Fallback for models that don't support JSON response format
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You must respond with valid JSON only, no other text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
        else:
            raise
    
    try:
        result = json.loads(response.choices[0].message.content)
        # Calculate a weighted composite score if not provided
        if "composite_score" not in result:
            scores = result.get("scores", {})
            result["composite_score"] = round((
                scores.get("content_accuracy", 0) * 0.4 +
                scores.get("speech_pattern_fidelity", 0) * 0.3 +
                scores.get("cultural_context", 0) * 0.15 +
                scores.get("overall_historical_reliability", 0) * 0.15
            ), 1)
        
        return result
    except json.JSONDecodeError:
        logger.error(f"Failed to parse response as JSON: {response.choices[0].message.content[:200]}...")
        return None


def evaluate_file(file_id: str, language: str, db: DatabaseManager, fm: FileManager, model: str = "gpt-4"):
    """Evaluate a single file's translation for historical accuracy."""
    # Get file paths
    orig_path = fm.get_transcript_path(file_id)
    trans_path = fm.get_translation_path(file_id, language)
    
    # If we can't find the transcript, try finding it directly
    if not orig_path or not os.path.exists(orig_path):
        # Look for transcript file in the transcripts directory
        transcript_files = list(Path("./output/transcripts").glob(f"{file_id}*.txt"))
        if transcript_files:
            orig_path = str(transcript_files[0])
            logger.info(f"Found transcript directly: {orig_path}")
        else:
            logger.error(f"Original transcript not found for {file_id}")
            return None
        
    # If we can't find the translation, try finding it directly
    if not trans_path or not os.path.exists(trans_path):
        # Look for translation file in the translations directory
        translation_files = list(Path(f"./output/translations/{language}").glob(f"{file_id}*_{language}.txt"))
        if translation_files:
            trans_path = str(translation_files[0])
            logger.info(f"Found translation directly: {trans_path}")
        else:
            logger.error(f"Translation not found for {file_id}")
            return None
    
    # Read file contents
    original = load_text(Path(orig_path))
    translation = load_text(Path(trans_path))
    
    if not original or not translation:
        logger.error(f"Failed to read files for {file_id}")
        return None
    
    # Evaluate
    try:
        result = evaluate_historical_accuracy(original, translation, model)
        if not result:
            return None
        
        # Store results in database
        scores = result.get("scores", {})
        composite_score = result.get("composite_score", 0)
        issues = result.get("issues", [])
        strengths = result.get("strengths", [])
        suitability = result.get("suitability", "")
        
        # Determine quality status
        status = "qa_completed" if composite_score >= 8.0 else "qa_failed"
        
        # Store in database
        db.add_quality_evaluation(
            file_id=file_id,
            language=language,
            model=f"historical-{model}",
            score=composite_score,
            issues=issues,
            comment=suitability,
            custom_data=json.dumps(scores)
        )
        
        # Update translation status
        db.update_translation_status(file_id, language, status)
        
        logger.info(f"Historical evaluation for {file_id} [{language}]:")
        logger.info(f"  Composite Score: {composite_score}/10")
        logger.info(f"  Content Accuracy: {scores.get('content_accuracy', 'N/A')}/10")
        logger.info(f"  Speech Pattern Fidelity: {scores.get('speech_pattern_fidelity', 'N/A')}/10")
        logger.info(f"  Cultural Context: {scores.get('cultural_context', 'N/A')}/10")
        logger.info(f"  Historical Reliability: {scores.get('overall_historical_reliability', 'N/A')}/10")
        logger.info(f"  Status: {status}")
        
        return result
    except Exception as e:
        logger.error(f"Error evaluating {file_id}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate historical accuracy of translations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--language", required=True, choices=["en", "de", "he"],
                       help="Language to evaluate")
    parser.add_argument("--limit", type=int, default=5,
                       help="Maximum number of files to evaluate (default: 5)")
    parser.add_argument("--model", default="gpt-4",
                       help="OpenAI model to use (default: gpt-4)")
    parser.add_argument("--threshold", type=float, default=8.0,
                       help="Minimum score for passing (default: 8.0)")
    parser.add_argument("--status", default="completed",
                       help="Status filter for files to evaluate (default: completed)")
    args = parser.parse_args()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize managers
    db = DatabaseManager("media_tracking.db")
    fm = FileManager(db, {"output_directory": "./output"})
    
    # Get files to evaluate
    status_field = f"translation_{args.language}_status"
    query = f"""
    SELECT p.file_id 
    FROM processing_status p
    JOIN media_files m ON p.file_id = m.file_id 
    WHERE p.{status_field} = ? 
    AND m.file_id IN (
        SELECT DISTINCT file_id FROM media_files WHERE file_id IN (
            SELECT file_id FROM processing_status WHERE transcription_status = 'completed'
        )
    )
    LIMIT ?
    """
    rows = db.execute_query(query, (args.status, args.limit))
    
    if not rows:
        logger.info(f"No files found with {args.status} {args.language} translations")
        return
    
    file_ids = [row["file_id"] for row in rows]
    logger.info(f"Evaluating {len(file_ids)} files for {args.language} historical accuracy")
    
    success_count = 0
    fail_count = 0
    
    for file_id in file_ids:
        logger.info(f"Processing file {file_id}")
        result = evaluate_file(file_id, args.language, db, fm, args.model)
        
        if result:
            success_count += 1
        else:
            fail_count += 1
        
        # Sleep a bit to avoid rate limiting
        time.sleep(1)
    
    logger.info(f"Evaluation complete! Successful: {success_count}, Failed: {fail_count}")


if __name__ == "__main__":
    main()