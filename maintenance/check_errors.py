#!/usr/bin/env python3
"""
Check recent errors in the translation pipeline.

Usage:
    python check_errors.py [--hours HOURS]
"""

import argparse
import datetime
from db_manager import DatabaseManager

def main():
    parser = argparse.ArgumentParser(description="Check recent errors in the translation pipeline")
    parser.add_argument("--hours", type=int, default=1, help="Hours to look back for errors")
    args = parser.parse_args()
    
    db = DatabaseManager('media_tracking.db')
    
    # Get error counts by stage
    query_stages = f"""
    SELECT process_stage, COUNT(*) as count 
    FROM errors 
    WHERE timestamp > datetime('now', '-{args.hours} hour') 
    GROUP BY process_stage
    """
    stage_results = db.execute_query(query_stages)
    
    print(f"Error summary (last {args.hours} hour{'s' if args.hours != 1 else ''}):")
    if stage_results:
        for row in stage_results:
            print(f"- {row['process_stage']}: {row['count']} errors")
    else:
        print("- No errors found")
    
    # Get error types
    query_types = f"""
    SELECT error_message, COUNT(*) as count 
    FROM errors 
    WHERE timestamp > datetime('now', '-{args.hours} hour') 
    GROUP BY error_message 
    ORDER BY count DESC 
    LIMIT 5
    """
    type_results = db.execute_query(query_types)
    
    print("\nMost common error types:")
    if type_results:
        for row in type_results:
            msg = row['error_message'] or "Unknown error"
            print(f"- {msg}: {row['count']} occurrences")
    else:
        print("- No errors found")
    
    # Get most recent errors with details
    query_recent = f"""
    SELECT e.file_id, e.process_stage, e.error_message, e.timestamp,
           m.original_path
    FROM errors e
    JOIN media_files m ON e.file_id = m.file_id
    WHERE e.timestamp > datetime('now', '-{args.hours} hour')
    ORDER BY e.timestamp DESC
    LIMIT 5
    """
    recent_results = db.execute_query(query_recent)
    
    print("\nMost recent errors:")
    if recent_results:
        for row in recent_results:
            file_id = row['file_id']
            filename = row['original_path'].split('/')[-1] if row['original_path'] else "Unknown"
            stage = row['process_stage']
            message = row['error_message'] or "Unknown error"
            time = row['timestamp']
            print(f"- File: {filename} (ID: {file_id})")
            print(f"  Stage: {stage}")
            print(f"  Error: {message}")
            print(f"  Time: {time}")
            print()
    else:
        print("- No errors found")

if __name__ == "__main__":
    main()