#!/bin/bash
# Start the Hebrew retranslation batch process
# This will run in the background and log progress

echo "Starting Hebrew retranslation batch process..."
echo "This will process 406 files and may take several hours."
echo "Progress will be logged to: retranslate_hebrew_batch.log"
echo ""
echo "To monitor progress, use: tail -f retranslate_hebrew_batch.log"
echo ""

# Run the process
cd "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/dev/scribe"
nohup uv run python retranslate_hebrew_batch.py > retranslate_output.log 2>&1 &
PID=$!

echo "Process started with PID: $PID"
echo "To stop: kill $PID"
echo ""
echo "Initial progress:"
sleep 5
tail -20 retranslate_hebrew_batch.log