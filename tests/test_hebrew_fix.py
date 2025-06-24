#!/usr/bin/env python3
"""
Test to verify the Hebrew translation fix is working in the new clean structure.
This ensures Hebrew translations use Microsoft/OpenAI instead of DeepL.
"""

import os
import sys
from pathlib import Path

# Test if we can import from the new structure
try:
    from scribe.translate import translate_text, validate_hebrew
    print("✓ Successfully imported from new scribe module")
except ImportError as e:
    print(f"✗ Failed to import from scribe module: {e}")
    sys.exit(1)

def test_hebrew_routing():
    """Test that Hebrew translations work correctly"""
    print("\n=== Testing Hebrew Translation Routing ===")
    
    # Test text
    test_text = "Hello, this is a test of the Hebrew translation system."
    
    try:
        # Attempt Hebrew translation
        print(f"\nTranslating: '{test_text}'")
        hebrew_result = translate_text(test_text, target_language='he', source_language='en')
        
        # Validate it contains Hebrew characters
        if validate_hebrew(hebrew_result):
            print(f"✓ Hebrew translation successful: {hebrew_result[:50]}...")
            print("✓ Contains Hebrew characters")
        else:
            print(f"✗ Translation returned but no Hebrew characters found: {hebrew_result}")
            return False
            
        # Check it doesn't start with [HEBREW TRANSLATION]
        if hebrew_result.startswith('[HEBREW TRANSLATION]'):
            print("✗ Old broken format detected!")
            return False
        else:
            print("✓ Does not use old broken format")
            
        return True
        
    except Exception as e:
        print(f"✗ Hebrew translation failed: {e}")
        return False

def test_other_languages():
    """Test that other languages still work"""
    print("\n=== Testing Other Languages ===")
    
    test_text = "This is a simple test."
    
    # Test German
    try:
        german = translate_text(test_text, target_language='de', source_language='en')
        print(f"✓ German translation: {german}")
    except Exception as e:
        print(f"✗ German translation failed: {e}")
        return False
        
    return True

def check_api_keys():
    """Check if required API keys are configured"""
    print("\n=== Checking API Keys ===")
    
    keys = {
        'DEEPL_API_KEY': 'DeepL (for EN/DE)',
        'MS_TRANSLATOR_KEY': 'Microsoft (for Hebrew)',
        'OPENAI_API_KEY': 'OpenAI (backup for Hebrew)'
    }
    
    all_configured = True
    for key, service in keys.items():
        if os.getenv(key):
            print(f"✓ {service}: Configured")
        else:
            print(f"✗ {service}: Not configured")
            if key in ['MS_TRANSLATOR_KEY', 'OPENAI_API_KEY']:
                all_configured = False
    
    if not (os.getenv('MS_TRANSLATOR_KEY') or os.getenv('OPENAI_API_KEY')):
        print("\n⚠️  Warning: Neither Microsoft nor OpenAI keys configured for Hebrew!")
        
    return all_configured

def main():
    """Run all tests"""
    print("Hebrew Translation Fix Verification")
    print("=" * 50)
    
    # Check environment
    keys_ok = check_api_keys()
    
    if not keys_ok:
        print("\n⚠️  Some API keys missing. Tests may fail.")
    
    # Run tests
    hebrew_ok = test_hebrew_routing()
    other_ok = test_other_languages()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    if hebrew_ok and other_ok:
        print("✅ All tests passed! Hebrew fix is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())