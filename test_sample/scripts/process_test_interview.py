#!/usr/bin/env python3
"""
Process the test interview with the subtitle fix.
This demonstrates the complete fix for the remote AI agent.
"""

import os
import sys
from pathlib import Path

# Add parent directories to path for imports
test_dir = Path(__file__).parent.parent
project_root = test_dir.parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import translate_srt_file

def main():
    """Process test interview with all fixes applied"""
    
    print("🔧 Subtitle Translation Fix - Test Processing")
    print("=" * 60)
    
    # Setup paths
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    source_dir = test_dir / "source_files"
    output_dir = test_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Input and output files
    orig_srt = source_dir / f"{interview_id}.orig.srt"
    de_srt_out = output_dir / f"{interview_id}.de.srt"
    
    if not orig_srt.exists():
        print(f"❌ Error: Original SRT not found at {orig_srt}")
        print("   Make sure you're running from the scribe directory")
        return False
    
    print(f"📄 Input: {orig_srt}")
    print(f"📄 Output: {de_srt_out}")
    print()
    
    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("   Export your API key: export OPENAI_API_KEY='your-key-here'")
        return False
    
    print("🚀 Processing with fixes:")
    print("   ✓ GPT-4o-mini language detection")
    print("   ✓ Batch processing (50 segments/call)")
    print("   ✓ Preserve segments already in target language")
    print("   ✓ Translate only segments in other languages")
    print()
    
    # Process with all fixes
    success = translate_srt_file(
        str(orig_srt),
        str(de_srt_out),
        target_language='de',
        preserve_original_when_matching=True,  # KEY FIX: Preserve German when target is German
        batch_size=100,
        estimate_only=False
    )
    
    if success:
        print("\n✅ SUCCESS! Translation completed")
        print(f"\n📄 Output saved to: {de_srt_out}")
        
        # Quick validation
        print("\n🔍 Quick validation:")
        with open(de_srt_out, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if English phrase is gone
        if "much Jews" in content:
            print("   ❌ PROBLEM: English phrase 'much Jews' still present!")
        else:
            print("   ✅ English phrases appear to be translated")
            
        # Check if German is preserved
        if "Wehrmacht" in content:
            print("   ✅ German content preserved")
        else:
            print("   ❌ PROBLEM: German content might be missing")
            
        # Check segment count
        segment_count = content.count(" --> ")
        print(f"   📊 Segment count: {segment_count} (expected: 1835)")
        
        print("\n🎯 Next step: Run validate_fix.py for detailed validation")
        
    else:
        print("\n❌ FAILED! Translation failed")
        print("   Check the logs above for error details")
        
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)