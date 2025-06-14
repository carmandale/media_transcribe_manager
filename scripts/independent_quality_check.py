#!/usr/bin/env python3
"""
Independent Quality Check for Translations

This script provides independent verification methods that don't rely on
our primary evaluation system, including:
1. Statistical analysis of speech patterns
2. Comparison metrics between source and target
3. Native speaker evaluation templates
4. Cross-validation with different models

Usage:
    uv run python scripts/independent_quality_check.py --file-id FILE_ID --language LANG
"""

import sys
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter
import statistics

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager

class IndependentQualityChecker:
    """Provides independent verification of translation quality."""
    
    def __init__(self):
        self.db = DatabaseManager("media_tracking.db")
        
    def analyze_speech_characteristics(self, text: str, language: str) -> Dict:
        """Analyze speech characteristics in a language-agnostic way."""
        analysis = {
            'sentence_lengths': [],
            'punctuation_density': 0,
            'fragment_ratio': 0,
            'repetition_score': 0,
            'pause_indicators': 0,
            'question_ratio': 0,
            'exclamation_ratio': 0
        }
        
        # Split into sentences (roughly)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return analysis
        
        # Analyze sentence lengths
        for sentence in sentences:
            words = sentence.split()
            if words:
                analysis['sentence_lengths'].append(len(words))
        
        # Calculate metrics
        total_words = sum(analysis['sentence_lengths'])
        
        # Punctuation density (commas, dashes, ellipses per 100 words)
        punctuation_count = text.count(',') + text.count('-') + text.count('...') + text.count('…')
        analysis['punctuation_density'] = (punctuation_count / max(total_words, 1)) * 100
        
        # Fragment ratio (sentences with < 5 words)
        fragments = sum(1 for length in analysis['sentence_lengths'] if length < 5)
        analysis['fragment_ratio'] = fragments / max(len(sentences), 1)
        
        # Repetition score (repeated words)
        words = text.lower().split()
        if len(words) > 1:
            repetitions = sum(1 for i in range(len(words)-1) if words[i] == words[i+1])
            analysis['repetition_score'] = repetitions / len(words)
        
        # Pause indicators
        analysis['pause_indicators'] = (
            text.count('...') + text.count('…') + 
            text.count(' - ') + text.count(' -- ') +
            text.count(', ,') + text.count(',,')
        )
        
        # Question and exclamation ratios
        analysis['question_ratio'] = text.count('?') / max(len(sentences), 1)
        analysis['exclamation_ratio'] = text.count('!') / max(len(sentences), 1)
        
        return analysis
    
    def compare_structural_similarity(self, source: str, target: str) -> Dict:
        """Compare structural similarity between source and target."""
        comparison = {
            'length_ratio': 0,
            'paragraph_preservation': 0,
            'line_count_similarity': 0,
            'punctuation_similarity': 0,
            'capitalization_similarity': 0
        }
        
        # Length ratio
        source_words = len(source.split())
        target_words = len(target.split())
        comparison['length_ratio'] = min(source_words, target_words) / max(source_words, target_words, 1)
        
        # Paragraph preservation
        source_paragraphs = source.split('\n\n')
        target_paragraphs = target.split('\n\n')
        comparison['paragraph_preservation'] = (
            min(len(source_paragraphs), len(target_paragraphs)) / 
            max(len(source_paragraphs), len(target_paragraphs), 1)
        )
        
        # Line count similarity
        source_lines = source.split('\n')
        target_lines = target.split('\n')
        comparison['line_count_similarity'] = (
            min(len(source_lines), len(target_lines)) / 
            max(len(source_lines), len(target_lines), 1)
        )
        
        # Punctuation similarity (normalized counts)
        source_punct = sum(1 for c in source if c in '.,!?;:-')
        target_punct = sum(1 for c in target if c in '.,!?;:-')
        source_punct_rate = source_punct / max(source_words, 1)
        target_punct_rate = target_punct / max(target_words, 1)
        comparison['punctuation_similarity'] = (
            min(source_punct_rate, target_punct_rate) / 
            max(source_punct_rate, target_punct_rate, 0.001)
        )
        
        # Capitalization patterns (start of sentences)
        source_caps = sum(1 for word in source.split() if word and word[0].isupper())
        target_caps = sum(1 for word in target.split() if word and word[0].isupper())
        source_cap_rate = source_caps / max(source_words, 1)
        target_cap_rate = target_caps / max(target_words, 1)
        comparison['capitalization_similarity'] = (
            min(source_cap_rate, target_cap_rate) / 
            max(source_cap_rate, target_cap_rate, 0.001)
        )
        
        return comparison
    
    def generate_native_speaker_checklist(self, file_id: str, language: str) -> Dict:
        """Generate a checklist for native speaker evaluation."""
        # Get sample text
        transcript_path = Path("output") / file_id / f"{file_id}.txt"
        translation_path = Path("output") / file_id / f"{file_id}.{language}.txt"
        
        if not (transcript_path.exists() and translation_path.exists()):
            return {"error": "Files not found"}
        
        transcript = transcript_path.read_text(encoding='utf-8')
        translation = translation_path.read_text(encoding='utf-8')
        
        # Get excerpts
        excerpts = []
        lines = transcript.split('\n')
        trans_lines = translation.split('\n')
        
        # Find interesting excerpts (with hesitations, questions, etc.)
        for i, line in enumerate(lines[:50]):  # Check first 50 lines
            if any(marker in line.lower() for marker in ['um', 'uh', '...', 'you know', 'I mean']):
                if i < len(trans_lines):
                    excerpts.append({
                        'source': line,
                        'translation': trans_lines[i],
                        'line_number': i + 1,
                        'check_for': 'Hesitations and filler words preserved'
                    })
                if len(excerpts) >= 5:
                    break
        
        checklist = {
            'file_id': file_id,
            'language': language,
            'instructions': f"""
Please evaluate this {language.upper()} translation for historical accuracy:

1. Does the translation sound like natural SPOKEN language (not written)?
2. Are hesitations, pauses, and filler words preserved?
3. Does the speaker's personality/voice come through?
4. Are incomplete thoughts and self-corrections maintained?
5. Would you trust this as an accurate historical record?

Rate each aspect 1-10 and provide comments.
""",
            'excerpts': excerpts,
            'evaluation_form': {
                'naturalness': {'score': None, 'comment': ''},
                'hesitation_preservation': {'score': None, 'comment': ''},
                'voice_authenticity': {'score': None, 'comment': ''},
                'completeness': {'score': None, 'comment': ''},
                'historical_reliability': {'score': None, 'comment': ''},
                'overall_quality': {'score': None, 'comment': ''}
            }
        }
        
        return checklist
    
    def cross_validate_with_basic_metrics(self, file_id: str, language: str) -> Dict:
        """Use basic metrics that don't depend on GPT evaluation."""
        results = {
            'file_id': file_id,
            'language': language,
            'metrics': {}
        }
        
        # Get texts
        transcript_path = Path("output") / file_id / f"{file_id}.txt"
        translation_path = Path("output") / file_id / f"{file_id}.{language}.txt"
        
        if not (transcript_path.exists() and translation_path.exists()):
            return {"error": "Files not found"}
        
        transcript = transcript_path.read_text(encoding='utf-8')
        translation = translation_path.read_text(encoding='utf-8')
        
        # Get speech characteristics
        source_chars = self.analyze_speech_characteristics(transcript, 'source')
        target_chars = self.analyze_speech_characteristics(translation, language)
        
        # Compare characteristics
        results['metrics']['punctuation_preservation'] = (
            min(source_chars['punctuation_density'], target_chars['punctuation_density']) /
            max(source_chars['punctuation_density'], target_chars['punctuation_density'], 0.001)
        )
        
        results['metrics']['fragment_preservation'] = 1 - abs(
            source_chars['fragment_ratio'] - target_chars['fragment_ratio']
        )
        
        results['metrics']['repetition_preservation'] = 1 - abs(
            source_chars['repetition_score'] - target_chars['repetition_score']
        )
        
        results['metrics']['pause_preservation'] = (
            min(source_chars['pause_indicators'], target_chars['pause_indicators']) /
            max(source_chars['pause_indicators'], target_chars['pause_indicators'], 1)
        )
        
        # Structural comparison
        structural = self.compare_structural_similarity(transcript, translation)
        results['metrics'].update(structural)
        
        # Calculate overall similarity score
        scores = [v for k, v in results['metrics'].items() if isinstance(v, (int, float))]
        results['overall_similarity'] = statistics.mean(scores) if scores else 0
        
        # Interpretation
        if results['overall_similarity'] > 0.8:
            results['interpretation'] = "High structural similarity - likely preserves speech patterns well"
        elif results['overall_similarity'] > 0.6:
            results['interpretation'] = "Moderate similarity - some speech patterns may be lost"
        else:
            results['interpretation'] = "Low similarity - may be over-polished or missing speech elements"
        
        return results
    
    def generate_report(self, file_id: str, language: str) -> Dict:
        """Generate comprehensive independent quality report."""
        report = {
            'file_id': file_id,
            'language': language,
            'checks': {}
        }
        
        # Run all checks
        print("Running cross-validation metrics...")
        report['checks']['metrics'] = self.cross_validate_with_basic_metrics(file_id, language)
        
        print("Generating native speaker checklist...")
        report['checks']['native_speaker'] = self.generate_native_speaker_checklist(file_id, language)
        
        # Get database scores for comparison
        score_query = """
            SELECT score, model, evaluated_at, issues
            FROM quality_evaluations
            WHERE file_id = ? AND language = ?
            ORDER BY evaluated_at DESC
            LIMIT 2
        """
        scores = self.db.execute_query(score_query, (file_id, language))
        if scores:
            report['gpt_scores'] = scores
        
        return report

