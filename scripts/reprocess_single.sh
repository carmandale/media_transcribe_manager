#!/bin/bash
# Single-interview validation command with JSON output
# Usage: ./scripts/reprocess_single.sh <file_id>

if [ -z "$1" ]; then
    echo "Usage: $0 <file_id>"
    echo "Example: $0 5c544e90-807b-4d2d-b75b-95aa739aed45"
    exit 1
fi

FILE_ID="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Use the run_with_env.sh wrapper to ensure environment is loaded
exec "$SCRIPT_DIR/run_with_env.sh" uv run python - "$FILE_ID" << 'EOF'
#!/usr/bin/env python3
"""Single interview validation with JSON output."""
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path.cwd()
sys.path.insert(0, str(project_root))

from scribe.srt_translator import translate_srt_file

def validate_single_interview(file_id: str):
    """Validate single interview reprocessing."""
    start_time = time.time()
    output_dir = Path("output") / file_id
    
    result = {
        "file_id": file_id,
        "timestamp": datetime.now().isoformat(),
        "status": "started",
        "timings": {},
        "results": {},
        "errors": [],
        "boundary_checks": {}
    }
    
    # Check if directory exists
    if not output_dir.exists():
        result["status"] = "error"
        result["errors"].append(f"Interview directory not found: {output_dir}")
        return result
    
    # Find original SRT
    orig_srt = output_dir / f"{file_id}.orig.srt"
    if not orig_srt.exists():
        orig_srt = output_dir / f"{file_id}.srt"
    
    if not orig_srt.exists():
        result["status"] = "error"
        result["errors"].append(f"No original SRT file found")
        return result
    
    # Count segments in original
    with open(orig_srt, 'r', encoding='utf-8') as f:
        orig_content = f.read()
        orig_segments = orig_content.count('\n\n')
        result["boundary_checks"]["original_segments"] = orig_segments
    
    # Process each language
    languages = ['en', 'de', 'he']
    for lang in languages:
        lang_start = time.time()
        output_srt = output_dir / f"{file_id}.{lang}.srt"
        
        try:
            success = translate_srt_file(
                str(orig_srt),
                str(output_srt),
                target_language=lang,
                preserve_original_when_matching=True,
                batch_size=100,
                estimate_only=False
            )
            
            lang_time = time.time() - lang_start
            
            # Boundary check: count segments in translated file
            if output_srt.exists():
                with open(output_srt, 'r', encoding='utf-8') as f:
                    translated_content = f.read()
                    translated_segments = translated_content.count('\n\n')
                    result["boundary_checks"][f"{lang}_segments"] = translated_segments
                    
                    # Check if segment counts match
                    if translated_segments != orig_segments:
                        result["errors"].append(
                            f"Segment count mismatch for {lang}: "
                            f"original={orig_segments}, translated={translated_segments}"
                        )
            
            result["results"][lang] = {
                "success": success,
                "duration_seconds": round(lang_time, 2),
                "output_file": str(output_srt),
                "file_size": output_srt.stat().st_size if output_srt.exists() else 0
            }
            result["timings"][lang] = round(lang_time, 2)
            
        except Exception as e:
            result["results"][lang] = {
                "success": False,
                "error": str(e),
                "duration_seconds": round(time.time() - lang_start, 2)
            }
            result["errors"].append(f"{lang}: {str(e)}")
    
    # Overall status
    total_time = time.time() - start_time
    result["timings"]["total"] = round(total_time, 2)
    
    # Check boundary alignment
    boundary_ok = all(
        result["boundary_checks"].get(f"{lang}_segments") == orig_segments
        for lang in languages
        if f"{lang}_segments" in result["boundary_checks"]
    )
    result["boundary_checks"]["aligned"] = boundary_ok
    
    if all(r.get("success", False) for r in result["results"].values()) and boundary_ok:
        result["status"] = "success"
    elif any(r.get("success", False) for r in result["results"].values()):
        result["status"] = "partial"
    else:
        result["status"] = "failed"
    
    return result

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Missing file_id argument"}))
        sys.exit(1)
    
    file_id = sys.argv[1]
    result = validate_single_interview(file_id)
    print(json.dumps(result, indent=2))
EOF