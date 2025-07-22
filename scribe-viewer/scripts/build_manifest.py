#!/usr/bin/env python3
"""
Build Manifest Script for Scribe Viewer Web Application

This script processes the Scribe project data to generate a comprehensive manifest.json file
that serves as the sole data source for the Next.js front-end application.

Main responsibilities:
1. Retrieve all files from the database
2. Parse metadata from original filenames
3. Convert SRT files to VTT format
4. Generate transcript cues for synchronized highlighting
5. Assemble and output the manifest.json file
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to Python path to import scribe modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scribe.database import Database
import webvtt


def parse_filename_metadata(filename: str) -> Dict[str, str]:
    """
    Intelligently parse metadata from filename using various patterns.
    
    Patterns to match:
    - YYYY-MM-DD_FirstName_LastName_Interview_ID.mp4
    - FirstName_LastName_YYYY-MM-DD.mp4
    - Interview_FirstName_LastName_Date.mp4
    - And various other common patterns
    
    Args:
        filename: The original file path from the database
        
    Returns:
        Dictionary with 'date' and 'interviewee' keys
    """
    # Extract just the filename without path
    base_name = os.path.basename(filename)
    name_without_ext = os.path.splitext(base_name)[0]
    
    # Initialize with defaults
    metadata = {
        'date': None,
        'interviewee': 'Unknown Interviewee'
    }
    
    # Pattern 1: YYYY-MM-DD at the beginning
    date_first_pattern = r'^(\d{4}-\d{2}-\d{2})_(.+?)(?:_Interview)?(?:_\d+)?$'
    match = re.match(date_first_pattern, name_without_ext)
    if match:
        metadata['date'] = match.group(1)
        # Clean up the name - replace underscores with spaces
        name_parts = match.group(2).replace('_', ' ')
        metadata['interviewee'] = name_parts
        return metadata
    
    # Pattern 2: Date at the end (various formats)
    date_end_pattern = r'^(.+?)_(\d{4}-\d{2}-\d{2})$'
    match = re.match(date_end_pattern, name_without_ext)
    if match:
        metadata['date'] = match.group(2)
        name_parts = match.group(1).replace('_', ' ')
        # Remove common words
        name_parts = re.sub(r'\b(Interview|interview|Recording|recording)\b', '', name_parts).strip()
        metadata['interviewee'] = name_parts
        return metadata
    
    # Pattern 3: Date in middle with Interview prefix/suffix
    interview_pattern = r'^(?:Interview_)?(.+?)_(\d{4}-\d{2}-\d{2})(?:_Interview)?$'
    match = re.match(interview_pattern, name_without_ext)
    if match:
        metadata['date'] = match.group(2)
        metadata['interviewee'] = match.group(1).replace('_', ' ')
        return metadata
    
    # Pattern 4: Try to find any date in the filename
    date_pattern = r'(\d{4}-\d{2}-\d{2})'
    date_match = re.search(date_pattern, name_without_ext)
    if date_match:
        metadata['date'] = date_match.group(1)
        # Remove the date and clean up the rest as the name
        name_parts = re.sub(date_pattern, '', name_without_ext)
        name_parts = name_parts.strip('_- ').replace('_', ' ')
        name_parts = re.sub(r'\b(Interview|interview|Recording|recording)\b', '', name_parts).strip()
        if name_parts:
            metadata['interviewee'] = name_parts
    
    # If no date found but we can extract a name
    if not metadata['date']:
        # Try to extract name by removing common words
        cleaned_name = name_without_ext.replace('_', ' ')
        cleaned_name = re.sub(r'\b(Interview|interview|Recording|recording|Video|video)\b', '', cleaned_name).strip()
        if cleaned_name:
            metadata['interviewee'] = cleaned_name
    
    return metadata


def convert_srt_to_vtt(srt_path: str, vtt_path: str) -> bool:
    """
    Convert an SRT file to VTT format.
    
    Args:
        srt_path: Path to the source SRT file
        vtt_path: Path where the VTT file should be saved
        
    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # The webvtt-py library can read the file directly
        vtt = webvtt.from_srt(srt_path)
        vtt.save(vtt_path)
        return True
        
    except Exception as e:
        logger.error(f"Error converting {srt_path} to VTT: {e}")
        return False


def parse_vtt_for_cues(vtt_path: str) -> List[Dict[str, any]]:
    """
    Parse a VTT file to extract cues for synchronized highlighting.
    
    Args:
        vtt_path: Path to the VTT file
        
    Returns:
        List of cue objects with 'time' (in seconds) and 'text' fields
    """
    cues = []
    
    try:
        vtt = webvtt.read(vtt_path)
        
        for caption in vtt:
            # Convert timestamp to seconds
            # webvtt-py provides start as a string like "00:00:01.000"
            time_parts = caption.start.split(':')
            hours = float(time_parts[0])
            minutes = float(time_parts[1])
            seconds = float(time_parts[2])
            total_seconds = hours * 3600 + minutes * 60 + seconds
            
            cues.append({
                'time': total_seconds,
                'text': caption.text
            })
            
    except Exception as e:
        logger.error(f"Error parsing VTT file {vtt_path}: {e}")
    
    return cues


