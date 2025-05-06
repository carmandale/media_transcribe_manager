#!/usr/bin/env python3
"""
Scribe Manager
-------------
Unified command-line tool for managing the Scribe media processing pipeline.

This script provides a single entry point for all pipeline operations including:
- Database maintenance and repair
- Pipeline monitoring and status tracking
- Transcription and translation processing
- Problem file handling

Usage:
    python scribe_manager.py [command] [options]

Commands:
    status      Check pipeline status
    monitor     Start pipeline monitoring
    restart     Restart stalled processes
    start       Start pipeline processes
    retry       Retry problematic files
    special     Apply special case processing
    fix         Fix database issues
    verify      Verify database consistency
    cleanup     Clean up stalled processes
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scribe_manager.log')
    ]
)

logger = logging.getLogger(__name__)

# Import local modules
try:
    from db_manager import DatabaseManager
    from file_manager import FileManager
    from db_maintenance import DatabaseMaintenance
    from pipeline_manager import PipelineMonitor, ProblemFileHandler, CommandLineInterface
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure all required modules are in the same directory or in PYTHONPATH")
    sys.exit(1)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file or create default config.
    
    Args:
        config_path: Path to configuration JSON file
        
    Returns:
        Configuration dictionary
    """
    config = {
        'output_directory': './output',
        'transcription_workers': 5,
        'translation_workers': 5,
        'batch_size': 20,
        'check_interval': 60,
        'restart_interval': 600,
        'stalled_timeout_minutes': 30
    }
    
    # Try to load from config file if provided
    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    config.update(loaded_config)
                logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.error(f"Error loading configuration from {config_path}: {e}")
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    # Add API keys from environment
    config['elevenlabs'] = {
        'api_key': os.getenv('ELEVENLABS_API_KEY'),
        'model': os.getenv('ELEVENLABS_MODEL', 'scribe_v1')
    }
    
    config['translation'] = {
        'openai_api_key': os.getenv('OPENAI_API_KEY'),
        'deepl_api_key': os.getenv('DEEPL_API_KEY'),
        'google_api_key': os.getenv('GOOGLE_API_KEY')
    }
    
    return config


