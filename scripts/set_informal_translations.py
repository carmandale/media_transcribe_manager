#!/usr/bin/env python3
"""
Set Translation Formality to Informal

This script ensures translations use informal/less formal style
to better preserve authentic speech patterns in oral history interviews.

Usage:
    uv run python scripts/set_informal_translations.py
"""

import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

print("Translation Formality Configuration")
print("="*50)
print()
print("To use informal translation style (recommended for oral histories),")
print("update your media_processor.py command to include:")
print()
print("  --formality less")
print()
print("Example:")
print("  uv run python scripts/media_processor.py --file-id FILE_ID --translate-only en --formality less")
print()
print("Or for batch processing:")
print("  uv run python scripts/process_missing_translations.py --languages en,de,he --formality less")
print()
print("This will preserve natural speech patterns better than the default formal style.")
print()
print("Note: The translation prompts have been updated to preserve:")
print("- Hesitations (um, uh, ah)")
print("- Repeated words")
print("- Self-corrections")
print("- Natural speech patterns")
print()
print("This change is critical for historical accuracy!")