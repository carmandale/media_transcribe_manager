# Core Modules Directory

This directory contains the core functionality of the Scribe media processing system. All modules here are designed to be imported by scripts throughout the project.

## Module Overview

### Database Management
- **db_manager.py**: Main database interface with connection pooling
- **db_connection_pool.py**: Thread-safe SQLite connection pooling
- **db_maintenance.py**: Database repair and maintenance operations

### File Operations
- **file_manager.py**: File path handling, metadata management, and directory operations
  - Handles unicode paths and special characters
  - Manages output directory structure
  - Validates file types and existence

### Processing Modules
- **transcription.py**: Audio transcription using ElevenLabs API
  - Handles audio extraction from video files
  - Manages transcription state and retries
  - Supports various audio formats

- **translation.py**: Multi-language translation services
  - Supports English, German, and Hebrew translations
  - Integrates with DeepL, Google Translate, and MS Translator
  - Handles context preservation and formatting

### Pipeline Management
- **pipeline_manager.py**: Orchestrates the entire processing pipeline
  - Monitors processing status
  - Handles stuck file recovery
  - Provides command-line interface

- **scribe_manager.py**: Unified CLI entry point
  - Combines all functionality in one interface
  - Provides status monitoring and maintenance commands

### Support Modules
- **worker_pool.py**: Parallel processing framework
  - Thread pool management
  - Task distribution and error handling

- **reporter.py**: Report generation and statistics
  - Processing summaries
  - Quality evaluation reports

- **log_config.py**: Centralized logging configuration
  - Consistent log formatting
  - Log file rotation

## Import Pattern

All scripts importing from core_modules should use:

```python
import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.resolve()
sys.path.insert(0, str(project_root))

# Import from core_modules
from core_modules.module_name import ClassName
```

## Key Design Principles

1. **Thread Safety**: All database operations use connection pooling
2. **Error Recovery**: Robust error handling with automatic retries
3. **Unicode Support**: All file operations handle special characters
4. **State Management**: Database tracks all processing states
5. **Modular Design**: Each module has a single responsibility

## Common Issues and Solutions

### Import Errors
- Always ensure the project root is in sys.path before importing
- Use absolute imports: `from core_modules.module import Class`

### Database Locking
- Use DatabaseManager for all database operations
- Never access the SQLite file directly
- Connection pool handles concurrent access

### File Path Issues
- Always use pathlib.Path for path operations
- Never use string concatenation for paths
- Handle spaces and special characters properly

## Testing Modules

To test individual modules:
```bash
# From project root
uv run python -m core_modules.module_name
```

Most modules include self-test code in their `if __name__ == "__main__":` blocks.