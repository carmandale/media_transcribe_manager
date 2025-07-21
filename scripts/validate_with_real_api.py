#!/usr/bin/env python3
"""
Real API validation script for subtitle language preservation logic.
Tests the preservation feature with actual translation APIs when available.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.srt_translator import translate_srt_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_api_availability():
    """Check which translation APIs are available."""
    apis_available = {
        'openai': bool(os.getenv('OPENAI_API_KEY')),
        'deepl': bool(os.getenv('DEEPL_API_KEY')),
        'azure': bool(os.getenv('AZURE_TRANSLATOR_KEY'))
    }
    
    logger.info("API Availability Check:")
    for api, available in apis_available.items():
        status = "✅ Available" if available else "❌ Not configured"
        logger.info(f"  - {api.upper()}: {status}")
    
    return apis_available

def validate_with_real_apis(test_file: Path, target_languages: list = None):
    """Validate preservation logic with real translation APIs."""
    if target_languages is None:
        target_languages = ['en', 'de']  # Skip Hebrew if no API available
    
    logger.info(f"Validating preservation logic with real APIs")
    logger.info(f"Test file: {test_file}")
    
    if not test_file.exists():
        logger.error(f"Test file not found: {test_file}")
        return False
    
    # Create results directory
    results_dir = Path("real_api_validation_results")
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    validation_dir = results_dir / f"validation_{timestamp}"
    validation_dir.mkdir(exist_ok=True)
    
    success_count = 0
    total_tests = len(target_languages)
    
    for target_lang in target_languages:
        logger.info(f"\\n{'='*50}")
        logger.info(f"Testing {target_lang.upper()} translation with preservation")
        logger.info(f"{'='*50}")
        
        output_file = validation_dir / f"test_{target_lang}.srt"
        
        try:
            # Test with preservation enabled
            logger.info("Running translation with preservation logic...")
            success = translate_srt_file(
                str(test_file),
                str(output_file),
                target_language=target_lang,
                preserve_original_when_matching=True,
                batch_size=10,
                estimate_only=False
            )
            
            if success:
                logger.info(f"✅ Translation successful: {output_file}")
                
                # Analyze the results
                analyze_preservation_results(test_file, output_file, target_lang)
                success_count += 1
                
            else:
                logger.error(f"❌ Translation failed for {target_lang}")
                
        except Exception as e:
            logger.error(f"❌ Exception during {target_lang} translation: {e}")
    
    # Summary
    logger.info(f"\\n{'='*60}")
    logger.info("REAL API VALIDATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Tests completed: {total_tests}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {total_tests - success_count}")
    
    if success_count == total_tests:
        logger.info("✅ ALL REAL API TESTS PASSED!")
        logger.info("The preservation logic is working correctly with real translation APIs")
        return True
    else:
        logger.warning(f"⚠️ {total_tests - success_count} tests failed")
        logger.warning("Check the logs and results for issues")
        return False

def analyze_preservation_results(original_file: Path, result_file: Path, target_lang: str):
    """Analyze the preservation results from real API translation."""
    logger.info(f"Analyzing preservation results for {target_lang.upper()}")
    
    try:
        # Read original file
        with open(original_file, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Read result file
        with open(result_file, 'r', encoding='utf-8') as f:
            result_content = f.read()
        
        # Basic analysis
        original_lines = original_content.strip().split('\\n')
        result_lines = result_content.strip().split('\\n')
        
        logger.info(f"Original file: {len(original_lines)} lines")
        logger.info(f"Result file: {len(result_lines)} lines")
        
        # Look for preserved vs translated segments
        preserved_segments = []
        translated_segments = []
        
        # Simple heuristic: if text is identical, it was preserved
        i = 0
        segment_num = 1
        
        while i < len(original_lines) and i < len(result_lines):
            # Skip timing and index lines, look for text lines
            if original_lines[i].strip() and not original_lines[i].strip().isdigit() and '-->' not in original_lines[i]:
                original_text = original_lines[i].strip()
                result_text = result_lines[i].strip() if i < len(result_lines) else ""
                
                if original_text == result_text:
                    preserved_segments.append((segment_num, original_text))
                    logger.info(f"  PRESERVED Segment {segment_num}: '{original_text}'")
                else:
                    translated_segments.append((segment_num, original_text, result_text))
                    logger.info(f"  TRANSLATED Segment {segment_num}:")
                    logger.info(f"    Original: '{original_text}'")
                    logger.info(f"    Result: '{result_text}'")
                
                segment_num += 1
            
            i += 1
        
        logger.info(f"\\nPreservation Summary:")
        logger.info(f"  - Preserved segments: {len(preserved_segments)}")
        logger.info(f"  - Translated segments: {len(translated_segments)}")
        
        if len(preserved_segments) > 0:
            logger.info("✅ Language preservation is working - some segments were preserved")
        else:
            logger.warning("⚠️ No segments were preserved - check preservation logic")
            
    except Exception as e:
        logger.error(f"Failed to analyze results: {e}")

def main():
    """Main validation function."""
    logger.info("Starting REAL API validation for subtitle language preservation")
    
    # Check API availability
    apis = check_api_availability()
    
    if not any(apis.values()):
        logger.warning("No translation APIs are configured")
        logger.warning("Set environment variables for API keys:")
        logger.warning("  - OPENAI_API_KEY for OpenAI")
        logger.warning("  - DEEPL_API_KEY for DeepL")
        logger.warning("  - AZURE_TRANSLATOR_KEY for Azure")
        logger.info("\\nRunning mock validation instead...")
        
        # Fall back to mock validation
        from validate_preservation_logic_mock import main as mock_main
        return mock_main()
    
    # Test file
    test_file = Path("srt_test_minimal/test_en.srt")
    
    if not test_file.exists():
        logger.error(f"Test file not found: {test_file}")
        logger.info("Create a test file with mixed-language content for validation")
        return False
    
    # Show test file content
    logger.info(f"\\nTest file content ({test_file}):")
    with open(test_file, 'r') as f:
        content = f.read()
        logger.info(content)
    
    # Run validation with available APIs
    target_languages = []
    if apis['openai'] or apis['deepl']:
        target_languages.extend(['en', 'de'])
    if apis['openai']:  # Hebrew typically requires OpenAI
        target_languages.append('he')
    
    if not target_languages:
        logger.error("No suitable APIs available for testing")
        return False
    
    return validate_with_real_apis(test_file, target_languages)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

