#!/usr/bin/env python3
"""
Create a videos directory in the output folder with symbolic links to
the original video files, using the same ID-based naming convention 
as subtitle files for consistency.
"""

import os
import logging
import argparse
import shutil
from pathlib import Path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)))

from db_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_video_symlinks(db_file='./media_tracking.db', output_dir='./output'):
    """
    Create symbolic links to original video files in the output/videos directory
    using the same naming pattern as subtitle files for consistency.
    """
    # Initialize database manager
    db_manager = DatabaseManager(db_file)
    
    # Create videos directory if it doesn't exist
    videos_dir = os.path.join(output_dir, 'videos')
    os.makedirs(videos_dir, exist_ok=True)
    
    # Get all video files from database
    try:
        db_manager.connect()
        cursor = db_manager.conn.cursor()
        cursor.execute("""
            SELECT file_id, original_path, safe_filename, media_type
            FROM media_files
            WHERE media_type = 'video'
        """)
        
        videos = cursor.fetchall()
        logger.info(f"Found {len(videos)} video files in database")
        
        # Create symbolic links
        created_count = 0
        error_count = 0
        
        for video in videos:
            file_id = video['file_id']
            original_path = video['original_path']
            safe_filename = video['safe_filename']
            
            # Check if original file exists
            if not os.path.exists(original_path):
                logger.warning(f"Original file not found: {original_path}")
                error_count += 1
                continue
            
            # Create a filename in the same format as subtitles
            # Format: {file_id}_{base_name}_orig.{extension}
            base_name = os.path.splitext(safe_filename)[0]
            file_ext = os.path.splitext(original_path)[1].lower()
            link_filename = f"{file_id}_{base_name}_orig{file_ext}"
            link_path = os.path.join(videos_dir, link_filename)
            
            # Remove existing link if it exists
            if os.path.exists(link_path):
                if os.path.islink(link_path):
                    os.unlink(link_path)
                    logger.debug(f"Removed existing symlink: {link_path}")
                else:
                    logger.warning(f"Non-symlink file exists at {link_path}, skipping")
                    error_count += 1
                    continue
            
            # Create symbolic link
            try:
                os.symlink(original_path, link_path)
                created_count += 1
                logger.debug(f"Created symlink: {link_path} -> {original_path}")
            except Exception as e:
                logger.error(f"Error creating symlink for {file_id}: {str(e)}")
                error_count += 1
        
        logger.info(f"Symlink creation completed. Created: {created_count}, Errors: {error_count}")
        return created_count
    
    except Exception as e:
        logger.error(f"Error creating video symlinks: {str(e)}")
        return 0
    finally:
        db_manager.close()

def copy_to_external(output_dir='./output', target_dir=None):
    """
    Copy the output directory to an external location, resolving all
    symbolic links to actual files for portability.
    """
    if not target_dir:
        logger.error("Target directory must be specified")
        return False
    
    try:
        logger.info(f"Copying output directory to {target_dir}...")
        source_dir = output_dir
        target_output_dir = os.path.join(target_dir, os.path.basename(source_dir))
        
        # Create target directory
        os.makedirs(target_output_dir, exist_ok=True)
        
        # First copy regular directories and files
        for item in os.listdir(source_dir):
            src_path = os.path.join(source_dir, item)
            target_path = os.path.join(target_output_dir, item)
            
            # Skip videos directory - handle separately
            if item == 'videos':
                continue
                
            # Copy other directories and files
            if os.path.isdir(src_path):
                logger.info(f"Copying directory: {item}")
                shutil.copytree(src_path, target_path, dirs_exist_ok=True)
            else:
                logger.info(f"Copying file: {item}")
                shutil.copy2(src_path, target_path)
        
        # Now handle videos directory
        videos_src = os.path.join(source_dir, 'videos')
        videos_target = os.path.join(target_output_dir, 'videos')
        
        if os.path.exists(videos_src):
            os.makedirs(videos_target, exist_ok=True)
            
            # Copy each video file, resolving symlinks
            file_count = 0
            for item in os.listdir(videos_src):
                src_path = os.path.join(videos_src, item)
                target_path = os.path.join(videos_target, item)
                
                if os.path.islink(src_path):
                    # Resolve symlink to actual file
                    real_path = os.path.realpath(src_path)
                    if os.path.exists(real_path):
                        logger.info(f"Copying video {file_count+1}: {item}")
                        shutil.copy2(real_path, target_path)
                        file_count += 1
                    else:
                        logger.warning(f"Original file not found for symlink: {src_path}")
                else:
                    # Regular file
                    shutil.copy2(src_path, target_path)
                    file_count += 1
            
            logger.info(f"Copied {file_count} video files")
        
        logger.info(f"Successfully copied output to {target_dir}")
        return True
        
    except Exception as e:
        logger.error(f"Error copying to external drive: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Manage video files in output directory")
    parser.add_argument('--db', default='./media_tracking.db', help='Path to SQLite database file')
    parser.add_argument('--output', default='./output', help='Output directory')
    parser.add_argument('--create-links', action='store_true', help='Create symbolic links in output directory')
    parser.add_argument('--copy-to', help='Copy to external drive with full file copies (resolving symlinks)')
    
    args = parser.parse_args()
    
    if args.create_links:
        create_video_symlinks(db_file=args.db, output_dir=args.output)
    
    if args.copy_to:
        copy_to_external(output_dir=args.output, target_dir=args.copy_to)
    
    if not args.create_links and not args.copy_to:
        # If no arguments provided, create links by default
        create_video_symlinks(db_file=args.db, output_dir=args.output)

if __name__ == "__main__":
    main()
