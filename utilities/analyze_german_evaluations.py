#!/usr/bin/env python3
"""
Analyze German Evaluation Results
Identifies low-scoring German translations that need improvement by reading structured JSON.
"""

import json
import os
from pathlib import Path
import re
from typing import Dict, List, Any

def analyze_german_evaluations() -> Dict:
    """Analyze all German evaluation JSON files."""
    output_dir = Path("output")
    results = {
        'total_files': 0,
        'evaluated_files': 0,
        'scores': [],
        'low_scoring_files': [],
        'excellent_files': [],
        'good_files': [],
        'needs_improvement': []
    }
    
    for file_dir in output_dir.iterdir():
        if not file_dir.is_dir():
            continue
            
        eval_file = file_dir / f"{file_dir.name}.evaluations.json"
        if not eval_file.exists():
            continue
            
        results['total_files'] += 1
        
        try:
            with open(eval_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'german' in data:
                german_eval = data['german']
                score = german_eval.get('composite_score', 0)
                
                if score > 0:
                    results['evaluated_files'] += 1
                    results['scores'].append(score)
                    
                    file_info = {
                        'file_id': file_dir.name,
                        'score': score,
                        'evaluation': german_eval
                    }
                    
                    if score >= 8.5:
                        results['excellent_files'].append(file_info)
                    elif score >= 7.0:
                        results['good_files'].append(file_info)
                    else:
                        results['needs_improvement'].append(file_info)
                        if score < 5.0:
                            results['low_scoring_files'].append(file_info)
                            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing {eval_file}: {e}")
            continue
    
    return results

def generate_improvement_plan(results: Dict) -> str:
    """Generate an improvement plan based on evaluation results."""
    total_evaluated = results['evaluated_files']
    if total_evaluated == 0:
        return "No German evaluations found."
    
    avg_score = sum(results['scores']) / len(results['scores']) if results['scores'] else 0
    needs_improvement_count = len(results['needs_improvement'])
    low_scoring_count = len(results['low_scoring_files'])
    
    plan = f"""
🇩🇪 GERMAN TRANSLATION IMPROVEMENT PLAN
=======================================

📊 CURRENT STATUS:
- Total files with German evaluations: {total_evaluated}
- Average score: {avg_score:.2f}/10
- Files needing improvement (<7.0): {needs_improvement_count} ({(needs_improvement_count/total_evaluated)*100:.1f}%)
- Critical low scores (<5.0): {low_scoring_count} ({(low_scoring_count/total_evaluated)*100:.1f}%)

🎯 QUALITY BREAKDOWN:
- 🟢 Excellent (8.5+): {len(results['excellent_files'])}
- 🟡 Good (7.0-8.4): {len(results['good_files'])}
- 🔴 Needs improvement (<7.0): {needs_improvement_count}

🚀 IMPROVEMENT STRATEGY:

PHASE 1: Fix Critical Issues ({low_scoring_count} files)
- Target files scoring below 5.0/10
- These likely have major accuracy or fluency problems.
- Priority for immediate re-translation using an improved prompt or model.

PHASE 2: Improve Moderate Issues ({needs_improvement_count - low_scoring_count} files)
- Target files scoring 5.0-6.9/10
- Focus on specific accuracy and cultural context improvements.
- May need targeted fixes rather than full re-translation.

RECOMMENDED ACTIONS:
1. Run targeted re-translation for scores < 5.0.
2. Review and improve translations scoring 5.0-6.9.
3. Use better German language models or specialized prompts.
4. Focus on historical accuracy and cultural context.
5. Implement quality checks before final approval.

TARGET: Achieve 80%+ of files scoring 7.0+ (currently {((len(results['excellent_files']) + len(results['good_files']))/total_evaluated)*100:.1f}%)
"""
    
    return plan

def save_file_lists(results: Dict[str, Any]):
    """Save lists of files that need improvement."""
    if results['low_scoring_files']:
        low_score_file = "german_low_scores.tsv"
        with open(low_score_file, 'w') as f:
            f.write("file_id\tscore\n")
            for file_info in sorted(results['low_scoring_files'], key=lambda x: x['score']):
                f.write(f"{file_info['file_id']}\t{file_info['score']}\n")
        print(f"\n💾 Low-scoring files saved to: {low_score_file}")
    
    moderate_files = [f for f in results['needs_improvement'] if f['score'] >= 5.0]
    if moderate_files:
        moderate_file = "german_moderate_improvement.tsv"
        with open(moderate_file, 'w') as f:
            f.write("file_id\tscore\n")
            for file_info in sorted(moderate_files, key=lambda x: x['score']):
                f.write(f"{file_info['file_id']}\t{file_info['score']}\n")
        print(f"💾 Moderate improvement files saved to: {moderate_file}")

def main():
    print("Analyzing German evaluation results...")
    results = analyze_german_evaluations()
    
    if results['evaluated_files'] == 0:
        print("❌ No German evaluations found!")
        return
    
    plan = generate_improvement_plan(results)
    print(plan)
    
    save_file_lists(results)

if __name__ == "__main__":
    main() 