# Transcript Issue Troubleshooting & Resolution

## Summary of Issues and Solutions

We've identified and resolved an important issue affecting the translation pipeline: files with "Transcript text not found" errors despite showing a "completed" transcription status in the database.

### Key Issues Identified

1. **Missing Transcript Files with Completed Status**
   - Files marked as "completed" in the database but actual transcript files missing
   - These caused translation failures with "Transcript text not found" errors
   - Affected 1 file identified in our investigation (a5c69df1-c4f4-4728-9052-7ba17b1a69a0)

2. **Missing Error Records for Transcription Stage**
   - The database had extensive error records for translation stages but none for transcription failures
   - This made it harder to track down exactly which files were failing at the transcription stage

### Solutions Implemented

1. **Diagnosis Tools**
   - Created `check_transcript_file.py` to verify if transcript files exist for a given file ID
   - Developed `debug_transcription.py` to diagnose specific transcription issues by:
     - Testing file integrity with ffprobe
     - Verifying API access
     - Attempting to transcribe a short sample
     - Providing detailed debugging information

2. **Fix Tools**
   - Created `fix_missing_transcripts.py` to reset files with "Transcript text not found" errors
   - Developed `find_all_missing_transcripts.py` to identify any files with missing transcripts
   - These tools reset the files to "not_started" status so they can be properly retranscribed

3. **Documentation & Monitoring Updates**
   - Updated the monitoring guide (docs/MONITORING_GUIDE.md) with detailed information about these issues
   - Added the new tools to CLAUDE.md for easy reference
   - Added troubleshooting sections to README.md
   - Updated the automated monitoring system to catch these issues in the future

### Current Status

- Fixed the file with "Transcript text not found" error by resetting it for retranscription
- Monitoring script running with 10-minute check interval: `monitor_and_restart.py --check-interval 10`
- Pipeline restarted and processing the missing file: `run_full_pipeline.py --languages en,de,he --batch-size 10`
- Overall translation progress is good:
  - English: 85.7% completed
  - German: 85.2% completed  
  - Hebrew: 77.9% completed

## Debugging Steps

If further transcript issues occur:

1. Use `python check_status.py` to see if any errors are being reported
2. Run `python check_transcript_file.py <file_id>` on specific problematic files
3. Debug with `python debug_transcription.py --file-id <file_id>` for deeper analysis
4. Fix missing transcripts with `python fix_missing_transcripts.py --reset`
5. Use the automated monitoring system to detect and restart stalled processes

## Future Improvements

Consider implementing:

1. Regular database integrity checks to catch mismatches between file status and actual files
2. Periodic verification of "completed" files to ensure all expected outputs exist
3. Automated testing of transcription on a small sample before full batch processing
4. More detailed transcription error logging to catch specific API failures