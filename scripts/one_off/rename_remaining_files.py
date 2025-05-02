#!/usr/bin/env python3
"""
Follow-up migration script to rename remaining output files to include file IDs.
This specifically targets the JSON transcript files and the orig-suffixed files 
that weren't handled in the first migration.
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
        logging.FileHandler("file_migration_followup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("file_migration_followup")

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
            'json_mapped': 0,
            'json_failed': 0,
            'orig_srt_mapped': 0,
            'orig_srt_failed': 0
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
    
    def migrate_json_files(self):
        """Rename JSON transcript files to include file IDs"""
        logger.info("Migrating JSON transcript files...")
        
        if not os.path.exists(self.transcript_dir):
            logger.warning(f"Transcript directory not found: {self.transcript_dir}")
            return
        
        # Create backup directory
        backup_dir = os.path.join(self.output_dir, 'backup', 'transcripts_json')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Find all JSON transcript files
        files = list(Path(self.transcript_dir).glob('*.json'))
        
        logger.info(f"Found {len(files)} JSON transcript files to migrate")
        
        for file_path in files:
            try:
                # Get the filename without .json extension
                filename = file_path.name
                raw_name = filename.replace('.txt.json', '') 
                ext = '.txt.json'
                
                # Try direct match first for .json files
                for key, value in self.file_map.items():
                    if raw_name == key or raw_name.startswith(key + '_'):
                        file_id = value['file_id']
                        
                        # Extract language if present
                        lang_match = re.search(r'_([a-z]{2})$', raw_name)
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
                        self.stats['json_mapped'] += 1
                        break
                else:
                    # Try extracting timestamp pattern
                    match = re.search(r'(.+?)_(\d+)(?:_[a-z]+)?', raw_name)
                    if match:
                        key = f"{match.group(1)}_{match.group(2)}"
                        
                        # If we have a mapping for this file
                        if key in self.file_map:
                            file_id = self.file_map[key]['file_id']
                            
                            # Extract language if present
                            lang_match = re.search(r'_([a-z]{2})$', raw_name)
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
                            self.stats['json_mapped'] += 1
                        else:
                            logger.warning(f"No mapping found for file: {filename}")
                            self.stats['json_failed'] += 1
                    else:
                        logger.warning(f"Could not parse filename pattern: {filename}")
                        self.stats['json_failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error migrating JSON file {file_path}: {e}")
                self.stats['json_failed'] += 1
    
    def migrate_orig_subtitle_files(self):
        """Rename subtitle files with _orig suffix to include file IDs"""
        logger.info("Migrating _orig suffix subtitle files...")
        
        if not os.path.exists(self.subtitle_dir):
            logger.warning(f"Subtitle directory not found: {self.subtitle_dir}")
            return
            
        # Create backup directory
        backup_dir = os.path.join(self.output_dir, 'backup', 'subtitles_orig')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Find all subtitle files with _orig suffix
        files = list(Path(self.subtitle_dir).glob('*_orig.srt'))
        
        logger.info(f"Found {len(files)} _orig suffix subtitle files to migrate")
        
        for file_path in files:
            try:
                # Get the filename without extension
                filename = file_path.name
                # Remove _orig.srt to get the base name
                base_name = filename.replace('_orig.srt', '')
                ext = '_orig.srt'
                
                # Try to match against our known files by removing _orig
                for key, value in self.file_map.items():
                    if base_name == key or base_name.startswith(key + '_'):
                        file_id = value['file_id']
                        
                        # Extract language if present
                        lang_match = re.search(r'_([a-z]{2})$', base_name)
                        language = lang_match.group(1) if lang_match else None
                        
                        # Create new filename with file_id
                        if language:
                            new_filename = f"{file_id}_{key}_{language}{ext}"
                        else:
                            new_filename = f"{file_id}_{key}{ext}"
                        
                        # Create language directory if needed
                        if language:
                            lang_dir = os.path.join(self.subtitle_dir, language)
                            os.makedirs(lang_dir, exist_ok=True)
                            new_path = os.path.join(lang_dir, new_filename)
                        else:
                            new_path = os.path.join(self.subtitle_dir, new_filename)
                        
                        # Backup the file
                        shutil.copy2(file_path, os.path.join(backup_dir, filename))
                        
                        # Rename the file
                        os.rename(file_path, new_path)
                        
                        logger.info(f"Migrated: {filename} -> {new_filename}")
                        self.stats['orig_srt_mapped'] += 1
                        break
                else:
                    # Try extracting timestamp pattern
                    match = re.search(r'(.+?)_(\d+)(?:_[a-z]+)?', base_name)
                    if match:
                        key = f"{match.group(1)}_{match.group(2)}"
                        
                        # If we have a mapping for this file
                        if key in self.file_map:
                            file_id = self.file_map[key]['file_id']
                            
                            # Extract language if present
                            lang_match = re.search(r'_([a-z]{2})$', base_name)
                            language = lang_match.group(1) if lang_match else None
                            
                            # Create new filename with file_id
                            if language:
                                new_filename = f"{file_id}_{key}_{language}{ext}"
                            else:
                                new_filename = f"{file_id}_{key}{ext}"
                            
                            # Create language directory if needed
                            if language:
                                lang_dir = os.path.join(self.subtitle_dir, language)
                                os.makedirs(lang_dir, exist_ok=True)
                                new_path = os.path.join(lang_dir, new_filename)
                            else:
                                new_path = os.path.join(self.subtitle_dir, new_filename)
                            
                            # Backup the file
                            shutil.copy2(file_path, os.path.join(backup_dir, filename))
                            
                            # Rename the file
                            os.rename(file_path, new_path)
                            
                            logger.info(f"Migrated: {filename} -> {new_filename}")
                            self.stats['orig_srt_mapped'] += 1
                        else:
                            logger.warning(f"No mapping found for file: {filename}")
                            self.stats['orig_srt_failed'] += 1
                    else:
                        logger.warning(f"Could not parse filename pattern: {filename}")
                        self.stats['orig_srt_failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error migrating subtitle file {file_path}: {e}")
                self.stats['orig_srt_failed'] += 1
    
    def run_migration(self):
        """Run the complete migration process for remaining files"""
        try:
            logger.info("Starting follow-up file migration process")
            logger.info("Building file mapping from database")
            self.build_file_map()
            
            # Create main backup directory
            backup_dir = os.path.join(self.output_dir, 'backup_followup')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Migrate remaining file types
            self.migrate_json_files()
            self.migrate_orig_subtitle_files()
            
            # Print summary
            logger.info("\n" + "="*60)
            logger.info("FOLLOW-UP MIGRATION SUMMARY")
            logger.info("="*60)
            logger.info(f"JSON transcript files: {self.stats['json_mapped']} migrated, {self.stats['json_failed']} failed")
            logger.info(f"Orig subtitle files: {self.stats['orig_srt_mapped']} migrated, {self.stats['orig_srt_failed']} failed")
            logger.info(f"Total files mapped: {self.stats['json_mapped'] + self.stats['orig_srt_mapped']}")
            logger.info(f"Total files failed: {self.stats['json_failed'] + self.stats['orig_srt_failed']}")
            logger.info("="*60)
            logger.info(f"Backup of all original files saved to: {backup_dir}")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Follow-up migration failed: {e}")
        finally:
            self.conn.close()

def main():
    migrator = FileMigrator()
    migrator.run_migration()

if __name__ == "__main__":
    main()
