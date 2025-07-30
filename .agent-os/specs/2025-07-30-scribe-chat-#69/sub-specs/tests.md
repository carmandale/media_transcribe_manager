# Tests Specification

This is the tests coverage details for the spec detailed in @.agent-os/specs/2025-07-30-scribe-chat-#69/spec.md

> Created: 2025-07-30
> Version: 1.0.0

## Test Coverage Overview

The chat system requires comprehensive testing across data pipeline, API endpoints, UI components, and integration scenarios to ensure accuracy and reliability for historical research use.

## Unit Tests

### Data Pipeline Tests

**SRTExtractor Class**
- `test_extract_clean_text_from_valid_srt()` - Verify proper text extraction from well-formed SRT files
- `test_extract_clean_text_removes_timestamps()` - Ensure timestamps are stripped from output
- `test_extract_clean_text_preserves_formatting()` - Verify paragraph structure is maintained
- `test_extract_clean_text_handles_multiple_languages()` - Test German/English language detection
- `test_extract_clean_text_handles_malformed_srt()` - Graceful handling of corrupted SRT files
- `test_process_all_interviews_batch_processing()` - Verify processing of all 726 interviews
- `test_process_all_interviews_error_recovery()` - Test recovery from individual file failures

**ManifestPopulator Class**
- `test_update_manifest_with_transcripts()` - Verify manifest structure updates correctly
- `test_update_manifest_preserves_existing_data()` - Ensure existing interview data remains intact
- `test_update_manifest_handles_large_content()` - Test performance with large transcript content
- `test_update_manifest_validates_interview_ids()` - Ensure ID matching between SRT and manifest
- `test_update_manifest_backup_and_restore()` - Test backup creation and rollback functionality

### Chat Engine Tests

**ChatEngine Class**
- `test_process_query_basic_functionality()` - Test basic query processing and response generation
- `test_process_query_with_context_preservation()` - Verify multi-turn conversation context handling
- `test_process_query_language_detection()` - Test automatic language detection and response matching
- `test_process_query_source_limitation()` - Verify maxSources parameter enforcement
- `test_process_query_empty_results()` - Handle queries with no relevant content found
- `test_process_query_openai_api_failure()` - Test graceful degradation when OpenAI unavailable

**ResponseGenerator**
- `test_generate_response_with_citations()` - Verify proper citation formatting in responses
- `test_generate_response_confidence_scoring()` - Test confidence score calculation accuracy
- `test_generate_response_source_attribution()` - Ensure all claims are properly attributed
- `test_generate_response_multi_language_support()` - Test German/Hebrew response generation
- `test_generate_response_hallucination_prevention()` - Verify responses are grounded in sources only

### Database Tests

**ChatSession Management**
- `test_create_chat_session()` - Verify session creation with proper UUID generation
- `test_update_session_with_conversation()` - Test conversation history storage
- `test_cleanup_expired_sessions()` - Verify automatic 24-hour cleanup functionality
- `test_session_data_privacy()` - Ensure no query content stored in session data
- `test_session_concurrent_access()` - Test thread-safe session management

**Query Logging**
- `test_log_chat_query_metrics()` - Verify proper analytics logging without content
- `test_query_hash_generation()` - Test SHA-256 query hashing for privacy
- `test_query_performance_tracking()` - Verify response time and token usage logging
- `test_query_error_logging()` - Test error condition logging and reporting

## Integration Tests

### Data Pipeline Integration

**End-to-End SRT Processing**
- `test_full_srt_extraction_pipeline()` - Process sample SRT files through complete pipeline
- `test_manifest_integration_with_search()` - Verify updated manifest works with Fuse.js search
- `test_interview_id_consistency()` - Ensure ID matching across all system components
- `test_transcript_language_detection()` - Verify correct language assignment and handling

### API Integration Tests

**Chat API Endpoints**
- `test_post_chat_endpoint_basic_query()` - Test basic chat endpoint functionality
- `test_post_chat_endpoint_with_session()` - Test session-based conversation continuity
- `test_post_chat_endpoint_rate_limiting()` - Verify rate limiting enforcement (60 req/min)
- `test_post_chat_endpoint_error_handling()` - Test various error scenarios and responses
- `test_get_session_endpoint()` - Test session retrieval functionality
- `test_delete_session_endpoint()` - Test session cleanup endpoint

**Search System Integration**
- `test_chat_search_integration()` - Verify chat queries properly utilize Fuse.js search
- `test_search_results_to_citations()` - Test conversion of search results to citation format
- `test_search_performance_with_transcripts()` - Verify acceptable performance with full transcript content
- `test_search_relevance_scoring()` - Test search result quality and ranking

### OpenAI API Integration

