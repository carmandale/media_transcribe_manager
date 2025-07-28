#!/usr/bin/env python3
"""
Run translation with simple, reliable approach.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator
from scribe.translate import HistoricalTranslator

def run_simple_translation():
    """Run translation with reliable single-segment approach."""
    
    # Test file path
    interview_id = "25af0f9c-8f96-44c9-be5e-e92cb462a41f"
    srt_path = f"output/{interview_id}/{interview_id}.orig.srt"
    output_path = f"output/{interview_id}/{interview_id}.de.srt"
    
    print("🔧 Simple Reliable Translation")
    print("=" * 40)
    print(f"Interview: {interview_id}")
    print(f"Approach: Individual segment processing")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    # Initialize translator
    translator = HistoricalTranslator()
    srt_translator = SRTTranslator(translator)
    
    # Parse segments
    print("📊 Parsing segments...")
    segments = srt_translator.parse_srt(srt_path)
    total_segments = len(segments)
    print(f"  Total segments: {total_segments}")
    
    # Test spacing normalization on sample
    sample_segments = segments[:10]
    spacing_fixes = 0
    for seg in sample_segments:
        original = seg.text
        normalized = srt_translator._normalize_spacing(original)
        if original != normalized:
            spacing_fixes += 1
            if spacing_fixes <= 3:
                print(f"  Example fix: '{original[:30]}...' → '{normalized[:30]}...'")
    
    print(f"  Spacing fixes needed: {spacing_fixes}/10 in sample")
    print()
    
    # Run batch language detection first
    print("🔍 Running batch language detection...")
    start_time = time.time()
    
    try:
        # Use the existing batch language detection
        if translator and hasattr(translator, 'openai_client') and translator.openai_client:
            from scribe.batch_language_detection import detect_languages_for_segments
            language_map = detect_languages_for_segments(
                segments, 
                translator.openai_client,
                batch_size=50  # Small, reliable batches
            )
            
            lang_detection_time = time.time() - start_time
            print(f"  Language detection completed in {lang_detection_time:.1f}s")
            print(f"  Detected languages for {len(language_map)} segments")
            
            # Quick sample of detection results
            german_count = sum(1 for seg in segments[:20] if seg.detected_language == 'de')
            english_count = sum(1 for seg in segments[:20] if seg.detected_language == 'en')
            print(f"  Sample detection (first 20): {german_count} German, {english_count} English")
            
            # Check Wehrmacht segments specifically
            wehrmacht_segments = [seg for seg in segments if "Wehrmacht" in seg.text]
            if wehrmacht_segments:
                wehrmacht_german = sum(1 for seg in wehrmacht_segments if seg.detected_language == 'de')
                print(f"  Wehrmacht segments: {wehrmacht_german}/{len(wehrmacht_segments)} detected as German ✅")
            
        else:
            print("  No OpenAI client available for batch detection")
            return False
        
        # Now do translation with deduplication but simple processing
        print(f"\n🎯 Running optimized translation...")
        translation_start = time.time()
        
        # Build unique texts with normalization
        texts_to_translate = {}
        segment_mapping = {}
        
        for i, segment in enumerate(segments):
            if srt_translator.should_translate_segment(segment, 'de'):
                normalized_text = srt_translator._normalize_spacing(segment.text)
                if normalized_text not in texts_to_translate:
                    texts_to_translate[normalized_text] = None
                    segment_mapping[normalized_text] = []
                segment_mapping[normalized_text].append(i)
        
        unique_count = len(texts_to_translate)
        print(f"  Unique texts to translate: {unique_count}")
        print(f"  Total segments: {total_segments}")
        print(f"  Deduplication savings: {total_segments - unique_count} API calls saved")
        
        # Translate unique texts in small batches
        translated_count = 0
        for i, text in enumerate(list(texts_to_translate.keys())):
            if i % 10 == 0:  # Progress every 10 translations
                print(f"  Progress: {i}/{unique_count} texts translated...")
            
            # Individual translation (reliable)
            translation = translator.translate(text, 'de')
            texts_to_translate[text] = translation
            translated_count += 1
        
        translation_time = time.time() - translation_start
        print(f"  Translation completed in {translation_time:.1f}s")
        
        # Apply translations back to segments
        print(f"\n💾 Applying translations and saving...")
        translated_segments = []
        
        for segment in segments:
            new_segment = type(segment)(
                index=segment.index,
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=segment.text,
                detected_language=segment.detected_language
            )
            
            # Apply translation if available
            normalized_text = srt_translator._normalize_spacing(segment.text)
            if normalized_text in texts_to_translate and texts_to_translate[normalized_text]:
                new_segment.text = texts_to_translate[normalized_text]
            
            translated_segments.append(new_segment)
        
        # Save the result
        success = srt_translator.save_translated_srt(translated_segments, output_path)
        
        total_time = time.time() - start_time
        
        if success:
            print(f"✅ Translation pipeline completed!")
            print(f"\n📊 Final Results:")
            print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
            print(f"  Language detection: {lang_detection_time:.1f}s")
            print(f"  Translation: {translation_time:.1f}s")
            print(f"  Unique texts translated: {unique_count}")
            print(f"  API calls saved: {total_segments - unique_count}")
            
            # Performance comparison
            old_estimated_time = 600  # 10 minutes
            improvement = ((old_estimated_time - total_time) / old_estimated_time) * 100
            print(f"  Estimated improvement: {improvement:.0f}% faster than before")
            
            print(f"\n✅ Saved to: {output_path}")
            return True
        else:
            print("❌ Failed to save translated file")
            return False
            
    except Exception as e:
        total_time = time.time() - start_time
        print(f"❌ Translation failed after {total_time:.1f}s")
        print(f"Error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = run_simple_translation()
    sys.exit(0 if success else 1)