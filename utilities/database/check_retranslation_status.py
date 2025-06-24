#!/usr/bin/env python3
"""Check status of the retranslation batch process"""
import csv
import sqlite3
from pathlib import Path

def check_status():
    # Check TSV file
    tsv_file = "english_retranslate.tsv"
    if not Path(tsv_file).exists():
        print("❌ TSV file not found!")
        return
    
    # Count remaining entries
    remaining = 0
    with open(tsv_file, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        remaining = sum(1 for _ in reader)
    
    original_count = 406
    completed = original_count - remaining
    
    print(f"Retranslation Progress:")
    print(f"="*50)
    print(f"Completed: {completed}/{original_count} ({completed/original_count*100:.1f}%)")
    print(f"Remaining: {remaining}")
    
    # Check recent evaluations
    db_path = "media_tracking.db"
    if Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get recent high scores
        query = """
            SELECT file_id, score, evaluated_at 
            FROM quality_evaluations 
            WHERE language = 'he' 
            AND score >= 9.0 
            AND evaluated_at > datetime('now', '-1 hour')
            ORDER BY evaluated_at DESC 
            LIMIT 10
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        if results:
            print(f"\nRecent successful evaluations (≥9.0):")
            print(f"-"*50)
            for file_id, score, timestamp in results:
                print(f"  {file_id[:8]}... Score: {score:.1f} at {timestamp}")
        
        conn.close()
    
    # Check log file
    log_file = "retranslate_hebrew_batch.log"
    if Path(log_file).exists():
        # Get last few lines
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-10:] if len(lines) > 10 else lines
        
        print(f"\nRecent log entries:")
        print(f"-"*50)
        for line in recent_lines:
            print(f"  {line.strip()}")

if __name__ == "__main__":
    check_status()