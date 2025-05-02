#!/usr/bin/env python3
"""
Report Generator for Media Transcription and Translation Tool
------------------------------------------------------------
Standalone script to generate detailed reports from the database.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv
import datetime
import time
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import our custom modules
from db_manager import DatabaseManager
from reporter import Reporter

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate detailed reports for the Media Transcription and Translation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate a JSON report:
    python generate_report.py --output report.json
    
  Generate a YAML report:
    python generate_report.py --output report.yaml
    
  Display a summary:
    python generate_report.py --summary
        """
    )
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '-o', '--output', 
        help="Path to save the report file (format determined by extension: .json, .yaml, .txt). "
             "If a simple filename is provided (no path), it will be saved to ./output/reports/"
    )
    output_group.add_argument(
        '--summary', 
        action='store_true',
        help="Display a summary of the processing status"
    )
    
    # Database options
    db_group = parser.add_argument_group('Database Options')
    db_group.add_argument(
        '--db', 
        default="./media_tracking.db",
        help="SQLite database file (default: ./media_tracking.db)"
    )
    
    return parser.parse_args()

def main():
    """Main entry point for report generation."""
    args = parse_args()
    
    # Check that at least one output option is specified
    if not args.output and not args.summary:
        logger.error("You must specify an output option (--output or --summary)")
        return
    
    # Initialize database manager
    db_manager = DatabaseManager(args.db)
    
    # Basic configuration for the reporter
    config = {
        'output_directory': './output',
        'database_file': args.db
    }
    
    # Initialize reporter
    reporter = Reporter(db_manager, config)
    
    try:
        # Display summary if requested
        if args.summary:
            reporter.display_summary()
            # Auto-append processing summary to docs/processing_summary.md
            try:
                date_str = datetime.datetime.now().strftime('%Y-%m-%d')
                time_str = datetime.datetime.now().strftime('%I:%M%p').lower()
                timezone = time.strftime('%Z').lower()
                stats = reporter.db_manager.get_summary_statistics()
                total_files = stats['total_files']
                transcripts_count = len(glob.glob(os.path.join('output', 'transcripts', '*.txt')))
                en_trans_count = reporter.db_manager.execute_query(
                    "SELECT COUNT(*) AS c FROM processing_status WHERE translation_en_status='completed'"
                )[0]['c']
                de_trans_count = reporter.db_manager.execute_query(
                    "SELECT COUNT(*) AS c FROM processing_status WHERE translation_de_status='completed'"
                )[0]['c']
                he_trans_count = reporter.db_manager.execute_query(
                    "SELECT COUNT(*) AS c FROM processing_status WHERE translation_he_status='completed'"
                )[0]['c']
                en_subs_count = len(glob.glob(os.path.join('output', 'subtitles', 'en', '*.srt')))
                de_subs_count = len(glob.glob(os.path.join('output', 'subtitles', 'de', '*.srt')))
                he_subs_count = len(glob.glob(os.path.join('output', 'subtitles', 'he', '*.srt')))
                lines = [
                    f"_Data collected on {date_str}_",
                    f"time: {time_str} {timezone}",
                    "",
                    "| Category                          | Count |",
                    "|-----------------------------------|------:|",
                    f"| Total media files                 | {total_files}   |",
                    f"| Transcripts completed             | {transcripts_count}   |",
                    f"| English translations completed    | {en_trans_count}   |",
                    f"| German translations completed     | {de_trans_count}   |",
                    f"| Hebrew translations completed     | {he_trans_count}   |",
                    f"| English subtitles generated       | {en_subs_count}     |",
                    f"| German subtitles generated        | {de_subs_count}     |",
                    f"| Hebrew subtitles generated        | {he_subs_count}     |",
                    ""
                ]
                with open(os.path.join('docs', 'processing_summary.md'), 'a') as md_file:
                    md_file.write("\n".join(lines) + "\n")
            except Exception as e:
                logger.error(f"Failed to update processing summary: {e}")
        
        # Generate detailed report if output file specified
        if args.output:
            # If just a filename is provided (no path), save to reports directory
            output_path = args.output
            if not os.path.dirname(output_path):
                reports_dir = Path('./output/reports')
                reports_dir.mkdir(parents=True, exist_ok=True)
                output_path = str(reports_dir / output_path)
            
            logger.info(f"Generating report to {output_path}")
            reporter.generate_report(output_path)
            logger.info(f"Report generated successfully: {output_path}")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        db_manager.close()

if __name__ == "__main__":
    main()
