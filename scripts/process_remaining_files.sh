#!/bin/bash
# This script processes the remaining problematic files and then runs the monitoring
# script to handle any files that still need to be processed.

echo "Starting problematic files processing..."
python transcribe_problematic_files.py > problematic_files_output.log 2>&1 &
PROBLEMATIC_PID=$!

echo "Problematic files processing started in background (PID: $PROBLEMATIC_PID)"
echo "Log output is being saved to problematic_files_output.log"

echo "Waiting for problematic files to finish processing..."
wait $PROBLEMATIC_PID
RESULT=$?

echo "Problematic files processing completed with exit code $RESULT"

echo "Checking current status..."
sqlite3 media_tracking.db "SELECT transcription_status, COUNT(*) FROM processing_status GROUP BY transcription_status; SELECT translation_en_status, COUNT(*) FROM processing_status GROUP BY translation_en_status; SELECT translation_de_status, COUNT(*) FROM processing_status GROUP BY translation_de_status; SELECT translation_he_status, COUNT(*) FROM processing_status GROUP BY translation_he_status;"

echo "Running fix_stalled_files.py to update database state..."
python fix_stalled_files.py

echo "Starting monitor_and_restart.py in background to process any remaining files..."
python monitor_and_restart.py --check-interval 30 --batch-size 5 > monitor_output.log 2>&1 &
MONITOR_PID=$!

echo "Monitor process started (PID: $MONITOR_PID)"
echo "Run 'ps -p $MONITOR_PID' to check if the monitor is still running"
echo "Run 'tail -f monitor_output.log' to see monitor progress"
echo "Check database status with: sqlite3 media_tracking.db \"SELECT transcription_status, COUNT(*) FROM processing_status GROUP BY transcription_status\""