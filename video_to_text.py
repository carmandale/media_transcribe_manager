#!/usr/bin/env python3
"""
Video to Text Transcription Tool
--------------------------------
This script processes video files, extracts their audio,
and transcribes them using ElevenLabs Speech-to-Text API.
It can also generate SRT subtitle files from the transcriptions.
"""

import os
import sys
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv
from io import BytesIO
import tempfile
from tqdm import tqdm
from moviepy.editor import VideoFileClip
from elevenlabs.client import ElevenLabs
import datetime

# Load environment variables
load_dotenv()

# Initialize ElevenLabs client
client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
)


def extract_audio_from_video(video_path, audio_path=None):
    """Extract audio from a video file."""
    print(f"Extracting audio from: {video_path}")
    
    if audio_path is None:
        # Create a temporary file if no output path is provided
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        audio_path = temp_file.name
        temp_file.close()
    
    try:
        # Create a simple progress indicator
        sys.stdout.write("Extracting audio... ")
        sys.stdout.flush()
        
        # Extract audio
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(audio_path, verbose=False, logger=None)
        
        # Indicate completion
        sys.stdout.write("Done\n")
        sys.stdout.flush()
        
        print(f"Audio extracted to: {audio_path}")
        return audio_path
    except Exception as e:
        print(f"Error extracting audio: {e}")
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return None


def transcribe_audio(audio_path, language_code="eng", diarize=True):
    """Transcribe audio using ElevenLabs Speech-to-Text API."""
    print(f"Transcribing audio: {audio_path}")
    
    try:
        # Get file size for progress estimation
        file_size = os.path.getsize(audio_path)
        
        # Show progress bar for reading the file
        progress_bar = tqdm(total=file_size, desc="Preparing audio data", unit="B", unit_scale=True)
        
        audio_data = BytesIO()
        with open(audio_path, 'rb') as audio_file:
            chunk_size = 1024 * 1024  # 1MB chunks
            while True:
                chunk = audio_file.read(chunk_size)
                if not chunk:
                    break
                audio_data.write(chunk)
                progress_bar.update(len(chunk))
        
        progress_bar.close()
        
        # Reset BytesIO position
        audio_data.seek(0)
        
        # Show that we're waiting for the API response
        print("Sending to ElevenLabs API (this may take some time depending on audio length)...")
        transcription_progress = tqdm(desc="Transcribing with ElevenLabs", total=100, bar_format='{desc}: {percentage:3.0f}%|{bar}| {elapsed}<{remaining}')
        
        # Start time for estimation
        start_time = time.time()
        
        # Estimate ~20% of time for API connection
        transcription_progress.update(5)
        
        # Call the API
        transcription = client.speech_to_text.convert(
            file=audio_data,
            model_id="scribe_v1",  # Currently the only model supported
            tag_audio_events=True,  # Tag laughter, applause, etc.
            language_code=language_code,  # Can be set to None for auto-detection
            diarize=diarize,  # Whether to annotate who is speaking
            timestamps_granularity="word"  # Enable word-level timestamps for subtitles
        )
        
        # Update progress to completion
        transcription_progress.n = 100
        transcription_progress.refresh()
        transcription_progress.close()
        
        # Report completion time
        elapsed_time = time.time() - start_time
        print(f"Transcription completed in {elapsed_time:.2f} seconds")
        
        return transcription
    except Exception as e:
        print(f"Error during transcription: {e}")
        return None


