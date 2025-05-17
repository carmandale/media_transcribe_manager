#!/usr/bin/env python3
"""
Export all quality evaluation records to CSV.

Usage:
    python export_all_quality.py [--db-path DB] [--out-csv FILE]
"""
import sqlite3
import csv
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Export all quality evaluations to CSV"
    )
    parser.add_argument(
        '--db-path', type=str, default='media_tracking.db',
        help='Path to SQLite database file'
    )
    parser.add_argument(
        '--out-csv', type=str, default='all_quality_evals.csv',
        help='Output CSV file path'
    )
    args = parser.parse_args()

    # Connect to the database
    conn = sqlite3.connect(args.db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file_id, language, score, issues FROM quality_evaluations"
    )
    rows = cursor.fetchall()
    conn.close()

    # Write to CSV
    with open(args.out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['file_id', 'language', 'score', 'issues'])
        for row in rows:
            writer.writerow(row)

    print(f"All evaluations exported to {args.out_csv}")

if __name__ == '__main__':
    main()
