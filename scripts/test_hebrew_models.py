#!/usr/bin/env python3
"""Benchmark Hebrew translation across multiple LLM providers.

Models covered:
  • OpenAI   – gpt-4.1, gpt-4o, gpt-4o-mini
  • xAI      – grok-3-latest
  • Anthropic– claude-3-sonnet-20240229 (adjust if opus/key available)
  • Google   – gemini-1.5-pro-latest (≈2.5 pro), gemini-1.5-flash-latest (≈2.5 flash)

Each model receives the same translation instruction and sample English text.
Reports latency (s), token usage (when available), and approximate USD cost using public prices (April 2025).

Env vars required:
  OPENAI_API_KEY
  GROK_API_KEY
  ANTHROPIC_API_KEY
  GEMINI_API_KEY    (note: variable name upper‑case here)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants & sample prompt
# ---------------------------------------------------------------------------
SAMPLE_ENGLISH = (
    """We must never forget history, for it teaches us the values of humanity, justice, and responsibility. "
    "Through remembrance, we honour those who came before us and ensure that the mistakes of the past are not repeated."""
)

MESSAGES_OPENAI = [
    {"role": "system", "content": "You are a professional translator."},
    {
        "role": "user",
        "content": (
            "Translate the following paragraph into fluent, idiomatic modern Hebrew. "
            "Respect proper nouns and keep terminology precise.\n\n" + SAMPLE_ENGLISH
        ),
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_price_table() -> Dict[str, Tuple[Optional[float], Optional[float]]]:
    """Return (price_in, price_out) per million tokens for known models."""
    return {
        # OpenAI (April 2025)
        "gpt-4o": (5, 15),
        "gpt-4o-mini": (1, 3),
        "gpt-4.1": (10, 30),
        # Anthropic (Sonnet)
        "claude-3-sonnet-20240229": (3, 15),
        # Gemini
        "gemini-1.5-pro-latest": (0, 0),   # free/low cost – placeholder
        "gemini-1.5-flash-latest": (0, 0),
        "gemini-2.0-flash": (0, 0),
        "gemini-2.5-flash-preview-04-17": (0, 0),
        "gemini-2.5-pro-preview-03-25": (0, 0),
    }


PRICE_TABLE = _load_price_table()

# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------

def call_openai(model: str) -> Dict[str, Any]:
    import openai  # local import to avoid hard dep if not needed

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    # Support both new and legacy SDKs
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI(api_key=api_key)
        t0 = time.time()
        completion = client.chat.completions.create(
            model=model,
            messages=MESSAGES_OPENAI,
            temperature=0,
        )
        latency = time.time() - t0
        content = completion.choices[0].message.content.strip()
        usage = completion.usage
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
    else:
        openai.api_key = api_key
        t0 = time.time()
        completion = openai.ChatCompletion.create(
            model=model,
            messages=MESSAGES_OPENAI,
            temperature=0,
        )
        latency = time.time() - t0
        content = completion["choices"][0]["message"]["content"].strip()
        usage = completion["usage"]
        prompt_tokens = usage["prompt_tokens"]
        completion_tokens = usage["completion_tokens"]

    return {
        "response": content,
        "latency_s": round(latency, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def call_grok() -> Dict[str, Any]:
    key = os.getenv("GROK_API_KEY") or os.getenv("GROK")
    if not key:
        raise RuntimeError("GROK_API_KEY not set")
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    payload = {
        "messages": [
            {"role": "system", "content": "You are a professional translator."},
            {
                "role": "user",
                "content": (
                    "Translate the following paragraph into fluent, idiomatic modern Hebrew. "
                    "Respect proper nouns and keep terminology precise.\n\n" + SAMPLE_ENGLISH
                ),
            },
        ],
        "model": "grok-3-latest",
        "stream": False,
        "temperature": 0,
    }
    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    latency = time.time() - t0
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    return {
        "response": content,
        "latency_s": round(latency, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def call_anthropic(model: str) -> Dict[str, Any]:
    import anthropic  # type: ignore

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    t0 = time.time()
    completion = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0,
        messages=[
            {"role": "user", "content": (
                "Translate the following paragraph into fluent, idiomatic modern Hebrew. "
                "Respect proper nouns and keep terminology precise.\n\n" + SAMPLE_ENGLISH
            )},
        ],
    )
    latency = time.time() - t0
    content = completion.content[0].text.strip()
    usage = completion.usage
    prompt_tokens = usage.input_tokens
    completion_tokens = usage.output_tokens
    return {
        "response": content,
        "latency_s": round(latency, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def call_gemini(model: str) -> Dict[str, Any]:
    import google.generativeai as genai  # type: ignore

    key = os.getenv("GEMINI_API_KEY") or os.getenv("gemini_api_key")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    genai.configure(api_key=key)
    gen_model = genai.GenerativeModel(model)
    t0 = time.time()
    resp = gen_model.generate_content(
        text_prompt := (
            "Translate the following paragraph into fluent, idiomatic modern Hebrew. "
            "Respect proper nouns and keep terminology precise.\n\n" + SAMPLE_ENGLISH
        )
    )
    latency = time.time() - t0
    content = resp.text.strip()
    # Token usage not provided in client (as of Apr 2025)
    return {
        "response": content,
        "latency_s": round(latency, 2),
        "prompt_tokens": None,
        "completion_tokens": None,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def estimate_cost(model: str, prompt_t: Optional[int], compl_t: Optional[int]) -> Optional[float]:
    price = PRICE_TABLE.get(model)
    if not price or prompt_t is None or compl_t is None:
        return None
    in_rate, out_rate = price
    return (prompt_t / 1_000_000 * (in_rate or 0)) + (compl_t / 1_000_000 * (out_rate or 0))


def main() -> None:
    results: Dict[str, Dict[str, Any]] = {}

    openai_models = ["gpt-4.1", "gpt-4o", "gpt-4o-mini"]
    for m in openai_models:
        print(f"Testing {m} …")
        try:
            res = call_openai(m)
            res["cost_est_usd"] = estimate_cost(m, res["prompt_tokens"], res["completion_tokens"])
            results[m] = res
            print("✔", res["latency_s"], "s")
        except Exception as e:
            results[m] = {"error": str(e)}
            print("✖", e)

    # Grok
    print("Testing grok-3-latest …")
    try:
        res = call_grok()
        res["cost_est_usd"] = None
        results["grok-3-latest"] = res
        print("✔", res["latency_s"], "s")
    except Exception as e:
        results["grok-3-latest"] = {"error": str(e)}
        print("✖", e)

    # Anthropic
    anthro_model = "claude-3-sonnet-20240229"
    print(f"Testing {anthro_model} …")
    try:
        res = call_anthropic(anthro_model)
        res["cost_est_usd"] = estimate_cost(anthro_model, res["prompt_tokens"], res["completion_tokens"])
        results[anthro_model] = res
        print("✔", res["latency_s"], "s")
    except Exception as e:
        results[anthro_model] = {"error": str(e)}
        print("✖", e)

    # Gemini models
    for gm in ["gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-2.0-flash", "gemini-2.5-flash-preview-04-17", "gemini-2.5-pro-preview-03-25"]:
        print(f"Testing {gm} …")
        try:
            res = call_gemini(gm)
            res["cost_est_usd"] = estimate_cost(gm, None, None)
            results[gm] = res
            print("✔", res["latency_s"], "s")
        except Exception as e:
            results[gm] = {"error": str(e)}
            print("✖", e)

    print("\n=== SUMMARY ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
