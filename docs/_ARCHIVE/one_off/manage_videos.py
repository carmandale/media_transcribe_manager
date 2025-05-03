#!/usr/bin/env python3
"""
Script to manage video files for the Bryan Rigg project.

This script:
1. Creates symbolic links in output/videos directory that match subtitle naming style
2. Provides an option to copy the output directory to an external drive,
   converting symbolic links to real files for portability
"""

import os
import logging
import argparse
import shutil
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)))
import mimetypes
from pathlib import Path
from typing import Tuple, Optional
from tqdm import tqdm

from db_manager import DatabaseManager
from file_manager import FileManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def is_video_file(filepath: str) -> bool:
    """
    Check if a file is a video file by examining its MIME type.
    
    Args:
        filepath: Path to the file to check
        
    Returns:
        True if the file is a video, False otherwise
    """
    if not os.path.exists(filepath):
        return False
        
    mime_type, _ = mimetypes.guess_type(filepath)
    if mime_type and mime_type.startswith('video/'):
        return True
    
    # Fallback to extension check for certain media types
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    file_ext = os.path.splitext(filepath)[1].lower()
    return file_ext in video_extensions

def create_video_symlinks(db_file: str, output_dir: str, dry_run: bool = False) -> Tuple[int, int]:
    """
    Create symbolic links for video files in the output directory.
    Uses the FileManager to ensure consistency with other file operations.
    
    Args:
        db_file: Path to the database file
        output_dir: Path to the output directory
        dry_run: If True, only report what would be done without making changes
        
    Returns:
        Tuple of (created_count, error_count)
    """
    # Initialize managers
    db_manager = DatabaseManager(db_file)
    
    # Create a simple config dict for FileManager
    config = {
        'output_directory': output_dir,
    }
    
    file_manager = FileManager(db_manager, config)
    
    try:
        # Get all video files from database
        db_manager.connect()
        cursor = db_manager.conn.cursor()
        cursor.execute("""
            SELECT file_id, original_path, safe_filename, media_type
            FROM media_files
            WHERE media_type = 'video'
        """)
        
        videos = cursor.fetchall()
        logger.info(f"Found {len(videos)} video files in database")
        
        if dry_run:
            logger.info("DRY RUN: No changes will be made")
        
        # Create symbolic links
        created_count = 0
        error_count = 0
        
        for video in videos:
            file_id = video['file_id']
            original_path = video['original_path']
            
            # Get the target path for the symbolic link using FileManager
            link_path = file_manager.get_video_path(file_id)
            
            if not link_path:
                logger.error(f"Could not determine video path for file ID: {file_id}")
                error_count += 1
                continue
            
            # Check if original file exists
            if not os.path.exists(original_path):
                logger.warning(f"Original file not found: {original_path}")
                error_count += 1
                continue
            
            # Check if original file is a video
            if not is_video_file(original_path):
                logger.warning(f"Original file is not a video: {original_path}")
                error_count += 1
                continue
            
            # Report what would be done in dry run
            if dry_run:
                logger.info(f"Would create symlink: {link_path} -> {original_path}")
                created_count += 1
                continue
            
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
                logger.info(f"Created symlink: {link_path} -> {original_path}")
            except Exception as e:
                logger.error(f"Error creating symlink for {file_id}: {str(e)}")
                error_count += 1
        
        action = "Would create" if dry_run else "Created"
        logger.info(f"Symlink creation completed. {action}: {created_count}, Errors: {error_count}")
        return created_count, error_count
    
    except Exception as e:
        logger.error(f"Error creating video symlinks: {str(e)}")
        return 0, 0
    finally:
        db_manager.close()

