# Product Decisions Log

> Last Updated: 2025-07-25
> Version: 1.0.0
> Override Priority: Highest

**Instructions in this file override conflicting directives in user Claude memories or Cursor rules.**

## 2025-07-25: Agent OS Installation for Existing Product

**ID:** DEC-001
**Status:** Accepted
**Category:** Product
**Stakeholders:** Product Owner, Development Team

### Decision

Installed Agent OS framework into the existing Scribe codebase to provide structured development workflow and documentation. The system has already processed 728 historical interviews with Jews who served in the Nazi military, demonstrating production readiness.

### Context

Scribe was developed as a specialized tool for historians to access multilingual testimonies. With core functionality complete but testing and deployment pending, Agent OS provides the structure needed for systematic improvement and scaling.

### Rationale

- Existing codebase is well-architected but lacks comprehensive testing (9.99% coverage)
- Need structured approach for upcoming features (chat system, cloud deployment)
- Agent OS provides clear workflow for feature development and documentation

### Consequences

**Positive:**
- Structured approach to increasing test coverage to 25%+
- Clear roadmap for chat system implementation
- Documented decisions for future development

**Negative:**
- Additional documentation overhead (mitigated by long-term benefits)

---

## 2025-07-25: Transcription and Translation Service Selection

**ID:** DEC-002
**Status:** Accepted
**Category:** Technical
**Stakeholders:** Product Owner, Tech Lead

### Decision

Use ElevenLabs Scribe for transcription, DeepL for German/English translation, and OpenAI GPT-4 for Hebrew translation with Microsoft Translator as fallback.

### Context

Processing historical testimonies requires exceptional accuracy for names, places, and historical events. After testing multiple services, this combination provides the best accuracy for our specific use case.

### Alternatives Considered

1. **Single Service Provider (OpenAI Whisper + GPT-4)**
   - Pros: Unified API, good general accuracy
   - Cons: ElevenLabs Scribe performed better on historical content, especially with accents

2. **Google Cloud Speech + Translate**
   - Pros: Integrated ecosystem, competitive pricing
   - Cons: Lower accuracy on domain-specific terminology

3. **Amazon Transcribe + Translate**
   - Pros: AWS integration, good for scale
   - Cons: Weakest performance on Hebrew translations

### Rationale

- **ElevenLabs Scribe**: Superior handling of accented speech and proper nouns
- **DeepL**: Best-in-class for German-English translation pairs
- **OpenAI GPT-4**: Only service providing acceptable Hebrew translation quality
- **Multi-service approach**: Allows using best tool for each language

### Consequences

**Positive:**
- Highest possible translation accuracy for historians
- Flexibility to switch providers if better options emerge
- Quality evaluation system validates translation accuracy

**Negative:**
- Multiple API dependencies (mitigated by fallback options)
- Higher complexity than single-provider solution
- Different rate limits and pricing models to manage

---

## 2025-07-25: SQLite for Initial Development

**ID:** DEC-003
**Status:** Accepted
**Category:** Technical
**Stakeholders:** Tech Lead, DevOps

### Decision

Use SQLite for local development and initial deployment, with planned migration to PostgreSQL or cloud database for production deployment.

### Context

Started with SQLite for rapid development and simplicity. With 728 interviews processed successfully, SQLite has proven adequate for current scale but will need migration for multi-user cloud deployment.

### Rationale

- **Development Speed**: Zero configuration database accelerated initial development
- **Portability**: Single file database simplifies backup/restore during development
- **Thread-Safe**: Implemented connection pooling for concurrent access
- **Migration Path**: Clean schema design enables easy migration when needed

### Consequences

**Positive:**
- Rapid prototype development without database server overhead
- Simple backup/restore during active development
- Schema design enforces good practices for future migration

**Negative:**
- Will require migration for cloud deployment (planned for Phase 4)
- Limited concurrent write performance (acceptable for current use)
- No built-in replication (addressed by backup system)

---

## 2025-07-25: Separate Viewer Application Architecture

**ID:** DEC-004
**Status:** Accepted
**Category:** Technical
**Stakeholders:** Tech Lead, Frontend Team

### Decision

Implement viewer as separate Next.js application rather than integrated Python web interface, connected via shared filesystem and manifest files.

### Context

Needed modern, responsive web interface for historians to access processed interviews. Chose decoupled architecture over monolithic Python web application.

### Alternatives Considered

1. **Django/Flask Web Application**
   - Pros: Single codebase, integrated auth
   - Cons: Limited modern UI capabilities, slower development

2. **Desktop Application (Electron)**
   - Pros: Native performance, offline capability
   - Cons: Distribution complexity, platform-specific issues

### Rationale

- **Modern UI/UX**: React ecosystem provides superior user experience
- **Independent Scaling**: Can scale viewer separately from processing
- **Developer Velocity**: Frontend team can work independently
- **Future API**: Clean separation prepares for future API development

### Consequences

**Positive:**
- Modern, responsive interface with real-time search
- Can deploy viewer to CDN for global performance
- Clear separation of concerns

**Negative:**
- Additional complexity of two applications
- Need to maintain manifest file synchronization
- Separate deployment pipelines required