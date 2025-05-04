#!/usr/bin/env python3
"""
Check the status of files marked for retranscription.
"""

from db_manager import DatabaseManager
import os
from pathlib import Path

# Initialize database connection
db = DatabaseManager('media_tracking.db')

# Get files marked for retranscription
query = """
SELECT file_id, status, transcription_status, original_path 
FROM processing_status 
JOIN media_files USING (file_id) 
WHERE transcription_status = 'not_started'
"""
results = db.execute_query(query)

print(f"Found {len(results)} files marked for retranscription")

# Check if original files exist
missing_files = 0
for row in results:
    file_id = row['file_id']
    orig_path = row['original_path']
    
    # Verify if the original file exists
    if not os.path.exists(orig_path):
        print(f"File not found: {file_id}, Path: {orig_path}")
        missing_files += 1
    
print(f"\n{missing_files} out of {len(results)} original files are missing")

# Check if any transcriptions have succeeded
query = """
SELECT file_id, transcription_status, last_updated
FROM processing_status
WHERE 
  file_id IN (
    SELECT file_id FROM errors 
    WHERE error_message = 'Transcript text not found'
  )
  AND transcription_status = 'completed'
"""
successful_transcripts = db.execute_query(query)

print(f"\n{len(successful_transcripts)} files with previous 'Transcript text not found' errors now have successful transcriptions")

# Check if there were any recent transcript errors
query = """
SELECT e.file_id, e.error_message, e.timestamp, m.original_path
FROM errors e
JOIN media_files m ON e.file_id = m.file_id
WHERE e.process_stage = 'transcription'
AND e.timestamp > datetime('now', '-1 hour')
ORDER BY e.timestamp DESC
LIMIT 10
"""
recent_errors = db.execute_query(query)

print(f"\nRecent transcription errors ({len(recent_errors)} in the last hour):")
for row in recent_errors:
    file_id = row['file_id']
    error_msg = row['error_message']
    timestamp = row['timestamp']
    path = row['original_path'].split('/')[-1]
    print(f"File: {file_id}, Error: {error_msg}, Time: {timestamp}, Path: {path}")

# Check file formats and sizes
file_types = {}
file_sizes = {}

for row in results:
    file_path = row['original_path']
    if os.path.exists(file_path):
        # Get file extension
        ext = os.path.splitext(file_path)[1].lower()
        file_types[ext] = file_types.get(ext, 0) + 1
        
        # Get file size
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        size_category = f"{int(size_mb / 10) * 10}-{int(size_mb / 10) * 10 + 10}MB"
        file_sizes[size_category] = file_sizes.get(size_category, 0) + 1

print("\nFile formats of unprocessed files:")
for ext, count in file_types.items():
    print(f"{ext}: {count} files")

print("\nFile sizes of unprocessed files:")
for size, count in sorted(file_sizes.items()):
    print(f"{size}: {count} files")

# Check for any common patterns in file paths
path_patterns = {}
for row in results:
    path = row['original_path']
    # Extract directory structure
    parts = path.split('/')
    if len(parts) > 3:
        pattern = '/'.join(parts[-3:-1])
        path_patterns[pattern] = path_patterns.get(pattern, 0) + 1

print("\nCommon directory patterns:")
for pattern, count in sorted(path_patterns.items(), key=lambda x: x[1], reverse=True):
    if count > 1:
        print(f"{pattern}: {count} files")

# Check if any transcription jobs are in progress
query = """
SELECT COUNT(*) as count
FROM processing_status
WHERE transcription_status = 'in-progress'
"""
in_progress = db.execute_query(query)[0]['count']

print(f"\nTranscription jobs currently in progress: {in_progress}")

# Check when the transcription processor was last active
query = """
SELECT MAX(last_updated) as last_active
FROM processing_status
WHERE transcription_status IN ('completed', 'failed', 'in-progress')
"""
last_active = db.execute_query(query)[0]['last_active']

print(f"Transcription processor last active: {last_active}")