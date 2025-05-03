#!/usr/bin/env python3
"""
Evaluate translation quality for English or German outputs.

Usage:
  python scripts/evaluate_translation_quality.py --uuid <FILE_UUID> --target <en|de> [--model gpt-4.1] [--max-chars 4000]
"""

from __future__ import annotations
import argparse
import json
import os
import pathlib
import re
import sys
from typing import Dict
from dotenv import load_dotenv
load_dotenv()

try:
    import openai  # type: ignore
except ImportError as exc:  # pragma: no cover
    sys.stderr.write("openai package not installed. Run `pip install openai`\n")
    raise exc

LANG_NAMES = {"en": "English", "de": "German", "he": "Hebrew"}

PROMPT_TEMPLATE = (
    "You are a professional translator and linguist. Evaluate the **{target_name}** "
    "candidate translation against the **{src_name}** source transcript.\n\n"
    "Give a holistic score from 0 (unintelligible) to 10 (publication quality). "
    "Focus on accuracy, fluency, proper names, idioms, and punctuation.\n\n"
    "Return a JSON object exactly in this form (no additional keys):\n"
    "{{\n  \"score_0_to_10\": <int>,\n  \"issues\": [\"issue 1\", ...],\n  \"overall_comment\": \"<concise summary>\"\n}}\n\n"
    "{src_name} source:\n<<<\n{src}\n>>>\n\n"
    "{target_name} candidate:\n<<<\n{cand}\n>>>"
)

def load_text(path: pathlib.Path, max_chars: int = 4000) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= max_chars:
        return text
    cut_at = text.rfind(" ", 0, max_chars)
    if cut_at == -1:
        cut_at = max_chars
    return text[:cut_at] + "\n[… truncated …]"

def build_paths(uuid: str, target: str) -> Dict[str, object]:
    """Return dict with source transcript path, candidate path, and source language."""
    trans_dir = pathlib.Path("./output/transcripts")
    cand_dir = pathlib.Path("./output/translations") / target

    cand_matches = list(cand_dir.glob(f"{uuid}*_{target}.txt"))
    if not cand_matches:
        raise FileNotFoundError(f"No {target} translation found for {uuid} in {cand_dir}")
    cand_path = cand_matches[0]

    transcripts = list(trans_dir.glob(f"{uuid}*.txt"))
    if not transcripts:
        raise FileNotFoundError(f"No source transcript found for {uuid}")
    src_path = transcripts[0]
    # default source transcript language opposite of target
    src_lang = "de" if target == "en" else "en"

    return {"src": src_path, "cand": cand_path, "src_lang": src_lang}

def evaluate(uuid: str, target: str, model: str = "gpt-4.1", max_chars: int = 4000) -> Dict:
    paths = build_paths(uuid, target)
    src_text = load_text(paths["src"], max_chars)
    cand_text = load_text(paths["cand"], max_chars)
    src_name = LANG_NAMES.get(paths["src_lang"], paths["src_lang"])
    tgt_name = LANG_NAMES.get(target, target)

    prompt = PROMPT_TEMPLATE.format(
        target_name=tgt_name, src_name=src_name, src=src_text, cand=cand_text
    )

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
            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
            return json.loads(cleaned)

    try:
        return _best_effort_parse(content)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if m:
            return _best_effort_parse(m.group())
        raise ValueError("Could not parse JSON from model response")

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate translation quality (en or de).")
    parser.add_argument("--uuid", required=True, help="File UUID to evaluate")
    parser.add_argument("--target", choices=["en", "de"], required=True, help="Target language code")
    parser.add_argument("--model", default="gpt-4.1", help="OpenAI model to use")
    parser.add_argument("--max-chars", type=int, default=4000, help="Max chars per segment")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY environment variable not set.")

    result = evaluate(args.uuid, args.target, args.model, args.max_chars)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
