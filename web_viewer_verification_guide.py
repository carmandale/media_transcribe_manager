#!/usr/bin/env python3
"""
Generate a verification guide for testing the translation in the web viewer.
"""

import sys
from pathlib import Path

def generate_verification_guide():
    """Generate step-by-step verification guide."""
    
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    base_path = f"output/{interview_id}/"
    
    print("🌐 Web Viewer Verification Guide")
    print("=" * 50)
    print(f"Interview ID: {interview_id}")
    print(f"Web Viewer: http://localhost:3000")
    print()
    
    # Check file availability
    print("📁 File Status Check:")
    files_to_check = [
        f"{interview_id}.orig.vtt",
        f"{interview_id}.de.vtt", 
        f"{interview_id}.mp4"
    ]
    
    all_files_present = True
    for filename in files_to_check:
        filepath = Path(base_path + filename)
        if filepath.exists() or filepath.is_symlink():
            size = filepath.stat().st_size if filepath.exists() else "symlink"
            print(f"  ✅ {filename} ({size} bytes)")
        else:
            print(f"  ❌ {filename} - MISSING")
            all_files_present = False
    
    if not all_files_present:
        print("\n⚠️  WARNING: Some files are missing. Web viewer may not work properly.")
    
    print(f"\n🎯 Key Test Points to Verify:")
    print("=" * 30)
    
    print("\n1. **Language Detection Fix Verification:**")
    print("   Navigate to the interview in the web viewer")
    print("   Switch to German subtitles")
    print("   Look for these specific segments around the beginning:")
    print("   - 'In die Wehrmacht gekommen?' should appear in German")
    print("   - 'die Wehrmacht-- in Deutschland' should appear in German")
    print("   - These should NOT be translated to English")
    
    print("\n2. **Translation Quality Check:**")
    print("   - German segments should remain in German (preserved)")
    print("   - English segments should be translated to German")
    print("   - Look for phrases like 'Because the family' → 'Wegen der Familie'")
    print("   - Timing should be perfectly synchronized with video")
    
    print("\n3. **Spacing and Formatting:**")
    print("   - Subtitles should display cleanly")
    print("   - No excessive spacing issues visible")
    print("   - Text should be readable and properly formatted")
    
    print("\n4. **Performance and Stability:**")
    print("   - Video should load quickly")
    print("   - Subtitle switching should be responsive")
    print("   - No errors in browser console")
    
    print("\n📋 Step-by-Step Verification:")
    print("=" * 35)
    print("1. Open http://localhost:3000 in your browser")
    print("2. Navigate to the interview gallery")
    print(f"3. Find interview {interview_id}")
    print("4. Click to open the interview")
    print("5. Wait for video to load")
    print("6. Switch subtitle language to German")
    print("7. Skip to around 0:00-0:30 to see Wehrmacht segments")
    print("8. Verify Wehrmacht segments are in German (not English)")
    print("9. Look for English segments that got translated")
    print("10. Check timing synchronization throughout")
    
    # Generate sample timestamps to check
    print(f"\n⏰ Specific Timestamps to Check:")
    print("Based on our verification, check these key moments:")
    print("- 00:00:00 - 00:00:02: 'In die Wehrmacht gekommen?' (should be German)")
    print("- 00:00:02 - 00:00:03: 'die Wehrmacht-- in Deutschland' (should be German)")
    print("- Look for any English phrases that should now be in German")
    
    print(f"\n✅ Success Criteria:")
    print("- Wehrmacht segments display in German")
    print("- No German text shows as English translation")
    print("- English segments are properly translated to German")
    print("- Video and subtitles are synchronized")
    print("- No display or formatting issues")
    
    print(f"\n🔄 If Issues Found:")
    print("- Check browser console for errors")
    print("- Verify VTT file format is correct")
    print("- Ensure latest translation file is being used")
    print("- Test with original subtitles first to ensure basic functionality")
    
    print(f"\n📝 Report Back:")
    print("After testing, please report:")
    print("- ✅/❌ Wehrmacht segments correctly shown in German")
    print("- ✅/❌ English segments translated to German")  
    print("- ✅/❌ Video synchronization working")
    print("- ✅/❌ Overall subtitle quality and readability")
    print("- Any specific issues or errors encountered")
    
    return True

if __name__ == "__main__":
    success = generate_verification_guide()
    sys.exit(0 if success else 1)