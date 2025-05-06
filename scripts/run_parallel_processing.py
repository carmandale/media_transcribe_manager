#!/usr/bin/env python3
"""
Parallel Processing Runner

This script launches parallel transcription and translation processes
to speed up the overall processing pipeline.

Usage:
    python run_parallel_processing.py [OPTIONS]

Options:
    --transcription-workers N    Number of concurrent transcription workers (default: 5)
    --translation-workers N      Number of concurrent translation workers per language (default: 5)
    --transcription-batch N      Number of files to transcribe (default: all pending)
    --translation-batch N        Number of files to translate per language (default: all pending)
    --languages LANGS            Languages to process (comma-separated, default: en,de,he)
"""

import os
import sys
import time
import argparse
import subprocess
import concurrent.futures
from typing import List, Dict
from pathlib import Path

# Add core_modules to the Python path
sys.path.append(str(Path(__file__).parent.parent / 'core_modules'))

from log_config import setup_logger

# Configure logging
logger = setup_logger('parallel_processing', 'parallel_processing.log')

def load_environment():
    """Ensure environment variables are loaded."""
    # Try to load from .env file if available
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        logger.error(f".env file not found at {env_path}")
        return False
        
    try:
        import dotenv
        dotenv.load_dotenv(env_path)
        logger.info("Loaded environment variables from .env file")
        return True
    except ImportError:
        logger.error("Failed to import dotenv. Please install with: pip install python-dotenv")
        return False

def run_transcription(workers: int, batch_size: int = None) -> bool:
    """Run parallel transcription process."""
    logger.info(f"Starting parallel transcription with {workers} workers")
    
    script_path = str(Path(__file__).parent / "parallel_transcription.py")
    cmd = ["python", script_path, "--workers", str(workers)]
    if batch_size:
        cmd.extend(["--batch-size", str(batch_size)])
    
    try:
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        
        logger.info(f"Transcription process output:")
        for line in result.stdout.splitlines():
            logger.info(f"  {line}")
        
        if result.stderr:
            logger.warning(f"Transcription process errors:")
            for line in result.stderr.splitlines():
                logger.warning(f"  {line}")
                
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Transcription process failed with code {e.returncode}")
        if e.stdout:
            logger.info(f"Output: {e.stdout}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error running transcription: {e}")
        return False

def run_translation(language: str, workers: int, batch_size: int = None) -> bool:
    """Run parallel translation process for a specific language."""
    logger.info(f"Starting parallel {language} translation with {workers} workers")
    
    script_path = str(Path(__file__).parent / "parallel_translation.py")
    cmd = ["python", script_path, "--language", language, "--workers", str(workers)]
    if batch_size:
        cmd.extend(["--batch-size", str(batch_size)])
    
    try:
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        
        logger.info(f"{language} translation process output:")
        for line in result.stdout.splitlines():
            logger.info(f"  {line}")
        
        if result.stderr:
            logger.warning(f"{language} translation process errors:")
            for line in result.stderr.splitlines():
                logger.warning(f"  {line}")
                
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"{language} translation process failed with code {e.returncode}")
        if e.stdout:
            logger.info(f"Output: {e.stdout}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error running {language} translation: {e}")
        return False

def run_all_translations(languages: List[str], workers: int, batch_size: int = None) -> Dict[str, bool]:
    """Run translations for all specified languages in parallel."""
    logger.info(f"Starting translations for languages: {', '.join(languages)}")
    
    results = {}
    
    # Process translations in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(languages)) as executor:
        futures = {}
        
        for lang in languages:
            # Submit translation job
            future = executor.submit(run_translation, lang, workers, batch_size)
            futures[lang] = future
        
        # Collect results
        for lang, future in futures.items():
            try:
                results[lang] = future.result()
                logger.info(f"{lang} translation {'succeeded' if results[lang] else 'failed'}")
            except Exception as e:
                logger.error(f"Exception running {lang} translation: {e}")
                results[lang] = False
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Run parallel transcription and translation processes")
    parser.add_argument("--transcription-workers", type=int, default=5,
                        help="Number of concurrent transcription workers (default: 5)")
    parser.add_argument("--translation-workers", type=int, default=5,
                        help="Number of concurrent translation workers per language (default: 5)")
    parser.add_argument("--transcription-batch", type=int, default=None,
                        help="Number of files to transcribe (default: all pending)")
    parser.add_argument("--translation-batch", type=int, default=None,
                        help="Number of files to translate per language (default: all pending)")
    parser.add_argument("--languages", default="en,de,he",
                        help="Languages to process (comma-separated, default: en,de,he)")
    args = parser.parse_args()
    
    # Ensure environment variables are loaded
    if not load_environment():
        logger.error("Failed to load environment variables")
        return 1
    
    # Parse languages
    languages = args.languages.split(',')
    logger.info(f"Processing languages: {', '.join(languages)}")
    
    # Run transcription and translations in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit transcription job
        transcription_future = executor.submit(
            run_transcription,
            workers=args.transcription_workers,
            batch_size=args.transcription_batch
        )
        
        # Submit translation job (which will launch parallel processes per language)
        translation_future = executor.submit(
            run_all_translations,
            languages=languages,
            workers=args.translation_workers,
            batch_size=args.translation_batch
        )
        
        # Wait for transcription to complete
        try:
            transcription_success = transcription_future.result()
            logger.info(f"Transcription process {'succeeded' if transcription_success else 'failed'}")
        except Exception as e:
            logger.error(f"Exception during transcription: {e}")
            transcription_success = False
        
        # Wait for translations to complete
        try:
            translation_results = translation_future.result()
            logger.info(f"Translation results: {translation_results}")
        except Exception as e:
            logger.error(f"Exception during translation: {e}")
            translation_results = {lang: False for lang in languages}
    
    # Summarize results
    all_success = transcription_success and all(translation_results.values())
    
    if all_success:
        logger.info("All processes completed successfully")
    else:
        failures = []
        if not transcription_success:
            failures.append("transcription")
        failed_langs = [lang for lang, success in translation_results.items() if not success]
        if failed_langs:
            failures.append(f"translation ({', '.join(failed_langs)})")
        
        logger.warning(f"Some processes failed: {', '.join(failures)}")
    
    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())