def create_srt_subtitles(transcription, max_chars_per_line=40):
    """Convert ElevenLabs transcription to SRT format."""
    if not hasattr(transcription, 'words') or not transcription.words:
        print("Warning: Transcription doesn't contain word-level timestamps needed for subtitles")
        return None
    
    print("Generating SRT subtitles...")
    progress_bar = tqdm(total=len(transcription.words), desc="Creating subtitles", unit="words")
    
    srt_lines = []
    subtitle_index = 1
    current_subtitle = []
    current_chars = 0
    subtitle_start = None
    subtitle_end = None
    current_speaker = None
    
    for word in transcription.words:
        # Get word information
        word_text = word.text
        word_start = word.start
        word_end = word.end
        
        # Get speaker information if available
        speaker = getattr(word, 'speaker', None)
        
        # Initialize the first subtitle
        if subtitle_start is None:
            subtitle_start = word_start
            current_speaker = speaker
        
        # Check if we need to split into a new subtitle line
        # Split conditions: exceeding character limit or speaker changes
        if (current_chars + len(word_text) > max_chars_per_line or 
            (speaker is not None and current_speaker is not None and speaker != current_speaker)):
            
            # Format and add the current subtitle
            subtitle_text = " ".join(current_subtitle)
            if current_speaker is not None:
                subtitle_text = f"Speaker {current_speaker}: {subtitle_text}"
            
            # Format timestamps for SRT (00:00:00,000)
            start_time = format_timestamp_for_srt(subtitle_start)
            end_time = format_timestamp_for_srt(subtitle_end)
            
            srt_lines.append(f"{subtitle_index}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(f"{subtitle_text}")
            srt_lines.append("")  # Empty line between subtitles
            
            # Reset for new subtitle
            subtitle_index += 1
            current_subtitle = [word_text]
            current_chars = len(word_text)
            subtitle_start = word_start
            subtitle_end = word_end
            current_speaker = speaker
        else:
            # Add word to current subtitle
            current_subtitle.append(word_text)
            current_chars += len(word_text) + 1  # +1 for space
            subtitle_end = word_end
        
        # Update progress bar
        progress_bar.update(1)
    
    # Add the last subtitle if there's any content
    if current_subtitle:
        subtitle_text = " ".join(current_subtitle)
        if current_speaker is not None:
            subtitle_text = f"Speaker {current_speaker}: {subtitle_text}"
            
        start_time = format_timestamp_for_srt(subtitle_start)
        end_time = format_timestamp_for_srt(subtitle_end)
        
        srt_lines.append(f"{subtitle_index}")
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(f"{subtitle_text}")
        srt_lines.append("")  # Empty line at the end
    
    # Close progress bar
    progress_bar.close()
    
    return "\n".join(srt_lines)


def format_timestamp_for_srt(seconds):
    """Convert seconds to SRT timestamp format (00:00:00,000)."""
    # Create a timedelta object
    time_obj = datetime.timedelta(seconds=seconds)
    
    # Calculate hours, minutes, seconds
    hours, remainder = divmod(time_obj.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Get milliseconds
    milliseconds = int(time_obj.microseconds / 1000)
    
    # Format the timestamp for SRT
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def process_video(video_path, output_dir=None, language_code="eng", diarize=True, keep_audio=False, generate_subtitles=False):
    """Process a video file: extract audio, transcribe, and save results."""
    
    # Create output directory if it doesn't exist
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Determine output paths
    video_filename = os.path.basename(video_path)
    video_name = os.path.splitext(video_filename)[0]
    
    audio_path = None
    if keep_audio and output_dir:
        audio_path = os.path.join(output_dir, f"{video_name}.mp3")
    
    # Extract audio
    temp_audio_path = extract_audio_from_video(video_path, audio_path)
    if not temp_audio_path:
        return False
    
    # Transcribe audio
    transcription = transcribe_audio(temp_audio_path, language_code, diarize)
    
    # Clean up temporary audio file if we're not keeping it
    if not keep_audio and temp_audio_path != audio_path:
        print(f"Cleaning up temporary audio file: {temp_audio_path}")
        os.remove(temp_audio_path)
    
    if not transcription:
        return False
    
    # Save transcription and subtitles
    if output_dir:
        # Save plain text transcription
        transcript_path = os.path.join(output_dir, f"{video_name}.txt")
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcription.text)
        print(f"Transcription saved to: {transcript_path}")
        
        # Generate and save subtitle file if requested
        if generate_subtitles:
            srt_content = create_srt_subtitles(transcription)
            if srt_content:
                subtitle_path = os.path.join(output_dir, f"{video_name}.srt")
                with open(subtitle_path, 'w', encoding='utf-8') as f:
                    f.write(srt_content)
                print(f"Subtitles saved to: {subtitle_path}")
            else:
                print("Warning: Could not generate subtitles. Word-level timestamps may be missing.")
    else:
        print("\nTranscription:")
        print("=" * 40)
        print(transcription.text)
        print("=" * 40)
    
    return True


def process_directory(input_dir, output_dir, language_code="eng", diarize=True, keep_audio=False, generate_subtitles=False):
    """Process all video files in a directory."""
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    
    # Get all video files
    video_files = []
    for ext in video_extensions:
        video_files.extend(list(Path(input_dir).glob(f"*{ext}")))
    
    if not video_files:
        print(f"No video files found in {input_dir}")
        return
    
    print(f"Found {len(video_files)} video files to process")
    
    # Process each video
    success_count = 0
    for video_path in tqdm(video_files, desc="Processing videos"):
        print(f"\nProcessing: {video_path}")
        if process_video(str(video_path), output_dir, language_code, diarize, keep_audio, generate_subtitles):
            success_count += 1
    
    print(f"Completed: {success_count}/{len(video_files)} videos successfully processed")


def main():
    parser = argparse.ArgumentParser(description="Transcribe video files using ElevenLabs Speech-to-Text API")
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-f', '--file', help="Path to a single video file to transcribe")
    input_group.add_argument('-d', '--directory', help="Path to a directory of video files to transcribe")
    
    # Output options
    parser.add_argument('-o', '--output', help="Directory to save transcriptions (and audio if --keep-audio is used)")
    
    # Transcription options
    parser.add_argument('-l', '--language', default="eng", help="Language code (default: eng) - set to 'auto' for auto-detection")
    parser.add_argument('--no-diarize', action='store_false', dest='diarize', help="Disable speaker diarization")
    parser.add_argument('--keep-audio', action='store_true', help="Save extracted audio files")
    parser.add_argument('--generate-subtitles', action='store_true', help="Generate SRT subtitle files")
    
    args = parser.parse_args()
    
    # Check API key
    if not os.getenv("ELEVENLABS_API_KEY"):
        print("Error: ELEVENLABS_API_KEY not found in environment variables or .env file")
        sys.exit(1)
    
    # Convert 'auto' to None for language auto-detection
    language_code = None if args.language.lower() == 'auto' else args.language
    
    # Process based on input type
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        process_video(args.file, args.output, language_code, args.diarize, args.keep_audio, args.generate_subtitles)
    else:  # Directory mode
        if not os.path.isdir(args.directory):
            print(f"Error: Directory not found: {args.directory}")
            sys.exit(1)
        process_directory(args.directory, args.output, language_code, args.diarize, args.keep_audio, args.generate_subtitles)


if __name__ == "__main__":
    main()
