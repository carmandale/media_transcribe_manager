#!/usr/bin/env python3
"""
Test Speech Pattern Preservation in Translations

This script tests whether the translation system properly preserves
hesitations, filler words, and authentic speech patterns.

Usage:
    uv run python scripts/test_speech_preservation.py
"""

import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

from core_modules.db_manager import DatabaseManager
from core_modules.file_manager import FileManager
from core_modules.translation import TranslationManager

# Test cases with authentic speech patterns
TEST_CASES = [
    {
        'name': 'Basic hesitations',
        'text': 'So, um, when did you first arrive at the camp?',
        'expected_markers': ['um', 'So']
    },
    {
        'name': 'Self-correction',
        'text': 'I think it was, uh, maybe April or... no, no, it was March.',
        'expected_markers': ['uh', 'maybe', '...', 'no, no']
    },
    {
        'name': 'Multiple fillers',
        'text': 'Well, you know, it was... it was very difficult, um, very hard.',
        'expected_markers': ['Well', 'you know', '...', 'um']
    },
    {
        'name': 'Incomplete thought',
        'text': 'The guards were... I mean, they would...',
        'expected_markers': ['...', 'I mean', '...']
    }
]

def test_translation(text: str, target_lang: str = 'de') -> str:
    """Test translation of a text sample."""
    # Initialize managers
    db = DatabaseManager(':memory:')  # Use in-memory DB for testing
    config = {
        'output_directory': './test_output',
        'deepl': {'formality': 'less'}  # Use informal style
    }
    
    file_manager = FileManager(db, config)
    translation_manager = TranslationManager(db, config)
    translation_manager.set_managers(file_manager, None)
    
    # Translate the text
    translated = translation_manager.translate_text(
        text=text,
        target_language=target_lang,
        formality='less'
    )
    
    return translated

def check_preservation(original: str, translated: str, markers: list) -> dict:
    """Check if speech markers were preserved."""
    results = {
        'preserved': [],
        'missing': [],
        'score': 0
    }
    
    # Check each marker
    for marker in markers:
        # For ellipses, check if pauses are indicated
        if marker == '...':
            if '...' in translated or '…' in translated or ' - ' in translated:
                results['preserved'].append(marker)
            else:
                results['missing'].append(marker)
        # For other markers, they should appear in some form
        elif marker in ['um', 'uh', 'ah']:
            # Check for German equivalents: äh, ähm, hm
            if any(filler in translated.lower() for filler in ['äh', 'ähm', 'hm', 'um', 'uh']):
                results['preserved'].append(marker)
            else:
                results['missing'].append(marker)
        else:
            # For other phrases, check if structure is preserved
            if len(original.split()) == len(translated.split()):
                results['preserved'].append('structure')
    
    # Calculate score
    if markers:
        results['score'] = len(results['preserved']) / len(markers) * 100
    
    return results

def main():
    print("Testing Speech Pattern Preservation in Translations")
    print("=" * 60)
    print()
    
    # Test each case
    for test_case in TEST_CASES:
        print(f"Test: {test_case['name']}")
        print(f"Original: {test_case['text']}")
        
        try:
            # Translate to German
            translated = test_translation(test_case['text'], 'de')
            print(f"Translated: {translated}")
            
            # Check preservation
            results = check_preservation(
                test_case['text'],
                translated,
                test_case['expected_markers']
            )
            
            print(f"Preservation Score: {results['score']:.1f}%")
            if results['preserved']:
                print(f"✓ Preserved: {', '.join(results['preserved'])}")
            if results['missing']:
                print(f"✗ Missing: {', '.join(results['missing'])}")
            
        except Exception as e:
            print(f"Error: {str(e)}")
        
        print("-" * 60)
        print()
    
    print("\nNOTE: If preservation scores are low, ensure:")
    print("1. OpenAI API is configured for translation")
    print("2. The --formality less flag is used")
    print("3. The translation prompts have been updated")

if __name__ == "__main__":
    main()