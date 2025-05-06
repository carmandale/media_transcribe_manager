#!/usr/bin/env python3
"""
Parallel Translation Processor

This script processes multiple files for translation in parallel,
significantly speeding up the processing of translations.

Usage:
    python parallel_translation.py [--language LANG] [--workers N] [--batch-size N]

Languages:
    - en: English
    - de: German 
    - he: Hebrew
"""

import os
import sys
import time
import logging
import argparse
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple

from db_manager import DatabaseManager
from file_manager import FileManager
from translation import TranslationManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('parallel_translation.log')
    ]
)

logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables and verify API keys are set."""
    # Try to load from .env file if available
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            import dotenv
            dotenv.load_dotenv(env_path)
            logger.info("Loaded environment from .env file")
        except ImportError:
            logger.warning("dotenv not available, using defaults")
    
    # Check if required keys are set based on target language
    if 'en' in sys.argv or 'de' in sys.argv:
        api_key = os.getenv('DEEPL_API_KEY')
        if not api_key:
            logger.error("DEEPL_API_KEY not found in environment")
            logger.error("Required for English/German translation")
            return False
        logger.info(f"DeepL API key loaded: {api_key[:5]}...{api_key[-5:]}")
        
    if 'he' in sys.argv:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment")
            logger.error("Required for Hebrew translation")
            return False
        logger.info(f"OpenAI API key loaded: {api_key[:5]}...{api_key[-5:]}")
        
    return True

def get_files_for_translation(db: DatabaseManager, language: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get files that need translation in a specific language."""
    status_field = f"translation_{language}_status"
    
    # Start by finding files that need translation
    query = f"""
    SELECT p.*, m.* 
    FROM processing_status p
    JOIN media_files m ON p.file_id = m.file_id
    WHERE p.{status_field} IN ('not_started', 'failed') 
    AND p.transcription_status = 'completed'
    ORDER BY p.file_id
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    candidate_files = db.execute_query(query)
    
    # Add debug logging
    logger.info(f"Translation query for {language}: found {len(candidate_files)} candidate files")
    
    # Filter to only include files that have transcript files available
    config = {
        'output_directory': './output',
    }
    file_manager = FileManager(db, config)
    
    valid_files = []
    for file in candidate_files:
        transcript_path = file_manager.get_transcript_path(file['file_id'])
        if os.path.exists(transcript_path):
            valid_files.append(file)
        else:
            logger.warning(f"File {file['file_id']} needs translation but transcript file not found at {transcript_path}")
    
    logger.info(f"Translation for {language}: {len(valid_files)} files have valid transcripts available")
    
    return valid_files

def translate_single_file(file: Dict[str, Any], language: str, db: DatabaseManager, 
                         file_manager: FileManager, translation_manager: TranslationManager) -> bool:
    """Process a single file for translation."""
    file_id = file['file_id']
    
    logger.info(f"Processing {language} translation for file: {file_id}")
    
    # Verify transcript exists
    transcript_path = file_manager.get_transcript_path(file_id)
    if not os.path.exists(transcript_path):
        logger.error(f"Transcript not found for {file_id} at {transcript_path}")
        # Update the status in the database to show this file as failed
        db.update_translation_status(file_id, language, 'failed')
        db.log_error(file_id, f"translation_{language}", 
                     f"Missing transcript file for {language} translation",
                     f"Transcript file not found at: {transcript_path}")
        return False
    
    # Translate text
    start_time = time.time()
    success = translation_manager.translate_file(
        file_id=file_id,
        target_language=language
    )
    
    elapsed = time.time() - start_time
    if success:
        logger.info(f"Successfully translated {file_id} to {language} in {elapsed:.2f} seconds")
        
        # Verify translation exists
        translation_path = file_manager.get_translation_path(file_id, language)
        if os.path.exists(translation_path):
            logger.info(f"Translation created at: {translation_path} "
                       f"({os.path.getsize(translation_path)} bytes)")
        else:
            logger.warning(f"Translation marked successful but file not found at: {translation_path}")
    else:
        logger.error(f"Failed to translate {file_id} to {language} after {elapsed:.2f} seconds")
    
    return success

def process_files_parallel(files: List[Dict[str, Any]], language: str, max_workers: int, 
                          db: DatabaseManager) -> Tuple[int, int]:
    """Process files in parallel using a thread pool."""
    config = {
        'output_directory': './output',
        'elevenlabs': {
            'api_key': os.getenv('ELEVENLABS_API_KEY')
        },
        'deepl': {
            'api_key': os.getenv('DEEPL_API_KEY'),
            'formality': 'default',
            'batch_size': 5000
        },
        'openai': {
            'api_key': os.getenv('OPENAI_API_KEY')
        },
        'quality_threshold': 8.0
    }
    
    # Create shared file manager
    file_manager = FileManager(db, config)
    
    # Track statistics
    processed_count = 0
    success_count = 0
    error_count = 0
    
    # Process in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks
        futures = []
        
        for file in files:
            # Create a dedicated translation manager for each file
            # This avoids sharing the same manager across threads
            translation_manager = TranslationManager(db, config)
            # Set file_manager - transcription_manager can be None since we won't need it for translation
            translation_manager.file_manager = file_manager
            
            # Submit task to executor
            future = executor.submit(
                translate_single_file, 
                file=file,
                language=language,
                db=db,
                file_manager=file_manager,
                translation_manager=translation_manager
            )
            futures.append(future)
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            processed_count += 1
            try:
                success = future.result()
                if success:
                    success_count += 1
                else:
                    error_count += 1
                
                logger.info(f"Progress: {processed_count}/{len(files)} files processed. "
                           f"Success: {success_count}, Errors: {error_count}")
            except Exception as e:
                error_count += 1
                logger.error(f"Exception during processing: {e}")
    
    return success_count, error_count

def main():
    parser = argparse.ArgumentParser(description="Process files for translation in parallel")
    parser.add_argument("--language", choices=['en', 'de', 'he'], required=True,
                        help="Target language for translation")
    parser.add_argument("--workers", type=int, default=5, 
                        help="Maximum number of concurrent workers (default: 5)")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Number of files to process (default: all pending files)")
    args = parser.parse_args()
    
    # Verify environment is set up correctly
    if not load_environment():
        logger.error("Failed to load environment variables")
        return 1
    
    # Connect to database
    db = DatabaseManager('media_tracking.db')
    
    # Get files for translation
    files = get_files_for_translation(db, args.language, args.batch_size)
    if not files:
        logger.info(f"No files found for {args.language} translation")
        return 0
    
    logger.info(f"Found {len(files)} files for {args.language} translation")
    
    # Process files in parallel
    start_time = time.time()
    success_count, error_count = process_files_parallel(
        files, args.language, args.workers, db
    )
    elapsed = time.time() - start_time
    
    logger.info(f"Completed in {elapsed:.2f} seconds")
    logger.info(f"Success: {success_count}, Errors: {error_count}")
    
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())