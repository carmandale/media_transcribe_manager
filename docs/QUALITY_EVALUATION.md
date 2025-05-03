# Quality Evaluation Implementation

This document summarizes the recent additions for semantic QA using GPT-4 in the Scribe project.

## 1. DB Schema Changes

**Table**: `quality_evaluations`

```sql
CREATE TABLE IF NOT EXISTS quality_evaluations (
  eval_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id        TEXT NOT NULL,
  language       TEXT NOT NULL,
  model          TEXT NOT NULL,
  score          REAL NOT NULL,
  issues         TEXT,
  comment        TEXT,
  evaluated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(file_id) REFERENCES media_files(file_id)
);
```

## 2. DB Manager Extensions

- **add_quality_evaluation(file_id, language, model, score, issues, comment)**
  Logs a GPT evaluation result.

- **update_translation_status(file_id, language, status)**
  Updates `translation_{lang}_status` in `processing_status` (e.g. `qa_completed` or `qa_failed`).

## 3. GPT Evaluator Scripts

- **scripts/evaluate_hebrew_quality.py**
  Rates Hebrew (`he`) translations using English source + German reference.

- **scripts/evaluate_english_quality.py**
  Rates English (`en`) translations against the original transcript.

- **scripts/evaluate_german_quality.py**
  Rates German (`de`) translations against the original transcript.

### Common Flow
1. Load transcript (`./output/transcripts`) and translation (`./output/translations/{lang}`).
2. Truncate to ~4000 chars (`load_text`).
3. Prompt GPT-4 with a custom template.
4. Parse JSON `{ "score_0_to_10":…, "issues":[…], "overall_comment":… }`.

## 4. Batch Runner

**scripts/batch_evaluate_quality.py**

- Iterates over files with `translation_{lang}_status='completed'` **and** `transcription_status='completed'`.
- Calls each language evaluator.
- Inserts into `quality_evaluations` via `add_quality_evaluation`.
- Updates `translation_{lang}_status` to `qa_completed` or `qa_failed` (threshold default 8.5).

**Usage:**
```bash
python batch_evaluate_quality.py --db media_tracking.db --languages he,en,de --threshold 8.5
```

## 5. Integration Options

1. **Embed in `evaluate_quality.py`** (`--gpt-eval` flag)
   - Single CLI for all QA (existence, size, lang-ID, GPT).
   - **Pros:** No additional script.
   - **Cons:** Slower, mixed concerns.

2. **Standalone Batch Script**
   - Keeps core I/O checks separate from semantic QA.
   - **Pros:** Decoupled, schedule independently.
   - **Cons:** Extra artifact to maintain.

> **Difference:**
> - *Option 1* (second suggestion) integrates GPT scoring directly into the existing `evaluate_quality.py` command under a new flag, providing a unified experience but adding latency and complexity to the core tool.
> - *Option 2* (third suggestion) uses a separate batch script (`batch_evaluate_quality.py`), keeping the core CLI lean and letting you run semantic QA as its own job.

## 6. Next Steps

- Implement and test `evaluate_english_quality.py` and `evaluate_german_quality.py`.
- Integrate EN/DE evaluators into the batch runner.
- Schedule regular QA runs (e.g. CI job, cron).
