#!/usr/bin/env python3
"""
evaluate_quality.py  –  MVP Quality-Gate CLI

Checks that every transcript / translation / subtitle exists, is non-empty,
and that translations are written in the expected language.

Exit codes:
 0  all pass
 1  missing / empty file(s)
 2  language mismatch(es)
 3  internal error
"""
from __future__ import annotations
import os, sys, json, argparse, logging, concurrent.futures
from datetime import datetime
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from db_manager import DatabaseManager
from file_manager import FileManager
from langdetect import detect, LangDetectException

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

# ---------------------------------------------------------------------------

THRESHOLD_BYTES = 10                         # TODO: load from yaml config
LANG_EQUIV = {                               # langdetect normalisation map
    "en": "en", "eng": "en",
    "de": "de", "deu": "de", "ger": "de",
    "he": "he", "heb": "he", "iw": "he",
}
TARGET_LANGS = ["en", "de", "he"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
log = logging.getLogger("qa-evaluator")

# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate media artefacts quality")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all",       action="store_true")
    g.add_argument("--file-id")
    p.add_argument("--limit",     type=int)
    p.add_argument("--json-out",  help="Write full JSON report to path")
    p.add_argument("--workers",   type=int, default=4, help="Parallel workers")
    p.add_argument("--size-min",  type=int, default=THRESHOLD_BYTES, help="Minimum bytes for non-empty check (default 10)")
    return p.parse_args()

# ---------------------------------------------------------------------------

def _normalise(lang: Optional[str]) -> Optional[str]:
    if not lang:
        return None
    return LANG_EQUIV.get(lang.lower(), lang.lower())

# ---------------------------------------------------------------------------

def evaluate_file(file_row: Dict[str, Any],
                  fm: FileManager) -> Dict[str, Any]:
    fid = file_row["file_id"]
    # record detected language for original subtitle summary
    det_lang = _normalise(file_row.get("detected_language"))
    checks: Dict[str, str] = {}
    failures: List[str] = []

    def _check_path(kind: str, path: Optional[str]) -> Optional[str]:
        if not path or not os.path.exists(path):
            checks[kind] = "missing"
            failures.append(f"{kind}_missing")
            return None
        if os.path.getsize(path) < THRESHOLD_BYTES:
            checks[kind] = "empty"
            failures.append(f"{kind}_empty")
            return None
        checks[kind] = "ok"
        return path

    _check_path("transcript", fm.get_transcript_path(fid))

    for lang in TARGET_LANGS:
        key = f"translation_{lang}"
        p = _check_path(key, fm.get_translation_path(fid, lang))
        if p:
            try:
                with open(p, encoding="utf-8") as fh:
                    txt = fh.read(65536)  # only first 64kB for lang-ID
                detected = _normalise(detect(txt))
            except (LangDetectException, UnicodeDecodeError):
                detected = None
            # skip language check on very short strings (< 50 bytes) and handle unknown
            if len(txt) >= 50:
                if detected not in LANG_EQUIV.values():
                    checks[key] = "lang_unknown"
                    failures.append(f"{key}_lang_unknown")
                elif detected != lang:
                    checks[key] = "lang_mismatch"
                    failures.append(f"{key}_lang_mismatch")

    for lang in TARGET_LANGS:
        _check_path(f"subtitle_{lang}", fm.get_subtitle_path(fid, lang))

    # determine status of original subtitle (in detected language)
    orig_status = None
    if det_lang:
        orig_status = checks.get(f"subtitle_{det_lang}")

    return {
        "file_id": fid,
        "detected_language": det_lang,
        "original_subtitle_status": orig_status,
        "checks": checks,
        "fail_reasons": failures,
        "evaluated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    # override byte-threshold from CLI
    global THRESHOLD_BYTES
    THRESHOLD_BYTES = args.size_min
    db = DatabaseManager(db_file="./media_tracking.db")
    fm = FileManager(db, {"output_dir": "./output"})

    if args.all:
        rows = db.get_files_by_status(['pending', 'in-progress', 'completed', 'failed'])
        if args.limit:
            rows = rows[:args.limit]
    else:
        row = db.get_file_by_id(args.file_id)
        if not row:
            log.error("File id %s not found", args.file_id)
            sys.exit(3)
        rows = [row]

    if not rows:
        log.info("Nothing to evaluate.")
        sys.exit(0)
    # attach progress bar for large batches
    rows_iter = tqdm(rows, desc="QA", unit="file") if len(rows) > 50 else rows

    results: List[Dict[str, Any]] = []
    exit_code = 0
    # process files sequentially to avoid DB threading issues
    for r in rows_iter:
        res = evaluate_file(r, fm)
        results.append(res)
        # determine exit code based on fail reasons
        if any("lang_mismatch" in x for x in res["fail_reasons"]):
            exit_code = max(exit_code, 2)
        elif res["fail_reasons"]:
            exit_code = max(exit_code, 1)
        # update overall status based on QA results
        db.update_status(
            res["file_id"],
            "failed" if res["fail_reasons"] else "completed"
        )

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        log.info("Wrote JSON report → %s", args.json_out)
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    # summary of pass/fail
    pass_ct = sum(1 for r in results if not r["fail_reasons"])
    fail_ct = len(results) - pass_ct
    log.info("QA finished → %d passed  %d failed", pass_ct, fail_ct)
    # summary of transcripts
    trans_ok = sum(1 for r in results if r["checks"].get("transcript") == "ok")
    trans_missing = sum(1 for r in results if r["checks"].get("transcript") == "missing")
    trans_empty = sum(1 for r in results if r["checks"].get("transcript") == "empty")
    log.info(f"Transcripts → ok:{trans_ok} missing:{trans_missing} empty:{trans_empty}")
    # summary of translations per language
    for lang in TARGET_LANGS:
        tr_ok = sum(1 for r in results if r["checks"].get(f"translation_{lang}") == "ok")
        tr_missing = sum(1 for r in results if r["checks"].get(f"translation_{lang}") == "missing")
        tr_empty = sum(1 for r in results if r["checks"].get(f"translation_{lang}") == "empty")
        tr_unknown = sum(1 for r in results if r["checks"].get(f"translation_{lang}") == "lang_unknown")
        tr_mismatch = sum(1 for r in results if r["checks"].get(f"translation_{lang}") == "lang_mismatch")
        log.info(f"Translations {lang} → ok:{tr_ok} missing:{tr_missing} empty:{tr_empty} unknown:{tr_unknown} mismatch:{tr_mismatch}")
    # summary of subtitles per language
    for lang in TARGET_LANGS:
        sub_ok = sum(1 for r in results if r["checks"].get(f"subtitle_{lang}") == "ok")
        sub_missing = sum(1 for r in results if r["checks"].get(f"subtitle_{lang}") == "missing")
        sub_empty = sum(1 for r in results if r["checks"].get(f"subtitle_{lang}") == "empty")
        log.info(f"Subtitles {lang} → ok:{sub_ok} missing:{sub_missing} empty:{sub_empty}")
    # summary of original subtitles by detected language
    for lang in TARGET_LANGS:
        lang_files = [r for r in results if r.get("detected_language") == lang]
        total = len(lang_files)
        orig_ok = sum(1 for r in lang_files if r.get("original_subtitle_status") == "ok")
        orig_missing = sum(1 for r in lang_files if r.get("original_subtitle_status") == "missing")
        orig_empty = sum(1 for r in lang_files if r.get("original_subtitle_status") == "empty")
        log.info(f"Original subtitles ({lang}) → total:{total} ok:{orig_ok} missing:{orig_missing} empty:{orig_empty}")
    # overall original subtitles summary
    orig_ok_total = sum(1 for r in results if r.get("original_subtitle_status") == "ok")
    orig_missing_total = sum(1 for r in results if r.get("original_subtitle_status") == "missing")
    orig_empty_total = sum(1 for r in results if r.get("original_subtitle_status") == "empty")
    log.info(f"Original subtitles overall → ok:{orig_ok_total} missing:{orig_missing_total} empty:{orig_empty_total}")
    # matrix of transcript vs original subtitle
    trans_ok_sub_ok = sum(1 for r in results if r["checks"].get("transcript")=="ok" and r.get("original_subtitle_status")=="ok")
    trans_ok_sub_missing = sum(1 for r in results if r["checks"].get("transcript")=="ok" and r.get("original_subtitle_status")=="missing")
    trans_missing_sub_ok = sum(1 for r in results if r["checks"].get("transcript")=="missing" and r.get("original_subtitle_status")=="ok")
    trans_missing_sub_missing = sum(1 for r in results if r["checks"].get("transcript")=="missing" and r.get("original_subtitle_status")=="missing")
    log.info(f"Transcript vs original subtitle → both_ok:{trans_ok_sub_ok} trans_ok_sub_missing:{trans_ok_sub_missing} trans_missing_sub_ok:{trans_missing_sub_ok} both_missing:{trans_missing_sub_missing}")
    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Internal error")
        sys.exit(3)
