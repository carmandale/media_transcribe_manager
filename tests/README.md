# Scribe Test Suite Documentation

This document provides comprehensive documentation for the Scribe project's test suite, including best practices, test organization, and guidelines for writing and running tests.

## Table of Contents

1. [Overview](#overview)
2. [Test Organization](#test-organization)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Test Coverage](#test-coverage)
6. [Best Practices](#best-practices)
7. [Continuous Integration](#continuous-integration)
8. [Troubleshooting](#troubleshooting)

## Overview

The Scribe test suite uses pytest as the testing framework and includes:

- **Unit tests**: Test individual functions and classes in isolation
- **Integration tests**: Test interactions between components
- **End-to-end tests**: Test complete workflows
- **Performance tests**: Test system performance and scalability

### Key Features

- Comprehensive test coverage (target: 80%+)
- Parallel test execution support
- Detailed coverage reporting
- Test categorization with markers
- Fixture-based test data management
- Mock-based external service isolation

## Test Organization

```
tests/
├── README.md                 # This file
├── conftest.py              # Shared fixtures and configuration
├── test_database.py         # Database module tests
├── test_transcribe.py       # Transcription module tests
├── test_translate.py        # Translation module tests
├── test_evaluate.py         # Evaluation module tests
├── test_pipeline.py         # Pipeline orchestration tests
├── test_utils.py            # Utility function tests
├── test_audit_system.py     # Audit system tests (existing)
├── test_backup.py           # Backup functionality tests (existing)
└── ...                      # Other test files
```

### Test Markers

Tests are categorized using pytest markers:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (may use real services)
- `@pytest.mark.slow` - Tests that take >1 second
- `@pytest.mark.external` - Tests requiring external services
- `@pytest.mark.database` - Database-related tests
- `@pytest.mark.async` - Asynchronous tests
- `@pytest.mark.hebrew` - Hebrew language-specific tests

## Running Tests

### Basic Usage

```bash
# Run all tests with coverage
python run_tests.py

# Run without coverage
python run_tests.py --no-cov

# Run specific test file
python run_tests.py tests/test_database.py

# Run tests matching pattern
python run_tests.py -k "test_hebrew"

# Run only unit tests
python run_tests.py -m unit

# Run tests in parallel (4 processes)
python run_tests.py -n 4
```

### Advanced Options

```bash
# Run with increased verbosity
python run_tests.py -vv

# Drop into debugger on failure
python run_tests.py --pdb

# Run only previously failed tests
python run_tests.py --lf

# Generate HTML coverage report
python run_tests.py --html

# Set coverage threshold
python run_tests.py --cov-fail-under=90
```

### Direct pytest Usage

```bash
# Run with pytest directly
pytest tests/

# Run with specific options
pytest -v --cov=scribe --cov-report=html

# Run tests for specific marker
pytest -m "unit and not slow"
```

## Writing Tests

### Test Structure

```python
import pytest
from unittest.mock import Mock, patch

from scribe.module import function_to_test


class TestFeatureName:
    """Test suite for specific feature."""
    
    @pytest.fixture
    def setup_data(self):
        """Fixture providing test data."""
        return {"key": "value"}
    
    @pytest.mark.unit
    def test_basic_functionality(self, setup_data):
        """Test basic feature functionality."""
        result = function_to_test(setup_data)
        assert result == expected_value
    
    @pytest.mark.unit
    @patch('scribe.module.external_service')
    def test_with_mock(self, mock_service):
        """Test with mocked external service."""
        mock_service.return_value = "mocked response"
        result = function_to_test()
        assert result == "expected"
        mock_service.assert_called_once()
```

### Using Fixtures

Common fixtures are available in `conftest.py`:

```python
def test_with_fixtures(temp_dir, db_operations, mock_audio_file):
    """Test using common fixtures."""
    # temp_dir: Temporary directory for test files
    # db_operations: Database instance with test database
    # mock_audio_file: Path to mock audio file
    
    # Your test code here
```

### Testing Async Code

```python
@pytest.mark.async
async def test_async_function():
    """Test asynchronous function."""
    result = await async_function()
    assert result == expected
```

### Testing with Hebrew Content

```python
@pytest.mark.unit
@pytest.mark.hebrew
def test_hebrew_processing():
    """Test Hebrew language processing."""
    hebrew_text = "טקסט בעברית"
    result = process_hebrew(hebrew_text)
    assert contains_hebrew(result)
```

## Test Coverage

### Coverage Goals

- Overall coverage: 80%+
- Core modules (database, transcribe, translate): 90%+
- Critical paths: 95%+

### Viewing Coverage

```bash
# Terminal report
python run_tests.py

# HTML report
python run_tests.py --html
# Then open htmlcov/index.html in browser

# Coverage for specific module
pytest --cov=scribe.database --cov-report=term-missing tests/test_database.py
```

### Coverage Configuration

Coverage settings are in `.coveragerc`:
- Excludes test files and utilities
- Ignores defensive code blocks
- Shows missing line numbers

## Best Practices

### 1. Test Isolation

- Each test should be independent
- Use fixtures for setup/teardown
- Mock external dependencies
- Clean up resources in teardown

### 2. Test Naming

- Use descriptive names: `test_<what>_<condition>_<expected_result>`
- Group related tests in classes
- Document complex test scenarios

### 3. Assertions

```python
# Be specific with assertions
assert result.status == "completed"  # Good
assert result  # Less informative

# Use pytest's rich assertions
assert actual_list == expected_list  # Shows diff

# Custom assertion messages
assert result, f"Expected result, got {result}"
```

### 4. Mocking

```python
# Mock at the right level
with patch('scribe.module.specific_function') as mock:
    mock.return_value = "test data"
    # test code

# Use spec for better mocks
mock_obj = Mock(spec=RealClass)
```

### 5. Performance

- Mark slow tests with `@pytest.mark.slow`
- Use test fixtures to reduce setup time
- Consider parallel execution for large test suites

### 6. Data Management

```python
# Use fixtures for test data
@pytest.fixture
def sample_transcript():
    return {
        "text": "Sample transcript",
        "language": "en",
        "segments": [...]
    }

# Use parametrize for multiple scenarios
@pytest.mark.parametrize("language,expected", [
    ("en", "English"),
    ("de", "German"),
    ("he", "Hebrew"),
])
def test_language_detection(language, expected):
    result = detect_language(language)
    assert result == expected
```

## Continuous Integration

### GitHub Actions Configuration

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, "3.10", "3.11"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        python run_tests.py -n auto
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: tests
        name: tests
        entry: python run_tests.py -m "unit and not slow"
        language: system
        pass_filenames: false
        always_run: true
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure project is in Python path
   export PYTHONPATH=$PYTHONPATH:$(pwd)
   ```

2. **Database Lock Errors**
   - Use separate test databases
   - Ensure proper cleanup in fixtures

3. **Flaky Tests**
   - Add retries for network operations
   - Use proper wait conditions
   - Mock time-dependent operations

4. **Slow Tests**
   - Use pytest-xdist for parallel execution
   - Cache expensive operations
   - Mark slow tests appropriately

### Debugging Tests

```bash
# Run specific test with debugging
pytest -vv -s tests/test_module.py::TestClass::test_method --pdb

# Show test setup
pytest --setup-show tests/test_module.py

# Profile slow tests
pytest --durations=10
```

### Test Environment

Set test-specific environment variables:

```bash
# In .env.test
SCRIBE_TEST_MODE=1
DATABASE_PATH=test_media_tracking.db
LOG_LEVEL=DEBUG
```

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure all tests pass
3. Maintain or improve coverage
4. Update test documentation
5. Add appropriate test markers

### Test Checklist

- [ ] Unit tests for new functions/classes
- [ ] Integration tests for component interactions
- [ ] Edge cases and error conditions tested
- [ ] Mocks used for external dependencies
- [ ] Tests are fast and reliable
- [ ] Documentation updated
- [ ] Coverage maintained above 80%

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Testing best practices](https://docs.python-guide.org/writing/tests/)