#!/usr/bin/env python3
"""
A simple script to evaluate historical accuracy of translations.
"""
import os
import sys
import openai
import logging
from pathlib import Path
from db_manager import DatabaseManager
from file_manager import FileManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("historical-eval")

# Check if API key is set
if not os.getenv("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY not set. Please set it in your environment.")
    sys.exit(1)

# Initialize managers
db = DatabaseManager("media_tracking.db")
fm = FileManager(db, {"output_directory": "./output"})

# Choose a language to evaluate
LANGUAGE = "en"  # Options: en, de, he
MAX_FILES = 3

def get_completed_files():
    """Get files with completed translations."""
    status_field = f"translation_{LANGUAGE}_status"
    query = f"SELECT file_id FROM processing_status WHERE {status_field} = ? LIMIT ?"
    rows = db.execute_query(query, ("completed", MAX_FILES))
    return [row["file_id"] for row in rows]

def read_file_text(path, max_chars=2000):
    """Read text from a file with truncation."""
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

def evaluate_historical_accuracy(original, translation):
    """Evaluate historical accuracy using simplified prompt."""
    prompt = f"""
As a bilingual historian specializing in oral histories, evaluate how well this translation preserves the historical content and speech characteristics of the original text.

EVALUATION CRITERIA:
1. Content accuracy (10 = perfect preservation of all facts, names, dates; 1 = major factual losses)
2. Speech pattern preservation (10 = perfectly maintains the speaker's voice; 1 = completely sanitized)
3. Overall historical fidelity (10 = historically reliable; 1 = historically unreliable)

Original text:
{original}

Translation:
{translation}

Rate each criterion with a number 1-10 and provide a brief justification for each score.
Then provide an overall assessment of whether this translation would be suitable for historical research.
"""
    
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    return response.choices[0].message.content

# Main evaluation loop
file_ids = get_completed_files()
logger.info(f"Evaluating {len(file_ids)} files for {LANGUAGE} historical accuracy")

for file_id in file_ids:
    logger.info(f"Evaluating {file_id}")
    
    # Get file paths
    orig_path = fm.get_transcript_path(file_id)
    trans_path = fm.get_translation_path(file_id, LANGUAGE)
    
    if not orig_path or not os.path.exists(orig_path):
        logger.error(f"Original transcript not found for {file_id}")
        continue
        
    if not trans_path or not os.path.exists(trans_path):
        logger.error(f"Translation not found for {file_id}")
        continue
    
    # Read file contents
    original = read_file_text(orig_path)
    translation = read_file_text(trans_path)
    
    if not original or not translation:
        logger.error(f"Failed to read files for {file_id}")
        continue
    
    # Evaluate
    try:
        result = evaluate_historical_accuracy(original, translation)
        logger.info(f"\nHISTORICAL EVALUATION for {file_id}:\n{result}\n")
    except Exception as e:
        logger.error(f"Error during evaluation: {e}")

logger.info("Evaluation complete!")