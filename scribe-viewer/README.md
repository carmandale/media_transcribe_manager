# Scribe Viewer

Web interface for viewing and searching transcribed interviews from the Scribe project.

## Overview

Scribe Viewer provides a modern web interface for:
- Browsing interview gallery with thumbnails
- Searching transcripts across languages
- Viewing synchronized video with multi-language subtitles
- Administrative interface for interview management

## Prerequisites

- Node.js 18+ 
- pnpm package manager
- FFmpeg (for thumbnail generation)

## Installation

```bash
# Install dependencies
pnpm install

# Generate static thumbnails for all videos
node scripts/generate-thumbnails.js

# Start development server
pnpm dev
```

## Scripts

### Thumbnail Generation

The viewer displays static thumbnails for video interviews in the gallery. These thumbnails must be generated manually when new videos are added:

```bash
node scripts/generate-thumbnails.js
```

This script:
- Reads all interviews from `public/manifest.json`
- Generates thumbnails for video files at 320x180 resolution
- Skips audio-only interviews (they display an audio icon instead)
- Saves thumbnails to `public/thumbnails/{interview-id}.jpg`
- Uses FFmpeg to extract frames from 10 seconds into each video

**When to run:**
- After adding new video interviews
- When thumbnails are missing or corrupted
- Before deploying to production

**Output:**
- ✅ Successfully generated thumbnails
- ⚠️ Skipped audio-only files (expected behavior)
- ❌ Failed generations (usually due to missing video files)

### Manifest Generation

The interview manifest must be generated from the database:

```bash
# From the parent scribe directory
python scripts/build_manifest.py
```

This creates `public/manifest.json` which contains all interview metadata.

## Development

```bash
# Start development server
pnpm dev

# Build for production
pnpm build

# Run production server
pnpm start

# Run tests
pnpm test

# Lint code
pnpm lint
```

## Project Structure

```
scribe-viewer/
├── app/                    # Next.js 13+ app directory
│   ├── gallery/           # Gallery page
│   ├── viewer/[id]/       # Video viewer page
│   ├── search/            # Search page
│   └── admin/             # Admin interface
├── components/            # React components
├── lib/                   # Utility functions
├── public/               
│   ├── media/            # Symlinked media files
│   ├── thumbnails/       # Generated thumbnails
│   └── manifest.json     # Interview metadata
└── scripts/
    └── generate-thumbnails.js  # Thumbnail generation script
```

## Features

### Gallery View
- Grid layout of interview cards
- Static thumbnails for videos
- Audio icon for audio-only interviews
- Displays interviewee name, date, and available languages

### Video Viewer
- Synchronized playback with subtitles
- Language selector for subtitles
- Keyboard controls (space to play/pause, arrows to seek)
- Fullscreen support

### Search
- Full-text search across all transcripts
- Results grouped by interview
- Direct links to specific timestamps
- Language indicators

### Admin Interface
- Protected by HTTP Basic Auth (see ADMIN_AUTH.md)
- Interview management
- Reindex functionality
- Metadata editing

## Deployment

1. Generate thumbnails: `node scripts/generate-thumbnails.js`
2. Build application: `pnpm build`
3. Set environment variables (see .env.example)
4. Deploy the `.next` directory and `public` folder

## Troubleshooting

### Missing Thumbnails
- Run `node scripts/generate-thumbnails.js`
- Check FFmpeg is installed: `ffmpeg -version`
- Verify video files exist in `public/media/`

### Videos Not Playing
- Check media symlinks are valid
- Verify video file permissions
- Check browser console for errors

### Search Not Working
- Regenerate manifest: `python scripts/build_manifest.py`
- Check manifest.json exists and is valid JSON
- Verify transcript data in manifest

## Related Documentation

- [Admin Authentication](ADMIN_AUTH.md)
- [Production Readiness](PRODUCTION_READINESS.md)
- [Testing Guide](tests/README.md)
- [Main Scribe Documentation](../README.md)