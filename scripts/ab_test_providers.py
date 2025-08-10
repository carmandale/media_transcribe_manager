#!/usr/bin/env python3
"""
A/B Testing Harness for Translation Provider Comparison
Tests DeepL vs OpenAI for English and German translations
"""

import os
import sys
import json
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import statistics

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.translate import HistoricalTranslator
from scribe.srt_parser import parse_srt_file


class ProviderABTest:
    """A/B testing harness for translation providers."""
    
    def __init__(self, sample_size: int = 10):
        """
        Initialize A/B testing.
        
        Args:
            sample_size: Number of segments to test per interview
        """
        self.sample_size = sample_size
        self.translator = HistoricalTranslator()
        self.results = {
            'test_id': f"ab_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'sample_size': sample_size,
            'providers': {
                'deepl': {'en': [], 'de': []},
                'openai': {'en': [], 'de': []}
            },
            'summary': {}
        }
    
    def select_test_segments(self, srt_file: Path) -> List[str]:
        """
        Select random segments from SRT file for testing.
        
        Args:
            srt_file: Path to SRT file
            
        Returns:
            List of segment texts
        """
        segments = parse_srt_file(str(srt_file))
        
        # Filter out very short segments
        valid_segments = [s for s in segments if len(s.text.strip()) > 20]
        
        # Select random sample
        sample_count = min(self.sample_size, len(valid_segments))
        selected = random.sample(valid_segments, sample_count)
        
        return [s.text for s in selected]
    
    def test_provider(self, texts: List[str], provider: str, target_lang: str) -> Dict:
        """
        Test a single provider with given texts.
        
        Args:
            texts: List of texts to translate
            provider: Provider name ('deepl' or 'openai')
            target_lang: Target language ('en' or 'de')
            
        Returns:
            Test results dictionary
        """
        start_time = time.time()
        results = []
        errors = []
        
        for text in texts:
            try:
                segment_start = time.time()
                translated = self.translator.translate(
                    text, 
                    target_language=target_lang,
                    provider=provider
                )
                segment_time = time.time() - segment_start
                
                results.append({
                    'original_length': len(text),
                    'translated_length': len(translated) if translated else 0,
                    'time_seconds': round(segment_time, 3),
                    'success': translated is not None
                })
                
            except Exception as e:
                errors.append(str(e))
                results.append({
                    'original_length': len(text),
                    'translated_length': 0,
                    'time_seconds': 0,
                    'success': False,
                    'error': str(e)
                })
        
        total_time = time.time() - start_time
        
        return {
            'provider': provider,
            'target_language': target_lang,
            'total_segments': len(texts),
            'successful_segments': sum(1 for r in results if r['success']),
            'total_time': round(total_time, 2),
            'avg_time_per_segment': round(total_time / len(texts), 3) if texts else 0,
            'segment_times': [r['time_seconds'] for r in results if r['success']],
            'errors': errors,
            'details': results
        }
    
    def run_ab_test(self, interview_id: str) -> Dict:
        """
        Run A/B test on a single interview.
        
        Args:
            interview_id: Interview file ID
            
        Returns:
            Complete test results
        """
        print(f"\n=== A/B Testing Translation Providers ===")
        print(f"Interview: {interview_id}")
        print(f"Sample size: {self.sample_size} segments")
        
        # Find original SRT file
        output_dir = Path("output") / interview_id
        orig_srt = output_dir / f"{interview_id}.orig.srt"
        if not orig_srt.exists():
            orig_srt = output_dir / f"{interview_id}.srt"
        
        if not orig_srt.exists():
            print(f"ERROR: No SRT file found for {interview_id}")
            return self.results
        
        # Select test segments
        print("\nSelecting random segments for testing...")
        test_segments = self.select_test_segments(orig_srt)
        print(f"Selected {len(test_segments)} segments")
        
        # Test each provider for each language
        for target_lang in ['en', 'de']:
            print(f"\n--- Testing {target_lang.upper()} translations ---")
            
            # Test DeepL
            print(f"Testing DeepL...")
            deepl_results = self.test_provider(test_segments, 'deepl', target_lang)
            self.results['providers']['deepl'][target_lang] = deepl_results
            print(f"  DeepL: {deepl_results['successful_segments']}/{deepl_results['total_segments']} successful")
            print(f"  Time: {deepl_results['total_time']:.2f}s total, {deepl_results['avg_time_per_segment']:.3f}s avg")
            
            # Test OpenAI
            print(f"Testing OpenAI...")
            openai_results = self.test_provider(test_segments, 'openai', target_lang)
            self.results['providers']['openai'][target_lang] = openai_results
            print(f"  OpenAI: {openai_results['successful_segments']}/{openai_results['total_segments']} successful")
            print(f"  Time: {openai_results['total_time']:.2f}s total, {openai_results['avg_time_per_segment']:.3f}s avg")
        
        # Calculate summary statistics
        self.calculate_summary()
        
        # Print summary
        self.print_summary()
        
        return self.results
    
    def calculate_summary(self):
        """Calculate summary statistics for the A/B test."""
        summary = {}
        
        for lang in ['en', 'de']:
            deepl_data = self.results['providers']['deepl'][lang]
            openai_data = self.results['providers']['openai'][lang]
            
            # Calculate statistics if we have data
            deepl_times = deepl_data.get('segment_times', [])
            openai_times = openai_data.get('segment_times', [])
            
            summary[lang] = {
                'deepl': {
                    'success_rate': deepl_data['successful_segments'] / deepl_data['total_segments'] if deepl_data['total_segments'] > 0 else 0,
                    'avg_time': deepl_data['avg_time_per_segment'],
                    'median_time': statistics.median(deepl_times) if deepl_times else 0,
                    'total_time': deepl_data['total_time']
                },
                'openai': {
                    'success_rate': openai_data['successful_segments'] / openai_data['total_segments'] if openai_data['total_segments'] > 0 else 0,
                    'avg_time': openai_data['avg_time_per_segment'],
                    'median_time': statistics.median(openai_times) if openai_times else 0,
                    'total_time': openai_data['total_time']
                },
                'winner': {
                    'speed': 'deepl' if deepl_data['avg_time_per_segment'] < openai_data['avg_time_per_segment'] else 'openai',
                    'reliability': 'deepl' if deepl_data['successful_segments'] > openai_data['successful_segments'] else 'openai',
                    'speed_advantage': abs(deepl_data['avg_time_per_segment'] - openai_data['avg_time_per_segment'])
                }
            }
        
        # Overall recommendation
        deepl_wins = sum(1 for lang in ['en', 'de'] 
                        for metric in ['speed', 'reliability'] 
                        if summary[lang]['winner'][metric] == 'deepl')
        
        summary['recommendation'] = {
            'provider': 'deepl' if deepl_wins >= 2 else 'openai',
            'reason': f"Won {deepl_wins}/4 metrics" if deepl_wins >= 2 else f"Won {4-deepl_wins}/4 metrics",
            'english_provider': summary['en']['winner']['speed'],
            'german_provider': summary['de']['winner']['speed']
        }
        
        self.results['summary'] = summary
    
    def print_summary(self):
        """Print a formatted summary of the A/B test results."""
        print("\n" + "="*60)
        print("A/B TEST SUMMARY")
        print("="*60)
        
        summary = self.results['summary']
        
        for lang in ['en', 'de']:
            print(f"\n{lang.upper()} Translation Results:")
            print("-" * 40)
            
            deepl = summary[lang]['deepl']
            openai = summary[lang]['openai']
            winner = summary[lang]['winner']
            
            print(f"DeepL:")
            print(f"  Success rate: {deepl['success_rate']:.1%}")
            print(f"  Avg time: {deepl['avg_time']:.3f}s")
            print(f"  Median time: {deepl['median_time']:.3f}s")
            
            print(f"\nOpenAI:")
            print(f"  Success rate: {openai['success_rate']:.1%}")
            print(f"  Avg time: {openai['avg_time']:.3f}s")
            print(f"  Median time: {openai['median_time']:.3f}s")
            
            print(f"\nWinner:")
            print(f"  Speed: {winner['speed']} (by {winner['speed_advantage']:.3f}s)")
            print(f"  Reliability: {winner['reliability']}")
        
        print("\n" + "="*60)
        print("RECOMMENDATION")
        print("="*60)
        rec = summary['recommendation']
        print(f"Recommended provider: {rec['provider'].upper()}")
        print(f"Reason: {rec['reason']}")
        print(f"\nOptimal configuration:")
        print(f"  English: {rec['english_provider']}")
        print(f"  German: {rec['german_provider']}")
    
    def save_results(self, output_file: str = None):
        """
        Save test results to JSON file.
        
        Args:
            output_file: Output file path (default: ab_test_results_<timestamp>.json)
        """
        if not output_file:
            output_file = f"ab_test_results_{self.results['test_id']}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")


def main():
    """Main entry point for A/B testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='A/B test translation providers')
    parser.add_argument('interview_id', nargs='?', 
                       default='5c544e90-807b-4d2d-b75b-95aa739aed45',
                       help='Interview ID to test')
    parser.add_argument('--sample-size', type=int, default=10,
                       help='Number of segments to test per interview (default: 10)')
    parser.add_argument('--save', action='store_true',
                       help='Save results to JSON file')
    
    args = parser.parse_args()
    
    # Run A/B test
    tester = ProviderABTest(sample_size=args.sample_size)
    results = tester.run_ab_test(args.interview_id)
    
    # Save results if requested
    if args.save:
        tester.save_results()
    
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())