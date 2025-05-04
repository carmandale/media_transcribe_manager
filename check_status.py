#!/usr/bin/env python3
"""
Translation Status Checking Tool

This script provides a comprehensive view of the current translation pipeline status,
including completion rates, quality evaluations, and stuck processes.

Usage:
    python check_status.py

See also:
    - check_stuck_files.py - For resetting stuck processes
    - monitor_and_restart.py - For automatic monitoring and recovery
    - docs/MONITORING_GUIDE.md - For detailed monitoring documentation
"""
from db_manager import DatabaseManager
import datetime

db = DatabaseManager('media_tracking.db')
query = '''
SELECT file_id, translation_en_status, translation_de_status, translation_he_status, last_updated 
FROM processing_status 
ORDER BY last_updated DESC 
LIMIT 5
'''
results = db.execute_query(query)

print("Most recently updated files:")
for row in results:
    print(f"File: {row['file_id']}, EN: {row['translation_en_status']}, DE: {row['translation_de_status']}, HE: {row['translation_he_status']}, Updated: {row['last_updated']}")

# Check for in-progress translations
query_in_progress = '''
SELECT COUNT(*) as count 
FROM processing_status 
WHERE translation_en_status = "in-progress" 
   OR translation_de_status = "in-progress" 
   OR translation_he_status = "in-progress"
'''
in_progress = db.execute_query(query_in_progress)[0]['count']
print(f"\nTranslations in progress: {in_progress}")

# Check when the last update happened
query_last_update = '''
SELECT MAX(last_updated) as last_update
FROM processing_status
'''
last_update = db.execute_query(query_last_update)[0]['last_update']
now = datetime.datetime.now()
time_diff = now - datetime.datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S.%f")
minutes_since_update = time_diff.total_seconds() / 60

print(f"Last database update: {last_update} ({minutes_since_update:.1f} minutes ago)")

# Check for completed translations
query_en = 'SELECT COUNT(*) as count FROM processing_status WHERE translation_en_status = "completed"'
query_de = 'SELECT COUNT(*) as count FROM processing_status WHERE translation_de_status = "completed"'
query_he = 'SELECT COUNT(*) as count FROM processing_status WHERE translation_he_status = "completed"'

en_completed = db.execute_query(query_en)[0]['count']
de_completed = db.execute_query(query_de)[0]['count']
he_completed = db.execute_query(query_he)[0]['count']

print(f"\nTranslation completion status:")
print(f"English: {en_completed}/728 completed ({en_completed/7.28:.1f}%)")
print(f"German: {de_completed}/728 completed ({de_completed/7.28:.1f}%)")
print(f"Hebrew: {he_completed}/728 completed ({he_completed/7.28:.1f}%)")

# Check for translations with placeholder
query_placeholder = '''
SELECT COUNT(*) as count 
FROM processing_status p
JOIN media_files m ON p.file_id = m.file_id
WHERE p.translation_he_status = "completed" 
  AND p.file_id IN (
    SELECT DISTINCT file_id FROM quality_evaluations 
    WHERE language = "he" AND score < 2
  )
'''

placeholder_count = db.execute_query(query_placeholder)[0]['count']
print(f"\nHebrew translations with placeholder still needing fixing: {placeholder_count}")

# Check quality evaluation status
query_quality = 'SELECT language, COUNT(*) as count FROM quality_evaluations GROUP BY language'
quality_results = db.execute_query(query_quality)

print("\nQuality evaluation status:")
for row in quality_results:
    language = row['language']
    count = row['count']
    print(f"{language} quality evaluations: {count}")

# Check quality evaluation results
query_quality_pass = '''
SELECT language, 
       SUM(CASE WHEN score >= 8.0 THEN 1 ELSE 0 END) as passed,
       SUM(CASE WHEN score < 8.0 THEN 1 ELSE 0 END) as failed,
       COUNT(*) as total
FROM quality_evaluations
GROUP BY language
'''
quality_pass_results = db.execute_query(query_quality_pass)

print("\nQuality evaluation pass/fail status:")
for row in quality_pass_results:
    language = row['language']
    passed = row['passed']
    failed = row['failed']
    total = row['total']
    pass_rate = (passed / total) * 100 if total > 0 else 0
    print(f"{language}: {passed} passed, {failed} failed ({pass_rate:.1f}% pass rate)")
    
# Check for recent errors
query_recent_errors = '''
SELECT COUNT(*) as count, process_stage 
FROM errors 
WHERE timestamp > datetime('now', '-30 minute') 
GROUP BY process_stage
'''
recent_errors = db.execute_query(query_recent_errors)

print("\nRecent errors (last 30 minutes):")
if recent_errors:
    for row in recent_errors:
        process_stage = row['process_stage']
        count = row['count']
        print(f"{process_stage}: {count} errors")
else:
    print("No recent errors found")