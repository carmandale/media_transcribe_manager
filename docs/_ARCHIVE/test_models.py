#!/usr/bin/env python3
"""Quick interactive benchmark for GPT‑4o, GPT‑4o‑mini, and Grok‑3.

Usage:
    python scripts/test_models.py

Env requirements:
    OPENAI_API_KEY   – for GPT‑4o / 4o‑mini
    GROK             – xAI key (added to .env)
"""
from __future__ import annotations

import os
import time
import json
import textwrap
from typing import Dict, Tuple

try:
    import openai  # type: ignore
except ImportError:
    openai = None  # type: ignore

import requests
from dotenv import load_dotenv

load_dotenv()

SAMPLE_MESSAGES = [
    {"role": "system", "content": "You are a test assistant."},
    {
        "role": "user",
        "content": "Testing. Just say hi and hello world and nothing else.",
    },
]

OPENAI_MODELS = [
    ("gpt-4o", 5, 15),  # price per 1M (input, output) in USD
    ("gpt-4o-mini", 1, 3),
]

GROK_PRICE = (None, None)  # Unknown; set as None

def call_openai(model: str) -> Tuple[str, float, int, int]:
    if not openai:
        raise RuntimeError("openai package not installed. pip install openai")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI(api_key=api_key)
        t0 = time.time()
        completion = client.chat.completions.create(
            model=model,
            messages=SAMPLE_MESSAGES,
            temperature=0,
        )
        latency = time.time() - t0
        content = completion.choices[0].message.content.strip()
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
    else:  # legacy SDK
        openai.api_key = api_key
        t0 = time.time()
        completion = openai.ChatCompletion.create(
            model=model,
            messages=SAMPLE_MESSAGES,
            temperature=0,
        )
        latency = time.time() - t0
        content = completion["choices"][0]["message"]["content"].strip()
        usage = completion["usage"]
        prompt_tokens = usage["prompt_tokens"]
        completion_tokens = usage["completion_tokens"]

    return content, latency, prompt_tokens, completion_tokens


def call_grok() -> Tuple[str, float, int, int]:
    key = os.getenv("GROK")
    if not key:
        raise RuntimeError("GROK env var missing")
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    payload = {
        "messages": SAMPLE_MESSAGES,
        "model": "grok-3-latest",
        "stream": False,
        "temperature": 0,
    }
    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    latency = time.time() - t0
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    return content, latency, prompt_tokens, completion_tokens


def main():
    results: Dict[str, Dict] = {}
    for model, price_in, price_out in OPENAI_MODELS:
        print(f"\nTesting {model} …")
        try:
            content, latency, p_tok, c_tok = call_openai(model)
            cost = None
            if price_in is not None:
                cost = (p_tok / 1_000_000 * price_in) + (c_tok / 1_000_000 * price_out)
            results[model] = {
                "response": content,
                "latency_s": round(latency, 2),
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "cost_est_usd": cost,
            }
            print("Response:", content)
            print("Latency:", latency, "s | tok in/out:", p_tok, c_tok)
        except Exception as e:
            print("Error with", model, e)

    print("\nTesting Grok‑3 …")
    try:
        content, latency, p_tok, c_tok = call_grok()
        results["grok-3-latest"] = {
            "response": content,
            "latency_s": round(latency, 2),
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "cost_est_usd": None,  # Unknown pricing
        }
        print("Response:", content)
        print("Latency:", latency, "s | tok in/out:", p_tok, c_tok)
    except Exception as e:
        print("Error with Grok‑3", e)

    print("\n=== Summary ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
