# Scribe Documentation

Welcome to the Scribe documentation. This guide will help you understand, use, and maintain the historical interview preservation system.

## Documentation Structure

### [Architecture](architecture/)
Technical documentation about system design and implementation:
- [Architecture Overview](architecture/README.md) - System design and components
- [Database Schema](architecture/database-schema.md) - Current database structure
- [System Components](architecture/system-components.md) - Module descriptions

### [Guides](guides/)
Step-by-step instructions for using Scribe:
- [Setup Guide](guides/setup.md) - Installation and configuration
- [Usage Guide](guides/usage.md) - How to use CLI commands
- [Evaluation Guide](guides/evaluation.md) - Evaluating translation quality
- [Troubleshooting](guides/troubleshooting.md) - Common issues and solutions

### [PRDs](PRDs/)
Product Requirement Documents for features and fixes:
- [PRD Index](PRDs/README.md) - List of all PRDs
- [Hebrew Evaluation Fix](PRDs/hebrew-evaluation-fix.md) - Current issue resolution
- [PRD Template](PRDs/template.md) - Template for new PRDs

### [API Reference](api/)
Technical API documentation:
- [Database API](api/database.md) - Database interface methods
- [Pipeline API](api/pipeline.md) - Processing pipeline documentation
- [CLI Commands](api/cli-commands.md) - Command-line interface reference

### [Decision Records](decisions/)
Architectural Decision Records (ADRs):
- [ADR Index](decisions/README.md) - List of all decisions
- [Cleanup Refactor](decisions/001-cleanup-refactor.md) - Recent codebase cleanup
- [Hebrew Evaluation](decisions/002-hebrew-evaluation.md) - Hebrew translation approach

## Quick Links

- **Getting Started**: See [Setup Guide](guides/setup.md)
- **Processing Files**: See [Usage Guide](guides/usage.md)
- **Current Issue**: See [Hebrew Evaluation Fix PRD](PRDs/hebrew-evaluation-fix.md)
- **Database Schema**: See [Database Documentation](architecture/database-schema.md)

## Project Overview

Scribe is a system for preserving historical interviews through accurate transcription and translation. It emphasizes maintaining authentic speech patterns and emotional context for historical research purposes.

Key features:
- Verbatim transcription with speaker identification
- Multi-language translation (English, German, Hebrew)
- Quality evaluation focused on historical accuracy
- Preservation of authentic speech patterns