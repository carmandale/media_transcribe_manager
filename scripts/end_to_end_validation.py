#!/usr/bin/env python3
"""
End-to-End Pipeline Validation Script

This script validates the complete Scribe pipeline for oral history interviews:
1. Transcription completeness
2. Translation completeness (EN, DE, HE)
3. Quality evaluation scores
4. Output file existence (transcripts, translations, subtitles)
5. Media file integrity

Usage:
    uv run python scripts/end_to_end_validation.py [--sample N] [--file-id ID]
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager

class PipelineValidator:
    """Validates the complete processing pipeline for interviews."""
    
    def __init__(self, db_path: str = "media_tracking.db"):
        self.db = DatabaseManager(db_path)
        self.validation_results = []
        
    def validate_file(self, file_id: str) -> Dict:
        """Validate a single file through the entire pipeline."""
        result = {
            'file_id': file_id,
            'timestamp': datetime.now().isoformat(),
            'stages': {},
            'files': {},
            'quality': {},
            'issues': [],
            'overall_status': 'pending'
        }
        
        # Get processing status from database
        status_query = """
            SELECT * FROM processing_status 
            WHERE file_id = ?
        """
        status = self.db.execute_query(status_query, (file_id,))
        
        if not status:
            result['issues'].append(f"File {file_id} not found in database")
            result['overall_status'] = 'error'
            return result
        
        status = status[0]
        
        # 1. Check transcription status
        result['stages']['transcription'] = {
            'status': status['transcription_status'],
            'passed': status['transcription_status'] == 'completed'
        }
        
        # 2. Check translation statuses
        for lang in ['en', 'de', 'he']:
            lang_status = status[f'translation_{lang}_status']
            result['stages'][f'translation_{lang}'] = {
                'status': lang_status,
                'passed': lang_status == 'completed'
            }
        
        # 3. Check quality evaluations
        quality_query = """
            SELECT language, score, model, evaluated_at, issues
            FROM quality_evaluations
            WHERE file_id = ?
        """
        quality_results = self.db.execute_query(quality_query, (file_id,))
        
        for lang in ['en', 'de', 'he']:
            lang_quality = next((q for q in quality_results if q['language'] == lang), None)
            if lang_quality:
                result['quality'][lang] = {
                    'score': lang_quality['score'],
                    'model': lang_quality['model'],
                    'evaluated_at': lang_quality['evaluated_at'],
                    'status': 'excellent' if lang_quality['score'] >= 8.5 else 
                             'acceptable' if lang_quality['score'] >= 8.0 else 'needs_improvement',
                    'issues': json.loads(lang_quality['issues']) if lang_quality['issues'] else []
                }
            else:
                result['quality'][lang] = {
                    'score': None,
                    'status': 'not_evaluated',
                    'issues': ['Quality evaluation not performed']
                }
                result['issues'].append(f"Missing quality evaluation for {lang.upper()}")
        
        # 4. Check output files
        output_dir = Path("output") / file_id
        
        # Check media file
        media_extensions = ['.mp4', '.mp3', '.wav', '.m4a']
        media_file = None
        for ext in media_extensions:
            if (output_dir / f"{file_id}{ext}").exists():
                media_file = output_dir / f"{file_id}{ext}"
                break
        
        result['files']['media'] = {
            'exists': media_file is not None,
            'path': str(media_file) if media_file else None
        }
        
        # Check transcript
        transcript_file = output_dir / f"{file_id}.txt"
        result['files']['transcript'] = {
            'exists': transcript_file.exists(),
            'path': str(transcript_file) if transcript_file.exists() else None
        }
        
        # Check translations and subtitles
        for lang in ['en', 'de', 'he']:
            # Translation text file
            trans_file = output_dir / f"{file_id}.{lang}.txt"
            result['files'][f'translation_{lang}'] = {
                'exists': trans_file.exists(),
                'path': str(trans_file) if trans_file.exists() else None
            }
            
            # Subtitle file
            srt_file = output_dir / f"{file_id}.{lang}.srt"
            result['files'][f'subtitle_{lang}'] = {
                'exists': srt_file.exists(),
                'path': str(srt_file) if srt_file.exists() else None
            }
            
            if not trans_file.exists():
                result['issues'].append(f"Missing {lang.upper()} translation file")
            if not srt_file.exists():
                result['issues'].append(f"Missing {lang.upper()} subtitle file")
        
        # Determine overall status
        all_stages_complete = all(stage['passed'] for stage in result['stages'].values())
        
        # Check if all languages have been evaluated
        all_quality_evaluated = all(
            q['status'] != 'not_evaluated' 
            for q in result['quality'].values()
        )
        
        # Check if all quality scores are good (8.0+)
        all_quality_good = all(
            q['status'] in ['excellent', 'acceptable'] 
            for q in result['quality'].values() 
            if q['status'] != 'not_evaluated'
        )
        
        # Check if all essential files exist (media, transcript, translations)
        essential_files = ['media', 'transcript', 'translation_en', 'translation_de', 'translation_he']
        all_essential_files_exist = all(
            result['files'][k]['exists'] for k in essential_files
        )
        
        # Check if all subtitle files exist
        subtitle_files = ['subtitle_en', 'subtitle_de', 'subtitle_he']
        all_subtitles_exist = all(
            result['files'][k]['exists'] for k in subtitle_files
        )
        
        if all_stages_complete and all_quality_evaluated and all_quality_good and all_essential_files_exist and all_subtitles_exist:
            result['overall_status'] = 'ready_for_delivery'
        elif all_stages_complete and all_quality_evaluated and all_quality_good and all_essential_files_exist:
            result['overall_status'] = 'ready_missing_subtitles'
        elif all_stages_complete and all_essential_files_exist and not all_quality_evaluated:
            result['overall_status'] = 'needs_quality_evaluation'
        elif all_stages_complete and all_essential_files_exist and not all_quality_good:
            result['overall_status'] = 'quality_below_threshold'
        elif all_stages_complete:
            result['overall_status'] = 'missing_files'
        else:
            result['overall_status'] = 'incomplete'
        
        return result
    
    def validate_sample(self, sample_size: int = 10) -> List[Dict]:
        """Validate a random sample of files."""
        # Get random sample
        sample_query = """
            SELECT file_id 
            FROM processing_status 
            WHERE transcription_status = 'completed'
            ORDER BY RANDOM()
            LIMIT ?
        """
        sample_files = self.db.execute_query(sample_query, (sample_size,))
        
        results = []
        for file_data in sample_files:
            result = self.validate_file(file_data['file_id'])
            results.append(result)
            self.validation_results.append(result)
        
        return results
    
    def generate_summary_report(self) -> Dict:
        """Generate a summary report of all validations."""
        if not self.validation_results:
            return {'error': 'No validations performed'}
        
        summary = {
            'total_validated': len(self.validation_results),
            'timestamp': datetime.now().isoformat(),
            'overall_statistics': {
                'ready_for_delivery': 0,
                'ready_missing_subtitles': 0,
                'needs_quality_evaluation': 0,
                'quality_below_threshold': 0,
                'missing_files': 0,
                'incomplete': 0,
                'error': 0
            },
            'quality_statistics': {
                'en': {'excellent': 0, 'acceptable': 0, 'needs_improvement': 0, 'not_evaluated': 0},
                'de': {'excellent': 0, 'acceptable': 0, 'needs_improvement': 0, 'not_evaluated': 0},
                'he': {'excellent': 0, 'acceptable': 0, 'needs_improvement': 0, 'not_evaluated': 0}
            },
            'common_issues': {},
            'files_by_status': {
                'ready_for_delivery': [],
                'ready_missing_subtitles': [],
                'needs_quality_evaluation': [],
                'quality_below_threshold': [],
                'missing_files': [],
                'incomplete': [],
                'error': []
            }
        }
        
        # Collect statistics
        for result in self.validation_results:
            status = result['overall_status']
            summary['overall_statistics'][status] += 1
            summary['files_by_status'][status].append(result['file_id'])
            
            # Quality statistics
            for lang in ['en', 'de', 'he']:
                if lang in result['quality']:
                    q_status = result['quality'][lang]['status']
                    summary['quality_statistics'][lang][q_status] += 1
            
            # Track issues
            for issue in result['issues']:
                if issue not in summary['common_issues']:
                    summary['common_issues'][issue] = 0
                summary['common_issues'][issue] += 1
        
        # Sort common issues by frequency
        summary['common_issues'] = dict(
            sorted(summary['common_issues'].items(), 
                   key=lambda x: x[1], reverse=True)
        )
        
        return summary
    
    def save_report(self, report: Dict, filename: str = None):
        """Save validation report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"validation_report_{timestamp}.json"
        
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        report_path = reports_dir / filename
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Report saved to: {report_path}")
        return report_path

