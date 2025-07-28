"""
Comprehensive tests for the database module.

Tests cover all major functionality including:
- Database initialization and schema creation
- File management (add, get, update)
- Status tracking and updates
- Error logging
- Query methods
- Thread safety
- Transaction handling
"""
import pytest
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

from scribe.database import Database


class TestDatabaseInitialization:
    """Test database initialization and schema creation."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_database_creation(self, temp_dir):
        """Test that database is created with proper schema."""
        db_path = temp_dir / "test.db"
        db = Database(db_path)
        
        assert db_path.exists()
        
        # Verify tables exist
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        expected_tables = {'media_files', 'processing_status', 'errors'}
        assert expected_tables.issubset(tables)
        
        # Check indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        expected_indexes = {
            'idx_status', 
            'idx_transcription_status',
            'idx_translation_statuses',
            'idx_last_updated'
        }
        assert expected_indexes.issubset(indexes)
        
        conn.close()
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_subtitle_segments_table_creation(self, temp_dir):
        """Test that subtitle_segments table is created with proper schema."""
        db_path = temp_dir / "test.db"
        db = Database(db_path)
        
        # Apply migration to create subtitle_segments table
        db._migrate_to_subtitle_segments()
        
        # Verify table exists
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subtitle_segments'")
        assert cursor.fetchone() is not None
        
        # Check table schema
        cursor.execute("PRAGMA table_info(subtitle_segments)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}  # name: type
        
        # Basic columns (excluding generated columns like duration)
        expected_columns = {
            'id': 'INTEGER',
            'interview_id': 'TEXT',  # TEXT because it references media_files.file_id which is TEXT
            'segment_index': 'INTEGER',
            'start_time': 'REAL',
            'end_time': 'REAL',
            'original_text': 'TEXT',
            'german_text': 'TEXT',
            'english_text': 'TEXT',
            'hebrew_text': 'TEXT',
            'confidence_score': 'REAL',
            'processing_timestamp': 'DATETIME'
        }
        
        for col_name, col_type in expected_columns.items():
            assert col_name in columns
            assert columns[col_name] == col_type
        
        # Test that we can query the duration column (generated column)
        cursor.execute("SELECT duration FROM subtitle_segments LIMIT 0")
        assert len(cursor.description) == 1  # Should be able to query duration column
        
        # Check indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='subtitle_segments'")
        segment_indexes = {row[0] for row in cursor.fetchall()}
        expected_segment_indexes = {
            'idx_subtitle_segments_interview_id',
            'idx_subtitle_segments_timing',
            'idx_subtitle_segments_search',
            'idx_subtitle_segments_original_text',
            'idx_subtitle_segments_english_text',
            'idx_subtitle_segments_german_text'
        }
        assert expected_segment_indexes.issubset(segment_indexes)
        
        # Check views exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {row[0] for row in cursor.fetchall()}
        expected_views = {'transcripts', 'segment_quality'}
        assert expected_views.issubset(views)
        
        conn.close()
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_subtitle_segments_constraints(self, temp_dir):
        """Test subtitle_segments table constraints work correctly."""
        db_path = temp_dir / "test.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Add a test interview first
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Test valid segment insertion
        valid_segment = (
            interview_id, 1, 0.0, 5.0, "Hello world", 
            "Hallo Welt", "Hello world", "שלום עולם", 0.95
        )
        
        conn.execute("""
            INSERT INTO subtitle_segments (
                interview_id, segment_index, start_time, end_time, 
                original_text, german_text, english_text, hebrew_text, 
                confidence_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, valid_segment)
        conn.commit()
        
        # Test constraint violations
        
        # 1. Negative start_time should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time, 
                    original_text, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (interview_id, 2, -1.0, 5.0, "Test", 0.8))
            conn.commit()
        
        # 2. end_time <= start_time should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time, 
                    original_text, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (interview_id, 3, 5.0, 5.0, "Test", 0.8))
            conn.commit()
        
        # 3. Confidence score > 1.0 should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time, 
                    original_text, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (interview_id, 4, 6.0, 10.0, "Test", 1.5))
            conn.commit()
        
        # 4. Duplicate (interview_id, segment_index) should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time, 
                    original_text, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (interview_id, 1, 10.0, 15.0, "Duplicate", 0.8))
            conn.commit()
        
        conn.close()
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_backward_compatibility_views(self, temp_dir):
        """Test that backward compatibility views work correctly."""
        db_path = temp_dir / "test.db"
        db = Database(db_path)
        db._migrate_to_subtitle_segments()
        
        # Add test interview
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        conn = sqlite3.connect(str(db_path))
        
        # Insert test segments
        segments = [
            (interview_id, 1, 0.0, 2.5, "Hello", "Hallo", "Hello", "שלום", 0.95),
            (interview_id, 2, 2.5, 5.0, "world", "Welt", "world", "עולם", 0.90),
            (interview_id, 3, 5.0, 8.0, "test", "Test", "test", "בדיקה", 0.85)
        ]
        
        for segment in segments:
            conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time,
                    original_text, german_text, english_text, hebrew_text,
                    confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, segment)
        conn.commit()
        
        # Test transcripts view
        cursor = conn.execute("SELECT * FROM transcripts WHERE interview_id = ?", (interview_id,))
        transcript = cursor.fetchone()
        
        assert transcript is not None
        # Check concatenated text (SQLite GROUP_CONCAT uses space separator by default)
        original_words = transcript[1].split()  # original_transcript
        assert "Hello" in original_words
        assert "world" in original_words  
        assert "test" in original_words
        
        assert transcript[5] == 3  # total_segments
        assert abs(transcript[6] - 0.9) < 0.01  # avg_confidence (0.95+0.90+0.85)/3
        assert transcript[7] == 0.0  # transcript_start
        assert transcript[8] == 8.0  # transcript_end
        assert transcript[9] == 8.0  # total_duration
        
        # Test segment_quality view
        cursor = conn.execute("SELECT * FROM segment_quality WHERE interview_id = ?", (interview_id,))
        quality = cursor.fetchone()
        
        assert quality is not None
        assert quality[1] == 3  # total_segments
        assert abs(quality[2] - 2.667) < 0.01  # avg_segment_duration (2.5+2.5+3.0)/3 = 8.0/3 = 2.667
        assert quality[3] == 2.5  # min_segment_duration
        assert quality[4] == 3.0  # max_segment_duration
        assert abs(quality[5] - 0.9) < 0.01  # avg_confidence
        assert quality[6] == 0  # low_confidence_segments (none < 0.8)
        assert quality[7] == 0  # short_segments (none < 1.0)
        assert quality[8] == 0  # long_segments (none > 10.0)
        
        conn.close()
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_database_path_creation(self, temp_dir):
        """Test that parent directories are created if needed."""
        db_path = temp_dir / "nested" / "path" / "test.db"
        db = Database(db_path)
        
        assert db_path.exists()
        assert db_path.parent.exists()
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_thread_local_connections(self, temp_dir):
        """Test that each thread gets its own connection."""
        db_path = temp_dir / "test.db"
        db = Database(db_path)
        
        connections = []
        
        def get_connection():
            conn = db._get_connection()
            connections.append(id(conn))
        
        # Get connections from different threads
        threads = []
        for _ in range(3):
            t = threading.Thread(target=get_connection)
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        # Each thread should have gotten a different connection
        assert len(set(connections)) == 3
        db.close()


