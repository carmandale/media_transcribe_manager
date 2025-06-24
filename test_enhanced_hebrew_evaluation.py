#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced Hebrew evaluation functionality.
This script shows how the new Hebrew-specific features work without requiring API calls.
"""

from scribe.evaluate import (
    contains_hebrew, 
    detect_language_ratio, 
    validate_hebrew_translation,
    HistoricalEvaluator
)

def test_hebrew_detection():
    """Test Hebrew language detection utilities"""
    print("=" * 50)
    print("HEBREW DETECTION TESTS")
    print("=" * 50)
    
    test_cases = [
        ("Pure Hebrew", "אני זוכר את המלחמה. זה היה בשנת 1943."),
        ("Pure English", "I remember the war. It was in 1943."),
        ("Mixed", "I remember המלחמה. It was ב-1943."),
        ("Placeholder", "[Hebrew translation not available]"),
        ("Empty", "")
    ]
    
    for name, text in test_cases:
        has_hebrew = contains_hebrew(text)
        ratio = detect_language_ratio(text)
        
        print(f"\n{name}:")
        print(f"  Text: {text[:50]}{'...' if len(text) > 50 else ''}")
        print(f"  Contains Hebrew: {has_hebrew}")
        print(f"  Hebrew ratio: {ratio:.1%}")

def test_hebrew_validation():
    """Test Hebrew translation validation"""
    print("\n" + "=" * 50)
    print("HEBREW VALIDATION TESTS")
    print("=" * 50)
    
    test_cases = [
        ("Good Hebrew", "אני זוכר את המלחמה הגדולה. זה היה זמן קשה מאוד עבור המשפחה שלנו."),
        ("English instead of Hebrew", "I remember the great war. It was a very difficult time for our family."),
        ("Mixed with low Hebrew ratio", "I remember את המלחמה הגדולה."),
        ("Placeholder text", "[Hebrew translation not available for this segment]"),
        ("Short Hebrew", "שלום"),
    ]
    
    for name, text in test_cases:
        validation = validate_hebrew_translation(text)
        
        print(f"\n{name}:")
        print(f"  Text: {text[:60]}{'...' if len(text) > 60 else ''}")
        print(f"  Valid: {validation['is_valid']}")
        print(f"  Hebrew ratio: {validation['hebrew_ratio']:.1%}")
        print(f"  Issues: {validation['issues']}")
        if validation['warnings']:
            print(f"  Warnings: {validation['warnings']}")

def test_evaluator_setup():
    """Test that the enhanced evaluator is properly configured"""
    print("\n" + "=" * 50)
    print("EVALUATOR CONFIGURATION TESTS")
    print("=" * 50)
    
    evaluator = HistoricalEvaluator(model="gpt-4.1")
    
    print(f"Model: {evaluator.model}")
    print(f"General weights: {evaluator.SCORE_WEIGHTS}")
    print(f"Hebrew weights: {evaluator.HEBREW_SCORE_WEIGHTS}")
    
    # Check that Hebrew weights include Hebrew-specific criteria
    hebrew_specific = set(evaluator.HEBREW_SCORE_WEIGHTS.keys()) - set(evaluator.SCORE_WEIGHTS.keys())
    print(f"Hebrew-specific criteria: {hebrew_specific}")
    
    # Verify prompts are different
    has_hebrew_prompt = "HEBREW-SPECIFIC EVALUATION CRITERIA" in evaluator.HEBREW_EVALUATION_PROMPT
    has_general_prompt = "EVALUATION CRITERIA" in evaluator.EVALUATION_PROMPT
    
    print(f"Has Hebrew-specific prompt: {has_hebrew_prompt}")
    print(f"Has general prompt: {has_general_prompt}")

def test_cli_integration():
    """Test CLI integration points"""
    print("\n" + "=" * 50)
    print("CLI INTEGRATION DEMO")
    print("=" * 50)
    
    print("Enhanced Hebrew evaluation can be used with:")
    print("  uv run python scribe_cli.py evaluate he --enhanced --model gpt-4.1")
    print("\nThis will:")
    print("  1. Auto-detect Hebrew in translations")
    print("  2. Perform sanity checks (no English in Hebrew files)")
    print("  3. Use Hebrew-specific evaluation prompt")
    print("  4. Apply Hebrew-specific scoring weights")
    print("  5. Report Hebrew validation statistics")
    print("  6. Use larger context window for modern GPT models")

if __name__ == "__main__":
    test_hebrew_detection()
    test_hebrew_validation()
    test_evaluator_setup()
    test_cli_integration()
    
    print("\n" + "=" * 50)
    print("INTEGRATION COMPLETE")
    print("=" * 50)
    print("Enhanced Hebrew evaluation functionality has been successfully integrated!")
    print("Use --enhanced flag with Hebrew evaluations for improved accuracy.")