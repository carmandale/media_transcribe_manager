#!/usr/bin/env python3
"""Generate initial Hebrew glossary from random German and English source transcripts.

The script performs:
1. Connect to the local SQLite `media_tracking.db`.
2. Randomly sample N German and M English files whose transcriptions are completed.
3. Load their transcript JSON files from `output/transcripts/`.
4. Extract candidate glossary terms (proper‑noun like phrases, military ranks, etc.)
5. Ask GPT‑4 to produce a two‑column CSV mapping to high‑quality Hebrew equivalents.
6. Write the CSV to `docs/glossaries/he_seed.csv` (directory will be created).

Usage (defaults to 10 + 10):
```
python scripts/generate_glossary.py --de 10 --en 10 --max-terms 200
```
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Set

# OpenAI import handled lazily so that the script still works when the package is absent.
try:
    import openai  # type: ignore
except ImportError:  # pragma: no cover
    openai = None  # type: ignore

DB_PATH = Path("media_tracking.db")
TRANSCRIPTS_DIR = Path("output/transcripts")
OUTPUT_CSV = Path("docs/glossaries/he_seed.csv")

CAP_SEQ_RE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*", re.UNICODE)


def sample_file_ids(conn: sqlite3.Connection, lang_codes: Iterable[str], limit: int) -> List[str]:
    placeholders = ",".join("?" for _ in lang_codes)
    sql = f"""
        SELECT m.file_id FROM media_files m
        JOIN processing_status p ON m.file_id = p.file_id
        WHERE detected_language IN ({placeholders})
          AND p.transcription_status = 'completed'
        ORDER BY RANDOM() LIMIT ?
    """
    cur = conn.execute(sql, [*lang_codes, limit])
    return [row[0] for row in cur.fetchall()]


def iter_transcript_texts(uuid: str) -> Iterable[str]:
    """Yield paragraphs from the transcript file for the given UUID."""
    files = list(TRANSCRIPTS_DIR.glob(f"{uuid}*.json"))
    if not files:
        # fallback to plain txt
        files = list(TRANSCRIPTS_DIR.glob(f"{uuid}*.txt"))
    if not files:
        return []
    path = files[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    # Common schema: list of segments/paragraphs with 'text'
    if isinstance(data, list):
        for seg in data:
            txt = seg.get("text") or seg.get("content") or ""
            if isinstance(txt, str):
                yield txt
    elif isinstance(data, dict):
        # Build paragraph from words list if present
        if "words" in data and isinstance(data["words"], list):
            joined = " ".join(w.get("text", "") for w in data["words"] if isinstance(w, dict))
            if joined:
                yield joined
        # Use 'paragraphs' field if exists
        for seg in data.get("paragraphs", []):
            txt = seg.get("text") or seg.get("content") or ""
            if isinstance(txt, str):
                yield txt
        # Fallback: segments list
        for seg in data.get("segments", []):
            txt = seg.get("text") or ""
            if isinstance(txt, str):
                yield txt


def extract_terms(paragraphs: Iterable[str]) -> Set[str]:
    terms: Set[str] = set()
    for para in paragraphs:
        for match in CAP_SEQ_RE.finditer(para):
            phrase = match.group(0).strip()
            if len(phrase) < 3:
                continue
            if phrase.lower() in {"the", "and", "but", "und", "der", "die", "das"}:
                continue
            terms.add(phrase)
    return terms


def ask_gpt_for_hebrew(terms: List[str]) -> List[tuple[str, str]]:
    if not openai:
        raise RuntimeError("openai package not installed. Run `pip install openai`.")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    prompt = (
        "You are a professional Hebrew translator. "
        "Provide a CSV list mapping each given term to its best Hebrew equivalent. "
        "If the term is a proper name, transliterate. Preserve acronyms. "
        "Return only lines in the format <source>,<hebrew> with no extra commentary.\n\n"  # noqa: E501
        + "\n".join(terms)
    )

    # Use chat completion (OpenAI SDK >=1.0 style if available)
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI()
        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = completion.choices[0].message.content
    else:
        completion = openai.ChatCompletion.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = completion["choices"][0]["message"]["content"]

    pairs: List[tuple[str, str]] = []
    for line in content.splitlines():
        if "," in line:
            src, heb = line.split(",", 1)
            pairs.append((src.strip(), heb.strip()))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate initial Hebrew glossary.")
    parser.add_argument("--de", type=int, default=10, help="Number of German files to sample (default 10)")
    parser.add_argument("--en", type=int, default=10, help="Number of English files to sample (default 10)")
    parser.add_argument("--max-terms", type=int, default=200, help="Maximum glossary terms (default 200)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)

    german_ids = sample_file_ids(conn, ["de", "ger", "deu"], args.de)
    english_ids = sample_file_ids(conn, ["en", "eng"], args.en)
    uuids = german_ids + english_ids

    print(f"Collected {len(uuids)} transcripts (DE {len(german_ids)}, EN {len(english_ids)}).")

    all_terms: Counter[str] = Counter()
    for uid in uuids:
        paras = iter_transcript_texts(uid)
        terms = extract_terms(paras)
        all_terms.update(terms)

    # Take the most common terms up to max-terms
    top_terms = [t for t, _ in all_terms.most_common(args.max_terms)]
    print(f"Extracted {len(top_terms)} candidate terms.")

    if not top_terms:
        print("No terms found. Exiting.")
        return

    print("Querying GPT‑4.1 for Hebrew equivalents …")
    pairs = ask_gpt_for_hebrew(top_terms)
    print(f"Received {len(pairs)} glossary pairs.")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8") as f:
        for src, heb in pairs:
            f.write(f"{src},{heb}\n")
    print(f"Glossary written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
