#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Quick test of Hebrew translation
test_text = "Also, äh, das war sehr interessant. Ähm, ich weiß nicht genau."

# Test with different providers
from core_modules.translation import TranslationManager
from core_modules.db_manager import DatabaseManager

db = DatabaseManager("media_tracking.db")
config = {'deepl': {'api_key': 'dummy'}, 'openai': {'api_key': 'dummy'}}
tm = TranslationManager(db, config)

# Check available providers
print("Available providers:", tm.available_providers)
print("Default provider:", tm.default_provider)

# Test Microsoft (which should handle Hebrew)
if 'microsoft' in tm.available_providers:
    print("\nTesting Microsoft provider for Hebrew...")
    result = tm.translate_text(test_text, 'he', 'de', provider='microsoft')
    if result:
        print("Result preview:", result[:100])
        has_hebrew = any('\u0590' <= c <= '\u05FF' for c in result)
        print("Contains Hebrew characters:", has_hebrew)