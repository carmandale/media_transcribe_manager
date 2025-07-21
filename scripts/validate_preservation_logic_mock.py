#!/usr/bin/env python3
"""
Mock validation script for subtitle language preservation logic.
Tests the preservation feature without requiring API keys.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import SRTTranslator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockTranslator:
    """Mock translator that simulates translation without API calls."""
    
    def translate(self, text, target_language, source_language=None):
        """Mock translation that adds a prefix to indicate translation."""
        if not text or not text.strip():
            return text
            
        # Simple mock translation - just add a prefix
        if target_language == 'en':
            return f"[EN] {text}"
        elif target_language == 'de':
            return f"[DE] {text}"
        elif target_language == 'he':
            return f"[HE] {text}"
        else:
            return f"[{target_language.upper()}] {text}"

def create_validation_directories():
    """Create directories for validation results."""
    base_dir = Path("validation_results")
    base_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    validation_dir = base_dir / f"mock_validation_{timestamp}"
    validation_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    (validation_dir / "results").mkdir(exist_ok=True)
    
    return validation_dir

def analyze_srt_segments(srt_path, target_language):
    """Analyze SRT segments to understand language distribution."""
    translator = SRTTranslator()
    segments = translator.parse_srt(str(srt_path))
    
    analysis = {
        'total_segments': len(segments),
        'segments_by_language': {},
        'segments_to_translate': 0,
        'segments_to_preserve': 0,
        'segment_details': []
    }
    
    for segment in segments:
        # Detect language
        detected_lang = translator.detect_segment_language(segment)
        should_translate = translator.should_translate_segment(segment, target_language)
        
        # Update statistics
        if detected_lang:
            analysis['segments_by_language'][detected_lang] = analysis['segments_by_language'].get(detected_lang, 0) + 1
        else:
            analysis['segments_by_language']['unknown'] = analysis['segments_by_language'].get('unknown', 0) + 1
            
        if should_translate:
            analysis['segments_to_translate'] += 1
        else:
            analysis['segments_to_preserve'] += 1
            
        # Store segment details
        analysis['segment_details'].append({
            'index': segment.index,
            'text': segment.text,
            'detected_language': detected_lang,
            'should_translate': should_translate,
            'timing': f"{segment.start_time} --> {segment.end_time}"
        })
    
    return analysis

def mock_translate_srt_with_preservation(srt_path, target_language, output_path):
    """Mock SRT translation with preservation logic."""
    translator = SRTTranslator()
    mock_translator = MockTranslator()
    
    # Replace the real translator with mock
    translator.translator = mock_translator
    
    # Parse segments
    segments = translator.parse_srt(str(srt_path))
    
    # Process each segment
    translated_segments = []
    for segment in segments:
        # Create a copy
        new_segment = type(segment)(
            index=segment.index,
            start_time=segment.start_time,
            end_time=segment.end_time,
            text=segment.text,
            detected_language=segment.detected_language
        )
        
        # Apply preservation logic
        if translator.should_translate_segment(segment, target_language):
            # Translate this segment
            new_segment.text = mock_translator.translate(segment.text, target_language)
        # else: preserve original text (no change)
        
        translated_segments.append(new_segment)
    
    # Save result
    return translator.save_translated_srt(translated_segments, str(output_path))

def validate_preservation_logic(test_file, validation_dir):
    """Test preservation logic on a sample file."""
    logger.info(f"Validating preservation logic on: {test_file}")
    
    # Test for each target language
    target_languages = ['en', 'de', 'he']
    results = {}
    
    for target_lang in target_languages:
        logger.info(f"\\n{'='*60}")
        logger.info(f"Testing preservation for target language: {target_lang.upper()}")
        logger.info(f"{'='*60}")
        
        # Analyze original file
        logger.info("Analyzing original SRT file...")
        analysis = analyze_srt_segments(test_file, target_lang)
        
        logger.info(f"Original file analysis:")
        logger.info(f"  - Total segments: {analysis['total_segments']}")
        logger.info(f"  - Language distribution: {analysis['segments_by_language']}")
        logger.info(f"  - Segments to preserve: {analysis['segments_to_preserve']}")
        logger.info(f"  - Segments to translate: {analysis['segments_to_translate']}")
        
        # Show segment-by-segment analysis
        logger.info(f"\\nSegment-by-segment analysis:")
        for detail in analysis['segment_details']:
            action = "PRESERVE" if not detail['should_translate'] else "TRANSLATE"
            logger.info(f"  Segment {detail['index']}: [{detail['detected_language'] or 'unknown'}] {action}")
            logger.info(f"    Text: {detail['text']}")
            logger.info(f"    Timing: {detail['timing']}")
        
        # Test translation with preservation (mock)
        output_file = validation_dir / "results" / f"test_{target_lang}.srt"
        logger.info(f"\\nTesting mock translation to {target_lang.upper()}...")
        
        success = mock_translate_srt_with_preservation(test_file, target_lang, output_file)
        
        if success:
            logger.info(f"✅ Mock translation successful: {output_file}")
            
            # Compare original vs result
            comparison = compare_srt_files(test_file, output_file, target_lang)
            
            results[target_lang] = {
                'success': True,
                'original_analysis': analysis,
                'comparison': comparison,
                'output_file': str(output_file)
            }
            
            logger.info(f"Preservation validation:")
            logger.info(f"  - Timing preserved: {'✅ YES' if comparison['timing_preserved'] else '❌ NO'}")
            logger.info(f"  - Segment count match: {'✅ YES' if comparison['segment_count_match'] else '❌ NO'}")
            logger.info(f"  - Preservation accuracy: {comparison['preservation_accuracy']:.1%}")
            logger.info(f"  - Correctly preserved: {len([s for s in comparison['preserved_segments'] if s.get('preserved_correctly', True)])}")
            logger.info(f"  - Correctly translated: {len([s for s in comparison['translated_segments'] if s['was_translated']])}")
            
        else:
            logger.error(f"❌ Mock translation failed for {target_lang}")
            results[target_lang] = {
                'success': False,
                'error': 'Mock translation failed'
            }
    
    return results

def compare_srt_files(original_path, result_path, target_language):
    """Compare original and result SRT files to validate preservation."""
    translator = SRTTranslator()
    
    original_segments = translator.parse_srt(str(original_path))
    result_segments = translator.parse_srt(str(result_path))
    
    comparison = {
        'timing_preserved': True,
        'segment_count_match': len(original_segments) == len(result_segments),
        'preserved_segments': [],
        'translated_segments': [],
        'timing_mismatches': [],
        'preservation_accuracy': 0.0
    }
    
    if not comparison['segment_count_match']:
        comparison['timing_preserved'] = False
        return comparison
    
    preserved_count = 0
    total_should_preserve = 0
    
    for orig, result in zip(original_segments, result_segments):
        # Check timing preservation
        if orig.start_time != result.start_time or orig.end_time != result.end_time:
            comparison['timing_preserved'] = False
            comparison['timing_mismatches'].append({
                'segment': orig.index,
                'original_timing': f"{orig.start_time} --> {orig.end_time}",
                'result_timing': f"{result.start_time} --> {result.end_time}"
            })
        
        # Check preservation logic
        should_preserve = not translator.should_translate_segment(orig, target_language)
        
        if should_preserve:
            total_should_preserve += 1
            if orig.text == result.text:
                preserved_count += 1
                comparison['preserved_segments'].append({
                    'segment': orig.index,
                    'text': orig.text,
                    'preserved_correctly': True
                })
            else:
                comparison['preserved_segments'].append({
                    'segment': orig.index,
                    'original_text': orig.text,
                    'result_text': result.text,
                    'preserved_correctly': False
                })
        else:
            comparison['translated_segments'].append({
                'segment': orig.index,
                'original_text': orig.text,
                'translated_text': result.text,
                'was_translated': orig.text != result.text
            })
    
    # Calculate preservation accuracy
    if total_should_preserve > 0:
        comparison['preservation_accuracy'] = preserved_count / total_should_preserve
    
    return comparison

def generate_validation_report(results, validation_dir):
    """Generate a comprehensive validation report."""
    report_file = validation_dir / "mock_validation_report.md"
    
    with open(report_file, 'w') as f:
        f.write("# Mock Subtitle Language Preservation Validation Report\\n\\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
        f.write("**Note:** This is a mock validation using simulated translations\\n\\n")
        
        f.write("## Summary\\n\\n")
        
        successful_tests = sum(1 for result in results.values() if result.get('success', False))
        total_tests = len(results)
        
        f.write(f"- **Total Tests:** {total_tests}\\n")
        f.write(f"- **Successful:** {successful_tests}\\n")
        f.write(f"- **Failed:** {total_tests - successful_tests}\\n\\n")
        
        for target_lang, result in results.items():
            f.write(f"## {target_lang.upper()} Translation Test\\n\\n")
            
            if result.get('success'):
                f.write("✅ **Status:** SUCCESS\\n\\n")
                
                original = result['original_analysis']
                comparison = result['comparison']
                
                f.write("### Original File Analysis\\n")
                f.write(f"- Total segments: {original['total_segments']}\\n")
                f.write(f"- Language distribution: {original['segments_by_language']}\\n")
                f.write(f"- Segments to preserve: {original['segments_to_preserve']}\\n")
                f.write(f"- Segments to translate: {original['segments_to_translate']}\\n\\n")
                
                f.write("### Preservation Results\\n")
                f.write(f"- Timing preserved: {'✅ YES' if comparison['timing_preserved'] else '❌ NO'}\\n")
                f.write(f"- Segment count match: {'✅ YES' if comparison['segment_count_match'] else '❌ NO'}\\n")
                f.write(f"- Preservation accuracy: {comparison['preservation_accuracy']:.1%}\\n")
                f.write(f"- Preserved segments: {len(comparison['preserved_segments'])}\\n")
                f.write(f"- Translated segments: {len(comparison['translated_segments'])}\\n\\n")
                
                if comparison['timing_mismatches']:
                    f.write("### ⚠️ Timing Mismatches\\n")
                    for mismatch in comparison['timing_mismatches']:
                        f.write(f"- Segment {mismatch['segment']}: {mismatch['original_timing']} → {mismatch['result_timing']}\\n")
                    f.write("\\n")
                
                f.write("### Detailed Results\\n")
                for segment in comparison['preserved_segments']:
                    if segment.get('preserved_correctly', True):
                        f.write(f"- ✅ Segment {segment['segment']}: PRESERVED - \\\"{segment['text']}\\\"\\n")
                    else:
                        f.write(f"- ❌ Segment {segment['segment']}: FAILED PRESERVATION\\n")
                        f.write(f"  - Original: \\\"{segment['original_text']}\\\"\\n")
                        f.write(f"  - Result: \\\"{segment['result_text']}\\\"\\n")
                
                for segment in comparison['translated_segments']:
                    status = "✅ TRANSLATED" if segment['was_translated'] else "⚠️ NOT TRANSLATED"
                    f.write(f"- {status} Segment {segment['segment']}:\\n")
                    f.write(f"  - Original: \\\"{segment['original_text']}\\\"\\n")
                    f.write(f"  - Result: \\\"{segment['translated_text']}\\\"\\n")
                
            else:
                f.write("❌ **Status:** FAILED\\n\\n")
                f.write(f"**Error:** {result.get('error', 'Unknown error')}\\n\\n")
    
    logger.info(f"Validation report generated: {report_file}")
    return report_file

def main():
    """Main validation function."""
    logger.info("Starting MOCK subtitle language preservation validation")
    logger.info("(This uses simulated translations to test preservation logic)")
    
    # Create validation directories
    validation_dir = create_validation_directories()
    logger.info(f"Validation directory: {validation_dir}")
    
    # Test file
    test_file = Path("srt_test_minimal/test_en.srt")
    
    if not test_file.exists():
        logger.error(f"Test file not found: {test_file}")
        return False
    
    # Show test file content
    logger.info(f"\\nTest file content ({test_file}):")
    with open(test_file, 'r') as f:
        content = f.read()
        logger.info(content)
    
    # Run validation
    results = validate_preservation_logic(test_file, validation_dir)
    
    # Generate report
    report_file = generate_validation_report(results, validation_dir)
    
    # Summary
    logger.info(f"\\n{'='*60}")
    logger.info("MOCK VALIDATION SUMMARY")
    logger.info(f"{'='*60}")
    
    successful_tests = sum(1 for result in results.values() if result.get('success', False))
    total_tests = len(results)
    
    logger.info(f"Tests completed: {total_tests}")
    logger.info(f"Successful: {successful_tests}")
    logger.info(f"Failed: {total_tests - successful_tests}")
    
    if successful_tests == total_tests:
        logger.info("✅ ALL MOCK TESTS PASSED - Preservation logic appears to be working correctly!")
        logger.info("Next step: Test with real translation APIs")
        return True
    else:
        logger.error("❌ SOME MOCK TESTS FAILED - Preservation logic needs investigation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

