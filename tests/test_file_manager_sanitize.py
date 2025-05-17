#!/usr/bin/env python3
"""
Tests for FileManager.sanitize_filename producing readable slugs.
"""
import os
import sys
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_modules.file_manager import FileManager


class TestFileManagerSanitize(unittest.TestCase):
    def setUp(self):
        # Use a dummy db_manager (None) and minimal config
        self.fm = FileManager(db_manager=None, config={'output_directory': '.'})

    def test_basic_slugification(self):
        cases = {
            'Simple File.mp4': 'simple_file.mp4',
            'Über File(1).mp3': 'uber_file_1.mp3',
            ' spaces  and---dashes .wav': 'spaces_and_dashes.wav',
            '___Crazy_Name###.flac': 'crazy_name.flac',
            '中文 文件.mp4': 'file.mp4',
            '123 Numbered File.MP4': '123_numbered_file.mp4',
            'file   with    many spaces.mp3': 'file_with_many_spaces.mp3',
        }
        for original, expected in cases.items():
            with self.subTest(original=original):
                safe = self.fm.sanitize_filename(original)
                self.assertEqual(
                    safe, expected,
                    f"sanitize_filename('{original}') -> '{safe}', expected '{expected}'"
                )

    def test_empty_name(self):
        # After removing all characters, default to 'file'
        safe = self.fm.sanitize_filename('!!!.mp4')
        self.assertEqual(safe, 'file.mp4')

    def test_lowercase_and_unicode_ext(self):
        # Extension should be lowercased
        safe = self.fm.sanitize_filename('Video.MKV')
        self.assertEqual(safe, 'video.mkv')

if __name__ == '__main__':
    unittest.main()