#!/usr/bin/env python3
"""
Script to verify file processing status by checking both database records and actual output files.
This ensures we're only reprocessing files that genuinely need it.
"""

import os
import sqlite3
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StatusVerifier:
    def __init__(self, db_path='media_tracking.db', output_dir='output'):
        self.db_path = db_path
        self.output_dir = output_dir
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Directories
        self.transcript_dir = os.path.join(output_dir, 'transcripts')
        self.translation_en_dir = os.path.join(output_dir, 'translations', 'en')
        self.translation_he_dir = os.path.join(output_dir, 'translations', 'he')
        
        # File completion statistics
        self.stats = {
            'total_files': 0,
            'db_completed': 0,
            'actual_completed': 0,
            'status_fixed': 0,
            'mismatch': 0,
            'missing_output': 0,
        }
    
    def verify_and_fix(self):
        """Main function to verify and fix file status"""
        logger.info("Starting verification process...")
        
        # Get all files marked with all stages completed in the database
        self.cursor.execute("""
        SELECT 
            f.file_id, 
            f.original_path,
            p.status,
            p.transcription_status,
            p.translation_en_status,
            p.translation_he_status
        FROM 
            media_files f
        JOIN 
            processing_status p ON f.file_id = p.file_id
        WHERE 
            p.transcription_status = 'completed' AND
            p.translation_en_status = 'completed' AND
            p.translation_he_status = 'completed'
        """)
        
        rows = self.cursor.fetchall()
        self.stats['total_files'] = self.get_total_file_count()
        self.stats['db_completed'] = len(rows)
        
        logger.info(f"Found {len(rows)} files with all stages marked as completed in database")
        
        # Verify each file has actual output files
        for row in rows:
            file_id = row['file_id']
            original_file = row['original_path']
            current_status = row['status']
            
            has_all_outputs = self.verify_outputs_exist(file_id)
            
            if has_all_outputs:
                self.stats['actual_completed'] += 1
                
                # If status is not already 'completed', update it
                if current_status != 'completed':
                    self.update_status_to_completed(file_id)
                    self.stats['status_fixed'] += 1
                    logger.info(f"Fixed status for file {file_id} ({Path(original_file).name})")
            else:
                self.stats['missing_output'] += 1
                logger.warning(f"File {file_id} ({Path(original_file).name}) is marked as completed but missing output files")
                
        # Commit changes
        self.conn.commit()
        logger.info("Database updates committed")
        
        # Display summary
        self.print_summary()
        
    def verify_outputs_exist(self, file_id):
        """Verify all required output files exist for a file_id"""
        # Look for transcript JSON
        transcript_path = self.find_file(self.transcript_dir, f"{file_id}*.json")
        
        # Look for EN translation JSON
        translation_en_path = self.find_file(self.translation_en_dir, f"{file_id}*.json")
        
        # Look for HE translation JSON
        translation_he_path = self.find_file(self.translation_he_dir, f"{file_id}*.json")
        
        # All outputs must exist for verification to pass
        return transcript_path and translation_en_path and translation_he_path
    
    def find_file(self, directory, pattern):
        """Find files matching pattern in directory"""
        if not os.path.exists(directory):
            return None
            
        matching_files = list(Path(directory).glob(pattern))
        return matching_files[0] if matching_files else None
    
    def update_status_to_completed(self, file_id):
        """Update the overall status to completed for a file"""
        self.cursor.execute("""
        UPDATE processing_status
        SET status = 'completed'
        WHERE file_id = ?
        """, (file_id,))
    
    def get_total_file_count(self):
        """Get total count of files in the database"""
        self.cursor.execute("SELECT COUNT(*) FROM media_files")
        return self.cursor.fetchone()[0]
    
    def print_summary(self):
        """Print summary statistics"""
        logger.info("\n" + "="*50)
        logger.info("STATUS VERIFICATION SUMMARY")
        logger.info("="*50)
        logger.info(f"Total files in database: {self.stats['total_files']}")
        logger.info(f"Files marked as completed in database: {self.stats['db_completed']}")
        logger.info(f"Files with verified output files: {self.stats['actual_completed']}")
        logger.info(f"Files with status fixed: {self.stats['status_fixed']}")
        logger.info(f"Files missing output files: {self.stats['missing_output']}")
        logger.info("="*50)
        
        # Print suggested next steps
        logger.info("\nSUGGESTED NEXT STEPS:")
        if self.stats['missing_output'] > 0:
            logger.info(f"1. Inspect the {self.stats['missing_output']} files with missing outputs")
            logger.info("2. Run the retry command for genuinely failed files:")
            logger.info("   python media_processor.py --retry --status failed")
        else:
            logger.info("All files marked as completed have verified output files")
            
        # Calculate remaining files to process
        remaining = self.stats['total_files'] - self.stats['actual_completed']
        logger.info(f"\nREMAINING FILES: {remaining}")
        logger.info("To process remaining files:")
        logger.info("   python media_processor.py --retry --status failed")
        
    def close(self):
        """Close database connection"""
        self.conn.close()

def main():
    verifier = StatusVerifier()
    try:
        verifier.verify_and_fix()
    finally:
        verifier.close()

if __name__ == "__main__":
    main()
