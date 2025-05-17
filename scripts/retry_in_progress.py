#!/usr/bin/env python3
"""
Retry all media files whose transcription is still in progress.
This script identifies file_ids in processing_status with transcription_status='in-progress'
and uses the ProblemFileHandler to retry transcription (and translation) for those files.
"""
import sqlite3
import sys
import os
from pathlib import Path

# Ensure project root is in sys.path so core_modules package can be imported
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager
from core_modules.file_manager import FileManager
from core_modules.pipeline_manager import ProblemFileHandler

def main():
    # Database and output paths
    db_path = Path('media_tracking.db')

    # Connect to DB and fetch in-progress transcription file_ids
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    # Retry any file whose transcription is not completed
    cursor.execute(
        "SELECT file_id FROM processing_status WHERE transcription_status != 'completed'"
    )
    rows = cursor.fetchall()
    conn.close()

    file_ids = [r[0] for r in rows]
    if not file_ids:
        print("No in-progress transcriptions to retry.")
        sys.exit(0)

    # Initialize managers with default config
    config = {}
    db_mgr = DatabaseManager(str(db_path))
    file_mgr = FileManager(db_mgr, config)
    handler = ProblemFileHandler(db_mgr, file_mgr, config)

    print(f"Retrying transcription for {len(file_ids)} files...")
    try:
        result = handler.retry_problematic_files(file_ids=file_ids)
        print("Retry results:", result)
    except Exception as e:
        print(f"Error during retry: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()