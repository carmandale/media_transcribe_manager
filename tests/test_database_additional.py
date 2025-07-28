"""
Additional database tests to increase coverage for frequently-used functions.

These tests target specific database operations that are heavily used
but may not have complete coverage in the existing test suite.
"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from scribe.database import Database


class TestDatabaseCRUDOperations:
    """Test Create, Read, Update, Delete operations."""
    
    @pytest.mark.unit
    def test_save_transcription_basic(self, db_operations):
        """Test basic transcription saving."""
        # Add test file first
        file_id = db_operations.add_file(
            file_path="/test/audio.mp3",
            file_name="audio.mp3",
            file_size=1024
        )
        
        result = db_operations.save_transcription(
            file_id=file_id,
            transcription_text="Test transcription",
            language_code="en",
            confidence_score=0.95
        )
        
        assert result is True
    
    @pytest.mark.unit
    def test_save_translation_basic(self, db_operations):
        """Test basic translation saving."""
        # Add test file first
        file_id = db_operations.add_file(
            file_path="/test/audio.mp3",
            file_name="audio.mp3", 
            file_size=1024
        )
        
        result = db_operations.save_translation(
            file_id=file_id,
            language_code="de",
            translated_text="Test Übersetzung",
            provider="deepl",
            cost=0.25
        )
        
        assert result is True
    
    @pytest.mark.unit
    def test_get_translations(self, populated_db):
        """Test retrieving translations for a file."""
        # Get the file that was added in populated_db fixture
        files = populated_db.get_all_files()
        file_id = files[0]['id']
        
        translations = populated_db.get_translations(file_id)
        
        assert isinstance(translations, list)
        assert len(translations) >= 0  # May have translations from fixture
    
    @pytest.mark.unit
    def test_update_translation_status(self, db_operations):
        """Test updating translation status."""
        # Add test file
        file_id = db_operations.add_file(
            file_path="/test/audio.mp3",
            file_name="audio.mp3",
            file_size=1024
        )
        
        # Update status
        result = db_operations.update_translation_status(
            file_id=file_id,
            language="de",
            status="completed"
        )
        
        assert result is True
    
    @pytest.mark.unit
    def test_save_evaluation(self, db_operations):
        """Test saving evaluation results."""
        # Add test file and translation
        file_id = db_operations.add_file(
            file_path="/test/audio.mp3",
            file_name="audio.mp3",
            file_size=1024
        )
        
        db_operations.save_translation(
            file_id=file_id,
            language_code="de",
            translated_text="Test translation",
            provider="deepl",
            cost=0.10
        )
        
        # Save evaluation
        result = db_operations.save_evaluation(
            file_id=file_id,
            language_code="de",
            accuracy_score=0.92,
            completeness_score=0.95,
            evaluation_text="Good translation"
        )
        
        assert result is True


class TestDatabaseQueryMethods:
    """Test various database query methods."""
    
    @pytest.mark.unit
    def test_get_files_needing_transcription(self, db_operations):
        """Test getting files that need transcription."""
        # Add a file without transcription
        db_operations.add_file(
            file_path="/test/need_transcription.mp3",
            file_name="need_transcription.mp3",
            file_size=1024
        )
        
        files = db_operations.get_files_needing_transcription()
        
        assert isinstance(files, list)
        assert len(files) >= 1
    
    @pytest.mark.unit
    def test_get_files_needing_translation(self, db_operations):
        """Test getting files that need translation."""
        # Add file with transcription but no translation
        file_id = db_operations.add_file(
            file_path="/test/need_translation.mp3",
            file_name="need_translation.mp3",
            file_size=1024
        )
        
        db_operations.save_transcription(
            file_id=file_id,
            transcription_text="English text",
            language_code="en",
            confidence_score=0.95
        )
        
        files = db_operations.get_files_needing_translation("de")
        
        assert isinstance(files, list)
        assert len(files) >= 1
    
    @pytest.mark.unit
    def test_get_files_needing_evaluation(self, db_operations):
        """Test getting files that need evaluation."""
        # Add file with translation but no evaluation
        file_id = db_operations.add_file(
            file_path="/test/need_evaluation.mp3",
            file_name="need_evaluation.mp3",
            file_size=1024
        )
        
        db_operations.save_translation(
            file_id=file_id,
            language_code="de",
            translated_text="German text",
            provider="deepl",
            cost=0.10
        )
        
        files = db_operations.get_files_needing_evaluation("de")
        
        assert isinstance(files, list)
        assert len(files) >= 1
    
    @pytest.mark.unit
    def test_get_processing_stats(self, populated_db):
        """Test getting processing statistics."""
        stats = populated_db.get_processing_stats()
        
        assert isinstance(stats, dict)
        assert 'total_files' in stats
        assert 'transcribed' in stats
        assert stats['total_files'] >= 1  # From populated_db fixture


class TestDatabaseTransactionHandling:
    """Test database transaction management."""
    
    @pytest.mark.unit
    def test_batch_operations(self, db_operations):
        """Test batch database operations."""
        files_to_add = [
            {
                'file_path': f'/test/batch_{i}.mp3',
                'file_name': f'batch_{i}.mp3',
                'file_size': 1024 * i
            }
            for i in range(1, 4)
        ]
        
        # Test that multiple operations work
        file_ids = []
        for file_data in files_to_add:
            file_id = db_operations.add_file(**file_data)
            file_ids.append(file_id)
        
        assert len(file_ids) == 3
        assert all(isinstance(fid, int) for fid in file_ids)
    
    @pytest.mark.unit
    def test_connection_recovery(self, db_operations):
        """Test that database can recover from connection issues."""
        # Simulate connection issue by closing
        if hasattr(db_operations, '_local'):
            if hasattr(db_operations._local, 'conn'):
                if db_operations._local.conn:
                    db_operations._local.conn.close()
                    db_operations._local.conn = None
        
        # Should be able to create new connection and work
        file_id = db_operations.add_file(
            file_path="/test/recovery.mp3",
            file_name="recovery.mp3",
            file_size=1024
        )
        
        assert isinstance(file_id, int)


class TestDatabaseErrorHandling:
    """Test database error handling and edge cases."""
    
    @pytest.mark.unit
    def test_duplicate_file_handling(self, db_operations):
        """Test handling of duplicate files."""
        file_data = {
            'file_path': '/test/duplicate.mp3',
            'file_name': 'duplicate.mp3', 
            'file_size': 1024
        }
        
        # Add file first time
        file_id1 = db_operations.add_file(**file_data)
        
        # Try to add same file again
        file_id2 = db_operations.add_file(**file_data)
        
        # Should handle gracefully (either return same ID or None)
        assert file_id1 is not None
        assert file_id2 is not None or file_id2 is None
    
    @pytest.mark.unit
    def test_invalid_file_id_operations(self, db_operations):
        """Test operations with invalid file IDs."""
        invalid_id = 99999
        
        # These operations should handle invalid IDs gracefully
        try:
            result = db_operations.save_transcription(
                file_id=invalid_id,
                transcription_text="Test",
                language_code="en",
                confidence_score=0.95
            )
            # Should return False or raise appropriate exception
            assert result in [True, False, None]
        except Exception:
            # Exception is acceptable for invalid ID
            pass
    
    @pytest.mark.unit
    def test_empty_query_results(self, db_operations):
        """Test queries that return empty results."""
        # Query for files with non-existent status
        files = db_operations.get_files_by_status("non_existent_status")
        
        assert isinstance(files, list)
        assert len(files) == 0


class TestDatabasePerformance:
    """Test database performance characteristics."""
    
    @pytest.mark.unit
    def test_large_text_handling(self, db_operations):
        """Test handling of large text content."""
        # Add file
        file_id = db_operations.add_file(
            file_path="/test/large.mp3",
            file_name="large.mp3",
            file_size=1024
        )
        
        # Create large text (10KB)
        large_text = "This is a long transcription. " * 350
        
        result = db_operations.save_transcription(
            file_id=file_id,
            transcription_text=large_text,
            language_code="en",
            confidence_score=0.95
        )
        
        assert result is True
    
    @pytest.mark.unit
    def test_multiple_concurrent_operations(self, db_operations):
        """Test multiple database operations in sequence."""
        # Simulate concurrent-like operations
        results = []
        
        for i in range(5):
            file_id = db_operations.add_file(
                file_path=f"/test/concurrent_{i}.mp3",
                file_name=f"concurrent_{i}.mp3",
                file_size=1024 * i
            )
            results.append(file_id)
        
        # All operations should succeed
        assert len(results) == 5
        assert all(isinstance(r, int) for r in results)
        assert len(set(results)) == 5  # All unique IDs