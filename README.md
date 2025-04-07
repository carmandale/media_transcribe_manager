# Video to Text Transcription Tool

This tool processes video files and converts speech to text transcriptions using the ElevenLabs Speech-to-Text API. It can handle single videos or entire directories of videos.

## Features

- Process a single video file or an entire directory of videos
- Extract audio tracks from video files
- Transcribe speech using ElevenLabs' advanced Speech-to-Text API
- Support for multiple languages with auto-detection option
- Speaker diarization (identifying different speakers)
- Audio event tagging (laughter, applause, etc.)
- Save transcriptions as text files

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

1. Create a `.env` file in the project directory with your ElevenLabs API key:

```
ELEVENLABS_API_KEY=your_api_key_here
```

You can get an API key by signing up at [ElevenLabs](https://elevenlabs.io/).

## Usage

### Basic Examples

**Process a single video file:**

```bash
python video_to_text.py -f path/to/video.mp4 -o output_folder
```

**Process all videos in a directory:**

```bash
python video_to_text.py -d path/to/videos_folder -o output_folder
```

### Command-line Options

```
usage: video_to_text.py [-h] (-f FILE | -d DIRECTORY) [-o OUTPUT] [-l LANGUAGE] [--no-diarize] [--keep-audio]

Transcribe video files using ElevenLabs Speech-to-Text API

options:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  Path to a single video file to transcribe
  -d DIRECTORY, --directory DIRECTORY
                        Path to a directory of video files to transcribe
  -o OUTPUT, --output OUTPUT
                        Directory to save transcriptions (and audio if --keep-audio is used)
  -l LANGUAGE, --language LANGUAGE
                        Language code (default: eng) - set to 'auto' for auto-detection
  --no-diarize          Disable speaker diarization
  --keep-audio          Save extracted audio files
```

### Language Codes

The default language is English (`eng`). You can specify other languages using their ISO language codes, or use `auto` for automatic language detection:

```bash
python video_to_text.py -f video.mp4 -o output_folder -l fra  # French
python video_to_text.py -f video.mp4 -o output_folder -l deu  # German
python video_to_text.py -f video.mp4 -o output_folder -l auto # Auto-detect
```

## Example Workflow

1. Set up your environment and API key as described above
2. Place your videos in a directory
3. Run the script:

```bash
python video_to_text.py -d ./my_videos -o ./transcriptions -l auto
```

4. Transcription files will be created in the output directory with the same base name as the video files

## Troubleshooting

- **API Key Issues**: Make sure your ElevenLabs API key is correctly set in the `.env` file
- **Long Videos**: Very long videos might time out during transcription; consider splitting them into smaller segments
- **Audio Quality**: Better audio quality leads to better transcription results
- **File Formats**: Supported video formats include MP4, MOV, AVI, MKV, and WebM

## Notes on ElevenLabs Speech-to-Text

- The service uses the "scribe_v1" model
- Transcriptions include speaker diarization by default (identifies different speakers)
- Audio events like laughter and applause are automatically tagged
- Pricing is based on the duration of audio processed
- Check the [ElevenLabs documentation](https://elevenlabs.io/docs/speech-to-text/overview) for more details

## License

This project is for internal use only.
