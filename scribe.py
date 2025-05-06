#!/usr/bin/env python3
"""
Scribe - Command-line wrapper for the Scribe Media Processing System

This is a convenience wrapper that forwards commands to the scribe_manager.py
module in the core_modules directory.

Usage:
    python scribe.py [command] [options]

Commands:
    status      Check pipeline status
    monitor     Start pipeline monitoring
    restart     Restart stalled processes
    start       Start pipeline processes
    retry       Retry problematic files
    special     Apply special case processing
    fix         Fix database issues
    verify      Verify database consistency
    cleanup     Clean up stalled processes
    help        Show this help message
"""

import os
import sys
from pathlib import Path

def main():
    """Forward commands to scribe_manager.py."""
    # Get the path to the scribe_manager.py script
    script_dir = Path(__file__).parent
    manager_path = script_dir / "core_modules" / "scribe_manager.py"
    
    if not manager_path.exists():
        print(f"Error: Could not find scribe_manager.py at {manager_path}")
        return 1
    
    # If no arguments or "help" is provided, show help message
    if len(sys.argv) == 1 or sys.argv[1] == "help":
        print(__doc__)
        return 0
    
    # Forward all arguments to scribe_manager.py
    cmd = [sys.executable, str(manager_path)] + sys.argv[1:]
    
    # Use os.execv to replace the current process
    # This ensures that signals (like Ctrl+C) are properly forwarded
    os.execv(sys.executable, cmd)

if __name__ == "__main__":
    sys.exit(main())