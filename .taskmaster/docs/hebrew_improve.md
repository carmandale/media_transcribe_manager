Below is a practical play-book you can follow to push every Hebrew translation to ≥ 8.5/10, with ready-to-copy commands and Claude prompts.

---

## 1 · Find the Problem Files

```bash
# All Hebrew translations < 8.5 and > 0
sqlite3 media_tracking.db "
  SELECT file_id, score 
  FROM quality_evaluations
  WHERE language='he' 
    AND model!='sanity-check' 
    AND score < 8.5
" > low_hebrew.tsv        # tab-separated: file_id <tab> score
```

Tip: keep a running copy—`low_hebrew.tsv`—so you can re-query after each improvement round.

---

## 2 · Prepare Working Material

For each `FILE_ID` in `low_hebrew.tsv`:

```bash
# Paths
TRANS=output/$FILE_ID/$FILE_ID.txt
HE_TXT=output/$FILE_ID/$FILE_ID.he.txt

# Optional: split the texts into manageable 2-3 k character chunks
split -b 2000 -p '' "$TRANS"   chunks/en_
split -b 2000 -p '' "$HE_TXT"  chunks/he_
```

---

## 3 · Claude Prompt Templates

### 3.1 Full-file “Rewrite” Prompt  
Use when the entire translation is weak.

```text
SYSTEM:
You are a professional Hebrew linguist who preserves historical speech patterns faithfully.

USER:
Below is an English transcript followed by its current Hebrew translation. 
The translation scored <<SCORE>>/10 on a 4-part rubric:
1⃣ Content accuracy 40 %  
2⃣ Speech patterns 30 %  
3⃣ Cultural context 15 %  
4⃣ Reliability 15 %  

Please rewrite the Hebrew so that it would earn at least 9/10 on all criteria.
Keep speaker quirks and era-appropriate expressions.
Return ONLY the improved Hebrew text, no explanations.

--- ENGLISH TRANSCRIPT ---
{<<<paste EN text or chunk>>>}

--- CURRENT HEBREW TRANSLATION ---
{<<<paste HE text or chunk>>>}
```

### 3.2 Targeted “Patch” Prompt  
Use when you know specific problems (mis-facts, wrong idioms, missing cultural nuance).

```text
SYSTEM:
Expert historical Hebrew translator.

USER:
The excerpt below contains specific issues (listed after “ISSUES:”). 
Fix ONLY those, leaving everything else unchanged.  
Return the corrected Hebrew excerpt verbatim—no extra commentary.

--- HEBREW EXCERPT ---
{<<<paste problematic Hebrew excerpt>>>}

ISSUES:
1. Mis-translated year (“Forty-four” rendered as “ארבעים ושתיים”).
2. Missing Ottoman-era rank terminology.
```

---

## 4 · Replace the Translation

Save Claude’s output to `output/$FILE_ID/$FILE_ID.he.txt` (overwrite or append if chunked, then `cat` all the pieces).

---

## 5 · Re-evaluate

```bash
uv run python evaluate_hebrew_improved.py --limit 1 --model gpt-4.5-preview \
  --file $FILE_ID        # if you add --file support, otherwise just re-run on a batch
```

Verify the new score; it should appear in `quality_evaluations` with the latest timestamp.

---

## 6 · Iterate

1. Re-run the SQL query from Step 1.  
2. Continue until `low_hebrew.tsv` is empty.

---

## 7 · Batch Automation (Optional)

If you want to script everything:

1. **Export** low-scoring IDs to JSON.
2. **Loop** through IDs, auto-generate a Claude chat via API, save the response.
3. **Re-evaluate** each file immediately; stop when score ≥ 8.5.

A skeleton bash loop you can expand:

```bash
while read FILE SCORE; do
  # build prompt.json with jq or here-doc
  # call Claude API (anthropic.messages.create …)
  # write the returned Hebrew to $FILE.he.txt
  uv run python evaluate_hebrew_improved.py --limit 1 --model gpt-4.1
done < low_hebrew.tsv
```

---

## 8 · Final Validation

```bash
sqlite3 media_tracking.db "
  SELECT COUNT(*)
  FROM quality_evaluations
  WHERE language='he' AND model!='sanity-check' AND score < 8.5;
"   # should return 0
```

Generate a summary report:

```bash
sqlite3 media_tracking.db "
  SELECT AVG(score), MIN(score), MAX(score) 
  FROM quality_evaluations 
  WHERE language='he' AND model!='sanity-check';
"
```

Once every file is ≥ 8.5, archive the improved Hebrew translations and run a last `scribe_cli.py status --detailed` to confirm.