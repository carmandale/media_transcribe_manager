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
            translation_de_status='pending'
        )
        
        status = db.get_status(file_id)
        assert status['transcription_status'] == 'completed'
        assert status['translation_en_status'] == 'in-progress'
        assert status['translation_de_status'] == 'pending'
        
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
        all_ids = [f['file_id'] for thread_results in results for f in thread_results]
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