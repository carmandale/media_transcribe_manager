# Tests Specification

This is the tests coverage details for the spec detailed in @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/spec.md

> Created: 2025-07-28
> Version: 1.0.0

## Test Coverage Strategy

The subtitle-first architecture requires comprehensive testing to ensure synchronization accuracy and prevent regression of the critical timing issues. Tests must validate both the technical implementation and the end-user experience of synchronized subtitles.

## Unit Tests

### ElevenLabs Integration Tests

**TestElevenLabsSegmentParsing**
- Test word-level timestamp extraction from API response
- Test segment creation logic with various speech patterns
- Test handling of confidence scores and language detection
- Test fallback behavior when segments data is missing
- Test segment boundary detection (sentence endings, pauses)

**TestSegmentCreation**
- Test max_duration parameter enforcement (segments ≤ 4 seconds)
- Test max_words parameter enforcement (segments ≤ 10 words)
- Test natural boundary detection (punctuation, pauses)
- Test segment overlap prevention
- Test minimum segment duration (≥ 0.5 seconds)

### Translation Integration Tests

**TestDeepLTranslation**
- Test segment-based translation preserves timing
- Test context injection for better translation quality
- Test batch translation efficiency
- Test rate limiting and retry logic
- Test translation confidence score handling

**TestOpenAIHebrewTranslation**
- Test Hebrew translation with historical context
- Test cultural sensitivity in translation choices
- Test segment length preservation in Hebrew
- Test handling of proper nouns and historical terms
- Test system prompt effectiveness for historical content

### Database Schema Tests

**TestSubtitleSegments**
- Test segment insertion with valid timing data
- Test timing overlap prevention triggers
- Test cascade deletion when interview is removed
- Test segment indexing and ordering
- Test confidence score constraints (0.0-1.0)

**TestTranscriptViews**
- Test transcript view aggregation from segments
- Test segment quality metrics calculation
- Test backward compatibility with existing queries
- Test performance with large segment counts
- Test concurrent access to views during updates

## Integration Tests

### End-to-End Processing Pipeline

**TestSubtitleFirstPipeline**
- Test complete processing: audio → ElevenLabs → segments → translation → SRT
- Test pipeline error handling and rollback
- Test quality validation at each stage
- Test concurrent processing of multiple interviews
- Test pipeline resume after interruption

**TestSynchronizationValidation**
- Test automated subtitle-video alignment checking
- Test quality scoring based on timing accuracy
- Test detection of synchronization drift over time
- Test validation of segment boundaries at natural speech pauses
- Test cross-language consistency in timing

### API Integration Tests

**TestExternalAPIResilience**
- Test ElevenLabs API failure recovery and retries
- Test DeepL API rate limiting and backoff
- Test OpenAI API timeout handling
- Test graceful degradation when services are unavailable
- Test API response validation and error detection

**TestTranslationQuality**
- Test translation consistency across segment boundaries
- Test context preservation in segment-based translation
- Test terminology consistency within interview
- Test handling of overlapping speech or unclear audio
- Test quality assessment and retry logic

## Feature Tests

### Video Player Synchronization Tests

**TestSubtitleVideoAlignment**
- Test SRT file playback synchronization in video player
- Test language switching maintains timing accuracy
- Test seeking to specific timestamps shows correct subtitles
- Test subtitle display timing matches speech exactly
- Test subtitle transitions at segment boundaries

**TestUserWorkflow**
- Test historian searching for specific terms in subtitles
- Test citation workflow with precise timestamps
- Test subtitle accuracy for historical names and places
- Test multi-language research workflow
- Test subtitle readability and timing for different speech patterns

### Quality Assurance Tests

**TestSynchronizationAccuracy**
- Test >95% of segments within 500ms timing tolerance
- Test segment duration distribution (0.5-10 seconds)
- Test gap analysis between consecutive segments
- Test subtitle-speech alignment with sample videos
- Test cross-language timing consistency

**TestTranslationAccuracy**
- Test historical term preservation in translations
- Test proper noun consistency across languages
- Test cultural context preservation in Hebrew translations
- Test German translation quality for historical testimony
- Test English translation accessibility for researchers

## Performance Tests

### Processing Performance

**TestBatchProcessingScaling**
- Test processing time for interviews of various lengths (1-3 hours)
- Test memory usage during segment creation and translation
- Test database performance with large segment counts
- Test concurrent interview processing capacity
- Test API rate limiting impact on throughput

