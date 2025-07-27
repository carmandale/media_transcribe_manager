# Scribe - Historical Interview Preservation System

This is a specialized tool for preserving and making accessible historical testimonies through automated transcription, translation, and intelligent search capabilities.

## Agent OS Documentation

### Product Context
- **Mission & Vision:** @.agent-os/product/mission.md
- **Technical Architecture:** @.agent-os/product/tech-stack.md
- **Development Roadmap:** @.agent-os/product/roadmap.md
- **Decision History:** @.agent-os/product/decisions.md

### Development Standards
- **Code Style:** @~/.agent-os/standards/code-style.md
- **Best Practices:** @~/.agent-os/standards/best-practices.md

### Project Management
- **Active Specs:** @.agent-os/specs/
- **Spec Planning:** Use `@~/.agent-os/instructions/create-spec.md`
- **Tasks Execution:** Use `@~/.agent-os/instructions/execute-tasks.md`

## Workflow Instructions

When asked to work on this codebase:

1. **First**, check @.agent-os/product/roadmap.md for current priorities
2. **Then**, follow the appropriate instruction file:
   - For new features: @~/.agent-os/instructions/create-spec.md
   - For tasks execution: @~/.agent-os/instructions/execute-tasks.md
3. **Always**, adhere to the standards in the files listed above

## Important Notes

- Product-specific files in `.agent-os/product/` override any global standards
- User's specific instructions override (or amend) instructions found in `.agent-os/specs/...`
- Always adhere to established patterns, code style, and best practices documented above

## Project-Specific Context

### Current Priorities (Phase 1)
1. **End-to-End Testing**: Achieve 25%+ test coverage
2. **Subtitle Bug Fix**: Verify and fix synchronization issues
3. **Error Handling**: Improve pipeline robustness

### Key Technical Decisions
- **Transcription**: ElevenLabs Scribe (best for historical content)
- **Translation**: DeepL (DE/EN), OpenAI GPT-4 (HE)
- **Database**: SQLite now, PostgreSQL for cloud deployment
- **Architecture**: Separate Python CLI and Next.js viewer

### Testing Commands
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=scribe --cov-report=html

# Run specific test file
pytest tests/test_transcribe.py
```

### Development Workflow
```bash
# Add new interview files
python scribe_cli.py add /path/to/files/

# Process interviews
python scribe_cli.py process

# Check status
python scribe_cli.py status

# Launch viewer
./start.sh
```