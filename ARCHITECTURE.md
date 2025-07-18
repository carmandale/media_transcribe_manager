# Scribe System Architecture

## 🏗️ High-Level Architecture

Scribe is a dual-component system designed for historical interview preservation:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SCRIBE SYSTEM ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────────┐ │
│  │    CORE PROCESSING      │    │         SCRIBE VIEWER                   │ │
│  │      (Python)           │    │        (Next.js/React)                  │ │
│  │                         │    │                                         │ │
│  │  ┌─────────────────┐    │    │  ┌─────────────────┐                   │ │
│  │  │   CLI Interface │    │    │  │   Web Interface │                   │ │
│  │  │  (scribe_cli.py)│    │    │  │  (Research UI)  │                   │ │
│  │  └─────────────────┘    │    │  └─────────────────┘                   │ │
│  │           │              │    │           │                             │ │
│  │  ┌─────────────────┐    │    │  ┌─────────────────┐                   │ │
│  │  │   Pipeline      │    │    │  │   Search Engine │                   │ │
│  │  │  (Orchestrator) │    │    │  │   (Client-side) │                   │ │
│  │  └─────────────────┘    │    │  └─────────────────┘                   │ │
│  │           │              │    │           │                             │ │
│  │  ┌─────────────────┐    │    │  ┌─────────────────┐                   │ │
│  │  │   Transcribe    │    │    │  │  Video Player   │                   │ │
│  │  │   Translate     │    │    │  │  (Synchronized) │                   │ │
│  │  │   Evaluate      │    │    │  └─────────────────┘                   │ │
│  │  └─────────────────┘    │    │           │                             │ │
│  │           │              │    │  ┌─────────────────┐                   │ │
│  │  ┌─────────────────┐    │    │  │  Admin Backend  │                   │ │
│  │  │    Database     │    │    │  │ (Metadata Edit) │                   │ │
│  │  │   (SQLite)      │    │    │  └─────────────────┘                   │ │
│  │  └─────────────────┘    │    │                                         │ │
│  └─────────────────────────┘    └─────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        SHARED DATA LAYER                               │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │   Input/    │  │   Output/   │  │  Database   │  │ manifest.json│   │ │
│  │  │ (Media)     │  │ (Results)   │  │ (SQLite)    │  │ (Web Index) │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📁 Directory Structure

```
media_transcribe_manager/
├── scribe/                          # Core Processing Engine
│   ├── __init__.py                  # Package initialization
│   ├── pipeline.py                  # Main orchestration logic
│   ├── transcribe.py                # ElevenLabs integration
│   ├── translate.py                 # Multi-provider translation
│   ├── evaluate.py                  # Quality assessment
│   ├── database.py                  # SQLite operations
│   ├── backup.py                    # Backup/restore system
│   ├── audit.py                     # System validation
│   ├── srt_translator.py            # Subtitle processing
│   └── utils.py                     # Helper functions
│
├── scribe-viewer/                   # Web Application
│   ├── app/                         # Next.js app directory
│   │   ├── page.tsx                 # Gallery homepage
│   │   ├── search/                  # Search results page
│   │   ├── viewer/[id]/             # Individual interview viewer
│   │   └── api/                     # Backend API routes
│   ├── components/                  # React components
│   ├── lib/                         # Utilities and types
│   ├── public/                      # Static assets
│   └── scripts/                     # Data processing scripts
│
├── tests/                           # Test suite
├── docs/                            # Documentation
├── utilities/                       # Maintenance scripts
├── scripts/                         # Processing scripts
├── output/                          # Processed results
├── backups/                         # System backups
├── scribe_cli.py                    # Command-line interface
└── requirements.txt                 # Python dependencies
```

## 🔄 Data Flow Architecture

### 1. Input Processing Flow
```
Media Files → CLI Add → Database Entry → Processing Queue
     ↓              ↓           ↓              ↓
[MP4/MP3/WAV] → [file_id] → [pending] → [transcription]
```

### 2. Core Processing Pipeline
```
Transcription → Translation → Evaluation → SRT Generation → Storage
      ↓              ↓            ↓             ↓            ↓
  [ElevenLabs] → [DeepL/OpenAI] → [GPT] → [WebVTT] → [output/{id}/]
```

### 3. Web Viewer Integration
```
Output Files → Manifest Script → manifest.json → Web Interface
      ↓              ↓              ↓              ↓
[Transcripts] → [Python Parser] → [JSON Index] → [React App]
```

## 🗄️ Database Schema

### Core Tables
```sql
-- Files table: Master record of all media files
CREATE TABLE files (
    file_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    original_filename TEXT,
    file_size INTEGER,
    duration REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processing status tracking
CREATE TABLE processing_status (
    file_id TEXT PRIMARY KEY,
    transcription_status TEXT DEFAULT 'pending',
    translation_en_status TEXT DEFAULT 'pending',
    translation_de_status TEXT DEFAULT 'pending',
    translation_he_status TEXT DEFAULT 'pending',
    evaluation_en_status TEXT DEFAULT 'pending',
    evaluation_de_status TEXT DEFAULT 'pending',
    evaluation_he_status TEXT DEFAULT 'pending',
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);

-- Quality evaluation results
CREATE TABLE evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    language TEXT NOT NULL,
    score REAL,
    feedback TEXT,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);
```

