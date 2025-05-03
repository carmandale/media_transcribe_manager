#!/usr/bin/env python3
"""Evaluate Hebrew translation quality via OpenAI GPT-4

Given a file UUID, this script loads the English source, German reference,
and Hebrew candidate translations from the standard output directories and
asks an OpenAI model to rate the Hebrew quality.

Usage
-----
python scripts/evaluate_hebrew_quality.py --uuid <FILE_UUID> [--model gpt-4.1]

Returned JSON example
---------------------
{
  "score_0_to_10": 9,
  "issues": ["Minor comma usage"],
  "overall_comment": "Excellent fidelity and style."
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
except ImportError as exc:  # pragma: no cover
    sys.stderr.write("openai package not installed. Run `uv pip install openai`\n")
    raise exc

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = (
    "You are a professional Hebrew linguist and translator. "
    "Evaluate the **Hebrew** candidate translation against the English source "
    "and the German reference.\n\n"
    "Give a holistic score from 0 (unintelligible) to 10 (publication quality). "
    "Focus on accuracy, fluency, proper names, idioms, and RTL punctuation.\n\n"
    "Return a JSON object exactly in this form (no additional keys):\n"
    "{{\n  \"score_0_to_10\": <int>,\n  \"issues\": [\"issue 1\", ...],\n  \"overall_comment\": \"<concise summary>\"\n}}\n\n"
    "English source:\n<<<\n{en}\n>>>\n\n"
    "German reference:\n<<<\n{de}\n>>>\n\n"
    "Hebrew candidate:\n<<<\n{he}\n>>>"
)


def load_text(path: pathlib.Path, max_chars: int = 4000) -> str:
    """Read a file and truncate to *roughly* max_chars without breaking words."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= max_chars:
        return text
    # Truncate at the last whitespace before max_chars for nicer cutting
    cut_at = text.rfind(" ", 0, max_chars)
    if cut_at == -1:
        cut_at = max_chars
    return text[:cut_at] + "\n[… truncated …]"


def build_paths(uuid: str) -> Dict[str, pathlib.Path]:
    """Return dict with en, de, he translation file paths for given uuid."""
    base_dir = pathlib.Path("./output/translations")
    paths: Dict[str, pathlib.Path] = {}
    for lang in ("en", "de", "he"):
        dir_path = base_dir / lang
        # Look for translation file
        pattern = f"{uuid}*_{lang}.txt"
        matches = list(dir_path.glob(pattern))
        # Fallback to transcripts for English source and German reference
        if lang == "en" and not matches:
            fallback_dir = pathlib.Path("./output/transcripts")
            # transcripts saved without lang suffix
            matches = list(fallback_dir.glob(f"{uuid}*.txt"))
        if lang == "de" and not matches:
            fallback_dir = pathlib.Path("./output/transcripts")
            # transcripts saved without suffix
            matches = list(fallback_dir.glob(f"{uuid}*.txt"))
        if not matches:
            raise FileNotFoundError(f"No {lang} file found for {uuid}")
        paths[lang] = matches[0]
    return paths


def evaluate(uuid: str, model: str = "gpt-4.1") -> Dict:
    """Call OpenAI model to evaluate translation quality."""
    paths = build_paths(uuid)
    prompt = PROMPT_TEMPLATE.format(
        en=load_text(paths["en"]),
        de=load_text(paths["de"]),
        he=load_text(paths["he"]),
    )

    # Determine which OpenAI client style is available (>=1.0.0 or legacy)
    if hasattr(openai, "OpenAI"):
        # New style client (openai>=1.0.0)
        client = openai.OpenAI()
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = completion.choices[0].message.content
    else:
        # Legacy 0.x SDK
        completion = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = completion.choices[0].message.content

    # Try to parse JSON from the assistant's message using a best-effort helper
    def _best_effort_parse(txt: str):
        """Attempt to load JSON, removing obvious formatting noise."""
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            # Strip backticks and whitespace
            cleaned = txt.strip().lstrip("` ").rstrip("` ")
            # Remove trailing commas before closing braces/brackets
            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
            return json.loads(cleaned)

    try:
        return _best_effort_parse(content)
    except json.JSONDecodeError:
        # If the model returned extra text, attempt to extract JSON block
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if m:
            return _best_effort_parse(m.group())
        raise ValueError("Could not parse JSON from model response")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Evaluate Hebrew translation quality.")
    parser.add_argument("--uuid", required=True, help="File UUID to evaluate")
    parser.add_argument("--model", default="gpt-4.1", help="OpenAI model (default: gpt-4.1)")
    parser.add_argument("--max-chars", type=int, default=4000, help="Max chars per input segment")
    args = parser.parse_args()

    # Ensure API key
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY environment variable not set.")

    result = evaluate(args.uuid, args.model)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
