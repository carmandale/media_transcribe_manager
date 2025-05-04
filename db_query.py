#!/usr/bin/env python3
"""
Database Query Utility

A simple utility to execute SQL queries against the media_tracking database
without needing to write complex one-liners with proper quoting.

Usage:
    python db_query.py "SELECT * FROM processing_status LIMIT 5"
    python db_query.py "SELECT COUNT(*) FROM processing_status WHERE translation_en_status = 'completed'"
    
The results are returned in a readable JSON format.
"""

import sys
import json
import argparse
from db_manager import DatabaseManager

def execute_query(query, params=None, format_output="json"):
    """Execute an SQL query and return the results."""
    db = DatabaseManager('media_tracking.db')
    results = db.execute_query(query, params)
    
    if format_output == "json":
        # Print results in JSON format
        print(json.dumps(results, indent=2, default=str))
    elif format_output == "table":
        # Print results in a simple table format
        if not results:
            print("No results")
            return
        
        # Get column names from first result
        columns = list(results[0].keys())
        
        # Calculate column widths
        col_widths = {col: max(len(col), max(len(str(row[col])) for row in results)) 
                     for col in columns}
        
        # Print header
        header = " | ".join(col.ljust(col_widths[col]) for col in columns)
        print(header)
        print("-" * len(header))
        
        # Print rows
        for row in results:
            print(" | ".join(str(row[col]).ljust(col_widths[col]) for col in columns))
    else:
        # Print raw results
        for row in results:
            print(row)

def main():
    parser = argparse.ArgumentParser(description="Execute SQL queries against the media_tracking database")
    parser.add_argument("query", help="SQL query to execute")
    parser.add_argument("--format", choices=["json", "table", "raw"], default="json",
                       help="Output format (default: json)")
    args = parser.parse_args()
    
    execute_query(args.query, format_output=args.format)

if __name__ == "__main__":
    main()