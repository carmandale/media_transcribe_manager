Migration Update: Per-ID Folder Layout
======================================

What’s implemented:
  - Media (MP4/MP3) are symlinked into `output/<file_id>/`.
  - Original transcripts (`.txt` & `.txt.json`), translations (`.en.txt`, `.de.txt`, `.he.txt`), subtitles (`.en.srt`/`.vtt`), and original subtitles (`.orig.srt`/`.orig.vtt`) now live in each `output/<file_id>/`.
  - Translation-comparison artifacts (`*_raw_translations.json`, `*_evaluations.json`) are renamed to `<file_id>.raw_translations.json` & `<file_id>.evaluations.json` and moved into the per-ID folders.
  - Flat top-level MP4/MP3 symlinks (`output/<file_id>.<ext>`) have been removed.

Artifacts to clean up:
  - Old root-level directories (`audio/`, `transcripts/`, `translations/`, `subtitles/`, `translation_comparison/`) can be archived or deleted.
  - Any remaining top-level symlinks in `output/` should be removed post-validation.

Database updates:
  - `media_files.safe_filename` is updated to `<file_id>.<ext>`.
  - Update any other DB tables or code that reference transcript, subtitle, or translation paths to point at `output/<file_id>/…`.

Downstream tooling changes:
  - Change all workflows that glob or read flats (`translations/en/…`, `subtitles/he/…`) to use `output/<file_id>/…`.
  - Remove/disable legacy code that expects the old flat layout.
  - Update configuration (paths, glob patterns) in ingestion, indexing, UI, etc.

Validation & cleanup steps:
  1) Add a CI or sanity-check that for each `file_id` in the DB verifies:
     - `<file_id>.<mp4|mp3>` symlink
     - `<file_id>.txt` & `.txt.json`
     - `<file_id>.<lang>.txt` for each language
     - `<file_id>.<lang>.(srt|vtt)` and `<file_id>.orig.(srt|vtt)`
     - `<file_id>.raw_translations.json` & `.evaluations.json`
  2) Archive/delete old flat directories & symlinks.
  3) Spot-check sample `output/<file_id>/` folders manually.

## ✅ Migration Tasks
- [x] Migrate media (MP4/MP3) into `output/<file_id>/`
- [x] Move transcripts, translations, subtitles, original subtitles, and translation-comparison JSONs into per-ID folders
- [x] Clean up flat top-level symlinks
- [x] Remove legacy flat directories (`audio/`, `transcripts/`, `translations/`, `subtitles/`, `translation_comparison/`) using `--cleanup`

## 🛠 Validation Checklist
- [x] Write and run a sanity-check script to verify for each `file_id` that:
  - `<file_id>.<mp4|mp3>` symlink exists
  - `<file_id>.txt` and `.txt.json` exist
  - `<file_id>.<lang>.txt` exist for all languages
  - `<file_id>.<lang>.(srt|vtt)` and `<file_id>.orig.(srt|vtt)` exist
  - `<file_id>.raw_translations.json` and `<file_id>.evaluations.json` exist
- [ ] Spot-check 5–10 random `output/<file_id>/` folders manually
- [x] Archive or delete any remaining legacy flat directories & symlinks

## 🔄 Integration & CI
- [x] Update all downstream pipelines, code, and DB lookups to use `output/<file_id>/…` paths
- [x] Remove or disable legacy code expecting old flat layout
- [x] Add a CI step to run the sanity-check script on every pull/merge

## 📖 Documentation & Training
- [x] Update README and developer docs to describe the new per-ID folder structure
- [ ] Train the team on using the per-ID layout and retiring old processes

Once all of the above are checked off, the migration is fully complete and the old flat layout can be decommissioned.
## 🧹 Maintenance Utilities
- [x] Relocate root-level `.log` files into `logs/` (run `scripts/cleanup_root_logs.py`)
- [x] Clean up `docs/` folder, archiving old docs to `docs/_ARCHIVE/` (run `scripts/cleanup_docs.py`)
