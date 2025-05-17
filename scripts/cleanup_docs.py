#!/usr/bin/env python3
"""
Clean up the docs/ folder by moving all non-current documents into docs/_ARCHIVE/.
Only `MIGRATION_GUIDE.md` will remain at the top-level of docs/.
"""
import shutil
from pathlib import Path

def main():
    docs_root = Path(__file__).parent.parent / 'docs'
    archive_dir = docs_root / '_ARCHIVE'
    archive_dir.mkdir(exist_ok=True)
    
    for item in docs_root.iterdir():
        # Skip the archive directory and the current valid doc
        if item.name == '_ARCHIVE' or item.name == 'MIGRATION_GUIDE.md':
            continue
        dest = archive_dir / item.name
        print(f"Moving {item.name} -> docs/_ARCHIVE/{item.name}")
        shutil.move(str(item), str(dest))

if __name__ == '__main__':
    main()