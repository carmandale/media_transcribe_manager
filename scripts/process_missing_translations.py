#!/usr/bin/env python3
"""
Process Missing Translations

This script identifies files with completed transcriptions but missing translations
in specified languages, then processes them in batches with the option to evaluate
the historical accuracy of the results.

Usage:
    python process_missing_translations.py --languages en,de,he --batch-size 10 --evaluate
"""

import argparse
import logging
import os
import sys
import time
from typing import List, Dict, Any
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager
from core_modules.file_manager import FileManager
from core_modules.translation import TranslationManager
from core_modules.transcription import TranscriptionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('missing-translations')

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Process missing translations")
    parser.add_argument("--languages", default="en,de,he",
                        help="Comma-separated list of languages to process (default: en,de,he)")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Number of files to process in each batch (default: 10)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of files to process overall (default: no limit)")
    parser.add_argument("--evaluate", action="store_true",
                        help="Evaluate historical accuracy after translation")
    parser.add_argument("--provider", choices=["deepl", "microsoft", "google", "openai"],
                        help="Translation provider to use (default: based on config)")
    parser.add_argument("--sleep", type=int, default=2,
                        help="Seconds to sleep between batches (default: 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without processing")
    parser.add_argument("--db-path", type=str, default="media_tracking.db",
                        help="Path to the database file (default: media_tracking.db)")
    
    return parser.parse_args()

def get_missing_translations(db: DatabaseManager, languages: List[str], limit: int = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get files with missing translations for each language.
    
    Returns:
        Dictionary mapping language code to list of files
    """
    results = {}
    
    for language in languages:
        # Get files with completed transcriptions but missing translations in this language
        status_field = f"translation_{language}_status"
        
        # Files with transcription completed but translation not started
        query = f"""
            SELECT file_id, original_path, detected_language
            FROM media_files
            JOIN processing_status USING (file_id)
            WHERE transcription_status = 'completed'
            AND ({status_field} IS NULL OR {status_field} = 'not_started')
        """
        
        rows = db.execute_query(query)
        if limit:
            rows = rows[:limit]
            
        results[language] = rows
        logger.info(f"Found {len(rows)} files with missing {language} translations")
    
    return results

def main():
    """Main entry point."""
    args = parse_args()
    
    # Parse languages
    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    
    # Initialize components
    db = DatabaseManager(args.db_path)
    
    # Load configuration
    config = {
        "output_directory": "./output",
        "database_file": args.db_path,
        "deepl": {
            "api_key": os.getenv("DEEPL_API_KEY"),
            "formality": "default",
            "batch_size": 5000
        },
        "microsoft_translator": {
            "api_key": os.getenv("MS_TRANSLATOR_KEY"),
            "location": "global"
        },
        "default_provider": args.provider
    }
    
    # Initialize managers
    file_manager = FileManager(db, config)
    transcription_manager = TranscriptionManager(db, config)
    translation_manager = TranslationManager(db, config)
    
    # Connect components
    transcription_manager.set_file_manager(file_manager)
    translation_manager.set_managers(file_manager, transcription_manager)
    
    # Get missing translations
    missing = get_missing_translations(db, languages, args.limit)
    
    if args.dry_run:
        # Just display what would be processed
        for language, files in missing.items():
            print(f"\nFiles with missing {language} translations:")
            for i, file in enumerate(files[:args.limit]):
                print(f"{i+1}. {file['file_id']} - {file['original_path']}")
        return
    
    # Process each language
    for language in languages:
        files = missing[language]
        if not files:
            logger.info(f"No missing {language} translations to process")
            continue
        
        logger.info(f"Processing {len(files)} {language} translations in batches of {args.batch_size}")
        
        # Process in batches
        for i in range(0, len(files), args.batch_size):
            batch = files[i:i+args.batch_size]
            logger.info(f"Processing batch {i//args.batch_size + 1} ({len(batch)} files)")
            
            success_count = 0
            fail_count = 0
            
            for file in batch:
                file_id = file['file_id']
                logger.info(f"Translating {file_id} to {language}")
                
                if translation_manager.translate_file(file_id, language, provider=args.provider):
                    success_count += 1
                else:
                    fail_count += 1
            
            logger.info(f"Batch complete: {success_count} success, {fail_count} fail")
            
            # Evaluate batch if requested
            if args.evaluate and success_count > 0:
                logger.info(f"Evaluating {success_count} translations for historical accuracy")
                try:
                    # Run the historical quality evaluation
                    os.system(f"python historical_evaluate_quality.py --language {language} --limit {success_count}")
                except Exception as e:
                    logger.error(f"Error evaluating translations: {e}")
            
            # Sleep between batches to avoid rate limiting
            if i + args.batch_size < len(files):
                logger.info(f"Sleeping for {args.sleep} seconds before next batch")
                time.sleep(args.sleep)
    
    logger.info("All missing translations processing complete!")

if __name__ == "__main__":
    main()