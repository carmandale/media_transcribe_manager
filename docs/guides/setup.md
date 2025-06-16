# Setup Guide

This guide will help you set up Scribe for first use.

## Prerequisites

- Python 3.11 or higher
- `uv` package manager (not pip/venv)
- API keys for transcription and translation services

## Installation

### 1. Clone or Download the Repository

```bash
git clone <repository-url>
cd scribe
```

### 2. Install Dependencies

**Important**: This project uses `uv`, not standard pip/venv.

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -r requirements.txt
```

### 3. Configure API Keys

Create a `.env` file in the project root:

```env
# Required for transcription
ELEVENLABS_API_KEY=your_elevenlabs_key_here

# Required for translation
DEEPL_API_KEY=your_deepl_key_here
MS_TRANSLATOR_KEY=your_microsoft_key_here
OPENAI_API_KEY=your_openai_key_here

# Optional settings
DATABASE_PATH=media_tracking.db
OUTPUT_PATH=output/
```

#### Getting API Keys:

- **ElevenLabs**: Sign up at [elevenlabs.io](https://elevenlabs.io)
- **DeepL**: Get API key from [deepl.com/pro-api](https://www.deepl.com/pro-api)
- **Microsoft Translator**: Azure Cognitive Services
- **OpenAI**: Get from [platform.openai.com](https://platform.openai.com)

### 4. Verify Installation

```bash
# Test the CLI
uv run python scribe_cli.py version

# Test Hebrew routing
uv run python test_hebrew_fix.py
```

## Database Setup

The SQLite database (`media_tracking.db`) is created automatically on first use. No manual setup required.

## Directory Structure

The following directories will be created automatically:
- `output/` - Processed files
- `logs/` - Application logs

## Known Issues

**Hebrew Evaluation Error**: The evaluation command currently has issues. See [Hebrew Evaluation Fix PRD](../PRDs/hebrew-evaluation-fix.md) for details.

## Next Steps

- Follow the [Usage Guide](usage.md) to start processing files
- Read about [Evaluation](evaluation.md) for quality control
- Check [Troubleshooting](troubleshooting.md) if you encounter issues