def main():
    parser = argparse.ArgumentParser(
        description="Validate the complete Scribe pipeline"
    )
    parser.add_argument(
        '--sample',
        type=int,
        default=10,
        help='Number of random files to validate (default: 10)'
    )
    parser.add_argument(
        '--file-id',
        help='Specific file ID to validate'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Validate all files (warning: this may take a long time)'
    )
    parser.add_argument(
        '--save-report',
        action='store_true',
        help='Save detailed report to file'
    )
    
    args = parser.parse_args()
    
    validator = PipelineValidator()
    
    if args.file_id:
        # Validate specific file
        print(f"Validating file: {args.file_id}")
        result = validator.validate_file(args.file_id)
        validator.validation_results.append(result)
        
        # Print detailed results
        print(f"\nFile ID: {result['file_id']}")
        print(f"Overall Status: {result['overall_status']}")
        print("\nProcessing Stages:")
        for stage, info in result['stages'].items():
            status_symbol = "✓" if info['passed'] else "✗"
            print(f"  {status_symbol} {stage}: {info['status']}")
        
        print("\nQuality Scores:")
        for lang, info in result['quality'].items():
            if info['score'] is not None:
                print(f"  {lang.upper()}: {info['score']}/10 ({info['status']})")
            else:
                print(f"  {lang.upper()}: Not evaluated")
        
        print("\nOutput Files:")
        for file_type, info in result['files'].items():
            status_symbol = "✓" if info['exists'] else "✗"
            print(f"  {status_symbol} {file_type}")
        
        if result['issues']:
            print("\nIssues Found:")
            for issue in result['issues']:
                print(f"  - {issue}")
    
    elif args.all:
        # Validate all files
        print("Validating all files... This may take a while.")
        all_files_query = "SELECT file_id FROM processing_status"
        all_files = validator.db.execute_query(all_files_query)
        total = len(all_files)
        
        for i, file_data in enumerate(all_files):
            if i % 50 == 0:
                print(f"Progress: {i}/{total} files validated")
            result = validator.validate_file(file_data['file_id'])
            validator.validation_results.append(result)
    
    else:
        # Validate sample
        print(f"Validating random sample of {args.sample} files...")
        validator.validate_sample(args.sample)
    
    # Generate and display summary
    summary = validator.generate_summary_report()
    
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    print(f"Total files validated: {summary['total_validated']}")
    print("\nOverall Status:")
    for status, count in summary['overall_statistics'].items():
        percentage = (count / summary['total_validated'] * 100) if summary['total_validated'] > 0 else 0
        print(f"  {status}: {count} ({percentage:.1f}%)")
    
    print("\nQuality Statistics:")
    for lang in ['en', 'de', 'he']:
        print(f"  {lang.upper()}:")
        for status, count in summary['quality_statistics'][lang].items():
            if count > 0:
                print(f"    {status}: {count}")
    
    if summary['common_issues']:
        print("\nMost Common Issues:")
        for issue, count in list(summary['common_issues'].items())[:5]:
            print(f"  - {issue}: {count} occurrences")
    
    # Save report if requested
    if args.save_report:
        detailed_report = {
            'summary': summary,
            'detailed_results': validator.validation_results
        }
        validator.save_report(detailed_report)

if __name__ == "__main__":
    main()