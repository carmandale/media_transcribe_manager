# Scribe Testing Framework

## Overview

A comprehensive testing framework has been implemented for the Scribe project, providing robust test coverage, best practices, and continuous integration support.

## What's Been Created

### 1. Test Configuration Files

- **`pytest.ini`**: Main pytest configuration with:
  - Test discovery patterns
  - Coverage settings (80% minimum)
  - Test markers for categorization
  - Logging configuration
  - Async test support

- **`.coveragerc`**: Coverage configuration with:
  - Source code paths
  - Exclusion patterns
  - Report formatting
  - Branch coverage tracking

### 2. Test Infrastructure

- **`tests/conftest.py`**: Shared test fixtures and utilities:
  - Database fixtures with test isolation
  - Mock audio/video files
  - Sample data for transcripts, translations, evaluations
  - Environment variable mocking
  - Helper functions for assertions

### 3. Comprehensive Test Suites

- **`tests/test_database.py`**: 500+ lines covering:
  - Database initialization and schema
  - File management (add, get, update)
  - Status tracking
  - Query methods
  - Thread safety
  - Transaction handling

- **`tests/test_transcribe.py`**: 600+ lines covering:
  - Audio extraction from video
  - File segmentation for large files
  - ElevenLabs API integration
  - Retry logic
  - SRT subtitle generation

- **`tests/test_translate.py`**: 700+ lines covering:
  - Critical Hebrew routing logic
  - Multi-provider support (DeepL, Microsoft, OpenAI)
  - Text chunking for long documents
  - Language detection
  - Error handling and retries

- **`tests/test_evaluate.py`**: 500+ lines covering:
  - Hebrew validation and sanity checks
  - Translation quality scoring
  - Enhanced evaluation modes
  - File-based evaluation
  - GPT integration

- **`tests/test_pipeline.py`**: 400+ lines covering:
  - Full workflow orchestration
  - Batch processing
  - Worker pool management
  - Progress tracking
  - Error recovery

- **`tests/test_utils.py`**: 400+ lines covering:
  - Path normalization
  - Filename sanitization
  - File ID generation
  - Progress tracking
  - Worker pool utilities

### 4. Test Runner and Documentation

- **`run_tests.py`**: User-friendly test runner with:
  - Coverage reporting
  - Parallel execution
  - Test filtering by marker/keyword
  - HTML report generation
  - Debug mode support
  - Failed test tracking

- **`tests/README.md`**: Comprehensive testing documentation:
  - Test organization guide
  - Running tests examples
  - Writing tests best practices
  - Coverage goals and viewing
  - CI/CD integration
  - Troubleshooting guide

### 5. CI/CD Integration

- **`GITHUB_ACTIONS_SETUP.md`**: Instructions for setting up GitHub Actions workflow with:
  - Multi-Python version testing (3.8-3.11)
  - Separate Hebrew language tests
  - Code quality checks (linting)
  - Security scanning
  - Coverage reporting to Codecov
  - Test summary generation

- **`requirements-dev.txt`**: Development dependencies

## Key Features

### Test Markers
- `unit`: Fast, isolated unit tests
- `integration`: Tests with external dependencies
- `hebrew`: Hebrew-specific functionality
- `slow`: Long-running tests
- `database`: Database-related tests
- `async`: Asynchronous tests
- `external`: Tests requiring external services

### Coverage Goals
- Overall: 80%+ coverage
- Core modules: 90%+ coverage
- Critical paths: 95%+ coverage

### Best Practices Implemented
1. **Test Isolation**: Each test is independent with proper setup/teardown
2. **Mocking**: External services are mocked for reliability
3. **Fixtures**: Reusable test data and utilities
4. **Parallel Execution**: Tests can run concurrently for speed
5. **Comprehensive Assertions**: Detailed failure messages
6. **Performance Tracking**: Slow tests are marked and monitored

## Usage Examples

```bash
# Run all tests with coverage
python run_tests.py

# Run only unit tests in parallel
python run_tests.py -m unit -n 4

# Run Hebrew-specific tests
python run_tests.py -k hebrew

# Generate HTML coverage report
python run_tests.py --html

# Debug a specific test
python run_tests.py tests/test_translate.py::TestHebrewRouting --pdb

# Run failed tests first
python run_tests.py --ff
```

## Integration with Development Workflow

1. **Pre-commit Testing**: Run unit tests before commits
2. **Pull Request Testing**: Full test suite on PRs
3. **Coverage Monitoring**: Track coverage trends
4. **Performance Monitoring**: Identify slow tests

## Benefits

1. **Confidence**: Comprehensive tests ensure code reliability
2. **Rapid Development**: Catch bugs early with fast tests
3. **Documentation**: Tests serve as usage examples
4. **Refactoring Safety**: Tests protect against regressions
5. **Quality Metrics**: Coverage reports show code health

## Next Steps

To use this testing framework:

1. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Run tests:
   ```bash
   python run_tests.py
   ```

3. View coverage:
   ```bash
   python run_tests.py --html
   open htmlcov/index.html
   ```

4. Add tests for new features following the patterns in existing test files

The testing framework is now ready to ensure the Scribe project maintains high code quality and reliability throughout its development lifecycle.