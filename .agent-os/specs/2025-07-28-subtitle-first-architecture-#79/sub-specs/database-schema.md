# Database Schema

This is the database schema implementation for the spec detailed in @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/spec.md

> Created: 2025-07-28
> Version: 1.0.0

## Schema Changes Overview

The subtitle-first architecture requires a fundamental shift from transcript-based to segment-based data storage. This addresses the core synchronization issues by making timed subtitle segments the primary data entity.

## New Tables

### `subtitle_segments` - Primary Entity

```sql
CREATE TABLE subtitle_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    segment_index INTEGER NOT NULL,
    start_time REAL NOT NULL,      -- Start timestamp in seconds (from ElevenLabs)
    end_time REAL NOT NULL,        -- End timestamp in seconds (from ElevenLabs)
    duration REAL GENERATED ALWAYS AS (end_time - start_time) STORED,
    original_text TEXT NOT NULL,
    german_text TEXT,
    english_text TEXT,
    hebrew_text TEXT,
    confidence_score REAL,         -- ElevenLabs confidence for this segment
    processing_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
    UNIQUE(interview_id, segment_index),
    CHECK(start_time >= 0),
    CHECK(end_time > start_time),
    CHECK(duration > 0),
    CHECK(confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1))
);
```

### Indexes for Performance

```sql
-- Primary lookup patterns
CREATE INDEX idx_subtitle_segments_interview_id ON subtitle_segments(interview_id);
CREATE INDEX idx_subtitle_segments_timing ON subtitle_segments(interview_id, start_time);
CREATE INDEX idx_subtitle_segments_search ON subtitle_segments(interview_id, segment_index);

-- Text search indexes (for future full-text search)
CREATE INDEX idx_subtitle_segments_original_text ON subtitle_segments(original_text);
CREATE INDEX idx_subtitle_segments_english_text ON subtitle_segments(english_text);
CREATE INDEX idx_subtitle_segments_german_text ON subtitle_segments(german_text);
```

## Modified Tables

### `interviews` Table - Add Segment Tracking

```sql
-- Add columns to existing interviews table
ALTER TABLE interviews ADD COLUMN total_segments INTEGER DEFAULT 0;
ALTER TABLE interviews ADD COLUMN avg_segment_duration REAL;
ALTER TABLE interviews ADD COLUMN subtitle_sync_quality REAL; -- 0.0-1.0 quality score

-- Update existing columns to reflect new architecture
-- processing_status will include 'segmented', 'synchronized' states
```

## Views for Backward Compatibility

### `transcripts` View - Derived from Segments

```sql
CREATE VIEW transcripts AS
SELECT 
    interview_id,
    GROUP_CONCAT(original_text, ' ') as original_transcript,
    GROUP_CONCAT(german_text, ' ') as german_transcript, 
    GROUP_CONCAT(english_text, ' ') as english_transcript,
    GROUP_CONCAT(hebrew_text, ' ') as hebrew_transcript,
    COUNT(*) as total_segments,
    AVG(confidence_score) as avg_confidence,
    MIN(start_time) as transcript_start,
    MAX(end_time) as transcript_end,
    MAX(end_time) - MIN(start_time) as total_duration
FROM subtitle_segments 
GROUP BY interview_id
ORDER BY interview_id;
```

### `segment_quality` View - Quality Metrics

```sql
CREATE VIEW segment_quality AS
SELECT 
    interview_id,
    COUNT(*) as total_segments,
    AVG(duration) as avg_segment_duration,
    MIN(duration) as min_segment_duration,
    MAX(duration) as max_segment_duration,
    AVG(confidence_score) as avg_confidence,
    COUNT(CASE WHEN confidence_score < 0.8 THEN 1 END) as low_confidence_segments,
    COUNT(CASE WHEN duration < 1.0 THEN 1 END) as short_segments,
    COUNT(CASE WHEN duration > 10.0 THEN 1 END) as long_segments
FROM subtitle_segments
GROUP BY interview_id;
```

## Migration Scripts

### Migration 1: Create New Schema

