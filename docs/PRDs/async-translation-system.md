# Product Requirements Document: Async Translation System

## Executive Summary

This PRD outlines the requirements for modernizing the Scribe translation system to support production-grade asynchronous processing with proper queue management, resilience patterns, and observability.

## Problem Statement

### Current Issues
1. **Synchronous Blocking**: Translation operations block the CLI, causing timeouts for large batches
2. **Poor Concurrency**: Multiple workers compete for API access without coordination
3. **No Retry Logic**: Failed translations require manual intervention
4. **Limited Observability**: No metrics or detailed progress tracking
5. **Fragile Operations**: API rate limits and timeouts cause batch failures

### Impact
- Hebrew translations at 96% completion with 28 files stuck
- CLI timeouts prevent efficient batch processing
- Manual intervention required for failures
- No visibility into system performance

## Goals & Objectives

### Primary Goals
1. **100% Translation Completion**: Ensure all files can be translated without manual intervention
2. **Scalable Performance**: Support concurrent translation with optimal throughput
3. **Production Reliability**: 99.9% success rate with automatic recovery
4. **Real-time Visibility**: Live progress tracking and system metrics

### Success Metrics
- Translation completion rate: >99.9%
- Average translation time: <30s per document
- System uptime: 99.9%
- Zero manual interventions for standard operations

## Proposed Solution

### Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   CLI/API   │────▶│ Message Queue│────▶│   Workers   │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                     │
       ▼                    ▼                     ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Progress   │     │   Monitor    │     │ Translation │
│   Events    │     │   Service    │     │  Services   │
└─────────────┘     └──────────────┘     └─────────────┘
```

### Core Components

#### 1. Async Translation Service
```python
class AsyncTranslationService:
    - Async/await pattern throughout
    - Connection pooling for API clients
    - Structured error handling
    - Progress streaming
```

#### 2. Job Queue System
- **Technology**: Redis + Celery (or AWS SQS for cloud)
- **Features**:
  - Priority queues (Hebrew > German > English)
  - Dead letter queue for failed jobs
  - Job persistence and replay
  - Distributed locking for deduplication

#### 3. Worker Pool Management
- **Auto-scaling**: Based on queue depth and API limits
- **Resource Limits**: Per-provider rate limiting
- **Health Checks**: Automatic worker recovery
- **Load Balancing**: Round-robin across providers

#### 4. Resilience Layer
- **Circuit Breakers**: Prevent cascade failures
- **Retry Logic**: Exponential backoff with jitter
- **Bulkheads**: Isolated failure domains
- **Timeouts**: Configurable per operation type

#### 5. Observability Stack
- **Metrics**: Prometheus + Grafana
- **Logging**: Structured logs with correlation IDs
- **Tracing**: OpenTelemetry for distributed tracing
- **Alerting**: PagerDuty/Slack integration

## Technical Requirements

### API Integration

```python
# OpenAI Client Configuration
client = AsyncOpenAI(
    api_key=api_key,
    timeout=httpx.Timeout(60.0, connect=5.0),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    http2=True
)

# Rate Limiter Configuration
rate_limiter = RateLimiter(
    providers={
        'openai': {'rpm': 500, 'tpm': 150000},
        'deepl': {'rpm': 300, 'characters': 500000},
        'microsoft': {'rpm': 1000, 'characters': 1000000}
    }
)
```

### Database Schema Updates

```sql
-- Add job tracking table
CREATE TABLE translation_jobs (
    job_id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    target_language TEXT NOT NULL,
    status TEXT NOT NULL, -- queued, processing, completed, failed
    priority INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    worker_id TEXT,
    FOREIGN KEY (file_id) REFERENCES media_files(file_id)
);

-- Add metrics table
CREATE TABLE translation_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    duration_ms INTEGER,
    tokens_used INTEGER,
    cost_cents INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES translation_jobs(job_id)
);
```

### CLI Interface Updates

```bash
# Async translation commands
scribe translate he --async --priority=high
scribe translate all --async --workers=auto

# Monitoring commands
scribe jobs list --status=pending
scribe jobs retry --failed
scribe jobs cancel <job_id>

# Progress tracking
scribe status --follow
scribe progress <file_id>

# Metrics and health
scribe metrics --provider=openai --period=1h
scribe health --verbose
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1-2)
1. Set up Redis/queue infrastructure
2. Implement async translation service
3. Create job management system
4. Add basic retry logic

### Phase 2: Resilience & Scaling (Week 3-4)
1. Implement circuit breakers
2. Add rate limiting per provider
3. Create worker auto-scaling
4. Set up health monitoring

### Phase 3: Observability (Week 5)
1. Integrate Prometheus metrics
2. Set up Grafana dashboards
3. Implement structured logging
4. Add OpenTelemetry tracing

### Phase 4: Production Hardening (Week 6)
1. Load testing and optimization
2. Failure scenario testing
3. Documentation and runbooks
4. Team training

## Migration Strategy

### Backward Compatibility
- Existing synchronous mode remains default
- `--async` flag enables new system
- Gradual migration of existing jobs

### Data Migration
```python
# Migration script to import existing pending translations
async def migrate_pending_translations():
    pending = db.get_pending_translations()
    for file in pending:
        await queue.submit_job(
            file_id=file.id,
            target_language=file.target_lang,
            priority=HIGH if file.target_lang == 'he' else NORMAL
        )
```

## Risk Analysis

### Technical Risks
1. **API Rate Limits**: Mitigation - intelligent rate limiting and backoff
2. **Queue Overflow**: Mitigation - auto-scaling and priority queues
3. **Data Loss**: Mitigation - persistent queues and job replay

### Operational Risks
1. **Complexity**: Mitigation - comprehensive monitoring and alerts
2. **Dependencies**: Mitigation - fallback to sync mode if queue unavailable

## Security Considerations

1. **API Key Management**: Use environment variables or secrets manager
2. **Queue Security**: Enable Redis AUTH and SSL/TLS
3. **Data Privacy**: No PII in logs or metrics
4. **Access Control**: Role-based permissions for job management

## Success Criteria

1. **All 728 files translated** to Hebrew within 2 hours using async mode
2. **Zero manual interventions** during standard operations
3. **Real-time progress** visible in CLI and web dashboard
4. **Automatic recovery** from transient failures
5. **Cost optimization** through intelligent batching and caching

## Future Enhancements

1. **Web Dashboard**: Real-time translation monitoring UI
2. **Smart Routing**: ML-based provider selection
3. **Cost Optimization**: Automatic model selection based on content
4. **Caching Layer**: Reduce redundant translations
5. **Webhook Support**: Push notifications for job completion

## Appendix

### Technology Stack
- **Languages**: Python 3.11+
- **Queue**: Redis 7.0+ or AWS SQS
- **Task Processing**: Celery 5.3+
- **Async HTTP**: httpx with HTTP/2
- **Monitoring**: Prometheus + Grafana
- **Logging**: structlog + Elasticsearch

### Reference Architecture
- [Twelve-Factor App](https://12factor.net/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Bulkhead Pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/bulkhead)

### Performance Benchmarks
- Single worker: ~5 translations/minute
- Target with async: 50-100 translations/minute
- API limits: OpenAI (500 RPM), DeepL (300 RPM)

---

**Document Version**: 1.0  
**Last Updated**: December 2024  
**Author**: Scribe Development Team  
**Status**: Draft for Review