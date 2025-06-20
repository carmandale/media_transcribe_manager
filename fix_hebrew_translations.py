#!/usr/bin/env python3
"""
Find and retranslate Hebrew files that contain [HEBREW TRANSLATION] placeholders.
"""

import os
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

from scribe.database import Database
from scribe.translate import HistoricalTranslator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def has_placeholder(file_path):
    """Check if a file contains [HEBREW TRANSLATION] placeholder."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(1000)  # Check first 1000 chars
            return '[HEBREW TRANSLATION]' in content
    except Exception:
        return False

def retranslate_hebrew(file_id):
    """Retranslate a file to Hebrew."""
    try:
        # Paths
        output_dir = Path(f'output/{file_id}')
        transcript_path = output_dir / f'{file_id}.txt'
        he_txt_path = output_dir / f'{file_id}.he.txt'
        
        # Check if transcript exists
        if not transcript_path.exists():
            return f"No transcript: {file_id}"
        
        # Read transcript
        with open(transcript_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        
        if not text:
            return f"Empty transcript: {file_id}"
        
        # Translate to Hebrew
        translator = HistoricalTranslator()
        translated = translator.translate(text, target_language='he', source_language='de')
        
        # Check if translation worked
        if '[HEBREW TRANSLATION]' in translated:
            return f"Translation failed - still has placeholder: {file_id}"
        
        # Save translation
        with open(he_txt_path, 'w', encoding='utf-8') as f:
            f.write(translated)
        
        return f"Success: {file_id}"
            
    except Exception as e:
        return f"Error {file_id}: {str(e)}"

def main():
    """Main function to fix Hebrew translations with placeholders."""
    db = Database()
    
    # Get all files marked as having Hebrew translation completed
    completed_files = db.execute_query(
        """
        SELECT file_id 
        FROM processing_status 
        WHERE translation_he_status = 'completed'
        ORDER BY file_id
        """
    )
    
    # Find files that need retranslation
    files_to_process = []
    logger.info("Scanning for Hebrew translations with placeholders...")
    
    for file_record in completed_files:
        file_id = file_record['file_id']
        he_txt_path = Path(f'output/{file_id}/{file_id}.he.txt')
        
        if he_txt_path.exists() and has_placeholder(he_txt_path):
            files_to_process.append(file_id)
    
    logger.info(f"Found {len(files_to_process)} Hebrew translations to fix")
    
    if not files_to_process:
        logger.info("No Hebrew translations need fixing")
        return
    
    # Update database status to pending for these files
    logger.info("Updating database status...")
    for file_id in files_to_process:
        db.update_status(file_id, translation_he_status='pending')
    
    # Process files in parallel
    max_workers = min(10, os.cpu_count() or 1)
    logger.info(f"Processing with {max_workers} workers...")
    
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(retranslate_hebrew, file_id): file_id 
                  for file_id in files_to_process}
        
        with tqdm(total=len(files_to_process), desc="Retranslating to Hebrew") as pbar:
            for future in as_completed(futures):
                file_id = futures[future]
                result = future.result()
                results.append(result)
                pbar.update(1)
                
                # Update database status
                if result.startswith("Success:"):
                    db.update_status(file_id, translation_he_status='completed')
                elif "No transcript" not in result and "Empty transcript" not in result:
                    # Log actual errors
                    logger.error(result)
                    db.update_status(file_id, translation_he_status='failed')
                    db.log_error(file_id, 'translation_he', result)
    
    # Summary
    successful = [r for r in results if r.startswith("Success:")]
    failed = [r for r in results if not r.startswith("Success:")]
    
    logger.info(f"\nRetranslation complete:")
    logger.info(f"  Successful: {len(successful)}")
    logger.info(f"  Failed: {len(failed)}")
    
    if failed:
        logger.info("\nFailed files:")
        for f in failed[:10]:  # Show first 10 failures
            logger.info(f"  {f}")
        if len(failed) > 10:
            logger.info(f"  ... and {len(failed) - 10} more")

if __name__ == "__main__":
    main()