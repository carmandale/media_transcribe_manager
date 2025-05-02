#!/usr/bin/env python3
"""
Media Transcription and Translation Tool
---------------------------------------
This tool processes audio and video files by automatically transcribing content using ElevenLabs,
translating transcripts from German to English and Hebrew, and producing organized outputs.

Main controller script that orchestrates the workflow.
"""

import os
import sys
import argparse
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
# Optional import for YAML configuration
try:
    import yaml
except ImportError:
    yaml = None
try:
    from dotenv import load_dotenv
except ImportError:
    # Fallback if python-dotenv is not installed
    load_dotenv = lambda *args, **kwargs: None
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# We'll import our custom modules here
# These will be implemented in separate files
from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager
from translation import TranslationManager
from worker_pool import WorkerPool
from reporter import Reporter


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from a YAML/JSON file or use default settings.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        A dictionary containing the configuration
    """
    # Default configuration
    default_config = {
        "output_directory": "./output",
        "database_file": "./media_tracking.db",
        "log_file": "./media_processor.log",
        "log_level": "INFO",
        "workers": 4,
        "extract_audio_format": "mp3",
        "extract_audio_quality": "192k",
        "elevenlabs": {
            "api_key": os.getenv("ELEVENLABS_API_KEY"),
            "model": "scribe_v1",
            "speaker_detection": True,
            "speaker_count": 32
        },
        "deepl": {
            "api_key": os.getenv("DEEPL_API_KEY"),
            "formality": "default",
            "batch_size": 5000
        },
        "google_translate": {
            "credentials_file": "./google_credentials.json",
            "location": "global",
            "batch_size": 5000
        },
        "microsoft_translator": {
            "api_key": os.getenv("MS_TRANSLATOR_KEY"),
            "location": "global",
            "batch_size": 5000
        },
        "media_extensions": {
            "audio": [".mp3", ".wav", ".m4a", ".aac", ".flac"],
            "video": [".mp4", ".avi", ".mov", ".mkv", ".webm"]
        }
    }
    
    # Load from file if provided
    if config_file and os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                if config_file.lower().endswith(('.yaml', '.yml')):
                    if yaml:
                        loaded_config = yaml.safe_load(f)
                    else:
                        logger.warning(f"YAML config file {config_file} provided but PyYAML is not installed, skipping.")
                        loaded_config = {}
                else:
                    loaded_config = json.load(f)
                # Merge with default config, with loaded config taking precedence
                for key, value in loaded_config.items():
                    if isinstance(value, dict) and key in default_config and isinstance(default_config[key], dict):
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
                logger.info(f"Configuration loaded from {config_file}")
        except Exception as e:
            logger.error(f"Error loading configuration from {config_file}: {e}")
            logger.info("Using default configuration")
    
    return default_config


def save_config(config: Dict[str, Any], output_file: str) -> bool:
    """
    Save the current configuration to a file.
    
    Args:
        config: Configuration dictionary
        output_file: Path to save the configuration
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        
        # Save based on file extension
        if output_file.lower().endswith('.yaml') or output_file.lower().endswith('.yml'):
            with open(output_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
        else:
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
        
        logger.info(f"Configuration saved to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration to {output_file}: {e}")
        return False


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Set up logging based on configuration.
    
    Args:
        config: Configuration dictionary
    """
    log_level = getattr(logging, config.get('log_level', 'INFO').upper())
    log_file = config.get('log_file')
    
    # Reset handlers to avoid duplicate logging
    logger.handlers = []
    
    # Configure file handler if log file specified
    if log_file:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Always add console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Set log level
    logger.setLevel(log_level)
    for handler in logger.handlers:
        handler.setLevel(log_level)


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Process media files by transcribing and translating content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Process a directory:
    python media_processor.py -d /path/to/media/files -o ./output
        
  Process a single file:
    python media_processor.py -f /path/to/media/file.mp4 -o ./output
        
  Test with limited files:
    python media_processor.py -d /path/to/media/files --test
        
  Retry failed files:
    python media_processor.py -r --status failed
        """
    )
    
    # Input Options
    input_group = parser.add_argument_group('Input Options')
    input_source = input_group.add_mutually_exclusive_group()
    input_source.add_argument('-d', '--directory', help="Process media in this directory (recursive)")
    input_source.add_argument('-f', '--file', help="Process a single file")
    input_source.add_argument('-r', '--retry', action='store_true', help="Retry previously failed files")
    input_source.add_argument('--status', choices=['pending', 'in-progress', 'failed', 'completed'], 
                            help="Filter by status")
    
    # Processing Options
    proc_group = parser.add_argument_group('Processing Options')
    proc_group.add_argument('--extract-only', action='store_true', help="Only extract audio, don't transcribe")
    proc_group.add_argument('--transcribe-only', action='store_true', help="Only transcribe, don't translate")
    proc_group.add_argument('--translate-only', help="Only translate to specified language(s)")
    proc_group.add_argument('--reprocess-unknown-language', action='store_true', 
                         help="Reprocess files with unknown language detection")
    proc_group.add_argument('--workers', type=int, help="Number of parallel workers (default: auto-detect)")
    proc_group.add_argument('--source-lang', help="Source language code (default: auto-detect)")
    proc_group.add_argument('--formality', choices=['default', 'more', 'less'], 
                          help="Formality level for translations")
    
    # Control Options
    control_group = parser.add_argument_group('Control Options')
    control_group.add_argument('--limit', type=int, help="Process only first N files found")
    control_group.add_argument('--test', action='store_true', help="Quick test with only 3 files")
    control_group.add_argument('--dry-run', action='store_true', 
                             help="Show what would be processed without processing")
    control_group.add_argument('--force', action='store_true', 
                             help="Force reprocessing of already completed items")
    
    # Output Options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument('-o', '--output', help="Base output directory (default: ./output)")
    output_group.add_argument('--report', help="Save processing report to file")
    output_group.add_argument('--summary', action='store_true', help="Display summary statistics about the project")
    output_group.add_argument('--log', help="Log file location")
    output_group.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                            help="Logging level")
    
    # Configuration
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument('--config', help="Load configuration from YAML/JSON file")
    config_group.add_argument('--save-config', help="Save current settings to config file")
    
    # Database Options
    db_group = parser.add_argument_group('Database Options')
    db_group.add_argument('--db', help="SQLite database file (default: ./media_tracking.db)")
    db_group.add_argument('--reset-db', action='store_true', help="Reset the database (caution!)")
    db_group.add_argument('--list-files', action='store_true', help="List all tracked files and status")
    db_group.add_argument('--file-status', help="Show detailed status for a specific file ID")
    db_group.add_argument('--clear-errors', action='store_true',
                        help="Clear error history from the database")
    
    return parser.parse_args()


