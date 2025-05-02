 # One-Off Maintenance Scripts

 This directory contains scripts that were used for one-time maintenance or data cleanup
 tasks. They are not part of the core media transcription pipeline and have been moved
 here for reference and archival purposes.

 ## Scripts Included

 - create_video_symlinks.py
   Create symbolic links for video files matching subtitle naming conventions.
 - manage_videos.py
   Manage video symlinks and optionally copy the output directory to an external drive.
 - rename_files_with_id.py
   Rename media files to include unique file IDs for tracking in the database.
 - rename_remaining_files.py
   Rename leftover media files that were missed in the initial renaming step.
 - process_untranscribed.py
   Re-process files that did not get transcribed during the main pipeline run.
 - retry_extraction.py
   Retry audio extraction for files that previously failed extraction.
 - retry_failed_transcriptions.py
   Retry transcription for files that previously failed in the transcription step.
 - verify_and_fix_status.py
   Verify and correct inconsistencies between database records and filesystem state.

 ## Usage

 To run any of these scripts, ensure you are in the project root and that the
 project dependencies are installed. Then invoke:

 ```bash
 python scripts/one_off/<script_name>.py --help
 ```