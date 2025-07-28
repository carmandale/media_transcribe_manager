# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/spec.md

> Created: 2025-07-28
> Version: 1.0.0

## Technical Requirements

### Strategic Refactor Approach

- **Preserve SRTTranslator Core**: Leverage existing segment boundary validation and timing preservation (67% test coverage)
- **Enhance ElevenLabs Integration**: Extend transcription parsing to capture word-level timestamps without breaking current functionality
- **Database-Centric Coordination**: Add subtitle_segments storage while maintaining existing transcript workflows
- **Build Upon Testing Infrastructure**: Expand the comprehensive existing test suite rather than replacing it
- **Gradual Integration**: Modify existing components strategically rather than complete rewrite

### Current Codebase Assessment

Analysis reveals substantial salvageable components:

1. **SRTTranslator Excellence**: 67% test coverage with perfect segment boundary validation and timing preservation already working
2. **Batch Language Detection**: 83% test coverage with excellent multilingual processing capabilities
3. **Translation Quality**: Proven timing preservation mechanisms in existing translation workflow
4. **Testing Infrastructure**: Comprehensive validation framework providing confidence in modifications
5. **ElevenLabs Integration Gap**: API provides word-level timestamps that current parsing doesn't capture (opportunity for enhancement)

### Approach Options

**Option A: Complete Rewrite**
- Pros: Clean slate design
- Cons: Discards working SRTTranslator core (67% coverage), loses proven timing mechanisms

**Option B: Strategic Refactor** (Selected)
- Pros: Preserves working components, builds upon proven foundation, leverages existing comprehensive tests
- Cons: Requires careful integration planning

**Option C: Minimal Patches**
- Pros: Low risk
- Cons: Doesn't leverage full potential of existing quality components

**Rationale:** Option B maximizes value from existing high-quality code while addressing synchronization issues. The SRTTranslator already handles segment boundaries perfectly - we should build database integration around this proven core rather than rebuilding from scratch.

## Technical Implementation Plan

### Phase 1: Enhanced ElevenLabs Integration

**Current Flow (Keep Working):**
```
Audio → ElevenLabs Scribe → Transcript → SRTTranslator → SRT with timing validation
```

**Enhanced Flow (Add Capability):**
```
Audio → ElevenLabs Scribe → Word-level timestamps + Transcript → Database segments → SRTTranslator → Validated SRT
```

**Strategic Modifications:**
- Extend existing ElevenLabs parsing to capture word-level timestamps (additive enhancement)
- Create database layer to store timestamped segments while preserving current transcript workflow
- Integrate with existing SRTTranslator segment boundary validation rather than replacing it

### Phase 2: Database-Coordinated Translation

**Current Process (Preserve):** Existing batch language detection and translation quality (83% coverage)
**Enhanced Process:** Database-coordinated translation using proven timing mechanisms

**Strategic Integration:**
- Leverage existing batch language detection capabilities (already excellent with 83% coverage)
- Use database segments to coordinate existing translation workflows rather than replacing them
- Preserve proven timing preservation mechanisms from current SRTTranslator
- Build upon existing translation quality validation rather than recreating

### Phase 3: Database Schema Evolution

**New Primary Entity: `subtitle_segments`**
```sql
CREATE TABLE subtitle_segments (
    id INTEGER PRIMARY KEY,
    interview_id INTEGER,
    start_time REAL,  -- Precise timestamp from ElevenLabs
    end_time REAL,    -- Precise timestamp from ElevenLabs
    original_text TEXT,
    german_text TEXT,
    english_text TEXT,
    hebrew_text TEXT,
    confidence_score REAL,
    segment_index INTEGER
);
```

**Derived Entity: `transcripts` (view from segments)**
```sql
CREATE VIEW transcripts AS 
SELECT interview_id, 
       GROUP_CONCAT(original_text, ' ') as original_transcript,
       GROUP_CONCAT(german_text, ' ') as german_transcript,
       -- etc.
FROM subtitle_segments 
GROUP BY interview_id 
ORDER BY segment_index;
```

### Phase 4: Quality Validation Framework

**Synchronization Testing:**
- Automated validation of subtitle timing against video duration
- Sample-based verification of speech-subtitle alignment
- Quality metrics: segment accuracy, timing drift, translation consistency

**Validation Metrics:**
- **Timing Accuracy**: >95% of segments within 500ms of actual speech
- **Segment Boundaries**: Natural speech pauses, no mid-word cuts
- **Translation Consistency**: Terminology consistent across segments within interview

## External Dependencies

**No New Dependencies Required:**
- ElevenLabs Scribe API already provides word-level timestamps
- DeepL and OpenAI APIs handle segmented translation
- Current database supports schema additions
- Existing SRT generation code needs modification, not replacement

**API Usage Changes:**
- **ElevenLabs**: Parse additional timestamp fields from existing API response
- **DeepL**: Send shorter text segments instead of full transcripts (may reduce costs)
- **OpenAI**: Provide context instructions for segment-based Hebrew translation

## Strategic Refactor Approach

**Preservation Strategy:**
1. Build database layer around existing SRTTranslator core (67% coverage, proven timing validation)
2. Enhance existing ElevenLabs integration to capture timestamps without breaking current quality
3. Coordinate existing translation workflows through database segments rather than replacing them
4. Extend existing comprehensive test suite (67-83% coverage) rather than rebuilding
5. Maintain all current CLI interfaces while adding database coordination capabilities

**Data Enhancement:**
- Preserve all existing transcript data and workflows
- Add subtitle_segments table as coordination layer
- Existing processing maintains current functionality
- Enhanced processing adds database segment storage
- No disruption to current operational interviews