```sql
-- Create subtitle_segments table
-- (Full table creation as shown above)

-- Create indexes
-- (All index creation as shown above)

-- Create views
-- (All view creation as shown above)
```

### Migration 2: Data Validation Functions

```sql
-- Function to validate segment timing consistency
CREATE TRIGGER validate_segment_timing 
BEFORE INSERT ON subtitle_segments
FOR EACH ROW
BEGIN
    -- Ensure no timing overlaps within same interview
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM subtitle_segments 
            WHERE interview_id = NEW.interview_id 
            AND id != NEW.id
            AND (
                (NEW.start_time BETWEEN start_time AND end_time) OR
                (NEW.end_time BETWEEN start_time AND end_time) OR
                (start_time BETWEEN NEW.start_time AND NEW.end_time)
            )
        )
        THEN RAISE(ABORT, 'Segment timing overlap detected')
    END;
END;
```

### Migration 3: Quality Validation

```sql
-- Trigger to update interview-level quality metrics
CREATE TRIGGER update_interview_quality 
AFTER INSERT ON subtitle_segments
FOR EACH ROW
BEGIN
    UPDATE interviews 
    SET 
        total_segments = (
            SELECT COUNT(*) FROM subtitle_segments 
            WHERE interview_id = NEW.interview_id
        ),
        avg_segment_duration = (
            SELECT AVG(duration) FROM subtitle_segments 
            WHERE interview_id = NEW.interview_id
        ),
        subtitle_sync_quality = (
            SELECT AVG(confidence_score) FROM subtitle_segments 
            WHERE interview_id = NEW.interview_id
        )
    WHERE id = NEW.interview_id;
END;
```

## Data Integrity Rules

### Timing Consistency Rules

1. **No Gaps**: Segments should have minimal gaps (<0.5s) between consecutive segments
2. **No Overlaps**: Segments within same interview cannot have overlapping timestamps
3. **Positive Duration**: All segments must have end_time > start_time
4. **Reasonable Length**: Segments should be 0.5-10 seconds (typical speech patterns)

### Text Consistency Rules

1. **Required Original**: All segments must have original_text
2. **Translation Completeness**: If interview is processed, all language fields should be populated
3. **Length Correlation**: Translated text length should correlate reasonably with original

### Quality Thresholds

1. **Confidence Score**: ElevenLabs confidence should be >0.7 for production use
2. **Segment Count**: Interviews should have reasonable segment density (30-120 segments per hour)
3. **Sync Quality**: Overall interview sync quality should be >0.8 for viewer use

## Rollback Strategy

### Phase 1 Rollback: Remove New Tables
```sql
DROP TRIGGER IF EXISTS validate_segment_timing;
DROP TRIGGER IF EXISTS update_interview_quality;
DROP VIEW IF EXISTS segment_quality;
DROP VIEW IF EXISTS transcripts;
DROP INDEX IF EXISTS idx_subtitle_segments_interview_id;
DROP INDEX IF EXISTS idx_subtitle_segments_timing;
DROP INDEX IF EXISTS idx_subtitle_segments_search;
DROP TABLE IF EXISTS subtitle_segments;
```

### Phase 2 Rollback: Restore Original Columns
```sql  
-- Remove added columns from interviews table
ALTER TABLE interviews DROP COLUMN total_segments;
ALTER TABLE interviews DROP COLUMN avg_segment_duration;
ALTER TABLE interviews DROP COLUMN subtitle_sync_quality;
```

## Performance Considerations

### Query Optimization
- Segment retrieval by interview_id + time range will be primary access pattern
- Indexes optimized for video player seeking to specific timestamps
- Views provide backward compatibility without performance penalty

### Storage Efficiency
- Segment-based storage increases granularity but improves accuracy
- Estimated 50-200 segments per interview (vs 1 transcript record)
- Storage increase acceptable for synchronization accuracy gain

### Concurrent Access
- Segment-level locking enables better concurrent processing
- Multiple interviews can be processed simultaneously
- Individual segment updates don't lock entire interview