#!/usr/bin/env python3
"""
Tests for FileManager.discover_files with paths containing spaces and special characters.
"""
import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path

# Ensure project root is on path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_manager import DatabaseManager
from core_modules.file_manager import FileManager


class TestFileManagerSpecialPaths(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory with spaces and special chars
        self.tempdir = Path(tempfile.mkdtemp(prefix="test fm "))
        # Initialize a temporary SQLite database in that directory
        self.db_path = self.tempdir / "test_media_tracking.db"
        self.db_manager = DatabaseManager(str(self.db_path))
        # Configure FileManager output inside tempdir
        self.output_dir = self.tempdir / "output folder"
        cfg = {'output_directory': str(self.output_dir)}
        self.fm = FileManager(self.db_manager, cfg)

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.tempdir)

    def test_discover_files_with_various_special_paths(self):
        # Create a subdirectory with spaces and special characters
        special_dir = self.tempdir / "sub dir & test"
        special_dir.mkdir()

        # Define filenames (some supported, some not)
        filenames = [
            "foo bar.mp3",
            "baz-qux (test).wav",
            "über file.mp4",
            "音楽.mp3",
            "(weird)&file name.flac",
            "notmedia.txt",
            "ARCHIVE.MP4"
        ]

        # Create each file
        for name in filenames:
            path = special_dir / name
            # Write some dummy content
            path.write_text("dummy content", encoding='utf-8')

        # Perform discovery
        discovered_ids = self.fm.discover_files(self.tempdir)

        # Count expected supported files by extension
        supported = set(self.fm.media_extensions.get('audio', []) + self.fm.media_extensions.get('video', []))
        expected_count = sum(1 for name in filenames if Path(name).suffix.lower() in supported)
        self.assertEqual(
            len(discovered_ids), expected_count,
            f"Expected {expected_count} discovered files, got {len(discovered_ids)}"
        )

        # Verify each supported file is recorded in the database
        for name in filenames:
            suffix = Path(name).suffix.lower()
            if suffix in supported:
                full_path = str(special_dir / name)
                record = self.db_manager.get_file_by_path(full_path)
                self.assertIsNotNone(
                    record,
                    f"Database missing record for {full_path}"
                )
                # Check safe_filename is non-empty
                self.assertTrue(
                    record.get('safe_filename'),
                    "safe_filename should not be empty"
                )
            else:
                # Ensure non-supported file is not in DB
                full_path = str(special_dir / name)
                record = self.db_manager.get_file_by_path(full_path)
                self.assertIsNone(
                    record,
                    f"Non-media file {full_path} should not be recorded"
                )

if __name__ == '__main__':
    unittest.main()