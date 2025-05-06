#!/usr/bin/env python3
"""
Fix Problem Translations

This script identifies problematic files that repeatedly fail translation
and marks them as 'qa_failed' to prevent further attempts.
"""

import os
import sqlite3
import logging
import json
from typing import List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fix_problem_translations.log')
    ]
)

logger = logging.getLogger(__name__)

# List of problematic file IDs 
PROBLEMATIC_FILE_IDS = [
    '19bf3b36-95d6-409e-b706-d63016851ec6',
    '52f763db-9c2e-42c9-b1b7-97aede60a0ab',
    '7a89fcac-0748-4aff-9d5f-cd7e7fef8fef',
    'ed4c11e0-4cd5-4177-9b47-be64df99add9'
]

def fix_problem_translations():
    """Mark problematic files as 'qa_failed' to prevent further processing attempts."""
    try:
        # Connect to database
        conn = sqlite3.connect('media_tracking.db')
        cursor = conn.cursor()
        
        # Get information about these files
        placeholders = ','.join(['?'] * len(PROBLEMATIC_FILE_IDS))
        cursor.execute(f"""
        SELECT m.file_id, m.safe_filename, m.original_path
        FROM media_files m
        WHERE m.file_id IN ({placeholders})
        """, PROBLEMATIC_FILE_IDS)
        
        files = cursor.fetchall()
        
        # Create a summary report
        summary = {
            "problematic_files": [],
            "total_fixed": 0
        }
        
        for file_id, safe_filename, original_path in files:
            file_info = {
                "file_id": file_id,
                "filename": safe_filename,
                "path": original_path
            }
            
            # Check error history
            cursor.execute("""
            SELECT error_message
            FROM errors
            WHERE file_id = ?
            ORDER BY timestamp DESC
            LIMIT 5
            """, (file_id,))
            
            errors = [row[0] for row in cursor.fetchall()]
            file_info["recent_errors"] = errors
            
            # Mark as qa_failed for all languages
            for lang in ['en', 'de', 'he']:
                status_field = f"translation_{lang}_status"
                cursor.execute(f"""
                UPDATE processing_status
                SET {status_field} = 'qa_failed'
                WHERE file_id = ? AND {status_field} IN ('not_started', 'failed')
                """, (file_id,))
                
                if cursor.rowcount > 0:
                    file_info[f"{lang}_updated"] = True
                    summary["total_fixed"] += 1
                else:
                    file_info[f"{lang}_updated"] = False
            
            # Log error explaining why this file is marked as qa_failed
            cursor.execute("""
            INSERT INTO errors (file_id, process_stage, error_message, error_details)
            VALUES (?, ?, ?, ?)
            """, (
                file_id, 
                "translation", 
                "Marked as qa_failed by fix_problem_translations.py",
                "File consistently fails translation due to source language detection issues"
            ))
            
            summary["problematic_files"].append(file_info)
            logger.info(f"Marked {file_id} ({safe_filename}) as qa_failed for all pending languages")
        
        # Commit changes
        conn.commit()
        
        # Save summary to file
        with open('problematic_translations.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Fixed {summary['total_fixed']} problematic translations")
        logger.info(f"Summary saved to problematic_translations.json")
        
        # Close connection
        conn.close()
        
        return summary["total_fixed"]
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return 0

def main():
    logger.info("Starting fix for problem translations")
    
    fixed_count = fix_problem_translations()
    
    if fixed_count > 0:
        logger.info(f"Successfully marked {fixed_count} problematic translations as qa_failed")
        logger.info("These files will no longer be attempted for translation")
    else:
        logger.warning("No problematic translations were fixed")
    
    return 0

if __name__ == "__main__":
    main()