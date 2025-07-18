# Scribe Development Guide

## 🚀 Quick Start for AI Assistants

This guide provides essential context for AI code assistants working on the Scribe historical interview preservation system.

### Project Context
- **Purpose**: Historical interview transcription, translation, and research interface
- **Users**: Historians, researchers, archive administrators
- **Scale**: 728+ interviews processed, multi-language support (EN/DE/HE)
- **Architecture**: Python processing engine + Next.js web viewer

## 🛠️ Development Environment Setup

### Prerequisites
- Python 3.8+ with `uv` package manager
- Node.js 18+ with `pnpm`
- SQLite 3
- Git

### Core Processing Setup
```bash
# Install Python dependencies
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

# Set up environment variables
cp .env.template .env
# Edit .env with your API keys:
# ELEVENLABS_API_KEY=your_key
# DEEPL_API_KEY=your_key  
# OPENAI_API_KEY=your_key
# MS_TRANSLATOR_KEY=your_key

# Run tests to verify setup
python -m pytest tests/ --cov=scribe
```

### Web Viewer Setup
```bash
cd scribe-viewer
pnpm install
pnpm dev  # Starts development server on http://localhost:3000
```

## 📁 Key Files and Their Purpose

### Core Processing (`scribe/`)
- **`pipeline.py`**: Main orchestration logic - START HERE for processing flow
- **`transcribe.py`**: ElevenLabs integration for audio→text
- **`translate.py`**: Multi-provider translation (DeepL/OpenAI/MS)
- **`evaluate.py`**: Quality assessment using GPT-4
- **`database.py`**: SQLite operations with connection pooling
- **`scribe_cli.py`**: Command-line interface - entry point for operations

### Web Viewer (`scribe-viewer/`)
- **`app/page.tsx`**: Gallery homepage showing all interviews
- **`app/viewer/[id]/viewer-client.tsx`**: Main video+transcript interface
- **`scripts/build_manifest.py`**: **MISSING** - needs to be created
- **`lib/types.ts`**: TypeScript interfaces for data structures

### Configuration & Documentation
- **`PROJECT_VISION.md`**: High-level goals and user context
- **`ARCHITECTURE.md`**: System design and component relationships
- **`requirements.txt`**: Python dependencies
- **`scribe-viewer/package.json`**: Node.js dependencies

## 🔄 Common Development Workflows

### Adding New Media Files
```bash
# Add single file
uv run python scribe_cli.py add path/to/interview.mp4

# Add directory recursively  
uv run python scribe_cli.py add input/ --recursive

# Check status
uv run python scribe_cli.py status
```

### Processing Pipeline
```bash
# Full pipeline (transcribe + translate + evaluate)
uv run python scribe_cli.py process

# Individual steps
uv run python scribe_cli.py transcribe --workers 10
uv run python scribe_cli.py translate en --workers 8
uv run python scribe_cli.py evaluate en --sample 20
```

### Web Viewer Development
```bash
cd scribe-viewer

# Development server
pnpm dev

# Build for production
pnpm build

# Generate manifest (when script exists)
python scripts/build_manifest.py
```

## 🧪 Testing Guidelines

### Running Tests
```bash
# All tests with coverage
python -m pytest tests/ --cov=scribe --cov-report=term-missing

# Specific test file
python -m pytest tests/test_pipeline.py -v

# Unit tests only
python -m pytest tests/ -m unit
```

### Test Categories
- **Unit Tests**: Individual function testing with mocks
- **Integration Tests**: Component interaction testing
- **End-to-End Tests**: Full pipeline validation

### Current Test Issues (Need Fixing)
- 17 test failures in pipeline tests
- Missing dependencies for some test modules
- Context manager mocking problems (`AttributeError: __enter__`)

## 🔧 Code Quality Standards

### Python Code Style
- **Formatter**: Black with 88-character line length
- **Linter**: Flake8 with standard configuration
- **Type Hints**: Encouraged but not required
- **Docstrings**: Required for public functions

### TypeScript/React Standards
- **Formatter**: Prettier (configured in scribe-viewer)
- **Linter**: ESLint with Next.js configuration
- **Components**: Functional components with hooks
- **Styling**: Tailwind CSS with Radix UI components

