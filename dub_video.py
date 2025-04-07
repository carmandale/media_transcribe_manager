#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Video Dubbing Tool
-----------------
This script processes video files and creates dubbed versions in different languages
using the ElevenLabs Dubbing API.
"""

import os
import sys
import time
import argparse
import requests
from pathlib import Path
from typing import Optional
from io import BytesIO

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# Load environment variables
load_dotenv()

# Retrieve the API key
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    raise ValueError(
        "ELEVENLABS_API_KEY environment variable not found. "
        "Please set the API key in your .env file."
    )

client = ElevenLabs(api_key=ELEVENLABS_API_KEY)


def download_dubbed_file(dubbing_id: str, language_code: str, output_path: str) -> str:
    """
    Downloads the dubbed file for a given dubbing ID and language code.

    Args:
        dubbing_id: The ID of the dubbing project.
        language_code: The language code for the dubbing.
        output_path: The path where the output file should be saved.

    Returns:
        The file path to the downloaded dubbed file.
    """
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as file:
        for chunk in client.dubbing.get_dubbed_file(dubbing_id, language_code):
            file.write(chunk)

    return output_path


def wait_for_dubbing_completion(dubbing_id: str) -> bool:
    """
    Waits for the dubbing process to complete by periodically checking the status.

    Args:
        dubbing_id (str): The dubbing project id.

    Returns:
        bool: True if the dubbing is successful, False otherwise.
    """
    MAX_ATTEMPTS = 120  # Increased from 60 to 120 based on ElevenLabs docs example
    CHECK_INTERVAL = 10  # In seconds

    print(f"Waiting for dubbing to complete (timeout: {MAX_ATTEMPTS * CHECK_INTERVAL / 60:.1f} minutes)...")
    
    for attempt in range(MAX_ATTEMPTS):
        try:
            metadata = client.dubbing.get_dubbing_project_metadata(dubbing_id)
            status = metadata.status
            
            if status == "dubbed":
                print(f"Dubbing completed successfully after {attempt * CHECK_INTERVAL} seconds")
                return True
            elif status == "dubbing":
                print(f"Dubbing in progress... ({attempt + 1}/{MAX_ATTEMPTS})")
                time.sleep(CHECK_INTERVAL)
            else:
                print(f"Dubbing failed or ended with unexpected status: {status}")
                if hasattr(metadata, 'error_message') and metadata.error_message:
                    print(f"Error message: {metadata.error_message}")
                return False
                
        except Exception as e:
            print(f"Error checking dubbing status: {str(e)}")
            time.sleep(CHECK_INTERVAL)
    
    print(f"Dubbing process timed out after {MAX_ATTEMPTS * CHECK_INTERVAL} seconds")
    return False


def create_dub_from_file(
    input_file_path: str,
    output_file_path: str,
    source_language: str,
    target_language: str,
    num_speakers: int = 2,
    disable_watermark: bool = True
) -> Optional[str]:
    """
    Dubs a video file from one language to another and saves the output.

    Args:
        input_file_path (str): The file path of the video to dub.
        output_file_path (str): The path where the output file should be saved.
        source_language (str): The language of the input file.
        target_language (str): The target language to dub into.
        num_speakers (int): Number of speakers to detect (default: 2)
        disable_watermark (bool): Whether to disable watermark (default: True)

    Returns:
        Optional[str]: The file path of the dubbed file or None if operation failed.
    """
    input_path = Path(input_file_path)
    if not input_path.exists():
        print(f"Error: The input file does not exist: {input_file_path}")
        return None
    
    # Check file size - ElevenLabs API limit is 1GB
    file_size_bytes = input_path.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)
    MAX_FILE_SIZE_MB = 1024  # 1GB limit for the ElevenLabs API
    
    if file_size_mb > MAX_FILE_SIZE_MB:
        print(f"Warning: File size ({file_size_mb:.2f} MB) exceeds the ElevenLabs API limit of 1GB.")
        print("ElevenLabs documentation recommends either:")
        print("1. Compress the file to reduce size while maintaining acceptable quality.")
        print("2. Split the video into smaller segments, each less than 1GB.")
        print("Processing will attempt to continue, but may fail due to API limitations.")
        print("See ElevenLabs documentation for more details: https://elevenlabs.io/docs/capabilities/dubbing")
        
        # Ask if the user wants to proceed anyway
        try:
            response = input("Do you want to proceed anyway? (y/n): ")
            if response.lower() != 'y':
                print("Dubbing cancelled.")
                return None
        except:
            # If running in non-interactive mode, continue but warn
            print("Running in non-interactive mode, attempting to continue despite file size warning.")
    
    file_format = "video/mp4"  # Assuming MP4 format based on file extension
    
    print(f"Starting dubbing process for: {input_path.name}")
    print(f"File size: {file_size_mb:.2f} MB")
    print(f"Source language: {source_language}, Target language: {target_language}")
    print(f"Number of speakers: {num_speakers}, Watermark disabled: {disable_watermark}")
    
    # Implement retry logic for API calls
    MAX_RETRIES = 3
    for retry in range(MAX_RETRIES):
        try:
            # Read the file contents first
            print("Reading file content...")
            with open(input_path, "rb") as f:
                file_content = f.read()
            
            print("Sending to ElevenLabs API (this may take a while)...")
            response = client.dubbing.dub_a_video_or_an_audio_file(
                file=("input_video.mp4", file_content, file_format),
                target_lang=target_language,
                mode="automatic",
                source_lang=source_language,
                num_speakers=num_speakers,
                watermark=not disable_watermark,
                # Set a longer timeout for large files
                _request_timeout=600  # 10 minutes timeout
            )

            dubbing_id = response.dubbing_id
            print(f"Dubbing job created with ID: {dubbing_id}")
            
            if wait_for_dubbing_completion(dubbing_id):
                print("Dubbing completed successfully!")
                output_file_path = download_dubbed_file(dubbing_id, target_language, output_file_path)
                return output_file_path
            else:
                return None
                
        except requests.exceptions.Timeout:
            print(f"Timeout during API call, retrying ({retry+1}/{MAX_RETRIES})...")
            if retry == MAX_RETRIES - 1:
                print("Maximum retries reached. Consider splitting the file into smaller segments.")
                return None
            time.sleep(10)  # Wait before retrying
            
        except Exception as e:
            print(f"Error during dubbing process: {str(e)}")
            if retry < MAX_RETRIES - 1:
                print(f"Retrying ({retry+1}/{MAX_RETRIES})...")
                time.sleep(10)  # Wait before retrying
            else:
                print("Maximum retries reached.")
                return None
    
    return None


def process_video(
    video_path: str, 
    output_dir: str = None, 
    source_language: str = "en", 
    target_language: str = "en",
    num_speakers: int = 2,
    disable_watermark: bool = True,
    output_filename: str = None
) -> Optional[str]:
    """
    Process a video file: create a dubbed version in the target language.
    
    Args:
        video_path (str): Path to the video file
        output_dir (str): Directory to save the output file (defaults to './output')
        source_language (str): Source language code
        target_language (str): Target language code
        num_speakers (int): Number of speakers to detect
        disable_watermark (bool): Whether to disable watermark
        output_filename (str): Custom output filename (without extension)
        
    Returns:
        Optional[str]: Path to the dubbed video or None if failed
    """
    # Convert to Path objects for safer path handling
    video_path = Path(video_path)
    
    # Default output directory if not specified
    if output_dir is None:
        output_dir = Path("./output")
    else:
        output_dir = Path(output_dir)
        
    # Create the output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine output filename
    if output_filename:
        output_name = f"{output_filename}.mp4"
    else:
        # Create a default output filename based on the original
        stem = video_path.stem
        output_name = f"{stem}_{target_language}.mp4"
    
    # Full output path
    output_path = output_dir / output_name
    
    print(f"Processing video: {video_path}")
    print(f"Output will be saved to: {output_path}")
    
    # Call the dubbing function
    result = create_dub_from_file(
        str(video_path),
        str(output_path),
        source_language,
        target_language,
        num_speakers,
        disable_watermark
    )
    
    if result:
        print(f"Dubbing completed successfully! Output saved to: {result}")
        return result
    else:
        print("Dubbing failed.")
        return None


def process_directory(
    input_dir: str, 
    output_dir: str = None, 
    source_language: str = "en", 
    target_language: str = "en",
    num_speakers: int = 2,
    disable_watermark: bool = True
) -> None:
    """
    Process all video files in a directory.
    
    Args:
        input_dir (str): Directory containing video files
        output_dir (str): Directory to save output files
        source_language (str): Source language code
        target_language (str): Target language code
        num_speakers (int): Number of speakers to detect
        disable_watermark (bool): Whether to disable watermark
    """
    input_dir = Path(input_dir)
    
    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory")
        return
    
    # Find all video files in the directory
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(input_dir.glob(f"*{ext}"))
    
    if not video_files:
        print(f"No video files found in {input_dir}")
        return
    
    print(f"Found {len(video_files)} video file(s) to process")
    
    # Process each video file
    for i, video_file in enumerate(video_files, 1):
        print(f"\nProcessing file {i} of {len(video_files)}: {video_file.name}")
        process_video(
            str(video_file),
            output_dir,
            source_language,
            target_language,
            num_speakers,
            disable_watermark
        )


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Dub video files using ElevenLabs Dubbing API")
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-f', '--file', help="Path to a single video file to dub")
    input_group.add_argument('-d', '--directory', help="Path to a directory of video files to dub")
    
    # Output options
    parser.add_argument('-o', '--output', help="Directory to save dubbed videos (default: ./output)")
    parser.add_argument('--output-filename', help="Custom output filename (without extension, only for single file mode)")
    
    # Dubbing options
    parser.add_argument('-s', '--source-language', default="en", help="Source language code (default: en)")
    parser.add_argument('-t', '--target-language', default="en", help="Target language code (default: en)")
    parser.add_argument('-n', '--num-speakers', type=int, default=2, help="Number of speakers to detect (default: 2)")
    parser.add_argument('--watermark', action='store_true', help="Enable watermark (disabled by default)")
    
    args = parser.parse_args()
    
    # Check API key
    if not os.getenv("ELEVENLABS_API_KEY"):
        print("Error: ELEVENLABS_API_KEY not found in environment variables or .env file")
        sys.exit(1)
    
    # Process based on input type
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        process_video(
            args.file, 
            args.output, 
            args.source_language, 
            args.target_language, 
            args.num_speakers, 
            not args.watermark,
            args.output_filename
        )
    else:  # Directory mode
        if not os.path.isdir(args.directory):
            print(f"Error: Directory not found: {args.directory}")
            sys.exit(1)
        
        if args.output_filename:
            print("Warning: --output-filename is ignored in directory mode")
            
        process_directory(
            args.directory, 
            args.output, 
            args.source_language, 
            args.target_language,
            args.num_speakers,
            not args.watermark
        )


if __name__ == "__main__":
    main()