class TestFileManagement:
    """Test file tracking functionality."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_add_file(self, temp_dir):
        """Test adding a file to the database."""
        db = Database(temp_dir / "test.db")
        
        file_id = db.add_file(
            file_path="/path/to/test.mp4",
            safe_filename="test_mp4",
            media_type="video",
            file_size=1024000,
            duration=3600.5,
            checksum="abc123"
        )
        
        assert file_id is not None
        assert len(file_id) == 36  # UUID length
        
        # Verify file was added
        file_record = db.get_file_by_id(file_id)
        assert file_record is not None
        assert file_record['original_path'] == str(Path("/path/to/test.mp4").resolve())
        assert file_record['safe_filename'] == "test_mp4"
        assert file_record['media_type'] == "video"
        assert file_record['file_size'] == 1024000
        assert file_record['duration'] == 3600.5
        assert file_record['checksum'] == "abc123"
        
        # Verify processing status was created
        status = db.get_status(file_id)
        assert status is not None
        assert status['status'] == 'pending'
        assert status['transcription_status'] == 'not_started'
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_add_file_simple(self, temp_dir, mock_audio_file):
        """Test simple file addition."""
        db = Database(temp_dir / "test.db")
        
        file_id = db.add_file_simple(mock_audio_file)
        
        assert file_id is not None
        
        # Verify file was added with auto-detected properties
        file_record = db.get_file_by_id(file_id)
        assert file_record is not None
        assert file_record['original_path'] == str(mock_audio_file.resolve())
        assert file_record['media_type'] == 'video'  # .mp4 extension
        assert file_record['file_size'] > 0
        
        # Test duplicate prevention
        duplicate_id = db.add_file_simple(mock_audio_file)
        assert duplicate_id is None
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_file_by_path(self, temp_dir):
        """Test retrieving file by path."""
        db = Database(temp_dir / "test.db")
        
        # Add a file
        file_path = "/test/path/audio.wav"
        file_id = db.add_file(
            file_path=file_path,
            safe_filename="audio_wav",
            media_type="audio"
        )
        
        # Test retrieval
        file_record = db.get_file_by_path(file_path)
        assert file_record is not None
        assert file_record['file_id'] == file_id
        assert file_record['safe_filename'] == "audio_wav"
        
        # Test non-existent file
        assert db.get_file_by_path("/non/existent/file.mp3") is None
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_all_files(self, temp_dir):
        """Test retrieving all files."""
        db = Database(temp_dir / "test.db")
        
        # Add multiple files
        file_ids = []
        for i in range(3):
            file_id = db.add_file(
                file_path=f"/test/file_{i}.mp4",
                safe_filename=f"file_{i}_mp4",
                media_type="video"
            )
            file_ids.append(file_id)
        
        # Get all files
        all_files = db.get_all_files()
        assert len(all_files) == 3
        
        # Verify all files are present
        retrieved_ids = {f['file_id'] for f in all_files}
        assert retrieved_ids == set(file_ids)
        
        # Verify join with processing_status worked
        for file_record in all_files:
            assert 'status' in file_record
            assert 'transcription_status' in file_record
        
        db.close()


class TestStatusManagement:
    """Test processing status tracking."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_update_status(self, temp_dir):
        """Test updating processing status."""
        db = Database(temp_dir / "test.db")
        
        # Add a file
        file_id = db.add_file(
            file_path="/test/audio.mp3",
            safe_filename="audio_mp3",
            media_type="audio"
        )
        
        # Update overall status
        assert db.update_status(file_id, status='in-progress')
        
        status = db.get_status(file_id)
        assert status['status'] == 'in-progress'
        assert status['started_at'] is not None
        
        # Update to completed
        assert db.update_status(file_id, status='completed')
        
        status = db.get_status(file_id)
        assert status['status'] == 'completed'
        assert status['completed_at'] is not None
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_update_stage_status(self, temp_dir):
        """Test updating stage-specific status."""
        db = Database(temp_dir / "test.db")
        
        file_id = db.add_file(
            file_path="/test/audio.mp3",
            safe_filename="audio_mp3",
            media_type="audio"
        )
        
        # Update transcription status
        assert db.update_status(
            file_id, 
            transcription_status='in-progress'
        )
        
        status = db.get_status(file_id)
        assert status['transcription_status'] == 'in-progress'
        
        # Update multiple statuses
        assert db.update_status(
            file_id,
            transcription_status='completed',
            translation_en_status='in-progress',
            translation_de_status='not_started'
        )
        
        status = db.get_status(file_id)
        assert status['transcription_status'] == 'completed'
        assert status['translation_en_status'] == 'in-progress'
        assert status['translation_de_status'] == 'not_started'
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_increment_attempts(self, temp_dir):
        """Test incrementing attempt counter."""
        db = Database(temp_dir / "test.db")
        
        file_id = db.add_file(
            file_path="/test/audio.mp3",
            safe_filename="audio_mp3",
            media_type="audio"
        )
        
        # Initial attempts should be 0
        status = db.get_status(file_id)
        assert status['attempts'] == 0
        
        # Increment attempts
        assert db.increment_attempts(file_id)
        status = db.get_status(file_id)
        assert status['attempts'] == 1
        
        # Increment again
        assert db.increment_attempts(file_id)
        status = db.get_status(file_id)
        assert status['attempts'] == 2
        
        db.close()


