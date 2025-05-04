#!/usr/bin/env python3
"""
Translation Stuck Process Detection and Recovery Tool

This script identifies and resets files that are stuck in the 'in-progress' state,
allowing them to be picked up and processed again by the pipeline.

Usage:
    python check_stuck_files.py

How it works:
1. Identifies files in 'in-progress' state
2. For files that have been in this state for >30 minutes, resets them to 'not_started'
3. Reports which files were reset

After running this script, restart the pipeline with:
    python run_full_pipeline.py

See also:
    - check_status.py - For checking overall translation status
    - monitor_and_restart.py - For automatic monitoring and recovery
    - docs/MONITORING_GUIDE.md - For detailed monitoring documentation
"""

from db_manager import DatabaseManager
import datetime

# Connect to database
db = DatabaseManager('media_tracking.db')

# Get files stuck in in-progress state
query = """
SELECT file_id, translation_en_status, translation_de_status, translation_he_status, last_updated
FROM processing_status
WHERE translation_en_status = 'in-progress'
   OR translation_de_status = 'in-progress'
   OR translation_he_status = 'in-progress'
ORDER BY last_updated ASC
"""

stuck_files = db.execute_query(query)
print(f"Found {len(stuck_files)} files stuck in 'in-progress' state:\n")

current_time = datetime.datetime.now()

for file in stuck_files:
    file_id = file['file_id']
    last_updated = datetime.datetime.strptime(file['last_updated'], "%Y-%m-%d %H:%M:%S.%f")
    minutes_since_update = (current_time - last_updated).total_seconds() / 60
    
    print(f"File: {file_id}")
    print(f"  EN: {file['translation_en_status']}") 
    print(f"  DE: {file['translation_de_status']}")
    print(f"  HE: {file['translation_he_status']}")
    print(f"  Last updated: {file['last_updated']} ({minutes_since_update:.1f} minutes ago)")
    
    # Reset status for files stuck longer than 30 minutes
    if minutes_since_update > 30:
        update_query = {}
        
        if file['translation_en_status'] == 'in-progress':
            update_query['translation_en_status'] = 'not_started'
            
        if file['translation_de_status'] == 'in-progress':
            update_query['translation_de_status'] = 'not_started'
            
        if file['translation_he_status'] == 'in-progress':
            update_query['translation_he_status'] = 'not_started'
        
        if update_query:
            print(f"  Resetting status for file {file_id}")
            db.update_status(file_id, 'pending', **update_query)
            print(f"  Status reset done")
    
    print("")

print("All stuck files processed. Run the pipeline again to continue processing.")