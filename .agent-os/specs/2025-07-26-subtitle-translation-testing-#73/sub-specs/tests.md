# Tests Specification

This is the tests coverage details for the spec detailed in @.agent-os/specs/2025-07-26-subtitle-translation-testing-#73/spec.md

> Created: 2025-07-26
> Version: 1.0.0

## Test Coverage

### Unit Tests

**SubtitleTranslator**
- Test segment-by-segment language detection logic
- Test language detection for single-language segments
- Test language detection for mixed-language segments
- Test handling of non-verbal segments ([crying], [pause], etc.)
- Test short segment handling (1-3 words)
- Test proper noun and technical term preservation

**TranslationService**
- Test API response parsing for each translation service
- Test error handling and retry logic
- Test rate limit handling
- Test fallback between translation services
- Test translation caching mechanisms

**QualityEvaluator**
- Test translation quality scoring algorithms
- Test Hebrew-specific quality checks
- Test segment alignment verification
- Test quality threshold validation

### Integration Tests

**Mixed-Language Processing Pipeline**
- Process interview with German-English switches
- Process interview with Hebrew phrases
- Process interview with all three languages
- Verify correct language detection per segment
- Verify translation accuracy metrics
- Test database transaction integrity

**Batch Processing**
- Process multiple interviews concurrently
- Test resource management under load
- Test error recovery during batch operations
- Verify progress tracking accuracy
- Test cancellation and resume capabilities

**Subtitle Generation**
- Test SRT file generation with mixed languages
- Test timing alignment with original audio
- Test subtitle length constraints
- Test special character handling
- Test file encoding for all languages

### Feature Tests

**End-to-End Subtitle Translation**
- Upload mixed-language interview
- Process through complete pipeline
- Verify all language segments detected
- Confirm translations in database
- Generate and validate SRT files
- Test viewer compatibility

**Reprocessing Workflow**
- Select interviews for reprocessing
- Monitor progress in real-time
- Handle partial failures gracefully
- Verify quality improvements
- Test rollback capabilities

### Mocking Requirements

- **ElevenLabs API:** Mock transcription responses with realistic mixed-language output
- **DeepL API:** Mock translation responses for German/English with proper formatting
- **OpenAI API:** Mock GPT-4 responses for Hebrew translation scenarios
- **Microsoft Translator:** Mock fallback translation responses
- **File System:** Mock media file operations for faster testing
- **Database:** Use in-memory SQLite for unit tests

## Test Data Fixtures

### Interview Scenarios
1. **Standard German Interview** - 30 minutes, 95% German, 5% English terms
2. **Bilingual Interview** - 45 minutes, frequent German-English switches
3. **Hebrew Phrases Interview** - 20 minutes, German base with Hebrew religious terms
4. **Complex Mixed Interview** - 60 minutes, all three languages with emotional segments
5. **Edge Case Interview** - 15 minutes, very short segments, non-verbal sounds

### Expected Behaviors
- Language detection accuracy: > 95% for segments > 5 words
- Translation accuracy score: > 0.8 for standard segments
- Processing time: Linear scaling with interview duration
- Memory usage: Stable across long interviews
- Error recovery: Automatic retry with exponential backoff