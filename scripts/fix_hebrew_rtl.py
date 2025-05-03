#!/usr/bin/env python3
"""
Fix Hebrew translation RTL formatting issues and apply proper noun protection.

This script applies necessary post-processing to Hebrew translations to fix:
1. RTL punctuation formatting
2. Proper noun handling (via glossary)
3. Paragraph and sentence structure

Usage:
python scripts/fix_hebrew_rtl.py [--all] [--file-id FILE_ID]

Options:
  --all         Process all Hebrew translations that need fixing
  --file-id     Process a specific file by ID
  --batch-size  Number of files to process in a batch (default: 20)
  --dry-run     Show what would be processed without making changes
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("hebrew-fixer")

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_manager import DatabaseManager

# Hebrew RTL specific characters and patterns
HEBREW_CHARS = re.compile(r'[\u0590-\u05FF\uFB1D-\uFB4F]')
RTL_MARK = '\u200F'  # Right-to-Left Mark
LTR_MARK = '\u200E'  # Left-to-Right Mark

# Load the Hebrew glossary if it exists
GLOSSARY_PATH = Path("./docs/glossaries/he_seed.csv")
GLOSSARY: Dict[str, str] = {}

def load_glossary():
    """Load the Hebrew glossary from CSV file."""
    global GLOSSARY
    if not GLOSSARY_PATH.exists():
        logger.warning(f"Glossary file not found: {GLOSSARY_PATH}")
        return
    
    try:
        with open(GLOSSARY_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                if ',' in line:
                    source, target = line.strip().split(',', 1)
                    GLOSSARY[source.strip()] = target.strip()
        logger.info(f"Loaded {len(GLOSSARY)} entries from glossary")
    except Exception as e:
        logger.error(f"Error loading glossary: {e}")

def fix_rtl_punctuation(text: str) -> str:
    """Fix RTL punctuation issues in Hebrew text."""
    # Add RTL mark before Hebrew text starts
    text = re.sub(r'(^|\n)(\s*)(' + HEBREW_CHARS.pattern + ')', r'\1\2' + RTL_MARK + r'\3', text, flags=re.MULTILINE)
    
    # Fix punctuation at the end of Hebrew sentences
    text = re.sub(r'(' + HEBREW_CHARS.pattern + r')(\s*)(\.|\?|!|:|;|,)(\s|$)', r'\1\3\2\4', text)
    
    # Fix parentheses and quotes
    text = re.sub(r'\((' + HEBREW_CHARS.pattern + r'[^)]*)\)', r')\1(', text)
    text = re.sub(r'"(' + HEBREW_CHARS.pattern + r'[^"]*)"', r'"\1"', text)
    
    return text

def apply_glossary(text: str) -> str:
    """Apply glossary terms to ensure proper nouns are correctly translated."""
    if not GLOSSARY:
        return text
    
    # Sort keys by length (longest first) to avoid partial replacements
    for source, target in sorted(GLOSSARY.items(), key=lambda x: len(x[0]), reverse=True):
        # Only replace if source is a proper noun (starts with capital letter)
        if source and source[0].isupper():
            # Use word boundary to avoid replacing parts of words
            text = re.sub(r'\b' + re.escape(source) + r'\b', target, text)
    
    return text

def fix_paragraph_structure(text: str) -> str:
    """Fix paragraph structure in Hebrew text."""
    # Ensure paragraphs maintain RTL direction
    paragraphs = text.split('\n\n')
    fixed_paragraphs = []
    
    for para in paragraphs:
        if HEBREW_CHARS.search(para):
            # Add RTL mark at the beginning of each paragraph
            if not para.startswith(RTL_MARK):
                para = RTL_MARK + para
        fixed_paragraphs.append(para)
    
    return '\n\n'.join(fixed_paragraphs)

def process_file(file_id: str, db: DatabaseManager, dry_run: bool = False) -> bool:
    """Process a single Hebrew translation file."""
    # Find the Hebrew translation file
    base_dir = Path("./output/translations/he")
    pattern = f"{file_id}*_he.txt"
    matches = list(base_dir.glob(pattern))
    
    if not matches:
        logger.error(f"No Hebrew translation file found for {file_id}")
        return False
    
    file_path = matches[0]
    subtitle_path = Path(str(file_path).replace('/translations/', '/subtitles/').replace('_he.txt', '_he.srt'))
    
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
        
        # Apply fixes
        fixed_text = original_text
        fixed_text = fix_rtl_punctuation(fixed_text)
        fixed_text = apply_glossary(fixed_text)
        fixed_text = fix_paragraph_structure(fixed_text)
        
        if fixed_text == original_text:
            logger.info(f"No changes needed for {file_id}")
            return True
        
        if dry_run:
            logger.info(f"Would fix {file_id} (dry run)")
            return True
        
        # Write the fixed text back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_text)
        
        # Fix subtitles if they exist
        if subtitle_path.exists():
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_text = f.read()
            
            # Extract and fix just the text portions of subtitles
            def fix_subtitle_line(match):
                line = match.group(0)
                if HEBREW_CHARS.search(line):
                    line = fix_rtl_punctuation(line)
                    line = apply_glossary(line)
                return line
            
            # Regex to match subtitle text lines (not timestamps or numbers)
            subtitle_lines_pattern = r'^(?!\d+$)(?!^\d+:\d+:\d+,\d+ --> \d+:\d+:\d+,\d+$)(.+)$'
            fixed_subtitle_text = re.sub(subtitle_lines_pattern, fix_subtitle_line, subtitle_text, flags=re.MULTILINE)
            
            with open(subtitle_path, 'w', encoding='utf-8') as f:
                f.write(fixed_subtitle_text)
        
        # Update the database
        db.execute_query(
            "UPDATE processing_status SET translation_he_status = 'completed' WHERE file_id = ?",
            (file_id,)
        )
        
        logger.info(f"Successfully fixed {file_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing {file_id}: {e}")
        return False

def get_files_needing_fix(db: DatabaseManager, limit: Optional[int] = None) -> List[str]:
    """Get list of file IDs that need Hebrew RTL fixes."""
    query = """
    SELECT file_id 
    FROM processing_status 
    WHERE translation_he_status = 'completed' 
    AND file_id IN (
        SELECT file_id 
        FROM quality_evaluations 
        WHERE language = 'he' 
        AND score < 8.0
    )
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    rows = db.execute_query(query)
    return [row[0] for row in rows]

def main():
    parser = argparse.ArgumentParser(description="Fix Hebrew RTL formatting issues")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Process all Hebrew translations that need fixing")
    group.add_argument("--file-id", help="Process a specific file by ID")
    parser.add_argument("--batch-size", type=int, default=20, help="Number of files to process in a batch")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without making changes")
    args = parser.parse_args()
    
    # Load the glossary
    load_glossary()
    
    # Connect to the database
    db = DatabaseManager()
    
    if args.file_id:
        success = process_file(args.file_id, db, args.dry_run)
        sys.exit(0 if success else 1)
    
    if args.all:
        file_ids = get_files_needing_fix(db, limit=args.batch_size)
        if not file_ids:
            logger.info("No files found that need fixing")
            sys.exit(0)
        
        logger.info(f"Processing {len(file_ids)} files")
        success_count = 0
        fail_count = 0
        
        for file_id in file_ids:
            if process_file(file_id, db, args.dry_run):
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(f"Processed {len(file_ids)} files: {success_count} succeeded, {fail_count} failed")
        sys.exit(0 if fail_count == 0 else 1)

if __name__ == "__main__":
    main()