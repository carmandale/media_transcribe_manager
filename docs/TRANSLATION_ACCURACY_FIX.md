# Translation Accuracy Fix - Preserving Authentic Speech

## Issue Identified

The current translation system has a critical disconnect:
- **Evaluation criteria** properly checks for "Speech Pattern Fidelity" (30% weight)
- **Translation prompts** do NOT instruct to preserve speech patterns, hesitations, or filler words
- This means translations are being penalized for not preserving elements they were never told to preserve

## Current Problems

### 1. OpenAI Translation Prompt (translation.py:579-586)
```python
system_msg = (
    f"You are a professional translator. "
    f"Translate any incoming text to {target_lang_name} only. "
    "No words from any other language may appear except immutable proper nouns "
    "(people, place, organisation names). "
    "Retain paragraph and line breaks and speaker labels. "
    "Return strict JSON with keys \"translation\" (string) and \"has_foreign\" (boolean)."
)
```
**Missing**: No instruction to preserve hesitations, filler words, or authentic speech patterns

### 2. Hebrew Polish Stage (translation.py:1174-1175)
```python
"You are a professional Hebrew translator and editor. "
"Your task: improve fluency, idiom, grammar, punctuation and RTL formatting while preserving 100% meaning. "
```
**Problem**: Actively instructs to "improve fluency" which removes authentic speech patterns

## Recommended Fix

### 1. Update OpenAI Translation System Prompt
```python
system_msg = (
    f"You are a professional translator specializing in historical interview transcripts. "
    f"Translate any incoming text to {target_lang_name} only. "
    "CRITICAL: This is a verbatim transcript of spoken language. You MUST preserve: "
    "- All hesitations and filler words (um, uh, ah, hmm, etc.) "
    "- Repeated words and self-corrections "
    "- Incomplete sentences and trailing thoughts "
    "- Natural pauses indicated by ellipses or dashes "
    "- The speaker's authentic manner of speaking "
    "- All grammatical 'errors' that reflect natural speech "
    "Do NOT 'improve' or 'polish' the language. "
    "No words from any other language may appear except immutable proper nouns. "
    "Retain paragraph and line breaks and speaker labels. "
    "Return strict JSON with keys \"translation\" (string) and \"has_foreign\" (boolean)."
)
```

### 2. Remove or Update Hebrew Polish Stage
Either remove the polish stage entirely, or update it:
```python
"You are a specialist in Hebrew historical interview transcripts. "
"Review this Hebrew translation ONLY to fix: "
"- RTL formatting issues "
"- Obvious mistranslations of proper nouns "
"- Technical Hebrew spelling errors "
"Do NOT change: fluency, hesitations, filler words, or speech patterns. "
"The goal is historical accuracy, not polished prose. "
```

### 3. Update DeepL/Google/Microsoft Settings
Configure all providers to use:
- Formality: "less" (to preserve informal speech)
- Add provider-specific instructions if possible

## Verification Tests

Create test cases to verify speech preservation:

### Test Input:
```
Interviewer: So, um, when did you first arrive at the camp?

Survivor: I... I think it was, uh, maybe April or... no, no, it was March. March 1943. Yes, definitely March because, um, because the snow was still... there was still snow on the ground, you know?
```

### Expected Output (English to German):
```
Interviewer: Also, ähm, wann sind Sie zum ersten Mal im Lager angekommen?

Überlebender: Ich... ich glaube, es war, äh, vielleicht April oder... nein, nein, es war März. März 1943. Ja, definitiv März, weil, ähm, weil der Schnee noch... es lag noch Schnee auf dem Boden, wissen Sie?
```

## Implementation Steps

1. **Update translation.py** with new prompts
2. **Test on sample files** with obvious speech patterns
3. **Re-evaluate** previously translated files to check improvement
4. **Document** the change in README_TRANSLATIONS.md

## Expected Outcomes

- Quality scores should improve, especially "Speech Pattern Fidelity"
- Translations will preserve authentic voice of speakers
- Historical accuracy will be maintained
- Evaluation system and translation system will be aligned

## Why This Matters

For oral history projects:
- Hesitations can indicate emotional difficulty discussing traumatic events
- Self-corrections show the speaker's thought process
- Filler words maintain the authentic voice and personality
- These elements are crucial historical artifacts, not defects to fix