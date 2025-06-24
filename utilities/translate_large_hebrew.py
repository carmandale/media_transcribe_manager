#!/usr/bin/env python3
"""
Special handler for translating very large Hebrew files that timeout with normal processing.
Splits files into smaller chunks and translates them separately.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from scribe.database import Database
from scribe.translate import HistoricalTranslator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def translate_large_file(file_id: str, chunk_size: int = 10000):
    """Translate a large file by splitting it into smaller chunks."""
    db = Database()
    translator = HistoricalTranslator()
    
    # Get transcript
    transcript_path = Path('output') / file_id / f'{file_id}.txt'
    if not transcript_path.exists():
        logger.error(f"Transcript not found: {transcript_path}")
        return False
    
    transcript = transcript_path.read_text(encoding='utf-8')
    logger.info(f"Transcript size: {len(transcript)} characters")
    
    # Split into smaller chunks
    chunks = []
    for i in range(0, len(transcript), chunk_size):
        chunk = transcript[i:i + chunk_size]
        # Try to break at sentence boundary
        if i + chunk_size < len(transcript) and chunk[-1] not in '.!?':
            # Look for last sentence ending
            for j in range(len(chunk) - 1, max(0, len(chunk) - 500), -1):
                if chunk[j] in '.!?':
                    chunk = chunk[:j + 1]
                    break
        chunks.append(chunk)
    
    logger.info(f"Split into {len(chunks)} chunks")
    
    # Translate each chunk
    translations = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
        try:
            translation = translator.translate(chunk, 'he', source_language='de')
            if translation:
                translations.append(translation)
                logger.info(f"Chunk {i+1} translated successfully")
            else:
                logger.error(f"Chunk {i+1} translation failed")
                return False
        except Exception as e:
            logger.error(f"Error translating chunk {i+1}: {e}")
            return False
    
    # Save combined translation
    output_path = Path('output') / file_id / f'{file_id}_he.txt'
    combined = '\n\n'.join(translations)
    output_path.write_text(combined, encoding='utf-8')
    logger.info(f"Saved translation: {output_path} ({len(combined)} chars)")
    
    # Update database
    db.update_status(file_id, translation_he_status='completed')
    logger.info(f"Updated database status to completed")
    
    return True


if __name__ == '__main__':
    # The two remaining files
    file_ids = [
        '7f248805-e046-4be7-9440-f930cac25a77',
        '32c845e5-3f4f-46f6-a24a-4960e34efeb4'
    ]
    
    for file_id in file_ids:
        logger.info(f"\nProcessing {file_id}")
        success = translate_large_file(file_id, chunk_size=8000)
        if success:
            logger.info(f"Successfully translated {file_id}")
        else:
            logger.error(f"Failed to translate {file_id}")