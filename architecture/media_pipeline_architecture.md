# Media Transcription and Translation Pipeline: Architecture Document

## 1. System Overview

The Media Transcription and Translation Tool processes media files through a multi-stage pipeline:

1. **File Discovery**: Find and register media files
2. **Audio Extraction**: Extract audio from video files
3. **Transcription**: Convert audio to text using ElevenLabs API
4. **Translation**: Translate transcribed text to target languages (English, Hebrew, etc.)
5. **Output Generation**: Create SRT subtitles and other formats

## 2. Database Schema

### Media Files Table
```
media_files
-----------
id: UUID (Primary Key)
path: String (Original file path)
type: String (video, audio)
status: String (not_started, in-progress, completed, failed)
extraction_status: String (not_started, in-progress, completed, failed)
audio_path: String (Path to extracted audio)
transcription_status: String (not_started, in-progress, completed, failed)
transcript_path: String (Path to transcript file)
created_at: Timestamp
updated_at: Timestamp
```

### Translations Table
```
translations
-----------
id: UUID (Primary Key)
file_id: UUID (Foreign Key to media_files)
language: String (en, he, etc.)
status: String (not_started, in-progress, completed, failed)
translation_path: String (Path to translation file)
created_at: Timestamp
updated_at: Timestamp
```

## 3. State Transitions

### File Status State Machine

```
              ┌─────────────┐
              │ not_started │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ in-progress │◄────┐
              └──────┬──────┘     │
                     │            │ (If any stage needs
                     │            │  reprocessing)
                     ▼            │
              ┌─────────────┐     │
              │  completed  │─────┘
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │   failed    │
              └─────────────┘
```

### Stage-Specific Status States

Each stage (extraction, transcription, translation) follows this pattern:

```
              ┌─────────────┐
              │ not_started │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ in-progress │◄────┐
              └──────┬──────┘     │
                     │            │
                     ▼            │
              ┌─────────────┐     │
              │  completed  │     │
              └─────────────┘     │
                     │            │
                     ▼            │
              ┌─────────────┐     │
              │   failed    │─────┘
              └─────────────┘
```

## 4. Processing Flow

### Complete Pipeline Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Discovery &   │     │     Audio       │     │  Transcription  │     │   Translation   │
│  Registration   │────►│   Extraction    │────►│     Process     │────►│     Process     │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
                                                                               │
                                                                               ▼
                                                                        ┌─────────────────┐
                                                                        │ Output Creation │
                                                                        │  (SRT, Text)    │
                                                                        └─────────────────┘
```

### Individual Stage Flows

#### File Discovery
1. Scan directories for media files
2. Register new files in database:
   - status = 'not_started'
   - extraction_status = 'not_started'
   - transcription_status = 'not_started'
3. Skip files already in database

#### Audio Extraction
1. Query: Get files where extraction_status = 'not_started'
2. For each file:
   - Set extraction_status = 'in-progress'
   - Set status = 'in-progress'
   - Extract audio to output directory
   - On success: Set extraction_status = 'completed'
   - On failure: Set extraction_status = 'failed'
   - **Keep overall status = 'in-progress'**

#### Transcription
1. Query: Get files where extraction_status = 'completed' AND transcription_status IN ['not_started', 'failed']
2. For each file:
   - Set transcription_status = 'in-progress'
   - Transcribe audio using ElevenLabs
   - On success: Set transcription_status = 'completed'
   - On failure: Set transcription_status = 'failed'
   - **Keep overall status = 'in-progress'**

#### Translation
1. Query: Get files where transcription_status = 'completed' AND translation status for target language IN ['not_started', 'failed']
2. For each file:
   - Set translation status = 'in-progress'
   - Translate text using selected provider
   - On success: Set translation status = 'completed'
   - On failure: Set translation status = 'failed'
   - **Update overall status based on pipeline completion**

### Overall Status Logic

```python
def update_overall_status(file_id):
    file = get_file_by_id(file_id)
    
    # Check if any stage has failed critically
    if file['extraction_status'] == 'failed' and is_critical_failure(file_id, 'extraction'):
        set_overall_status(file_id, 'failed')
        return
        
    # Check all required stages
    all_complete = (
        file['extraction_status'] == 'completed' and
        file['transcription_status'] == 'completed' and
        all(translation['status'] == 'completed' for translation in get_translations(file_id))
    )
    
    if all_complete:
        set_overall_status(file_id, 'completed')
    else:
        set_overall_status(file_id, 'in-progress')
```

## 5. Query Design Patterns

### Stage-Specific Queries

For each stage, create a specific query method:

```python
# File Manager
def get_files_for_extraction():
    """Get files that need audio extraction."""
    return db.query("""
        SELECT * FROM media_files 
        WHERE extraction_status IN ('not_started', 'failed')
    """)

# Transcription Manager
def get_files_for_transcription():
    """Get files that need transcription."""
    return db.query("""
        SELECT * FROM media_files 
        WHERE extraction_status = 'completed' 
        AND transcription_status IN ('not_started', 'failed')
    """)

# Translation Manager
def get_files_for_translation(language):
    """Get files that need translation for a specific language."""
    return db.query("""
        SELECT m.*, t.status as translation_status 
        FROM media_files m
        LEFT JOIN translations t ON m.id = t.file_id AND t.language = ?
        WHERE m.transcription_status = 'completed'
        AND (t.status IS NULL OR t.status IN ('not_started', 'failed'))
    """, (language,))
```

## 6. Command Line Flow

### Command Behavior

| Command Flag       | Behavior                                                      |
|--------------------|---------------------------------------------------------------|
| No flags           | Run complete pipeline                                         |
| --extract-only     | Only perform audio extraction                                 |
| --transcribe-only  | Only perform transcription (on extracted files)               |
| --translate-only   | Only perform translation (on transcribed files)               |
| --reset-status     | Reset file statuses for reprocessing                          |
| --list-files       | Show all files and their statuses                             |

## 7. Implementation Recommendations

### 1. DatabaseManager Updates

* Add stage-specific query methods:
  - `get_files_for_extraction()`
  - `get_files_for_transcription()`
  - `get_files_for_translation(language)`
  
* Create clear status transition methods:
  - `update_extraction_status(file_id, status)`
  - `update_transcription_status(file_id, status)`
  - `update_translation_status(file_id, language, status)`
  - `update_overall_status(file_id)` (using the logic shown earlier)

### 2. Manager Class Updates

* Use the stage-specific query methods:

```python
# TranscriptionManager.transcribe_batch
def transcribe_batch(self, limit=None):
    # Use the dedicated query for transcription files
    files = self.db_manager.get_files_for_transcription()
    if limit:
        files = files[:limit]
    
    # Process files
    success_count = 0
    fail_count = 0
    
    for file in tqdm(files, desc="Transcribing audio"):
        if self.transcribe_audio(file['id']):
            success_count += 1
        else:
            fail_count += 1
    
    return success_count, fail_count
```

### 3. Status Management Logic

* Only update the specific stage status in each manager
* Create a separate method to update overall status based on all stages
* Call this after each stage completion/failure

## 8. Migration Plan

1. Update database schema to ensure it tracks all status fields correctly
2. Implement stage-specific query methods in DatabaseManager
3. Update manager classes to use stage-specific queries
4. Implement proper overall status update logic
5. Test with existing files in the database

By implementing these architectural changes, the pipeline will properly handle files at each stage, enabling independent operation of extraction, transcription, and translation while maintaining proper state tracking.
