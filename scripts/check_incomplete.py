#!/usr/bin/env python3
"""Check for incomplete processing files."""

import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager

db = DatabaseManager('media_tracking.db')

query = """
SELECT file_id, transcription_status, translation_en_status, 
       translation_de_status, translation_he_status 
FROM processing_status 
WHERE transcription_status != 'completed' 
   OR translation_en_status != 'completed' 
   OR translation_de_status != 'completed' 
   OR translation_he_status != 'completed'
"""

results = db.execute_query(query)

if results:
    print(f"Found {len(results)} incomplete files:")
    for r in results:
        print(f"  {r['file_id']}: T={r['transcription_status']}, EN={r['translation_en_status']}, DE={r['translation_de_status']}, HE={r['translation_he_status']}")
else:
    print("All files have completed processing!")