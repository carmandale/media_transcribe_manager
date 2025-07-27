# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-26-subtitle-translation-testing-#73/spec.md

> Created: 2025-07-26
> Version: 1.0.0

## Technical Requirements

- Implement unit tests for segment-by-segment language detection in `subtitle_translator.py`
- Create integration tests for the complete translation pipeline with mixed-language content
- Add test fixtures with real-world examples of language switching patterns
- Implement performance benchmarking for batch processing scenarios
- Create test reports showing translation accuracy metrics
- Ensure all tests can run in CI/CD environment without external API calls
- Mock all external translation API responses for deterministic testing

## Approach Options

**Option A:** Test-first development with comprehensive mocking
- Pros: Fast test execution, no API costs, deterministic results
- Cons: May not catch real API edge cases

**Option B:** Hybrid testing with real API calls for smoke tests (Selected)
- Pros: Validates actual API behavior, catches integration issues, still mostly mocked
- Cons: Some tests require API credentials, slightly slower

**Rationale:** The hybrid approach ensures we catch real-world API issues while keeping most tests fast and free. We'll use environment variables to control which tests make real API calls.

## External Dependencies

- **pytest-mock** - Advanced mocking capabilities for API responses
- **Justification:** Needed to mock complex translation API responses accurately

- **pytest-benchmark** - Performance testing and benchmarking
- **Justification:** Required to measure reprocessing performance at scale

- **factory-boy** - Test data generation for realistic interview scenarios
- **Justification:** Creates consistent, realistic test data for mixed-language scenarios

## Test Data Requirements

### Sample Interview Segments
- German-only segments (control group)
- English-only segments (control group)
- German-English switches within sentences
- Hebrew phrases embedded in German/English
- Non-verbal segments (crying, pauses, [inaudible])
- Very short segments (1-3 words)
- Technical terms and proper nouns

### Expected Test Coverage Areas
1. Language detection accuracy per segment
2. Translation quality for detected languages
3. Handling of unsupported language segments
4. Performance under concurrent processing
5. Error recovery and retry mechanisms
6. Database transaction integrity during batch operations

## Performance Criteria

- Single interview processing: < 5 minutes for 1-hour content
- Batch processing: Support 10 concurrent interviews
- Memory usage: < 2GB per worker process
- API rate limit handling: Automatic backoff and retry
- Database operations: < 100ms per transaction