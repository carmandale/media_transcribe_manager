#!/usr/bin/env python3
"""
Demonstration of SRT translation cost savings.
Shows how batch translation with deduplication saves money.
"""

import tempfile
import os
from scribe.srt_translator import SRTTranslator

def create_realistic_srt(num_segments=3000):
    """Create a realistic SRT file similar to actual interview transcripts."""
    # Common repeated phrases in interviews
    repeated_phrases = [
        ("Mm-hmm.", 150),
        ("Yes.", 120),
        ("Ja.", 200),
        ("Uh...", 80),
        ("Yeah.", 60),
        ("No.", 40),
        ("I see.", 30),
        ("Okay.", 50),
        ("Thank you.", 20),
        ("Please continue.", 15),
    ]
    
    # Generate SRT content
    lines = []
    segment_num = 1
    time_offset = 0
    
    # Add repeated phrases throughout
    for phrase, count in repeated_phrases:
        for _ in range(count):
            start_min = time_offset // 60
            start_sec = time_offset % 60
            end_offset = time_offset + 2
            end_min = end_offset // 60
            end_sec = end_offset % 60
            
            lines.append(f"{segment_num}")
            lines.append(f"00:{start_min:02d}:{start_sec:02d},000 --> 00:{end_min:02d}:{end_sec:02d},000")
            lines.append(phrase)
            lines.append("")
            
            segment_num += 1
            time_offset += 3
            
            if segment_num > num_segments:
                break
        if segment_num > num_segments:
            break
    
    # Fill remaining with unique content
    unique_phrases = [
        "Can you tell me about your childhood?",
        "We lived in a small village near Berlin.",
        "My father was a teacher at the local school.",
        "Life was difficult during those years.",
        "We had to leave everything behind.",
        "I remember the day very clearly.",
        "It was a cold winter morning.",
        "The soldiers came to our house.",
        "My mother tried to protect us.",
        "We were taken to the train station.",
    ]
    
    while segment_num <= num_segments:
        for phrase in unique_phrases:
            if segment_num > num_segments:
                break
                
            start_min = time_offset // 60
            start_sec = time_offset % 60
            end_offset = time_offset + 4
            end_min = end_offset // 60
            end_sec = end_offset % 60
            
            # Add some variation
            modified_phrase = f"{phrase} (segment {segment_num})"
            
            lines.append(f"{segment_num}")
            lines.append(f"00:{start_min:02d}:{start_sec:02d},000 --> 00:{end_min:02d}:{end_sec:02d},000")
            lines.append(modified_phrase)
            lines.append("")
            
            segment_num += 1
            time_offset += 5
    
    return "\n".join(lines)


def demonstrate_savings():
    """Show the cost savings for a realistic interview transcript."""
    print("SRT Translation Cost Savings Demonstration")
    print("=" * 60)
    print("\nScenario: 1-hour interview transcript with ~3000 segments")
    print("(Similar to actual Holocaust survivor testimonies)\n")
    
    # Create test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
        f.write(create_realistic_srt(3000))
        test_file = f.name
    
    try:
        translator = SRTTranslator()
        
        # Estimate costs for different languages
        for target_lang in ['en', 'de', 'he']:
            print(f"\nTranslating to {target_lang.upper()}:")
            print("-" * 40)
            
            cost_info = translator.estimate_cost(test_file, target_lang)
            
            print(f"Total segments: {cost_info['total_segments']:,}")
            print(f"Unique texts: {cost_info['unique_texts']:,}")
            print(f"Deduplication rate: {(1 - cost_info['unique_texts']/cost_info['total_segments'])*100:.1f}%")
            print(f"\nTraditional approach (segment-by-segment):")
            print(f"  API calls: {cost_info['total_segments']:,}")
            print(f"  Cost: ${cost_info['cost_without_optimization']:.2f}")
            print(f"\nOptimized approach (batch + deduplication):")
            print(f"  API calls: ~{cost_info['unique_texts']//100 + 1} (batches of 100)")
            print(f"  Cost: ${cost_info['cost_with_optimization']:.2f}")
            print(f"\nSavings: ${cost_info['cost_without_optimization'] - cost_info['cost_with_optimization']:.2f} ({cost_info['savings_factor']:.0f}x reduction)")
        
        # Show total archive savings
        print("\n" + "=" * 60)
        print("TOTAL ARCHIVE SAVINGS (726 files):")
        print("=" * 60)
        
        # Assume average file has similar characteristics
        avg_savings_per_file = cost_info['cost_without_optimization'] - cost_info['cost_with_optimization']
        total_traditional = cost_info['cost_without_optimization'] * 726
        total_optimized = cost_info['cost_with_optimization'] * 726
        
        print(f"\nTraditional approach: ${total_traditional:,.2f}")
        print(f"Optimized approach: ${total_optimized:,.2f}")
        print(f"Total savings: ${total_traditional - total_optimized:,.2f}")
        print(f"\nThat's a {(total_traditional - total_optimized)/total_traditional*100:.0f}% cost reduction!")
        
    finally:
        os.unlink(test_file)
    
    print("\n" + "=" * 60)
    print("Key optimization techniques:")
    print("1. Batch translation (100 texts per API call)")
    print("2. Deduplication (translate 'Mm-hmm' once, apply 150 times)")
    print("3. Language preservation (skip segments already in target language)")
    print("4. Efficient API usage (proper batching reduces overhead)")


if __name__ == "__main__":
    demonstrate_savings()