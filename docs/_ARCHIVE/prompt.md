"Create a new script called 'media_transcribe_manager.py' that builds upon the video_to_text.py functionality to implement a resilient batch transcription system with built-in extensibility for future translation capabilities:

1. Recursive directory traversal that processes the entire media collection

2. Stateful processing with a sqlite database that:
   - Assigns unique IDs to each media file
   - Tracks processing status (pending, in-progress, completed, failed)
   - Records error information for failed files
   - Enables resuming interrupted jobs
   - Includes extensible schema for tracking translation status per language

3. Translation-ready output organization:
   - Create a standardized output structure: output/{fileID}/
   - Within each fileID folder, use language code subfolders: output/{fileID}/{lang}/
   - Store original filename mapping, transcription text, and SRT files
   - For the original language: output/{fileID}/original/{filename}.txt|.srt
   - For future translations: output/{fileID}/{lang_code}/{filename}.txt|.srt
   - Sanitize filenames for cross-platform compatibility

4. Recovery-focused workflow:
   - Implement a retry mode to target only previously failed files
   - Include comprehensive error reporting
   - Maintain checksums to detect file changes/repairs
   - Provide a command-line flag to process only specific status categories (failed, pending)

5. Translation pipeline preparation:
   - Design workflow to separate transcription and translation phases
   - Include metadata to track original language identification
   - Implement hooks for future translation services integration
   - Store intermediate data in a format conducive to batch translation

6. Progress visualization:
   - Generate real-time statistics on processing status
   - Provide ETA for completion of batches
   - Create summary reports for each run

The system should leverage the existing ElevenLabs API integration from video_to_text.py while enhancing it with robust batch processing, state management, and future-proof architecture for the translation phase.

The ElevenLabs API key is already configured in .env."