def main():
    """Main entry point for the application."""
    # Parse command line arguments
    args = parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command line arguments
    if args.output:
        config['output_directory'] = args.output
    if args.db:
        config['database_file'] = args.db
    if args.log:
        config['log_file'] = args.log
    if args.log_level:
        config['log_level'] = args.log_level
    if args.workers is not None:
        config['workers'] = args.workers
    if args.source_lang:
        # Change 'auto' to None for auto-detection
        config['source_language'] = None if args.source_lang.lower() == 'auto' else args.source_lang
    if args.formality:
        config['deepl']['formality'] = args.formality
    
    # Save config if requested
    if args.save_config:
        save_config(config, args.save_config)
        print(f"Configuration saved to {args.save_config}")
        if not any([args.directory, args.file, args.retry, args.list_files, args.file_status]):
            return
    
    # Setup logging
    setup_logging(config)
    
    # Initialize database manager
    db_manager = DatabaseManager(config['database_file'])
    
    # Initialize reporter
    reporter = Reporter(db_manager, config)
    
    # Reset database if requested
    if args.reset_db:
        confirm = input("This will delete all tracking data. Are you sure? (y/n): ")
        if confirm.lower() == 'y':
            db_manager.reset_database()
            logger.info("Database has been reset")
        else:
            logger.info("Database reset cancelled")
        if not any([args.directory, args.file, args.retry]):
            return
    
    # List files if requested
    if args.list_files:
        status_filter = args.status if args.status else None
        db_manager.list_files(status_filter)
        return
    
    # Show file status if requested
    if args.file_status:
        db_manager.show_file_status(args.file_status)
        return
    
    # Handle clear errors if requested
    if args.clear_errors:
        # Get confirmation unless --force is used
        if not args.force:
            confirm = input("This will delete error history from the database. Are you sure? (y/n): ")
            if confirm.lower() != 'y':
                logger.info("Error clearing cancelled")
                return
        
        # Clear errors
        success, count = db_manager.clear_errors()
        
        if success:
            print(f"Cleared {count} error records from the database")
        else:
            print("Failed to clear error records")
            
        if not any([args.directory, args.file, args.retry]):
            return
    
    # Show summary if requested
    if args.summary:
        reporter.display_summary()
        return
    
    # Handle reprocessing of files with unknown language
    if args.reprocess_unknown_language:
        print("Reprocessing files with unknown language detection...")
        # Get files with unknown language
        unknown_files = db_manager.get_files_with_unknown_language()
        
        if not unknown_files:
            print("No files with unknown language detection found.")
            return
            
        print(f"Found {len(unknown_files)} files with unknown language. Reprocessing...")
        # Setup for processing
        file_manager = FileManager(db_manager, config)
        
        # Force auto-detection regardless of command line
        source_language = None  # None means auto-detect
        logger.info("Using automatic language detection for reprocessing")
        
        # Enable force flag to overwrite existing transcriptions
        config['force_reprocess'] = True
        
        transcription_manager = TranscriptionManager(
            db_manager, 
            config,
            auto_detect_language=True,
            force_language=None
        )
        transcription_manager.set_file_manager(file_manager)
        
        # Process each file
        for file_info in unknown_files:
            file_id = file_info['file_id']
            file_path = file_info['original_path']
            logger.info(f"Reprocessing file for language detection: {file_path}")
            
            # Force reprocessing by setting transcription status to "not_started"
            db_manager.update_transcription_status(file_id, "not_started")
            
            # Get audio path
            audio_path = file_manager.get_audio_path(file_id)
            if not os.path.exists(audio_path):
                logger.warning(f"Audio file not found: {audio_path}. Skipping.")
                continue
                
            # Get file details
            file_details = db_manager.get_file_status(file_id)
            if not file_details:
                logger.warning(f"Could not get file details for {file_id}. Skipping.")
                continue
                
            # Transcribe with auto language detection and force flag
            transcription_manager.transcribe_audio(file_id, audio_path, file_details, True)
            
        # Display updated summary
        print("\nReprocessing completed. Updated language statistics:")
        reporter = Reporter(db_manager, config)
        reporter.display_summary()
        return
    
    # Initialize components
    file_manager = FileManager(db_manager, config)
    
    # Use source_language from config (which may have been set from command line)
    # Default to auto-detection if not specified
    source_language = config.get('source_language', 'auto')
    if source_language == 'auto':
        source_language = None  # None means auto-detect in ElevenLabs API
        logger.debug("Using automatic language detection")
    else:
        logger.debug(f"Using specified language: {source_language}")
        
    auto_detect = source_language is None
    
    transcription_manager = TranscriptionManager(
        db_manager, 
        config,
        auto_detect_language=auto_detect,
        force_language=source_language
    )
    
    translation_manager = TranslationManager(db_manager, config)
    
    # Debug output for translation configuration
    print("======== Translation Configuration ========")
    print(f"DeepL API Key in Config: {'Present' if config.get('deepl', {}).get('api_key') else 'Missing'}")
    print(f"DeepL API Key in Env: {'Present' if os.getenv('DEEPL_API_KEY') else 'Missing'}")
    print(f"Default Provider: {translation_manager.default_provider}")
    print(f"Available Providers: {list(translation_manager.providers.keys())}")
    print("=========================================")
    
    # Connect components
    transcription_manager.set_file_manager(file_manager)
    translation_manager.set_managers(file_manager, transcription_manager)
    
    # Set test mode if requested (limit to 3 files)
    if args.test:
        args.limit = 3
    
    # Process based on input source
    try:
        if args.directory:
            # Process directory
            logger.info(f"Processing directory: {args.directory}")
            file_manager.discover_files(args.directory, args.limit)
            
        elif args.file:
            # Process single file
            logger.info(f"Processing file: {args.file}")
            file_manager.process_single_file(args.file)
            
        elif args.retry:
            # Retry failed files
            status = args.status if args.status else 'failed'
            logger.info(f"Retrying files with status: {status}")
            file_manager.retry_files(status)
            
        else:
            logger.error("No input source specified. Use -d, -f, or -r option.")
            return
        
        # Determine processing mode based on arguments
        if args.dry_run:
            logger.info("Dry run mode - showing what would be processed without processing")
            # Show the list of files that would be processed for the selected operation
            if args.transcribe_only:
                # Transcription-only dry run
                if args.retry:
                    # Retrying failed files
                    status = 'failed'
                    files = file_manager.retry_files(status)
                    print("Dry-run would retry transcription for failed files:")
                    for fid in files:
                        path = file_manager.get_audio_path(fid) or ''
                        print(f"  {fid}: {path}")
                else:
                    # New transcription batch
                    to_transcribe = db_manager.get_files_for_transcription(args.limit)
                    print("Dry-run would transcribe the following files:")
                    for f in to_transcribe:
                        print(f"  {f['file_id']}: {f['original_path']}")
            else:
                # Fallback: show full report summary
                reporter.generate_report()
            return
        
        # Execute processing pipeline based on requested operations
        if args.extract_only:
            # Only perform audio extraction
            file_manager.extract_audio_batch()
        elif args.transcribe_only:
            # Extract audio and transcribe, but don't translate
            file_manager.extract_audio_batch()
            
            # Log the language setting for clarity
            if source_language:
                logger.info(f"Using specified language: {source_language}")
            else:
                logger.info("Using automatic language detection")
                
            transcription_manager.transcribe_batch()
        elif args.translate_only:
            # Only perform translation on existing transcriptions
            translation_manager.translate_batch(args.translate_only.split(','), force=args.force)
        else:
            # Full pipeline
            file_manager.extract_audio_batch()
            transcription_manager.transcribe_batch()
            translation_manager.translate_batch(['en', 'he'], force=args.force)  # Default to English and Hebrew
        
        # Generate final report
        if args.report:
            reporter.generate_report(args.report)
        else:
            reporter.display_summary()
            
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        # Cleanup and save current state
        db_manager.close()
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        db_manager.close()
        sys.exit(1)
    finally:
        # Skip automatic summary/report on dry-run
        if not args.dry_run and any([args.directory, args.file, args.retry]):
            logger.info("Generating processing summary report...")

            # Create reports directory if it doesn't exist
            reports_dir = os.path.join(config['output_directory'], 'reports')
            os.makedirs(reports_dir, exist_ok=True)

            # Generate summary report to console
            reporter.display_summary()

            # Generate detailed report file with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(reports_dir, f"processing_report_{timestamp}.txt")

            reporter.generate_report(report_file)
            logger.info(f"Detailed processing report saved to: {report_file}")

            # Show log file location
            logger.info(f"Log file: {config['log_file']}")
        # Cleanup
        db_manager.close()


if __name__ == "__main__":
    main()
