# Pipeline Verification Checklist

## 1. Code Sanity
- [ ] Confirm `scripts/one_off/process_transcriptions.py`:
  - outputs `output/transcripts/*.txt`
  - outputs `output/subtitles/orig/*.srt`
- [ ] Confirm `process_translations.py --file-id <FILE_ID>` produces:
  - `output/translations/de/*.txt` + `output/subtitles/de/*.srt`
  - `output/translations/en/*.txt` + `output/subtitles/en/*.srt`
  - `output/translations/he/*.txt` + `output/subtitles/he/*.srt`

## 2. Sample Selection
- [x] Query DB for 5 `file_id` where all `translation_*_status = 'not_started'`
- Selected IDs:
  - d1cba9b9-2511-4549-aa34-3eb20a90e302
  - 262f31a8-e7e5-4405-bec4-23c78ac224cb
  - d1815fea-69b2-4f63-9c7f-af0314eba863
  - 7276da3b-b59b-42fb-afd8-5c67b20daf87
  - 9c76c735-eccc-4f9a-96e3-f61b1258524a

## 3. Pipeline Execution (per sample `<FILE_ID>`)
- [x] Transcription & orig subtitles:
  ```bash
  python3 scripts/one_off/process_transcriptions.py --file-id <FILE_ID>
  ```
- [x] Translation & subtitles:
  ```bash
  python3 process_translations.py --file-id <FILE_ID>
  ```

## 4. Quality Evaluation (per sample `<FILE_ID>`)
- [x] English:
  ```bash
  python3 scripts/evaluate_translation_quality.py --uuid <FILE_ID> --target en
  ```
- [x] German:
  ```bash
  python3 scripts/evaluate_translation_quality.py --uuid <FILE_ID> --target de
  ```
- [x] Hebrew:
  ```bash
  python3 scripts/evaluate_hebrew_quality.py --uuid <FILE_ID> --model gpt-4.1
  ```

## 5. Final Verification
- [ ] Check for each `<FILE_ID>`:
  - raw transcript + `orig.srt`
  - German translation + `.srt`
  - English translation + `.srt`
  - Hebrew translation + `.srt`
- [ ] Ensure all evaluation scores ≥ 8.5