**External API Testing**
- `test_openai_api_connection()` - Verify successful connection to OpenAI GPT-4
- `test_openai_response_generation()` - Test response generation with real API calls
- `test_openai_api_error_handling()` - Test handling of API failures and rate limits
- `test_openai_token_usage_tracking()` - Verify accurate token consumption reporting

## Feature Tests

### Chat Interface End-to-End

**User Workflow Tests**
- `test_complete_chat_conversation_flow()` - Test full user interaction from query to response
- `test_citation_links_to_interviews()` - Verify citation links properly navigate to interview views
- `test_multi_turn_conversation_context()` - Test conversation continuity across multiple queries
- `test_chat_interface_responsive_design()` - Test chat UI on different screen sizes
- `test_chat_message_history_display()` - Verify proper conversation history presentation

**Content Discovery Tests**
- `test_historical_content_discovery()` - Test various historical queries return relevant results
- `test_cross_interview_synthesis()` - Verify responses synthesize information from multiple sources
- `test_proper_attribution_display()` - Test citation display and interview linking functionality
- `test_multilingual_query_support()` - Test queries in German, English, and Hebrew

### Performance and Reliability

**System Performance Tests**
- `test_chat_response_time_under_2_seconds()` - Verify 95% of queries respond within 2 seconds
- `test_concurrent_user_support()` - Test system with multiple simultaneous chat sessions
- `test_large_query_handling()` - Test system with maximum length queries (500 characters)
- `test_memory_usage_during_chat_sessions()` - Monitor memory consumption during extended use

**Error Recovery Tests**
- `test_search_system_failure_recovery()` - Test graceful degradation when search fails
- `test_database_connection_error_handling()` - Test chat functionality when database unavailable
- `test_manifest_file_corruption_handling()` - Test behavior with corrupted manifest data
- `test_network_interruption_recovery()` - Test system recovery from network failures

## Mocking Requirements

### External Service Mocks

**OpenAI API Mock**
- Mock successful GPT-4 responses with realistic content and token usage
- Mock API rate limiting and quota exceeded scenarios
- Mock API timeout and connection failure scenarios
- Mock invalid API key and authentication failures

**File System Mocks**
- Mock SRT file reading with various content scenarios (valid, malformed, empty)
- Mock manifest file operations (read, write, backup, restore)
- Mock file permission errors and disk space issues
- Mock concurrent file access scenarios

### Database Mocks

**SQLite Mock Strategy**
- Use in-memory SQLite database for unit tests (`:memory:`)
- Mock database connection failures and timeout scenarios
- Mock concurrent access and locking scenarios
- Mock database migration and schema update failures

### Search System Mocks

**Fuse.js Integration Mock**
- Mock search results with varying relevance scores
- Mock search performance with large datasets
- Mock empty search results and edge cases
- Mock search system failures and recovery

## Test Data Requirements

### Sample SRT Files
- **Valid multilingual SRT:** Files with English/German content and proper timestamps
- **Malformed SRT:** Files with missing timestamps, corrupted encoding, truncated content
- **Large SRT:** Files representing longest interviews (4,500+ lines) for performance testing
- **Empty/minimal SRT:** Edge cases with very short or empty content

### Sample Interview Data
- **Complete interview records:** Full interview objects with all metadata fields
- **Partial interview records:** Records missing optional fields for robustness testing
- **Invalid interview data:** Malformed IDs, missing required fields for error handling
- **Large dataset:** Subset of real 726 interviews for integration testing

### Sample Chat Queries
- **Historical content queries:** "Eastern Front stories", "military service restrictions"
- **Person-specific queries:** "What did [name] say about...", "Find interviews mentioning [person]"
- **Location-based queries:** "Interviews from Berlin", "Stories from concentration camps"
- **Emotion/theme queries:** "Feelings of discrimination", "Post-war experiences"
- **Edge case queries:** Very short queries, very long queries, non-historical queries

## Test Environment Setup

### Local Development Testing
```bash
# Test environment setup script
pytest tests/unit/ --cov=scribe_chat --cov-report=html
pytest tests/integration/ --slow
pytest tests/e2e/ --browser=chrome --headless
```

### Continuous Integration Testing
- **Unit Tests:** Run on every commit with coverage reporting
- **Integration Tests:** Run on PR creation with external API mocking
- **E2E Tests:** Run on staging deployment with full system testing
- **Performance Tests:** Run weekly with full 726 interview dataset

### Test Coverage Goals
- **Unit Tests:** 90%+ code coverage for all new chat system components
- **Integration Tests:** 100% coverage of API endpoints and data pipeline flows
- **E2E Tests:** 100% coverage of user-facing chat functionality
- **Performance Tests:** Validate all PRD performance requirements (response time, throughput)