class TestQueryMethods:
    """Test various query methods."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_pending_files(self, temp_dir):
        """Test retrieving pending files for processing."""
        db = Database(temp_dir / "test.db")
        
        # Add files with different statuses
        file_ids = []
        for i in range(5):
            file_id = db.add_file(
                file_path=f"/test/file_{i}.mp3",
                safe_filename=f"file_{i}_mp3",
                media_type="audio"
            )
            file_ids.append(file_id)
        
        # Update some statuses
        db.update_status(file_ids[0], transcription_status='completed')
        db.update_status(file_ids[1], transcription_status='in-progress')
        db.update_status(file_ids[2], transcription_status='failed')
        db.update_status(file_ids[3], status='failed')  # Overall failed
        
        # Get pending transcription files
        pending = db.get_pending_files('transcription')
        
        # Should only get file_ids[4] (not_started) 
        assert len(pending) == 1
        assert pending[0]['file_id'] == file_ids[4]
        
        # Test with limit
        pending_limited = db.get_pending_files('transcription', limit=1)
        assert len(pending_limited) == 1
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_files_by_status(self, temp_dir):
        """Test retrieving files by overall status."""
        db = Database(temp_dir / "test.db")
        
        # Add files with different statuses
        completed_ids = []
        failed_ids = []
        
        for i in range(3):
            file_id = db.add_file(
                file_path=f"/test/completed_{i}.mp3",
                safe_filename=f"completed_{i}_mp3",
                media_type="audio"
            )
            db.update_status(file_id, status='completed')
            completed_ids.append(file_id)
        
        for i in range(2):
            file_id = db.add_file(
                file_path=f"/test/failed_{i}.mp3",
                safe_filename=f"failed_{i}_mp3",
                media_type="audio"
            )
            db.update_status(file_id, status='failed')
            failed_ids.append(file_id)
        
        # Test single status
        completed = db.get_files_by_status('completed')
        assert len(completed) == 3
        assert {f['file_id'] for f in completed} == set(completed_ids)
        
        # Test multiple statuses
        all_done = db.get_files_by_status(['completed', 'failed'])
        assert len(all_done) == 5
        
        # Test with limit
        limited = db.get_files_by_status('completed', limit=2)
        assert len(limited) == 2
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_stuck_files(self, temp_dir):
        """Test retrieving stuck files."""
        db = Database(temp_dir / "test.db")
        
        # Add files
        normal_id = db.add_file(
            file_path="/test/normal.mp3",
            safe_filename="normal_mp3",
            media_type="audio"
        )
        
        stuck_id = db.add_file(
            file_path="/test/stuck.mp3",
            safe_filename="stuck_mp3",
            media_type="audio"
        )
        
        # Set one as in-progress recently
        db.update_status(normal_id, status='in-progress')
        
        # Manually set one as stuck (in-progress for long time)
        with db.transaction() as conn:
            old_time = datetime.now() - timedelta(hours=2)
            conn.execute("""
                UPDATE processing_status 
                SET status = 'in-progress',
                    last_updated = ?
                WHERE file_id = ?
            """, (old_time, stuck_id))
        
        # Get stuck files (default 30 min timeout)
        stuck = db.get_stuck_files()
        assert len(stuck) == 1
        assert stuck[0]['file_id'] == stuck_id
        
        # Test with custom timeout
        stuck_1hr = db.get_stuck_files(timeout_minutes=60)
        assert len(stuck_1hr) == 1
        
        stuck_3hr = db.get_stuck_files(timeout_minutes=180)
        assert len(stuck_3hr) == 0
        
        db.close()


class TestErrorLogging:
    """Test error logging functionality."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_log_error(self, temp_dir):
        """Test logging errors."""
        db = Database(temp_dir / "test.db")
        
        file_id = db.add_file(
            file_path="/test/audio.mp3",
            safe_filename="audio_mp3",
            media_type="audio"
        )
        
        # Log an error
        assert db.log_error(
            file_id=file_id,
            process_stage="transcription",
            error_message="API rate limit exceeded",
            error_details="429 Too Many Requests"
        )
        
        # Retrieve errors
        errors = db.get_errors(file_id)
        assert len(errors) == 1
        assert errors[0]['process_stage'] == "transcription"
        assert errors[0]['error_message'] == "API rate limit exceeded"
        assert errors[0]['error_details'] == "429 Too Many Requests"
        assert errors[0]['timestamp'] is not None
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_all_errors(self, temp_dir):
        """Test retrieving all errors."""
        db = Database(temp_dir / "test.db")
        
        # Add multiple files with errors
        for i in range(3):
            file_id = db.add_file(
                file_path=f"/test/file_{i}.mp3",
                safe_filename=f"file_{i}_mp3",
                media_type="audio"
            )
            db.log_error(
                file_id=file_id,
                process_stage=f"stage_{i}",
                error_message=f"Error {i}"
            )
        
        # Get all errors
        all_errors = db.get_errors()
        assert len(all_errors) == 3
        
        # Verify order (most recent first)
        assert all_errors[0]['error_message'] == "Error 2"
        assert all_errors[2]['error_message'] == "Error 0"
        
        db.close()


