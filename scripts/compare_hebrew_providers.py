#!/usr/bin/env python3
"""
Compare Hebrew Translation Providers

This script compares Microsoft Translator and OpenAI for Hebrew translations,
evaluating quality, speed, and cost.

Usage:
    python compare_hebrew_providers.py --file-id FILE_ID
    python compare_hebrew_providers.py --sample-text "Text to translate"
"""

import sys
import time
import os
import argparse
from pathlib import Path
from typing import Dict, Tuple

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager
from core_modules.translation import TranslationManager
from core_modules.file_manager import FileManager

def count_hebrew_chars(text: str) -> int:
    """Count Hebrew characters in text."""
    return sum(1 for c in text if '\u0590' <= c <= '\u05FF')

def analyze_speech_patterns(text: str) -> Dict[str, int]:
    """Analyze speech patterns in Hebrew text."""
    patterns = {
        'hesitations': 0,
        'repetitions': 0,
        'ellipses': 0,
        'questions': 0
    }
    
    # Hebrew hesitations
    hebrew_hesitations = ['אה', 'אמ', 'ממ', 'אהה', 'המממ']
    for hesitation in hebrew_hesitations:
        patterns['hesitations'] += text.count(hesitation)
    
    # Look for ellipses
    patterns['ellipses'] = text.count('...')
    
    # Questions
    patterns['questions'] = text.count('?')
    
    # Simple repetition detection (word repeated within 5 words)
    words = text.split()
    for i in range(len(words) - 5):
        if words[i] in words[i+1:i+6]:
            patterns['repetitions'] += 1
    
    return patterns

def compare_providers(text: str, source_lang: str = 'de') -> Dict[str, Dict]:
    """Compare translation providers for Hebrew."""
    config = {
        'output_directory': './output',
        'deepl': {'api_key': os.getenv('DEEPL_API_KEY')},
        'openai': {'api_key': os.getenv('OPENAI_API_KEY')},
        'microsoft_translator': {
            'api_key': os.getenv('MS_TRANSLATOR_KEY'),
            'location': os.getenv('MS_TRANSLATOR_LOCATION', 'global')
        }
    }
    
    db = DatabaseManager('media_tracking.db')
    tm = TranslationManager(db, config)
    
    results = {}
    
    # Test Microsoft Translator
    if 'microsoft' in tm.providers:
        print("\nTesting Microsoft Translator...")
        start_time = time.time()
        ms_result = tm.translate_text(
            text=text,
            target_language='he',
            source_language=source_lang,
            provider='microsoft'
        )
        ms_time = time.time() - start_time
        
        if ms_result:
            results['microsoft'] = {
                'translation': ms_result,
                'time': ms_time,
                'hebrew_chars': count_hebrew_chars(ms_result),
                'char_count': len(ms_result),
                'patterns': analyze_speech_patterns(ms_result),
                'cost_estimate': len(text) * 0.00001  # $10 per million chars
            }
            print(f"✓ Completed in {ms_time:.2f}s")
        else:
            print("✗ Failed")
    
    # Test OpenAI
    if 'openai' in tm.providers:
        print("\nTesting OpenAI...")
        start_time = time.time()
        openai_result = tm.translate_text(
            text=text,
            target_language='he',
            source_language=source_lang,
            provider='openai'
        )
        openai_time = time.time() - start_time
        
        if openai_result:
            results['openai'] = {
                'translation': openai_result,
                'time': openai_time,
                'hebrew_chars': count_hebrew_chars(openai_result),
                'char_count': len(openai_result),
                'patterns': analyze_speech_patterns(openai_result),
                'cost_estimate': len(text) / 4 * 0.00006  # ~4 chars/token, $60/million tokens
            }
            print(f"✓ Completed in {openai_time:.2f}s")
        else:
            print("✗ Failed")
    
    return results

def print_comparison(results: Dict[str, Dict], source_text: str):
    """Print comparison results."""
    print("\n" + "="*60)
    print("PROVIDER COMPARISON RESULTS")
    print("="*60)
    
    print(f"\nSource text length: {len(source_text)} characters")
    
    for provider, data in results.items():
        print(f"\n{provider.upper()}:")
        print(f"  Translation time: {data['time']:.2f} seconds")
        print(f"  Hebrew characters: {data['hebrew_chars']}")
        print(f"  Total characters: {data['char_count']}")
        print(f"  Estimated cost: ${data['cost_estimate']:.6f}")
        print(f"  Speech patterns preserved:")
        for pattern, count in data['patterns'].items():
            print(f"    - {pattern}: {count}")
        print(f"  Preview: {data['translation'][:100]}...")
    
    # Recommendation
    print("\n" + "-"*60)
    print("RECOMMENDATION:")
    
    if len(results) == 2:
        ms = results.get('microsoft', {})
        oa = results.get('openai', {})
        
        # Speed comparison
        if ms.get('time', float('inf')) < oa.get('time', float('inf')):
            print(f"✓ Microsoft is {oa['time']/ms['time']:.1f}x faster")
        else:
            print(f"✓ OpenAI is {ms['time']/oa['time']:.1f}x faster")
        
        # Cost comparison
        if ms.get('cost_estimate', float('inf')) < oa.get('cost_estimate', float('inf')):
            print(f"✓ Microsoft is {oa['cost_estimate']/ms['cost_estimate']:.1f}x cheaper")
        else:
            print(f"✓ OpenAI is {ms['cost_estimate']/oa['cost_estimate']:.1f}x cheaper")
        
        # Pattern preservation
        ms_patterns = sum(ms.get('patterns', {}).values())
        oa_patterns = sum(oa.get('patterns', {}).values())
        if abs(ms_patterns - oa_patterns) < 2:
            print("✓ Both preserve speech patterns equally well")
        elif ms_patterns > oa_patterns:
            print("✓ Microsoft preserves more speech patterns")
        else:
            print("✓ OpenAI preserves more speech patterns")

def main():
    parser = argparse.ArgumentParser(description="Compare Hebrew translation providers")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file-id", help="File ID to test with")
    group.add_argument("--sample-text", help="Sample text to translate")
    
    args = parser.parse_args()
    
    if args.file_id:
        # Get transcript text from file
        db = DatabaseManager('media_tracking.db')
        config = {'output_directory': './output'}
        fm = FileManager(db, config)
        
        transcript_path = fm.get_transcript_path(args.file_id)
        if not transcript_path.exists():
            print(f"Error: Transcript not found for {args.file_id}")
            return 1
        
        text = transcript_path.read_text(encoding='utf-8')
        # Use first 1000 characters for comparison
        text = text[:1000]
        print(f"Using first 1000 characters from {args.file_id}")
    else:
        text = args.sample_text
    
    # Detect source language (assume German if contains German words)
    source_lang = 'de' if any(word in text.lower() for word in ['der', 'die', 'das', 'und', 'ich']) else 'en'
    print(f"Detected source language: {source_lang}")
    
    # Run comparison
    results = compare_providers(text, source_lang)
    
    if results:
        print_comparison(results, text)
        
        # Save full translations for manual review
        output_dir = Path("provider_comparison")
        output_dir.mkdir(exist_ok=True)
        
        for provider, data in results.items():
            output_file = output_dir / f"hebrew_{provider}_{int(time.time())}.txt"
            output_file.write_text(data['translation'], encoding='utf-8')
            print(f"\nFull translation saved to: {output_file}")
    else:
        print("No providers available for testing")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())