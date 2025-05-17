# Parallel Processing Guide

This document explains how to use the parallel processing scripts to significantly accelerate transcription and translation.

## Overview

The parallel processing system consists of three main components:

1. **Parallel Transcription**: Processes multiple audio files for transcription simultaneously
2. **Parallel Translation**: Processes multiple files for translation in a specific language simultaneously
3. **Combined Parallel Runner**: Orchestrates both transcription and translation processes in parallel

These tools dramatically improve performance by:
- Processing multiple files at the same time
- Keeping system resources efficiently utilized
- Handling transcription and translation as separate parallel workflows

## Quick Start

To run the full parallel processing pipeline with default settings:

```bash
python run_parallel_processing.py
```

This will:
- Launch 5 concurrent transcription workers
- Launch 5 concurrent translation workers for each language (en, de, he)
- Process all pending files

## Parallel Transcription

The `parallel_transcription.py` script processes audio files in parallel:

```bash
# Process with 8 concurrent workers
python parallel_transcription.py --workers 8

# Process only 20 files
python parallel_transcription.py --workers 5 --batch-size 20
```

### Performance Notes

- Each transcription job requires significant API bandwidth
- Testing indicates 5-10 concurrent transcription jobs is optimal
- Very large files (>50MB) may take longer to process

## Parallel Translation

The `parallel_translation.py` script processes translation for a specific language in parallel:

```bash
# Process English translations with 10 concurrent workers
python parallel_translation.py --language en --workers 10

# Process German translations with batch limit
python parallel_translation.py --language de --workers 8 --batch-size 30

# Process Hebrew translations
python parallel_translation.py --language he --workers 8
```

### Performance Notes

- DeepL API (used for English/German) generally handles concurrent requests well
- OpenAI API (used for Hebrew) may have rate limiting with too many concurrent requests
- Starting with 5-8 workers per language is recommended

## Combined Parallel Processing

The `run_parallel_processing.py` script orchestrates both transcription and translation in parallel:

```bash
# Custom worker configuration
python run_parallel_processing.py --transcription-workers 8 --translation-workers 5

# Process specific languages only
python run_parallel_processing.py --languages en,de

# Set batch sizes
python run_parallel_processing.py --transcription-batch 20 --translation-batch 30
```

### Command-line Options

- `--transcription-workers N`: Number of concurrent transcription workers (default: 5)
- `--translation-workers N`: Number of concurrent translation workers per language (default: 5)
- `--transcription-batch N`: Number of files to transcribe (default: all pending)
- `--translation-batch N`: Number of files to translate per language (default: all pending)
- `--languages LANGS`: Languages to process as comma-separated list (default: en,de,he)

## Performance Optimization

For optimal performance on a system with 128GB RAM:

```bash
# High performance configuration
python run_parallel_processing.py --transcription-workers 10 --translation-workers 8
```

For systems with less RAM (e.g., 16GB):

```bash
# Lower resource configuration
python run_parallel_processing.py --transcription-workers 3 --translation-workers 2
```

## Logging and Monitoring

Each script creates detailed logs:

- `parallel_transcription.log`: Logs from transcription processes
- `parallel_translation.log`: Logs from translation processes
- `parallel_processing.log`: Logs from the orchestration script

You can monitor progress in real-time with:

```bash
# Follow transcription logs
tail -f parallel_transcription.log

# Follow translation logs
tail -f parallel_translation.log
```

## Troubleshooting

If you encounter issues:

1. **API Rate Limiting**: Reduce the number of workers
2. **Memory Issues**: Reduce batch sizes and worker counts
3. **Database Locking**: Ensure only one process accesses the database at once (the scripts handle this)
4. **Missing Environment Variables**: Ensure all required API keys are in your `.env` file

## Resume After Interruption

The parallel processing system is designed to pick up where it left off. If a process is interrupted, simply run the command again and it will continue with the remaining files.