def read_full_transcript(file_path: str) -> str:
    """
    Read the full transcript text from a file.
    
    Args:
        file_path: Path to the transcript file
        
    Returns:
        The full transcript text or empty string if error
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading transcript {file_path}: {e}")
        return ""


def process_interview(file_record: Dict, project_root: Path) -> Optional[Dict]:
    """
    Process a single interview file record to create its manifest entry.
    
    Args:
        file_record: Database record for the file
        project_root: The root directory of the scribe project
        
    Returns:
        Manifest entry for this interview or None if processing fails
    """
    file_id = file_record['file_id']
    original_path = Path(file_record['original_path'])
    output_base_dir = project_root / "output"
    
    # Parse metadata from filename
    metadata = parse_filename_metadata(original_path.name)
    
    # Add empty summary field (can be filled by admin later)
    metadata['summary'] = ""
    
    # Build paths
    interview_dir = output_base_dir / file_id
    
    # Check if directory exists
    if not interview_dir.exists():
        logger.warning(f"Output directory not found for {file_id}, skipping.")
        return None
    
    # --- Symbolic Link Creation ---
    media_dir = project_root / "scribe-viewer" / "public" / "media" / file_id
    media_dir.mkdir(parents=True, exist_ok=True)
    
    # Use safe filename for symlink (ID + extension)
    file_extension = original_path.suffix
    safe_filename = f"{file_id}{file_extension}"
    symlink_path = media_dir / safe_filename
    
    if not symlink_path.exists():
        try:
            os.symlink(original_path.resolve(), symlink_path)
            logger.info(f"  ✓ Created symlink for video: {symlink_path}")
        except Exception as e:
            logger.error(f"  ✗ Failed to create symlink for {safe_filename}: {e}")
            return None # Cannot proceed without the video
    # ---------------------------

    # Initialize manifest entry
    manifest_entry = {
        'id': file_id,
        'metadata': metadata,
        'assets': {
            'video': f"/media/{file_id}/{safe_filename}",
            'subtitles': {}
        },
        'transcripts': []
    }
    
    # Process each language
    languages = [
        ('en', 'English'),
        ('de', 'German'),
        ('he', 'Hebrew')
    ]
    
    for lang_code, lang_name in languages:
        # Paths for this language
        srt_path = os.path.join(interview_dir, f"{file_id}.{lang_code}.srt")
        vtt_path = os.path.join(interview_dir, f"{file_id}.{lang_code}.vtt")
        txt_path = os.path.join(interview_dir, f"{file_id}.{lang_code}.txt")
        
        # Skip if SRT doesn't exist
        if not os.path.exists(srt_path):
            logger.warning(f"SRT file not found for {file_id} in {lang_code}, skipping this language.")
            continue
        
        # Convert SRT to VTT
        if convert_srt_to_vtt(srt_path, vtt_path):
            # Create symlink for VTT file
            vtt_filename = f"{file_id}.{lang_code}.vtt"
            vtt_symlink_path = media_dir / vtt_filename
            
            if not vtt_symlink_path.exists():
                try:
                    os.symlink(Path(vtt_path).resolve(), vtt_symlink_path)
                    logger.info(f"  ✓ Created symlink for {lang_code} subtitles: {vtt_symlink_path}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to create symlink for {vtt_filename}: {e}")
                    continue  # Skip this language if we can't create the symlink
            
            # Add subtitle asset
            manifest_entry['assets']['subtitles'][lang_code] = f"/media/{file_id}/{vtt_filename}"
            
            # Parse cues from VTT
            cues = parse_vtt_for_cues(vtt_path)
            
            # Read full transcript
            full_text = read_full_transcript(txt_path)
            
            # Add transcript entry
            manifest_entry['transcripts'].append({
                'language': lang_code,
                'text': full_text,
                'cues': cues
            })
    
    return manifest_entry


def main():
    """
    Main function to orchestrate the manifest building process.
    """
    logger.info("Scribe Viewer Manifest Builder")
    logger.info("=" * 50)
    
    project_root = Path(__file__).parent.parent.parent
    
    # Initialize database connection
    logger.info("Connecting to database...")
    db = Database()
    
    # Get all files from database
    logger.info("Retrieving files from database...")
    files = db.get_all_files()
    logger.info(f"Found {len(files)} files to process")
    
    # Process each file
    manifest = []
    failures = []
    
    for i, file_record in enumerate(files, 1):
        logger.info(f"Processing file {i}/{len(files)}: {file_record['file_id']}")
        
        entry = process_interview(file_record, project_root)
        if entry:
            manifest.append(entry)
            logger.info(f"  ✓ Successfully processed: {entry['metadata']['interviewee']}")
        else:
            logger.error(f"  ✗ Failed to process {file_record['file_id']}")
            failures.append(file_record['file_id'])
    
    # Create output directory if it doesn't exist
    manifest_dir = "scribe-viewer/public"
    os.makedirs(manifest_dir, exist_ok=True)
    
    # --- Write Full Manifest ---
    manifest_path = os.path.join(manifest_dir, "manifest.json")
    logger.info(f"Writing full manifest to {manifest_path}...")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    # --- Write Minified Manifest for Gallery ---
    mini_manifest = []
    for entry in manifest:
        mini_entry = {
            "id": entry["id"],
            "metadata": entry["metadata"],
            "assets": entry["assets"]  # Include assets for thumbnails and video info
        }
        mini_manifest.append(mini_entry)
        
    mini_manifest_path = os.path.join(manifest_dir, "manifest.min.json")
    logger.info(f"Writing minified manifest to {mini_manifest_path}...")
    with open(mini_manifest_path, 'w', encoding='utf-8') as f:
        json.dump(mini_manifest, f, indent=2, ensure_ascii=False)

    
    logger.info(f"✓ Manifest generation complete!")
    logger.info(f"  - Total interviews processed: {len(manifest)}")
    
    if failures:
        logger.warning(f"  - Failed to process {len(failures)} interviews:")
        for failure_id in failures:
            logger.warning(f"    - {failure_id}")
    
    # Close database connection
    db.close()


if __name__ == "__main__":
    main()