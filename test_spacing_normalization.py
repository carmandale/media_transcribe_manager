#!/usr/bin/env python3
"""
Test spacing normalization optimization in SRT translator.

This test verifies that the optimization correctly handles texts with
different spacing patterns, reducing unnecessary API calls.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator, SRTSegment


def test_spacing_normalization():
    """Test that spacing normalization reduces unique text count."""
    print("Testing spacing normalization optimization...")
    
    translator = SRTTranslator()
    
    # Test cases with different spacing patterns
    test_texts = [
        "In die Wehrmacht gekommen?",
        "In   die   Wehrmacht   gekommen?",  # Extra spaces
        "In  die  Wehrmacht  gekommen?",     # Different spacing
        "In die Wehrmacht gekommen?",         # Same as first
        "Das ist ein Test",
        "Das   ist   ein   Test",            # Extra spaces
        "Hello world",
        "Hello    world",                     # Extra spaces
    ]
    
    # Test the normalize function directly
    print("\n1. Testing _normalize_spacing function:")
    normalized_results = {}
    for text in test_texts:
        normalized = translator._normalize_spacing(text)
        print(f"   '{text}' -> '{normalized}'")
        normalized_results[text] = normalized
    
    # Count unique normalized texts
    unique_normalized = set(normalized_results.values())
    print(f"\nUnique texts before normalization: {len(test_texts)}")
    print(f"Unique texts after normalization: {len(unique_normalized)}")
    print(f"Reduction: {len(test_texts) - len(unique_normalized)} ({(1 - len(unique_normalized)/len(test_texts))*100:.1f}%)")
    
    # Verify specific cases
    print("\n2. Verifying specific cases:")
    assert translator._normalize_spacing("In   die   Wehrmacht   gekommen?") == "In die Wehrmacht gekommen?"
    print("   ✓ Multiple spaces normalized correctly")
    
    assert translator._normalize_spacing("Das   ist   ein   Test") == "Das ist ein Test"
    print("   ✓ German text normalized correctly")
    
    assert translator._normalize_spacing("Hello    world") == "Hello world"
    print("   ✓ English text normalized correctly")
    
    # Test with leading/trailing spaces
    assert translator._normalize_spacing("  Spaces  everywhere  ") == "Spaces everywhere"
    print("   ✓ Leading/trailing spaces handled correctly")
    
    # Test empty and single word cases
    assert translator._normalize_spacing("") == ""
    assert translator._normalize_spacing("Word") == "Word"
    print("   ✓ Edge cases handled correctly")
    
    print("\n✅ All spacing normalization tests passed!")
    
    # Show the impact on the specific problematic case
    print("\n3. Impact on the problematic interview:")
    problematic_texts = [
        "In   die   Wehrmacht   gekommen?",
        "In die Wehrmacht gekommen?",
        "Ja,   ich   bin   1936   geboren.",
        "Ja, ich bin 1936 geboren.",
    ]
    
    unique_before = len(set(problematic_texts))
    unique_after = len(set(translator._normalize_spacing(t) for t in problematic_texts))
    
    print(f"   Unique texts before: {unique_before}")
    print(f"   Unique texts after: {unique_after}")
    print(f"   API calls saved: {unique_before - unique_after}")
    
    return True


if __name__ == "__main__":
    success = test_spacing_normalization()
    sys.exit(0 if success else 1)