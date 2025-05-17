<!-- docs/MIGRATION_GUIDE.md -->
# Migration Guide: Transition to Per-ID Folder Layout

This guide explains how to migrate from the flat output layout to the new per-`file_id` folder structure, and how to update downstream code and processes accordingly.

## 1. Overview of New Layout
All artifacts for a given media file now live under `output/<file_id>/`:

```
output/
├── <file_id>/
│   ├── <file_id>.<mp4|mp3>           # Media symlink
│   ├── <file_id>.txt                # Original transcript
│   ├── <file_id>.txt.json           # Transcript metadata
│   ├── <file_id>.en.txt             # English translation
│   ├── <file_id>.de.txt             # German translation
│   ├── <file_id>.he.txt             # Hebrew translation
│   ├── <file_id>.en.srt             # English subtitles (or .vtt)
│   ├── <file_id>.de.srt             # German subtitles (or .vtt)
│   ├── <file_id>.he.srt             # Hebrew subtitles (or .vtt)
│   ├── <file_id>.orig.srt           # Original subtitles
│   ├── <file_id>.raw_translations.json
│   └── <file_id>.evaluations.json
└── ...
```

## 2. Migration Steps
1. **Dry run** (preview only):
   ```bash
   ./scripts/migrate_output.py --db media_tracking.db --output output --dry-run
   ```
2. **Perform migration**:
   ```bash
   ./scripts/migrate_output.py --db media_tracking.db --output output
   ```
3. **Cleanup legacy** (remove flat dirs & symlinks):
   ```bash
   ./scripts/migrate_output.py --db media_tracking.db --output output --cleanup
   ```

## 3. Validation
Run the validator to ensure every per-ID folder is complete:
```bash
python scripts/validate_output.py
```
It will exit with code `0` if no issues are found.

## 4. Update Downstream Code
- **Path construction**: Replace old flat paths:
  ```python
  # OLD
  Path('output/transcripts') / f"{base_name}.txt"

  # NEW
  root = Path('output')
  d = root / file_id
  transcript = d / f"{file_id}.txt"
  ```
- **Media access**: Use pattern matching or FileManager helper:
  ```python
  media = next(
      (d / f"{file_id}{ext}" for ext in ['.mp4','.mp3'] if (d / f"{file_id}{ext}").exists()),
      None
  )
  ```
- **Translations & subtitles**: Similar patterns under same folder.

## 5. Continuous Integration
The workflow `.github/workflows/validate_output.yml` runs the validator on every push/PR to catch regressions.

## 6. Decommission Old Layout
Once validation and integration updates are complete, archive or delete the old directories:
```
rm -rf output/audio output/transcripts output/translations output/subtitles output/translation_comparison
```

## 7. Team Onboarding
Share this guide and walk the team through:
- Running the migration script
- Validating and troubleshooting missing artifacts
- Updating scripts and code to consume `output/<file_id>/…`
- Verifying CI checks on PRs

For questions or support, contact the maintainers.