def copy_to_external(output_dir: str, target_dir: str, dry_run: bool = False) -> bool:
    """
    Copy the output directory to an external location, resolving all
    symbolic links to actual files for portability.
    
    Args:
        output_dir: Path to the output directory
        target_dir: Path to the target directory (where files will be copied)
        dry_run: If True, only report what would be done without making changes
        
    Returns:
        True if successful, False otherwise
    """
    if not target_dir:
        logger.error("Target directory must be specified")
        return False
    
    # Validate output directory
    if not os.path.isdir(output_dir):
        logger.error(f"Output directory not found: {output_dir}")
        return False
    
    # Check if target exists and is writable
    if os.path.exists(target_dir):
        if not os.path.isdir(target_dir):
            logger.error(f"Target exists but is not a directory: {target_dir}")
            return False
        if not os.access(target_dir, os.W_OK):
            logger.error(f"Target directory is not writable: {target_dir}")
            return False
    else:
        # Create target if it doesn't exist
        if not dry_run:
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Could not create target directory: {str(e)}")
                return False
    
    try:
        source_dir = output_dir
        target_output_dir = os.path.join(target_dir, os.path.basename(source_dir))
        
        logger.info(f"{'Would copy' if dry_run else 'Copying'} output directory to {target_dir}...")
        
        # First check if we have enough space
        try:
            # Calculate total source size including resolving symlinks
            total_size = 0
            symlink_size = 0
            
            # Count total files for progress bar
            total_files = 0
            for root, _, files in os.walk(source_dir):
                total_files += len(files)
                for file in files:
                    src_path = os.path.join(root, file)
                    if os.path.islink(src_path):
                        real_path = os.path.realpath(src_path)
                        if os.path.exists(real_path):
                            symlink_size += os.path.getsize(real_path)
                    else:
                        total_size += os.path.getsize(src_path)
            
            total_size += symlink_size
            
            # Get target drive free space
            target_stat = os.statvfs(target_dir)
            free_space = target_stat.f_frsize * target_stat.f_bavail
            
            logger.info(f"Required space: {total_size / (1024*1024):.2f} MB, "
                       f"Free space: {free_space / (1024*1024):.2f} MB")
            
            if total_size > free_space:
                logger.error(f"Not enough space on target drive. "
                            f"Need {total_size / (1024*1024):.2f} MB, "
                            f"have {free_space / (1024*1024):.2f} MB")
                return False
        except Exception as e:
            logger.warning(f"Could not check disk space: {str(e)}")
        
        # Dry run just reports what would be done
        if dry_run:
            logger.info(f"Would create directory: {target_output_dir}")
            
            # List of directories to copy
            dirs_to_copy = []
            for item in os.listdir(source_dir):
                src_path = os.path.join(source_dir, item)
                if os.path.isdir(src_path) and item != 'videos':
                    dirs_to_copy.append(item)
            
            logger.info(f"Would copy {len(dirs_to_copy)} directories: {', '.join(dirs_to_copy)}")
            
            # Count symlinks to resolve
            if os.path.exists(os.path.join(source_dir, 'videos')):
                videos_src = os.path.join(source_dir, 'videos')
                symlink_count = 0
                normal_file_count = 0
                
                for item in os.listdir(videos_src):
                    src_path = os.path.join(videos_src, item)
                    if os.path.islink(src_path):
                        symlink_count += 1
                    else:
                        normal_file_count += 1
                
                logger.info(f"Would copy videos directory with {symlink_count} symlinks resolved to real files "
                           f"and {normal_file_count} normal files")
            
            logger.info("DRY RUN: No files were copied")
            return True
        
        # Create target directory
        os.makedirs(target_output_dir, exist_ok=True)
        
        # First copy regular directories and files
        regular_files = []
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
                regular_files.append((src_path, target_path))
        
        # Copy regular files with progress bar
        if regular_files:
            logger.info(f"Copying {len(regular_files)} regular files...")
            for src_path, target_path in tqdm(regular_files, desc="Copying files"):
                shutil.copy2(src_path, target_path)
        
        # Now handle videos directory
        videos_src = os.path.join(source_dir, 'videos')
        videos_target = os.path.join(target_output_dir, 'videos')
        
        if os.path.exists(videos_src):
            os.makedirs(videos_target, exist_ok=True)
            
            # Get list of video files to copy
            video_files = []
            skipped_files = 0
            
            for item in os.listdir(videos_src):
                src_path = os.path.join(videos_src, item)
                target_path = os.path.join(videos_target, item)
                
                if os.path.islink(src_path):
                    # Resolve symlink to actual file
                    real_path = os.path.realpath(src_path)
                    if os.path.exists(real_path):
                        # Verify it's a video file
                        if is_video_file(real_path):
                            video_files.append((real_path, target_path, True))
                        else:
                            logger.warning(f"Skipping non-video symlink: {src_path} -> {real_path}")
                            skipped_files += 1
                    else:
                        logger.warning(f"Original file not found for symlink: {src_path}")
                        skipped_files += 1
                else:
                    # Regular file - still verify it's a video
                    if is_video_file(src_path):
                        video_files.append((src_path, target_path, False))
                    else:
                        logger.warning(f"Skipping non-video file: {src_path}")
                        skipped_files += 1
            
            # Copy video files with progress bar
            if video_files:
                logger.info(f"Copying {len(video_files)} video files...")
                for src_path, target_path, is_resolved in tqdm(video_files, desc="Copying videos"):
                    try:
                        shutil.copy2(src_path, target_path)
                    except OSError as e:
                        logger.error(f"Error copying {'resolved symlink' if is_resolved else 'file'} "
                                     f"{src_path}: {str(e)}")
                        skipped_files += 1
            
            if skipped_files > 0:
                logger.warning(f"Skipped {skipped_files} problematic files")
            
            logger.info(f"Copied {len(video_files)} video files")
        
        logger.info(f"Successfully copied output to {target_dir}")
        return True
        
    except Exception as e:
        logger.error(f"Error copying to external drive: {str(e)}")
        return False

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Manage video files in the output directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create symbolic links in output/videos
  python manage_videos.py --create-links
  
  # Do a dry run to see what would happen
  python manage_videos.py --create-links --dry-run
  
  # Copy to an external drive
  python manage_videos.py --copy-to /Volumes/ExternalDrive/BryanRigg
  
  # Do both operations
  python manage_videos.py --create-links --copy-to /Volumes/ExternalDrive/BryanRigg
        """
    )
    
    parser.add_argument(
        '--db', 
        default='./media_tracking.db', 
        help='Path to SQLite database file (default: ./media_tracking.db)'
    )
    
    parser.add_argument(
        '--output', 
        default='./output', 
        help='Output directory (default: ./output)'
    )
    
    parser.add_argument(
        '--create-links', 
        action='store_true', 
        help='Create symbolic links in output directory'
    )
    
    parser.add_argument(
        '--copy-to', 
        help='Copy to external drive with full file copies (resolving symlinks)'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Perform a dry run without making changes'
    )
    
    args = parser.parse_args()
    
    # Check if at least one action is specified
    if not args.create_links and not args.copy_to:
        parser.print_help()
        print("\nError: No action specified. Use --create-links or --copy-to.")
        return 1
    
    # Execute requested actions
    success = True
    
    if args.create_links:
        created, errors = create_video_symlinks(
            db_file=args.db, 
            output_dir=args.output,
            dry_run=args.dry_run
        )
        
        if not args.dry_run and created == 0:
            success = False
    
    if args.copy_to:
        copy_success = copy_to_external(
            output_dir=args.output, 
            target_dir=args.copy_to,
            dry_run=args.dry_run
        )
        
        if not copy_success:
            success = False
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
