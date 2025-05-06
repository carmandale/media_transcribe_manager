#!/usr/bin/env python3
"""
Monitor and Restart Script

This script continuously monitors the transcription and translation status
and automatically restarts processes when they've completed.

Usage:
    python monitor_and_restart.py [--check-interval SECONDS] [--batch-size N] [--languages LANGS]

Options:
    --check-interval SECONDS    Seconds between status checks (default: 60)
    --batch-size N              Batch size for processing (default: 5)
    --languages LANGS           Comma-separated list of languages (default: en,de,he)
"""

import os
import sys
import time
import logging
import argparse
import subprocess
from typing import List, Dict, Tuple, Set
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('monitor.log')
    ]
)

logger = logging.getLogger(__name__)

def get_status(db_file: str = 'media_tracking.db') -> Dict[str, Dict[str, int]]:
    """Get current processing status from database."""
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    result = {
        'transcription': {},
        'translation': {'en': {}, 'de': {}, 'he': {}}
    }
    
    # Get transcription status
    cursor.execute("""
    SELECT transcription_status, COUNT(*) as count 
    FROM processing_status 
    GROUP BY transcription_status
    """)
    for row in cursor.fetchall():
        status = row['transcription_status']
        count = row['count']
        result['transcription'][status] = count
    
    # Get translation status for each language
    for lang in ['en', 'de', 'he']:
        cursor.execute(f"""
        SELECT translation_{lang}_status as status, COUNT(*) as count 
        FROM processing_status 
        GROUP BY translation_{lang}_status
        """)
        for row in cursor.fetchall():
            status = row['status']
            count = row['count']
            result['translation'][lang][status] = count
    
    conn.close()
    return result

def get_process_list() -> Set[str]:
    """Get list of running processes containing 'python' and 'parallel'."""
    try:
        output = subprocess.check_output(
            "ps -ef | grep python | grep -E 'parallel_(transcription|translation)' | grep -v grep | awk '{print $2}'", 
            shell=True, text=True
        )
        processes = set(output.strip().split('\n')) if output.strip() else set()
        
        # Also get the commands for better logging
        cmd_output = subprocess.check_output(
            "ps -ef | grep python | grep -E 'parallel_(transcription|translation)' | grep -v grep", 
            shell=True, text=True
        )
        logger.debug(f"Running processes:\n{cmd_output}")
        
        return processes
    except subprocess.CalledProcessError:
        return set()

def start_transcription(batch_size: int = 5) -> Tuple[bool, str]:
    """Start transcription process."""
    command = f"python parallel_transcription.py --workers 2 --batch-size {batch_size} > transcription.log 2>&1"
    try:
        process = subprocess.Popen(command, shell=True)
        logger.info(f"Started transcription process (PID: {process.pid})")
        return True, f"Started with PID {process.pid}"
    except Exception as e:
        logger.error(f"Failed to start transcription: {e}")
        return False, str(e)

def start_translation(language: str, batch_size: int = 5) -> Tuple[bool, str]:
    """Start translation process for a specific language."""
    command = f"python parallel_translation.py --language {language} --workers 2 --batch-size {batch_size} > {language}_translation.log 2>&1"
    try:
        process = subprocess.Popen(command, shell=True)
        logger.info(f"Started {language} translation process (PID: {process.pid})")
        return True, f"Started with PID {process.pid}"
    except Exception as e:
        logger.error(f"Failed to start {language} translation: {e}")
        return False, str(e)

def needs_transcription(status: Dict[str, Dict[str, int]]) -> bool:
    """Check if transcription is needed."""
    transcription = status['transcription']
    not_started = transcription.get('not_started', 0)
    failed = transcription.get('failed', 0)
    return (not_started + failed) > 0

def needs_translation(status: Dict[str, Dict[str, int]], language: str) -> bool:
    """Check if translation is needed for a specific language."""
    translation = status['translation'][language]
    not_started = translation.get('not_started', 0)
    failed = translation.get('failed', 0)
    
    # Log the number of files that need translation
    if (not_started + failed) > 0:
        logger.info(f"Found {not_started} not_started and {failed} failed files for {language} translation")
    
    return (not_started + failed) > 0

def main():
    parser = argparse.ArgumentParser(description="Monitor and restart transcription/translation processes")
    parser.add_argument("--check-interval", type=int, default=60,
                        help="Seconds between status checks (default: 60)")
    parser.add_argument("--batch-size", type=int, default=5,
                        help="Batch size for processing (default: 5)")
    parser.add_argument("--languages", type=str, default="en,de,he",
                        help="Comma-separated list of languages (default: en,de,he)")
    args = parser.parse_args()
    
    languages = args.languages.split(',')
    logger.info(f"Starting monitor with check interval: {args.check_interval}s, "
               f"batch size: {args.batch_size}, languages: {languages}")
    
    process_check_time = 0
    running_processes = set()
    
    try:
        while True:
            current_time = time.time()
            
            # Check running processes every 10 seconds
            if current_time - process_check_time >= 10:
                process_check_time = current_time
                running_processes = get_process_list()
                logger.debug(f"Running processes: {running_processes}")
            
            # Get current status
            try:
                status = get_status()
                total_remaining = 0
                
                # Check transcription status
                transcription_remaining = sum(status['transcription'].get(s, 0) for s in ['not_started', 'failed'])
                total_remaining += transcription_remaining
                
                # Check if we need to start transcription
                if needs_transcription(status) and len(running_processes) == 0:
                    logger.info(f"Need to process {transcription_remaining} transcriptions")
                    success, msg = start_transcription(args.batch_size)
                    if success:
                        # Allow time for process to start before checking again
                        time.sleep(2)
                        running_processes = get_process_list()
                
                # Check translation status for each language
                for lang in languages:
                    translation_remaining = sum(status['translation'][lang].get(s, 0) for s in ['not_started', 'failed'])
                    total_remaining += translation_remaining
                    
                    # Check if we need to start translation
                    if needs_translation(status, lang) and len(running_processes) == 0:
                        logger.info(f"Need to process {translation_remaining} {lang} translations")
                        success, msg = start_translation(lang, args.batch_size)
                        if success:
                            # Allow time for process to start before checking again
                            time.sleep(2)
                            running_processes = get_process_list()
                
                # Log status summary
                logger.info(
                    f"Status: Transcription remaining: {transcription_remaining}, "
                    f"Translation remaining: {sum(sum(status['translation'][lang].get(s, 0) for s in ['not_started', 'failed']) for lang in languages)}, "
                    f"Running processes: {len(running_processes)}"
                )
                
                # Exit if everything is completed
                if total_remaining == 0 and len(running_processes) == 0:
                    logger.info("All processing completed!")
                    print_final_stats(status)
                    break
                    
            except Exception as e:
                logger.error(f"Error during status check: {e}")
            
            # Wait before next check
            time.sleep(args.check_interval)
            
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
        
def print_final_stats(status: Dict[str, Dict[str, int]]):
    """Print final statistics."""
    logger.info("Final Processing Statistics:")
    
    # Transcription stats
    logger.info("Transcription:")
    for status_type, count in status['transcription'].items():
        logger.info(f"  - {status_type}: {count}")
    
    # Translation stats
    logger.info("Translations:")
    for lang in ['en', 'de', 'he']:
        logger.info(f"  {lang.upper()}:")
        for status_type, count in status['translation'][lang].items():
            logger.info(f"    - {status_type}: {count}")

if __name__ == "__main__":
    main()