class TestSummaryStatistics:
    """Test summary and statistics methods."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_summary(self, temp_dir):
        """Test getting summary statistics."""
        db = Database(temp_dir / "test.db")
        
        # Add files with various statuses
        for i in range(10):
            file_id = db.add_file(
                file_path=f"/test/file_{i}.mp3",
                safe_filename=f"file_{i}_mp3",
                media_type="audio"
            )
            
            # Set different statuses
            if i < 3:
                db.update_status(file_id, status='completed')
                db.update_status(file_id, 
                    transcription_status='completed',
                    translation_en_status='completed',
                    translation_de_status='completed',
                    translation_he_status='completed'
                )
            elif i < 5:
                db.update_status(file_id, status='in-progress')
                db.update_status(file_id, transcription_status='completed')
            elif i < 7:
                db.update_status(file_id, status='failed')
                db.log_error(file_id, "test", "Test error")
        
        summary = db.get_summary()
        
        assert summary['total_files'] == 10
        assert summary['status_counts']['completed'] == 3
        assert summary['status_counts']['in-progress'] == 2
        assert summary['status_counts']['failed'] == 2
        assert summary['status_counts']['pending'] == 3
        
        assert summary['transcribed'] == 5  # 3 completed + 2 in-progress
        assert summary['en_translated'] == 3
        assert summary['de_translated'] == 3
        assert summary['he_translated'] == 3
        
        assert summary['error_count'] == 2
        
        db.close()


class TestTransactionHandling:
    """Test transaction management."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_transaction_commit(self, temp_dir):
        """Test successful transaction commit."""
        db = Database(temp_dir / "test.db")
        
        with db.transaction() as conn:
            conn.execute("""
                INSERT INTO media_files (
                    file_id, original_path, safe_filename, media_type
                ) VALUES (?, ?, ?, ?)
            """, ("test-id", "/test/path", "test", "audio"))
        
        # Verify data was committed
        file_record = db.get_file_by_id("test-id")
        assert file_record is not None
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_transaction_rollback(self, temp_dir):
        """Test transaction rollback on error."""
        db = Database(temp_dir / "test.db")
        
        try:
            with db.transaction() as conn:
                conn.execute("""
                    INSERT INTO media_files (
                        file_id, original_path, safe_filename, media_type
                    ) VALUES (?, ?, ?, ?)
                """, ("test-id", "/test/path", "test", "audio"))
                
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Verify data was rolled back
        file_record = db.get_file_by_id("test-id")
        assert file_record is None
        
        db.close()


