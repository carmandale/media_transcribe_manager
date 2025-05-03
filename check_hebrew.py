#!/usr/bin/env python3
from pathlib import Path
import re

files = list(Path('./output/translations/he').glob('*_he.txt'))
count = 0
total = min(100, len(files))

print(f"Checking {total} Hebrew translation files for placeholders...")

for file in files[:total]:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read(100)
            if '[HEBREW TRANSLATION]' in content:
                count += 1
    except Exception as e:
        print(f"Error reading {file}: {e}")

print(f'Files with Hebrew placeholder (sampled {total}): {count}')