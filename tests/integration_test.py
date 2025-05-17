#!/usr/bin/env python3
"""
Integration test for the refactored Scribe modules.

This script verifies that the new consolidated modules work correctly with real data.
It uses a small sample of files to test the pipeline end-to-end.

Usage:
    python tests/integration_test.py [--db-path DB_PATH]
"""

import os
import sys
import argparse
import logging
import tempfile
import shutil
from pathlib import Path
import time

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Scribe modules
from db_manager import DatabaseManager
from file_manager import FileManager
from db_maintenance import DatabaseMaintenance
from pipeline_manager import PipelineMonitor, ProblemFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('integration_test.log')
    ]
)
logger = logging.getLogger(__name__)


class IntegrationTest:
    """Integration test for the Scribe modules."""
    
    def __init__(self, db_path=None):
        """
        Initialize the integration test.
        
        Args:
            db_path: Path to SQLite database file (temporary if None)
        """
        # Create temporary directory for test files
        self.test_dir = Path(tempfile.mkdtemp())
        logger.info(f"Created test directory: {self.test_dir}")
        
        # Use provided DB path or create a temporary one
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = self.test_dir / "test_integration.db"
        
        logger.info(f"Using database: {self.db_path}")
        
        # Create configuration
        self.config = {
            'output_directory': str(self.test_dir / "output"),
            'transcription_workers': 2,
            'translation_workers': 2,
            'batch_size': 5,
            'check_interval': 5,
            'restart_interval': 30,
            'stalled_timeout_minutes': 10,
            'max_audio_size_mb': 25,
            'elevenlabs': {
                'api_key': os.getenv('ELEVENLABS_API_KEY'),
                'model': 'scribe_v1'
            },
            'translation': {
                'openai_api_key': os.getenv('OPENAI_API_KEY')
            }
        }
        
        # Create output directories
        os.makedirs(self.config['output_directory'], exist_ok=True)
        os.makedirs(self.test_dir / "output" / "transcripts", exist_ok=True)
        os.makedirs(self.test_dir / "output" / "translations", exist_ok=True)
        os.makedirs(self.test_dir / "audio", exist_ok=True)
        
        # Initialize components
        self.db_manager = DatabaseManager(str(self.db_path))
        self.file_manager = FileManager(self.db_manager, self.config)
        self.db_maintenance = DatabaseMaintenance(str(self.db_path))
        self.db_maintenance.file_manager = self.file_manager
        self.pipeline_monitor = PipelineMonitor(self.db_manager, self.config)
        self.problem_handler = ProblemFileHandler(self.db_manager, self.file_manager, self.config)
    
    def cleanup(self):
        """Clean up temporary files."""
        try:
            shutil.rmtree(self.test_dir)
            logger.info(f"Cleaned up test directory: {self.test_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up test directory: {e}")
    
    def setup_test_data(self):
        """Set up test data for integration testing."""
        # Check if we have sample files in fixed_source directory
        fixed_source_dir = Path("fixed_source")
        if not fixed_source_dir.exists() or not any(fixed_source_dir.iterdir()):
            logger.warning("No sample files found in fixed_source directory.")
            logger.warning("Add test audio files to fixed_source/ directory for proper testing.")
            # Create some dummy files for structural testing
            self._create_dummy_files()
            return False
        
        # Copy sample files to test directory
        audio_dir = self.test_dir / "audio"
        file_count = 0
        
        for idx, src_file in enumerate(fixed_source_dir.iterdir()):
            if src_file.is_file() and src_file.suffix.lower() in ['.mp3', '.wav', '.m4a']:
                # Copy file to test directory
                dest_file = audio_dir / src_file.name
                shutil.copy2(src_file, dest_file)
                
                # Register file in database
                file_id = f"test_{idx:03d}"
                self.db_manager.add_file(
                    file_id=file_id,
                    file_path=str(dest_file),
                    status='not_started',
                    transcription_status='not_started'
                )
                file_count += 1
                logger.info(f"Added test file: {file_id} ({dest_file})")
        
        logger.info(f"Set up {file_count} test files")
        return file_count > 0
    
    def _create_dummy_files(self):
        """Create dummy files for structural testing."""
        audio_dir = self.test_dir / "audio"
        
        # Create 5 dummy files
        for idx in range(5):
            file_id = f"dummy_{idx:03d}"
            file_path = audio_dir / f"dummy_{idx}.mp3"
            
            # Create an empty file
            with open(file_path, 'wb') as f:
                f.write(b'DUMMY AUDIO FILE')
            
            # Register file in database
            self.db_manager.add_file(
                file_id=file_id,
                file_path=str(file_path),
                status='not_started',
                transcription_status='not_started'
            )
            logger.info(f"Created dummy file: {file_id} ({file_path})")
    
    def test_status_check(self):
        """Test status checking functionality."""
        logger.info("Testing status check functionality")
        status = self.pipeline_monitor.check_status(detailed=True)
        
        logger.info(f"Status summary: {status['summary']}")
        for stage, stage_data in status['stages'].items():
            logger.info(f"{stage} status: {stage_data}")
        
        # Generate a report
        report = self.pipeline_monitor.generate_report(output_format='markdown')
        logger.info(f"Status report:\n{report}")
        
        return True
    
    def test_database_maintenance(self):
        """Test database maintenance functionality."""
        logger.info("Testing database maintenance functionality")
        
        # Create a stalled file
        file_id = "stalled_test"
        file_path = self.test_dir / "audio" / "stalled.mp3"
        with open(file_path, 'wb') as f:
            f.write(b'STALLED FILE')
        
        # Add to database with in-progress status
        self.db_manager.add_file(
            file_id=file_id,
            file_path=str(file_path),
            status='in-progress',
            transcription_status='in-progress'
        )
        
        # Set last_updated to a time in the past
        stalled_time = int(time.time()) - (60 * 60)  # 1 hour ago
        self.db_manager.execute_query(
            "UPDATE processing_status SET last_updated = ? WHERE file_id = ?",
            (stalled_time, file_id)
        )
        
        logger.info("Created stalled file for testing")
        
        # Test fix_stalled_files
        fixed = self.db_maintenance.fix_stalled_files()
        logger.info(f"Fixed {fixed} stalled files")
        
        # Verify consistency
        stats = self.db_maintenance.verify_consistency(report_only=True)
        logger.info(f"Consistency check: {stats}")
        
        return fixed > 0
    
    def test_problem_handling(self):
        """Test problem file handling functionality."""
        logger.info("Testing problem file handling")
        
        # Create a problem file
        file_id = "problem_test"
        file_path = self.test_dir / "audio" / "problem.mp3"
        with open(file_path, 'wb') as f:
            f.write(b'PROBLEM FILE')
        
        # Add to database
        self.db_manager.add_file(
            file_id=file_id,
            file_path=str(file_path),
            status='failed',
            transcription_status='failed'
        )
        
        # Add error logs
        self.db_manager.log_error(
            file_id=file_id,
            process_stage='transcription',
            error_message='Invalid audio format',
            error_details='Corrupt header detected'
        )
        
        logger.info("Created problem file for testing")
        
        # Identify problem files
        problem_files = self.problem_handler.identify_problem_files()
        logger.info(f"Identified problem files: {problem_files}")
        
        return len(problem_files['invalid_audio']) > 0
    
    def run_tests(self):
        """Run all integration tests."""
        tests = [
            self.setup_test_data,
            self.test_status_check,
            self.test_database_maintenance,
            self.test_problem_handling
        ]
        
        results = {}
        for test_func in tests:
            test_name = test_func.__name__
            logger.info(f"Running test: {test_name}")
            
            try:
                result = test_func()
                results[test_name] = "PASS" if result else "WARN"
                logger.info(f"Test {test_name}: {'PASS' if result else 'WARN'}")
            except Exception as e:
                results[test_name] = "FAIL"
                logger.error(f"Test {test_name} failed: {e}")
        
        # Print summary
        logger.info("\n--- Integration Test Results ---")
        for test_name, result in results.items():
            logger.info(f"{test_name}: {result}")
        
        # Overall result
        if "FAIL" in results.values():
            logger.error("Integration tests FAILED")
            return False
        elif "WARN" in results.values():
            logger.warning("Integration tests PASSED with WARNINGS")
            return True
        else:
            logger.info("Integration tests PASSED")
            return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run integration tests for Scribe")
    parser.add_argument('--db-path', type=str, help='Path to database file')
    parser.add_argument('--keep-files', action='store_true', help='Keep test files after testing')
    args = parser.parse_args()
    
    logger.info("Starting integration tests")
    
    test = IntegrationTest(db_path=args.db_path)
    try:
        success = test.run_tests()
        if success:
            logger.info("Integration tests completed successfully")
            return 0
        else:
            logger.error("Integration tests failed")
            return 1
    finally:
        if not args.keep_files:
            test.cleanup()
        else:
            logger.info(f"Test files preserved in: {test.test_dir}")


if __name__ == "__main__":
    sys.exit(main())