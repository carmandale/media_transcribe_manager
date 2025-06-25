#!/usr/bin/env python3
"""
Update Quality Scores in Database from JSON Files

This script scans for .evaluations.json files and updates the central
database with the composite scores, ensuring the main `status` command
reflects the most accurate and up-to-date quality metrics.
"""

import json
import logging
from pathlib import Path
import sys
from typing import Dict, Any, List, Tuple
import sqlite3

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scribe.database import Database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScoreUpdater:
    """Synchronizes evaluation scores from JSON files to the database."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.db = Database()
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """
        Ensure the quality_evaluations table exists with the correct schema,
        recreating it if necessary to enforce constraints.
        """
        with self.db.transaction() as conn:
            # Check for the existence of the primary key on the table
            cursor = conn.execute("PRAGMA table_info(quality_evaluations);")
            columns = {row['name']: row for row in cursor.fetchall()}
            
            pk_cols = [col for col, info in columns.items() if info['pk'] > 0]
            
            # If the primary key is not what we expect, recreate the table
            if sorted(pk_cols) != ['file_id', 'language']:
                logger.warning("Recreating quality_evaluations table to enforce PRIMARY KEY constraint.")
                
                # 1. Rename old table
                conn.execute("ALTER TABLE quality_evaluations RENAME TO quality_evaluations_old;")
                
                # 2. Create new table with correct schema
                conn.execute("""
                    CREATE TABLE quality_evaluations (
                        file_id TEXT NOT NULL,
                        language TEXT NOT NULL,
                        score REAL NOT NULL,
                        evaluation_details TEXT,
                        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (file_id, language)
                    )
                """)
                
                # 3. Copy data from old table, if it has the right columns
                old_cols = [col.lower() for col in columns.keys()]
                if 'file_id' in old_cols and 'language' in old_cols and 'score' in old_cols:
                    conn.execute("""
                        INSERT OR IGNORE INTO quality_evaluations (file_id, language, score)
                        SELECT file_id, language, score FROM quality_evaluations_old;
                    """)
                
                # 4. Drop the old table
                conn.execute("DROP TABLE quality_evaluations_old;")
                logger.info("Successfully recreated quality_evaluations table.")
            else:
                # If table is correct, just ensure the details column exists
                if 'evaluation_details' not in columns:
                    try:
                        conn.execute("ALTER TABLE quality_evaluations ADD COLUMN evaluation_details TEXT;")
                        logger.info("Added 'evaluation_details' column.")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e):
                            raise

        logger.info("Ensured quality_evaluations table is up to date.")

    def run(self):
        """
        Scan for evaluation files and update the database.
        """
        evaluation_files = list(self.output_dir.rglob("*.evaluations.json"))
        if not evaluation_files:
            logger.warning("No .evaluations.json files found. Nothing to update.")
            return

        logger.info(f"Found {len(evaluation_files)} evaluation files to process.")
        
        updates: List[Tuple[str, str, float, str]] = []
        for eval_file in evaluation_files:
            try:
                file_id = eval_file.parent.name
                with open(eval_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for lang_name, eval_data in data.items():
                    if isinstance(eval_data, dict) and 'composite_score' in eval_data:
                        score = eval_data['composite_score']
                        updates.append((
                            file_id,
                            lang_name.lower(),
                            float(score),
                            json.dumps(eval_data)
                        ))
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Could not process {eval_file}: {e}")
                continue
        
        if not updates:
            logger.info("No valid scores found in evaluation files.")
            return
            
        self._commit_to_db(updates)

    def _commit_to_db(self, updates: List[Tuple[str, str, float, str]]):
        """
        Commit the updated scores to the database using an UPSERT operation.

        Args:
            updates: A list of tuples, each containing (file_id, language, score, details_json).
        """
        
        cleanup_query = "DELETE FROM quality_evaluations WHERE language IN ('de', 'en', 'he');"

        insert_query = """
            INSERT INTO quality_evaluations (file_id, language, score, evaluation_details, evaluated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(file_id, language) DO UPDATE SET
                score = excluded.score,
                evaluation_details = excluded.evaluation_details,
                evaluated_at = CURRENT_TIMESTAMP;
        """
        try:
            with self.db.transaction() as conn:
                # Clean up old, short-form language entries first
                conn.execute(cleanup_query)
                logger.info("Removed old short-form language entries from quality_evaluations.")
                
                # Insert or update the new, full-name entries
                conn.executemany(insert_query, updates)
            logger.info(f"Successfully inserted or updated {len(updates)} scores in the database.")
        except Exception as e:
            logger.critical(f"Failed to commit scores to the database: {e}", exc_info=True)

def main():
    try:
        updater = ScoreUpdater()
        updater.run()
        logger.info("Database score update process complete.")
    except Exception as e:
        logger.critical(f"A critical error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 