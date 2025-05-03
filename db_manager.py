#!/usr/bin/env python3
"""
Database Manager for Media Transcription and Translation Tool
------------------------------------------------------------
Handles all database operations including schema creation, state tracking,
status updates, and error logging according to the PRD specifications.
"""

import os
import sqlite3
import logging
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
from pathlib import Path
import uuid

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages all database operations for the Media Transcription and Translation Tool.
    
    This class provides methods for:
    - Schema creation and database initialization
    - Adding and updating media files
    - Tracking processing status
    - Error logging
    - Reporting
    """
    
    def __init__(self, db_file: str):
        """
        Initialize the database manager.
        
        Args:
            db_file: Path to SQLite database file
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)
        
        self.db_file = db_file
        self.conn = None
        self.cursor = None
        
        # Connect to database
        self.connect()
        
        # Create tables if they don't exist
        self.initialize_database()
        
    def connect(self) -> None:
        """
        Establish connection to the SQLite database.
        """
        try:
            # Allow usage of connection across threads for parallel QA
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            # Enable foreign key support
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Return rows as dictionaries
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            logger.debug(f"Connected to database: {self.db_file}")
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
            
    def close(self) -> None:
        """
        Close the database connection.
        """
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")
            
    def initialize_database(self) -> None:
        """
        Create the necessary tables if they don't exist.
        """
        try:
            # Media Files Table
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_files (
                file_id TEXT PRIMARY KEY,     -- Unique ID for the file
                original_path TEXT NOT NULL,  -- Full original path to the file
                safe_filename TEXT NOT NULL,  -- Sanitized filename
                file_size INTEGER,            -- Size in bytes
                duration REAL,                -- Duration in seconds
                checksum TEXT,                -- File checksum
                media_type TEXT,              -- 'audio' or 'video'
                detected_language TEXT,       -- Detected language code
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Processing Status Table
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_status (
                file_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,         -- 'pending', 'in-progress', 'completed', 'failed'
                transcription_status TEXT,    -- 'not_started', 'completed', 'failed'
                translation_en_status TEXT,   -- 'not_started', 'completed', 'failed'
                translation_he_status TEXT,   -- 'not_started', 'completed', 'failed'
                translation_de_status TEXT,   -- 'not_started', 'completed', 'failed'
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                last_updated TIMESTAMP,
                attempts INTEGER DEFAULT 0,
                FOREIGN KEY (file_id) REFERENCES media_files(file_id)
            )
            """)
            
            # Error Tracking Table
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                process_stage TEXT NOT NULL,  -- 'discovery', 'extraction', 'transcription', 'translation_en', 'translation_he', 'translation_de'
                error_message TEXT,
                error_details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES media_files(file_id)
            )
            """)
            
            # Quality Evaluations Table
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_evaluations (
                eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                language TEXT NOT NULL,
                model TEXT NOT NULL,
                score REAL NOT NULL,
                issues TEXT,
                comment TEXT,
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES media_files(file_id)
            )
            """)
            
            self.conn.commit()
            logger.debug("Database initialized with required tables")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise
            
    def reset_database(self) -> None:
        """
        Reset the database by dropping and recreating all tables.
        Warning: This will delete all data!
        """
        try:
            # Drop tables if they exist
            self.cursor.execute("DROP TABLE IF EXISTS errors")
            self.cursor.execute("DROP TABLE IF EXISTS quality_evaluations")
            self.cursor.execute("DROP TABLE IF EXISTS processing_status")
            self.cursor.execute("DROP TABLE IF EXISTS media_files")
            
            self.conn.commit()
            logger.info("Database tables dropped")
            
            # Recreate tables
            self.initialize_database()
            logger.info("Database reset completed")
        except sqlite3.Error as e:
            logger.error(f"Database reset error: {e}")
            raise
            
    def add_media_file(self, file_path: str, safe_filename: str, media_type: str, 
                      file_size: int = None, duration: float = None,
                      checksum: str = None, detected_language: str = None) -> str:
        """
        Add a new media file to the database.
        
        Args:
            file_path: Original path to the media file
            safe_filename: Sanitized filename for processing
            media_type: Type of media ('audio' or 'video')
            file_size: Size of file in bytes (optional)
            duration: Duration of media in seconds (optional)
            checksum: File checksum (optional)
            detected_language: Detected language code (optional)
            
        Returns:
            The unique file_id generated for this media file
        """
        try:
            # Generate a unique ID for the file
            file_id = str(uuid.uuid4())
            
            # Insert file record
            self.cursor.execute("""
            INSERT INTO media_files (
                file_id, original_path, safe_filename, file_size,
                duration, checksum, media_type, detected_language
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_id, file_path, safe_filename, file_size, 
                 duration, checksum, media_type, detected_language))
            
            # Initialize processing status
            self.cursor.execute("""
            INSERT INTO processing_status (
                file_id, status, transcription_status, 
                translation_en_status, translation_he_status, translation_de_status,
                started_at, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_id, 'pending', 'not_started', 'not_started', 
                 'not_started', 'not_started', datetime.now(), datetime.now()))
            
            self.conn.commit()
            logger.debug(f"Added media file {file_id}: {file_path}")
            return file_id
            
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Error adding media file {file_path}: {e}")
            raise
            
    def update_media_file(self, file_id: str, **kwargs) -> bool:
        """
        Update metadata for an existing media file.
        
        Args:
            file_id: Unique ID of the file to update
            **kwargs: Fields to update as keyword arguments
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build update query dynamically based on provided fields
            allowed_fields = ['file_size', 'duration', 'checksum', 
                              'detected_language', 'safe_filename']
            
            update_fields = []
            update_values = []
            
            for key, value in kwargs.items():
                if key in allowed_fields:
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
            
            if not update_fields:
                logger.warning(f"No valid fields to update for file {file_id}")
                return False
                
            # Add file_id to values
            update_values.append(file_id)
            
            query = f"""
            UPDATE media_files SET 
                {', '.join(update_fields)}
            WHERE file_id = ?
            """
            
            self.cursor.execute(query, update_values)
            self.conn.commit()
            
            if self.cursor.rowcount == 0:
                logger.warning(f"No file with ID {file_id} found to update")
                return False
                
            logger.debug(f"Updated media file {file_id}")
            return True
            
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Error updating media file {file_id}: {e}")
            return False
            
    def update_status(self, file_id: str, status: str, **kwargs) -> bool:
        """
        Update the processing status for a file.
        
        Args:
            file_id: Unique ID of the file
            status: Overall status ('pending', 'in-progress', 'completed', 'failed')
            **kwargs: Additional status fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build update query dynamically based on provided fields
            allowed_fields = ['transcription_status', 'translation_en_status', 
                              'translation_he_status', 'translation_de_status', 'completed_at']
            
            update_fields = ["status = ?", "last_updated = ?"]
            update_values = [status, datetime.now()]
            
            # If status is changing to 'in-progress', set started_at if not already set
            if status == 'in-progress':
                # Check if started_at is already set
                self.cursor.execute(
                    "SELECT started_at FROM processing_status WHERE file_id = ?", 
                    (file_id,)
                )
                result = self.cursor.fetchone()
                
                if result and result['started_at'] is None:
                    update_fields.append("started_at = ?")
                    update_values.append(datetime.now())
            
            # If status is 'completed' or 'failed', set completed_at
            if status in ('completed', 'failed') and 'completed_at' not in kwargs:
                update_fields.append("completed_at = ?")
                update_values.append(datetime.now())
            
            # Increment attempts
            update_fields.append("attempts = attempts + 1")
            
            # Add additional fields
            for key, value in kwargs.items():
                if key in allowed_fields:
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
            
            # Add file_id to values
            update_values.append(file_id)
            
            query = f"""
            UPDATE processing_status SET 
                {', '.join(update_fields)}
            WHERE file_id = ?
            """
            
            self.cursor.execute(query, update_values)
            self.conn.commit()
            
            if self.cursor.rowcount == 0:
                logger.warning(f"No file with ID {file_id} found to update status")
                return False
                
            logger.debug(f"Updated status for file {file_id} to {status}")
            return True
            
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Error updating status for file {file_id}: {e}")
            return False
            
    def log_error(self, file_id: str, process_stage: str, 
                 error_message: str, error_details: str = None) -> bool:
        """
        Log an error that occurred during processing.
        
        Args:
            file_id: Unique ID of the file
            process_stage: Stage where the error occurred
            error_message: Brief error message
            error_details: Detailed error information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.cursor.execute("""
            INSERT INTO errors (
                file_id, process_stage, error_message, error_details
            ) VALUES (?, ?, ?, ?)
            """, (file_id, process_stage, error_message, error_details))
            
            self.conn.commit()
            logger.debug(f"Logged error for file {file_id} in stage {process_stage}")
            return True
            
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Error logging error for file {file_id}: {e}")
            return False
    
    def add_quality_evaluation(self, file_id: str, language: str, model: str, score: float, 
                         issues: List[str], comment: str = None, custom_data: str = None) -> bool:
        """
        Insert a quality evaluation record into the database.
        
        Args:
            file_id: Unique ID of the file
            language: Language code (en, de, he)
            model: Model used for evaluation (e.g., gpt-4, historical-gpt-4)
            score: Quality score (0-10)
            issues: List of issues identified
            comment: Optional comment or overall assessment
            custom_data: Optional JSON string with additional evaluation data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            issues_json = json.dumps(issues, ensure_ascii=False)
            self.cursor.execute(
                """
                INSERT INTO quality_evaluations (
                    file_id, language, model, score, issues, comment, evaluated_at, custom_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, language, model, score, issues_json, comment, datetime.now(), custom_data)
            )
            self.conn.commit()
            logger.debug(f"Logged quality evaluation for {file_id} [{language}] → {score}")
            return True
            
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Error logging quality evaluation for {file_id}: {e}")
            return False
            
    def update_translation_status(self, file_id: str, language: str, status: str) -> bool:
        """
        Update a specific translation_{language}_status field for a file.
        """
        try:
            col = f"translation_{language}_status"
            now = datetime.now()
            self.cursor.execute(
                f"UPDATE processing_status SET {col} = ?, last_updated = ? WHERE file_id = ?",
                (status, now, file_id)
            )
            self.conn.commit()
            logger.debug(f"Updated {col} for {file_id} → {status}")
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Error updating {col} for {file_id}: {e}")
            return False
            
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute an arbitrary SQL query and return results as a list of dictionaries.
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            
        Returns:
            List of dictionaries with query results
        """
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
                
            # Get column names
            columns = [description[0] for description in self.cursor.description]
            
            # Convert rows to dictionaries
            results = []
            for row in self.cursor.fetchall():
                results.append({columns[i]: row[i] for i in range(len(columns))})
                
            return results
            
        except sqlite3.Error as e:
            logger.error(f"Error executing query: {e}")
            return []
            
    def get_file_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get a file record by its original path.
        
        Args:
            file_path: Original path to the file
            
        Returns:
            File record as a dictionary or None if not found
        """
        try:
            self.cursor.execute(
                "SELECT * FROM media_files WHERE original_path = ?", 
                (file_path,)
            )
            row = self.cursor.fetchone()
            
            if row:
                return dict(row)
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Error getting file by path {file_path}: {e}")
            return None
            
    def get_file_status(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the processing status for a file.
        
        Args:
            file_id: Unique ID of the file
            
        Returns:
            Status record as a dictionary or None if not found
        """
        try:
            self.cursor.execute("""
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE m.file_id = ?
            """, (file_id,))
            
            row = self.cursor.fetchone()
            
            if row:
                return dict(row)
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Error getting status for file {file_id}: {e}")
            return None
            
    def get_files_by_status(self, status: Union[str, List[str]], limit: int = None) -> List[Dict[str, Any]]:
        """
        Get files with a specific processing status or multiple statuses.
        
        Args:
            status: Status to filter by ('pending', 'in-progress', 'completed', 'failed')
                   or a list of such statuses
            limit: Maximum number of files to return
            
        Returns:
            List of file records with their status
        """
        try:
            if isinstance(status, list):
                # Multiple statuses
                placeholders = ', '.join(['?' for _ in status])
                query = f"""
                SELECT m.*, p.*
                FROM media_files m
                JOIN processing_status p ON m.file_id = p.file_id
                WHERE p.status IN ({placeholders})
                ORDER BY p.last_updated DESC
                """
                params = tuple(status)
            else:
                # Single status
                query = """
                SELECT m.*, p.*
                FROM media_files m
                JOIN processing_status p ON m.file_id = p.file_id
                WHERE p.status = ?
                ORDER BY p.last_updated DESC
                """
                params = (status,)
            
            if limit is not None:
                query += f" LIMIT {int(limit)}"
                
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting files with status {status}: {e}")
            return []
            
    def get_pending_files(self, stage: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get files that are pending for a specific processing stage.
        
        Args:
            stage: Processing stage ('transcription', 'translation_en', 'translation_he', 'translation_de')
            limit: Maximum number of files to return
            
        Returns:
            List of file records pending for the specified stage
        """
        try:
            # Map stage to status field
            status_field = f"{stage}_status"
            
            query = f"""
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.{status_field} = 'not_started' AND p.status != 'failed'
            ORDER BY p.last_updated ASC
            """
            
            if limit is not None:
                query += f" LIMIT {int(limit)}"
                
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting pending files for stage {stage}: {e}")
            return []
            
    def get_files_for_transcription(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get files that need transcription: those with completed audio extraction
        but transcription_status of 'not_started' or 'failed', regardless of overall status.
        
        Args:
            limit: Maximum number of files to return
            
        Returns:
            List of file records ready for transcription
        """
        try:
            query = """
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.transcription_status IN ('not_started', 'failed')
            ORDER BY p.last_updated ASC
            """
            
            if limit is not None:
                query += f" LIMIT {int(limit)}"
                
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting files for transcription: {e}")
            return []
    
    def list_files(self, status_filter: Optional[str] = None) -> None:
        """
        Print a list of all tracked files and their status.
        
        Args:
            status_filter: Optional status to filter by
        """
        try:
            query = """
            SELECT m.file_id, m.original_path, m.media_type, 
                   p.status, p.attempts, p.started_at, p.completed_at,
                   p.transcription_status, p.translation_en_status, p.translation_he_status, p.translation_de_status
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            """
            
            if status_filter:
                query += f" WHERE p.status = '{status_filter}'"
                
            query += " ORDER BY p.last_updated DESC"
                
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            if not rows:
                print(f"No files found{' with status ' + status_filter if status_filter else ''}.")
                return
                
            # Print header
            print(f"\nMedia Files ({len(rows)} total{' with status ' + status_filter if status_filter else ''}):")
            print("-" * 100)
            print(f"{'ID':10} {'Status':12} {'Type':8} {'Attempts':8} {'Transcription':15} {'Translation EN':15} {'Translation HE':15} {'Translation DE':15} {'Path':30}")
            print("-" * 100)
            
            # Print each file
            for row in rows:
                print(f"{row['file_id'][:8]:10} {row['status']:12} {row['media_type']:8} "
                      f"{row['attempts']:8} {row['transcription_status']:15} "
                      f"{row['translation_en_status']:15} {row['translation_he_status']:15} "
                      f"{row['translation_de_status']:15} "
                      f"{Path(row['original_path']).name:30}")
                
        except sqlite3.Error as e:
            logger.error(f"Error listing files: {e}")
            print(f"Error listing files: {e}")
            
    def show_file_status(self, file_id: str) -> None:
        """
        Print detailed status information for a specific file.
        
        Args:
            file_id: Unique ID of the file
        """
        try:
            # Get file and status info
            file_status = self.get_file_status(file_id)
            
            if not file_status:
                print(f"No file found with ID: {file_id}")
                return
                
            # Get errors for this file
            self.cursor.execute(
                "SELECT * FROM errors WHERE file_id = ? ORDER BY timestamp DESC", 
                (file_id,)
            )
            errors = [dict(row) for row in self.cursor.fetchall()]
            
            # Print detailed status
            print("\nFile Details:")
            print("-" * 50)
            print(f"File ID:          {file_status['file_id']}")
            print(f"Original Path:    {file_status['original_path']}")
            print(f"Safe Filename:    {file_status['safe_filename']}")
            print(f"Media Type:       {file_status['media_type']}")
            print(f"Size:             {file_status['file_size']} bytes")
            print(f"Duration:         {file_status['duration']} seconds")
            print(f"Detected Lang:    {file_status['detected_language']}")
            print(f"Created At:       {file_status['created_at']}")
            
            print("\nProcessing Status:")
            print("-" * 50)
            print(f"Status:           {file_status['status']}")
            print(f"Transcription:    {file_status['transcription_status']}")
            print(f"Translation EN:   {file_status['translation_en_status']}")
            print(f"Translation HE:   {file_status['translation_he_status']}")
            print(f"Translation DE:   {file_status['translation_de_status']}")
            print(f"Started At:       {file_status['started_at']}")
            print(f"Completed At:     {file_status['completed_at']}")
            print(f"Last Updated:     {file_status['last_updated']}")
            print(f"Attempts:         {file_status['attempts']}")
            
            if errors:
                print("\nErrors:")
                print("-" * 50)
                for error in errors:
                    print(f"Timestamp:       {error['timestamp']}")
                    print(f"Process Stage:   {error['process_stage']}")
                    print(f"Error Message:   {error['error_message']}")
                    if error['error_details']:
                        print(f"Error Details:   {error['error_details']}")
                    print("-" * 30)
                    
        except sqlite3.Error as e:
            logger.error(f"Error showing file status {file_id}: {e}")
            print(f"Error showing file status: {e}")
            
    def get_summary_statistics(self) -> Dict[str, Any]:
        """
        Get summary statistics about the processing state.
        
        Returns:
            Dictionary containing statistics
        """
        try:
            # Total files
            self.cursor.execute("SELECT COUNT(*) as count FROM media_files")
            total_files = self.cursor.fetchone()['count']
            
            # Status counts
            self.cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM processing_status 
            GROUP BY status
            """)
            status_counts = {row['status']: row['count'] for row in self.cursor.fetchall()}
            
            # Stage completion counts
            stage_counts = {}
            for stage in ['transcription', 'translation_en', 'translation_he', 'translation_de']:
                status_field = f"{stage}_status"
                
                self.cursor.execute(f"""
                SELECT {status_field}, COUNT(*) as count 
                FROM processing_status 
                GROUP BY {status_field}
                """)
                
                stage_counts[stage] = {
                    row[status_field]: row['count'] for row in self.cursor.fetchall()
                }
                
            # Media type counts
            self.cursor.execute("""
            SELECT media_type, COUNT(*) as count 
            FROM media_files 
            GROUP BY media_type
            """)
            media_type_counts = {row['media_type']: row['count'] for row in self.cursor.fetchall()}
            
            # Error counts by stage
            self.cursor.execute("""
            SELECT process_stage, COUNT(*) as count 
            FROM errors 
            GROUP BY process_stage
            """)
            error_counts = {row['process_stage']: row['count'] for row in self.cursor.fetchall()}
            
            # Language distribution
            self.cursor.execute("""
            SELECT detected_language, COUNT(*) as count 
            FROM media_files 
            GROUP BY detected_language
            """)
            language_counts = {row['detected_language'] or 'unknown': row['count'] for row in self.cursor.fetchall()}
            
            # Total duration statistics
            self.cursor.execute("""
            SELECT SUM(duration) as total_duration, 
                   AVG(duration) as avg_duration,
                   MIN(duration) as min_duration,
                   MAX(duration) as max_duration
            FROM media_files
            WHERE duration IS NOT NULL
            """)
            duration_stats = dict(self.cursor.fetchone())
            
            # File size statistics
            self.cursor.execute("""
            SELECT SUM(file_size) as total_size, 
                   AVG(file_size) as avg_size,
                   MIN(file_size) as min_size,
                   MAX(file_size) as max_size
            FROM media_files
            WHERE file_size IS NOT NULL
            """)
            size_stats = dict(self.cursor.fetchone())
            
            # Word count estimate (based on average speaking rate of 150 words per minute)
            words_per_minute = 150
            if duration_stats['total_duration']:
                total_minutes = duration_stats['total_duration'] / 60
                word_count_estimate = int(total_minutes * words_per_minute)
            else:
                word_count_estimate = 0
            
            # Transcription completion statistics
            self.cursor.execute("""
            SELECT COUNT(*) as completed_count
            FROM processing_status
            WHERE transcription_status = 'completed'
            """)
            completed_transcriptions = self.cursor.fetchone()['completed_count']
            
            # Duration of completed transcriptions
            self.cursor.execute("""
            SELECT SUM(m.duration) as completed_duration
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.transcription_status = 'completed'
            """)
            completed_duration = self.cursor.fetchone()['completed_duration'] or 0
            
            # Word count data
            word_count_stats = self.get_word_count_stats()
            
            return {
                'total_files': total_files,
                'status_counts': status_counts,
                'stage_counts': stage_counts,
                'media_type_counts': media_type_counts,
                'error_counts': error_counts,
                'language_counts': language_counts,
                'duration_stats': duration_stats,
                'size_stats': size_stats,
                'word_count_estimate': word_count_estimate,
                'completed_transcriptions': completed_transcriptions,
                'completed_duration': completed_duration,
                'word_count_stats': word_count_stats
            }
            
        except sqlite3.Error as e:
            logger.error(f"Error getting summary statistics: {e}")
            return {
                'total_files': 0,
                'status_counts': {},
                'stage_counts': {},
                'media_type_counts': {},
                'error_counts': {},
                'language_counts': {},
                'duration_stats': {},
                'size_stats': {},
                'word_count_estimate': 0,
                'completed_transcriptions': 0,
                'completed_duration': 0,
                'word_count_stats': {}
            }

    def update_file_language(self, file_id: str, language_code: str) -> bool:
        """
        Update the detected language for a media file.
        
        Args:
            file_id: Unique ID of the file
            language_code: ISO language code (e.g., 'eng', 'deu')
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_media_file(file_id=file_id, detected_language=language_code)
        
    def update_transcription_status(self, file_id: str, status: str) -> bool:
        """
        Update the transcription status for a file.
        
        Args:
            file_id: Unique ID of the file
            status: Status ('not_started', 'in-progress', 'completed', 'failed')
            
        Returns:
            True if successful, False otherwise
        """
        # Get the current overall status
        current = self.get_file_status(file_id)
        
        # Keep the same overall status, only update the transcription status
        if current and 'status' in current:
            overall_status = current['status']
        else:
            # Default to 'in-progress' if we can't determine the current status
            overall_status = 'in-progress'
            
        return self.update_status(file_id=file_id, status=overall_status, transcription_status=status)

    def get_word_count_stats(self) -> Dict[str, Any]:
        """
        Get actual word count statistics from transcription files.
        
        Returns:
            Dictionary with word count statistics
        """
        try:
            # Get files with completed transcriptions
            self.cursor.execute("""
            SELECT file_id 
            FROM processing_status 
            WHERE transcription_status = 'completed'
            """)
            
            completed_files = [row['file_id'] for row in self.cursor.fetchall()]
            
            total_words = 0
            file_count = 0
            word_counts = []
            
            # Read each transcription file to count words
            for file_id in completed_files:
                # Get the transcript path
                self.cursor.execute("""
                SELECT safe_filename 
                FROM media_files 
                WHERE file_id = ?
                """, (file_id,))
                
                row = self.cursor.fetchone()
                if not row:
                    continue
                
                # Construct transcript path
                safe_filename = row['safe_filename']
                base_name = os.path.splitext(safe_filename)[0]
                transcript_path = os.path.join('./output/transcripts', f"{base_name}.txt")
                
                # Read and count words if file exists
                if os.path.exists(transcript_path):
                    try:
                        with open(transcript_path, 'r', encoding='utf-8') as f:
                            text = f.read()
                            # Count words (splitting by whitespace)
                            words = len(text.split())
                            total_words += words
                            word_counts.append(words)
                            file_count += 1
                    except Exception as e:
                        logger.warning(f"Error reading transcript file {transcript_path}: {e}")
            
            # Calculate statistics
            result = {
                'total_words': total_words,
                'file_count': file_count,
                'avg_words_per_file': total_words // file_count if file_count > 0 else 0
            }
            
            if word_counts:
                result['min_words'] = min(word_counts)
                result['max_words'] = max(word_counts)
            
            return result
            
        except sqlite3.Error as e:
            logger.error(f"Error getting word count statistics: {e}")
            return {
                'total_words': 0,
                'file_count': 0,
                'avg_words_per_file': 0
            }

    def get_files_with_unknown_language(self) -> List[Dict[str, Any]]:
        """
        Get files that have unknown or NULL language detection.
        
        Returns:
            List of file records with unknown language
        """
        try:
            query = """
            SELECT m.*, p.*
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE m.detected_language IS NULL 
               OR m.detected_language = ''
               OR m.detected_language = 'unknown'
            """
            
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting files with unknown language: {e}")
            return []

    def clear_errors(self) -> Tuple[bool, int]:
        """
        Clear all error records from the database.
        
        Returns:
            Tuple with success status and number of cleared records
        """
        try:
            self.cursor.execute("SELECT COUNT(*) FROM errors")
            count = self.cursor.fetchone()[0]
            
            self.cursor.execute("DELETE FROM errors")
            self.conn.commit()
            
            logger.info(f"Cleared {count} error records from database")
            return True, count
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Error clearing errors: {e}")
            return False, 0
            
    def clear_file_errors(self, file_id: str, process_stage: Optional[str] = None) -> Tuple[bool, int]:
        """
        Clear error records for a specific file.
        
        Args:
            file_id: The file ID to clear errors for
            process_stage: Optional stage to clear errors for (or all stages if None)
            
        Returns:
            Tuple with success status and number of cleared records
        """
        try:
            if process_stage:
                self.cursor.execute("SELECT COUNT(*) FROM errors WHERE file_id = ? AND process_stage = ?", 
                                 (file_id, process_stage))
                count = self.cursor.fetchone()[0]
                
                self.cursor.execute("DELETE FROM errors WHERE file_id = ? AND process_stage = ?", 
                                 (file_id, process_stage))
            else:
                self.cursor.execute("SELECT COUNT(*) FROM errors WHERE file_id = ?", (file_id,))
                count = self.cursor.fetchone()[0]
                
                self.cursor.execute("DELETE FROM errors WHERE file_id = ?", (file_id,))
                
            self.conn.commit()
            
            if count > 0:
                logger.debug(f"Cleared {count} error records for file {file_id}")
            return True, count
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Error clearing errors for file {file_id}: {e}")
            return False, 0
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute an arbitrary SQL query and return results as a list of dictionaries.
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            
        Returns:
            List of dictionaries with query results
        """
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
                
            # Get column names
            columns = [description[0] for description in self.cursor.description]
            
            # Convert rows to dictionaries
            results = []
            for row in self.cursor.fetchall():
                results.append({columns[i]: row[i] for i in range(len(columns))})
                
            return results
            
        except sqlite3.Error as e:
            logger.error(f"Error executing query: {e}")
            return []

    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get a file record by its UUID. Returns None if not found."""
        try:
            self.cursor.execute("SELECT * FROM media_files WHERE file_id = ?", (file_id,))
            row = self.cursor.fetchone()
            if row:
                return dict(row)
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting file by id {file_id}: {e}")
            return None
