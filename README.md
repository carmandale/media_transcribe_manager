# Media Transcription and Translation Tool

This advanced tool processes audio and video files by automatically transcribing content using ElevenLabs, translating transcripts (currently from German to English and Hebrew), and producing organized outputs including SRT subtitle files.

## Features

- **Core Functionality**:
  - Recursively scan directories for audio/video files
  - Handle complex filenames (Unicode, special characters)
  - Extract audio from video files
  - Transcribe audio using ElevenLabs Scribe v1
  - Translate transcripts to multiple languages
  - Generate SRT subtitle files for all languages
  - Track processing states in a database
  - Produce detailed reports
  - Support resumption of interrupted processes

- **Enhanced Features**:
  - Parallel processing via worker pool
  - Progress tracking and detailed reporting
  - Robust error handling and recovery
  - Multiple translation providers support (DeepL, Google, Microsoft)

## Installation

### Using `uv` (Recommended)

[`uv`](https://github.com/astral-sh/uv) is a much faster alternative to pip/virtualenv for Python package management.

1. Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone or download this repository and navigate to the project directory

3. Create and activate a virtual environment:

```bash
uv venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows
```

4. Install dependencies:

```bash
uv pip install -r requirements.txt
```

### Using Traditional `venv`

If you prefer using the standard Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows
pip install -r requirements.txt
```

## Configuration

1. Create a `.env` file in the project directory with your API keys:

```
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
DEEPL_API_KEY=your_deepl_api_key_here  # Optional for translations
MS_TRANSLATOR_KEY=your_ms_key_here     # Optional for translations
```

You can get an ElevenLabs API key by signing up at [ElevenLabs](https://elevenlabs.io/).

2. Alternatively, you can create a configuration file (YAML or JSON) with all settings:

```yaml
output_directory: "./output"
database_file: "./media_tracking.db"
log_file: "./media_processor.log"
log_level: "INFO"
workers: 4
extract_audio_format: "mp3"
extract_audio_quality: "192k"
elevenlabs:
  api_key: "your_elevenlabs_api_key_here"
  model: "scribe_v1"
  speaker_detection: true
  speaker_count: 32
deepl:
  api_key: "your_deepl_api_key_here"
  formality: "default"
  batch_size: 5000
media_extensions:
  audio: [".mp3", ".wav", ".m4a", ".aac", ".flac"]
  video: [".mp4", ".avi", ".mov", ".mkv", ".webm"]
```

## Usage

### Main Tool

The new media processor tool provides a comprehensive interface for processing audio and video files:

```bash
python media_processor.py -d /path/to/media/directory -o ./output
```

### Command-line Options

```
usage: media_processor.py [-h] [-d DIRECTORY | -f FILE | -r] [--status {pending,in-progress,failed,completed}]
                         [--extract-only] [--transcribe-only] [--translate-only TRANSLATE_ONLY]
                         [--workers WORKERS] [--source-lang SOURCE_LANG]
                         [--formality {default,more,less}] [--limit LIMIT] [--test]
                         [--dry-run] [--force] [-o OUTPUT] [--report REPORT] [--log LOG]
                         [--log-level {DEBUG,INFO,WARNING,ERROR}] [--config CONFIG]
                         [--save-config SAVE_CONFIG] [--db DB] [--reset-db]
                         [--list-files] [--file-status FILE_STATUS]

Process media files by transcribing and translating content
```

#### Input Options:
- `-d DIRECTORY` - Process all media in this directory (recursively)
- `-f FILE` - Process a single file
- `-r` - Retry previously failed files
- `--status STATUS` - Filter by status (pending, in-progress, failed, completed)

#### Processing Options:
- `--extract-only` - Only extract audio, don't transcribe
- `--transcribe-only` - Only transcribe, don't translate
- `--translate-only LANGS` - Only translate to specified language(s), comma-separated
- `--workers N` - Number of parallel workers
- `--source-lang LANG` - Source language code (default: auto-detect)
- `--formality {default,more,less}` - Translation formality level

#### Control Options:
- `--limit N` - Process only first N files found
- `--test` - Quick test with only 3 files
- `--dry-run` - Show what would be processed without processing
- `--force` - Force reprocessing of already completed items

#### Output Options:
- `-o, --output DIR` - Base output directory (default: ./output)
- `--report FILE` - Save processing report to file
- `--log FILE` - Log file location
- `--log-level {DEBUG,INFO,WARNING,ERROR}` - Logging level

#### Configuration:
- `--config FILE` - Load configuration from YAML/JSON file
- `--save-config FILE` - Save current settings to config file

#### Database Options:
- `--db FILE` - SQLite database file (default: ./media_tracking.db)
- `--reset-db` - Reset the database (caution!)
- `--list-files` - List all tracked files and status
- `--file-status ID` - Show detailed status for a specific file ID

### Example Workflows

#### Complete Processing Pipeline:
```bash
# Process all videos in a directory with default settings
python media_processor.py -d /path/to/videos -o ./output

# Quick test with 3 files only
python media_processor.py -d /path/to/videos --test

# Process a directory and save a detailed report
python media_processor.py -d /path/to/videos -o ./output --report ./report.json
```

#### Phased Processing:
```bash
# Step 1: Extract audio only
python media_processor.py -d /path/to/videos --extract-only

# Step 2: Transcribe the extracted audio
python media_processor.py --transcribe-only

# Step 3: Translate to specific languages
python media_processor.py --translate-only en,he
```

#### Status Management:
```bash
# List all tracked files
python media_processor.py --list-files

# Show files with failed status
python media_processor.py --list-files --status failed

# View detailed status for a specific file
python media_processor.py --file-status 3fd8a920-7c2e-4d0b-b8f5-8c9bce35e0a2

# Retry failed files
python media_processor.py -r
```

## Legacy Tools

For simpler use cases, the original video-to-text tool is still available:

```bash
python video_to_text.py -f path/to/video.mp4 -o output_folder
```

See the legacy options with:
```bash
python video_to_text.py -h
```

## Project Structure

The project is organized into modular components:

- `media_processor.py` - Main controller script
- `db_manager.py` - Database operations and state tracking
- `file_manager.py` - File operations and metadata handling
- `transcription.py` - Audio transcription using ElevenLabs
- `translation.py` - Text translation between languages
- `worker_pool.py` - Parallel processing management
- `reporter.py` - Report generation
- `retry_extraction.py` - Tool for retrying failed extractions
- `generate_report.py` - Standalone reporting tool

## Database Schema

The system uses an SQLite database (`media_tracking.db` by default) with the following tables:

### Main Tables

- **media_files**: Tracks all discovered media files
  - `file_id`: Primary key (UUID)
  - `original_path`: Original file path
  - `file_name`: Extracted file name
  - `file_size`: Size in bytes
  - `media_type`: "audio" or "video"
  - `duration`: Duration in seconds
  - `timestamp`: When the file was added

- **processing_status**: Tracks the processing status of each file
  - `file_id`: Foreign key to media_files
  - `status`: Overall status (pending, in-progress, failed, completed)
  - `extraction_status`: Audio extraction status
  - `transcription_status`: Transcription status
  - `translation_status_en`: English translation status
  - `translation_status_he`: Hebrew translation status
  - `language`: Detected language code
  - `language_confidence`: Confidence score for language detection
  - `last_updated`: Timestamp of last status update

- **errors**: Records detailed error information
  - `error_id`: Primary key (UUID)
  - `file_id`: Foreign key to media_files
  - `process_stage`: Which stage failed (extraction, transcription, translation)
  - `error_message`: Short error description
  - `error_details`: Detailed error information
  - `timestamp`: When the error occurred

- **output_files**: Tracks generated output files
  - `output_id`: Primary key (UUID)
  - `file_id`: Foreign key to media_files
  - `output_type`: Type of output (audio, transcript, translation, subtitle)
  - `language`: Language code if applicable
  - `file_path`: Path to the output file
  - `timestamp`: When the output was generated

### Database Utility Commands

Reset or create a new database:
```bash
python db_manager.py --reset
```

Export database schema:
```bash
sqlite3 media_tracking.db .schema > schema.sql
```

## Error Management and Reporting

### Generating Reports

The system includes a dedicated reporting tool that provides detailed insights:

```bash
# Display a summary of processing status and recent errors
python generate_report.py --summary

# Generate a JSON report file
python generate_report.py --output report.json

# Generate a YAML report file
python generate_report.py --output report.yaml

# Generate a text report file
python generate_report.py --output report.txt
```

The `--summary` flag shows:
- File count by status
- Media type distribution
- Language distribution
- Content statistics (duration, size)
- Stage completion statistics
- Recent errors (last 24 hours by default)

### Error Handling and Debugging

#### View Error Details

Error reports now filter by recency (last 24 hours by default) to prevent confusion with historical errors. To see all historical errors:

```bash
python -c "from reporter import Reporter; from db_manager import DatabaseManager; r = Reporter(DatabaseManager('./media_tracking.db'), {}); r.display_error_analysis(recent_only=False)"
```

To see only recent errors (last 24 hours):

```bash
python -c "from reporter import Reporter; from db_manager import DatabaseManager; r = Reporter(DatabaseManager('./media_tracking.db'), {}); r.display_error_analysis(recent_only=True)"
```

#### Clear Error Records

Clear all error records (useful after resolving known issues):

```bash
python -c "from db_manager import DatabaseManager; db = DatabaseManager('./media_tracking.db'); success, count = db.clear_errors(); print(f'Cleared {count} error records')"
```

#### Clear Errors for Specific Files

Clear errors for a specific file:

```bash
python -c "from db_manager import DatabaseManager; db = DatabaseManager('./media_tracking.db'); db.clear_file_errors('FILE_ID_HERE')"
```

### Retry Failed Extractions

The system includes a dedicated tool for retrying failed extractions and transcriptions:

```bash
# Preview which failed files would be processed (without actually processing them)
python retry_extraction.py --dry-run

# Retry a specific failed file by UUID
python retry_extraction.py --file-id UUID_OF_FAILED_FILE

# Retry all failed files
python retry_extraction.py

# Retry a limited number of failed files
python retry_extraction.py --limit 10

# Process in batches (good for API rate limits)
python retry_extraction.py --batch-size 5

# Use a specific source language
python retry_extraction.py --source-language deu
```

When a retry succeeds, the error records for that file are automatically cleared to prevent confusion in error reporting.

### Handling Large Files and Timeouts

For large audio/video files (over 1GB), the ElevenLabs API may require extended processing time. The system now automatically configures a 5-minute (300 second) timeout for API requests to handle these large files.

If you experience timeout issues with extremely large files, you can adjust the timeout in the `TranscriptionManager` class in `transcription.py`:

```python
# In transcription.py
request_options = {
    "timeout_in_seconds": 300  # Increase this value for larger files if needed
}
```

## Special Processing Scripts

### Processing Untranscribed Files

The `process_untranscribed.py` script is designed to specifically target files that have never been transcribed (those with a transcription status of 'not_started').

```bash
# Process untranscribed files (default up to 183 files)
python process_untranscribed.py --batch-size 10

# Process with a specific limit
python process_untranscribed.py --limit 50 --batch-size 10

# Dry run to see which files would be processed
python process_untranscribed.py --dry-run
```

**Current Processing Run (Started: April 8, 2025)**
- Target: Files with transcription_status = 'not_started'
- Total untranscribed files identified: 276
- Current batch processing: 183 files
- Batch size: 10 files
- Estimated completion time: ~4.5 hours
- Command used: `python process_untranscribed.py --batch-size 10`

### Retrying Failed Files

The system includes a dedicated tool for retrying failed extractions and transcriptions:

```bash
# Preview which failed files would be processed (without actually processing them)
python retry_extraction.py --dry-run

# Retry a specific failed file by UUID
python retry_extraction.py --file-id UUID_OF_FAILED_FILE

# Retry all failed files
python retry_extraction.py

# Retry a limited number of failed files
python retry_extraction.py --limit 10

# Process in batches (good for API rate limits)
python retry_extraction.py --batch-size 5

# Use a specific source language
python retry_extraction.py --source-language deu
```

When a retry succeeds, the error records for that file are automatically cleared to prevent confusion in error reporting.

## Common Workflow for Error Resolution

1. **Identify issues**: `python generate_report.py --summary`
2. **Preview failed files**: `python retry_extraction.py --dry-run`
3. **Test fix on a single file**: `python retry_extraction.py --file-id UUID_OF_FAILED_FILE`
4. **Retry all failed files**: `python retry_extraction.py`
5. **Check results**: `python generate_report.py --summary`

## Troubleshooting

- **API Key Issues**: Make sure your API keys are correctly set in the `.env` file
- **Database Errors**: If you encounter database corruption, try resetting it with `--reset-db`
- **Processing Failures**: Use `--list-files --status failed` to identify failed files, then retry with `retry_extraction.py`
- **Memory Errors**: For large video files, the system uses FFmpeg for extraction to prevent memory issues
- **API Rate Limiting**: Use batch processing with delays between batches to avoid hitting API limits
- **Timeout Errors**: Large files may cause API timeouts. The system now uses a 5-minute timeout by default, which should handle most files
- **Stale Error Records**: If reports show errors but files process correctly, the errors might be historical - they are now automatically cleared on successful retries

## Notes on ElevenLabs Scribe

- The service uses the "scribe_v1" model for transcription
- Transcriptions include speaker diarization when enabled
- Audio events like laughter and applause are automatically tagged
- Pricing is based on the duration of audio processed
- Check the [ElevenLabs documentation](https://elevenlabs.io/docs/speech-to-text/overview) for more details

## License

This project is for internal use only.
