#!/usr/bin/env python3
"""
Fix Transcript Status Script (Alias)

This script is a backward-compatible alias for the new consolidated command:
    python scribe_manager.py fix transcripts

This script identifies and fixes inconsistencies between the transcript status
in the database and the actual state of transcript files on disk.

Original script saved in legacy_scripts/fix_transcript_status.py
"""

import sys
import os
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fix_transcript_status.log')
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments and convert to new format."""
    parser = argparse.ArgumentParser(
        description="Fix transcript status inconsistencies (DEPRECATED)"
    )
    parser.add_argument('--no-reset', action='store_true',
                      help='Do not reset status to failed')
    parser.add_argument('--batch-size', type=int, default=20,
                      help='Process in batches of this size')
    parser.add_argument('--db-path', type=str, default='media_tracking.db',
                      help='Path to SQLite database file')
    
    return parser.parse_args()

def main():
    """Convert arguments and forward to new command."""
    args = parse_args()
    
    # Print deprecation notice
    print("=" * 80)
    print("DEPRECATION WARNING: fix_transcript_status.py is deprecated.")
    print("Please use 'python scribe_manager.py fix transcripts' instead.")
    print("Original script saved in legacy_scripts/fix_transcript_status.py")
    print("=" * 80)
    
    # Build the new command
    cmd = ["python", "scribe_manager.py", "fix", "transcripts"]
    
    # Add arguments
    if args.no_reset:
        cmd.append("--no-reset")
    
    if args.batch_size != 20:  # Only if not default
        cmd.extend(["--batch-size", str(args.batch_size)])
        
    if args.db_path != 'media_tracking.db':  # Only if not default
        cmd.extend(["--db-path", args.db_path])
    
    # Print the command
    logger.info(f"Forwarding to: {' '.join(cmd)}")
    
    # Execute the new command
    os.execvp(cmd[0], cmd)

if __name__ == "__main__":
    main()