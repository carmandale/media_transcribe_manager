#!/usr/bin/env python3
"""
Single File Transcription Tool
------------------------------
This script processes a single video file and generates an English transcript,
saving the output in the same directory as the source file.
"""

import os
import sys
import argparse
from pathlib import Path
from video_to_text import extract_audio_from_video, transcribe_audio

def transcribe_single_file(video_path):
    """
    Process a single video file and save the transcript in the same directory.
    
    Args:
        video_path (str): Path to the video file
    
    Returns:
        str: Path to the transcript file if successful, None otherwise
    """
    video_path = Path(video_path)
    
    # Verify file exists
    if not video_path.exists():
        print(f"Error: File not found - {video_path}")
        return None
    
    # Define output path (same directory as input with .txt extension)
    output_path = video_path.with_suffix(".txt")
    
    print(f"Processing video: {video_path}")
    
    # Extract audio to temporary file
    audio_path = extract_audio_from_video(str(video_path))
    if not audio_path:
        print("Error: Failed to extract audio")
        return None
    
    # Transcribe the audio (English language, with speaker diarization)
    transcription = transcribe_audio(audio_path, language_code="eng", diarize=True)
    if not transcription:
        print("Error: Failed to transcribe audio")
        # Clean up temporary audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return None
    
    # Save the transcription to output file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(transcription.text)
        print(f"Transcript saved to: {output_path}")
    except Exception as e:
        print(f"Error saving transcript: {e}")
        output_path = None
    
    # Clean up temporary audio file
    if os.path.exists(audio_path):
        os.remove(audio_path)
        print("Temporary audio file removed")
    
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Transcribe a single video file and save output in the same directory")
    parser.add_argument("video_path", help="Path to the video file to transcribe")
    
    args = parser.parse_args()
    
    result = transcribe_single_file(args.video_path)
    if result:
        print("Transcription completed successfully")
        return 0
    else:
        print("Transcription failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
