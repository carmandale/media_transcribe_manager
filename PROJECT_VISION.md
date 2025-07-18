# Scribe: Historical Interview Preservation System - Project Vision

## 🎯 Project Mission

**Scribe** is a comprehensive system designed to preserve historical interviews through accurate transcription, multi-language translation, and accessible digital presentation. Our mission is to make historical testimonies searchable, accessible, and preserved for future generations while maintaining the authentic voice and emotional context of the speakers.

## 🏗️ System Architecture Overview

Scribe consists of **two integrated components**:

### 1. **Core Processing Engine** (`scribe/`)
- **Purpose**: Automated transcription and translation pipeline
- **Technology**: Python-based CLI and library system
- **Capabilities**:
  - Audio/video transcription using ElevenLabs Scribe
  - Multi-language translation (English, German, Hebrew)
  - Quality evaluation and validation
  - SRT subtitle generation
  - Database tracking and management
  - Backup and recovery systems

### 2. **Scribe Viewer Web Application** (`scribe-viewer/`)
- **Purpose**: Quality control, research interface, and end-user access
- **Technology**: Next.js/React with TypeScript
- **Capabilities**:
  - Synchronized video playback with transcripts
  - Multi-language transcript viewing and comparison
  - Full-text search across all interviews
  - Metadata editing and quality control
  - Responsive web interface for researchers and historians

## 🔄 Data Flow Architecture

```
Input Media Files → Core Processing → Database → Manifest Generation → Web Viewer
     ↓                    ↓              ↓              ↓              ↓
[MP4/MP3/WAV]    [Transcribe/Translate] [SQLite]   [manifest.json]  [Research UI]
```

### Detailed Flow:
1. **Ingestion**: Media files added via CLI (`scribe_cli.py add`)
2. **Processing**: Automated transcription and translation pipeline
3. **Storage**: Results stored in database and file system (`output/`)
4. **Manifest**: Python script generates `manifest.json` for web viewer
5. **Access**: Researchers use web interface for quality control and research

## 🎯 Target Users

### Primary Users
- **Historians & Researchers**: Need to search, analyze, and cite historical interviews
- **Archive Administrators**: Manage metadata, quality control, and system operations
- **Quality Control Reviewers**: Validate transcription and translation accuracy

### Use Cases
- **Research**: "Find all mentions of 'Berlin' across 728 interviews"
- **Quality Control**: "Review Hebrew translation accuracy for interview #123"
- **Citation**: "Link to timestamp 15:32 in interview with specific quote"
- **Comparison**: "Compare German original with English translation side-by-side"

## 🛠️ Technology Stack

### Core Processing Engine
- **Language**: Python 3.8+
- **Database**: SQLite with connection pooling
- **APIs**: ElevenLabs (transcription), DeepL/OpenAI (translation)
- **CLI**: Click-based command interface
- **Testing**: pytest with comprehensive coverage

### Web Viewer Application
- **Framework**: Next.js 15 with React 19
- **Language**: TypeScript
- **UI**: Tailwind CSS + Radix UI components
- **Search**: Client-side with Fuse.js
- **Video**: HTML5 with custom controls
- **Deployment**: Static export capable

## 📊 Current Status (July 2025)

### ✅ Completed Components
- **Core Processing**: 728 files fully processed (transcribed + translated)
- **Database System**: SQLite with audit and backup capabilities
- **CLI Interface**: Full command-line management system
- **Web Viewer UI**: Modern React interface with video synchronization
- **Multi-language Support**: English, German, Hebrew with special Hebrew handling

### 🚧 Production Readiness Gaps
- **Test Stability**: 17 test failures need resolution
- **Integration**: Scribe Viewer not fully connected to core processing
- **Deployment**: Missing production configuration and CI/CD
- **Monitoring**: No production observability or error handling
- **Documentation**: Inconsistent and incomplete for AI assistants

## 🎯 Production Vision

### End-State Goals
1. **Reliable Processing**: 99.9% uptime for transcription/translation pipeline
2. **Fast Search**: Sub-5-second search across entire archive
3. **Quality Control**: Streamlined review workflow for accuracy validation
4. **Easy Deployment**: One-command deployment to any environment
5. **Scalable Architecture**: Handle 10,000+ interviews efficiently

### Success Metrics
- **Processing Speed**: <30 minutes per hour of audio
- **Search Performance**: <5 seconds for full-text search
- **Quality Scores**: >8.5/10 average translation quality
- **Uptime**: 99.9% system availability
- **User Experience**: <60 seconds to correct metadata via web interface

## 🔮 Future Roadmap

### Phase 1: Production Stabilization (Current)
- Fix test suite and establish CI/CD
- Complete Scribe Viewer integration
- Implement monitoring and error handling
- Create production deployment system

### Phase 2: Enhanced Features
- Advanced search with semantic similarity
- Automated speaker identification
- Integration with external archive systems
- Mobile-responsive improvements

### Phase 3: Scale & Performance
- Distributed processing capabilities
- Advanced caching and CDN integration
- Real-time collaboration features
- API for external integrations

## 🤝 Development Philosophy

### Core Principles
1. **Authenticity First**: Preserve original speech patterns and emotional context
2. **Quality Over Speed**: Accuracy is more important than processing speed
3. **Accessibility**: Make historical content discoverable and usable
4. **Reliability**: System must be dependable for historical preservation
5. **Transparency**: Clear audit trails and quality metrics

### AI Assistant Guidelines
- **Context**: This is a historical preservation system, not a general transcription tool
- **Quality**: Hebrew translations require special validation and enhanced evaluation
- **Integration**: Core processing and web viewer are tightly coupled components
- **Users**: Primarily historians and researchers, not general consumers
- **Data**: Sensitive historical content requiring careful handling

## 📋 Key Terminology

- **Interview**: A single audio/video file with associated transcripts and translations
- **File ID**: Unique identifier for each processed media file
- **Manifest**: JSON index file that powers the web viewer search and navigation
- **Cue**: Individual timestamped segment of transcript text
- **Quality Score**: 1-10 rating of translation accuracy and authenticity
- **Enhanced Evaluation**: Special Hebrew translation validation with cultural context

This vision document serves as the definitive guide for understanding Scribe's purpose, architecture, and development direction for both human developers and AI assistants.

