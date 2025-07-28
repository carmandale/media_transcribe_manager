# Spec Requirements Document

> Spec: Subtitle-First Architecture Redesign
> Created: 2025-07-28
> GitHub Issue: #79
> Status: Planning
> Priority: CRITICAL - Emergency fix for 0% synchronization rate

## Overview

Refactor the Scribe architecture to leverage the existing high-quality SRTTranslator core (67% test coverage, perfect timing preservation) while implementing a subtitle-first approach for new processing. This strategic refactor builds upon the substantial working codebase, particularly the proven segment boundary validation and translation timing mechanisms, while integrating database-centric coordination to address synchronization issues.

## User Stories

### Primary Story: Historian Video Research

As a historian researching testimonies, I want to watch videos with perfectly synchronized subtitles in my preferred language, so that I can accurately follow the speaker's words and cite specific moments with confidence.

**Current Problem**: Subtitles are completely out of sync with video, making the viewer unusable for research purposes.

**Required Workflow**: 
1. Historian opens video in viewer
2. Subtitles display at exact moment words are spoken
3. Historian can switch languages while maintaining perfect sync
4. Timing accuracy enables precise citation of testimony moments

### Secondary Story: System Administrator

As a system administrator, I want the processing pipeline to produce reliable subtitle files that work correctly with videos, so that historians can access the testimony collection without technical barriers.

**Current Problem**: Processing produces subtitle files with incorrect timing that don't align with video playback.

**Required Workflow**:
1. System processes interview files through subtitle-first pipeline
2. Generated SRT files have accurate timestamps matching video
3. All three languages (DE/EN/HE) maintain consistent timing
4. Quality validation confirms subtitle-video synchronization

## Spec Scope

1. **Preserve SRTTranslator Core** - Build database integration around existing timing validation and segment boundary logic
2. **Enhance ElevenLabs Integration** - Extend transcription parsing to capture word-level timestamps while preserving current quality
3. **Database Schema Evolution** - Add subtitle_segments table while maintaining existing transcript storage
4. **Strategic Refactor** - Database-centric coordination using proven translation engine as foundation
5. **Expand Testing Infrastructure** - Build upon existing comprehensive test suite (currently 67-83% coverage)

## Out of Scope

- Complete reprocessing of existing 728 interviews (will be separate task after validation)
- UI changes to the viewer application (current player works fine with correct SRT files)
- Translation service changes (DeepL/OpenAI integration remains the same)
- Backup/restore functionality changes

## Expected Deliverable

1. **Working Subtitle-Video Synchronization** - Demo videos play with perfectly aligned subtitles in all languages
2. **Validated Processing Pipeline** - Test runs produce SRT files that sync correctly with sample videos
3. **Quality Assurance Metrics** - Measurable synchronization accuracy (target: >95% of segments within 500ms tolerance)

## Spec Documentation

- Tasks: @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/tasks.md
- Technical Specification: @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/sub-specs/technical-spec.md
- API Specification: @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/sub-specs/api-spec.md
- Database Schema: @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/sub-specs/database-schema.md
- Tests Specification: @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/sub-specs/tests.md