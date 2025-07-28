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
        if not hasattr(self._local, 'conn') or self._local.conn is None:
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
    
    def _migrate_to_subtitle_segments(self):
        """
        Migration to add subtitle_segments table and related views.
        This is additive - preserves all existing functionality.
        """
        with self.transaction() as conn:
            # Check if already migrated
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subtitle_segments'")
            if cursor.fetchone() is not None:
                logger.debug("subtitle_segments table already exists, skipping migration")
                return
            
            logger.info("Creating subtitle_segments table and views...")
            
            # Create subtitle_segments table
            conn.execute("""
                CREATE TABLE subtitle_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    segment_index INTEGER NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    duration REAL GENERATED ALWAYS AS (end_time - start_time) STORED,
                    original_text TEXT NOT NULL,
                    german_text TEXT,
                    english_text TEXT,
                    hebrew_text TEXT,
                    confidence_score REAL,
                    processing_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraints
                    FOREIGN KEY (interview_id) REFERENCES media_files(file_id) ON DELETE CASCADE,
                    UNIQUE(interview_id, segment_index),
                    CHECK(start_time >= 0),
                    CHECK(end_time > start_time),
                    CHECK(confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1))
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX idx_subtitle_segments_interview_id ON subtitle_segments(interview_id)")
            conn.execute("CREATE INDEX idx_subtitle_segments_timing ON subtitle_segments(interview_id, start_time)")
            conn.execute("CREATE INDEX idx_subtitle_segments_search ON subtitle_segments(interview_id, segment_index)")
            conn.execute("CREATE INDEX idx_subtitle_segments_original_text ON subtitle_segments(original_text)")
            conn.execute("CREATE INDEX idx_subtitle_segments_english_text ON subtitle_segments(english_text)")
            conn.execute("CREATE INDEX idx_subtitle_segments_german_text ON subtitle_segments(german_text)")
            
            # Create backward compatibility views
            conn.execute("""
                CREATE VIEW transcripts AS
                SELECT 
                    interview_id,
                    GROUP_CONCAT(original_text, ' ') as original_transcript,
                    GROUP_CONCAT(german_text, ' ') as german_transcript, 
                    GROUP_CONCAT(english_text, ' ') as english_transcript,
                    GROUP_CONCAT(hebrew_text, ' ') as hebrew_transcript,
                    COUNT(*) as total_segments,
                    AVG(confidence_score) as avg_confidence,
                    MIN(start_time) as transcript_start,
                    MAX(end_time) as transcript_end,
                    MAX(end_time) - MIN(start_time) as total_duration
                FROM subtitle_segments 
                GROUP BY interview_id
                ORDER BY interview_id
            """)
            
            conn.execute("""
                CREATE VIEW segment_quality AS
                SELECT 
                    interview_id,
                    COUNT(*) as total_segments,
                    AVG(duration) as avg_segment_duration,
                    MIN(duration) as min_segment_duration,
                    MAX(duration) as max_segment_duration,
                    AVG(confidence_score) as avg_confidence,
                    COUNT(CASE WHEN confidence_score < 0.8 THEN 1 END) as low_confidence_segments,
                    COUNT(CASE WHEN duration < 1.0 THEN 1 END) as short_segments,
                    COUNT(CASE WHEN duration > 10.0 THEN 1 END) as long_segments
                FROM subtitle_segments
                GROUP BY interview_id
            """)
            
            logger.info("Subtitle segments migration completed successfully")
    
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
        file_id = generate_file_id()
        
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
    
    def get_file_by_path(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Get file record by original path."""
        file_path = str(Path(file_path).resolve())
        conn = self._get_connection()
        
        cursor = conn.execute("""
            SELECT * FROM media_files WHERE original_path = ?
        """, (file_path,))
        
        row = cursor.fetchone()
        if row:
            try:
                return dict(row)
            except (TypeError, ValueError):
                # Fallback if row is not a proper Row object
                return None
        return None
    
    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID."""
        conn = self._get_connection()
        
        cursor = conn.execute("""
            SELECT * FROM media_files WHERE file_id = ?
        """, (file_id,))
        
        row = cursor.fetchone()
        if row:
            try:
                return dict(row)
            except (TypeError, ValueError):
                # Fallback if row is not a proper Row object
                return None
        return None
    
    def get_all_files(self) -> List[Dict[str, Any]]:
        """Get all file records from the database."""
        conn = self._get_connection()
        
        cursor = conn.execute("""
            SELECT m.*, p.*
            FROM media_files m
            LEFT JOIN processing_status p ON m.file_id = p.file_id
            ORDER BY m.created_at
        """)
        
        results = []
        for row in cursor.fetchall():
            try:
                results.append(dict(row))
            except (TypeError, ValueError):
                # Skip malformed rows
                continue
        return results
    
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
        if row:
            try:
                return dict(row)
            except (TypeError, ValueError):
                # Fallback if row is not a proper Row object
                return None
        return None
    
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
            WHERE p.{status_field} IN ('not_started')
              AND p.status != 'failed'
            ORDER BY p.last_updated ASC
        """
        
        if limit:
            query += f" LIMIT {int(limit)}"
        
        conn = self._get_connection()
        cursor = conn.execute(query)
        results = []
        for row in cursor.fetchall():
            try:
                results.append(dict(row))
            except (TypeError, ValueError):
                # Skip malformed rows
                continue
        return results
    
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
        results = []
        for row in cursor.fetchall():
            try:
                results.append(dict(row))
            except (TypeError, ValueError):
                # Skip malformed rows
                continue
        return results
    
    def get_stuck_files(self, timeout_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get files that have been in-progress for too long."""
        from datetime import datetime, timedelta
        
        # Calculate cutoff time in Python and format as ISO string
        cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
        cutoff_iso = cutoff_time.isoformat()
        
        query = """
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.status = 'in-progress'
              AND p.last_updated < ?
            ORDER BY p.last_updated ASC
        """
        
        conn = self._get_connection()
        cursor = conn.execute(query, (cutoff_iso,))
        results = []
        for row in cursor.fetchall():
            try:
                results.append(dict(row))
            except (TypeError, ValueError):
                # Skip malformed rows
                continue
        return results
    
    def get_files_for_srt_translation(self, language: str) -> List[Dict[str, Any]]:
        """
        Get files that have original SRT but no translated SRT for a language.
        
        Args:
            language: Target language code ('en', 'de', 'he')
            
        Returns:
            List of file records needing SRT translation
        """
        query = """
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.transcription_status = 'completed'
              AND p.status != 'failed'
              AND NOT EXISTS (
                  SELECT 1 FROM (
                      SELECT file_id,
                             CASE 
                                 WHEN ? = 'en' THEN 1
                                 WHEN ? = 'de' THEN 1
                                 WHEN ? = 'he' THEN 1
                                 ELSE 0
                             END as has_srt
                      FROM processing_status
                      WHERE file_id = m.file_id
                  ) sub
                  WHERE sub.has_srt = 0
              )
            ORDER BY p.last_updated ASC
        """
        
        # Note: This query needs to be enhanced to check actual file existence
        # For now, we'll return all files with completed transcription
        # The pipeline will check for actual SRT file existence
        simple_query = """
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.transcription_status = 'completed'
              AND p.status != 'failed'
            ORDER BY p.last_updated ASC
        """
        
        conn = self._get_connection()
        cursor = conn.execute(simple_query)
        results = []
        for row in cursor.fetchall():
            try:
                results.append(dict(row))
            except (TypeError, ValueError):
                # Skip malformed rows
                continue
        return results
    
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
        
        query += " ORDER BY timestamp DESC, error_id DESC"
        
        conn = self._get_connection()
        cursor = conn.execute(query, params)
        results = []
        for row in cursor.fetchall():
            try:
                results.append(dict(row))
            except (TypeError, ValueError):
                # Skip malformed rows
                continue
        return results
    
    def get_all_errors(self) -> List[Dict[str, Any]]:
        """Get all errors - alias for get_errors()."""
        return self.get_errors()
    
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
    
    # Subtitle segments methods for subtitle-first architecture
    
    def add_subtitle_segment(self,
                           interview_id: str,
                           segment_index: int,
                           start_time: float,
                           end_time: float,
                           original_text: str,
                           german_text: Optional[str] = None,
                           english_text: Optional[str] = None,
                           hebrew_text: Optional[str] = None,
                           confidence_score: Optional[float] = None) -> int:
        """
        Add a subtitle segment to the database.
        
        Args:
            interview_id: ID of the interview file
            segment_index: Index/order of this segment
            start_time: Start timestamp in seconds
            end_time: End timestamp in seconds  
            original_text: Original transcribed text
            german_text: German translation (optional)
            english_text: English translation (optional)
            hebrew_text: Hebrew translation (optional)
            confidence_score: ElevenLabs confidence score (optional)
            
        Returns:
            ID of the inserted segment
        """
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time,
                    original_text, german_text, english_text, hebrew_text,
                    confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interview_id, segment_index, start_time, end_time,
                original_text, german_text, english_text, hebrew_text,
                confidence_score
            ))
            return cursor.lastrowid
    
    def get_subtitle_segments(self, interview_id: str) -> List[Dict[str, Any]]:
        """Get all subtitle segments for an interview, ordered by segment_index."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM subtitle_segments 
            WHERE interview_id = ?
            ORDER BY segment_index
        """, (interview_id,))
        
        results = []
        for row in cursor.fetchall():
            try:
                results.append(dict(row))
            except (TypeError, ValueError):
                continue
        return results
    
    def get_subtitle_segments_by_time_range(self,
                                          interview_id: str,
                                          start_time: Optional[float] = None,
                                          end_time: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Get subtitle segments within a specific time range.
        
        Args:
            interview_id: ID of the interview
            start_time: Minimum start time (inclusive)
            end_time: Maximum end time (inclusive)
            
        Returns:
            List of segment records within the time range
        """
        conn = self._get_connection()
        
        query = "SELECT * FROM subtitle_segments WHERE interview_id = ?"
        params = [interview_id]
        
        if start_time is not None:
            query += " AND start_time >= ?"
            params.append(start_time)
        
        if end_time is not None:
            query += " AND end_time <= ?"
            params.append(end_time)
        
        query += " ORDER BY segment_index"
        
        cursor = conn.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            try:
                results.append(dict(row))
            except (TypeError, ValueError):
                continue
        return results
    
    def update_subtitle_segment_translations(self,
                                           segment_id: int,
                                           german_text: Optional[str] = None,
                                           english_text: Optional[str] = None,
                                           hebrew_text: Optional[str] = None) -> bool:
        """
        Update translations for an existing subtitle segment.
        
        Args:
            segment_id: ID of the segment to update
            german_text: German translation (optional)
            english_text: English translation (optional) 
            hebrew_text: Hebrew translation (optional)
            
        Returns:
            True if update was successful
        """
        updates = []
        values = []
        
        if german_text is not None:
            updates.append("german_text = ?")
            values.append(german_text)
        
        if english_text is not None:
            updates.append("english_text = ?")
            values.append(english_text)
        
        if hebrew_text is not None:
            updates.append("hebrew_text = ?")
            values.append(hebrew_text)
        
        if not updates:
            return False
        
        values.append(segment_id)
        
        with self.transaction() as conn:
            cursor = conn.execute(f"""
                UPDATE subtitle_segments 
                SET {', '.join(updates)}
                WHERE id = ?
            """, values)
            return cursor.rowcount > 0
    
    def get_subtitle_quality_metrics(self, interview_id: str) -> Dict[str, Any]:
        """
        Get quality metrics for subtitle segments of an interview.
        
        Args:
            interview_id: ID of the interview
            
        Returns:
            Dictionary with quality metrics
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM segment_quality WHERE interview_id = ?
        """, (interview_id,))
        
        row = cursor.fetchone()
        if row:
            try:
                metrics = dict(row)
                # Convert to more readable format
                return {
                    'total_segments': metrics['total_segments'],
                    'avg_segment_duration': round(metrics['avg_segment_duration'], 2),
                    'min_segment_duration': metrics['min_segment_duration'],
                    'max_segment_duration': metrics['max_segment_duration'],
                    'avg_confidence': round(metrics['avg_confidence'], 3),
                    'low_confidence_segments': metrics['low_confidence_segments'],
                    'short_segments': metrics['short_segments'],
                    'long_segments': metrics['long_segments']
                }
            except (TypeError, ValueError):
                pass
        
        return {
            'total_segments': 0,
            'avg_segment_duration': 0.0,
            'min_segment_duration': 0.0,
            'max_segment_duration': 0.0,
            'avg_confidence': 0.0,
            'low_confidence_segments': 0,
            'short_segments': 0,
            'long_segments': 0
        }
    
    def validate_subtitle_timing(self, interview_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Validate subtitle segment timing for gaps and overlaps.
        
        Args:
            interview_id: ID of the interview to validate
            
        Returns:
            Dictionary with 'gaps' and 'overlaps' lists
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT segment_index, start_time, end_time
            FROM subtitle_segments 
            WHERE interview_id = ?
            ORDER BY segment_index
        """, (interview_id,))
        
        segments = cursor.fetchall()
        gaps = []
        overlaps = []
        
        for i in range(len(segments) - 1):
            current = segments[i]
            next_segment = segments[i + 1]
            
            current_end = current[2]  # end_time
            next_start = next_segment[1]  # start_time
            
            if current_end < next_start:
                # Gap detected
                gap_duration = next_start - current_end
                gaps.append({
                    'after_segment': current[0],  # segment_index
                    'before_segment': next_segment[0],  # segment_index
                    'gap_duration': gap_duration
                })
            elif current_end > next_start:
                # Overlap detected
                overlap_duration = current_end - next_start
                overlaps.append({
                    'segment1': current[0],  # segment_index
                    'segment2': next_segment[0],  # segment_index
                    'overlap_duration': overlap_duration
                })
        
        return {
            'gaps': gaps,
            'overlaps': overlaps
        }
    
    def close(self):
        """Close database connection for current thread."""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            delattr(self._local, 'conn')