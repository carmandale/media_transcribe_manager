# Logging Guide

This document provides guidance on using the centralized logging system in the Scribe project.

## Overview

All logs are now stored in the `logs/` directory at the project root. The log system uses a centralized configuration that ensures consistent formatting and storage of logs across all modules and scripts.

## Using the Logging System

### In Core Modules

Core modules should import and use the `get_script_logger` function:

```python
from log_config import get_script_logger

# Get a logger with the current module name
logger = get_script_logger(__name__)

# Now use the logger
logger.debug("Detailed debug information")
logger.info("General information messages")
logger.warning("Warning messages")
logger.error("Error messages")
logger.critical("Critical error messages")
```

### In Scripts

Scripts should import and use the `setup_logger` function:

```python
import sys
import pathlib
from typing import Dict, Any

# Add core_modules to the Python path
sys.path.append(str(pathlib.Path(__file__).parent.parent / 'core_modules'))

from log_config import setup_logger

# Configure logging with a specific log file
logger = setup_logger('script_name', 'script_name.log')

# Now use the logger
logger.info("Script started")
logger.error("An error occurred")
```

## Log Configuration

All log configuration is handled by the `log_config.py` module in the `core_modules` directory. This ensures:

1. Consistent log formatting across all parts of the application
2. All logs are stored in the `logs/` directory
3. Proper log rotation and management
4. Both console and file logging for all components

## Log Files

Common log files include:

- `transcription.log` - Transcription process logs
- `translation_*.log` - Translation process logs for each language
- `monitor.log` - Monitoring system logs
- `parallel_*.log` - Parallel processing logs
- `*.log` - Various component-specific logs

## Best Practices

1. **Use Appropriate Log Levels**:
   - `DEBUG`: Detailed information for debugging
   - `INFO`: General information about program execution
   - `WARNING`: For potentially problematic situations
   - `ERROR`: For error conditions that prevent normal operation
   - `CRITICAL`: For very serious errors that may cause program failure

2. **Include Contextual Information**:
   - When logging errors, include relevant context (file ID, operation, etc.)
   - Include timing information for long-running processes

3. **Don't Log Sensitive Information**:
   - Never log API keys, passwords, or sensitive data
   - Use masking for sensitive information (e.g., `api_key[:5]...`)

4. **Log Exception Information**:
   - When catching exceptions, include the exception details in logs
   - Use `logger.exception()` to automatically include the traceback

## Viewing and Managing Logs

All logs are stored in the `logs/` directory. You can view logs with standard tools:

```bash
# View the last 50 lines of a log file
tail -n 50 logs/transcription.log

# Follow a log file in real-time
tail -f logs/monitor.log

# Search for errors in logs
grep ERROR logs/*.log

# Check all logs for specific file ID
grep "file-1234" logs/*.log
```