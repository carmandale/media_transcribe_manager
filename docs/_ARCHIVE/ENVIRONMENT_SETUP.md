# Environment Setup Guide

This document explains how to properly set up environment variables for the transcription and translation pipeline.

## Required API Keys

The pipeline requires several API keys to function properly:

- **ELEVENLABS_API_KEY**: For audio transcription via ElevenLabs Scribe API
- **OPENAI_API_KEY**: For Hebrew translations and quality evaluations
- **DEEPL_API_KEY**: For German translations
- **MS_TRANSLATOR_KEY**: For Microsoft Translator (optional)

## Setting Up Environment Variables

### Option 1: .env File (Recommended)

Create a `.env` file in the project root directory with your API keys:

```
ELEVENLABS_API_KEY=your_elevenlabs_key_here
OPENAI_API_KEY=your_openai_key_here
DEEPL_API_KEY=your_deepl_key_here
MS_TRANSLATOR_KEY=your_microsoft_key_here
MS_TRANSLATOR_LOCATION=eastus
```

⚠️ **IMPORTANT: Security Best Practices**

- **NEVER commit API keys to Git** - make sure `.env` is in your `.gitignore` file
- **NEVER hardcode API keys** in source code files
- **ALWAYS use environment variables** to access sensitive credentials
- **AVOID printing full API keys** in logs (use truncated versions like `key[:5]...key[-5:]`)

### Option 2: System Environment Variables

Set environment variables at the system level:

```bash
# Linux/macOS
export ELEVENLABS_API_KEY=your_elevenlabs_key_here
export OPENAI_API_KEY=your_openai_key_here
export DEEPL_API_KEY=your_deepl_key_here

# Windows (Command Prompt)
set ELEVENLABS_API_KEY=your_elevenlabs_key_here
set OPENAI_API_KEY=your_openai_key_here
set DEEPL_API_KEY=your_deepl_key_here
```

## New Environment Loading Utility

To ensure API keys are properly loaded, we've created a `load_env.py` utility:

```bash
# Load environment variables
python load_env.py
```

This will:
1. Look for a `.env` file in the project root
2. Load variables from the file if it exists
3. Verify that critical API keys are set
4. Output the status of each key

## Using the Environment-Aware Scripts

### For Processing Individual Files

```bash
# Process a specific file with environment loading
python run_transcription_pipeline.py --file-id YOUR_FILE_ID
```

### For Running the Full Pipeline

```bash
# Run the full pipeline with environment loading
python run_transcription_pipeline.py --restart --batch-size 10 --languages en,de,he
```

### For Monitoring

```bash
# Start monitoring with environment loading
python run_transcription_pipeline.py --monitor --interval 10
```

## Troubleshooting Environment Issues

If you encounter API errors like:

```
API connection failed: 'ElevenLabs' object has no attribute 'info'
```

Try the following:

1. Verify your API keys are correct:
   ```bash
   python load_env.py
   ```

2. Check if environment variables are being properly loaded:
   ```bash
   python -c "import os; print(os.getenv('ELEVENLABS_API_KEY'))"
   ```

3. Test API connectivity directly:
   ```bash
   python test_api.py
   ```

4. For transcription issues, test direct transcription:
   ```bash
   python direct_transcribe.py
   ```

## Important Scripts for Environment Management

- `load_env.py`: Utility for loading and verifying environment variables
- `run_transcription_pipeline.py`: Environment-aware script for running pipeline operations
- `direct_transcribe.py`: Direct test of transcription API without database dependencies
- `test_api.py`: Test ElevenLabs API connectivity

## Running in Production

For production environments, always ensure environment variables are loaded when starting any part of the pipeline. The `run_transcription_pipeline.py` script handles this automatically for you:

```bash
# Start complete setup (pipeline and monitoring)
python run_transcription_pipeline.py --restart --monitor --interval 10
```