def create_parser() -> argparse.ArgumentParser:
    """
    Create command-line argument parser.
    
    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Scribe Manager - Unified command-line tool for managing the Scribe media processing pipeline"
    )
    
    # Global options
    parser.add_argument('--db-path', type=str, default='media_tracking.db',
                      help='Path to SQLite database file')
    parser.add_argument('--config', type=str,
                      help='Path to configuration JSON file')
    parser.add_argument('--log-level', type=str, default='INFO',
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                      help='Logging level')
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Check pipeline status')
    status_parser.add_argument('--detailed', action='store_true',
                             help='Show detailed status information')
    status_parser.add_argument('--format', type=str, default='text',
                             choices=['text', 'json', 'markdown'],
                             help='Output format for report')
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Start pipeline monitoring')
    monitor_parser.add_argument('--check-interval', type=int, 
                              help='Seconds between status checks')
    monitor_parser.add_argument('--restart-interval', type=int,
                              help='Seconds between restart checks')
    monitor_parser.add_argument('--no-auto-restart', action='store_true',
                              help='Disable automatic restart of stalled processes')
    
    # Restart command
    restart_parser = subparsers.add_parser('restart', help='Restart stalled processes')
    restart_parser.add_argument('--timeout', type=int,
                              help='Minutes after which to consider a process stalled')
    restart_parser.add_argument('--no-auto-restart', action='store_true',
                              help='Only reset status, do not start new processes')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start pipeline processes')
    start_parser.add_argument('--transcription', action='store_true',
                            help='Start transcription process')
    start_parser.add_argument('--translation', type=str,
                            help='Languages to translate (comma-separated, e.g., "en,de,he")')
    start_parser.add_argument('--transcription-workers', type=int,
                            help='Number of transcription worker threads')
    start_parser.add_argument('--translation-workers', type=int,
                            help='Number of translation worker threads per language')
    start_parser.add_argument('--batch-size', type=int,
                            help='Batch size for processing')
    
    # Retry command
    retry_parser = subparsers.add_parser('retry', help='Retry problematic files')
    retry_parser.add_argument('--file-ids', type=str,
                            help='Comma-separated list of file IDs to retry')
    retry_parser.add_argument('--timeout-multiplier', type=float, default=2.0,
                            help='Multiply default timeouts by this factor')
    retry_parser.add_argument('--max-retries', type=int, default=3,
                            help='Maximum number of retry attempts')
    
    # Special command
    special_parser = subparsers.add_parser('special', help='Apply special case processing')
    special_parser.add_argument('--file-ids', type=str,
                              help='Comma-separated list of file IDs to process')
    
    # Fix command
    fix_parser = subparsers.add_parser('fix', help='Fix database issues')
    fix_subparsers = fix_parser.add_subparsers(dest='fix_command', help='Fix operation')
    
    # Fix stalled files
    stalled_parser = fix_subparsers.add_parser('stalled', help='Reset status of stalled processing')
    stalled_parser.add_argument('--timeout', type=int,
                              help='Minutes after which to consider a process stalled')
    stalled_parser.add_argument('--reset-all', action='store_true',
                              help='Reset all in-progress files regardless of time')
    
    # Fix path issues
    path_parser = fix_subparsers.add_parser('paths', help='Fix incorrect file paths')
    path_parser.add_argument('--mapping-file', type=str,
                           help='JSON file with file_id to path mapping')
    path_parser.add_argument('--no-verify', action='store_true',
                           help='Skip verification of file existence')
    
    # Fix missing transcripts
    trans_parser = fix_subparsers.add_parser('transcripts', help='Fix files with missing transcripts')
    trans_parser.add_argument('--no-reset', action='store_true',
                            help='Do not reset status to failed')
    trans_parser.add_argument('--batch-size', type=int,
                            help='Process in batches of this size')
    
    # Mark problem files
    mark_parser = fix_subparsers.add_parser('mark', help='Mark problematic files')
    mark_parser.add_argument('--file-ids', type=str,
                           help='Comma-separated list of file IDs to mark')
    mark_parser.add_argument('--status', type=str, default='qa_failed',
                           help='Status to set (default: qa_failed)')
    mark_parser.add_argument('--reason', type=str, default='',
                           help='Reason for marking as problem')
    
    # Fix Hebrew translations
    hebrew_parser = fix_subparsers.add_parser('hebrew', help='Fix Hebrew translations with placeholder text')
    hebrew_parser.add_argument('--batch-size', type=int,
                             help='Process in batches of this size')
    hebrew_parser.add_argument('--model', type=str, default='gpt-4o',
                             help='OpenAI model to use for translation')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify database consistency')
    verify_parser.add_argument('--auto-fix', action='store_true',
                             help='Automatically fix inconsistencies')
    verify_parser.add_argument('--report-only', action='store_true',
                             help='Only report issues, no fixes')
    
    # Cleanup command - deprecated but kept for backward compatibility
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up stalled processes (deprecated)')
    cleanup_parser.add_argument('--timeout', type=int, default=30,
                              help='Minutes after which to consider a process stalled')
    
    return parser


def main():
    """Main function."""
    # Create parser and parse arguments
    parser = create_parser()
    args = parser.parse_args()
    
    # Set up logging
    log_level = getattr(logging, args.log_level)
    logging.getLogger().setLevel(log_level)
    
    # Check if a command was provided
    if not args.command:
        parser.print_help()
        return 1
    
    # Load configuration
    config = load_config(args.config)
    
    # Connect to database
    db_manager = DatabaseManager(args.db_path)
    
    # Create file manager
    file_manager = FileManager(db_manager, config)
    
    # Create maintenance and pipeline components
    db_maintenance = DatabaseMaintenance(args.db_path)
    db_maintenance.file_manager = file_manager
    
    pipeline_monitor = PipelineMonitor(db_manager, config)
    problem_handler = ProblemFileHandler(db_manager, file_manager, config)
    
    # Handle pipeline commands using pipeline_manager.py
    if args.command in ['status', 'monitor', 'restart', 'start', 'retry', 'special']:
        # Use the CommandLineInterface from pipeline_manager.py
        cli = CommandLineInterface()
        return cli.run_command(args)
    
    # Handle database maintenance commands
    elif args.command == 'fix':
        # Check if a fix command was provided
        if not hasattr(args, 'fix_command') or not args.fix_command:
            logger.error("No fix operation specified")
            return 1
        
        # Handle fix commands
        if args.fix_command == 'stalled':
            timeout = args.timeout or config.get('stalled_timeout_minutes', 30)
            fixed = db_maintenance.fix_stalled_files(timeout_minutes=timeout, reset_all=args.reset_all)
            logger.info(f"Fixed {fixed} stalled files")
            
        elif args.fix_command == 'paths':
            # Load mapping if provided
            path_mapping = None
            if args.mapping_file:
                mapping_path = Path(args.mapping_file)
                if mapping_path.exists():
                    try:
                        with open(mapping_path, 'r', encoding='utf-8') as f:
                            path_mapping = json.load(f)
                    except Exception as e:
                        logger.error(f"Error loading path mapping: {e}")
                        return 1
                        
            fixed = db_maintenance.fix_path_issues(path_mapping=path_mapping, verify=not args.no_verify)
            logger.info(f"Fixed {fixed} file paths")
            
        elif args.fix_command == 'transcripts':
            batch_size = args.batch_size or config.get('batch_size', 20)
            fixed = db_maintenance.fix_missing_transcripts(reset_to_failed=not args.no_reset, batch_size=batch_size)
            logger.info(f"Fixed {fixed} files with missing transcripts")
            
        elif args.fix_command == 'mark':
            # Parse file IDs if provided
            file_ids = None
            if args.file_ids:
                file_ids = [fid.strip() for fid in args.file_ids.split(',')]
                
            marked = db_maintenance.mark_problem_files(file_ids=file_ids, status=args.status, reason=args.reason)
            logger.info(f"Marked {marked} files as {args.status}")
            
        elif args.fix_command == 'hebrew':
            batch_size = args.batch_size or config.get('batch_size', 20)
            fixed = db_maintenance.fix_hebrew_translations(batch_size=batch_size, language_model=args.model)
            logger.info(f"Fixed {fixed} Hebrew translations")
            
        else:
            logger.error(f"Unknown fix command: {args.fix_command}")
            return 1
    
    # Handle verify command
    elif args.command == 'verify':
        stats = db_maintenance.verify_consistency(auto_fix=args.auto_fix, report_only=args.report_only)
        
        # Print report
        print("Database consistency verification results:")
        print(f"Total files: {stats['total_files']}")
        print(f"Files with missing source: {stats['missing_source']}")
        print(f"Files with missing transcript: {stats['missing_transcript']}")
        print(f"Files with missing EN translation: {stats['missing_translation_en']}")
        print(f"Files with missing DE translation: {stats['missing_translation_de']}")
        print(f"Files with missing HE translation: {stats['missing_translation_he']}")
        print(f"Total files with inconsistencies: {stats['status_mismatch']}")
        
        if args.auto_fix:
            print(f"Fixed: {stats['fixed']}")
    
    # Handle cleanup command (deprecated)
    elif args.command == 'cleanup':
        logger.warning("The 'cleanup' command is deprecated. Please use 'fix stalled' instead.")
        timeout = args.timeout or config.get('stalled_timeout_minutes', 30)
        fixed = db_maintenance.fix_stalled_files(timeout_minutes=timeout)
        logger.info(f"Fixed {fixed} stalled files")
    
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())