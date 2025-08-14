#!/usr/bin/env python3
"""
Quick progress check for batch reprocessing.
Shows current status without continuous monitoring.
"""
import re
import json
import os
from pathlib import Path
from datetime import datetime

def get_progress_summary():
    """Get a one-time summary of progress."""
    log_file = Path("batch_normalized.log")
    
    if not log_file.exists():
        print("❌ No batch_normalized.log file found. Is the process running?")
        return
    
    # Parse the log
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Find all processed interviews
    interview_matches = re.findall(r'Processing interview (\d+)/(\d+): ([\w-]+)', content)
    
    # Completed interviews (two patterns: old and new)
    completed_old = re.findall(r'Successfully reprocessed subtitles for ([\w-]+)', content)
    completed_new = re.findall(r'✅ Successfully processed ([\w-]+)', content)
    completed_log_set = set(completed_old) | set(completed_new)

    # Also count on-disk markers as authoritative completed interviews across runs
    markers = list(Path("output").rglob('.preservation_fix_applied'))
    completed_markers = len(markers)
    
    # Identify the current run segment by the last occurrence of "Processing Batch 1/..."
    run_start_iter = list(re.finditer(r'Processing Batch 1/\d+ \(\d+ interviews\)', content))
    run_segment = content
    if run_start_iter:
        run_segment = content[run_start_iter[-1].start():]

    # Find current batch (from entire log for display)
    batch_matches = re.findall(r'Processing Batch (\d+)/(\d+)', content)

    # Compute total interviews planned for the current run by summing "(N interviews)" in the run segment
    run_batch_sizes = re.findall(r'Processing Batch (\d+)/(\d+) \((\d+) interviews\)', run_segment)
    total_planned_current_run = sum(int(n) for _, _, n in run_batch_sizes) if run_batch_sizes else None
    
    # Get current status (defaults from log parsing; will be overridden by status.json if present)
    current_interview = 0
    current_interview_in_batch = 0
    current_file = "unknown"
    if interview_matches:
        last = interview_matches[-1]
        current_interview_in_batch = int(last[0])
        current_file = last[2]

    # Prefer authoritative status from latest backup directory's status.json
    latest_status = None
    latest_batch_dir = None
    backups_root = Path("reprocessing_backups")
    if backups_root.exists():
        try:
            batch_dirs = sorted(backups_root.glob("batch_*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if batch_dirs:
                latest_batch_dir = batch_dirs[0]
                status_path = latest_batch_dir / "status.json"
                if status_path.exists():
                    with open(status_path, 'r', encoding='utf-8') as sf:
                        latest_status = json.load(sf)
        except Exception:
            latest_status = None
    
    current_batch = "unknown"
    total_batches = "unknown"
    if batch_matches:
        current_batch, total_batches = batch_matches[-1]
    
    # Find latest language being processed
    lang_matches = re.findall(r'Reprocessing .+ for (\w+)', content)
    current_lang = lang_matches[-1] if lang_matches else "unknown"
    
    # Display summary
    print("="*70)
    print("SUBTITLE REPROCESSING STATUS")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Progress bar (prefer status.json; fallback to prior heuristic)
    bar_length = 50
    if latest_status and isinstance(latest_status, dict):
        processed = int(latest_status.get("processed", 0))
        total = int(latest_status.get("total", 0))
        percent = (processed / total) * 100 if total else 0.0
        filled = int(bar_length * processed / total) if total else 0
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"Progress (current run): [{bar}] {percent:.1f}%")
        print(f"Interviews in current run: {processed}/{total}")
        eta_human = latest_status.get("eta_human")
        rate = latest_status.get("processing_rate")
        if eta_human:
            print(f"  • ETA (current batch): {eta_human}")
        if rate:
            print(f"  • Rate: {rate}")
        # Override current file if available
        current_file = latest_status.get("current_file_id", current_file)
        # Also prefer batch numbers if present
        current_batch = 'unknown'
        total_batches = 'unknown'
        if 'progress_percent' in latest_status:
            # keep batch info from earlier regex if available
            pass
    else:
        total = total_planned_current_run if total_planned_current_run else 0
        if total:
            percent = (current_interview_in_batch / total) * 100
            filled = int(bar_length * current_interview_in_batch / total)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"Progress (current run, by batch index): [{bar}] {percent:.1f}%")
            print(f"Interviews in current run: {current_interview_in_batch}/{total}")
        else:
            print("Progress: current run total unknown (no plan line found)")

    # Overall progress bar (across runs) using on-disk markers out of known total
    TOTAL_INTERVIEWS = 728  # overall target size
    overall_total = TOTAL_INTERVIEWS
    overall_done = min(completed_markers, overall_total)
    overall_percent = (overall_done / overall_total) * 100 if overall_total else 0
    bar_length = 50
    overall_filled = int(bar_length * overall_done / overall_total) if overall_total else 0
    overall_bar = '█' * overall_filled + '░' * (bar_length - overall_filled)
    print()
    print(f"Overall Progress (all runs): [{overall_bar}] {overall_percent:.1f}%")
    print(f"Overall Interviews: {overall_done}/{overall_total}")
    print()
    
    print(f"Current Interview:")
    print(f"  • Number: {current_interview}")
    print(f"  • File ID: {current_file}")
    print(f"  • Language: {current_lang}")
    print(f"  • Batch: {current_batch}/{total_batches}")
    print()
    
    print(f"Statistics:")
    print(f"  • Completed (on-disk markers): {completed_markers}")
    print(f"  • Completed (log this run): {len(completed_log_set)}")
    if latest_status and isinstance(latest_status, dict) and int(latest_status.get("total", 0)):
        rem = int(latest_status.get("total", 0)) - int(latest_status.get("processed", 0))
        print(f"  • Remaining (current run): {max(rem, 0)}")
    elif total:
        print(f"  • Remaining (current run est): {max(total - current_interview_in_batch, 0)}")
    
    # Estimate time
    if current_interview > 0:
        # Rough estimate: ~5 minutes per interview
        remaining_minutes = (total - current_interview) * 5
        hours = remaining_minutes // 60
        minutes = remaining_minutes % 60
        print(f"  • Estimated time remaining: {hours}h {minutes}m")
    
    print()
    print("-"*70)
    print("For continuous monitoring, run: python monitor_progress.py")
    print("To view detailed log: tail -f batch_normalized.log")

if __name__ == "__main__":
    get_progress_summary()