## 🔌 External API Integrations

### Transcription Service
- **Provider**: ElevenLabs Scribe
- **Purpose**: Audio/video to text conversion
- **Rate Limits**: Managed with retry logic
- **Error Handling**: Circuit breaker pattern

### Translation Services
- **Primary**: DeepL (English, German)
- **Secondary**: Microsoft Translator (Hebrew)
- **Fallback**: OpenAI GPT (all languages)
- **Quality**: Enhanced Hebrew validation

### Evaluation Service
- **Provider**: OpenAI GPT-4
- **Purpose**: Translation quality assessment
- **Scoring**: 1-10 scale with detailed feedback
- **Hebrew**: Enhanced cultural context evaluation

## 🌐 Web Viewer Architecture

### Frontend (Next.js/React)
```
┌─────────────────────────────────────────────────────────────┐
│                    SCRIBE VIEWER FRONTEND                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Gallery   │  │   Search    │  │      Viewer         │  │
│  │  (Homepage) │  │  (Results)  │  │   (Interview)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │                │                    │             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Interview   │  │ Search      │  │ Video Player +      │  │
│  │ Cards       │  │ Engine      │  │ Transcript Sync     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                    SHARED COMPONENTS                        │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Video       │  │ Transcript  │  │ Language            │  │
│  │ Controls    │  │ Viewer      │  │ Switcher            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Backend API (Next.js API Routes)
- **Health Check**: `/api/health`
- **Admin Auth**: `/api/admin/auth`
- **Metadata Edit**: `/api/admin/metadata`
- **Search Index**: `/api/search/index`

## 📊 File System Layout

### Output Directory Structure
```
output/
└── {file_id}/                       # Unique identifier directory
    ├── {file_id}.txt                # Original transcript
    ├── {file_id}_en.txt             # English translation
    ├── {file_id}_de.txt             # German translation
    ├── {file_id}_he.txt             # Hebrew translation
    ├── {file_id}.srt                # Original subtitles
    ├── {file_id}.orig.srt           # Backup original
    ├── {file_id}_en.srt             # English subtitles
    ├── {file_id}_de.srt             # German subtitles
    ├── {file_id}_he.srt             # Hebrew subtitles
    └── metadata.json                # Processing metadata
```

### Manifest Structure (Web Viewer)
```json
{
  "interviews": [
    {
      "id": "d6cc9262-5ba2-410c-a707-d981a7459105",
      "metadata": {
        "interviewee": "John Doe",
        "date": "1995-04-12",
        "summary": "Testimony regarding...",
        "duration": 3600,
        "languages": ["en", "de", "he"]
      },
      "assets": {
        "video": "/output/{id}/video.mp4",
        "transcripts": [
          {
            "language": "en",
            "file": "/output/{id}/{id}_en.txt",
            "cues": [
              {"time": 0.0, "text": "Interview begins..."},
              {"time": 5.2, "text": "My name is John Doe..."}
            ]
          }
        ],
        "subtitles": {
          "en": "/output/{id}/{id}_en.srt",
          "de": "/output/{id}/{id}_de.srt",
          "he": "/output/{id}/{id}_he.srt"
        }
      },
      "quality": {
        "transcription": 9.2,
        "translation_en": 8.8,
        "translation_de": 8.5,
        "translation_he": 8.9
      }
    }
  ],
  "metadata": {
    "generated": "2025-07-18T10:30:00Z",
    "total_interviews": 728,
    "total_duration": 2184000,
    "languages": ["en", "de", "he"]
  }
}
```

## 🔧 Component Interactions

### Core Processing → Web Viewer
1. **Data Generation**: Core processing creates transcripts and translations
2. **Manifest Building**: Python script scans output directory
3. **Index Creation**: Generates searchable manifest.json
4. **Web Consumption**: React app loads manifest for navigation and search

### Quality Control Workflow
1. **Processing**: Automated transcription and translation
2. **Web Review**: Researchers use viewer to validate quality
3. **Metadata Edit**: Admin interface allows corrections
4. **Re-processing**: Updated metadata triggers re-evaluation

### Search Architecture
1. **Index Building**: Manifest includes full-text content
2. **Client Search**: Fuse.js provides fuzzy search capabilities
3. **Result Display**: Contextual snippets with timestamp links
4. **Deep Linking**: Direct navigation to specific video moments

## 🚀 Deployment Architecture

### Development Environment
- **Core**: Python virtual environment with requirements.txt
- **Viewer**: Node.js with pnpm package management
- **Database**: Local SQLite file
- **Assets**: Local file system storage

### Production Environment (Planned)
- **Core**: Docker container with Python runtime
- **Viewer**: Static Next.js build served by CDN
- **Database**: SQLite with automated backups
- **Assets**: Object storage (S3-compatible)
- **Orchestration**: Docker Compose or Kubernetes

This architecture ensures separation of concerns while maintaining tight integration between the processing engine and user interface components.

