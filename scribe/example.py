#!/usr/bin/env python3
"""
Example usage of the clean Scribe transcription module.

This demonstrates:
1. Basic transcription
2. Advanced configuration
3. Handling different file types
4. Saving outputs in various formats
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scribe import Transcriber, TranscriptionConfig, transcribe

# Load environment variables
load_dotenv()


def example_basic():
    """Basic transcription example."""
    print("=== Basic Transcription Example ===")
    
    # Get API key from environment
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in environment")
        return
    
    # Example file (you would replace with your actual file)
    file_path = "path/to/your/media.mp4"
    
    try:
        # Simple transcription
        result = transcribe(file_path, api_key)
        
        print(f"Language detected: {result.language}")
        print(f"Confidence: {result.confidence}")
        print(f"Word count: {len(result.words)}")
        print(f"\nTranscript preview:")
        print(result.text[:500] + "..." if len(result.text) > 500 else result.text)
        
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        print("Please update the file_path variable with a real media file")
    except Exception as e:
        print(f"Error: {e}")


def example_advanced():
    """Advanced transcription with custom configuration."""
    print("\n=== Advanced Transcription Example ===")
    
    # Get API key
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in environment")
        return
    
    # Custom configuration
    config = TranscriptionConfig(
        api_key=api_key,
        speaker_detection=True,         # Enable speaker diarization
        speaker_count=5,                # Expected number of speakers
        max_file_size_mb=50,           # Larger file size limit
        max_segment_duration=900,       # 15 minute segments
        auto_detect_language=True,      # Auto-detect language
        max_retries=10,                # More retries for reliability
        api_timeout=600                # 10 minute timeout
    )
    
    # Create transcriber
    transcriber = Transcriber(config)
    
    # Example file
    file_path = Path("path/to/your/media.mp4")
    output_dir = Path("output")
    
    try:
        # Transcribe
        print("Starting transcription...")
        result = transcriber.transcribe_file(file_path)
        
        # Save all outputs
        output_base = output_dir / file_path.stem
        transcriber.save_results(
            result, 
            output_base,
            save_json=True,  # Save detailed JSON
            save_srt=True    # Save SRT subtitles
        )
        
        print(f"Transcription completed!")
        print(f"Files saved to: {output_dir}")
        
        # Show speaker information if available
        if result.speakers:
            print(f"\nSpeakers detected: {len(result.speakers)}")
            for speaker in result.speakers:
                print(f"  - {speaker}")
                
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        print("Please update the file_path variable with a real media file")
    except Exception as e:
        print(f"Error: {e}")


def example_batch():
    """Example of batch processing multiple files."""
    print("\n=== Batch Processing Example ===")
    
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in environment")
        return
    
    # Configure for batch processing
    config = TranscriptionConfig(
        api_key=api_key,
        speaker_detection=True,
        auto_detect_language=True
    )
    
    transcriber = Transcriber(config)
    
    # Example directory with media files
    media_dir = Path("path/to/media/directory")
    output_dir = Path("output/transcripts")
    
    # Supported extensions
    extensions = ['.mp4', '.mp3', '.wav', '.m4a', '.mov', '.avi']
    
    if not media_dir.exists():
        print(f"Media directory not found: {media_dir}")
        print("Please update media_dir with a real directory path")
        return
    
    # Find all media files
    media_files = []
    for ext in extensions:
        media_files.extend(media_dir.glob(f"*{ext}"))
    
    print(f"Found {len(media_files)} media files")
    
    # Process each file
    for file_path in media_files:
        print(f"\nProcessing: {file_path.name}")
        
        try:
            result = transcriber.transcribe_file(file_path)
            
            # Save with organized structure
            output_base = output_dir / file_path.stem
            transcriber.save_results(result, output_base)
            
            print(f"  ✓ Completed - {len(result.words)} words")
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")


def example_verbatim_preservation():
    """Example focused on historical preservation with verbatim accuracy."""
    print("\n=== Historical Preservation Example ===")
    
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in environment")
        return
    
    # Configure for maximum accuracy
    config = TranscriptionConfig(
        api_key=api_key,
        model="scribe_v1",              # Best model for accuracy
        speaker_detection=True,         # Identify speakers
        speaker_count=32,               # Max speakers for interviews
        auto_detect_language=False,     # Specify language if known
        force_language="de",            # e.g., German for interviews
        max_file_size_mb=100,          # Handle larger files
        max_retries=15,                # More retries for critical content
        api_timeout=900                # 15 minute timeout
    )
    
    transcriber = Transcriber(config)
    
    # Example historical interview
    interview_path = Path("path/to/historical_interview.mp4")
    preservation_dir = Path("preservation/transcripts")
    
    try:
        print(f"Transcribing historical content: {interview_path.name}")
        print("Preserving verbatim speech patterns and disfluencies...")
        
        result = transcriber.transcribe_file(interview_path)
        
        # Save all formats for preservation
        output_base = preservation_dir / interview_path.stem
        transcriber.save_results(
            result,
            output_base,
            save_json=True,   # Complete data for archival
            save_srt=True     # Subtitles for accessibility
        )
        
        # Create preservation metadata
        metadata_path = output_base.with_suffix('.metadata.txt')
        metadata = f"""Historical Transcription Metadata
================================
File: {interview_path.name}
Language: {result.language or 'Unknown'}
Duration: {result.duration or 'Unknown'} seconds
Word Count: {len(result.words)}
Speakers: {len(result.speakers)}
Transcription Model: {config.model}
Preserved: Verbatim with speech patterns

Note: This transcription preserves the authentic speech patterns,
including pauses, repetitions, and disfluencies as they are
crucial for historical accuracy.
"""
        metadata_path.write_text(metadata, encoding='utf-8')
        
        print(f"\nPreservation complete!")
        print(f"Files saved to: {preservation_dir}")
        
    except FileNotFoundError:
        print(f"File not found: {interview_path}")
        print("Please update the path with a real historical recording")
    except Exception as e:
        print(f"Error during preservation: {e}")


if __name__ == "__main__":
    # Run examples
    example_basic()
    example_advanced()
    # example_batch()  # Uncomment to run batch example
    # example_verbatim_preservation()  # Uncomment for preservation example