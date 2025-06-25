# Product Requirements Document: Scribe Viewer Web Application

## 1. Executive Summary
This document outlines the requirements for a modern, local-first web application designed for historians and researchers to explore the Scribe project's archive of historical interviews. The application will provide an intuitive interface for viewing videos with synchronized, multilingual transcripts and subtitles, powerful search capabilities, and a simple administrative backend for metadata management.

## 2. Problem Statement
The current Scribe system produces a wealth of valuable data (videos, transcripts, translations), but it is stored in a decentralized, file-based format. This makes it incredibly difficult for a researcher to:
- **Discover Content:** There is no way to search for keywords, names, or places across all interviews simultaneously.
- **Navigate Efficiently:** A user must manually open files to find relevant information, a time-consuming and inefficient process.
- **Analyze in Context:** Comparing different language translations or viewing a transcript alongside the video requires multiple applications and manual synchronization.
- **Curate Metadata:** Initial metadata is often incomplete or requires expert correction, but there is no easy way to update it.
- **Accessibly Share:** There is no simple, user-friendly way to view the interviews without direct access to the file system and the necessary media players.

The value of this historical goldmine is currently locked away by a technical barrier. This project aims to remove that barrier.

## 3. Goals & Objectives

### Primary Goals
- **Build an Intuitive Viewing Experience:** Create a seamless interface for watching interviews with synchronized transcripts.
- **Enable Powerful Discovery:** Allow researchers to search the entire archive instantly.
- **Facilitate Easy Curation:** Provide a simple, secure way for administrators to edit and improve interview metadata.
- **Ensure High Performance:** The application must be fast and responsive, even when handling large amounts of text data.
- **Local-First, Deployable Design:** The application must run entirely locally but be structured for easy deployment to a web server.

### Success Metrics
- A historian can find all mentions of a specific keyword across all interviews in under 5 seconds.
- An administrator can log in and correct an interviewee's name in under 60 seconds.
- The UI can smoothly handle and display transcripts of any length while maintaining video synchronization.
- The entire application can be launched with a single command locally.

## 4. User Personas
- **Primary Persona: The Historian/Researcher**
  - **Needs:** To quickly find specific topics, names, and events within hours of video content. Needs to verify translation accuracy by comparing languages side-by-side. Needs to cite specific moments in time.
  - **Pain Points:** Wasting hours scrubbing through video timelines. Inability to search across an entire project. Losing context when switching between a video player and a text document.
- **Secondary Persona: The Archive Administrator**
  - **Needs:** A simple interface to correct or add metadata (like names, dates, and summaries) as more information becomes available.
  - **Pain Points:** Manually editing JSON files is error-prone and requires technical knowledge. No central place to manage archive-wide metadata.

## 5. Proposed Solution & Features

### Core Architecture
A three-tiered application:
1.  **Data Pre-processing Script:** A Python script that scans the `output` directory, intelligently parses metadata from original filenames, and generates a single `manifest.json` file. This script will be run once to build the index, and again whenever new interviews are added.
2.  **Front-End Web Application:** A modern single-page application (SPA) that consumes the `manifest.json` file to render the user interface for viewing and searching.
3.  **Backend API (for Admin):** A lightweight backend server (e.g., Python/Flask or Node.js/Express) that serves the front-end and provides a secure API endpoint for updating the `manifest.json` file.

### Feature Breakdown

#### F1: The Gallery (Homepage)
- A grid or list view of all available interviews.
- Each interview card will display:
  - A video thumbnail.
  - Interviewee's name.
  - Interview date.
  - A short summary or description.
- A prominent, top-level search bar.
- Filters to sort and view interviews by date, name, or other available metadata.

#### F2: The Search Engine
- The search bar on the gallery page will search across all transcripts in all languages.
- Search results will be displayed on a dedicated page, grouped by interview.
- Each result will show the keyword in context (a text snippet) and will be a direct deep-link to the specific timestamp in the video where that phrase is spoken.
- The search should be client-side, using the pre-built index for maximum speed and local-first compatibility.

#### F3: The Viewer Page
- A two-panel layout:
  - **Left Panel (Video Player):**
    - A clean, modern HTML5 video player.
    - Controls for play/pause, volume, fullscreen, and playback speed (0.5x, 1x, 1.5x, 2x).
    - A dropdown menu to select the active subtitle track (EN, DE, HE, or subtitles off).
  - **Right Panel (Transcript Viewer):**
    - Displays the full transcript for a selected language.
    - A dropdown to switch between transcript languages (EN, DE, HE).
    - As the video plays, the currently spoken phrase/sentence is automatically highlighted.
    - The panel auto-scrolls to keep the highlighted text in view.
    - **Crucially, clicking on any text in the transcript will seek the video player to that exact time.**

