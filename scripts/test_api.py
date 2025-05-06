#!/usr/bin/env python3
"""
Test ElevenLabs API Connection

Simple script to test ElevenLabs API connectivity.
"""

import os
import sys
from elevenlabs import ElevenLabs

def test_api_connection():
    """Test connection to ElevenLabs API."""
    print("Testing ElevenLabs API connection...")
    
    # Try loading from environment first
    api_key = os.getenv("ELEVENLABS_API_KEY")
    
    # Check if key is available
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY environment variable not found")
        print("Please ensure it is set in your .env file or environment variables")
        return False
    
    print(f"API key found: {api_key[:5]}...{api_key[-5:]}")
    
    try:
        client = ElevenLabs(api_key=api_key)
        # Test if we can access API functionality
        voice_id = "AZnzlk1XvdvUeBnXmlld"  # Default voice ID
        with open("/tmp/test_message.txt", "w") as f:
            f.write("This is a test message to check API connectivity.")
            
        print("ElevenLabs client initialized successfully")
        print("Client attributes:", dir(client))
        
        # Test if client has text_to_speech attribute
        if hasattr(client, 'text_to_speech'):
            print("Text-to-speech API available")
        else:
            print("Text-to-speech API not available on client")
            
        # Test if client has speech_to_text attribute
        if hasattr(client, 'speech_to_text'):
            print("Speech-to-text API available")
            print("Speech-to-text attributes:", dir(client.speech_to_text))
        else:
            print("Speech-to-text API not available on client")
            
        # Check for model information
        if hasattr(client, 'models'):
            models = client.models
            print("Models available:", models)
        else:
            print("Models not available on client")
            
        return True
    except Exception as e:
        print(f"Error connecting to ElevenLabs API: {e}")
        print(f"Exception type: {type(e)}")
        return False

if __name__ == "__main__":
    success = test_api_connection()
    sys.exit(0 if success else 1)