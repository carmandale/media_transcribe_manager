#!/usr/bin/env python3
"""
Fix Problem Translations Script (Alias)

This script is a backward-compatible alias for the new consolidated command:
    python scribe_manager.py fix mark

This script marks problematic translation files with special status in the database.

Original script saved in legacy_scripts/fix_problem_translations.py
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
        logging.FileHandler('fix_problem_translations.log')
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments and convert to new format."""
    parser = argparse.ArgumentParser(
        description="Mark problematic translation files (DEPRECATED)"
    )
    parser.add_argument('--file-ids', type=str,
                      help='Comma-separated list of file IDs to mark')
    parser.add_argument('--status', type=str, default='qa_failed',
                      help='Status to set (default: qa_failed)')
    parser.add_argument('--reason', type=str, default='',
                      help='Reason for marking as problem')
    parser.add_argument('--db-path', type=str, default='media_tracking.db',
                      help='Path to SQLite database file')
    
    return parser.parse_args()

def main():
    """Convert arguments and forward to new command."""
    args = parse_args()
    
    # Print deprecation notice
    print("=" * 80)
    print("DEPRECATION WARNING: fix_problem_translations.py is deprecated.")
    print("Please use 'python scribe_manager.py fix mark' instead.")
    print("Original script saved in legacy_scripts/fix_problem_translations.py")
    print("=" * 80)
    
    # Build the new command
    cmd = ["python", "scribe_manager.py", "fix", "mark"]
    
    # Add arguments
    if args.file_ids:
        cmd.extend(["--file-ids", args.file_ids])
    
    if args.status != 'qa_failed':  # Only if not default
        cmd.extend(["--status", args.status])
    
    if args.reason:
        cmd.extend(["--reason", args.reason])
        
    if args.db_path != 'media_tracking.db':  # Only if not default
        cmd.extend(["--db-path", args.db_path])
    
    # Print the command
    logger.info(f"Forwarding to: {' '.join(cmd)}")
    
    # Execute the new command
    os.execvp(cmd[0], cmd)

if __name__ == "__main__":
    main()