#!/usr/bin/env python3
"""
Run Quality Evaluations for Unevaluated Files

This script identifies all files that haven't been quality evaluated
and runs the evaluation process for them.

Usage:
    uv run python scripts/run_missing_evaluations.py [--language LANG] [--limit N] [--dry-run]
"""

import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Set

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager

class MissingEvaluationRunner:
    """Runs quality evaluations for files that haven't been evaluated."""
    
    def __init__(self, db_path: str = "media_tracking.db"):
        self.db = DatabaseManager(db_path)
        
    def find_unevaluated_files(self, language: str = None) -> Dict[str, Set[str]]:
        """Find files that need quality evaluation."""
        
        # Get all completed files
        query = """
            SELECT 
                ps.file_id,
                ps.translation_en_status,
                ps.translation_de_status,
                ps.translation_he_status,
                qe_en.score as en_score,
                qe_de.score as de_score,
                qe_he.score as he_score
            FROM processing_status ps
            LEFT JOIN quality_evaluations qe_en ON ps.file_id = qe_en.file_id AND qe_en.language = 'en'
            LEFT JOIN quality_evaluations qe_de ON ps.file_id = qe_de.file_id AND qe_de.language = 'de'
            LEFT JOIN quality_evaluations qe_he ON ps.file_id = qe_he.file_id AND qe_he.language = 'he'
            WHERE ps.transcription_status = 'completed'
        """
        
        results = self.db.execute_query(query)
        
        unevaluated = {
            'en': set(),
            'de': set(),
            'he': set()
        }
        
        for row in results:
            file_id = row['file_id']
            
            # Check each language
            if language is None or language == 'en':
                if row['translation_en_status'] == 'completed' and row['en_score'] is None:
                    unevaluated['en'].add(file_id)
                    
            if language is None or language == 'de':
                if row['translation_de_status'] == 'completed' and row['de_score'] is None:
                    unevaluated['de'].add(file_id)
                    
            if language is None or language == 'he':
                if row['translation_he_status'] == 'completed' and row['he_score'] is None:
                    unevaluated['he'].add(file_id)
        
        return unevaluated
    
    def run_evaluation(self, file_id: str, language: str, dry_run: bool = False) -> bool:
        """Run quality evaluation for a specific file and language."""
        
        script_name = f"evaluate_{language}_quality.py"
        script_path = self.project_root / "scripts" / script_name
        
        if not script_path.exists():
            # Try historical evaluation script
            script_path = self.project_root / "scripts" / "historical_evaluate_quality.py"
            cmd = [
                "uv", "run", "python", str(script_path),
                "--file-id", file_id,
                "--language", language
            ]
        else:
            cmd = [
                "uv", "run", "python", str(script_path),
                "--file-id", file_id
            ]
        
        if dry_run:
            print(f"Would run: {' '.join(cmd)}")
            return True
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✓ Evaluated {file_id} ({language})")
                return True
            else:
                print(f"✗ Failed to evaluate {file_id} ({language}): {result.stderr}")
                return False
                
        except Exception as e:
            print(f"✗ Error evaluating {file_id} ({language}): {str(e)}")
            return False
    
    @property
    def project_root(self):
        return Path(__file__).parent.parent

def main():
    parser = argparse.ArgumentParser(
        description="Run quality evaluations for unevaluated files"
    )
    parser.add_argument(
        '--language',
        choices=['en', 'de', 'he'],
        help='Evaluate only specific language (default: all)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of files to evaluate'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue processing even if some evaluations fail'
    )
    
    args = parser.parse_args()
    
    runner = MissingEvaluationRunner()
    
    # Find unevaluated files
    print("Finding unevaluated files...")
    unevaluated = runner.find_unevaluated_files(args.language)
    
    # Report counts
    total_missing = sum(len(files) for files in unevaluated.values())
    print(f"\nFound {total_missing} missing evaluations:")
    for lang, files in unevaluated.items():
        if files:
            print(f"  {lang.upper()}: {len(files)} files")
    
    if total_missing == 0:
        print("\nAll files have been evaluated!")
        return
    
    # Process files
    print(f"\n{'DRY RUN: ' if args.dry_run else ''}Starting evaluations...")
    
    processed = 0
    failed = 0
    
    for lang, file_ids in unevaluated.items():
        if not file_ids:
            continue
            
        print(f"\nProcessing {lang.upper()} evaluations...")
        
        for i, file_id in enumerate(sorted(file_ids)):
            if args.limit and processed >= args.limit:
                print(f"\nReached limit of {args.limit} evaluations")
                break
                
            # Show progress
            if i > 0 and i % 10 == 0:
                print(f"Progress: {i}/{len(file_ids)} files...")
            
            # Run evaluation
            success = runner.run_evaluation(file_id, lang, args.dry_run)
            
            if success:
                processed += 1
            else:
                failed += 1
                if not args.continue_on_error and not args.dry_run:
                    print("\nStopping due to error. Use --continue-on-error to continue.")
                    break
        
        if args.limit and processed >= args.limit:
            break
    
    # Summary
    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    print(f"Total files processed: {processed}")
    if failed > 0:
        print(f"Failed evaluations: {failed}")
    
    if args.dry_run:
        print("\nThis was a dry run. No evaluations were actually performed.")
    else:
        remaining = total_missing - processed
        if remaining > 0:
            print(f"\nRemaining evaluations: {remaining}")
            print("Run again to continue processing.")

if __name__ == "__main__":
    main()