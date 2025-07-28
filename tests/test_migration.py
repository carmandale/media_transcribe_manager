"""
Tests for database migration to subtitle-first architecture.
"""
import pytest
import subprocess
import sqlite3
from pathlib import Path

from scribe.database import Database
from migrate_to_subtitle_segments import migrate_database


class TestSubtitleSegmentsMigration:
    """Test migration to subtitle-first architecture."""
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_migration_script_functionality(self, temp_dir):
        """Test that migration script works correctly."""
        db_path = temp_dir / "test_migration.db"
        
        # Create a database with some test data
        db = Database(db_path)
        
        # Add test files
        file_ids = []
        for i in range(3):
            file_id = db.add_file(
                file_path=f"/test/file_{i}.mp4",
                safe_filename=f"file_{i}_mp4",
                media_type="video"
            )
            file_ids.append(file_id)
        
        # Update some statuses
        db.update_status(file_ids[0], status='completed', transcription_status='completed')
        db.update_status(file_ids[1], status='in-progress', transcription_status='in-progress')
        
        # Add some errors
        db.log_error(file_ids[2], "transcription", "Test error")
        
        # Get pre-migration counts
        pre_media_count = len(db.get_all_files())
        pre_error_count = len(db.get_all_errors())
        
        db.close()
        
        # Verify pre-migration state
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        pre_tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        expected_pre_tables = {'media_files', 'processing_status', 'errors'}
        assert expected_pre_tables.issubset(pre_tables)
        assert 'subtitle_segments' not in pre_tables
        
        # Run migration
        success = migrate_database(str(db_path))
        assert success
        
        # Verify post-migration state
        db = Database(db_path)
        conn = db._get_connection()
        
        # Check tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        post_tables = {row[0] for row in cursor.fetchall()}
        
        expected_post_tables = {'media_files', 'processing_status', 'errors', 'subtitle_segments'}
        assert expected_post_tables.issubset(post_tables)
        
        # Check views exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {row[0] for row in cursor.fetchall()}
        expected_views = {'transcripts', 'segment_quality'}
        assert expected_views.issubset(views)
        
        # Verify data integrity
        post_media_count = len(db.get_all_files())
        post_error_count = len(db.get_all_errors())
        
        assert post_media_count == pre_media_count
        assert post_error_count == pre_error_count
        
        # Test new functionality
        subtitle_count = conn.execute("SELECT COUNT(*) FROM subtitle_segments").fetchone()[0]
        assert subtitle_count == 0  # Should be empty initially
        
        # Test views are queryable
        conn.execute("SELECT * FROM transcripts LIMIT 0")
        conn.execute("SELECT * FROM segment_quality LIMIT 0")
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_migration_idempotency(self, temp_dir):
        """Test that running migration twice doesn't cause issues."""
        db_path = temp_dir / "test_idempotent.db"
        
        # Create and populate database
        db = Database(db_path)
        file_id = db.add_file(
            file_path="/test/file.mp4",
            safe_filename="file_mp4",
            media_type="video"
        )
        db.close()
        
        # Run migration first time
        success1 = migrate_database(str(db_path))
        assert success1
        
        # Run migration second time
        success2 = migrate_database(str(db_path))
        assert success2
        
        # Verify database is still healthy
        db = Database(db_path)
        files = db.get_all_files()
        assert len(files) == 1
        assert files[0]['file_id'] == file_id
        
        conn = db._get_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subtitle_segments'")
        assert cursor.fetchone() is not None
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_migration_preserves_complex_data(self, temp_dir):
        """Test migration preserves complex existing data correctly."""
        db_path = temp_dir / "test_complex.db"
        
        # Create database with complex data
        db = Database(db_path)
        
        # Add files with various states
        completed_id = db.add_file("/test/completed.mp4", "completed_mp4", "video")
        db.update_status(completed_id, 
                        status='completed',
                        transcription_status='completed',
                        translation_en_status='completed',
                        translation_de_status='completed',
                        translation_he_status='completed')
        
        failed_id = db.add_file("/test/failed.mp4", "failed_mp4", "video")
        db.update_status(failed_id, status='failed')
        db.log_error(failed_id, "transcription", "API timeout", "Connection timeout after 30s")
        
        pending_id = db.add_file("/test/pending.mp3", "pending_mp3", "audio")
        # Leave as pending
        
        # Get comprehensive pre-migration state
        pre_summary = db.get_summary()
        pre_files = {f['file_id']: f for f in db.get_all_files()}
        pre_errors = db.get_all_errors()
        
        db.close()
        
        # Run migration
        success = migrate_database(str(db_path))
        assert success
        
        # Verify all data preserved
        db = Database(db_path)
        
        post_summary = db.get_summary()
        post_files = {f['file_id']: f for f in db.get_all_files()}
        post_errors = db.get_all_errors()
        
        # Compare summaries
        assert post_summary['total_files'] == pre_summary['total_files']
        assert post_summary['transcribed'] == pre_summary['transcribed']
        assert post_summary['en_translated'] == pre_summary['en_translated']
        assert post_summary['de_translated'] == pre_summary['de_translated']
        assert post_summary['he_translated'] == pre_summary['he_translated']
        assert post_summary['error_count'] == pre_summary['error_count']
        
        # Compare individual files
        assert len(post_files) == len(pre_files)
        for file_id in pre_files:
            assert file_id in post_files
            
            pre_file = pre_files[file_id]
            post_file = post_files[file_id]
            
            # Check key fields preserved
            assert post_file['original_path'] == pre_file['original_path']
            assert post_file['safe_filename'] == pre_file['safe_filename']
            assert post_file['media_type'] == pre_file['media_type']
            assert post_file['status'] == pre_file['status']
            assert post_file['transcription_status'] == pre_file['transcription_status']
            assert post_file['translation_en_status'] == pre_file['translation_en_status']
            assert post_file['translation_de_status'] == pre_file['translation_de_status']
            assert post_file['translation_he_status'] == pre_file['translation_he_status']
        
        # Compare errors
        assert len(post_errors) == len(pre_errors)
        
        db.close()
    
    @pytest.mark.unit
    @pytest.mark.database
    def test_migration_handles_nonexistent_database(self, temp_dir):
        """Test migration gracefully handles nonexistent database."""
        nonexistent_path = temp_dir / "nonexistent.db"
        
        success = migrate_database(str(nonexistent_path))
        assert not success
    
    @pytest.mark.integration
    def test_migration_script_cli(self, temp_dir):
        """Test migration script command line interface."""
        db_path = temp_dir / "test_cli.db"
        
        # Create test database
        db = Database(db_path)
        db.add_file("/test/cli.mp4", "cli_mp4", "video")
        db.close()
        
        # Test dry-run
        result = subprocess.run([
            "python", "migrate_to_subtitle_segments.py",
            "--db-path", str(db_path),
            "--dry-run"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        assert result.returncode == 0
        assert "needs migration" in result.stdout.lower()
        
        # Test actual migration
        result = subprocess.run([
            "python", "migrate_to_subtitle_segments.py",
            "--db-path", str(db_path)
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        assert result.returncode == 0
        assert "completed successfully" in result.stdout.lower()
        
        # Test dry-run after migration
        result = subprocess.run([
            "python", "migrate_to_subtitle_segments.py",
            "--db-path", str(db_path),
            "--dry-run"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        assert result.returncode == 0
        assert "already migrated" in result.stdout.lower()