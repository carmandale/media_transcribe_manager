# Architectural Decision Records (ADRs)

This directory contains records of significant architectural decisions made for the Scribe project.

## What is an ADR?

An Architectural Decision Record captures an important architectural decision made along with its context and consequences.

## Active ADRs

### [001 - Cleanup Refactor](001-cleanup-refactor.md)
**Date**: 2025-06-15  
**Status**: Accepted  
**Summary**: Massive codebase cleanup removing 80,000+ lines of legacy code.

### [002 - Hebrew Evaluation Approach](002-hebrew-evaluation.md)
**Date**: 2025-06-15  
**Status**: Proposed  
**Summary**: Approach for fixing Hebrew translation evaluation after cleanup.

## ADR Format

Each ADR follows this structure:

1. **Title**: ADR-NNN - Short descriptive title
2. **Status**: Proposed | Accepted | Deprecated | Superseded
3. **Context**: What motivated this decision?
4. **Decision**: What was decided?
5. **Consequences**: What are the results?

## Creating New ADRs

1. Copy the template from an existing ADR
2. Use next sequential number
3. Set status to "Proposed"
4. Update this README with the new entry