### Git Workflow
- **Branches**: `feature/description` or `fix/description`
- **Commits**: Conventional commits format
- **PRs**: Required for all changes, include tests

## 🚨 Critical Development Notes

### Hebrew Translation Special Handling
- Hebrew requires Microsoft Translator or OpenAI (DeepL doesn't support Hebrew)
- Enhanced evaluation includes cultural context validation
- Right-to-left text rendering considerations in web viewer
- Special validation functions in `translate.py`

### Database Considerations
- SQLite with connection pooling for thread safety
- File IDs are UUIDs, not sequential integers
- Status tracking across multiple processing stages
- Backup system integrated with processing pipeline

### External API Rate Limits
- **ElevenLabs**: Managed with retry logic and circuit breakers
- **DeepL**: 500,000 character/month limit on free tier
- **OpenAI**: Rate limiting varies by model and tier
- **Error Handling**: Exponential backoff with jitter

### File System Layout
- **Input**: Any location, tracked by database
- **Output**: `output/{file_id}/` with standardized naming
- **Backups**: `backups/` with timestamped archives
- **Logs**: Application logs for debugging

## 🔍 Debugging Common Issues

### Processing Pipeline Problems
```bash
# Check stuck files
uv run python scribe_cli.py fix-stuck

# Database audit
uv run python scribe_cli.py db audit

# View detailed status
uv run python scribe_cli.py status --detailed
```

### Web Viewer Issues
```bash
# Check if manifest exists
ls -la scribe-viewer/public/manifest.json

# Verify Next.js build
cd scribe-viewer && pnpm build

# Check for TypeScript errors
cd scribe-viewer && pnpm lint
```

### API Key Problems
```bash
# Test API connectivity
uv run python -c "from scribe.transcribe import test_connection; test_connection()"

# Verify environment variables
uv run python scribe_cli.py version
```

## 📊 Performance Considerations

### Processing Optimization
- **Parallel Workers**: 10 for transcription, 8 for translation
- **Batch Sizes**: Configurable in pipeline settings
- **Memory Usage**: Monitor for large files (>2GB)
- **API Quotas**: Track usage to avoid rate limits

### Web Viewer Performance
- **Large Datasets**: 728+ interviews require virtual scrolling
- **Search Performance**: Client-side indexing with Fuse.js
- **Video Loading**: Lazy loading and progressive enhancement
- **Mobile Support**: Responsive design considerations

## 🔐 Security Guidelines

### API Key Management
- Never commit API keys to version control
- Use environment variables or secure secret management
- Rotate keys regularly
- Monitor usage for anomalies

### Data Handling
- Historical interviews may contain sensitive content
- Implement proper access controls for admin functions
- Audit trail for all metadata changes
- Secure backup storage

## 📈 Monitoring and Observability

### Current Logging
- Application logs in standard output
- Database operations logged
- API call success/failure tracking
- Processing pipeline status updates

### Planned Monitoring (Production)
- Prometheus metrics for processing rates
- Health checks for all components
- Alert system for failures
- Performance dashboards

## 🤖 AI Assistant Guidelines

### When Working on Core Processing
1. **Always check database schema** before modifying data operations
2. **Test with small datasets** before processing large batches
3. **Verify API key requirements** for new features
4. **Consider Hebrew special handling** for translation features

### When Working on Web Viewer
1. **Check manifest.json structure** for data expectations
2. **Test with multiple languages** including RTL (Hebrew)
3. **Verify video synchronization** with transcript changes
4. **Consider mobile responsiveness** for all UI changes

### When Writing Tests
1. **Mock external APIs** to avoid rate limits and costs
2. **Use temporary directories** for file system tests
3. **Clean up resources** in test teardown
4. **Test error conditions** not just happy paths

### Common Pitfalls to Avoid
- Don't modify database schema without migration strategy
- Don't hardcode file paths (use Path objects)
- Don't ignore rate limits on external APIs
- Don't break backward compatibility without version bump
- Don't commit large test files to repository

This guide should provide sufficient context for productive development work on the Scribe system.

