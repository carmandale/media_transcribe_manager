# Scribe Architecture Overview

## System Design

Scribe is designed as a modular pipeline system for processing historical interview recordings. The architecture emphasizes:

1. **Accuracy over Polish**: Preserving authentic speech patterns and hesitations
2. **Scalability**: Parallel processing with worker pools
3. **Reliability**: Error recovery and progress tracking
4. **Maintainability**: Clean module separation

## Core Components

### 1. Database Layer (`scribe/database.py`)
- Thread-safe SQLite interface with connection pooling
- Tracks file metadata, processing status, and quality evaluations
- Provides transaction support and error logging

### 2. Transcription Module (`scribe/transcribe.py`)
- Integrates with ElevenLabs Scribe API
- Handles audio extraction from video files
- Produces verbatim transcripts with speaker diarization
- Manages rate limiting and retries

### 3. Translation Module (`scribe/translate.py`)
- Multi-provider support (DeepL, Microsoft, OpenAI)
- Special Hebrew routing (DeepL doesn't support Hebrew)
- Preserves speech patterns and historical context
- Handles idiomatic expressions and cultural references

### 4. Evaluation Module (`scribe/evaluate.py`)
- Uses GPT-4 for quality assessment
- Weighted scoring emphasizing speech pattern fidelity (30%)
- Evaluates content accuracy, cultural context, and reliability
- Produces scores suitable for research validation

### 5. Pipeline Orchestrator (`scribe/pipeline.py`)
- Coordinates the full workflow
- Manages parallel processing with worker pools
- Handles error recovery and retry logic
- Provides progress tracking

### 6. CLI Interface (`scribe_cli.py`)
- User-friendly command-line interface
- Commands for each pipeline stage
- Status monitoring and troubleshooting tools
- Batch processing capabilities

## Data Flow

```
1. Media Files (MP3/MP4/etc.)
   ↓
2. File Discovery & Registration
   → Database: media_files table
   ↓
3. Transcription (ElevenLabs Scribe)
   → Output: {file_id}_transcript.txt
   → Database: processing_status.transcription_status
   ↓
4. Translation (Multi-provider)
   → Output: {file_id}_en.txt, {file_id}_de.txt, {file_id}_he.txt
   → Database: processing_status.translation_*_status
   ↓
5. Quality Evaluation (GPT-4)
   → Database: quality_evaluations table
   ↓
6. Final Output in output/{file_id}/
```

## Technology Stack

- **Language**: Python 3.13
- **Database**: SQLite with thread-safe pooling
- **Package Manager**: uv (not pip/venv)
- **APIs**: 
  - ElevenLabs (transcription)
  - DeepL (EN/DE translation)
  - Microsoft Translator (Hebrew)
  - OpenAI GPT-4 (evaluation)

## Design Decisions

### Why SQLite?
- Single-file database perfect for this use case
- No server setup required
- Excellent for read-heavy workloads
- Built-in thread safety with proper configuration

### Why Multiple Translation Providers?
- DeepL: Best for European languages
- Microsoft: Reliable Hebrew support
- OpenAI: Fallback and evaluation

### Why Separate Tables?
- Clean separation of concerns
- Easier to extend without schema changes
- Better normalization

## Current Limitations

1. **SQL Query Mismatch**: Some code expects different table structure (being fixed)
2. **Single Database**: Could benefit from read replicas for large scale
3. **File-based Output**: Could move to object storage for better scalability

## Future Considerations

1. **API Service**: REST API for web interface
2. **Cloud Storage**: S3/GCS for media and outputs
3. **Queue System**: Redis/RabbitMQ for better job management
4. **Monitoring**: Prometheus/Grafana for production deployments