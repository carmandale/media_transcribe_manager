#!/usr/bin/env python3
"""
Automated Translation Pipeline Monitoring and Recovery Tool

This script continuously monitors the translation pipeline, automatically detects and resets
stuck processes, and restarts the pipeline as needed to ensure continuous processing.

Usage:
    python monitor_and_restart.py [OPTIONS]

Options:
    --check-interval MINUTES   Minutes between checks (default: 30)
    --batch-size SIZE          Batch size for processing (default: 10)
    --languages LANGS          Languages to process (comma-separated, default: en,de,he)
    --max-runs COUNT           Maximum number of monitoring cycles (0 = unlimited, default: 0)

Examples:
    # Basic usage with default settings (check every 30 minutes)
    python monitor_and_restart.py
    
    # Custom check interval and batch size
    python monitor_and_restart.py --check-interval 15 --batch-size 20
    
    # Process only English and German translations
    python monitor_and_restart.py --languages en,de
    
    # Run for a limited number of cycles
    python monitor_and_restart.py --max-runs 5
    
    # Run in background (Linux/MacOS)
    python monitor_and_restart.py > monitoring.log 2>&1 &

See also:
    - check_status.py - For checking overall translation status
    - check_stuck_files.py - For manually resetting stuck processes
    - docs/MONITORING_GUIDE.md - For detailed monitoring documentation
"""

import argparse
import subprocess
import time
import datetime
import sys
import os
from db_manager import DatabaseManager

# Ensure environment variables are set
def load_environment():
    """Load environment variables and ensure API keys are set."""
    print("Loading environment variables...")
    
    # Define critical keys with default values
    critical_keys = {
        'ELEVENLABS_API_KEY': "sk_e067dc46fad47e2ef355ba909b7ad5ff938c0b1d6cf63e43",
        'OPENAI_API_KEY': "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",
        'DEEPL_API_KEY': "3c08c92c-daee-4567-8ec6-736faa2ec2b5"
    }
    
    # Try to load from .env file if available
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            import dotenv
            dotenv.load_dotenv(env_path)
            print("Loaded environment from .env file")
        except ImportError:
            print("dotenv not available, using defaults")
    
    # Check and set keys if needed
    for key, default in critical_keys.items():
        if not os.environ.get(key):
            print(f"Setting {key} from default value")
            os.environ[key] = default
        else:
            value = os.environ.get(key)
            print(f"{key} is set: {value[:5]}...{value[-5:]}")
            
    return True

def parse_args():
    parser = argparse.ArgumentParser(description="Monitor and restart stuck translation processes")
    parser.add_argument("--check-interval", type=int, default=30,
                        help="Minutes between checks (default: 30)")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Batch size for processing (default: 10)")
    parser.add_argument("--languages", type=str, default="en,de,he",
                        help="Languages to process (comma-separated, default: en,de,he)")
    parser.add_argument("--max-runs", type=int, default=0,
                        help="Maximum number of monitoring cycles (0 = unlimited, default: 0)")
    return parser.parse_args()

def reset_stuck_processes():
    """Reset files stuck in 'in-progress' state."""
    db = DatabaseManager('media_tracking.db')
    
    # Get files stuck in in-progress state
    query = """
    SELECT file_id, translation_en_status, translation_de_status, translation_he_status, last_updated
    FROM processing_status
    WHERE translation_en_status = 'in-progress'
       OR translation_de_status = 'in-progress'
       OR translation_he_status = 'in-progress'
    """
    
    stuck_files = db.execute_query(query)
    reset_count = 0
    current_time = datetime.datetime.now()
    
    for file in stuck_files:
        file_id = file['file_id']
        last_updated = datetime.datetime.strptime(file['last_updated'], "%Y-%m-%d %H:%M:%S.%f")
        minutes_since_update = (current_time - last_updated).total_seconds() / 60
        
        # Reset status for files stuck longer than 30 minutes
        if minutes_since_update > 30:
            update_query = {}
            
            if file['translation_en_status'] == 'in-progress':
                update_query['translation_en_status'] = 'not_started'
                
            if file['translation_de_status'] == 'in-progress':
                update_query['translation_de_status'] = 'not_started'
                
            if file['translation_he_status'] == 'in-progress':
                update_query['translation_he_status'] = 'not_started'
            
            if update_query:
                print(f"Resetting status for file {file_id} (stuck for {minutes_since_update:.1f} minutes)")
                db.update_status(file_id, 'pending', **update_query)
                reset_count += 1
    
    return reset_count, len(stuck_files)

