#!/bin/bash
# Simple script to monitor transcription and translation progress

while true; do
    echo ""
    echo "$(date): Checking processing status..."
    echo "----------------------------------------"
    
    # Check if any parallel processes are running
    RUNNING_PROCESSES=$(ps -ef | grep python | grep -E 'parallel_(transcription|translation)' | grep -v grep | wc -l)
    echo "Running processes: $RUNNING_PROCESSES"
    
    # Show database status
    echo ""
    echo "Database Status:"
    sqlite3 media_tracking.db "SELECT transcription_status, COUNT(*) FROM processing_status GROUP BY transcription_status; SELECT translation_en_status, COUNT(*) FROM processing_status GROUP BY translation_en_status; SELECT translation_de_status, COUNT(*) FROM processing_status GROUP BY translation_de_status; SELECT translation_he_status, COUNT(*) FROM processing_status GROUP BY translation_he_status;"
    
    # Check if all processing is complete
    PENDING_TRANSCRIPTIONS=$(sqlite3 media_tracking.db "SELECT COUNT(*) FROM processing_status WHERE transcription_status IN ('not_started', 'in-progress', 'failed')")
    
    PENDING_TRANSLATIONS=$(sqlite3 media_tracking.db "SELECT 
        SUM(CASE WHEN translation_en_status IN ('not_started', 'in-progress', 'failed') THEN 1 ELSE 0 END) +
        SUM(CASE WHEN translation_de_status IN ('not_started', 'in-progress', 'failed') THEN 1 ELSE 0 END) +
        SUM(CASE WHEN translation_he_status IN ('not_started', 'in-progress', 'failed') THEN 1 ELSE 0 END)
        FROM processing_status")
    
    echo ""
    echo "Pending transcriptions: $PENDING_TRANSCRIPTIONS"
    echo "Pending translations: $PENDING_TRANSLATIONS"
    
    # If any transcriptions are in-progress, check transcript length
    IN_PROGRESS=$(sqlite3 media_tracking.db "SELECT file_id, safe_filename FROM media_files m JOIN processing_status p ON m.file_id = p.file_id WHERE p.transcription_status = 'in-progress'")
    
    if [ ! -z "$IN_PROGRESS" ]; then
        echo ""
        echo "Files currently in progress:"
        echo "$IN_PROGRESS"
    fi
    
    # Start parallel_transcription if nothing is running and we have pending transcripts
    if [ "$RUNNING_PROCESSES" -eq 0 ] && [ "$PENDING_TRANSCRIPTIONS" -gt 0 ]; then
        echo ""
        echo "Starting transcription process..."
        python parallel_transcription.py --batch-size 5 > transcription_output.log 2>&1 &
        echo "Transcription process started in background. Check transcription_output.log for progress."
    fi
    
    # Check if all transcriptions are done but translations are pending
    if [ "$PENDING_TRANSCRIPTIONS" -eq 0 ] && [ "$RUNNING_PROCESSES" -eq 0 ] && [ "$PENDING_TRANSLATIONS" -gt 0 ]; then
        echo ""
        echo "Starting translation processes..."
        
        # Start one process for each language
        python parallel_translation.py --language en --batch-size 5 > en_translation.log 2>&1 &
        echo "English translation process started in background."
        
        sleep 2
        
        python parallel_translation.py --language de --batch-size 5 > de_translation.log 2>&1 &
        echo "German translation process started in background."
        
        sleep 2
        
        python parallel_translation.py --language he --batch-size 5 > he_translation.log 2>&1 &
        echo "Hebrew translation process started in background."
    fi
    
    # Check if all processing is complete
    if [ "$PENDING_TRANSCRIPTIONS" -eq 0 ] && [ "$PENDING_TRANSLATIONS" -eq 0 ]; then
        echo ""
        echo "All processing complete!"
        break
    fi
    
    echo ""
    echo "Next check in 60 seconds..."
    sleep 60
done