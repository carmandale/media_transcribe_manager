#!/usr/bin/env python3
"""
Environment Variable Loader

Loads environment variables from .env file and ensures they are properly set.
"""

import os
import sys
import dotenv

def load_env_vars():
    """Load environment variables from .env file and verify they are set."""
    print("Loading environment variables...")
    
    # Load from .env file
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(dotenv_path):
        print(f"ERROR: .env file not found at {dotenv_path}")
        return False
        
    # Load variables from .env file
    success = dotenv.load_dotenv(dotenv_path)
    if not success:
        print("WARNING: Failed to load variables from .env file")
    
    # Check critical variables
    critical_vars = [
        'ELEVENLABS_API_KEY',
        'DEEPL_API_KEY',
        'OPENAI_API_KEY'
    ]
    
    all_set = True
    for var in critical_vars:
        value = os.getenv(var)
        if not value:
            print(f"WARNING: {var} not set in environment")
            all_set = False
        else:
            print(f"✓ {var} set: {value[:5]}...{value[-5:]}")
    
    # Explicitly set ElevenLabs API key if not set
    if not os.getenv('ELEVENLABS_API_KEY'):
        print("NOTICE: Setting ELEVENLABS_API_KEY directly")
        os.environ['ELEVENLABS_API_KEY'] = "sk_e067dc46fad47e2ef355ba909b7ad5ff938c0b1d6cf63e43"
        
    return all_set

if __name__ == "__main__":
    success = load_env_vars()
    print(f"Environment loaded: {'Success' if success else 'Warning - some variables missing'}")
    sys.exit(0 if success else 1)