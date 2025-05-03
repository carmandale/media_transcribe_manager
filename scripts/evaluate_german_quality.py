#!/usr/bin/env python3
"""
Evaluate German translation quality via OpenAI GPT-4

Given a file UUID, this script loads the original transcript and German candidate translation
from the standard output directories and asks an OpenAI model to rate the German quality.

Usage
-----
python scripts/evaluate_german_quality.py --uuid <FILE_UUID> [--model gpt-4.1]

Returned JSON example
---------------------
{
  "score_0_to_10": 8,
  "issues": ["Minor grammatical error"],
  "overall_comment": "Gute Übersetzung, kleine Anpassungen bei der Satzstruktur nötig."
}
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
from typing import Dict

try:
    import openai  # type: ignore
except ImportError as exc:
    sys.stderr.write("openai package not installed. Run `pip install openai`\n")
    raise exc

# ---------------------------------------------------------------------------
# Prompt Template
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = (
    "You are a professional German linguist and translator. "
    "Evaluate the **German** candidate translation against the original transcript.\n\n"
    "Give a holistic score from 0 (unintelligible) to 10 (publication quality). "
    "Focus on accuracy, grammar, idiomatic usage, and terminology.\n\n"
    "Return a JSON object exactly in this form (no additional keys):\n"
    "{\n  \"score_0_to_10\": <int>,\n  \"issues\": [\"issue 1\", ...],\n  \"overall_comment\": \"<concise summary>\"\n}\n\n"
    "Original transcript:\n<<<\n{src}\n>>>\n\n"
    "German candidate translation:\n<<<\n{de}\n>>>"
)

def load_text(path: pathlib.Path, max_chars: int = 4000) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= max_chars:
        return text
    cut_at = text.rfind(" ", 0, max_chars)
    if cut_at == -1:
        cut_at = max_chars
    return text[:cut_at] + "\n[… truncated …]"


def build_paths(uuid: str) -> Dict[str, pathlib.Path]:
    base_trans = pathlib.Path("./output/transcripts")
    base_transl = pathlib.Path("./output/translations") / "de"
    paths: Dict[str, pathlib.Path] = {}

    # Original transcript
    trans_matches = list(base_trans.glob(f"{uuid}*.txt"))
    if not trans_matches:
        raise FileNotFoundError(f"No transcript file found for {uuid}")
    paths["src"] = trans_matches[0]

    # German translation
    transl_matches = list(base_transl.glob(f"{uuid}*_{'de'}.txt"))
    if not transl_matches:
        raise FileNotFoundError(f"No German translation file found for {uuid}")
    paths["de"] = transl_matches[0]

    return paths


def evaluate(uuid: str, model: str = "gpt-4.1") -> Dict:
    paths = build_paths(uuid)
    prompt = PROMPT_TEMPLATE.format(
        src=load_text(paths["src"]),
        de=load_text(paths["de"]),
    )
    # OpenAI call
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI()
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = completion.choices[0].message.content
    else:
        completion = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = completion.choices[0].message.content

    def _best_effort_parse(txt: str):
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            cleaned = txt.strip().lstrip("` ").rstrip("` ")
            cleaned = re.sub(r',\s*([}\]])', r"\1", cleaned)
            return json.loads(cleaned)

    try:
        return _best_effort_parse(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            return _best_effort_parse(m.group())
        raise ValueError("Could not parse JSON from model response")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate German translation quality.")
    parser.add_argument("--uuid", required=True, help="File UUID to evaluate")
    parser.add_argument("--model", default="gpt-4.1", help="OpenAI model (default: gpt-4.1)")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY environment variable not set.")

    result = evaluate(args.uuid, args.model)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
