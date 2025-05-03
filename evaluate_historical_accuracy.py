#!/usr/bin/env python3
"""
Evaluate historical translation accuracy for interview transcripts.

This script provides a specialized evaluation focused on faithfulness to the original 
historical content rather than written language quality.

Usage:
    python evaluate_historical_accuracy.py --language en --limit 3
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

from db_manager import DatabaseManager
from file_manager import FileManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("historical-evaluator")

# Import OpenAI API
try:
    import openai
except ImportError:
    logger.error("OpenAI package not installed. Please run: pip install openai")
    sys.exit(1)

# Historical accuracy evaluation prompt
HISTORICAL_PROMPT = """
You are a professional historian and linguistic expert specializing in historical interviews and oral histories.

Your task is to evaluate how faithfully a translation captures the original source interview.

EVALUATION CRITERIA:
1. Content Preservation - All historical facts, dates, names, and events must be accurately translated
2. Speech Pattern Preservation - Hesitations, pauses, and natural speech patterns should be preserved when relevant
3. Cultural Context - Cultural references and idioms should be translated appropriately
4. Technical Accuracy - Specialized terminology should be correctly translated

Return a JSON object in this exact format:
{
  "historical_accuracy": <0-10 score>,
  "content_preservation": <0-10 score>,
  "speech_pattern_preservation": <0-10 score>,
  "cultural_context": <0-10 score>,
  "technical_accuracy": <0-10 score>,
  "issues": ["issue 1", "issue 2"],
  "strengths": ["strength 1", "strength 2"],
  "overall_assessment": "<1-2 sentence summary>"
}

Original Text:
<<<
{original}
>>>

Translation:
<<<
{translation}
>>>
"""

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

def evaluate_historical_accuracy(original_text: str, translation_text: str, model: str) -> Dict:
    """Evaluate historical accuracy of a translation compared to the original text."""
    prompt = HISTORICAL_PROMPT.format(
        original=original_text,
        translation=translation_text
    )
    
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

def evaluate_file(file_id: str, language: str, db: DatabaseManager, fm: FileManager, model: str) -> Optional[Dict]:
    """Evaluate a single file's translation for historical accuracy."""
    try:
        # Get the paths to original and translation
        orig_path = fm.get_transcript_path(file_id)
        trans_path = fm.get_translation_path(file_id, language)
        
        if not orig_path or not os.path.exists(orig_path):
            logger.error(f"Original transcript not found for {file_id}")
            return None
            
        if not trans_path or not os.path.exists(trans_path):
            logger.error(f"Translation not found for {file_id} in {language}")
            return None
        
        # Load the texts
        original_text = load_text(Path(orig_path))
        translation_text = load_text(Path(trans_path))
        
        if len(original_text) < 100 or len(translation_text) < 100:
            logger.warning(f"Texts too short for {file_id}")
            return None
        
        # Evaluate the translation
        result = evaluate_historical_accuracy(original_text, translation_text, model)
        
        # Store the result in the database
        if result:
            historical_score = result.get("historical_accuracy", 0)
            content_score = result.get("content_preservation", 0)
            speech_score = result.get("speech_pattern_preservation", 0)
            cultural_score = result.get("cultural_context", 0)
            technical_score = result.get("technical_accuracy", 0)
            
            issues = result.get("issues", [])
            strengths = result.get("strengths", [])
            assessment = result.get("overall_assessment", "")
            
            # Calculate specialized composite score that emphasizes historical accuracy
            composite_score = (
                historical_score * 0.4 +
                content_score * 0.3 +
                speech_score * 0.1 + 
                cultural_score * 0.1 + 
                technical_score * 0.1
            )
            
            # Add combined field for database
            result["composite_score"] = round(composite_score, 1)
            
            # Store evaluation in database
            custom_data = {
                "historical_accuracy": historical_score,
                "content_preservation": content_score,
                "speech_pattern": speech_score,
                "cultural_context": cultural_score,
                "technical_accuracy": technical_score,
                "strengths": strengths,
                "composite_score": result["composite_score"],
            }
            
            # Use the existing quality evaluation table with our specialized results
            db.add_quality_evaluation(
                file_id=file_id,
                language=language,
                model=f"historical-{model}",
                score=historical_score,  # Use historical score as main score
                issues=issues,
                comment=assessment,
                custom_data=json.dumps(custom_data)
            )
            
            # Update status based on composite score
            status = "qa_completed" if composite_score >= 8.5 else "qa_failed"
            db.update_translation_status(file_id, language, status)
            
            return result
        
        return None
        
    except Exception as e:
        logger.error(f"Error evaluating {file_id}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Evaluate historical translation accuracy")
    parser.add_argument("--language", required=True, choices=["en", "de", "he"], 
                        help="Language to evaluate")
    parser.add_argument("--model", default="gpt-4.1", 
                        help="OpenAI model to use (default: gpt-4.1)")
    parser.add_argument("--limit", type=int, default=3,
                        help="Maximum number of files to evaluate (default: 3)")
    parser.add_argument("--threshold", type=float, default=8.5,
                        help="Minimum score for passing (default: 8.5)")
    args = parser.parse_args()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize managers
    db = DatabaseManager("media_tracking.db")
    fm = FileManager(db, {"output_directory": "./output"})
    
    # Get files with completed translations
    status_field = f"translation_{args.language}_status"
    rows = db.execute_query(
        f"SELECT file_id FROM processing_status WHERE {status_field} = ? AND transcription_status = ? LIMIT ?",
        ("completed", "completed", args.limit)
    )
    
    if not rows:
        logger.info(f"No files found with completed {args.language} translations")
        return
    
    file_ids = [row["file_id"] for row in rows]
    logger.info(f"Evaluating {len(file_ids)} files for {args.language} historical accuracy")
    
    success_count = 0
    fail_count = 0
    
    for file_id in file_ids:
        logger.info(f"Evaluating {file_id} [{args.language}]")
        
        result = evaluate_file(file_id, args.language, db, fm, args.model)
        
        if result:
            historical_score = result.get("historical_accuracy", 0)
            composite_score = result.get("composite_score", 0)
            
            logger.info(f"{file_id} [{args.language}] historical accuracy: {historical_score}/10")
            logger.info(f"{file_id} [{args.language}] composite score: {composite_score}/10")
            logger.info(f"Assessment: {result.get('overall_assessment', '')}")
            
            if result.get("issues"):
                logger.info(f"Issues: {', '.join(result.get('issues', []))}")
            
            if result.get("strengths"):
                logger.info(f"Strengths: {', '.join(result.get('strengths', []))}")
            
            success_count += 1
        else:
            logger.error(f"Evaluation failed for {file_id} [{args.language}]")
            fail_count += 1
        
        # Small delay to avoid rate limiting
        time.sleep(1)
    
    logger.info(f"Evaluation completed. Success: {success_count}, Fail: {fail_count}")

if __name__ == "__main__":
    main()