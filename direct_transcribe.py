#!/usr/bin/env python3
"""
Direct Transcription Test

Tests the ElevenLabs transcription API directly, without dependencies on the database.
"""

import os
import sys
import tempfile
import subprocess
import json
from elevenlabs import ElevenLabs

def test_direct_transcription():
    """Test transcription on a small audio sample."""
    print("Testing direct transcription with ElevenLabs API")
    
    # Load environment variables (if available)
    os.system("python load_env.py > /dev/null 2>&1")
    
    # Get API key from environment or use hardcoded value
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("Warning: ELEVENLABS_API_KEY environment variable not found")
        print("Using hardcoded key for testing...")
        api_key = "sk_e067dc46fad47e2ef355ba909b7ad5ff938c0b1d6cf63e43"
    
    print(f"Using API key: {api_key[:5]}...{api_key[-5:]}")
    
    # File to test with
    file_path = "/Users/dalecarman/Groove Jones Dropbox/Dale Carman/Projects/Bryan Rigg/_ORIGINAL_SOURCE/Bryan Rigg - new jon 10-9-2023/62a Peter Gaupp (50% Jew) 17 Jan. 1995, Vancouver, Canada/side a.mp3"
    
    # Create a temporary clip for testing
    try:
        print(f"Creating test clip from: {file_path}")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="direct_transcribe_")
        test_clip_path = os.path.join(temp_dir, "test_clip.mp3")
        
        # Extract a 5-second clip
        ffmpeg_cmd = [
            'ffmpeg', '-v', 'warning', 
            '-i', file_path,
            '-ss', '0', '-t', '5',  # Extract first 5 seconds
            '-acodec', 'libmp3lame', '-ab', '192k', '-ar', '44100',
            '-y', test_clip_path
        ]
        
        print("Extracting audio sample...")
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if not os.path.exists(test_clip_path):
            print(f"Error: Test clip file not created at {test_clip_path}")
            return False
            
        print(f"Test clip created successfully ({os.path.getsize(test_clip_path) / 1024:.2f} KB)")
        
        # Initialize ElevenLabs client
        client = ElevenLabs(api_key=api_key)
        
        # Test transcription
        print("Sending test audio to ElevenLabs API...")
        with open(test_clip_path, 'rb') as audio_file:
            api_params = {
                "file": audio_file,
                "model_id": "scribe_v1",
                "tag_audio_events": True,
                "diarize": True,
                "timestamps_granularity": "word",
                "language_code": "deu"  # Assuming German language
            }
            
            # Set extended timeout
            request_options = {"timeout_in_seconds": 120}
            
            try:
                print("Calling speech-to-text API with params:", api_params)
                transcription = client.speech_to_text.convert(**api_params, request_options=request_options)
                
                # Check transcription result
                if transcription and hasattr(transcription, 'text') and transcription.text:
                    print("\nTranscription successful!")
                    print(f"Detected language: {getattr(transcription, 'language_code', 'unknown')}")
                    print("\nTranscript text:")
                    print("-" * 40)
                    print(transcription.text[:500] + "..." if len(transcription.text) > 500 else transcription.text)
                    print("-" * 40)
                    
                    # Save transcription to file for inspection
                    transcript_path = os.path.join(temp_dir, "transcript.txt")
                    with open(transcript_path, 'w', encoding='utf-8') as f:
                        f.write(transcription.text)
                    
                    print(f"Full transcript saved to: {transcript_path}")
                    
                    # Save full response as JSON
                    json_path = os.path.join(temp_dir, "response.json")
                    with open(json_path, 'w', encoding='utf-8') as f:
                        try:
                            json.dump(transcription.dict(), f, ensure_ascii=False, indent=2)
                            print(f"Full response saved to: {json_path}")
                        except Exception as e:
                            print(f"Error saving JSON response: {e}")
                    
                    print("\nTemporary files kept at:", temp_dir)
                    return True
                else:
                    print("Error: No text in transcription response")
                    return False
                    
            except Exception as e:
                print(f"Error during transcription: {e}")
                print(f"Error type: {type(e)}")
                return False
    except Exception as e:
        print(f"Error in test: {e}")
        return False

if __name__ == "__main__":
    success = test_direct_transcription()
    sys.exit(0 if success else 1)