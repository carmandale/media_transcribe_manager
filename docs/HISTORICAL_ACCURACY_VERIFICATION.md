# Historical Accuracy Verification Report

## Summary

**Good News**: The quality evaluation system is properly designed to check for historical accuracy and authentic speech preservation.

**Critical Issue**: The translation system does NOT implement the documented requirements for preserving authentic speech patterns.

## Current State

### ✅ What's Working

1. **Quality Evaluation Criteria** (historical_evaluate_quality.py)
   - Properly weights "Speech Pattern Fidelity" at 30%
   - Checks for preservation of hesitations, filler words, natural voice
   - Designed specifically for historical interview accuracy

2. **Documentation** 
   - README_TRANSLATIONS.md correctly states the need to preserve speech patterns
   - QUALITY_EVALUATION_GUIDE.md provides clear guidelines
   - Evaluation thresholds are appropriate (8.5+ for excellent)

3. **Evaluation Results**
   - System has achieved your target of 8.5+ scores on many files
   - Hebrew translations averaging 7.51 (needs improvement)
   - English translations averaging 8.58 (excellent)

### ❌ What's NOT Working

1. **Translation Prompts**
   - OpenAI prompt has NO instruction to preserve hesitations or filler words
   - Hebrew polish stage actively tries to "improve fluency"
   - No mention of verbatim translation or authentic speech

2. **Provider Configuration**
   - DeepL formality not set to "less" for informal speech
   - No special instructions for historical accuracy

## Verification

### Test Case
To verify, translate this sample with current system:
```
Interviewer: So, um, when did you arrive?
Survivor: I... I think, uh, April... no, March 1943.
```

Current system likely produces:
```
Interviewer: When did you arrive?
Survivor: I think March 1943.
```

But should produce:
```
Interviewer: So, um, when did you arrive?
Survivor: I... I think, uh, April... no, March 1943.
```

## Immediate Actions Required

### 1. Fix Translation Prompts
Edit `core_modules/translation.py` line 579:
```python
# CURRENT (WRONG)
system_msg = (
    f"You are a professional translator. "
    f"Translate any incoming text to {target_lang_name} only. "
    ...
)

# SHOULD BE
system_msg = (
    f"You are a professional translator specializing in historical interview transcripts. "
    f"Translate any incoming text to {target_lang_name} only. "
    "CRITICAL: This is a verbatim transcript. Preserve ALL: "
    "- Hesitations (um, uh, ah, hmm) "
    "- Repeated words and self-corrections "
    "- Incomplete sentences "
    "- Natural speech patterns "
    ...
)
```

### 2. Remove/Fix Hebrew Polish Stage
Line 1174 actively harms accuracy by trying to "improve fluency"

### 3. Set DeepL Formality
Configure to use `formality='less'` for all translations

## Impact

Once fixed:
- Quality scores should improve across all languages
- Hebrew scores should rise from 7.51 to 8.0+
- Translations will preserve authentic voice
- System will actually match its documentation

## Validation Plan

1. Fix the translation prompts
2. Re-translate 5 sample files with obvious speech patterns
3. Compare quality scores before/after
4. Verify hesitations are preserved
5. Roll out to all files needing quality improvement

## Conclusion

Your instinct about historical accuracy vs. writing quality is correct and well-documented. However, the implementation doesn't match the documentation. The fix is straightforward - update the translation prompts to explicitly preserve authentic speech patterns as the evaluation system expects.