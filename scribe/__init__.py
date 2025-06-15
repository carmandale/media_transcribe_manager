"""
Scribe - Clean translation module for historical interview transcripts.
"""

from .translate import (
    HistoricalTranslator,
    translate_text,
    validate_hebrew
)

from .utils import (
    normalize_path,
    sanitize_filename,
    generate_file_id,
    calculate_checksum,
    SimpleWorkerPool,
    ProgressTracker,
    ensure_directory,
    get_file_info,
    chunk_list,
    safe_execute
)

__version__ = "1.0.0"
__all__ = [
    # Translation functions
    "HistoricalTranslator", 
    "translate_text", 
    "validate_hebrew",
    # Utility functions
    "normalize_path",
    "sanitize_filename",
    "generate_file_id",
    "calculate_checksum",
    "SimpleWorkerPool",
    "ProgressTracker",
    "ensure_directory",
    "get_file_info",
    "chunk_list",
    "safe_execute"
]