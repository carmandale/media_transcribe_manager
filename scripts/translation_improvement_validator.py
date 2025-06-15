#!/usr/bin/env python3
"""
Translation Improvement Validator

This script validates that translation quality improvements are working by:
1. Selecting sample files with low quality scores
2. Re-translating them with the new speech-preserving system
3. Re-evaluating quality scores
4. Providing independent verification methods

Usage:
    uv run python scripts/translation_improvement_validator.py --language he --sample-size 10
"""

import sys
import argparse
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import shutil

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager
from core_modules.translation import TranslationManager
from core_modules.file_manager import FileManager

class TranslationValidator:
    """Validates translation improvements with before/after comparison."""
    
    def __init__(self, db_path: str = "media_tracking.db"):
        self.db = DatabaseManager(db_path)
        self.results = []
        self.backup_dir = Path("validation_backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def get_low_scoring_files(self, language: str, limit: int = 10) -> List[Dict]:
        """Get files with low quality scores for a language."""
        query = """
            SELECT 
                qe.file_id,
                mf.original_path as original_filename,
                qe.score,
                qe.issues,
                qe.evaluated_at
            FROM quality_evaluations qe
            JOIN media_files mf ON qe.file_id = mf.file_id
            WHERE qe.language = ?
            AND qe.score < 8.0
            AND qe.score > 1.0  -- Exclude placeholder scores
            ORDER BY qe.score ASC
            LIMIT ?
        """
        return self.db.execute_query(query, (language, limit))
    
    def backup_translation(self, file_id: str, language: str) -> Optional[Path]:
        """Backup current translation before re-translating."""
        translation_path = Path("output") / file_id / f"{file_id}.{language}.txt"
        if translation_path.exists():
            backup_path = self.backup_dir / f"{file_id}.{language}.original.txt"
            shutil.copy2(translation_path, backup_path)
            return backup_path
        return None
    
    def extract_speech_patterns(self, text: str) -> Dict[str, int]:
        """Extract speech patterns from text for comparison."""
        patterns = {
            'hesitations': 0,
            'repetitions': 0,
            'ellipses': 0,
            'dashes': 0,
            'questions': 0,
            'total_words': 0
        }
        
        # Count patterns
        hesitation_words = ['um', 'uh', 'ah', 'hmm', 'äh', 'ähm', 'אה', 'אהה', 'אמ']
        
        words = text.split()
        patterns['total_words'] = len(words)
        
        # Count hesitations
        for word in words:
            if word.lower().strip('.,?!') in hesitation_words:
                patterns['hesitations'] += 1
        
        # Count repetitions (consecutive duplicate words)
        for i in range(len(words) - 1):
            if words[i].lower() == words[i + 1].lower():
                patterns['repetitions'] += 1
        
        # Count ellipses and dashes
        patterns['ellipses'] = text.count('...') + text.count('…')
        patterns['dashes'] = text.count(' - ') + text.count(' -- ')
        patterns['questions'] = text.count('?')
        
        return patterns
    
    def compare_translations(self, old_path: Path, new_path: Path) -> Dict:
        """Compare old and new translations for speech pattern preservation."""
        old_text = old_path.read_text(encoding='utf-8')
        new_text = new_path.read_text(encoding='utf-8') if new_path.exists() else ""
        
        old_patterns = self.extract_speech_patterns(old_text)
        new_patterns = self.extract_speech_patterns(new_text)
        
        comparison = {
            'old_patterns': old_patterns,
            'new_patterns': new_patterns,
            'improvements': {}
        }
        
        # Calculate improvements
        for key in old_patterns:
            if key != 'total_words':
                old_rate = old_patterns[key] / max(old_patterns['total_words'], 1) * 100
                new_rate = new_patterns[key] / max(new_patterns['total_words'], 1) * 100
                comparison['improvements'][key] = {
                    'old_rate': old_rate,
                    'new_rate': new_rate,
                    'change': new_rate - old_rate
                }
        
        return comparison
    
    def create_independent_verification(self, file_id: str, language: str) -> Dict:
        """Create independent verification data for manual review."""
        verification = {
            'file_id': file_id,
            'language': language,
            'checks': []
        }
        
        # Get transcript excerpt
        transcript_path = Path("output") / file_id / f"{file_id}.txt"
        translation_path = Path("output") / file_id / f"{file_id}.{language}.txt"
        
        if transcript_path.exists() and translation_path.exists():
            # Get first 500 characters of each
            transcript_excerpt = transcript_path.read_text(encoding='utf-8')[:500]
            translation_excerpt = translation_path.read_text(encoding='utf-8')[:500]
            
            verification['transcript_excerpt'] = transcript_excerpt
            verification['translation_excerpt'] = translation_excerpt
            
            # Create specific checks
            verification['checks'] = [
                {
                    'question': 'Does the translation preserve hesitation words (um, uh, ah)?',
                    'what_to_look_for': 'Check if "um", "uh" in source appear as "äh", "ähm" (German) or "אה", "אמ" (Hebrew)'
                },
                {
                    'question': 'Are repeated words maintained?',
                    'what_to_look_for': 'If source has "I... I think", translation should have similar repetition'
                },
                {
                    'question': 'Are incomplete sentences preserved?',
                    'what_to_look_for': 'Sentences ending with "..." or trailing off should remain incomplete'
                },
                {
                    'question': 'Is the speech natural or overly polished?',
                    'what_to_look_for': 'Translation should sound like spoken language, not written text'
                }
            ]
        
        return verification
    
    def run_validation(self, language: str, sample_size: int = 10, 
                      skip_retranslation: bool = False) -> Dict:
        """Run the complete validation process."""
        print(f"Starting validation for {language.upper()} translations...")
        
        # Get low-scoring files
        files = self.get_low_scoring_files(language, sample_size)
        if not files:
            print(f"No low-scoring files found for {language}")
            return {}
        
        print(f"Found {len(files)} files with scores below 8.0")
        
        results = {
            'language': language,
            'timestamp': datetime.now().isoformat(),
            'files_processed': [],
            'summary': {
                'total_files': len(files),
                'improved': 0,
                'degraded': 0,
                'unchanged': 0,
                'avg_score_before': 0,
                'avg_score_after': 0
            }
        }
        
        for i, file_data in enumerate(files):
            file_id = file_data['file_id']
            original_score = file_data['score']
            
            print(f"\n[{i+1}/{len(files)}] Processing {file_id}")
            print(f"  Original score: {original_score:.2f}")
            
            file_result = {
                'file_id': file_id,
                'original_filename': file_data['original_filename'],
                'original_score': original_score,
                'original_issues': json.loads(file_data['issues']) if file_data['issues'] else [],
                'new_score': None,
                'new_issues': [],
                'pattern_comparison': {},
                'verification': {}
            }
            
            # Backup current translation
            backup_path = self.backup_translation(file_id, language)
            if backup_path:
                print(f"  Backed up to: {backup_path.name}")
                file_result['backup_path'] = str(backup_path)
            
            if not skip_retranslation:
                # Get the original file path for this file_id
                file_info = self.db.get_file_status(file_id)
                if not file_info or 'original_path' not in file_info:
                    print(f"  ✗ Could not find original path for file_id: {file_id}")
                    continue
                    
                original_path = file_info['original_path']
                
                # Re-translate with new system
                print(f"  Re-translating with speech preservation...")
                cmd = [
                    "uv", "run", "python", "scripts/media_processor.py",
                    "-f", original_path,
                    "--translate-only", language,
                    "--formality", "less",
                    "--force"
                ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=project_root,
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        print("  ✓ Re-translation completed")
                        time.sleep(2)  # Brief pause
                    else:
                        print(f"  ✗ Re-translation failed: {result.stderr}")
                        continue
                except Exception as e:
                    print(f"  ✗ Error: {str(e)}")
                    continue
            
            # Compare translations if backup exists
            if backup_path:
                new_path = Path("output") / file_id / f"{file_id}.{language}.txt"
                if new_path.exists():
                    comparison = self.compare_translations(backup_path, new_path)
                    file_result['pattern_comparison'] = comparison
                    
                    # Show improvement summary
                    print("  Pattern changes:")
                    for pattern, data in comparison['improvements'].items():
                        change = data['change']
                        symbol = "↑" if change > 0 else "↓" if change < 0 else "="
                        print(f"    {pattern}: {data['old_rate']:.1f}% → {data['new_rate']:.1f}% {symbol}")
            
            # Re-evaluate quality
            print(f"  Re-evaluating quality...")
            eval_cmd = [
                "uv", "run", "python", "scripts/historical_evaluate_quality.py",
                "--file-id", file_id,
                "--language", language
            ]
            
            try:
                result = subprocess.run(
                    eval_cmd,
                    cwd=project_root,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    # Get new score from database
                    new_score_query = """
                        SELECT score, issues 
                        FROM quality_evaluations 
                        WHERE file_id = ? AND language = ?
                        ORDER BY evaluated_at DESC
                        LIMIT 1
                    """
                    new_result = self.db.execute_query(new_score_query, (file_id, language))
                    if new_result:
                        new_score = new_result[0]['score']
                        file_result['new_score'] = new_score
                        file_result['new_issues'] = json.loads(new_result[0]['issues']) if new_result[0]['issues'] else []
                        
                        score_change = new_score - original_score
                        print(f"  New score: {new_score:.2f} ({score_change:+.2f})")
                        
                        if score_change > 0.1:
                            results['summary']['improved'] += 1
                        elif score_change < -0.1:
                            results['summary']['degraded'] += 1
                        else:
                            results['summary']['unchanged'] += 1
            except Exception as e:
                print(f"  ✗ Evaluation error: {str(e)}")
            
            # Create independent verification
            file_result['verification'] = self.create_independent_verification(file_id, language)
            
            results['files_processed'].append(file_result)
            results['summary']['avg_score_before'] += original_score
            if file_result.get('new_score') is not None:
                results['summary']['avg_score_after'] += file_result['new_score']
            else:
                results['summary']['avg_score_after'] += original_score
        
        # Calculate averages
        if results['files_processed']:
            n = len(results['files_processed'])
            results['summary']['avg_score_before'] /= n
            results['summary']['avg_score_after'] /= n
        
        # Save results
        report_path = Path("reports") / f"translation_validation_{language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\nValidation report saved to: {report_path}")
        
        return results
    
    def generate_verification_html(self, results: Dict) -> Path:
        """Generate HTML report for independent verification."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Translation Verification - {results['language'].upper()}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .file {{ border: 1px solid #ccc; margin: 20px 0; padding: 15px; }}
        .comparison {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .text-box {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
        .score {{ font-size: 24px; font-weight: bold; }}
        .improved {{ color: green; }}
        .degraded {{ color: red; }}
        .unchanged {{ color: orange; }}
        .checklist {{ margin: 20px 0; }}
        .check-item {{ margin: 10px 0; padding: 10px; background: #e8f4f8; }}
        pre {{ white-space: pre-wrap; word-wrap: break-word; }}
    </style>
</head>
<body>
    <h1>Translation Quality Validation Report - {results['language'].upper()}</h1>
    <p>Generated: {results['timestamp']}</p>
    
    <h2>Summary</h2>
    <ul>
        <li>Files processed: {results['summary']['total_files']}</li>
        <li>Average score before: {results['summary']['avg_score_before']:.2f}</li>
        <li>Average score after: {results['summary']['avg_score_after']:.2f}</li>
        <li>Improved: {results['summary']['improved']}</li>
        <li>Degraded: {results['summary']['degraded']}</li>
        <li>Unchanged: {results['summary']['unchanged']}</li>
    </ul>
"""
        
        for file_data in results['files_processed']:
            score_change = (file_data.get('new_score', 0) - file_data['original_score']) if file_data.get('new_score') else 0
            score_class = 'improved' if score_change > 0.1 else 'degraded' if score_change < -0.1 else 'unchanged'
            
            html += f"""
    <div class="file">
        <h3>{file_data['original_filename']}</h3>
        <p>File ID: {file_data['file_id']}</p>
        <p>Score: <span class="score">{file_data['original_score']:.2f}</span> → 
           <span class="score {score_class}">{file_data.get('new_score', 'N/A')}</span></p>
        
        <h4>Text Comparison</h4>
        <div class="comparison">
            <div>
                <h5>Original Transcript (excerpt)</h5>
                <div class="text-box">
                    <pre>{file_data['verification'].get('transcript_excerpt', 'N/A')}</pre>
                </div>
            </div>
            <div>
                <h5>Translation (excerpt)</h5>
                <div class="text-box">
                    <pre>{file_data['verification'].get('translation_excerpt', 'N/A')}</pre>
                </div>
            </div>
        </div>
        
        <h4>Verification Checklist</h4>
        <div class="checklist">
"""
            
            for check in file_data['verification'].get('checks', []):
                html += f"""
            <div class="check-item">
                <strong>{check['question']}</strong><br>
                <em>Look for: {check['what_to_look_for']}</em><br>
                <label><input type="checkbox"> Yes</label>
                <label><input type="checkbox"> No</label>
                <label><input type="checkbox"> Unsure</label>
            </div>
"""
            
            html += """
        </div>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        html_path = Path("reports") / f"verification_{results['language']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        html_path.write_text(html, encoding='utf-8')
        
        return html_path

def main():
    parser = argparse.ArgumentParser(
        description="Validate translation quality improvements"
    )
    parser.add_argument(
        '--language',
        required=True,
        choices=['en', 'de', 'he'],
        help='Language to validate'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=10,
        help='Number of files to test (default: 10)'
    )
    parser.add_argument(
        '--skip-retranslation',
        action='store_true',
        help='Skip re-translation step (just re-evaluate existing)'
    )
    
    args = parser.parse_args()
    
    validator = TranslationValidator()
    
    # Run validation
    results = validator.run_validation(
        args.language,
        args.sample_size,
        args.skip_retranslation
    )
    
    if results:
        # Generate HTML verification report
        html_path = validator.generate_verification_html(results)
        print(f"\nIndependent verification report: {html_path}")
        print("\nOpen this HTML file to manually verify translation quality.")
        print("Share with native speakers for independent assessment.")
        
        # Print summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Language: {results['language'].upper()}")
        print(f"Files tested: {results['summary']['total_files']}")
        print(f"Average score change: {results['summary']['avg_score_after'] - results['summary']['avg_score_before']:+.2f}")
        print(f"Files improved: {results['summary']['improved']}")
        print(f"Files degraded: {results['summary']['degraded']}")
        print(f"Files unchanged: {results['summary']['unchanged']}")

if __name__ == "__main__":
    main()