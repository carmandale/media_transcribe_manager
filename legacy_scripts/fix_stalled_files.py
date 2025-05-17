#!/usr/bin/env python3
"""
Fix Stalled Files Script (Alias)

This script is a backward-compatible alias for the new consolidated command:
    python scribe_manager.py fix stalled

This script identifies and fixes files that are stuck in 'in-progress' state
but don't have the necessary files to proceed with processing.
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
        logging.FileHandler('fix_stalled_files.log')
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments and convert to new format."""
    parser = argparse.ArgumentParser(
        description="Fix files stuck in 'in-progress' state (DEPRECATED)"
    )
    parser.add_argument('--timeout', type=int, default=30,
                      help='Minutes after which to consider a process stalled')
    parser.add_argument('--reset-all', action='store_true',
                      help='Reset all in-progress files regardless of time')
    parser.add_argument('--db-path', type=str, default='media_tracking.db',
                      help='Path to SQLite database file')
    
    return parser.parse_args()

def main():
    """Convert arguments and forward to new command."""
    args = parse_args()
    
    # Print deprecation notice
    print("=" * 80)
    print("DEPRECATION WARNING: fix_stalled_files.py is deprecated.")
    print("Please use 'python scribe_manager.py fix stalled' instead.")
    print("=" * 80)
    
    # Build the new command
    cmd = ["python", "scribe_manager.py", "fix", "stalled"]
    
    # Add arguments
    if args.timeout != 30:  # Only if not default
        cmd.extend(["--timeout", str(args.timeout)])
    
    if args.reset_all:
        cmd.append("--reset-all")
        
    if args.db_path != 'media_tracking.db':  # Only if not default
        cmd.extend(["--db-path", args.db_path])
    
    # Print the command
    logger.info(f"Forwarding to: {' '.join(cmd)}")
    
    # Execute the new command
    os.execvp(cmd[0], cmd)

if __name__ == "__main__":
    main()