**TestDatabasePerformance**
- Test segment retrieval performance for video player
- Test search performance across large segment collections
- Test index effectiveness for time-based queries
- Test view aggregation performance for transcript generation
- Test concurrent read/write performance during processing

## Mocking Requirements

### External Service Mocks

**ElevenLabs Scribe API Mock**
```python
@pytest.fixture
def mock_elevenlabs_response():
    return {
        "text": "This is a test transcript with multiple words and sentences.",
        "segments": [
            {"start": 0.0, "end": 0.5, "text": "This", "confidence": 0.95},
            {"start": 0.5, "end": 0.8, "text": "is", "confidence": 0.92},
            {"start": 0.8, "end": 1.1, "text": "a", "confidence": 0.89},
            {"start": 1.1, "end": 1.4, "text": "test", "confidence": 0.94}
        ],
        "language": "en",
        "confidence": 0.92
    }
```

**DeepL Translation API Mock**
```python
@pytest.fixture
def mock_deepl_translation():
    return {
        "translations": [{
            "detected_source_language": "EN",
            "text": "Dies ist ein Test"
        }]
    }
```

**OpenAI API Mock for Hebrew Translation**
```python
@pytest.fixture  
def mock_openai_hebrew_response():
    return {
        "choices": [{
            "message": {
                "content": "זהו מבחן"
            }
        }]
    }
```

### Database Mocking

**Test Database Setup**
```python
@pytest.fixture
def test_database():
    """Create isolated test database with subtitle_segments schema"""
    db_path = ":memory:"  # In-memory SQLite for tests
    conn = sqlite3.connect(db_path)
    
    # Create tables and indexes
    create_subtitle_segments_table(conn)
    create_indexes(conn)
    create_views(conn)
    
    yield conn
    conn.close()
```

### Video File Mocking

**Sample Media Files**
```python
@pytest.fixture
def sample_audio_files():
    """Provide test audio files with known timing characteristics"""
    return {
        "short_sample": "tests/media/sample_30s.wav",  # 30 second test file
        "medium_sample": "tests/media/sample_5min.wav",  # 5 minute test file
        "long_sample": "tests/media/sample_1hour.wav",   # 1 hour test file
        "multi_speaker": "tests/media/conversation.wav"  # Multiple speakers
    }
```

## Test Data Requirements

### Reference Interviews

**Timing Reference Data**
- Sample interviews with manually verified subtitle timing
- Ground truth timestamps for synchronization validation
- Multi-language reference translations for quality comparison
- Historical terminology reference lists for translation accuracy

**Quality Benchmarks**
- Expected synchronization accuracy thresholds (>95% within 500ms)
- Translation quality scores for different content types
- Processing time benchmarks for various interview lengths
- Memory usage baselines for batch processing

### Edge Case Test Data

**Challenging Audio Scenarios**
- Interviews with heavy accents requiring robust transcription
- Overlapping speech or background noise
- Very fast or very slow speech patterns
- Technical or historical terminology density
- Mixed language content (code-switching)

**Translation Edge Cases**
- Proper nouns requiring cultural context
- Historical events and dates
- Geographic locations with multiple naming conventions
- Technical military or historical terminology
- Emotional or sensitive content requiring appropriate tone

## Continuous Integration Requirements

### Automated Test Execution

**Test Pipeline Stages**
1. **Unit Tests**: Run on every commit, complete in <2 minutes
2. **Integration Tests**: Run on PR creation, complete in <10 minutes  
3. **Feature Tests**: Run on merge to main, complete in <30 minutes
4. **Performance Tests**: Run nightly, identify regressions

**Quality Gates**
- Unit test coverage >80% for new subtitle-first code
- Integration tests must pass for all API interactions
- Synchronization accuracy tests must meet >95% threshold
- Performance tests must not regress beyond 10% of baseline

### Test Environment Management

**API Test Credentials**
- Separate test API keys for ElevenLabs, DeepL, OpenAI
- Rate-limited test accounts to prevent production impact
- Mock services for offline testing and CI environments
- Test data cleanup after each test run

**Database Test Management**
- Isolated test databases for each test run
- Automatic test data seeding and cleanup
- Migration testing with sample data
- Performance test data sets for realistic load testing