def main():
    parser = argparse.ArgumentParser(
        description="Independent quality check for translations"
    )
    parser.add_argument(
        '--file-id',
        required=True,
        help='File ID to check'
    )
    parser.add_argument(
        '--language',
        required=True,
        choices=['en', 'de', 'he'],
        help='Language to check'
    )
    parser.add_argument(
        '--output-format',
        choices=['json', 'html'],
        default='json',
        help='Output format'
    )
    
    args = parser.parse_args()
    
    checker = IndependentQualityChecker()
    report = checker.generate_report(args.file_id, args.language)
    
    # Save report
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    if args.output_format == 'json':
        report_path = reports_dir / f"independent_check_{args.file_id}_{args.language}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    else:
        # Generate HTML for easier sharing
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Independent Quality Check - {args.file_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .metric {{ margin: 10px 0; padding: 10px; background: #f0f0f0; }}
        .good {{ color: green; }}
        .warning {{ color: orange; }}
        .bad {{ color: red; }}
        pre {{ background: #f5f5f5; padding: 10px; overflow: auto; }}
    </style>
</head>
<body>
    <h1>Independent Quality Check</h1>
    <p>File: {args.file_id}</p>
    <p>Language: {args.language.upper()}</p>
    
    <h2>Structural Similarity Metrics</h2>
"""
        
        if 'metrics' in report['checks']:
            metrics = report['checks']['metrics']['metrics']
            for metric, value in metrics.items():
                css_class = 'good' if value > 0.8 else 'warning' if value > 0.6 else 'bad'
                html += f'<div class="metric {css_class}">{metric}: {value:.2%}</div>\n'
            
            html += f'<p><strong>Overall Similarity: {report["checks"]["metrics"]["overall_similarity"]:.2%}</strong></p>'
            html += f'<p>{report["checks"]["metrics"]["interpretation"]}</p>'
        
        html += """
    <h2>Native Speaker Evaluation Form</h2>
    <div style="background: #e8f4f8; padding: 20px; margin: 20px 0;">
"""
        
        if 'native_speaker' in report['checks']:
            checklist = report['checks']['native_speaker']
            html += f'<pre>{checklist["instructions"]}</pre>'
            
            if 'excerpts' in checklist:
                html += '<h3>Sample Excerpts</h3>'
                for excerpt in checklist['excerpts']:
                    html += f'''
<div style="margin: 20px 0; padding: 15px; background: white;">
    <p><strong>Line {excerpt["line_number"]}:</strong></p>
    <p>Source: {excerpt["source"]}</p>
    <p>Translation: {excerpt["translation"]}</p>
    <p><em>Check for: {excerpt["check_for"]}</em></p>
</div>
'''
        
        html += """
    </div>
</body>
</html>
"""
        
        report_path = reports_dir / f"independent_check_{args.file_id}_{args.language}.html"
        report_path.write_text(html, encoding='utf-8')
    
    print(f"Report saved to: {report_path}")
    
    # Print summary
    if 'metrics' in report['checks']:
        print("\nStructural Similarity Summary:")
        print(f"Overall: {report['checks']['metrics']['overall_similarity']:.2%}")
        print(report['checks']['metrics']['interpretation'])

if __name__ == "__main__":
    main()