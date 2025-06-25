#!/usr/bin/env python3
"""
Simple German Translation Improvement System
Re-evaluates German translations and identifies those needing improvement.
"""

import os
import sys
import json
import time
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.append(str(Path(__file__).parent.parent))

from scribe.database import Database
from scribe.evaluate import HistoricalEvaluator

def get_api_key():
    """Get OpenAI API key from environment."""
    return os.getenv('OPENAI_API_KEY')

def find_improvement_candidates(db, evaluator, max_files=100, min_score=7.0):
    """
    Find German files that need improvement by sampling and evaluating.
    
    Args:
        db: Database instance
        evaluator: HistoricalEvaluator instance
        max_files: Maximum files to evaluate
        min_score: Minimum acceptable score
        
    Returns:
        List of files needing improvement
    """
    print(f"Sampling up to {max_files} German files for quality assessment...")
    
    # Get completed German translations
    completed_files = db.execute_query('''
        SELECT m.file_id, m.safe_filename, m.original_path
        FROM media_files m
        JOIN processing_status p ON m.file_id = p.file_id
        WHERE p.translation_de_status = 'completed'
        ORDER BY RANDOM()
        LIMIT ?
    ''', (max_files,))
    
    improvement_candidates = []
    evaluated_count = 0
    
    for file_info in completed_files:
        try:
            # Get file paths
            file_id = file_info['file_id']
            output_dir = Path("output") / file_id
            
            original_file = output_dir / f"{file_id}.txt"
            german_file = output_dir / f"{file_id}.de.txt"
            
            if not original_file.exists() or not german_file.exists():
                continue
            
            # Read texts (limit for evaluation)
            with open(original_file, 'r', encoding='utf-8') as f:
                original_text = f.read()[:3000]
            
            with open(german_file, 'r', encoding='utf-8') as f:
                german_text = f.read()[:3000]
            
            # Evaluate current translation
            result = evaluator.evaluate(original_text, german_text, language="de")
            
            if result:
                score = result.get('composite_score', 0)
                evaluated_count += 1
                print(f"Evaluated {file_id}: {score:.1f}/10")
                
                if score < min_score:
                    improvement_candidates.append({
                        'file_id': file_id,
                        'current_score': score,
                        'safe_filename': file_info['safe_filename'],
                        'evaluation_details': result
                    })
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"Error evaluating {file_id}: {e}")
            continue
    
    print(f"Evaluated {evaluated_count} files, found {len(improvement_candidates)} needing improvement")
    return improvement_candidates

def analyze_german_quality():
    """
    Analyze German translation quality and generate improvement recommendations.
    """
    # Check for API key
    if not get_api_key():
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        return
    
    # Initialize components
    db = Database()
    evaluator = HistoricalEvaluator()
    
    print("🇩🇪 German Translation Quality Analysis")
    print("=" * 40)
    
    # Get user preferences
    max_files_input = input("Maximum files to evaluate (default: 100): ").strip()
    max_files = int(max_files_input) if max_files_input.isdigit() else 100
    
    min_score_input = input("Minimum acceptable score (default: 7.0): ").strip()
    min_score = float(min_score_input) if min_score_input else 7.0
    
    print(f"\nEvaluating up to {max_files} files with score threshold {min_score}")
    print("This may take 10-30 minutes depending on the number of files...")
    
    # Find improvement candidates
    candidates = find_improvement_candidates(db, evaluator, max_files, min_score)
    
    if not candidates:
        print("✅ Great! No files found that need improvement.")
        return
    
    # Sort by score (worst first)
    candidates = sorted(candidates, key=lambda x: x['current_score'])
    
    # Generate analysis
    total_evaluated = max_files  # Approximation
    avg_score = sum(c['current_score'] for c in candidates) / len(candidates) if candidates else 0
    
    print(f"\n📊 GERMAN QUALITY ANALYSIS RESULTS:")
    print(f"Files needing improvement: {len(candidates)}")
    print(f"Average score of low-scoring files: {avg_score:.2f}/10")
    
    # Save results
    timestamp = int(time.time())
    
    # Save low-scoring files list
    low_score_file = f"german_low_scores_{timestamp}.tsv"
    with open(low_score_file, 'w', encoding='utf-8') as f:
        f.write("file_id\tscore\tsafe_filename\n")
        for candidate in candidates:
            f.write(f"{candidate['file_id']}\t{candidate['current_score']:.1f}\t{candidate['safe_filename']}\n")
    
    # Save detailed analysis
    analysis_file = f"german_analysis_{timestamp}.json"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'analysis_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'parameters': {
                'max_files_evaluated': max_files,
                'min_score_threshold': min_score
            },
            'results': {
                'total_candidates': len(candidates),
                'average_score': avg_score,
                'score_distribution': {}
            },
            'candidates': candidates
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved:")
    print(f"- Low-scoring files: {low_score_file}")
    print(f"- Detailed analysis: {analysis_file}")
    
    # Show score distribution
    print(f"\n📈 SCORE DISTRIBUTION:")
    score_ranges = {
        "1.0-2.9": [c for c in candidates if 1.0 <= c['current_score'] < 3.0],
        "3.0-4.9": [c for c in candidates if 3.0 <= c['current_score'] < 5.0],
        "5.0-6.9": [c for c in candidates if 5.0 <= c['current_score'] < 7.0]
    }
    
    for range_name, files in score_ranges.items():
        if files:
            print(f"Score {range_name}: {len(files)} files")
    
    # Recommendations
    critical_files = [c for c in candidates if c['current_score'] < 4.0]
    moderate_files = [c for c in candidates if 4.0 <= c['current_score'] < min_score]
    
    print(f"\n🚀 RECOMMENDATIONS:")
    if critical_files:
        print(f"1. URGENT: {len(critical_files)} files scoring < 4.0 need immediate re-translation")
    if moderate_files:
        print(f"2. MODERATE: {len(moderate_files)} files scoring 4.0-{min_score-0.1} need quality improvements")
    
    print(f"\n💡 NEXT STEPS:")
    print(f"1. Review the low-scoring files in {low_score_file}")
    print(f"2. Manually inspect a few examples to understand common issues")
    print(f"3. Consider re-translating files with scores < 4.0")
    print(f"4. Use improved German prompts focusing on historical accuracy")
    
    # Show worst examples
    if candidates:
        print(f"\n🔍 WORST SCORING FILES (for manual review):")
        for i, candidate in enumerate(candidates[:5], 1):
            print(f"{i}. {candidate['file_id']}: {candidate['current_score']:.1f}/10")
            if 'evaluation_details' in candidate and candidate['evaluation_details'].get('issues'):
                issues = candidate['evaluation_details']['issues'][:2]  # Show first 2 issues
                for issue in issues:
                    print(f"   Issue: {issue}")
            print()

if __name__ == "__main__":
    analyze_german_quality() 