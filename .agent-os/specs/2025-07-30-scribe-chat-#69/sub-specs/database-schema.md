# Database Schema

This is the database schema implementation for the spec detailed in @.agent-os/specs/2025-07-30-scribe-chat-#69/spec.md

> Created: 2025-07-30
> Version: 1.0.0

## Schema Changes

### New Tables

#### chat_sessions
Stores chat conversation sessions for context preservation and optional user experience improvements.

```sql
CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY,  -- UUID v4
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_data TEXT,    -- JSON blob for conversation context
    message_count INTEGER DEFAULT 0,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_sessions_last_active ON chat_sessions(last_active);
CREATE INDEX idx_chat_sessions_updated_at ON chat_sessions(updated_at);
```

#### chat_queries
Logs chat queries for performance monitoring and system improvement (no personal data stored).

```sql
CREATE TABLE chat_queries (
    id TEXT PRIMARY KEY,  -- UUID v4
    session_id TEXT NOT NULL,
    query_hash TEXT NOT NULL,     -- SHA-256 hash of query (privacy-preserving)
    response_time_ms INTEGER,
    sources_count INTEGER,        -- Number of interviews referenced
    tokens_used INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_queries_session_id ON chat_queries(session_id);
CREATE INDEX idx_chat_queries_created_at ON chat_queries(created_at);
CREATE INDEX idx_chat_queries_response_time ON chat_queries(response_time_ms);
```

### Modified Tables

#### interviews (Existing Table Enhancement)
Add transcript content support to existing interview tracking system.

```sql
-- Add new columns to existing interviews table
ALTER TABLE interviews ADD COLUMN transcript_extracted BOOLEAN DEFAULT FALSE;
ALTER TABLE interviews ADD COLUMN transcript_word_count INTEGER DEFAULT 0;
ALTER TABLE interviews ADD COLUMN transcript_languages TEXT; -- JSON array: ["en", "de"]
ALTER TABLE interviews ADD COLUMN last_transcript_update TIMESTAMP;

-- Create index for transcript queries
CREATE INDEX idx_interviews_transcript_extracted ON interviews(transcript_extracted);
CREATE INDEX idx_interviews_transcript_update ON interviews(last_transcript_update);
```

## Data Storage Strategy

### Transcript Content Storage
**Primary Storage:** JSON manifest file (`manifest.min.json`) for optimal search performance
- **Rationale:** Existing Fuse.js system expects manifest format, zero infrastructure changes
- **Structure:** Extend existing Interview interface with `transcripts` array
- **Performance:** Single file load with compression, cached in memory

**Database Tracking:** SQLite for metadata and processing status only
- **Content:** Track extraction status, word counts, processing timestamps
- **No Duplication:** Actual transcript text stored only in manifest to avoid data sync issues

### Chat Session Management
**Temporary Storage:** In-memory session context with optional database persistence
- **Session Duration:** 24 hours maximum, auto-cleanup
- **Privacy:** No query content stored, only hashed query signatures for analytics
- **Context Preservation:** Store conversation state for multi-turn interactions

## Migration Scripts

### Forward Migration (Schema Updates)
```sql
-- migrations/004_add_chat_support.sql
BEGIN TRANSACTION;

-- Create chat_sessions table
CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_data TEXT,
    message_count INTEGER DEFAULT 0,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create chat_queries table  
CREATE TABLE chat_queries (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    response_time_ms INTEGER,
    sources_count INTEGER,
    tokens_used INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

-- Enhance interviews table
ALTER TABLE interviews ADD COLUMN transcript_extracted BOOLEAN DEFAULT FALSE;
ALTER TABLE interviews ADD COLUMN transcript_word_count INTEGER DEFAULT 0;
ALTER TABLE interviews ADD COLUMN transcript_languages TEXT;
ALTER TABLE interviews ADD COLUMN last_transcript_update TIMESTAMP;

-- Create all indexes
CREATE INDEX idx_chat_sessions_last_active ON chat_sessions(last_active);
CREATE INDEX idx_chat_sessions_updated_at ON chat_sessions(updated_at);
CREATE INDEX idx_chat_queries_session_id ON chat_queries(session_id);
CREATE INDEX idx_chat_queries_created_at ON chat_queries(created_at);
CREATE INDEX idx_chat_queries_response_time ON chat_queries(response_time_ms);
CREATE INDEX idx_interviews_transcript_extracted ON interviews(transcript_extracted);
CREATE INDEX idx_interviews_transcript_update ON interviews(last_transcript_update);

-- Update schema version
UPDATE schema_version SET version = 4, updated_at = CURRENT_TIMESTAMP;

COMMIT;
```

### Rollback Migration (Schema Downgrade)
```sql
-- migrations/rollback_004_chat_support.sql
BEGIN TRANSACTION;

-- Remove indexes
DROP INDEX IF EXISTS idx_interviews_transcript_update;
DROP INDEX IF EXISTS idx_interviews_transcript_extracted;
DROP INDEX IF EXISTS idx_chat_queries_response_time;
DROP INDEX IF EXISTS idx_chat_queries_created_at;
DROP INDEX IF EXISTS idx_chat_queries_session_id;
DROP INDEX IF EXISTS idx_chat_sessions_updated_at;
DROP INDEX IF EXISTS idx_chat_sessions_last_active;

-- Remove added columns from interviews table
-- Note: SQLite doesn't support DROP COLUMN directly, would need table recreation
-- For development, we'll document the columns as unused instead

-- Drop chat tables
DROP TABLE IF EXISTS chat_queries;
DROP TABLE IF EXISTS chat_sessions;

-- Revert schema version
UPDATE schema_version SET version = 3, updated_at = CURRENT_TIMESTAMP;

COMMIT;
```

## Data Privacy Considerations

### Query Privacy Protection
- **No Query Storage:** Actual user queries never stored in database
- **Hash-Only Analytics:** Only SHA-256 hashes stored for performance analysis
- **Session Cleanup:** Automatic cleanup of session data after 24 hours
- **No Personal Data:** System designed to be GDPR compliant by design

### Transcript Content Security
- **Local Storage:** All transcript content remains on local filesystem
- **No Cloud Sync:** Database contains no sensitive historical content
- **Access Control:** Database access limited to application only

## Performance Optimizations

### Query Performance
```sql
-- Composite index for common chat analytics queries
CREATE INDEX idx_chat_queries_analytics ON chat_queries(created_at, response_time_ms, sources_count);

-- Partial index for error tracking
CREATE INDEX idx_chat_queries_errors ON chat_queries(created_at) WHERE error_message IS NOT NULL;
```

### Session Management
```sql
-- Cleanup query for automated session management
DELETE FROM chat_sessions 
WHERE last_active < datetime('now', '-24 hours');

-- Archive old query logs for performance
DELETE FROM chat_queries 
WHERE created_at < datetime('now', '-30 days');
```

## Integration with Existing Schema

### Backward Compatibility
- **Existing Tables:** No breaking changes to current interview, processing, or backup tables
- **Foreign Key Integrity:** New tables reference existing structures appropriately
- **Schema Versioning:** Follows existing migration pattern with version tracking

### Data Relationships
```sql
-- Connection between chat system and existing interview data
SELECT 
    cq.query_hash,
    cq.sources_count,
    COUNT(DISTINCT i.id) as interviews_referenced
FROM chat_queries cq
LEFT JOIN interviews i ON i.transcript_extracted = TRUE
WHERE cq.created_at > datetime('now', '-7 days')
GROUP BY cq.query_hash, cq.sources_count;
```