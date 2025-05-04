#!/usr/bin/env python3
"""
Run Debug Transcription with Environment Variables

Ensures environment variables are loaded before running debug transcription.
"""

import os
import sys
import subprocess
import load_env

def main():
    """Main function to run the debug transcription test."""
    # First load environment variables
    print("Setting up environment...")
    load_env.load_env_vars()
    
    # Get ElevenLabs API key
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("ERROR: Failed to set ELEVENLABS_API_KEY in environment")
        return 1
    
    print(f"API key is set in environment: {api_key[:5]}...{api_key[-5:]}")
    
    # File ID to debug
    file_id = "a5c69df1-c4f4-4728-9052-7ba17b1a69a0"
    
    # Run debug transcription with the environment set
    print(f"Running debug transcription for file ID: {file_id}")
    result = subprocess.run(
        ["python", "debug_transcription.py", "--file-id", file_id],
        capture_output=True,
        text=True,
        env=os.environ
    )
    
    # Output results
    print("\n--- STDOUT ---")
    print(result.stdout)
    
    print("\n--- STDERR ---")
    print(result.stderr)
    
    print(f"\nExit code: {result.returncode}")
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())