class TestThreadSafety:
    """Test thread safety of database operations."""
    
    @pytest.mark.unit
    @pytest.mark.database
    @pytest.mark.slow
    def test_concurrent_writes(self, temp_dir):
        """Test concurrent writes from multiple threads."""
        db = Database(temp_dir / "test.db")
        
        num_threads = 5
        files_per_thread = 10
        results = []
        
        def add_files(thread_id):
            thread_results = []
            for i in range(files_per_thread):
                file_id = db.add_file(
                    file_path=f"/test/thread_{thread_id}_file_{i}.mp3",
                    safe_filename=f"thread_{thread_id}_file_{i}_mp3",
                    media_type="audio"
                )
                thread_results.append(file_id)
            results.append(thread_results)
        
        # Start threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=add_files, args=(i,))
            t.start()
            threads.append(t)
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify all files were added
        all_files = db.get_all_files()
        assert len(all_files) == num_threads * files_per_thread
        
        # Verify no duplicate IDs
        all_ids = [file_id for thread_results in results for file_id in thread_results]
        assert len(all_ids) == len(set(all_ids))
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_concurrent_reads(self, temp_dir):
        """Test concurrent reads from multiple threads."""
        db = Database(temp_dir / "test.db")
        
        # Add test data
        file_id = db.add_file(
            file_path="/test/shared.mp3",
            safe_filename="shared_mp3",
            media_type="audio"
        )
        
        read_results = []
        
        def read_file():
            for _ in range(10):
                result = db.get_file_by_id(file_id)
                read_results.append(result is not None)
        
        # Start threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=read_file)
            t.start()
            threads.append(t)
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # All reads should have succeeded
        assert all(read_results)
        assert len(read_results) == 50
        
        db.close()


