# Tests Directory

This directory contains test suites for the Scribe system. Tests ensure code quality and catch regressions before they impact production processing.

## Test Structure

### Unit Tests
- **test_db_manager.py**: Database operations testing
  - Connection pooling
  - CRUD operations
  - Thread safety

- **test_file_manager.py**: File handling tests
  - Path normalization
  - Unicode handling
  - Directory operations

- **test_transcription.py**: Transcription module tests
  - API mocking
  - Error handling
  - Audio format support

- **test_translation.py**: Translation module tests
  - Multi-language support
  - API failover
  - Context preservation

### Integration Tests
- **test_pipeline.py**: End-to-end pipeline tests
  - Full processing flow
  - State transitions
  - Error recovery

- **test_worker_pool.py**: Parallel processing tests
  - Thread pool management
  - Task distribution
  - Error propagation

## Running Tests

### Run All Tests
```bash
# From project root
uv run python -m pytest tests/

# With coverage
uv run python -m pytest tests/ --cov=core_modules
```

### Run Specific Test File
```bash
uv run python -m pytest tests/test_db_manager.py

# Run specific test
uv run python -m pytest tests/test_db_manager.py::test_connection_pooling
```

### Run with Verbose Output
```bash
uv run python -m pytest tests/ -v

# Show print statements
uv run python -m pytest tests/ -s
```

## Test Patterns

### Standard Test Structure
```python
import pytest
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core_modules.module_name import ClassName

class TestClassName:
    def setup_method(self):
        """Setup for each test"""
        pass
    
    def teardown_method(self):
        """Cleanup after each test"""
        pass
    
    def test_feature(self):
        """Test specific feature"""
        assert expected == actual
```

### Using Fixtures
```python
@pytest.fixture
def test_db():
    """Provide test database"""
    db = DatabaseManager(':memory:')
    yield db
    db.close()

def test_with_db(test_db):
    """Test using fixture"""
    result = test_db.execute_query("SELECT 1")
    assert result is not None
```

## Test Data

### Mock Files
- Place test media files in `tests/test_data/`
- Use small files to keep tests fast
- Include various formats for compatibility testing

### Database Fixtures
- Use in-memory SQLite for speed
- Create fresh database for each test
- Load known test data as needed

## Writing New Tests

### Guidelines
1. **Test one thing** - Each test should verify a single behavior
2. **Use descriptive names** - `test_transcription_handles_mp3_files`
3. **Clean up resources** - Close files, connections, etc.
4. **Mock external APIs** - Don't make real API calls in tests
5. **Test edge cases** - Empty inputs, unicode, large files

### Example Test
```python
def test_file_manager_handles_unicode():
    """Ensure FileManager correctly handles unicode filenames"""
    fm = FileManager()
    test_path = "/path/to/tëst_fîlé.mp3"
    
    normalized = fm.normalize_path(test_path)
    assert normalized is not None
    assert fm.is_valid_media_file(normalized)
```

## Continuous Integration

Tests should be run:
- Before committing changes
- In CI/CD pipeline
- After major refactoring

## Test Coverage

Aim for:
- 80%+ coverage for core_modules
- 100% coverage for critical paths (database, file operations)
- Focus on error handling paths

Check coverage:
```bash
uv run python -m pytest tests/ --cov=core_modules --cov-report=html
# Open htmlcov/index.html
```

## Common Test Issues

### Import Errors
- Ensure test files add project root to sys.path
- Use absolute imports from core_modules

### Database Lock Errors
- Use separate test database
- Clean up connections in teardown
- Don't share database between tests

### API Rate Limits
- Always mock external API calls
- Use pytest-mock or unittest.mock
- Test both success and failure responses

## Test Maintenance

- Update tests when changing functionality
- Remove obsolete tests
- Keep tests fast (< 5 seconds per test)
- Run tests before pushing changes