#### F4: The Admin Backend
- **Secure Access:** A simple, password-protected login page (`/admin`). The password will be configured via an environment variable for security and ease of setup.
- **Interview List:** A simple list of all interviews in the manifest.
- **Metadata Editor:** Clicking an interview opens a form where an admin can edit fields like `interviewee`, `date`, and `summary`.
- **Save Functionality:** A "Save" button that sends the updated metadata to the backend API, which then updates the `manifest.json` file on the server. The front-end will then be prompted to refresh its data.

## 6. Technical Stack Recommendations
- **Data Pre-processing:**
  - **Python:** To script the indexing of the `output` directory and parse filenames.
  - **VTT Generation:** The script should convert existing `.srt` files to the more flexible `.vtt` format, which is standard for web video and easily manipulated with JavaScript.
- **Front-End Application:**
  - **Framework:** React or Vue (using a framework like Next.js or Nuxt.js is highly recommended for its structure and performance optimizations).
  - **Search Library:** A client-side library like [Fuse.js](https://fusejs.io/) or [FlexSearch](https://github.com/nextapps-de/flexsearch) to enable fast, fuzzy searching on the `manifest.json` data.
  - **Styling:** A modern CSS framework like Tailwind CSS for rapid, clean UI development.
  - **Video Player:** A customizable library like [Plyr.io](https://plyr.io/) or a custom-built player using the standard HTML5 video API.
- **Admin Backend API:**
  - **Framework:** A lightweight Python framework like **Flask** or a Node.js framework like **Express.js**. This keeps the backend simple, with its primary role being to serve the app and handle file I/O for the manifest.

## 7. Data Structure & Processing

### Filename-based Metadata Extraction
The Python pre-processing script will attempt to parse metadata from the original filenames stored in the database. It will use regular expressions to look for common patterns to extract initial data for:
- Interviewee Name
- Interview Date
- Other potential identifiers

This data provides a baseline that can be corrected or augmented via the Admin Backend.

### Manifest `manifest.json`
The structure remains the same, but will now be initially populated by the intelligent parsing script and can be updated via the admin API.

```json
[
  {
    "id": "d6cc9262-5ba2-410c-a707-d981a7459105",
    "metadata": {
      "interviewee": "John Doe", // Initially parsed from filename
      "date": "1995-04-12",      // Initially parsed from filename
      "summary": "Testimony regarding experiences in..." // Can be added by admin
    },
    // ... rest of the structure ...
  }
]
```

## 8. Implementation Plan

- **Phase 1: Data Processing & Core Viewer**
  1. Develop the Python script to scan `output`, parse metadata from filenames, convert SRT to VTT, and generate the `manifest.json`.
  2. Build the basic Viewer page that can load a single interview from the manifest and display the video.
  3. Implement the synchronized highlighting and auto-scrolling of the transcript.

- **Phase 2: Gallery & Navigation**
  1. Build the Gallery homepage that dynamically lists all interviews from the manifest.
  2. Implement routing so that clicking an interview card navigates to the Viewer page for that interview.

- **Phase 3: Search & Discovery**
  1. Integrate a client-side search library.
  2. Build the search functionality on the Gallery page.
  3. Create the Search Results page that displays contextual snippets and links them to the correct timestamp in the Viewer.

- **Phase 4: Admin Backend**
  1. Set up a lightweight Flask or Express.js server to serve the built front-end application.
  2. Create a secure API endpoint (`/api/manifest`) that accepts `POST` requests to update the manifest.
  3. Build the password-protected admin UI (`/admin`) with the metadata editing form.
  4. Connect the admin UI to the backend API.


## 9. Risks & Mitigation
- **Risk:** Performance issues with very large transcripts.
  - **Mitigation:** Use virtualized scrolling for the transcript panel to ensure only the visible text is rendered in the DOM.
- **Risk:** Data processing is slow.
  - **Mitigation:** The pre-processing script is run offline and only needs to be updated when new content is added, not every time the app is launched.
- **Risk:** Inaccurate subtitle timing.
  - **Mitigation:** The initial accuracy depends on the source `.srt` files. The UI will allow for easy comparison, which will help identify timing issues for future correction.
- **Risk:** Unauthorized access to the admin panel.
  - **Mitigation:** Use a strong, environment-variable-based password. For a hosted version, place the application behind a proper authentication proxy (e.g., using Nginx, Cloudflare Access).

---
**Document Version:** 1.1
**Status:** Draft 