class TestCompatibilityMethods:
    """Test methods for backward compatibility."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_execute_query(self, temp_dir):
        """Test generic query execution method."""
        db = Database(temp_dir / "test.db")
        
        # Add test data
        for i in range(3):
            db.add_file(
                file_path=f"/test/file_{i}.mp3",
                safe_filename=f"file_{i}_mp3",
                media_type="audio"
            )
        
        # Test SELECT query
        results = db.execute_query("SELECT * FROM media_files ORDER BY safe_filename")
        assert len(results) == 3
        assert results[0]['safe_filename'] == "file_0_mp3"
        
        # Test with parameters
        results = db.execute_query(
            "SELECT * FROM media_files WHERE media_type = ?",
            ("audio",)
        )
        assert len(results) == 3
        
        # Test aggregation
        results = db.execute_query("SELECT COUNT(*) as count FROM media_files")
        assert results[0]['count'] == 3
        
        db.close()


class TestSubtitleSegments:
    """Test subtitle segments functionality for subtitle-first architecture."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_add_subtitle_segments(self, temp_dir):
        """Test adding subtitle segments to the database."""
        db = Database(temp_dir / "test.db")
        db._migrate_to_subtitle_segments()
        
        # Add test interview
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        # Add subtitle segments
        segments = [
            {
                'interview_id': interview_id,
                'segment_index': 1,
                'start_time': 0.0,
                'end_time': 2.5,
                'original_text': "Hello world",
                'german_text': "Hallo Welt",
                'english_text': "Hello world", 
                'hebrew_text': "שלום עולם",
                'confidence_score': 0.95
            },
            {
                'interview_id': interview_id,
                'segment_index': 2,
                'start_time': 2.5,
                'end_time': 5.0,
                'original_text': "How are you?",
                'german_text': "Wie geht es dir?",
                'english_text': "How are you?",
                'hebrew_text': "איך אתה?",
                'confidence_score': 0.92
            }
        ]
        
        for segment in segments:
            segment_id = db.add_subtitle_segment(**segment)
            assert segment_id is not None
        
        # Verify segments were added
        retrieved_segments = db.get_subtitle_segments(interview_id)
        assert len(retrieved_segments) == 2
        
        # Check first segment
        first_segment = retrieved_segments[0]
        assert first_segment['segment_index'] == 1
        assert first_segment['start_time'] == 0.0
        assert first_segment['end_time'] == 2.5
        assert first_segment['original_text'] == "Hello world"
        assert first_segment['confidence_score'] == 0.95
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_get_subtitle_segments_by_time_range(self, temp_dir):
        """Test retrieving subtitle segments by time range."""
        db = Database(temp_dir / "test.db")
        db._migrate_to_subtitle_segments()
        
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        # Add segments with different time ranges
        segments = [
            (interview_id, 1, 0.0, 2.0, "First", 0.95),
            (interview_id, 2, 2.0, 4.0, "Second", 0.90),
            (interview_id, 3, 4.0, 6.0, "Third", 0.85),
            (interview_id, 4, 6.0, 8.0, "Fourth", 0.92),
            (interview_id, 5, 8.0, 10.0, "Fifth", 0.88)
        ]
        
        conn = sqlite3.connect(str(temp_dir / "test.db"))
        for segment in segments:
            conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time, 
                    original_text, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, segment)
        conn.commit()
        conn.close()
        
        # Test getting segments within time range
        segments_in_range = db.get_subtitle_segments_by_time_range(
            interview_id, start_time=2.0, end_time=6.0
        )
        
        assert len(segments_in_range) == 2  # segments 2 and 3
        assert segments_in_range[0]['original_text'] == "Second"
        assert segments_in_range[1]['original_text'] == "Third"
        
        # Test getting all segments (no time range)
        all_segments = db.get_subtitle_segments(interview_id)
        assert len(all_segments) == 5
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_update_subtitle_segment_translations(self, temp_dir):
        """Test updating translations for existing segments."""
        db = Database(temp_dir / "test.db")
        db._migrate_to_subtitle_segments()
        
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        # Add segment with only original text
        segment_id = db.add_subtitle_segment(
            interview_id=interview_id,
            segment_index=1,
            start_time=0.0,
            end_time=2.5,
            original_text="Hello world",
            confidence_score=0.95
        )
        
        # Update with translations
        db.update_subtitle_segment_translations(
            segment_id=segment_id,
            german_text="Hallo Welt",
            english_text="Hello world",
            hebrew_text="שלום עולם"
        )
        
        # Verify translations were added
        segments = db.get_subtitle_segments(interview_id)
        assert len(segments) == 1
        
        segment = segments[0]
        assert segment['german_text'] == "Hallo Welt"
        assert segment['english_text'] == "Hello world" 
        assert segment['hebrew_text'] == "שלום עולם"
        assert segment['original_text'] == "Hello world"  # Should be unchanged
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_subtitle_segment_quality_metrics(self, temp_dir):
        """Test quality metrics calculation for subtitle segments."""
        db = Database(temp_dir / "test.db")
        db._migrate_to_subtitle_segments()
        
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        # Add segments with varying quality
        segments = [
            (interview_id, 1, 0.0, 0.5, "Short1", 0.95),    # Short segment (0.5s)
            (interview_id, 2, 0.5, 1.0, "Short2", 0.85),    # Short segment (0.5s)
            (interview_id, 3, 1.0, 2.0, "Normal2", 0.75),   # Low confidence (1.0s)
            (interview_id, 4, 2.0, 13.0, "Long", 0.90),     # Long segment (11.0s)
            (interview_id, 5, 13.0, 14.0, "Normal3", 0.88)  # Normal segment (1.0s)
        ]
        
        conn = sqlite3.connect(str(temp_dir / "test.db"))
        for segment in segments:
            conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time, 
                    original_text, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, segment)
        conn.commit()
        conn.close()
        
        # Test quality metrics
        quality_metrics = db.get_subtitle_quality_metrics(interview_id)
        
        assert quality_metrics['total_segments'] == 5
        assert quality_metrics['avg_confidence'] == 0.866  # (0.95+0.85+0.75+0.90+0.88)/5
        assert quality_metrics['low_confidence_segments'] == 1  # confidence < 0.8
        assert quality_metrics['short_segments'] == 2  # duration < 1.0 (0.5s + 0.5s)
        assert quality_metrics['long_segments'] == 1  # duration > 10.0 (11.0s)
        # avg_segment_duration = (0.5+0.5+1.0+11.0+1.0)/5 = 14.0/5 = 2.8
        assert abs(quality_metrics['avg_segment_duration'] - 2.8) < 0.1
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_subtitle_segments_timing_validation(self, temp_dir):
        """Test timing validation for subtitle segments."""
        db = Database(temp_dir / "test.db")
        db._migrate_to_subtitle_segments()
        
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        # Add valid segments
        valid_segments = [
            (interview_id, 1, 0.0, 2.0, "First"),
            (interview_id, 2, 2.0, 4.0, "Second"),  # No gap
            (interview_id, 3, 4.5, 6.0, "Third")    # Small gap (0.5s)
        ]
        
        conn = sqlite3.connect(str(temp_dir / "test.db"))
        for segment in valid_segments:
            conn.execute("""
                INSERT INTO subtitle_segments (
                    interview_id, segment_index, start_time, end_time, 
                    original_text
                ) VALUES (?, ?, ?, ?, ?)
            """, segment)
        conn.commit()
        conn.close()
        
        # Test timing validation
        timing_issues = db.validate_subtitle_timing(interview_id)
        
        assert 'gaps' in timing_issues
        assert 'overlaps' in timing_issues
        assert len(timing_issues['gaps']) == 1  # One gap between segments 2 and 3
        assert len(timing_issues['overlaps']) == 0  # No overlaps
        
        # Check gap details
        gap = timing_issues['gaps'][0]
        assert gap['after_segment'] == 2
        assert gap['before_segment'] == 3
        assert gap['gap_duration'] == 0.5
        
        db.close()


