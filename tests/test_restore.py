#!/usr/bin/env python3
"""
Test script to verify backup can be restored.
"""

import tempfile
import shutil
import tarfile
import json
from pathlib import Path

def test_restore(backup_dir: Path):
    """Test restoring from a backup."""
    print(f"Testing restore from: {backup_dir}")
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 1. Check manifest
        manifest_path = backup_dir / "manifest.json"
        if not manifest_path.exists():
            print("❌ Manifest not found")
            return False
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        print(f"✓ Manifest loaded: {manifest['backup_timestamp']}")
        print(f"  Hebrew issues: {manifest['validation_status']['total_hebrew_issues']}")
        
        # 2. Check database
        db_path = backup_dir / "media_tracking.db"
        if not db_path.exists():
            print("❌ Database backup not found")
            return False
        
        print(f"✓ Database found: {db_path.stat().st_size:,} bytes")
        
        # 3. Check archive
        archive_path = backup_dir / "output.tar.gz"
        if not archive_path.exists():
            print("❌ Archive not found")
            return False
        
        print(f"✓ Archive found: {archive_path.stat().st_size:,} bytes")
        
        # 4. Test extraction
        print("  Testing archive extraction...")
        import subprocess
        result = subprocess.run(
            ["tar", "-tzf", str(archive_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"❌ Archive test failed: {result.stderr}")
            return False
        
        file_count = len(result.stdout.strip().split('\n'))
        print(f"✓ Archive contains {file_count} entries")
        
        print("\n✅ Backup verification passed!")
        print(f"To restore this backup:")
        print(f"  1. cp {db_path} ./media_tracking.db")
        print(f"  2. tar -xzf {archive_path}")
        
        return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        # Use latest backup
        backups_dir = Path("backups")
        if backups_dir.exists():
            backups = sorted(backups_dir.iterdir(), key=lambda x: x.stat().st_mtime)
            if backups:
                backup_dir = backups[-1]
            else:
                print("No backups found")
                sys.exit(1)
        else:
            print("Backups directory not found")
            sys.exit(1)
    else:
        backup_dir = Path(sys.argv[1])
    
    if not backup_dir.exists():
        print(f"Backup directory not found: {backup_dir}")
        sys.exit(1)
    
    success = test_restore(backup_dir)
    sys.exit(0 if success else 1)