# QA Checklist – Bryan Rigg Scribe Project

This checklist should be run (or automated) before any delivery or major milestone to ensure the transcription & translation workflow is healthy and complete.

---

## 1  File & Directory Integrity

| Item | Command / Script | Expected ✔︎ |
|------|------------------|-------------|
| Core output directories exist | `ls ./output/{audio,transcripts,subtitles,videos}` | All four paths are present |
| Source media present | Count of files in `_ORIGINAL_SOURCE` | > 0 |
| No empty files | `find ./output -type f -size 0` | *No output* |
| File names are UTF‑8 clean & ≤ 255 chars | Custom lint (see `scripts/one_off/verify_filenames.py`) | All pass |

---

## 2  Database ↔ Filesystem Consistency

| Check | Script | Notes |
|-------|--------|-------|
| Every `media_files.id` has a matching **source file** | `python reports/check_db_vs_source.py` | Paths stored in DB must exist |
| Every `media_files.id` has extracted **audio** (or is audio) | `python reports/check_audio_extracted.py` | Verifies file in `./output/audio` |
| Every "completed" entry in `processing_status` has **transcript** | `python reports/check_transcripts.py` | Looks in `./output/transcripts` |
| Errors in `errors` table are 0 | `sqlite3 ./media_tracking.db "SELECT COUNT(*) FROM errors;"` | Should return 0 |

---

## 3  Content Sanity

- Audio duration ⟷ transcript length ratio in reasonable range (e.g., 1 min audio ≈ 160‑200 words).  
  Script: `python reports/flag_suspicious_durations.py`
- Detect obviously wrong language via `langdetect` on first 1 000 chars of each transcript.  
  Script: `python reports/check_language.py --expected en` (or `de`, `he`, …)
- No excessive blank lines / placeholder text (`[INAUDIBLE]`, etc.).

---

## 4  Duplicate & Stray Files

| Check | Command | Expected |
|-------|---------|----------|
| Duplicate transcripts (same checksum) | `fdupes -r ./output/transcripts` | *No duplicates* |
| Duplicate subtitles | `fdupes -r ./output/subtitles` | *No duplicates* |
| Stray files not referenced in DB | `python reports/find_stray_outputs.py` | Outputs list must be empty |

---

## 5  Symbolic‑Link Verification

| Media Type | Destination Dir | Script |
|------------|-----------------|--------|
| Audio (MP3) | `./output/audio` | `python scripts/one_off/create_audio_symlinks.py --verify` |
| Video (MP4/MOV/…) | `./output/videos` | `python scripts/one_off/create_video_symlinks.py --verify` |

The scripts should report **Created: 0, Errors: 0** when run in verify‑only mode.

---

## 6  Subtitle ↔ Transcript Alignment

Run `python reports/check_sub_vs_transcript.py` which:
1. Parses each subtitle (WEBVTT/SRT) into plain text.
2. Compares against transcript with `difflib.SequenceMatcher`.
3. Flags pairs whose similarity ratio < 0.85.

Investigate and re‑transcribe any flagged items.

---

## 7  Reporting & Automation

After all checks pass, generate an HTML/CSV summary:

```bash
python generate_report.py --summary  # quick CLI summary
python generate_report.py --html out/report.html  # full detail
```

Archive the report alongside deliverables.

---

## 8  Running Everything at Once (optional)

A convenience runner can execute all of the above:

```bash
python qa_run_all.py --fix  # fixes simple issues automatically (symlinks, stray dirs)
python qa_run_all.py --dry-run  # report only
```

---

### When to Fail the QA Gate

Fail delivery if **any** of the following are true:

- Missing audio, transcript or subtitle for any `media_files.id` marked complete.
- Any error rows exist in the database.
- Symbolic links missing or broken.
- Subtitle/transcript alignment below threshold for any language.
- Duplicate or stray files are present.

All failures must be resolved or explicitly waived by project stakeholders.

---

_Last updated: 2025‑04‑20 05:36 CDT_
