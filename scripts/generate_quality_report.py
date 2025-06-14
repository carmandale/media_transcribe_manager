#!/usr/bin/env python3
"""
Quality Report Generator for Scribe Project

Generates comprehensive reports on translation quality and readiness for delivery.
Includes detailed analysis of quality scores, missing evaluations, and action items.

Usage:
    uv run python scripts/generate_quality_report.py [--format html|csv|json] [--output-file FILENAME]
"""

import sys
import argparse
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import html

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager

class QualityReportGenerator:
    """Generates comprehensive quality reports for the Scribe project."""
    
    def __init__(self, db_path: str = "media_tracking.db"):
        self.db = DatabaseManager(db_path)
        
    def get_all_files_status(self) -> List[Dict]:
        """Get comprehensive status for all files."""
        query = """
            SELECT 
                ps.*,
                qe_en.score as en_score,
                qe_en.evaluated_at as en_evaluated_at,
                qe_de.score as de_score,
                qe_de.evaluated_at as de_evaluated_at,
                qe_he.score as he_score,
                qe_he.evaluated_at as he_evaluated_at
            FROM processing_status ps
            LEFT JOIN quality_evaluations qe_en ON ps.file_id = qe_en.file_id AND qe_en.language = 'en'
            LEFT JOIN quality_evaluations qe_de ON ps.file_id = qe_de.file_id AND qe_de.language = 'de'
            LEFT JOIN quality_evaluations qe_he ON ps.file_id = qe_he.file_id AND qe_he.language = 'he'
            ORDER BY ps.file_id
        """
        return self.db.execute_query(query)
    
    def analyze_quality_status(self, files: List[Dict]) -> Dict:
        """Analyze quality status across all files."""
        total_files = len(files)
        
        analysis = {
            'total_files': total_files,
            'processing_complete': 0,
            'quality_status': {
                'fully_evaluated': 0,
                'partially_evaluated': 0,
                'not_evaluated': 0
            },
            'by_language': {
                'en': {'evaluated': 0, 'excellent': 0, 'acceptable': 0, 'needs_improvement': 0, 'total_score': 0},
                'de': {'evaluated': 0, 'excellent': 0, 'acceptable': 0, 'needs_improvement': 0, 'total_score': 0},
                'he': {'evaluated': 0, 'excellent': 0, 'acceptable': 0, 'needs_improvement': 0, 'total_score': 0}
            },
            'ready_for_delivery': 0,
            'action_required': {
                'need_evaluation': [],
                'below_threshold': [],
                'missing_translations': []
            }
        }
        
        for file in files:
            file_id = file['file_id']
            
            # Check if processing is complete
            if (file['transcription_status'] == 'completed' and
                file['translation_en_status'] == 'completed' and
                file['translation_de_status'] == 'completed' and
                file['translation_he_status'] == 'completed'):
                analysis['processing_complete'] += 1
            else:
                analysis['action_required']['missing_translations'].append(file_id)
            
            # Check quality evaluation status
            eval_count = 0
            all_good = True
            
            for lang in ['en', 'de', 'he']:
                score = file[f'{lang}_score']
                if score is not None:
                    eval_count += 1
                    analysis['by_language'][lang]['evaluated'] += 1
                    analysis['by_language'][lang]['total_score'] += score
                    
                    if score >= 8.5:
                        analysis['by_language'][lang]['excellent'] += 1
                    elif score >= 8.0:
                        analysis['by_language'][lang]['acceptable'] += 1
                    else:
                        analysis['by_language'][lang]['needs_improvement'] += 1
                        all_good = False
                        if file_id not in analysis['action_required']['below_threshold']:
                            analysis['action_required']['below_threshold'].append(file_id)
                else:
                    all_good = False
                    if file_id not in analysis['action_required']['need_evaluation']:
                        analysis['action_required']['need_evaluation'].append(file_id)
            
            # Categorize evaluation status
            if eval_count == 3:
                analysis['quality_status']['fully_evaluated'] += 1
                if all_good and file['transcription_status'] == 'completed':
                    analysis['ready_for_delivery'] += 1
            elif eval_count > 0:
                analysis['quality_status']['partially_evaluated'] += 1
            else:
                analysis['quality_status']['not_evaluated'] += 1
        
        # Calculate averages
        for lang in ['en', 'de', 'he']:
            if analysis['by_language'][lang]['evaluated'] > 0:
                analysis['by_language'][lang]['average_score'] = (
                    analysis['by_language'][lang]['total_score'] / 
                    analysis['by_language'][lang]['evaluated']
                )
            else:
                analysis['by_language'][lang]['average_score'] = 0
        
        return analysis
    
    def generate_html_report(self, analysis: Dict, files: List[Dict]) -> str:
        """Generate an HTML report."""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Scribe Quality Report - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #0066cc; }}
        .metric-label {{ color: #666; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .excellent {{ color: #00aa00; font-weight: bold; }}
        .acceptable {{ color: #ff8800; }}
        .needs-improvement {{ color: #cc0000; font-weight: bold; }}
        .not-evaluated {{ color: #666; font-style: italic; }}
        .progress-bar {{ width: 100%; height: 20px; background: #f0f0f0; border-radius: 10px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: #00aa00; transition: width 0.3s; }}
        .action-section {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .ready {{ background: #d4edda; }}
        .warning {{ background: #fff3cd; }}
        .danger {{ background: #f8d7da; }}
    </style>
</head>
<body>
    <h1>Scribe Project Quality Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="summary">
        <h2>Executive Summary</h2>
        <div class="metric">
            <div class="metric-value">{analysis['total_files']}</div>
            <div class="metric-label">Total Files</div>
        </div>
        <div class="metric">
            <div class="metric-value">{analysis['processing_complete']}</div>
            <div class="metric-label">Processing Complete</div>
        </div>
        <div class="metric">
            <div class="metric-value">{analysis['ready_for_delivery']}</div>
            <div class="metric-label">Ready for Delivery</div>
        </div>
        
        <h3>Overall Progress</h3>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {(analysis['ready_for_delivery'] / analysis['total_files'] * 100):.1f}%"></div>
        </div>
        <p>{(analysis['ready_for_delivery'] / analysis['total_files'] * 100):.1f}% ready for delivery</p>
    </div>
    
    <h2>Quality Evaluation Status</h2>
    <table>
        <tr>
            <th>Status</th>
            <th>Count</th>
            <th>Percentage</th>
        </tr>
        <tr>
            <td>Fully Evaluated (all 3 languages)</td>
            <td>{analysis['quality_status']['fully_evaluated']}</td>
            <td>{(analysis['quality_status']['fully_evaluated'] / analysis['total_files'] * 100):.1f}%</td>
        </tr>
        <tr>
            <td>Partially Evaluated</td>
            <td>{analysis['quality_status']['partially_evaluated']}</td>
            <td>{(analysis['quality_status']['partially_evaluated'] / analysis['total_files'] * 100):.1f}%</td>
        </tr>
        <tr>
            <td>Not Evaluated</td>
            <td>{analysis['quality_status']['not_evaluated']}</td>
            <td>{(analysis['quality_status']['not_evaluated'] / analysis['total_files'] * 100):.1f}%</td>
        </tr>
    </table>
    
    <h2>Quality Scores by Language</h2>
    <table>
        <tr>
            <th>Language</th>
            <th>Evaluated</th>
            <th>Average Score</th>
            <th>Excellent (8.5+)</th>
            <th>Acceptable (8.0-8.4)</th>
            <th>Needs Improvement (<8.0)</th>
        </tr>
"""
        
        for lang in ['en', 'de', 'he']:
            lang_data = analysis['by_language'][lang]
            lang_name = {'en': 'English', 'de': 'German', 'he': 'Hebrew'}[lang]
            html_content += f"""
        <tr>
            <td>{lang_name}</td>
            <td>{lang_data['evaluated']} / {analysis['total_files']}</td>
            <td>{lang_data['average_score']:.2f}</td>
            <td class="excellent">{lang_data['excellent']}</td>
            <td class="acceptable">{lang_data['acceptable']}</td>
            <td class="needs-improvement">{lang_data['needs_improvement']}</td>
        </tr>
"""
        
        html_content += """
    </table>
    
    <div class="action-section">
        <h2>Action Required</h2>
        <h3>Files Needing Quality Evaluation</h3>
        <p>{} files need quality evaluation</p>
        
        <h3>Files Below Quality Threshold</h3>
        <p>{} files scored below 8.0 and need improvement</p>
        
        <h3>Files with Incomplete Processing</h3>
        <p>{} files have incomplete transcription or translation</p>
    </div>
    
    <h2>Detailed File List</h2>
    <table>
        <tr>
            <th>File ID</th>
            <th>Transcription</th>
            <th>EN Translation</th>
            <th>DE Translation</th>
            <th>HE Translation</th>
            <th>EN Score</th>
            <th>DE Score</th>
            <th>HE Score</th>
            <th>Status</th>
        </tr>
""".format(
    len(analysis['action_required']['need_evaluation']),
    len(analysis['action_required']['below_threshold']),
    len(analysis['action_required']['missing_translations'])
)
        
        # Add file details
        for file in files[:100]:  # Limit to first 100 for readability
            status = "Ready" if file['file_id'] not in (
                analysis['action_required']['need_evaluation'] + 
                analysis['action_required']['below_threshold'] + 
                analysis['action_required']['missing_translations']
            ) else "Action Required"
            
            html_content += f"""
        <tr>
            <td>{html.escape(file['file_id'])}</td>
            <td>{html.escape(file['transcription_status'])}</td>
            <td>{html.escape(file['translation_en_status'])}</td>
            <td>{html.escape(file['translation_de_status'])}</td>
            <td>{html.escape(file['translation_he_status'])}</td>
"""
            
            for lang in ['en', 'de', 'he']:
                score = file[f'{lang}_score']
                if score is not None:
                    score_class = 'excellent' if score >= 8.5 else 'acceptable' if score >= 8.0 else 'needs-improvement'
                    html_content += f'            <td class="{score_class}">{score:.1f}</td>\n'
                else:
                    html_content += '            <td class="not-evaluated">-</td>\n'
            
            status_class = 'ready' if status == "Ready" else 'warning'
            html_content += f'            <td class="{status_class}">{status}</td>\n        </tr>\n'
        
        if len(files) > 100:
            html_content += f"""
        <tr>
            <td colspan="9" style="text-align: center;">... and {len(files) - 100} more files</td>
        </tr>
"""
        
        html_content += """
    </table>
</body>
</html>
"""
        return html_content
    
    def generate_csv_report(self, files: List[Dict]) -> str:
        """Generate a CSV report."""
        output = []
        writer = csv.DictWriter(output, fieldnames=[
            'file_id', 'transcription_status', 
            'translation_en_status', 'translation_de_status', 'translation_he_status',
            'en_score', 'de_score', 'he_score',
            'en_evaluated_at', 'de_evaluated_at', 'he_evaluated_at',
            'overall_status'
        ])
        
        writer.writeheader()
        for file in files:
            # Determine overall status
            overall_status = 'ready'
            if any(file[f'{lang}_score'] is None for lang in ['en', 'de', 'he']):
                overall_status = 'needs_evaluation'
            elif any(file[f'{lang}_score'] < 8.0 for lang in ['en', 'de', 'he'] if file[f'{lang}_score'] is not None):
                overall_status = 'below_threshold'
            elif any(file[f'translation_{lang}_status'] != 'completed' for lang in ['en', 'de', 'he']):
                overall_status = 'incomplete'
            
            writer.writerow({
                'file_id': file['file_id'],
                'transcription_status': file['transcription_status'],
                'translation_en_status': file['translation_en_status'],
                'translation_de_status': file['translation_de_status'],
                'translation_he_status': file['translation_he_status'],
                'en_score': file['en_score'] or '',
                'de_score': file['de_score'] or '',
                'he_score': file['he_score'] or '',
                'en_evaluated_at': file['en_evaluated_at'] or '',
                'de_evaluated_at': file['de_evaluated_at'] or '',
                'he_evaluated_at': file['he_evaluated_at'] or '',
                'overall_status': overall_status
            })
        
        return '\n'.join(output)

def main():
    parser = argparse.ArgumentParser(
        description="Generate quality reports for the Scribe project"
    )
    parser.add_argument(
        '--format',
        choices=['html', 'csv', 'json'],
        default='html',
        help='Output format (default: html)'
    )
    parser.add_argument(
        '--output-file',
        help='Output filename (default: quality_report_[timestamp].[format])'
    )
    parser.add_argument(
        '--show-all',
        action='store_true',
        help='Show all files in detailed list (default: first 100)'
    )
    
    args = parser.parse_args()
    
    generator = QualityReportGenerator()
    
    print("Fetching file data...")
    files = generator.get_all_files_status()
    
    print("Analyzing quality status...")
    analysis = generator.analyze_quality_status(files)
    
    # Generate output filename
    if args.output_file:
        output_file = args.output_file
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"quality_report_{timestamp}.{args.format}"
    
    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    output_path = reports_dir / output_file
    
    # Generate report
    print(f"Generating {args.format.upper()} report...")
    
    if args.format == 'html':
        content = generator.generate_html_report(analysis, files)
    elif args.format == 'csv':
        content = generator.generate_csv_report(files)
    else:  # json
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'analysis': analysis,
            'files': files if args.show_all else files[:100]
        }
        content = json.dumps(report_data, indent=2)
    
    # Save report
    with open(output_path, 'w') as f:
        f.write(content)
    
    print(f"Report saved to: {output_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("QUALITY REPORT SUMMARY")
    print("="*60)
    print(f"Total Files: {analysis['total_files']}")
    print(f"Processing Complete: {analysis['processing_complete']} ({analysis['processing_complete']/analysis['total_files']*100:.1f}%)")
    print(f"Ready for Delivery: {analysis['ready_for_delivery']} ({analysis['ready_for_delivery']/analysis['total_files']*100:.1f}%)")
    print("\nAction Required:")
    print(f"  - Need Quality Evaluation: {len(analysis['action_required']['need_evaluation'])}")
    print(f"  - Below Quality Threshold: {len(analysis['action_required']['below_threshold'])}")
    print(f"  - Incomplete Processing: {len(analysis['action_required']['missing_translations'])}")

if __name__ == "__main__":
    main()