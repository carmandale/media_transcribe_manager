# Reporting Guide

This guide shows how to generate summary reports for the transcription and translation pipeline, including existence/quality checks and GPT-4 evaluations.

## 1. Existence & Language-ID Checks

### CLI Command
```bash
python evaluate_quality.py --all --json-out=report.json
```

- **`--all`**: process every file in `processing_status`.
- **`--json-out`**: save full per-file JSON to `report.json`.

### JSON Schema (`report.json`)
```json
[
  {
    "file_id": "<uuid>",
    "checks": {
      "transcript": "ok|missing|empty",
      "translation_en": "ok|missing|empty|lang_mismatch",
      "subtitle_he": "ok|missing|empty",
      ...
    },
    "fail_reasons": ["translation_en_missing", ...],
    "evaluated_at": "2025-05-XXTXX:XX:XXZ"
  },
  ...
]
```

### Quick Summary (built-in)
After running, the CLI logs counts:
- **QA finished →** `N passed  M failed`
- **Transcripts →** ok:…, missing:…, empty:…
- **Translations en →** ok:…, missing:…, empty:…, mismatch:…
- **Subtitles he →** ok:…, missing:…, empty:…

You can also parse `report.json` with `jq`:  
```bash
jq '[.[] | select(.fail_reasons|length==0)] | length' report.json  # passed
jq '[.[] | select(.fail_reasons|length>0)] | length' report.json  # failed
```

## 2. GPT-4 Semantic QA

### CLI Command
```bash
python batch_evaluate_quality.py \
  --db media_tracking.db \
  --languages he,en,de \
  --threshold 8.5 \
  --limit 100
```

- **`--languages`**: comma list (default: `he`).
- **`--threshold`**: minimum passing score.

### Database Table: `quality_evaluations`
| Column        | Type    | Description                              |
|---------------|---------|------------------------------------------|
| `eval_id`     | INTEGER | PK                                       |
| `file_id`     | TEXT    | Media UUID                               |
| `language`    | TEXT    | `en` &#124; `de` &#124; `he`             |
| `model`       | TEXT    | e.g. `gpt-4.1`                           |
| `score`       | REAL    | 0.0–10.0                                 |
| `issues`      | TEXT    | JSON array of issues                     |
| `comment`     | TEXT    | Overall comment                          |
| `evaluated_at`| TIMESTAMP | When evaluation ran                     |

### Sample Queries
```sql
-- Count evaluations by language
SELECT language, COUNT(*) FROM quality_evaluations GROUP BY language;

-- Average score per language
SELECT language, ROUND(AVG(score),2) AS avg_score
FROM quality_evaluations
GROUP BY language;

-- Failures below threshold
SELECT file_id, language, score
FROM quality_evaluations
WHERE score < 8.5;
```

## 3. Processing Status Overview

Table: `processing_status` (in `media_tracking.db`)
- **`file_id`**, **`transcription_status`**, **`translation_en_status`**, **...**

### Sample Queries
```sql
-- Total files by transcription state
SELECT transcription_status, COUNT(*)
FROM processing_status
GROUP BY transcription_status;

-- Translation ready for QA
SELECT COUNT(*)
FROM processing_status
WHERE transcription_status='completed'
  AND translation_he_status='completed';
```

## 4. Automating Reports
- Integrate above SQL in a script (e.g. `reporting.py`) to export CSV/JSON.
- Schedule via cron or CI pipeline.

## 5. Updating Docs
- This file `docs/reporting.md` is the single source for reporting steps.
- Reference it in README and CI docs.  

---
*Last updated: 2025-05-03T07:30Z*
