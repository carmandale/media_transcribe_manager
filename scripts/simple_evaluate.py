#!/usr/bin/env python3
"""
A simple script to evaluate translation quality for one file
"""
import os
import sys
import json
import openai
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("simple-eval")

# Check if API key is set
if not os.getenv("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY not set. Please set it in your environment.")
    sys.exit(1)

# Set the file ID to evaluate
FILE_ID = "225f0880-e414-43cd-b3a5-2bd6e5642f07"
LANGUAGE = "de"

# Get the file paths
translation_path = Path(f"./output/translations/{LANGUAGE}/{FILE_ID}_01_1744061646_{LANGUAGE}.txt")

if not translation_path.exists():
    logger.error(f"Translation file not found at {translation_path}")
    sys.exit(1)

# Read the file content
with open(translation_path, "r", encoding="utf-8", errors="ignore") as f:
    translation_text = f.read(3000)  # Read up to 3000 characters

# Create the prompt
prompt = (
    f"You are a professional {LANGUAGE} linguist and translator. "
    f"Evaluate the following {LANGUAGE} text for quality, grammar, style, and clarity.\n\n"
    f"Give a holistic score from 0 to 10. Return a JSON object with these fields only:\n"
    f"{{\"score_0_to_10\": <int>, \"issues\": [<strings>], \"overall_comment\": <string>}}\n\n"
    f"Text to evaluate:\n{translation_text[:2000]}"
)

# Make the API call
client = openai.OpenAI()
completion = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0
)

result = completion.choices[0].message.content
print("\nRaw API response:")
print(result)

# Try to parse JSON
try:
    data = json.loads(result)
    print("\nParsed result:")
    print(f"Score: {data.get('score_0_to_10', 'N/A')}/10")
    print(f"Issues: {data.get('issues', [])}")
    print(f"Comment: {data.get('overall_comment', '')}")
except json.JSONDecodeError:
    print("\nFailed to parse response as JSON")
    # Try to extract JSON from markdown
    try:
        import re
        match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if match:
            json_str = match.group(1)
            data = json.loads(json_str)
            print("\nParsed from markdown:")
            print(f"Score: {data.get('score_0_to_10', 'N/A')}/10")
            print(f"Issues: {data.get('issues', [])}")
            print(f"Comment: {data.get('overall_comment', '')}")
        else:
            # Try direct regex
            match = re.search(r'{\s*"score_0_to_10":\s*(\d+),\s*"issues":\s*\[(.*?)\],\s*"overall_comment":\s*"(.*?)"\s*}', result, re.DOTALL)
            if match:
                print("\nExtracted with regex:")
                print(f"Score: {match.group(1)}/10")
                print(f"Issues: {match.group(2)}")
                print(f"Comment: {match.group(3)}")
    except Exception as e:
        print(f"Error processing response: {e}")