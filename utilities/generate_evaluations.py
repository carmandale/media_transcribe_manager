#!/usr/bin/env python3
"""
Generate quality evaluations for translations.

This script iterates through processed files and generates evaluations
for any translations that have not yet been evaluated.
"""

import json
import logging
import os
from pathlib import Path
import sys
from typing import Dict, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scribe.evaluate import HistoricalEvaluator
from scribe.database import Database
from scribe.utils import find_transcript_file

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EvaluationGenerator:
    """Generates and saves translation evaluations."""

    def __init__(self, output_dir: str = "output", model: str = "gpt-4-turbo"):
        self.output_dir = Path(output_dir)
        self.evaluator = HistoricalEvaluator(model=model)
        self.db = Database()
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("OPENAI_API_KEY environment variable not set.")
            raise ValueError("OPENAI_API_KEY must be set.")

    def run(self, languages: Optional[list] = None, overwrite: bool = False):
        """
        Run the evaluation generation process.

        Args:
            languages: A list of language codes (e.g., ['de', 'en']) to evaluate.
                       If None, evaluates all available languages.
            overwrite: If True, re-evaluate and overwrite existing evaluations.
        """
        if languages is None:
            languages = ['de', 'en', 'he']
        
        media_files = self.db.get_all_files()
        logger.info(f"Found {len(media_files)} media files in the database.")

        for i, media_file in enumerate(media_files):
            file_id = media_file['file_id']
            logger.info(f"Processing file {i+1}/{len(media_files)}: {file_id}")
            
            file_output_dir = self.output_dir / file_id
            if not file_output_dir.exists():
                logger.warning(f"Output directory not found for {file_id}, skipping.")
                continue

            # Find original transcript
            original_transcript_path = find_transcript_file(file_output_dir, file_id)
            if not original_transcript_path:
                logger.warning(f"Original transcript not found for {file_id}, skipping.")
                continue

            evaluations_file = file_output_dir / f"{file_id}.evaluations.json"
            
            # Load existing evaluations
            if evaluations_file.exists() and not overwrite:
                with open(evaluations_file, 'r', encoding='utf-8') as f:
                    try:
                        evaluations = json.load(f)
                    except json.JSONDecodeError:
                        evaluations = {}
            else:
                evaluations = {}

            for lang in languages:
                lang_name = {"de": "german", "en": "english", "he": "hebrew"}.get(lang, lang)
                if lang_name in evaluations and not overwrite:
                    logger.info(f"Skipping {lang} evaluation for {file_id} as it already exists.")
                    continue
                
                translation_path = file_output_dir / f"{file_id}.{lang}.txt"
                if not translation_path.exists():
                    continue

                logger.info(f"Evaluating {lang} translation for {file_id}...")
                
                try:
                    evaluation_result = self.evaluator.evaluate_file(
                        original_path=original_transcript_path,
                        translation_path=translation_path,
                        language=lang,
                        enhanced=True
                    )

                    if evaluation_result:
                        evaluations[lang_name] = evaluation_result
                        logger.info(f"Successfully evaluated {lang} for {file_id}. Score: {evaluation_result.get('composite_score')}")
                    else:
                        logger.error(f"Evaluation failed for {lang} on {file_id}.")

                except Exception as e:
                    logger.critical(f"An unexpected error occurred during evaluation for {file_id} ({lang}): {e}", exc_info=True)

            # Save updated evaluations
            if evaluations:
                with open(evaluations_file, 'w', encoding='utf-8') as f:
                    json.dump(evaluations, f, ensure_ascii=False, indent=4)
                logger.info(f"Saved evaluations to {evaluations_file}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate quality evaluations for translations.")
    parser.add_argument(
        "--lang",
        type=str,
        nargs='+',
        help="Specific language codes to evaluate (e.g., de en). If not provided, all are evaluated."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing evaluation files."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4-turbo",
        help="OpenAI model to use for evaluation."
    )
    
    args = parser.parse_args()

    try:
        generator = EvaluationGenerator(model=args.model)
        generator.run(languages=args.lang, overwrite=args.overwrite)
        logger.info("Evaluation generation complete.")
    except ValueError as e:
        logger.error(e)
        sys.exit(1)
    except Exception as e:
        logger.critical(f"A critical error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 