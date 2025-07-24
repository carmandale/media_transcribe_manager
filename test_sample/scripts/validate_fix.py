#!/usr/bin/env python3
"""
Validate that the subtitle fix worked correctly.
Checks all critical points to ensure the fix is ready for production.
"""

import sys
from pathlib import Path
import json

# Add parent directories to path
test_dir = Path(__file__).parent.parent
project_root = test_dir.parent
sys.path.insert(0, str(project_root))

def validate_subtitle_fix():
    """Run comprehensive validation of the fix"""
    
    print("🔍 Subtitle Fix Validation")
    print("=" * 60)
    
    # Load test data
    with open(test_dir / "test_data.json", 'r') as f:
        test_data = json.load(f)
    
    interview_id = test_data['test_interview']['id']
    
    # Check if output exists
    output_dir = test_dir / "output"
    de_srt = output_dir / f"{interview_id}.de.srt"
    
    if not de_srt.exists():
        print("❌ Output file not found!")
        print(f"   Expected: {de_srt}")
        print("   Run process_test_interview.py first")
        return False
    
    # Read files
    orig_srt = test_dir / "source_files" / f"{interview_id}.orig.srt"
    
    with open(orig_srt, 'r', encoding='utf-8') as f:
        orig_content = f.read()
    
    with open(de_srt, 'r', encoding='utf-8') as f:
        de_content = f.read()
    
    all_passed = True
    
    # Test 1: Segment count preserved
    print("\n📊 Test 1: Segment Count")
    orig_segments = orig_content.count(" --> ")
    de_segments = de_content.count(" --> ")
    
    if orig_segments == de_segments:
        print(f"   ✅ PASS: {orig_segments} segments preserved")
    else:
        print(f"   ❌ FAIL: {orig_segments} → {de_segments} segments")
        all_passed = False
    
    # Test 2: Critical English translation
    print("\n🌐 Test 2: English Translation Check")
    test_points = test_data['test_interview']['test_points']
    
    for point in test_points:
        if point['language'] == 'en':
            if point['current_text'] in de_content:
                print(f"   ❌ FAIL: '{point['current_text']}' not translated at {point['timestamp']}")
                all_passed = False
            else:
                print(f"   ✅ PASS: English text properly translated at {point['timestamp']}")
    
    # Test 3: German preservation
    print("\n🇩🇪 Test 3: German Preservation Check")
    german_phrases = [
        "Wehrmacht",
        "In die Wehrmacht gekommen",
        "Wir wussten nicht viel"
    ]
    
    for phrase in german_phrases:
        if phrase in orig_content and phrase in de_content:
            print(f"   ✅ PASS: German phrase preserved: '{phrase[:30]}...'")
        elif phrase in orig_content and phrase not in de_content:
            print(f"   ❌ FAIL: German phrase lost: '{phrase}'")
            all_passed = False
    
    # Test 4: Timing preservation
    print("\n⏱️  Test 4: Timing Preservation")
    
    # Extract all timestamps
    import re
    timing_pattern = r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})'
    
    orig_timings = re.findall(timing_pattern, orig_content)
    de_timings = re.findall(timing_pattern, de_content)
    
    if orig_timings == de_timings:
        print(f"   ✅ PASS: All {len(orig_timings)} timings preserved exactly")
    else:
        print(f"   ❌ FAIL: Timing mismatch!")
        all_passed = False
    
    # Test 5: Specific problem timestamp
    print("\n🎯 Test 5: Specific Problem Check (00:39:42.030)")
    
    # Find content at specific timestamp
    lines = de_content.split('\n')
    for i, line in enumerate(lines):
        if "00:39:42.030 --> 00:39:45.110" in line:
            if i + 1 < len(lines):
                content_at_timestamp = lines[i + 1].strip()
                print(f"   Content: '{content_at_timestamp}'")
                
                if "much Jews" in content_at_timestamp:
                    print("   ❌ FAIL: English text not translated!")
                    all_passed = False
                elif "Juden" in content_at_timestamp:
                    print("   ✅ PASS: Correctly shows German translation")
                else:
                    print("   ⚠️  WARNING: Unexpected content")
            break
    
    # Test 6: Language consistency
    print("\n🔤 Test 6: Language Consistency")
    
    # Count language indicators
    english_words = ["the", "and", "of", "to", "is", "was", "have", "has"]
    german_words = ["der", "die", "das", "und", "ist", "war", "haben", "nicht"]
    
    de_lower = de_content.lower()
    english_count = sum(1 for word in english_words if f" {word} " in de_lower)
    german_count = sum(1 for word in german_words if f" {word} " in de_lower)
    
    print(f"   German word frequency: {german_count}")
    print(f"   English word frequency: {english_count}")
    
    if german_count > english_count * 2:  # German should dominate
        print("   ✅ PASS: German language dominates as expected")
    else:
        print("   ⚠️  WARNING: Language balance might be off")
    
    # Final summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED! The fix is working correctly.")
        print("\n🎉 Ready to process all 728 interviews!")
    else:
        print("❌ SOME TESTS FAILED! Please review the issues above.")
        print("\n⚠️  Do not process all interviews until tests pass!")
    
    return all_passed

if __name__ == "__main__":
    success = validate_subtitle_fix()
    sys.exit(0 if success else 1)