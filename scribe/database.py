#!/usr/bin/env python3
"""
Consolidated Database Module for Scribe
--------------------------------------
Thread-safe database interface with connection pooling for SQLite.
Provides essential functionality for tracking media files and processing status.
"""

import sqlite3
import threading
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
import uuid
import os

logger = logging.getLogger(__name__)


class Database:
    """Thread-safe database interface with connection pooling."""
    
    def __init__(self, db_path: Union[str, Path] = "media_tracking.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Initialize database schema
        self._initialize_schema()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.conn.execute("PRAGMA foreign_keys = ON")
            # Register datetime adapter
            sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
        return self._local.conn
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _initialize_schema(self):
        """Create database tables if they don't exist."""
        with self.transaction() as conn:
            # Media files table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS media_files (
                    file_id TEXT PRIMARY KEY,
                    original_path TEXT NOT NULL UNIQUE,
                    safe_filename TEXT NOT NULL,
                    file_size INTEGER,
                    duration REAL,
                    checksum TEXT,
                    media_type TEXT CHECK(media_type IN ('audio', 'video')),
                    detected_language TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Processing status table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_status (
                    file_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'pending' 
                        CHECK(status IN ('pending', 'in-progress', 'completed', 'failed')),
                    transcription_status TEXT DEFAULT 'not_started'
                        CHECK(transcription_status IN ('not_started', 'in-progress', 'completed', 'failed')),
                    translation_en_status TEXT DEFAULT 'not_started'
                        CHECK(translation_en_status IN ('not_started', 'in-progress', 'completed', 'failed')),
                    translation_de_status TEXT DEFAULT 'not_started'
                        CHECK(translation_de_status IN ('not_started', 'in-progress', 'completed', 'failed')),
                    translation_he_status TEXT DEFAULT 'not_started'
                        CHECK(translation_he_status IN ('not_started', 'in-progress', 'completed', 'failed')),
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    attempts INTEGER DEFAULT 0,
                    FOREIGN KEY (file_id) REFERENCES media_files(file_id)
                )
            """)
            
            # Errors table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    process_stage TEXT NOT NULL,
                    error_message TEXT,
                    error_details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES media_files(file_id)
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON processing_status(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transcription_status 
                ON processing_status(transcription_status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_translation_statuses 
                ON processing_status(translation_en_status, translation_de_status, translation_he_status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_updated 
                ON processing_status(last_updated)
            """)
    
    # File tracking methods
    
    def add_file_simple(self, file_path: Union[str, Path]) -> Optional[str]:
        """
        Simple interface to add a file - handles path sanitization automatically.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            file_id if added successfully, None if already exists
        """
        file_path = Path(file_path)
        
        # Check if already exists
        existing = self.get_file_by_path(str(file_path))
        if existing:
            return None
            
        # Generate safe filename and file_id
        from .utils import sanitize_filename, generate_file_id
        safe_filename = sanitize_filename(file_path.name)
        file_id = generate_file_id(file_path)
        
        # Determine media type from extension
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
        media_type = 'video' if file_path.suffix.lower() in video_extensions else 'audio'
        
        # Get file metadata
        metadata = {}
        if file_path.exists():
            metadata['file_size'] = file_path.stat().st_size
            
        # Add to database
        return self.add_file(
            file_path=str(file_path),
            safe_filename=safe_filename,
            media_type=media_type,
            **metadata
        )
    
    def add_file(self, 
                 file_path: Union[str, Path],
                 safe_filename: str,
                 media_type: str = 'audio',
                 **metadata) -> str:
        """
        Add a new file to the database.
        
        Args:
            file_path: Original path to the media file
            safe_filename: Sanitized filename for processing
            media_type: Type of media ('audio' or 'video')
            **metadata: Additional metadata (file_size, duration, checksum, detected_language)
            
        Returns:
            file_id of the added file
        """
        file_id = str(uuid.uuid4())
        file_path = str(Path(file_path).resolve())
        
        with self.transaction() as conn:
            # Insert media file
            conn.execute("""
                INSERT INTO media_files (
                    file_id, original_path, safe_filename, media_type,
                    file_size, duration, checksum, detected_language
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id, file_path, safe_filename, media_type,
                metadata.get('file_size'), metadata.get('duration'),
                metadata.get('checksum'), metadata.get('detected_language')
            ))
            
            # Insert initial processing status
            conn.execute("""
                INSERT INTO processing_status (file_id) VALUES (?)
            """, (file_id,))
        
        logger.debug(f"Added file {file_id}: {file_path}")
        return file_id
    
    def add_file_simple(self, file_path: Union[str, Path]) -> Optional[str]:
        """
        Simple wrapper to add a file with just a path.
        Extracts necessary information from the file path.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            file_id if added successfully, None if already exists
        """
        file_path = Path(file_path).resolve()
        
        # Check if file already exists
        existing = self.get_file_by_path(file_path)
        if existing:
            return None
            
        # Extract safe filename
        filename = file_path.name
        # Simple sanitization - replace spaces and special chars with underscores
        safe_filename = filename.lower()
        safe_filename = ''.join(c if c.isalnum() or c in '._-' else '_' for c in safe_filename)
        
        # Determine media type from extension
        extension = file_path.suffix.lower()
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
        media_type = 'video' if extension in video_extensions else 'audio'
        
        # Get file size
        try:
            file_size = file_path.stat().st_size
        except OSError:
            file_size = None
            
        # Add the file
        return self.add_file(
            file_path=str(file_path),
            safe_filename=safe_filename,
            media_type=media_type,
            file_size=file_size
        )
    
    def get_file_by_path(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Get file record by original path."""
        file_path = str(Path(file_path).resolve())
        conn = self._get_connection()
        
        cursor = conn.execute("""
            SELECT * FROM media_files WHERE original_path = ?
        """, (file_path,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID."""
        conn = self._get_connection()
        
        cursor = conn.execute("""
            SELECT * FROM media_files WHERE file_id = ?
        """, (file_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # Status management methods
    
    def get_status(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get processing status for a file."""
        conn = self._get_connection()
        
        cursor = conn.execute("""
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE m.file_id = ?
        """, (file_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_status(self,
                     file_id: str,
                     status: Optional[str] = None,
                     **stage_statuses) -> bool:
        """
        Update processing status for a file.
        
        Args:
            file_id: File ID to update
            status: Overall status ('pending', 'in-progress', 'completed', 'failed')
            **stage_statuses: Stage-specific statuses (e.g., transcription_status='completed')
            
        Returns:
            True if update was successful
        """
        updates = []
        values = []
        
        if status:
            updates.append("status = ?")
            values.append(status)
            
            # Auto-set timestamps
            if status == 'in-progress':
                updates.append("started_at = COALESCE(started_at, ?)")
                values.append(datetime.now())
            elif status in ('completed', 'failed'):
                updates.append("completed_at = ?")
                values.append(datetime.now())
        
        # Add stage-specific status updates
        for key, value in stage_statuses.items():
            if key.endswith('_status'):
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        # Always update last_updated
        updates.append("last_updated = ?")
        values.append(datetime.now())
        
        # Add file_id for WHERE clause
        values.append(file_id)
        
        query = f"""
            UPDATE processing_status 
            SET {', '.join(updates)}
            WHERE file_id = ?
        """
        
        with self.transaction() as conn:
            cursor = conn.execute(query, values)
            return cursor.rowcount > 0
    
    def increment_attempts(self, file_id: str) -> bool:
        """Increment attempt counter for a file."""
        with self.transaction() as conn:
            cursor = conn.execute("""
                UPDATE processing_status 
                SET attempts = attempts + 1,
                    last_updated = ?
                WHERE file_id = ?
            """, (datetime.now(), file_id))
            return cursor.rowcount > 0
    
    # Query methods
    
    def get_pending_files(self, 
                         stage: str,
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get files pending for a specific stage.
        
        Args:
            stage: Processing stage ('transcription', 'translation_en', 'translation_de', 'translation_he')
            limit: Maximum number of files to return
            
        Returns:
            List of file records pending for the stage
        """
        status_field = f"{stage}_status"
        query = f"""
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.{status_field} = 'not_started'
              AND p.status != 'failed'
            ORDER BY p.last_updated ASC
        """
        
        if limit:
            query += f" LIMIT {int(limit)}"
        
        conn = self._get_connection()
        cursor = conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_files_by_status(self,
                           status: Union[str, List[str]],
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get files with specific overall status."""
        if isinstance(status, str):
            statuses = [status]
        else:
            statuses = status
        
        placeholders = ', '.join(['?' for _ in statuses])
        query = f"""
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.status IN ({placeholders})
            ORDER BY p.last_updated DESC
        """
        
        if limit:
            query += f" LIMIT {int(limit)}"
        
        conn = self._get_connection()
        cursor = conn.execute(query, statuses)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stuck_files(self, timeout_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get files that have been in-progress for too long."""
        query = """
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.status = 'in-progress'
              AND p.last_updated < datetime('now', ? || ' minutes')
            ORDER BY p.last_updated ASC
        """
        
        conn = self._get_connection()
        cursor = conn.execute(query, (-timeout_minutes,))
        return [dict(row) for row in cursor.fetchall()]
    
    # Error logging
    
    def log_error(self,
                 file_id: str,
                 process_stage: str,
                 error_message: str,
                 error_details: Optional[str] = None) -> bool:
        """Log an error for a file."""
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO errors (file_id, process_stage, error_message, error_details)
                VALUES (?, ?, ?, ?)
            """, (file_id, process_stage, error_message, error_details))
        return True
    
    def get_errors(self, file_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get errors, optionally filtered by file_id."""
        query = "SELECT * FROM errors"
        params = []
        
        if file_id:
            query += " WHERE file_id = ?"
            params.append(file_id)
        
        query += " ORDER BY timestamp DESC"
        
        conn = self._get_connection()
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    # Summary statistics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics about processing state."""
        conn = self._get_connection()
        
        # Total files
        total = conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]
        
        # Status counts
        status_counts = {}
        cursor = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM processing_status
            GROUP BY status
        """)
        for row in cursor:
            status_counts[row['status']] = row['count']
        
        # Stage completion counts
        stage_counts = {}
        for stage in ['transcription', 'translation_en', 'translation_de', 'translation_he']:
            cursor = conn.execute(f"""
                SELECT {stage}_status as status, COUNT(*) as count
                FROM processing_status
                GROUP BY {stage}_status
            """)
            stage_counts[stage] = {row['status']: row['count'] for row in cursor}
        
        # Error count
        error_count = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        
        # Calculate summary stats for CLI compatibility
        transcribed = stage_counts.get('transcription', {}).get('completed', 0)
        en_translated = stage_counts.get('translation_en', {}).get('completed', 0)
        de_translated = stage_counts.get('translation_de', {}).get('completed', 0)
        he_translated = stage_counts.get('translation_he', {}).get('completed', 0)
        
        return {
            'total_files': total,
            'status_counts': status_counts,
            'stage_counts': stage_counts,
            'error_count': error_count,
            # Added for CLI compatibility
            'transcribed': transcribed,
            'en_translated': en_translated,
            'de_translated': de_translated,
            'he_translated': he_translated
        }
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dicts.
        
        This method is provided for compatibility with code expecting
        the old database interface.
        
        Args:
            query: SQL SELECT query
            params: Query parameters (optional)
            
        Returns:
            List of dictionaries representing rows
        """
        conn = self._get_connection()
        cursor = conn.execute(query, params or ())
        
        # Get column names
        columns = [col[0] for col in cursor.description] if cursor.description else []
        
        # Fetch all rows and convert to dicts
        rows = []
        for row in cursor.fetchall():
            rows.append(dict(zip(columns, row)))
        
        return rows
    
    def close(self):
        """Close database connection for current thread."""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            delattr(self._local, 'conn')