class TestIntegratedWorkflows:
    """Test combined transcript + segment workflows for backward compatibility."""
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_combined_transcript_segment_workflow(self, temp_dir):
        """Test that transcript and segment workflows work together seamlessly."""
        db = Database(temp_dir / "test.db")
        db._migrate_to_subtitle_segments()
        
        # Create interview
        interview_id = db.add_file(
            file_path="/test/interview.mp4",
            safe_filename="interview_mp4",
            media_type="video"
        )
        
        # Add subtitle segments (simulating segment-first processing)
        segments = [
            {
                'interview_id': interview_id,
                'segment_index': 1,
                'start_time': 0.0,
                'end_time': 3.0,
                'original_text': "Welcome to the interview.",
                'german_text': "Willkommen zum Interview.",
                'english_text': "Welcome to the interview.",
                'hebrew_text': "ברוכים הבאים לראיון.",
                'confidence_score': 0.92
            },
            {
                'interview_id': interview_id,
                'segment_index': 2,
                'start_time': 3.0,
                'end_time': 6.0,
                'original_text': "Please tell us your story.",
                'german_text': "Bitte erzählen Sie uns Ihre Geschichte.",
                'english_text': "Please tell us your story.",
                'hebrew_text': "אנא ספרו לנו את הסיפור שלכם.",
                'confidence_score': 0.88
            }
        ]
        
        for segment in segments:
            db.add_subtitle_segment(**segment)
        
        # Test that transcript view provides consolidated data
        conn = db._get_connection()
        cursor = conn.execute("SELECT * FROM transcripts WHERE interview_id = ?", (interview_id,))
        transcript = cursor.fetchone()
        
        assert transcript is not None
        # Should have concatenated text from both segments
        assert "Welcome to the interview" in transcript[1]  # original_transcript
        assert "Please tell us your story" in transcript[1]
        assert "Willkommen zum Interview" in transcript[2]  # german_transcript
        assert "Bitte erzählen Sie uns Ihre Geschichte" in transcript[2]
        
        # Test quality metrics
        quality_metrics = db.get_subtitle_quality_metrics(interview_id)
        assert quality_metrics['total_segments'] == 2
        assert quality_metrics['avg_confidence'] == 0.9  # (0.92 + 0.88) / 2
        
        # Test that both access patterns work
        # 1. Segment-based access (new way)
        segments_retrieved = db.get_subtitle_segments(interview_id)
        assert len(segments_retrieved) == 2
        
        # 2. Traditional database queries still work
        all_files = db.get_all_files()
        assert len(all_files) == 1
        assert all_files[0]['file_id'] == interview_id
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_mixed_processing_compatibility(self, temp_dir):
        """Test compatibility between old transcript processing and new segment processing."""
        db = Database(temp_dir / "test.db")
        db._migrate_to_subtitle_segments()
        
        # Simulate mixed environment: some interviews processed old way, some new way
        
        # Old-style interview (no segments, just database tracking)
        old_interview_id = db.add_file(
            file_path="/test/old_interview.mp4",
            safe_filename="old_interview_mp4",
            media_type="video"
        )
        db.update_status(old_interview_id, 
                        transcription_status='completed',
                        translation_en_status='completed')
        
        # New-style interview (with segments)
        new_interview_id = db.add_file(
            file_path="/test/new_interview.mp4",
            safe_filename="new_interview_mp4",
            media_type="video"
        )
        
        # Add segments for new interview
        db.add_subtitle_segment(
            interview_id=new_interview_id,
            segment_index=1,
            start_time=0.0,
            end_time=5.0,
            original_text="This is the new processing approach.",
            english_text="This is the new processing approach.",
            confidence_score=0.95
        )
        
        # Both should appear in general queries
        all_files = db.get_all_files()
        assert len(all_files) == 2
        
        file_ids = {f['file_id'] for f in all_files}
        assert old_interview_id in file_ids
        assert new_interview_id in file_ids
        
        # Old interview should not appear in segment queries
        old_segments = db.get_subtitle_segments(old_interview_id)
        assert len(old_segments) == 0
        
        # New interview should appear in segment queries
        new_segments = db.get_subtitle_segments(new_interview_id)
        assert len(new_segments) == 1
        
        # Summary should include both
        summary = db.get_summary()
        assert summary['total_files'] == 2
        
        db.close()
    
    @pytest.mark.integration
    @pytest.mark.database
    def test_processing_pipeline_integration(self, temp_dir):
        """Test integration with existing processing pipeline patterns."""
        db = Database(temp_dir / "test.db")
        db._migrate_to_subtitle_segments()
        
        # Simulate processing pipeline workflow
        interview_id = db.add_file(
            file_path="/test/pipeline_interview.mp4",
            safe_filename="pipeline_interview_mp4",
            media_type="video"
        )
        
        # Stage 1: Start transcription
        db.update_status(interview_id, 
                        status='in-progress',
                        transcription_status='in-progress')
        
        # Stage 2: Transcription complete, add segments
        segments = [
            (interview_id, 1, 0.0, 2.0, "First segment", 0.9),
            (interview_id, 2, 2.0, 4.0, "Second segment", 0.85),
            (interview_id, 3, 4.0, 6.0, "Third segment", 0.92)
        ]
        
        for interview_id_val, idx, start, end, text, conf in segments:
            db.add_subtitle_segment(
                interview_id=interview_id_val,
                segment_index=idx,
                start_time=start,
                end_time=end,
                original_text=text,
                confidence_score=conf
            )
        
        db.update_status(interview_id, transcription_status='completed')
        
        # Stage 3: Start translation
        db.update_status(interview_id, translation_en_status='in-progress')
        
        # Update segments with translations
        retrieved_segments = db.get_subtitle_segments(interview_id)
        for segment in retrieved_segments:
            db.update_subtitle_segment_translations(
                segment_id=segment['id'],
                english_text=f"EN: {segment['original_text']}"
            )
        
        db.update_status(interview_id, translation_en_status='completed')
        
        # Stage 4: Complete processing
        db.update_status(interview_id, status='completed')
        
        # Verify final state
        final_status = db.get_status(interview_id)
        assert final_status['status'] == 'completed'
        assert final_status['transcription_status'] == 'completed'
        assert final_status['translation_en_status'] == 'completed'
        
        # Verify segments have translations
        final_segments = db.get_subtitle_segments(interview_id)
        assert len(final_segments) == 3
        for segment in final_segments:
            assert segment['english_text'].startswith("EN:")
        
        # Verify quality metrics
        quality = db.get_subtitle_quality_metrics(interview_id)
        assert quality['total_segments'] == 3
        assert quality['avg_confidence'] > 0.8
        
        db.close()


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_invalid_media_type(self, temp_dir):
        """Test handling of invalid media type."""
        db = Database(temp_dir / "test.db")
        
        with pytest.raises(sqlite3.IntegrityError):
            db.add_file(
                file_path="/test/file.xyz",
                safe_filename="file_xyz",
                media_type="invalid"  # Not 'audio' or 'video'
            )
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_duplicate_file_path(self, temp_dir):
        """Test handling of duplicate file paths."""
        db = Database(temp_dir / "test.db")
        
        # Add a file
        db.add_file(
            file_path="/test/unique.mp3",
            safe_filename="unique_mp3",
            media_type="audio"
        )
        
        # Try to add the same file again
        with pytest.raises(sqlite3.IntegrityError):
            db.add_file(
                file_path="/test/unique.mp3",
                safe_filename="unique_mp3_2",
                media_type="audio"
            )
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_update_nonexistent_file(self, temp_dir):
        """Test updating status of non-existent file."""
        db = Database(temp_dir / "test.db")
        
        result = db.update_status("non-existent-id", status='completed')
        assert result is False
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_empty_database_queries(self, temp_dir):
        """Test queries on empty database."""
        db = Database(temp_dir / "test.db")
        
        assert db.get_all_files() == []
        assert db.get_pending_files('transcription') == []
        assert db.get_files_by_status('completed') == []
        assert db.get_stuck_files() == []
        assert db.get_errors() == []
        
        summary = db.get_summary()
        assert summary['total_files'] == 0
        assert summary['error_count'] == 0
        
        db.close()