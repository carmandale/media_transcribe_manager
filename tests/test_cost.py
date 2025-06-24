#!/usr/bin/env python3
# Quick test of cost estimation

# Average file is ~2000 words, ~10000 characters
avg_chars = 10000
tokens_per_char = 1/4  # Rough estimate: 1 token ≈ 4 characters

input_tokens = avg_chars * tokens_per_char
output_tokens = input_tokens  # Assume similar length output

# GPT-4 Turbo pricing
input_cost = (input_tokens / 1000) * 0.01
output_cost = (output_tokens / 1000) * 0.03
total_cost = input_cost + output_cost

print(f"Average file analysis:")
print(f"  Characters: {avg_chars}")
print(f"  Estimated input tokens: {input_tokens}")
print(f"  Estimated output tokens: {output_tokens}")
print(f"  Input cost: ${input_cost:.4f}")
print(f"  Output cost: ${output_cost:.4f}")
print(f"  Total cost per file: ${total_cost:.4f}")
print(f"\nFor 379 files:")
print(f"  Total cost: ${total_cost * 379:.2f}")
