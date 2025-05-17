#!/usr/bin/env python3
"""
Transcription Pipeline Runner with Environment Setup

This script ensures environment variables are properly loaded and then runs the transcription pipeline.
"""

import os
import sys
import subprocess
import time
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('transcription_pipeline.log')
    ]
)

logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables and verify API keys are set."""
    # Look for .env file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        logger.warning(f".env file not found at {env_path}")
    
    # Try to load with python-dotenv if available
    try:
        import dotenv
        dotenv.load_dotenv(env_path)
        logger.info("Loaded environment variables from .env file")
    except ImportError:
        logger.warning("python-dotenv not available, environment may not be fully loaded")
    
    # List of critical API keys that should be in the environment
    critical_keys = [
        'ELEVENLABS_API_KEY',
        'OPENAI_API_KEY',
        'DEEPL_API_KEY'
    ]
    
    # Check if keys are set
    missing_keys = []
    for key in critical_keys:
        value = os.getenv(key)
        if not value:
            missing_keys.append(key)
            logger.warning(f"{key} not found in environment")
        else:
            logger.info(f"{key} found in environment: {value[:5]}...{value[-5:]}")
    
    # If keys are missing, warn about it
    if missing_keys:
        logger.error(f"Missing required API keys: {', '.join(missing_keys)}")
        logger.error("Please ensure these are set in your .env file")
        return False
    
    return True

def transcribe_specific_file(file_id):
    """Process a specific file for transcription."""
    logger.info(f"Transcribing specific file: {file_id}")
    
    # Create a simple script to directly transcribe
    temp_script = """
import os
import sys
from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

def main():
    # Set up DB connection
    db = DatabaseManager('media_tracking.db')
    
    # Get file status
    file_id = '{file_id}'
    file_status = db.get_file_status(file_id)
    if not file_status:
        print(f"Error: File {file_id} not found in database")
        return 1
    
    # Set up managers
    config = {{
        'output_directory': './output',
        'elevenlabs': {{
            'api_key': '{api_key}',
            'model': 'scribe_v1',
            'speaker_detection': True,
            'speaker_count': 32
        }},
        'force_reprocess': True  # Force reprocessing
    }}
    
    # Get file path
    file_manager = FileManager(db, config)
    audio_path = file_manager.get_audio_path(file_id)
    if not audio_path:
        print(f"Error: Audio path not found for {file_id}")
        return 1
    
    # Reset file status
    db.update_status(
        file_id=file_id,
        status='pending',
        transcription_status='not_started'
    )
    
    # Create transcription manager
    transcription_manager = TranscriptionManager(db, config)
    transcription_manager.set_file_manager(file_manager)
    
    # Transcribe audio
    print(f"Transcribing audio: {{audio_path}}")
    success = transcription_manager.transcribe_audio(
        file_id=file_id,
        audio_path=audio_path,
        file_details=file_status
    )
    
    if success:
        print(f"Transcription successful for file {file_id}")
        return 0
    else:
        print(f"Transcription failed for file {file_id}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
    """.format(
        file_id=file_id,
        api_key=os.environ.get('ELEVENLABS_API_KEY', '')
    )
    
    # Write the temporary script
    script_path = "temp_transcribe.py"
    with open(script_path, "w") as f:
        f.write(temp_script)
    
    # Run the script
    try:
        result = subprocess.run(["python", script_path], capture_output=True, text=True)
        
        # Display output
        logger.info(f"Transcription process output:")
        logger.info(result.stdout)
        
        if result.stderr:
            logger.warning(f"Transcription errors:")
            logger.warning(result.stderr)
        
        # Clean up
        os.remove(script_path)
        
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running transcription: {e}")
        return False

def restart_pipeline(batch_size=10, languages="en,de,he"):
    """Restart the full processing pipeline."""
    logger.info(f"Restarting pipeline with languages: {languages}, batch size: {batch_size}")
    
    try:
        # First, ensure environment is loaded in the process
        subprocess.run(["python", "load_env.py"], check=True)
        
        # Run the pipeline
        cmd = [
            "python", "run_full_pipeline.py",
            "--languages", languages,
            "--batch-size", str(batch_size)
        ]
        
        result = subprocess.Popen(cmd)
        logger.info(f"Pipeline started with PID: {result.pid}")
        return True
    except Exception as e:
        logger.error(f"Error restarting pipeline: {e}")
        return False

def monitor_pipeline(interval=10, batch_size=10, languages="en,de,he"):
    """Start monitoring with environment variables properly set."""
    logger.info(f"Starting pipeline monitoring with {interval}min interval")
    
    try:
        # First, ensure environment is loaded in the process
        subprocess.run(["python", "load_env.py"], check=True)
        
        # Run the monitoring script
        cmd = [
            "python", "monitor_and_restart.py",
            "--check-interval", str(interval),
            "--batch-size", str(batch_size),
            "--languages", languages
        ]
        
        # Start the monitoring process
        result = subprocess.Popen(cmd, env=os.environ)
        logger.info(f"Monitoring started with PID: {result.pid}")
        return True
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        return False

def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(description="Transcription Pipeline Runner with Environment Setup")
    
    # Add command-line arguments
    parser.add_argument("--file-id", help="Process a specific file")
    parser.add_argument("--monitor", action="store_true", help="Start pipeline monitoring")
    parser.add_argument("--restart", action="store_true", help="Restart the pipeline")
    parser.add_argument("--interval", type=int, default=10, help="Check interval for monitoring (minutes)")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    parser.add_argument("--languages", default="en,de,he", help="Languages to process (comma-separated)")
    
    args = parser.parse_args()
    
    # Load environment variables
    load_environment()
    
    # Process based on arguments
    if args.file_id:
        success = transcribe_specific_file(args.file_id)
        if not success:
            logger.error(f"Failed to transcribe file: {args.file_id}")
            return 1
    
    if args.restart:
        success = restart_pipeline(args.batch_size, args.languages)
        if not success:
            logger.error("Failed to restart pipeline")
            return 1
    
    if args.monitor:
        success = monitor_pipeline(args.interval, args.batch_size, args.languages)
        if not success:
            logger.error("Failed to start monitoring")
            return 1
    
    # If no specific action was provided, show usage
    if not (args.file_id or args.restart or args.monitor):
        parser.print_help()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())