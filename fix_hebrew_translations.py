#!/usr/bin/env python3
"""
Fix Hebrew Translations

This script is designed to fix the Hebrew translation issues in the project:
1. Identify translations that have the placeholder [HEBREW TRANSLATION] pattern
2. Properly translate them using OpenAI's translation with the Hebrew glossary
3. Apply RTL formatting and fixes to the resulting translations
4. Update the database with the fixed translations

Usage:
python fix_hebrew_translations.py [--batch-size N] [--dry-run]
"""

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("hebrew-fixer")

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db_manager import DatabaseManager
from translation import TranslationManager
from file_manager import FileManager
from transcription import TranscriptionManager


def get_files_with_placeholder(db: DatabaseManager, limit: Optional[int] = None) -> List[str]:
    """
    Get list of file IDs that have placeholder Hebrew translations.
    
    Args:
        db: Database manager instance
        limit: Optional limit for the number of files to process
        
    Returns:
        List of file IDs that need fixing
    """
    query = """
    SELECT file_id 
    FROM processing_status 
    WHERE translation_he_status = 'completed'
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    rows = db.execute_query(query)
    file_ids = []
    # Extract file_id from rows, accounting for possible structure differences
    for row in rows:
        if isinstance(row, dict) and 'file_id' in row:
            file_ids.append(row['file_id'])
        elif isinstance(row, (list, tuple)) and len(row) > 0:
            file_ids.append(row[0])
        elif hasattr(row, 'file_id'):
            file_ids.append(row.file_id)
    
    # Filter to files that actually have the placeholder
    result = []
    for file_id in file_ids:
        # Find Hebrew translation file
        he_file = list(Path("./output/translations/he").glob(f"{file_id}*_he.txt"))
        if not he_file:
            continue
            
        # Check if file has placeholder
        try:
            with open(he_file[0], 'r', encoding='utf-8') as f:
                content = f.read(100)  # Just read the beginning
                if "[HEBREW TRANSLATION]" in content:
                    result.append(file_id)
        except Exception as e:
            logger.error(f"Error reading {file_id}: {e}")
    
    return result


def fix_hebrew_translation(
    file_id: str,
    translation_manager: TranslationManager,
    db: DatabaseManager,
    dry_run: bool = False
) -> bool:
    """
    Fix a single Hebrew translation file by properly translating it.
    
    Args:
        file_id: The file ID to process
        translation_manager: Translation manager instance
        db: Database manager instance
        dry_run: If True, only show what would be done
        
    Returns:
        True if successful, False otherwise
    """
    # Find the Hebrew translation file
    he_file_path = list(Path("./output/translations/he").glob(f"{file_id}*_he.txt"))
    if not he_file_path:
        logger.error(f"No Hebrew translation file found for {file_id}")
        return False
    
    he_file_path = he_file_path[0]
    
    # Find the source transcript or translation
    transcript_path = None
    # First look for English translation
    en_path = list(Path("./output/translations/en").glob(f"{file_id}*_en.txt"))
    if en_path:
        transcript_path = en_path[0]
    else:
        # Look for German translation
        de_path = list(Path("./output/translations/de").glob(f"{file_id}*_de.txt"))
        if de_path:
            transcript_path = de_path[0]
        else:
            # Fall back to original transcript
            orig_path = list(Path("./output/transcripts").glob(f"{file_id}*.txt"))
            if orig_path:
                transcript_path = orig_path[0]
    
    if not transcript_path:
        logger.error(f"No source transcript or translation found for {file_id}")
        return False
    
    try:
        # Read the source text
        with open(transcript_path, 'r', encoding='utf-8') as f:
            source_text = f.read()
        
        # Read current Hebrew text to check for placeholder
        with open(he_file_path, 'r', encoding='utf-8') as f:
            current_hebrew = f.read()
        
        if "[HEBREW TRANSLATION]" not in current_hebrew:
            logger.info(f"File {file_id} does not have placeholder text, skipping")
            return True
        
        # Extract just the text part
        current_text = current_hebrew.replace("[HEBREW TRANSLATION]", "").strip()
        
        if dry_run:
            logger.info(f"Would translate {file_id} to Hebrew (dry run)")
            return True
        
        # Determine source language
        source_lang = "en"
        if transcript_path.name.endswith("_de.txt"):
            source_lang = "de"
        elif "transcripts" in str(transcript_path):
            # For original transcripts, check DB for detected language
            lang_row = db.execute_query(
                "SELECT detected_language FROM media_files WHERE file_id = ?",
                (file_id,)
            )
            if lang_row and lang_row[0][0]:
                source_lang = lang_row[0][0]
        
        # Use OpenAI directly for translation
        logger.info(f"Translating {file_id} from {source_lang} to Hebrew using OpenAI")
        translated = translation_manager.translate_text(
            text=source_text,
            target_language="he",
            source_language=source_lang,
            provider="openai"
        )
        
        if not translated:
            logger.error(f"OpenAI translation failed for {file_id}")
            return False
        
        # Apply additional Hebrew polish with GPT
        polished = translation_manager._polish_hebrew_with_gpt(source_text, translated)
        if polished:
            translated = polished
        
        # Write the properly translated text
        with open(he_file_path, 'w', encoding='utf-8') as f:
            f.write(translated)
        
        # Update the subtitle file if it exists
        srt_path = Path(str(he_file_path).replace('/translations/', '/subtitles/').replace('_he.txt', '_he.srt'))
        if srt_path.exists():
            # Create subtitle content from the translation
            transcript_manager = translation_manager.transcription_manager
            orig_srt_content = transcript_manager.get_subtitle_from_file(str(transcript_path))
            
            if orig_srt_content:
                # Replace subtitle text with translated text
                he_srt_content = transcript_manager.create_translated_subtitle(
                    original_srt=orig_srt_content,
                    translated_text=translated
                )
                
                # Write the updated subtitle file
                with open(srt_path, 'w', encoding='utf-8') as f:
                    f.write(he_srt_content)
        
        # Update database status
        db.execute_query(
            "UPDATE quality_evaluations SET score = NULL WHERE file_id = ? AND language = 'he'",
            (file_id,)
        )
        
        db.execute_query(
            "UPDATE processing_status SET translation_he_status = 'completed' WHERE file_id = ?",
            (file_id,)
        )
        
        logger.info(f"Successfully fixed Hebrew translation for {file_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error fixing Hebrew translation for {file_id}: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fix Hebrew translations with placeholders")
    parser.add_argument("--batch-size", type=int, default=20, 
                        help="Number of files to process (default: 20)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be fixed without making changes")
    parser.add_argument("--db-path", type=str, default="media_tracking.db",
                        help="Path to the database file (default: media_tracking.db)")
    args = parser.parse_args()
    
    # Initialize DB
    db = DatabaseManager(args.db_path)
    
    # Create config with all required settings
    config = {
        "translation": {
            "default_provider": "openai",
            "providers": ["openai", "deepl"]
        },
        "output_directory": "./output",
        "media_extensions": {
            "audio": [".mp3", ".wav", ".m4a", ".aac", ".flac"],
            "video": [".mp4", ".mov", ".avi", ".mkv"]
        },
        "extract_audio_format": "mp3",
        "extract_audio_quality": "192k",
        "checksum_alg": "sha256"
    }
    
    # Initialize managers
    file_manager = FileManager(db, config)
    transcription_manager = TranscriptionManager(db, config)
    translation_manager = TranslationManager(db, config)
    
    # Set up references between managers
    translation_manager.set_managers(file_manager, transcription_manager)
    transcription_manager.set_file_manager(file_manager)
    
    # Find files with placeholder translations
    file_ids = get_files_with_placeholder(db, args.batch_size)
    if not file_ids:
        logger.info("No files found with Hebrew translation placeholders")
        return
    
    logger.info(f"Found {len(file_ids)} files with placeholder Hebrew translations")
    
    # Process files
    success_count = 0
    fail_count = 0
    
    for file_id in file_ids:
        if fix_hebrew_translation(file_id, translation_manager, db, args.dry_run):
            success_count += 1
        else:
            fail_count += 1
        
        # Sleep between API calls to avoid rate limits
        time.sleep(1)
    
    logger.info(f"Processed {len(file_ids)} files: {success_count} succeeded, {fail_count} failed")


if __name__ == "__main__":
    main()