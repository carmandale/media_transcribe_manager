#!/usr/bin/env python3
"""
Script to identify interviews that need reprocessing for Issue #56.
This script can work with or without database records by scanning the filesystem.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def scan_output_directory(output_dir: Path, cutoff_date: str = "2025-01-07") -> List[Dict]:
    """
    Scan the output directory for interviews that need reprocessing.
    
    Args:
        output_dir: Directory containing interview subdirectories
        cutoff_date: Only consider files modified before this date
        
    Returns:
        List of interview records that need reprocessing
    """
    logger.info(f"Scanning {output_dir} for interviews needing reprocessing")
    
    if not output_dir.exists():
        logger.warning(f"Output directory does not exist: {output_dir}")
        return []
    
    interviews_to_reprocess = []
    cutoff_timestamp = datetime.fromisoformat(cutoff_date).timestamp()
    
    # Scan each subdirectory (should be file_id directories)
    for item in output_dir.iterdir():
        if not item.is_dir():
            continue
            
        file_id = item.name
        logger.debug(f"Examining directory: {file_id}")
        
        # Look for subtitle files
        subtitle_files = {}
        
        # Check for different subtitle file patterns
        patterns = [
            f"{file_id}.orig.srt",
            f"{file_id}.srt",
            f"{file_id}.en.srt", 
            f"{file_id}.de.srt",
            f"{file_id}.he.srt"
        ]
        
        for pattern in patterns:
            file_path = item / pattern
            if file_path.exists():
                # Check modification time
                mod_time = file_path.stat().st_mtime
                
                # Determine file type
                if pattern.endswith('.orig.srt'):
                    file_type = 'orig'
                elif pattern.endswith('.srt') and not any(lang in pattern for lang in ['.en.', '.de.', '.he.']):
                    file_type = 'orig'  # Regular .srt is treated as original
                elif '.en.' in pattern:
                    file_type = 'en'
                elif '.de.' in pattern:
                    file_type = 'de'
                elif '.he.' in pattern:
                    file_type = 'he'
                else:
                    continue
                
                subtitle_files[file_type] = {
                    'path': file_path,
                    'modified_time': mod_time,
                    'modified_date': datetime.fromtimestamp(mod_time).isoformat()
                }
        
        # Determine if this interview needs reprocessing
        needs_reprocessing = False
        reason = ""
        
        if not subtitle_files:
            logger.debug(f"No subtitle files found in {file_id}")
            continue
        
        # Check if we have an original file
        if 'orig' not in subtitle_files:
            logger.debug(f"No original SRT file found in {file_id}")
            continue
        
        # Check if any translated files exist and were created before cutoff
        translated_files = {k: v for k, v in subtitle_files.items() if k in ['en', 'de', 'he']}
        
        if translated_files:
            # Check if any translated files are old (before preservation fix)
            old_translated_files = []
            for lang, file_info in translated_files.items():
                if file_info['modified_time'] < cutoff_timestamp:
                    old_translated_files.append(lang)
            
            if old_translated_files:
                needs_reprocessing = True
                reason = f"Has translated files from before {cutoff_date}: {', '.join(old_translated_files)}"
        else:
            # No translated files exist - this might be a new interview or one that failed translation
            # For Issue #56, we're specifically looking for interviews with over-translated files
            logger.debug(f"No translated files found in {file_id} - skipping")
            continue
        
        if needs_reprocessing:
            interview_record = {
                'file_id': file_id,
                'interview_dir': item,
                'subtitle_files': {k: v['path'] for k, v in subtitle_files.items()},
                'subtitle_file_info': subtitle_files,
                'reason': reason,
                'original_file': subtitle_files['orig']['path'],
                'translated_files': list(translated_files.keys()),
                'needs_reprocessing': True
            }
            
            interviews_to_reprocess.append(interview_record)
            logger.debug(f"Added {file_id} for reprocessing: {reason}")
    
    logger.info(f"Found {len(interviews_to_reprocess)} interviews needing reprocessing")
    return interviews_to_reprocess

def analyze_interview_languages(interview: Dict) -> Dict:
    """
    Analyze the languages present in an interview's subtitle files.
    
    Args:
        interview: Interview record
        
    Returns:
        Language analysis results
    """
    file_id = interview['file_id']
    original_file = interview['original_file']
    
    # This would require the SRTTranslator to analyze languages
    # For now, return basic info
    analysis = {
        'file_id': file_id,
        'has_original': True,
        'translated_languages': interview['translated_files'],
        'analysis_note': 'Detailed language analysis requires SRTTranslator'
    }
    
    return analysis

def generate_reprocessing_plan(interviews: List[Dict], output_file: Path = None) -> Path:
    """
    Generate a detailed reprocessing plan.
    
    Args:
        interviews: List of interviews needing reprocessing
        output_file: Output file path (default: auto-generated)
        
    Returns:
        Path to the generated plan file
    """
    if output_file is None:
        output_file = Path(f"reprocessing_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    # Create detailed plan
    plan = {
        'generated_at': datetime.now().isoformat(),
        'total_interviews': len(interviews),
        'cutoff_date': '2025-01-07',
        'target_languages': ['en', 'de', 'he'],
        'batch_size': 50,
        'estimated_batches': (len(interviews) + 49) // 50,  # Ceiling division
        'interviews': []
    }
    
    # Add interview details
    for interview in interviews:
        interview_plan = {
            'file_id': interview['file_id'],
            'interview_dir': str(interview['interview_dir']),
            'original_file': str(interview['original_file']),
            'existing_translated_files': interview['translated_files'],
            'reason': interview['reason'],
            'files_to_backup': [str(path) for path in interview['subtitle_files'].values()],
            'files_to_reprocess': [
                f"{interview['file_id']}.{lang}.srt" 
                for lang in ['en', 'de', 'he']
            ]
        }
        plan['interviews'].append(interview_plan)
    
    # Save plan
    with open(output_file, 'w') as f:
        json.dump(plan, f, indent=2)
    
    logger.info(f"Reprocessing plan saved to: {output_file}")
    return output_file

def generate_summary_report(interviews: List[Dict], plan_file: Path) -> Path:
    """
    Generate a human-readable summary report.
    
    Args:
        interviews: List of interviews needing reprocessing
        plan_file: Path to the JSON plan file
        
    Returns:
        Path to the generated report file
    """
    report_file = plan_file.with_suffix('.md')
    
    with open(report_file, 'w') as f:
        f.write("# Subtitle Reprocessing Plan - Issue #56\\n\\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n")
        
        f.write("## Problem Summary\\n\\n")
        f.write("This plan addresses Issue #56: Subtitle Translation Issue where 728 interviews\\n")
        f.write("have over-translated subtitles from the old system that translated ALL segments\\n")
        f.write("regardless of original language, causing inaccurate and out-of-sync subtitles.\\n\\n")
        
        f.write("## Solution\\n\\n")
        f.write("Apply language preservation logic (`preserve_original_when_matching=True`) to:\\n")
        f.write("- Preserve segments already in the target language (exact transcription + timing)\\n")
        f.write("- Only translate segments that are NOT in the target language\\n")
        f.write("- Maintain perfect timing synchronization\\n\\n")
        
        f.write("## Reprocessing Plan\\n\\n")
        f.write(f"- **Total interviews to reprocess:** {len(interviews)}\\n")
        f.write(f"- **Target languages:** English, German, Hebrew\\n")
        f.write(f"- **Batch size:** 50 interviews per batch\\n")
        f.write(f"- **Estimated batches:** {(len(interviews) + 49) // 50}\\n")
        f.write(f"- **Cutoff date:** 2025-01-07 (before preservation fix)\\n\\n")
        
        # Language distribution
        language_stats = {}
        for interview in interviews:
            for lang in interview['translated_files']:
                language_stats[lang] = language_stats.get(lang, 0) + 1
        
        f.write("## Language Distribution\\n\\n")
        for lang, count in sorted(language_stats.items()):
            f.write(f"- **{lang.upper()}:** {count} interviews\\n")
        f.write("\\n")
        
        f.write("## Sample Interviews\\n\\n")
        f.write("First 10 interviews to be reprocessed:\\n\\n")
        for i, interview in enumerate(interviews[:10]):
            f.write(f"{i+1}. **{interview['file_id']}**\\n")
            f.write(f"   - Languages: {', '.join(interview['translated_files'])}\\n")
            f.write(f"   - Reason: {interview['reason']}\\n")
        
        if len(interviews) > 10:
            f.write(f"\\n... and {len(interviews) - 10} more interviews\\n")
        
        f.write("\\n## Next Steps\\n\\n")
        f.write("1. **Review this plan** - Verify the identified interviews are correct\\n")
        f.write("2. **Run validation** - Test preservation logic on sample interviews\\n")
        f.write("3. **Execute reprocessing** - Run batch processing script\\n")
        f.write("4. **Validate results** - Ensure subtitles are fixed and synchronized\\n")
        f.write("5. **Update web viewer** - Regenerate VTT files and manifests\\n\\n")
        
        f.write(f"## Files Generated\\n\\n")
        f.write(f"- **JSON Plan:** `{plan_file.name}`\\n")
        f.write(f"- **Summary Report:** `{report_file.name}`\\n\\n")
    
    logger.info(f"Summary report saved to: {report_file}")
    return report_file

def main():
    """Main identification function."""
    logger.info("Identifying interviews for subtitle reprocessing (Issue #56)")
    
    # Configuration
    output_dir = Path("output")
    cutoff_date = "2025-01-07"  # Before preservation fix was deployed
    
    # Scan for interviews needing reprocessing
    interviews = scan_output_directory(output_dir, cutoff_date)
    
    if not interviews:
        logger.info("No interviews found needing reprocessing")
        logger.info("This could mean:")
        logger.info("  - No output directory exists")
        logger.info("  - No interviews have old translated subtitle files")
        logger.info("  - All interviews were already reprocessed")
        return True
    
    logger.info(f"\\n{'='*60}")
    logger.info(f"FOUND {len(interviews)} INTERVIEWS NEEDING REPROCESSING")
    logger.info(f"{'='*60}")
    
    # Show summary by language
    language_stats = {}
    for interview in interviews:
        for lang in interview['translated_files']:
            language_stats[lang] = language_stats.get(lang, 0) + 1
    
    logger.info("Language distribution:")
    for lang, count in sorted(language_stats.items()):
        logger.info(f"  - {lang.upper()}: {count} interviews")
    
    # Generate reprocessing plan
    plan_file = generate_reprocessing_plan(interviews)
    report_file = generate_summary_report(interviews, plan_file)
    
    logger.info(f"\\nGenerated files:")
    logger.info(f"  - Plan: {plan_file}")
    logger.info(f"  - Report: {report_file}")
    
    logger.info(f"\\nNext steps:")
    logger.info(f"  1. Review the generated plan and report")
    logger.info(f"  2. Run validation on sample interviews")
    logger.info(f"  3. Execute batch reprocessing script")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

