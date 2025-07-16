#!/usr/bin/env python3
"""
Test runner script for the Scribe project.

This script provides a convenient interface for running tests with various options
including coverage reporting, specific test selection, and parallel execution.
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, check=True):
    """Run a command and optionally check for errors."""
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd, check=check)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Run tests for the Scribe project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests with coverage
  python run_tests.py
  
  # Run only unit tests
  python run_tests.py -m unit
  
  # Run tests for a specific module
  python run_tests.py tests/test_database.py
  
  # Run tests matching a pattern
  python run_tests.py -k "test_hebrew"
  
  # Run tests in parallel
  python run_tests.py -n 4
  
  # Generate HTML coverage report
  python run_tests.py --html
  
  # Run without coverage
  python run_tests.py --no-cov
        """
    )
    
    parser.add_argument(
        'tests',
        nargs='*',
        default=['tests'],
        help='Specific test files or directories to run (default: all tests)'
    )
    
    parser.add_argument(
        '-k',
        '--keyword',
        help='Only run tests matching the given keyword expression'
    )
    
    parser.add_argument(
        '-m',
        '--marker',
        help='Only run tests marked with the given marker (e.g., unit, integration, hebrew)'
    )
    
    parser.add_argument(
        '-n',
        '--numprocesses',
        type=int,
        help='Number of parallel processes for test execution'
    )
    
    parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=1,
        help='Increase verbosity (can be used multiple times)'
    )
    
    parser.add_argument(
        '--no-cov',
        action='store_true',
        help='Disable coverage reporting'
    )
    
    parser.add_argument(
        '--cov-fail-under',
        type=int,
        default=80,
        help='Fail if coverage is below this percentage (default: 80)'
    )
    
    parser.add_argument(
        '--html',
        action='store_true',
        help='Generate HTML coverage report'
    )
    
    parser.add_argument(
        '--pdb',
        action='store_true',
        help='Drop into debugger on failures'
    )
    
    parser.add_argument(
        '--lf',
        '--last-failed',
        action='store_true',
        help='Run only tests that failed in the last run'
    )
    
    parser.add_argument(
        '--ff',
        '--failed-first',
        action='store_true',
        help='Run failed tests first, then the rest'
    )
    
    parser.add_argument(
        '--markers',
        action='store_true',
        help='Show available test markers and exit'
    )
    
    parser.add_argument(
        '--setup-only',
        action='store_true',
        help='Only setup fixtures, do not run tests'
    )
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = [sys.executable, '-m', 'pytest']
    
    # Add verbosity
    if args.verbose > 1:
        cmd.append('-' + 'v' * args.verbose)
    
    # Add coverage options
    if not args.no_cov:
        cmd.extend([
            '--cov=scribe',
            '--cov-report=term-missing',
            f'--cov-fail-under={args.cov_fail_under}'
        ])
        
        if args.html:
            cmd.append('--cov-report=html')
    
    # Add test selection options
    if args.keyword:
        cmd.extend(['-k', args.keyword])
    
    if args.marker:
        cmd.extend(['-m', args.marker])
    
    # Add parallel execution
    if args.numprocesses:
        cmd.extend(['-n', str(args.numprocesses)])
    
    # Add debugging options
    if args.pdb:
        cmd.append('--pdb')
    
    # Add failure handling options
    if args.lf:
        cmd.append('--lf')
    elif args.ff:
        cmd.append('--ff')
    
    # Add other options
    if args.markers:
        cmd.append('--markers')
        run_command(cmd)
        return 0
    
    if args.setup_only:
        cmd.append('--setup-only')
    
    # Add test paths
    cmd.extend(args.tests)
    
    # Run tests
    success = run_command(cmd, check=False)
    
    # Generate coverage report
    if not args.no_cov and success:
        print("\n" + "="*60)
        print("COVERAGE SUMMARY")
        print("="*60)
        
        if args.html:
            print("\nHTML coverage report generated in htmlcov/index.html")
            print("Open with: python -m http.server 8000 --directory htmlcov")
    
    # Show test summary
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()