#!/usr/bin/env python3
"""
Example usage of the consolidated database module.
"""

from pathlib import Path
from scribe.database import Database


def main():
    """Demonstrate database usage."""
    # Initialize database
    db = Database("media_tracking.db")
    
    # Add a new media file
    file_id = db.add_file(
        file_path="/path/to/interview.mp3",
        safe_filename="interview_001.mp3",
        media_type="audio",
        duration=1800.0,  # 30 minutes
        detected_language="en"
    )
    
    # Update processing status
    db.update_status(file_id, status='in-progress')
    db.update_status(file_id, transcription_status='completed')
    
    # Check for files ready for translation
    pending_en = db.get_pending_files('translation_en', limit=10)
    for file in pending_en:
        print(f"Ready for English translation: {file['safe_filename']}")
    
    # Handle errors
    try:
        # Some processing...
        pass
    except Exception as e:
        db.log_error(file_id, 'translation_en', str(e))
    
    # Get summary statistics
    summary = db.get_summary()
    print(f"Total files: {summary['total_files']}")
    print(f"Status breakdown: {summary['status_counts']}")
    
    # Query stuck files (in-progress for >30 minutes)
    stuck = db.get_stuck_files(timeout_minutes=30)
    for file in stuck:
        print(f"Stuck file: {file['file_id']} - {file['safe_filename']}")
    
    # Clean up
    db.close()


if __name__ == "__main__":
    main()