def check_processing_status():
    """Check if translations are still being processed."""
    db = DatabaseManager('media_tracking.db')
    
    # Check when the last update happened
    query_last_update = 'SELECT MAX(last_updated) as last_update FROM processing_status'
    last_update = db.execute_query(query_last_update)[0]['last_update']
    
    now = datetime.datetime.now()
    last_update_time = datetime.datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S.%f")
    minutes_since_update = (now - last_update_time).total_seconds() / 60
    
    # Get count of remaining translations
    query_remaining = '''
    SELECT 
        SUM(CASE WHEN translation_en_status IN ('not_started', 'in-progress') THEN 1 ELSE 0 END) as en_remaining,
        SUM(CASE WHEN translation_de_status IN ('not_started', 'in-progress') THEN 1 ELSE 0 END) as de_remaining,
        SUM(CASE WHEN translation_he_status IN ('not_started', 'in-progress') THEN 1 ELSE 0 END) as he_remaining
    FROM processing_status
    '''
    
    remaining = db.execute_query(query_remaining)[0]
    
    return {
        'last_update': last_update,
        'minutes_since_update': minutes_since_update,
        'en_remaining': remaining['en_remaining'],
        'de_remaining': remaining['de_remaining'],
        'he_remaining': remaining['he_remaining']
    }

def restart_pipeline(languages, batch_size):
    """Restart the full pipeline."""
    print(f"Restarting pipeline with languages: {languages}, batch_size: {batch_size}")
    
    # Use our new script that ensures environment variables are loaded
    cmd = [
        "python", "run_transcription_pipeline.py",
        "--restart",
        "--batch-size", str(batch_size),
        "--languages", languages
    ]
    
    try:
        subprocess.Popen(cmd)
        print("Pipeline restarted successfully")
        return True
    except Exception as e:
        print(f"Error restarting pipeline: {e}")
        return False

def generate_status_report():
    """Generate a status report."""
    print("Generating status report...")
    
    try:
        output = subprocess.check_output(["python", "check_status.py"], text=True)
        print("\n--- STATUS REPORT ---")
        print(output)
        print("--- END REPORT ---\n")
    except Exception as e:
        print(f"Error generating status report: {e}")

def main():
    # Load environment variables first
    load_environment()
    
    args = parse_args()
    check_interval_seconds = args.check_interval * 60
    runs = 0
    
    print(f"Starting monitoring with {args.check_interval} minute check interval")
    print(f"Will process languages: {args.languages} with batch size {args.batch_size}")
    print(f"Max runs: {args.max_runs if args.max_runs > 0 else 'unlimited'}")
    
    try:
        while True:
            runs += 1
            print(f"\n--- Monitoring Run #{runs} at {datetime.datetime.now()} ---")
            
            # Generate status report
            generate_status_report()
            
            # Check for stuck processes
            reset_count, stuck_count = reset_stuck_processes()
            print(f"Found {stuck_count} stuck processes, reset {reset_count}")
            
            # Check processing status
            status = check_processing_status()
            print(f"Last database update: {status['last_update']} ({status['minutes_since_update']:.1f} minutes ago)")
            print(f"Remaining translations - EN: {status['en_remaining']}, DE: {status['de_remaining']}, HE: {status['he_remaining']}")
            
            # Restart pipeline if needed
            total_remaining = status['en_remaining'] + status['de_remaining'] + status['he_remaining']
            if total_remaining > 0 and (status['minutes_since_update'] > 15 or reset_count > 0):
                print("Translations still needed and no recent updates or stuck processes reset")
                restart_pipeline(args.languages, args.batch_size)
            else:
                print("No need to restart pipeline - either no translations remaining or still active")
            
            # Check if we've reached max runs
            if args.max_runs > 0 and runs >= args.max_runs:
                print(f"Reached maximum number of runs ({args.max_runs}), exiting")
                break
                
            # Sleep until next check
            next_check = datetime.datetime.now() + datetime.timedelta(seconds=check_interval_seconds)
            print(f"Next check at: {next_check}")
            time.sleep(check_interval_seconds)
    
    except KeyboardInterrupt:
        print("\nMonitoring interrupted by user")
    except Exception as e:
        print(f"Error in monitoring: {e}")
    
    print("Monitoring complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())