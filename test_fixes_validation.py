#!/usr/bin/env python3
"""
Quick validation script to test that our fixes work correctly.
This will help validate the fixes without running the full test suite.
"""

import sys
import traceback

def test_imports():
    """Test that all critical imports work."""
    print("Testing imports...")
    
    try:
        # Test openai_integration imports
        from openai_integration import HebrewTranslator, APIUsageStats, TranslationProgress, PRICING
        print("✅ openai_integration imports successful")
    except Exception as e:
        print(f"❌ openai_integration import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        # Test hebrew_translation_pipeline imports  
        from hebrew_translation_pipeline import HebrewTranslationPipeline, FileProcessingResult, PipelineStatistics, estimate_translation_cost
        print("✅ hebrew_translation_pipeline imports successful")
    except Exception as e:
        print(f"❌ hebrew_translation_pipeline import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        # Test existing scribe modules still work
        from scribe.utils import SimpleWorkerPool, ProgressTracker, generate_file_id, retry
        from scribe.translate import HistoricalTranslator, retry
        from scribe.pipeline import Pipeline, PipelineConfig
        from scribe.database import Database
        print("✅ Scribe module imports successful")
    except Exception as e:
        print(f"❌ Scribe module import failed: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_class_instantiation():
    """Test that classes can be instantiated without errors."""
    print("\nTesting class instantiation...")
    
    try:
        # Test APIUsageStats
        stats = APIUsageStats()
        stats.update(100, 50, "gpt-4.1-mini", success=True)
        assert stats.total_requests == 1
        assert stats.successful_requests == 1
        assert stats.total_cost > 0
        print("✅ APIUsageStats working correctly")
    except Exception as e:
        print(f"❌ APIUsageStats test failed: {e}")
        return False
    
    try:
        # Test TranslationProgress
        progress = TranslationProgress()
        progress.mark_completed("test_file_1")
        progress.mark_failed("test_file_2", "Test error")
        assert progress.is_completed("test_file_1")
        assert not progress.is_completed("test_file_2")
        assert len(progress.failed_files) == 1
        print("✅ TranslationProgress working correctly")
    except Exception as e:
        print(f"❌ TranslationProgress test failed: {e}")
        return False
    
    try:
        # Test PipelineStatistics
        stats = PipelineStatistics(total_files=100, successful=80, failed=15, skipped=5)
        assert stats.success_rate == 80.0
        print("✅ PipelineStatistics working correctly")
    except Exception as e:
        print(f"❌ PipelineStatistics test failed: {e}")
        return False
    
    try:
        # Test FileProcessingResult
        result = FileProcessingResult(
            file_id="test_123",
            issue_type="placeholder", 
            success=True,
            processing_time=1.5,
            hebrew_char_count=150
        )
        assert result.file_id == "test_123"
        assert result.success == True
        print("✅ FileProcessingResult working correctly")
    except Exception as e:
        print(f"❌ FileProcessingResult test failed: {e}")
        return False
    
    return True

def test_pipeline_config_validation():
    """Test pipeline configuration validation."""
    print("\nTesting pipeline configuration validation...")
    
    try:
        from scribe.pipeline import Pipeline, PipelineConfig
        
        # Test invalid config gets fixed
        config = PipelineConfig(
            transcription_workers=0,  # Invalid
            translation_workers=-5,  # Invalid
            batch_size=0,  # Invalid
            evaluation_sample_size=-10,  # Invalid
            languages=[]  # Invalid
        )
        
        pipeline = Pipeline(config)
        
        # Check that invalid values were fixed
        assert pipeline.config.transcription_workers >= 1
        assert pipeline.config.translation_workers >= 1 
        assert pipeline.config.batch_size >= 1
        assert pipeline.config.evaluation_sample_size >= 1
        assert len(pipeline.config.languages) >= 1
        
        print("✅ Pipeline configuration validation working correctly")
    except Exception as e:
        print(f"❌ Pipeline configuration validation test failed: {e}")
        return False
    
    return True

def test_worker_pool_timeout():
    """Test worker pool timeout improvements."""
    print("\nTesting worker pool timeout handling...")
    
    try:
        from scribe.utils import SimpleWorkerPool
        import time
        
        def slow_task(x):
            time.sleep(0.1)  # Short delay
            return x * 2
        
        # Test with timeout
        with SimpleWorkerPool(max_workers=2, timeout=1.0) as pool:
            items = [1, 2, 3, 4, 5]
            results = pool.map(slow_task, items, timeout=0.5)
            # Should have some results, possibly some timeouts
            assert len(results) == len(items)
        
        print("✅ Worker pool timeout handling working correctly")
    except Exception as e:
        print(f"❌ Worker pool timeout test failed: {e}")
        return False
    
    return True

def test_retry_decorator():
    """Test improved retry decorator."""
    print("\nTesting retry decorator improvements...")
    
    try:
        from scribe.translate import retry
        
        # Test retry with return_on_failure='raise'
        @retry(tries=2, delay=0.01, return_on_failure='raise')
        def failing_function():
            raise ValueError("Test error")
        
        try:
            failing_function()
            assert False, "Should have raised exception"
        except ValueError:
            pass  # Expected
        
        # Test retry with default return_on_failure=None
        @retry(tries=2, delay=0.01)
        def failing_function_2():
            raise ValueError("Test error")
        
        result = failing_function_2()
        assert result is None
        
        print("✅ Retry decorator improvements working correctly")
    except Exception as e:
        print(f"❌ Retry decorator test failed: {e}")
        return False
    
    return True

def main():
    """Run all validation tests."""
    print("🧪 Running validation tests for test failure fixes...\n")
    
    all_passed = True
    
    # Run all tests
    test_functions = [
        test_imports,
        test_class_instantiation,
        test_pipeline_config_validation,
        test_worker_pool_timeout,
        test_retry_decorator
    ]
    
    for test_func in test_functions:
        try:
            if not test_func():
                all_passed = False
        except Exception as e:
            print(f"❌ {test_func.__name__} encountered an unexpected error: {e}")
            traceback.print_exc()
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 All validation tests PASSED!")
        print("The fixes should resolve the 6 critical test failures.")
    else:
        print("💥 Some validation tests FAILED!")
        print("There may be issues with the fixes that need to be addressed.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())