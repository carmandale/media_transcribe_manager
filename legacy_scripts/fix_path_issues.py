#!/usr/bin/env python3
"""
Fix Path Issues Script (Alias)

This script is a backward-compatible alias for the new consolidated command:
    python scribe_manager.py fix paths

This script identifies and fixes incorrect file paths in the database.
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
        logging.FileHandler('fix_path_issues.log')
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments and convert to new format."""
    parser = argparse.ArgumentParser(
        description="Fix incorrect file paths in the database (DEPRECATED)"
    )
    parser.add_argument('--mapping-file', type=str,
                      help='JSON file with file_id to path mapping')
    parser.add_argument('--no-verify', action='store_true',
                      help='Skip verification of file existence')
    parser.add_argument('--db-path', type=str, default='media_tracking.db',
                      help='Path to SQLite database file')
    
    return parser.parse_args()

def main():
    """Convert arguments and forward to new command."""
    args = parse_args()
    
    # Print deprecation notice
    print("=" * 80)
    print("DEPRECATION WARNING: fix_path_issues.py is deprecated.")
    print("Please use 'python scribe_manager.py fix paths' instead.")
    print("=" * 80)
    
    # Build the new command
    cmd = ["python", "scribe_manager.py", "fix", "paths"]
    
    # Add arguments
    if args.mapping_file:
        cmd.extend(["--mapping-file", args.mapping_file])
    
    if args.no_verify:
        cmd.append("--no-verify")
        
    if args.db_path != 'media_tracking.db':  # Only if not default
        cmd.extend(["--db-path", args.db_path])
    
    # Print the command
    logger.info(f"Forwarding to: {' '.join(cmd)}")
    
    # Execute the new command
    os.execvp(cmd[0], cmd)

if __name__ == "__main__":
    main()