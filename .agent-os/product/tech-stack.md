# Technical Stack

> Last Updated: 2025-07-25
> Version: 1.0.0

## Core Technologies

### Application Framework
- **Framework:** Python CLI Application
- **Version:** Python 3.8+
- **Language:** Python with Type Hints

### Database
- **Primary:** SQLite
- **Version:** 3.x
- **ORM:** Direct SQL with thread-safe connection pooling

## Backend Stack

### Package Management
- **Tool:** uv (Astral)
- **Version:** Latest
- **Virtual Environment:** .venv

### CLI Framework
- **Library:** Click
- **Version:** 8.1.7
- **Command Structure:** Modular subcommands

### External APIs
- **Transcription:** ElevenLabs Scribe API
- **Translation (Primary):** DeepL API
- **Translation (Hebrew):** OpenAI GPT-4
- **Translation (Fallback):** Microsoft Translator

### Testing Framework
- **Framework:** pytest
- **Version:** 8.3.4
- **Coverage:** pytest-cov

## Frontend Stack

### JavaScript Framework
- **Framework:** Next.js
- **Version:** 15.1.0
- **Build Tool:** Next.js built-in (Turbopack)

### Import Strategy
- **Strategy:** Node.js modules
- **Package Manager:** pnpm
- **Node Version:** 20.x LTS

### CSS Framework
- **Framework:** Tailwind CSS
- **Version:** 3.4.1
- **PostCSS:** Yes

### UI Components
- **Library:** Radix UI
- **Version:** Latest
- **Styling:** Tailwind CSS classes

### Client-Side Search
- **Library:** Fuse.js
- **Version:** 7.0.0
- **Implementation:** In-browser search

### Video Player
- **Technology:** HTML5 Video
- **Controls:** Custom React components
- **Subtitles:** WebVTT/SRT format

## Assets & Media

### Fonts
- **Provider:** Next.js Font Optimization
- **Loading Strategy:** Self-hosted with font-display swap

### Icons
- **Library:** Lucide React
- **Implementation:** React components
- **Version:** 0.469.0

## Infrastructure

### Application Hosting
- **Platform:** TBD (Cloud deployment planned)
- **Service:** TBD
- **Region:** TBD

### Database Hosting
- **Provider:** Local SQLite (current)
- **Service:** File-based
- **Backups:** Manual backup/restore commands

### Asset Storage
- **Provider:** Local filesystem
- **Structure:** UUID-based organization in output/
- **Media Files:** MP3, MP4, WAV support

## Deployment

### Current State
- **Local Development:** Python venv + pnpm
- **Viewer Launch:** start.sh script
- **Processing:** CLI-based execution

### Planned CI/CD Pipeline
- **Platform:** TBD
- **Trigger:** TBD
- **Tests:** Run before deployment

### Environments
- **Production:** TBD
- **Staging:** TBD
- **Development:** Local only (current)

## Code Repository
- **URL:** https://github.com/[TBD]
- **Version Control:** Git
- **Branch Strategy:** main branch development

## Development Tools

### Code Quality
- **Python Linting:** TBD (ruff recommended)
- **TypeScript:** Built-in Next.js TypeScript support
- **Pre-commit Hooks:** TBD

### Documentation
- **API Docs:** Code comments and CLI help
- **User Docs:** docs/ directory with guides
- **README:** Comprehensive setup instructions