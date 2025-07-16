# PRD: SRT Translation with Language Preservation

**Status**: Completed  
**Created**: 2025-01-07  
**Updated**: 2025-01-07  
**Author**: Claude

## Problem Statement

The current subtitle translation system overtranslates mixed-language interviews, causing multiple critical issues:

1. **Loss of Authentic Voice**: When translating German interviews with English questions, the English questions get unnecessarily translated, losing the interviewer's authentic voice
2. **Broken Timing**: Full retranslation can break subtitle-video synchronization
3. **Excessive Costs**: Translating segments already in the target language wastes API calls and money
4. **Poor User Experience**: Viewers see unnatural translations of content that was already in their language

### Specific Issues:
- German interview with English questions → English translation translates EVERYTHING
- API costs are 50-100x higher than necessary due to segment-by-segment translation
- Current implementation makes ~3,000 API calls per file (one per segment)
- No language detection to identify what actually needs translation

## Current State

### Working Components:
- Basic SRT parsing and generation
- Translation APIs (DeepL, OpenAI) are functional
- Hebrew routing to appropriate providers
- File I/O and timing preservation

### Broken/Missing Components:
- No language detection per segment
- No preservation of segments already in target language
- Inefficient segment-by-segment API calls
- No deduplication of repeated phrases
- Excessive API costs ($300-400 for full archive)

## Requirements

### Functional Requirements:
1. **Preserve Exact Timing**: Every subtitle segment MUST maintain its original timestamp
2. **Language Detection**: Automatically detect the language of each segment
3. **Selective Translation**: Only translate segments NOT in the target language
4. **Batch Processing**: Translate multiple texts in single API calls
5. **Deduplication**: Translate each unique phrase only once

### Technical Requirements:
1. **Timing Accuracy**: Millisecond precision on all subtitle timestamps
2. **API Efficiency**: Reduce API calls by 50-100x through batching
3. **Memory Efficiency**: Handle files with 3,000+ segments without timeout
4. **Language Support**: English, German, Hebrew with appropriate routing

### Non-Functional Requirements:
1. **Cost Target**: Under $10 for entire 726-file archive
2. **Performance**: Process typical file in under 30 seconds
3. **Accuracy**: Maintain translation quality while batching

## Technical Solution

### Architecture Changes:

Replace segment-by-segment translation with intelligent batching:

```python
class SRTTranslator:
    def translate_srt(self, srt_path, target_language, preserve_original=True):
        # 1. Parse SRT file
        segments = self.parse_srt(srt_path)
        
        # 2. Build translation map
        texts_to_translate = {}
        for segment in segments:
            if self.should_translate_segment(segment, target_language):
                texts_to_translate[segment.text] = None
        
        # 3. Batch translate unique texts
        if texts_to_translate:
            unique_texts = list(texts_to_translate.keys())
            translations = self.batch_translate(unique_texts, target_language)
            
            # Create lookup map
            for original, translated in zip(unique_texts, translations):
                texts_to_translate[original] = translated
        
        # 4. Apply translations while preserving timing
        for segment in segments:
            if segment.text in texts_to_translate:
                segment.text = texts_to_translate[segment.text]
        
        return segments
```

### Implementation Details:

1. **Language Detection Optimization**:
   - Use pattern matching for common words (fast)
   - Fall back to langdetect for ambiguous cases
   - Cache detection results for repeated phrases

2. **Batch Translation**:
   - Group up to 100 unique texts per API call
   - Use newline separation for batch processing
   - Handle API response parsing and alignment

3. **Deduplication Strategy**:
   - Common phrases like "Yes", "Mm-hmm", "Uh" appear hundreds of times
   - Translate once, apply everywhere
   - Reduces 3,000 segments to ~50-100 unique phrases per file

### Integration Points:
- Reuse existing `HistoricalTranslator` for API calls
- Maintain compatibility with pipeline.py
- Keep same CLI interface
- Preserve existing provider selection logic (DeepL for EN/DE, OpenAI for HE)

## Success Criteria

1. **Functionality**:
   - Segments in target language remain unchanged
   - All timestamps preserved exactly
   - Hebrew routing continues to work

2. **Performance**:
   - 50-100x reduction in API calls
   - Process 1-hour interview in < 30 seconds
   - No timeouts on large files

3. **Quality**:
   - Translations maintain historical accuracy
   - Speech patterns preserved
   - Natural subtitle flow

## Implementation Plan

### Phase 1: Core Implementation (Day 1)
1. Add `batch_translate()` method to HistoricalTranslator
2. Refactor `translate_srt()` to use batching
3. Implement text deduplication logic
4. Add progress logging

### Phase 2: Testing (Day 2)
1. Test on known mixed-language interviews
2. Verify timing preservation
3. Compare costs with/without optimization
4. Validate all three languages

### Phase 3: Full Processing (Day 3)
1. Process entire 726-file archive
2. Monitor API usage and costs
3. Generate comparison report
4. Document actual savings

## Risks and Mitigations

### Risk: Batch translation may alter context
**Mitigation**: Preserve paragraph boundaries in batches, include context markers

### Risk: API rate limits with large batches
**Mitigation**: Implement retry logic, chunk batches if needed

### Risk: Memory issues with deduplication map
**Mitigation**: Process in chunks for very large files

## Alternative Approaches Considered

1. **Streaming Translation**: Process segments in real-time
   - Rejected: Still requires one API call per unique segment

2. **Pre-translate Common Phrases**: Build translation dictionary
   - Rejected: Would miss context-specific translations

3. **Full-file Translation**: Translate entire transcript, re-segment
   - Rejected: Would lose precise timing synchronization

## Decision

Implement batch translation with deduplication while preserving exact timing. This approach:
- Reduces costs by 50-100x
- Preserves authentic voices
- Maintains perfect synchronization
- Scales to entire archive

## References

- Original feature implementation: `/scribe/srt_translator.py`
- Translation system: `/scribe/translate.py`
- Cost analysis: Based on provider pricing (DeepL for EN/DE, OpenAI for HE)
- Related PRD: `hebrew-evaluation-fix.md`