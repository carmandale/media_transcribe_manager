#!/usr/bin/env python3
"""
Migration script to rename existing output files to include file IDs.
This preserves your existing transcription and translation files while ensuring 
they can be properly tracked and connected to the database records.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)))
import sqlite3
import shutil
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("file_migration.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("file_migration")

class FileMigrator:
    def __init__(self, db_path='media_tracking.db', output_dir='output'):
        self.db_path = db_path
        self.output_dir = output_dir
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Directories
        self.transcript_dir = os.path.join(output_dir, 'transcripts')
        self.translation_dir = os.path.join(output_dir, 'translations')
        self.subtitle_dir = os.path.join(output_dir, 'subtitles')
        
        # Stats
        self.stats = {
            'transcript_mapped': 0,
            'transcript_failed': 0,
            'translation_mapped': 0,
            'translation_failed': 0,
            'subtitle_mapped': 0,
            'subtitle_failed': 0
        }
        
        # Migration maps
        self.file_map = {}  # Maps original filename pattern to file_id
    
    def build_file_map(self):
        """Build a mapping between existing filenames and file IDs"""
        logger.info("Building file mapping from database...")
        
        # Get all files from the database
        self.cursor.execute("""
        SELECT file_id, safe_filename, original_path 
        FROM media_files
        """)
        
        for row in self.cursor.fetchall():
            file_id = row['file_id']
            safe_filename = row['safe_filename']
            original_path = row['original_path']
            
            # Extract base name without extension for matching
            base_name = os.path.splitext(safe_filename)[0]
            original_name = os.path.basename(original_path)
            
            # Store mapping
            self.file_map[base_name] = {
                'file_id': file_id,
                'original_name': original_name
            }
            
        logger.info(f"Built mapping for {len(self.file_map)} files")
    
    def migrate_transcript_files(self):
        """Rename transcript files to include file IDs"""
        logger.info("Migrating transcript files...")
        
        if not os.path.exists(self.transcript_dir):
            logger.warning(f"Transcript directory not found: {self.transcript_dir}")
            return
        
        # Create backup directory
        backup_dir = os.path.join(self.output_dir, 'backup', 'transcripts')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Find all transcript files
        files = list(Path(self.transcript_dir).glob('*.txt')) + list(Path(self.transcript_dir).glob('*.json'))
        
        logger.info(f"Found {len(files)} transcript files to migrate")
        
        for file_path in files:
            try:
                # Get the filename without extension
                filename = file_path.name
                base_name = os.path.splitext(filename)[0]
                ext = os.path.splitext(filename)[1]
                
                # Extract the base timestamp portion
                match = re.search(r'(.+?)_(\d+)(?:_[a-z]+)?$', base_name)
                if match:
                    key = f"{match.group(1)}_{match.group(2)}"
                    
                    # If we have a mapping for this file
                    if key in self.file_map:
                        file_id = self.file_map[key]['file_id']
                        original_name = self.file_map[key]['original_name']
                        
                        # Check if it's a language-specific file
                        lang_match = re.search(r'_([a-z]{2})$', base_name)
                        language = lang_match.group(1) if lang_match else None
                        
                        # Create new filename with file_id
                        if language:
                            new_filename = f"{file_id}_{key}_{language}{ext}"
                        else:
                            new_filename = f"{file_id}_{key}{ext}"
                        
                        # Backup the file
                        shutil.copy2(file_path, os.path.join(backup_dir, filename))
                        
                        # Rename the file
                        new_path = os.path.join(self.transcript_dir, new_filename)
                        os.rename(file_path, new_path)
                        
                        logger.info(f"Migrated: {filename} -> {new_filename}")
                        self.stats['transcript_mapped'] += 1
                    else:
                        logger.warning(f"No mapping found for file: {filename}")
                        self.stats['transcript_failed'] += 1
                else:
                    logger.warning(f"Could not parse filename pattern: {filename}")
                    self.stats['transcript_failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error migrating transcript file {file_path}: {e}")
                self.stats['transcript_failed'] += 1
    
    def migrate_translation_files(self):
        """Rename translation files to include file IDs"""
        logger.info("Migrating translation files...")
        
        if not os.path.exists(self.translation_dir):
            logger.warning(f"Translation directory not found: {self.translation_dir}")
            return
            
        # Create backup directory
        backup_dir = os.path.join(self.output_dir, 'backup', 'translations')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Find all translation files (they're directly in the translations dir)
        files = list(Path(self.translation_dir).glob('*.txt'))
        
        logger.info(f"Found {len(files)} translation files to migrate")
        
        for file_path in files:
            try:
                # Get the filename without extension
                filename = file_path.name
                base_name = os.path.splitext(filename)[0]
                ext = os.path.splitext(filename)[1]
                
                # Extract the base timestamp portion and language
                match = re.search(r'(.+?)_(\d+)_([a-z]{2})$', base_name)
                if match:
                    key = f"{match.group(1)}_{match.group(2)}"
                    language = match.group(3)
                    
                    # If we have a mapping for this file
                    if key in self.file_map:
                        file_id = self.file_map[key]['file_id']
                        
                        # Create new filename with file_id
                        new_filename = f"{file_id}_{key}_{language}{ext}"
                        
                        # Create language directory
                        lang_dir = os.path.join(self.translation_dir, language)
                        os.makedirs(lang_dir, exist_ok=True)
                        
                        # Backup the file
                        shutil.copy2(file_path, os.path.join(backup_dir, filename))
                        
                        # Move the file to language dir with new name
                        new_path = os.path.join(lang_dir, new_filename)
                        os.rename(file_path, new_path)
                        
                        logger.info(f"Migrated: {filename} -> {language}/{new_filename}")
                        self.stats['translation_mapped'] += 1
                    else:
                        logger.warning(f"No mapping found for file: {filename}")
                        self.stats['translation_failed'] += 1
                else:
                    logger.warning(f"Could not parse filename pattern: {filename}")
                    self.stats['translation_failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error migrating translation file {file_path}: {e}")
                self.stats['translation_failed'] += 1
    
    def migrate_subtitle_files(self):
        """Rename subtitle files to include file IDs"""
        logger.info("Migrating subtitle files...")
        
        if not os.path.exists(self.subtitle_dir):
            logger.warning(f"Subtitle directory not found: {self.subtitle_dir}")
            return
            
        # Create backup directory
        backup_dir = os.path.join(self.output_dir, 'backup', 'subtitles')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Find all subtitle files
        files = list(Path(self.subtitle_dir).glob('*.srt'))
        
        logger.info(f"Found {len(files)} subtitle files to migrate")
        
        for file_path in files:
            try:
                # Get the filename without extension
                filename = file_path.name
                base_name = os.path.splitext(filename)[0]
                ext = os.path.splitext(filename)[1]
                
                # Extract the base timestamp portion and language
                match = re.search(r'(.+?)_(\d+)_([a-z]{2})$', base_name)
                if match:
                    key = f"{match.group(1)}_{match.group(2)}"
                    language = match.group(3)
                    
                    # If we have a mapping for this file
                    if key in self.file_map:
                        file_id = self.file_map[key]['file_id']
                        
                        # Create new filename with file_id
                        new_filename = f"{file_id}_{key}_{language}{ext}"
                        
                        # Create language directory
                        lang_dir = os.path.join(self.subtitle_dir, language)
                        os.makedirs(lang_dir, exist_ok=True)
                        
                        # Backup the file
                        shutil.copy2(file_path, os.path.join(backup_dir, filename))
                        
                        # Move the file to language dir with new name
                        new_path = os.path.join(lang_dir, new_filename)
                        os.rename(file_path, new_path)
                        
                        logger.info(f"Migrated: {filename} -> {language}/{new_filename}")
                        self.stats['subtitle_mapped'] += 1
                    else:
                        logger.warning(f"No mapping found for file: {filename}")
                        self.stats['subtitle_failed'] += 1
                else:
                    logger.warning(f"Could not parse filename pattern: {filename}")
                    self.stats['subtitle_failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error migrating subtitle file {file_path}: {e}")
                self.stats['subtitle_failed'] += 1
    
    def run_migration(self):
        """Run the complete migration process"""
        try:
            logger.info("Starting file migration process")
            logger.info("Building file mapping from database")
            self.build_file_map()
            
            # Create main backup directory
            backup_dir = os.path.join(self.output_dir, 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Migrate each file type
            self.migrate_transcript_files()
            self.migrate_translation_files()
            self.migrate_subtitle_files()
            
            # Print summary
            logger.info("\n" + "="*60)
            logger.info("MIGRATION SUMMARY")
            logger.info("="*60)
            logger.info(f"Transcript files: {self.stats['transcript_mapped']} migrated, {self.stats['transcript_failed']} failed")
            logger.info(f"Translation files: {self.stats['translation_mapped']} migrated, {self.stats['translation_failed']} failed")
            logger.info(f"Subtitle files: {self.stats['subtitle_mapped']} migrated, {self.stats['subtitle_failed']} failed")
            logger.info(f"Total files mapped: {self.stats['transcript_mapped'] + self.stats['translation_mapped'] + self.stats['subtitle_mapped']}")
            logger.info(f"Total files failed: {self.stats['transcript_failed'] + self.stats['translation_failed'] + self.stats['subtitle_failed']}")
            logger.info("="*60)
            logger.info(f"Backup of all original files saved to: {backup_dir}")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
        finally:
            self.conn.close()

def main():
    migrator = FileMigrator()
    migrator.run_migration()

if __name__ == "__main__":
    main()
