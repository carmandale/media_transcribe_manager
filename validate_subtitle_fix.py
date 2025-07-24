#!/usr/bin/env python3
"""
Validate that the subtitle translation fix is working correctly
by checking the actual output from our test processing.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def validate_german_translation():
    """Validate the German translation output"""
    
    # Path to the test output file
    test_output = "output_fixed/25af0f9c-8f96-44c9-be5e-e92cb462a41f/25af0f9c-8f96-44c9-be5e-e92cb462a41f.de.vtt"
    
    if not os.path.exists(test_output):
        print(f"❌ Test output file not found: {test_output}")
        print("   Run process_single_interview.py first to generate the fixed output")
        return False
    
    print(f"✅ Found test output file: {test_output}")
    
    # Read the file
    with open(test_output, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check 1: File should contain VTT header
    if "WEBVTT" not in content:
        print("❌ Missing WEBVTT header")
        return False
    print("✅ Valid VTT file format")
    
    # Check 2: Should NOT contain untranslated English phrases
    english_phrases = [
        "much Jews. We know that one",
        "How did you feel",
        "I don't think that",
        "What did you think"
    ]
    
    found_english = False
    for phrase in english_phrases:
        if phrase in content:
            print(f"❌ Found untranslated English: '{phrase}'")
            found_english = True
            
            # Find the context
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if phrase in line:
                    start = max(0, i-3)
                    end = min(len(lines), i+4)
                    print(f"   Context (lines {start}-{end}):")
                    for j in range(start, end):
                        print(f"     {j}: {lines[j]}")
    
    if not found_english:
        print("✅ No untranslated English phrases found")
    
    # Check 3: Should contain German text
    german_indicators = ["der", "die", "das", "und", "ich", "wir", "sie", "war", "haben"]
    german_count = sum(1 for word in german_indicators if word in content.lower())
    
    if german_count < 50:
        print(f"❌ Insufficient German content (only {german_count} German words found)")
        return False
    print(f"✅ Contains German text ({german_count} common German words found)")
    
    # Check 4: Specific timestamp check - line 3663
    target_time = "00:39:42.030 --> 00:39:45.110"
    if target_time in content:
        # Find what text is at this timestamp
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if target_time in line and i+1 < len(lines):
                next_line = lines[i+1].strip()
                print(f"\n📍 Text at timestamp {target_time}:")
                print(f"   '{next_line}'")
                
                if "much Jews" in next_line:
                    print("   ❌ This should be translated to German!")
                    return False
                elif "viele Juden" in next_line or "Juden" in next_line:
                    print("   ✅ Correctly translated to German")
                else:
                    print("   ⚠️  Unexpected content - please verify manually")
    
    # Check 5: Timing preservation
    print("\n🕐 Checking timing preservation...")
    timing_count = content.count(" --> ")
    if timing_count < 1800:
        print(f"❌ Missing subtitles? Only {timing_count} timing entries found (expected ~1835)")
        return False
    print(f"✅ Timing preserved ({timing_count} subtitle entries)")
    
    return True

def main():
    print("🔍 Validating Subtitle Translation Fix")
    print("=" * 50)
    
    if validate_german_translation():
        print("\n✅ All validation checks passed!")
        print("The subtitle translation system is working correctly.")
    else:
        print("\n❌ Validation failed!")
        print("Please check the issues above and rerun the translation.")

if __name__ == "__main__":
    main()