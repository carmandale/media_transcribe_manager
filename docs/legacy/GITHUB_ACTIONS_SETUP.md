# GitHub Actions Setup for Scribe Testing

Since GitHub Apps don't have workflow permissions, you'll need to manually create the GitHub Actions workflow file.

## Setup Instructions

1. Create the workflow directory:
   ```bash
   mkdir -p .github/workflows
   ```

2. Create `.github/workflows/tests.yml` with the following content:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop, terragon/* ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

env:
  PYTHON_VERSION: "3.10"

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.8", "3.9", "3.10", "3.11"]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Cache pip packages
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
        restore-keys: |
          ${{ runner.os }}-pip-
    
    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y ffmpeg
    
    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio pytest-xdist pytest-timeout
    
    - name: Create test environment
      run: |
        cp .env.example .env.test 2>/dev/null || true
        echo "SCRIBE_TEST_MODE=1" >> .env.test
        echo "DATABASE_PATH=test_media_tracking.db" >> .env.test
    
    - name: Run unit tests
      env:
        PYTEST_TIMEOUT: 300
      run: |
        python -m pytest tests/ -m "unit and not slow" -v --cov=scribe --cov-report=xml --cov-report=term-missing
    
    - name: Run integration tests
      if: matrix.python-version == '3.10'
      env:
        PYTEST_TIMEOUT: 600
      run: |
        python -m pytest tests/ -m "integration" -v
    
    - name: Upload coverage to Codecov
      if: matrix.python-version == '3.10'
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-scribe
        fail_ci_if_error: false

  test-hebrew:
    runs-on: ubuntu-latest
    name: Hebrew Language Tests
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run Hebrew-specific tests
      run: |
        python -m pytest tests/ -m "hebrew" -v --cov=scribe --cov-report=term-missing
    
    - name: Check Hebrew routing logic
      run: |
        python test_hebrew_fix.py

  lint:
    runs-on: ubuntu-latest
    name: Code Quality Checks
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install flake8 black isort mypy
    
    - name: Run flake8
      run: |
        flake8 scribe/ tests/ --max-line-length=120 --ignore=E203,W503
      continue-on-error: true
    
    - name: Check black formatting
      run: |
        black --check scribe/ tests/
      continue-on-error: true
    
    - name: Check import sorting
      run: |
        isort --check-only scribe/ tests/
      continue-on-error: true
    
    - name: Run mypy type checking
      run: |
        mypy scribe/ --ignore-missing-imports
      continue-on-error: true

  security:
    runs-on: ubuntu-latest
    name: Security Checks
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install safety bandit
    
    - name: Run safety check
      run: |
        pip install -r requirements.txt
        safety check --json
      continue-on-error: true
    
    - name: Run bandit security check
      run: |
        bandit -r scribe/ -f json -o bandit-report.json
      continue-on-error: true

  test-summary:
    runs-on: ubuntu-latest
    needs: [test, test-hebrew, lint, security]
    if: always()
    name: Test Summary
    
    steps:
    - name: Summary
      run: |
        echo "## Test Summary" >> $GITHUB_STEP_SUMMARY
        echo "" >> $GITHUB_STEP_SUMMARY
        echo "| Job | Status |" >> $GITHUB_STEP_SUMMARY
        echo "|-----|--------|" >> $GITHUB_STEP_SUMMARY
        echo "| Unit Tests | ${{ needs.test.result }} |" >> $GITHUB_STEP_SUMMARY
        echo "| Hebrew Tests | ${{ needs.test-hebrew.result }} |" >> $GITHUB_STEP_SUMMARY
        echo "| Linting | ${{ needs.lint.result }} |" >> $GITHUB_STEP_SUMMARY
        echo "| Security | ${{ needs.security.result }} |" >> $GITHUB_STEP_SUMMARY
```

3. Commit and push the workflow file:
   ```bash
   git add .github/workflows/tests.yml
   git commit -m "Add GitHub Actions workflow for testing"
   git push
   ```

## Features

The workflow includes:

- **Multi-Python Testing**: Tests on Python 3.8, 3.9, 3.10, and 3.11
- **Hebrew Language Tests**: Separate job for Hebrew-specific functionality
- **Code Quality**: Linting with flake8, black, isort, and mypy
- **Security Scanning**: Safety and bandit checks
- **Coverage Reporting**: Upload to Codecov
- **Test Summary**: Consolidated status report

## Optional: Pre-commit Hooks

For local development, you can also set up pre-commit hooks:

1. Install pre-commit:
   ```bash
   pip install pre-commit
   ```

2. Create `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: local
       hooks:
         - id: tests
           name: Run unit tests
           entry: python run_tests.py -m "unit and not slow"
           language: system
           pass_filenames: false
           always_run: true
         - id: black
           name: black
           entry: black
           language: system
           types: [python]
         - id: flake8
           name: flake8
           entry: flake8
           language: system
           types: [python]
   ```

3. Install the hooks:
   ```bash
   pre-commit install
   ```

This will run tests and code quality checks before each commit.