# Hebrew Translation Pipeline – Current Issues (2025-06-17)

This doc captures the errors encountered while re-processing 382 Hebrew "English-in-Hebrew" files so they can be fixed methodically.

---

## 1  ProgressTracker Parameter Mismatch

| File | Line | Problem | Quick Fix |
|------|------|---------|-----------|
| `scribe/pipeline.py` | ≈140 & 210 | Instantiated with `task=` but `ProgressTracker.__init__` expects parameter `description=` | Replace `task=` → `description=` (fixed ad-hoc during session) |

### Follow-up
* Write unit-test ensuring `process_transcriptions()` and `process_translations()` run without raising `TypeError`.
* Add mypy type-checking for constructor signatures.

---

## 2  KeyError: `file_path` in `process_translations()`

Stack trace excerpt:
```
result = PipelineResult(
    file_id=file_info['file_id'],
    file_path=Path(file_info['file_path'])  # ← KeyError
)
```
### Root Cause
`Database.get_pending_files('translation_he')` no longer returns a `file_path` column.

### Immediate Patch
```python
file_path = Path(file_info.get('file_path')
                 or self.config.output_dir / file_info['file_id'])
```

### Permanent Fix
1. Update `Database.get_pending_files()` to always include `file_path` for each stage.
2. Add regression test that calls `process_translations('he', limit=1)` with a mocked DB row.

---

## 3  OpenAI JSON Parsing Error – "Unterminated string"

Occurs when `translate_text()` manually `json.loads()` the already-parsed SDK response.

### Tasks
* Remove redundant `json.loads()`; use `response.choices[0].message.content` directly.
* Add defensive check for empty content and retry once.

---

## 4  Git Push Blocked – Secrets in `.cursor/mcp.json`

* Ensure `.cursor/mcp.json` is in `.gitignore`.
* Provide `mcp.sample.json` template (keys redacted) for new developers.

---

## 5  Database.update_status() Parameter Mismatch

Stack trace excerpt:
```
TypeError: Database.update_status() takes from 2 to 3 positional arguments but 4 were given
```

### Root Cause
`pipeline.py` calls `self.db.update_status(file_id, stage, status, error=str(e))` but the method signature changed.

### Immediate Fix
Check `Database.update_status()` signature and adjust calls in `pipeline.py` lines ~158 and ~198.

---

## 6  Microsoft Translator Rate Limiting (429 Errors)

**Error Pattern**:
```
ERROR:scribe.translate:Translation error with microsoft: 429 Client Error: Too Many Requests
ERROR:scribe.pipeline:he translation failed for {file_id}: 'NoneType' object is not iterable
```

### Root Cause
- Microsoft Translator API has strict rate limits
- 492 files failed due to 429 errors
- Translation provider returns `None` when rate limited, causing `'NoneType' object is not iterable`

### Immediate Fix
1. Switch Hebrew translation routing to OpenAI (no rate limits with API key)
2. Reset failed translations to pending status
3. Re-run translation process

### Code Change Needed
In `scribe/translate.py`, modify Hebrew routing to use OpenAI instead of Microsoft Translator.

---

## 7  OpenAI JSON Response Parsing Errors

**Error Pattern**:
```
ERROR:scribe.translate:OpenAI translation error: Unterminated string starting at: line 1 column 17 (char 16)
ERROR:scribe.pipeline:he translation failed for {file_id}: 'NoneType' object is not iterable
```

### Root Cause
- OpenAI sometimes returns malformed JSON despite `response_format={"type": "json_object"}`
- Strict JSON parsing fails, causing translation to return `None`
- This triggers the `'NoneType' object is not iterable` error in pipeline

### Immediate Fix
Added robust JSON parsing with fallback extraction and error handling in `_call_openai_api()` method.

---

### Next Steps Checklist
- [ ] Apply permanent fix for **Issue 2** in `pipeline.py` and add tests.
- [ ] Refactor `translate_text()` to address **Issue 3**.
- [ ] Update DB layer to guarantee `file_path` availability.
- [ ] Commit `.gitignore` update for cursor secrets.
- [ ] Run full translation batch again.

---

Maintainer: @dale • Last updated 2025-06-17 