#!/usr/bin/env python3
"""
Process Translations Script for Media Transcription and Translation Tool
-----------------------------------------------------------------------
Processes files with completed transcriptions but missing translations.
Supports batch processing and handles translations for all required languages:
- English
- German
- Hebrew

Special handling: 
- If source is English, ensures German translation is created
- All files should have translations in all three languages
"""

import os
import argparse
import logging
import time
import sys
from typing import List, Dict, Tuple, Optional

from tqdm import tqdm
from dotenv import load_dotenv

from db_manager import DatabaseManager
from file_manager import FileManager
from translation import TranslationManager
from transcription import TranscriptionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('translation_processing.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Process transcribed files for translation.')
    parser.add_argument('--batch-size', type=int, default=10, 
                        help='Number of files to process in each batch')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum number of files to process')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        help='Show what would be done without making changes')
    parser.add_argument('--force', action='store_true', default=False,
                        help='Force reprocessing of files with failed translation status')
    parser.add_argument('--file-id', type=str, default=None,
                        help='Process only the specified file')
    parser.add_argument('--languages', type=str, default='en,de,he',
                        help='Comma-separated list of target languages (default: en,de,he)')
    return parser.parse_args()

def get_files_for_translation(db_manager: DatabaseManager, args) -> List[Dict]:
    """
    Get files that need translation based on the provided arguments.
    
    Args:
        db_manager: Database manager instance
        args: Command line arguments
        
    Returns:
        List of files that need translation
    """
    if args.file_id:
        # Process specific file
        file = db_manager.get_file_by_id(args.file_id)
        if not file:
            logger.error(f"File with ID {args.file_id} not found in database")
            return []
        
        # Proceed regardless of transcription status; TranslationManager will verify
        
        logger.info(f"Processing specific file: {args.file_id}")
        return [file]
    
    # Get files with completed transcriptions (regardless of overall status)
    status_scope = ['completed', 'in-progress']
    if args.force:
        status_scope.append('failed')

    files = db_manager.get_files_by_status(status_scope)

    # Keep only those whose transcription stage is completed
    translation_files = [f for f in files if f.get('transcription_status') == 'completed']
    
    # Filter files based on languages
    target_languages = args.languages.split(',')
    filtered_files = []
    
    for file in translation_files:
        needs_translation = False
        for lang in target_languages:
            status_field = f"translation_{lang}_status"
            current_status = file.get(status_field, 'not_started')

            # Default: queue only items that were never started.
            # With --force we also re‑queue previously failed/in‑progress ones.
            if args.force:
                if current_status != 'completed':
                    needs_translation = True
                    break
            else:
                if current_status == 'not_started':
                    needs_translation = True
                    break
        
        if needs_translation:
            filtered_files.append(file)
    
    logger.info(f"Found {len(filtered_files)} files that need translation")
    
    if args.limit:
        filtered_files = filtered_files[:args.limit]
        logger.info(f"Limited to {len(filtered_files)} files")
    
    return filtered_files

def process_batch(batch: List[Dict], translation_manager: TranslationManager, 
                  target_languages: List[str], dry_run: bool, force: bool) -> Tuple[int, int]:
    """
    Process a batch of files for translation.
    
    Args:
        batch: List of files to process
        translation_manager: Translation manager instance
        target_languages: List of target languages
        dry_run: Whether to perform a dry run
        force: Whether to force reprocessing of files with failed status
        
    Returns:
        Tuple of (success_count, fail_count)
    """
    success_count = 0
    fail_count = 0
    
    for file in tqdm(batch, desc="Translating batch"):
        file_id = file['file_id']
        source_language = file.get('language', 'en')  # Default to English if language not specified
        
        # Handle special case for English source (add German to target languages)
        current_targets = target_languages.copy()
        if source_language.lower() in ['en', 'eng', 'english']:
            if 'de' not in current_targets:
                current_targets.append('de')
            logger.info(f"English source detected for {file_id}, adding German to target languages")
        
        # Skip source language if it's in the targets
        current_targets = [lang for lang in current_targets if lang.lower() != source_language.lower()]
        
        if dry_run:
            logger.info(f"[DRY RUN] Would translate {file_id} from {source_language} to {', '.join(current_targets)}")
            success_count += 1
            continue
        
        try:
            # Process each target language
            file_success = True
            for target_language in current_targets:
                logger.info(f"Translating {file_id} from {source_language} to {target_language}")
                if not translation_manager.translate_file(file_id, target_language, force=force):
                    logger.warning(f"Translation to {target_language} failed for {file_id}")
                    file_success = False
                else:
                    logger.info(f"Translation to {target_language} completed for {file_id}")
            
            if file_success:
                success_count += 1
            else:
                fail_count += 1
                
        except Exception as e:
            logger.error(f"Error processing file {file_id}: {e}")
            fail_count += 1
    
    return success_count, fail_count

def process_translations(translation_manager: TranslationManager, db_manager: DatabaseManager, args):
    """
    Process files for translation based on command line arguments.
    
    Args:
        translation_manager: Translation manager instance
        db_manager: Database manager instance
        args: Command line arguments
    """
    logger.info(f"Starting translation processing with batch size {args.batch_size}")
    
    target_languages = args.languages.split(',')
    logger.info(f"Target languages: {target_languages}")
    
    # Get files that need translation
    files = get_files_for_translation(db_manager, args)
    
    if not files:
        logger.info("No files found that need translation")
        return
    
    logger.info(f"Processing {len(files)} files for translation")
    
    # Process in batches
    total_success = 0
    total_fail = 0
    
    for i in range(0, len(files), args.batch_size):
        batch = files[i:i + args.batch_size]
        logger.info(f"Processing batch {i // args.batch_size + 1}/{(len(files) + args.batch_size - 1) // args.batch_size}")
        
        success, fail = process_batch(
            batch=batch, 
            translation_manager=translation_manager, 
            target_languages=target_languages,
            dry_run=args.dry_run,
            force=args.force
        )
        
        total_success += success
        total_fail += fail
        
        # If not a dry run, wait a bit between batches to avoid overwhelming the API
        if not args.dry_run and i + args.batch_size < len(files):
            logger.info("Waiting 5 seconds before next batch...")
            time.sleep(5)
    
    logger.info(f"Translation processing completed. Success: {total_success}, Failed: {total_fail}")

def main():
    """Main entry point for the script."""
    args = parse_args()
    
    # Initialize managers
    db_manager = DatabaseManager(db_file='./media_tracking.db')
    
    # Load configuration
    config = {
        'output_dir': './output',
        'deepl': {
            'api_key': os.getenv('DEEPL_API_KEY'),
            'formality': 'default'
        },
        'google_translate': {
            'credentials_file': os.getenv('GOOGLE_TRANSLATE_CREDENTIALS')
        },
        'microsoft_translator': {
            'api_key': os.getenv('MS_TRANSLATOR_KEY'),
            'location': os.getenv('MS_TRANSLATOR_LOCATION', 'global')
        }
    }
    
    # Initialize managers properly
    file_manager = FileManager(db_manager, config)
    transcription_manager = TranscriptionManager(db_manager, config)
    translation_manager = TranslationManager(db_manager, config)
    
    # Connect managers
    transcription_manager.set_file_manager(file_manager)
    translation_manager.set_managers(file_manager, transcription_manager)
    
    # Process translations
    process_translations(translation_manager, db_manager, args)

if __name__ == '__main__':
    main()
