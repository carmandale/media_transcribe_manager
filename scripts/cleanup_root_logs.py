#!/usr/bin/env python3
"""
Relocate any root-level .log files into the logs/ folder.
This helps consolidate all logs in a single directory.
"""
import shutil
from pathlib import Path

def main():
    root = Path(__file__).parent.parent
    logs_dir = root / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    moved = False
    for log_file in root.glob('*.log'):
        dest = logs_dir / log_file.name
        if dest.exists():
            # Remove duplicate root-level log
            print(f"Deleting duplicate root log: {log_file.name}")
            log_file.unlink()
            moved = True
        else:
            print(f"Moving {log_file.name} -> logs/{log_file.name}")
            shutil.move(str(log_file), str(dest))
            moved = True
    
    if not moved:
        print("No root-level log files to move.")

if __name__ == '__main__':
    main()