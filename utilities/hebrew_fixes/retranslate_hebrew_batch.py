#!/usr/bin/env python3
"""
Batch re-translate English-in-Hebrew files to achieve score ≥ 9.0
Processes files from english_retranslate.tsv
"""
import os
import sys
import logging
import csv
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import time
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('retranslate_hebrew_batch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add scribe module to path
sys.path.insert(0, str(Path(__file__).parent))

from scribe.database import Database
from scribe.translate import HistoricalTranslator

class HebrewRetranslator:
    def __init__(self):
        self.db = Database()
        self.translator = HistoricalTranslator()
        self.tsv_file = "english_retranslate.tsv"
        self.completed_count = 0
        self.total_count = 0
        
    def read_tsv(self) -> List[Tuple[str, float]]:
        """Read file IDs and scores from TSV"""
        entries = []
        with open(self.tsv_file, 'r') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                entries.append((row['file_id'], float(row['score'])))
        return entries
    
    def write_tsv(self, entries: List[Tuple[str, float]]):
        """Write remaining entries back to TSV"""
        with open(self.tsv_file, 'w') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(['file_id', 'score'])
            for file_id, score in entries:
                writer.writerow([file_id, score])
    
    def create_backup(self, file_path: Path) -> Path:
        """Create timestamped backup of Hebrew file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f'.txt.bak.{timestamp}')
        if file_path.exists():
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
        return backup_path
    
    def translate_file(self, file_id: str) -> bool:
        """Translate a single file to Hebrew"""
        try:
            # Paths
            english_path = Path(f"output/{file_id}/{file_id}.txt")
            hebrew_path = Path(f"output/{file_id}/{file_id}.he.txt")
            
            # Check if English file exists
            if not english_path.exists():
                logger.error(f"English file not found: {english_path}")
                return False
            
            # Create backup of existing Hebrew file
            if hebrew_path.exists():
                self.create_backup(hebrew_path)
            
            # Read English text
            english_text = english_path.read_text(encoding='utf-8')
            logger.info(f"Read English file: {len(english_text)} chars")
            
            # Check if chunking is needed
            if len(english_text) > 40000:
                logger.info(f"File requires chunking ({len(english_text)} chars)")
                hebrew_text = self.translate_chunked(english_text)
            else:
                # Translate entire file
                logger.info("Translating entire file...")
                # Force OpenAI provider for best quality
                hebrew_text = self.translator.translate(
                    english_text,
                    source_language='en',
                    target_language='he',
                    provider='openai'
                )
            
            if not hebrew_text:
                logger.error("Translation returned empty text")
                return False
            
            # Save Hebrew translation
            hebrew_path.write_text(hebrew_text, encoding='utf-8')
            logger.info(f"Saved Hebrew translation: {len(hebrew_text)} chars")
            
            # Delete old evaluation
            self.db.execute_query(
                "DELETE FROM quality_evaluations WHERE file_id = ? AND language = 'he' AND model = 'sanity-check'",
                (file_id,)
            )
            logger.info("Deleted old evaluation record")
            
            # Wait a moment before evaluation
            time.sleep(2)
            
            # Run evaluation
            logger.info("Running evaluation...")
            result = subprocess.run(
                ['uv', 'run', 'python', 'evaluate_hebrew_improved.py', '--limit', '1', '--model', 'gpt-4.5-preview'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Evaluation failed: {result.stderr}")
                return False
            
            # Check score
            score_query = """
                SELECT score FROM quality_evaluations 
                WHERE file_id = ? AND language = 'he' 
                ORDER BY evaluated_at DESC LIMIT 1
            """
            score_result = self.db.execute_query(score_query, (file_id,))
            
            if not score_result:
                logger.error("No evaluation score found")
                return False
            
            score = score_result[0]['score']
            logger.info(f"Evaluation score: {score}/10")
            
            if score >= 9.0:
                logger.info(f"✓ SUCCESS: {file_id} achieved score {score}")
                return True
            else:
                logger.warning(f"Score {score} < 9.0, translation quality insufficient")
                return False
                
        except Exception as e:
            logger.error(f"Error processing {file_id}: {e}")
            return False
    
    def translate_chunked(self, text: str) -> str:
        """Translate text in chunks of ~2000 characters"""
        chunks = []
        current_chunk = []
        current_size = 0
        
        # Split by sentences
        sentences = text.replace('. ', '.|').replace('? ', '?|').replace('! ', '!|').split('|')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if current_size + len(sentence) > 2000 and current_chunk:
                # Process current chunk
                chunk_text = ' '.join(current_chunk)
                chunks.append(chunk_text)
                current_chunk = [sentence]
                current_size = len(sentence)
            else:
                current_chunk.append(sentence)
                current_size += len(sentence) + 1
        
        # Don't forget last chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        logger.info(f"Split into {len(chunks)} chunks")
        
        # Translate each chunk
        hebrew_chunks = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Translating chunk {i+1}/{len(chunks)}...")
            hebrew_chunk = self.translator.translate(
                chunk,
                source_language='en', 
                target_language='he',
                provider='openai'
            )
            if not hebrew_chunk:
                raise Exception(f"Failed to translate chunk {i+1}")
            hebrew_chunks.append(hebrew_chunk)
            time.sleep(1)  # Rate limiting
        
        return ' '.join(hebrew_chunks)
    
    def process_all(self):
        """Process all files in the TSV"""
        entries = self.read_tsv()
        self.total_count = len(entries)
        logger.info(f"Starting batch processing of {self.total_count} files")
        
        while entries:
            file_id, old_score = entries[0]
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {self.completed_count + 1}/{self.total_count}: {file_id}")
            
            success = self.translate_file(file_id)
            
            if success:
                # Remove from list and update TSV
                entries.pop(0)
                self.write_tsv(entries)
                self.completed_count += 1
                logger.info(f"Progress: {self.completed_count}/{self.total_count} completed")
                
                # Show summary every 10 files
                if self.completed_count % 10 == 0:
                    logger.info(f"\n*** PROGRESS SUMMARY: {self.completed_count}/{self.total_count} files completed ***")
                    logger.info(f"*** Remaining: {len(entries)} files ***\n")
            else:
                logger.error(f"Failed to process {file_id}. Stopping for manual intervention.")
                break
            
            # Brief pause between files
            time.sleep(3)
        
        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info(f"FINAL SUMMARY: Completed {self.completed_count}/{self.total_count} files")
        if entries:
            logger.info(f"Remaining files in TSV: {len(entries)}")
        else:
            logger.info("✓ ALL FILES PROCESSED - TSV is empty!")
        

if __name__ == "__main__":
    # Check API key
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not set in environment")
        sys.exit(1)
    
    # Run batch processing
    processor = HebrewRetranslator()
    processor.process_all()