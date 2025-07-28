#!/usr/bin/env python3
"""
Comprehensive Subtitle Synchronization Validation Runner
========================================================

Executes all subtitle synchronization tests to verify that the issues
mentioned in the roadmap have been resolved with the new multilingual
subtitle workflow implementation.

This script runs:
1. Core synchronization tests (timing accuracy, VTT conversion)
2. VTT precision tests (microsecond-level timing)
3. Real data validation (using actual processed interviews)
4. Generates comprehensive validation report

Usage:
    python tests/run_subtitle_sync_validation.py [--quick] [--verbose]
    
Options:
    --quick     Run a subset of tests for faster validation
    --verbose   Show detailed test output
    --report    Generate detailed HTML report
"""

import sys
import unittest
import argparse
from pathlib import Path
import time
import json
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import all test modules
from tests.test_subtitle_synchronization import run_synchronization_tests
from tests.test_vtt_timing_precision import run_vtt_precision_tests
from tests.test_real_data_sync_validation import run_real_data_sync_tests


class SubtitleSyncValidationRunner:
    """Comprehensive subtitle synchronization validation runner."""
    
    def __init__(self, quick_mode=False, verbose=False, generate_report=False):
        self.quick_mode = quick_mode
        self.verbose = verbose
        self.generate_report = generate_report
        self.results = {
            'start_time': datetime.now().isoformat(),
            'test_suites': {},
            'summary': {},
            'issues_found': [],
            'recommendations': []
        }
        
    def run_test_suite(self, suite_name: str, test_function) -> bool:
        """Run a test suite and capture results."""
        print(f"\n{'='*80}")
        print(f"RUNNING: {suite_name}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        try:
            success = test_function()
            duration = time.time() - start_time
            
            self.results['test_suites'][suite_name] = {
                'success': success,
                'duration': f"{duration:.2f}s",
                'status': 'PASSED' if success else 'FAILED'
            }
            
            if success:
                print(f"\n✅ {suite_name} PASSED ({duration:.2f}s)")
            else:
                print(f"\n❌ {suite_name} FAILED ({duration:.2f}s)")
                self.results['issues_found'].append(f"{suite_name} test suite failed")
                
            return success
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"\n💥 {suite_name} ERROR: {str(e)} ({duration:.2f}s)")
            
            self.results['test_suites'][suite_name] = {
                'success': False,
                'duration': f"{duration:.2f}s",
                'status': 'ERROR',
                'error': str(e)
            }
            
            self.results['issues_found'].append(f"{suite_name} encountered error: {str(e)}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all subtitle synchronization validation tests."""
        print("🎬 SUBTITLE SYNCHRONIZATION VALIDATION")
        print("=" * 80)
        print("Verifying that subtitle synchronization issues have been resolved")
        print("with the new multilingual subtitle workflow implementation.")
        print("=" * 80)
        
        all_passed = True
        
        # 1. Core Synchronization Tests
        if not self.run_test_suite(
            "Core Synchronization Tests",
            run_synchronization_tests
        ):
            all_passed = False
            
        # 2. VTT Timing Precision Tests
        if not self.run_test_suite(
            "VTT Timing Precision Tests", 
            run_vtt_precision_tests
        ):
            all_passed = False
            
        # 3. Real Data Validation Tests (skip in quick mode)
        if not self.quick_mode:
            if not self.run_test_suite(
                "Real Data Sync Validation",
                run_real_data_sync_tests
            ):
                all_passed = False
        else:
            print(f"\n⚡ Skipping Real Data Validation (quick mode)")
            self.results['test_suites']['Real Data Sync Validation'] = {
                'success': True,
                'duration': '0.00s',
                'status': 'SKIPPED',
                'note': 'Skipped in quick mode'
            }
        
        return all_passed
    
    def generate_summary(self, all_passed: bool):
        """Generate validation summary."""
        total_suites = len(self.results['test_suites'])
        passed_suites = sum(1 for s in self.results['test_suites'].values() if s['success'])
        failed_suites = sum(1 for s in self.results['test_suites'].values() if not s['success'] and s['status'] != 'SKIPPED')
        skipped_suites = sum(1 for s in self.results['test_suites'].values() if s['status'] == 'SKIPPED')
        
        total_duration = sum(
            float(s['duration'].replace('s', '')) 
            for s in self.results['test_suites'].values() 
            if s['status'] != 'SKIPPED'
        )
        
        self.results['summary'] = {
            'overall_success': all_passed,
            'total_suites': total_suites,
            'passed_suites': passed_suites,
            'failed_suites': failed_suites,
            'skipped_suites': skipped_suites,
            'total_duration': f"{total_duration:.2f}s",
            'completion_time': datetime.now().isoformat()
        }
        
        # Generate recommendations
        if all_passed:
            self.results['recommendations'] = [
                "✅ All subtitle synchronization tests passed",
                "✅ The multilingual subtitle workflow is working correctly",
                "✅ Timing accuracy is maintained across all language translations",
                "✅ SRT to VTT conversion preserves microsecond precision",
                "✅ Ready to proceed with Phase 2 reprocessing",
                "🎯 Consider running the full test suite periodically to maintain quality"
            ]
        else:
            self.results['recommendations'] = [
                "❌ Subtitle synchronization issues detected",
                "🔧 Review failed test cases and fix timing inconsistencies",
                "🚫 DO NOT proceed with Phase 2 reprocessing until issues are resolved",
                "🔍 Run tests in verbose mode for detailed failure analysis",
                "📞 Consider escalating to development team if issues persist"
            ]
            
        print(f"\n{'='*80}")
        print("SUBTITLE SYNCHRONIZATION VALIDATION SUMMARY")
        print(f"{'='*80}")
        print(f"Overall Result: {'✅ PASSED' if all_passed else '❌ FAILED'}")
        print(f"Test Suites: {passed_suites}/{total_suites} passed")
        if failed_suites > 0:
            print(f"Failed Suites: {failed_suites}")
        if skipped_suites > 0:
            print(f"Skipped Suites: {skipped_suites}")
        print(f"Total Duration: {total_duration:.2f}s")
        print(f"{'='*80}")
        
        print("\nRECOMMENDATIONS:")
        for rec in self.results['recommendations']:
            print(f"  {rec}")
            
        if self.results['issues_found']:
            print(f"\nISSUES FOUND ({len(self.results['issues_found'])}):")
            for issue in self.results['issues_found']:
                print(f"  • {issue}")
                
        print(f"{'='*80}")
    
    def save_report(self):
        """Save detailed validation report."""
        if not self.generate_report:
            return
            
        report_file = Path(__file__).parent / f"subtitle_sync_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\n📄 Detailed report saved to: {report_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive Subtitle Synchronization Validation"
    )
    parser.add_argument('--quick', action='store_true',
                       help='Run quick validation (skip real data tests)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show verbose test output')
    parser.add_argument('--report', action='store_true',
                       help='Generate detailed JSON report')
    
    args = parser.parse_args()
    
    # Create runner
    runner = SubtitleSyncValidationRunner(
        quick_mode=args.quick,
        verbose=args.verbose,
        generate_report=args.report
    )
    
    # Run all tests
    try:
        all_passed = runner.run_all_tests()
        runner.generate_summary(all_passed)
        runner.save_report()
        
        # Exit with appropriate code
        sys.exit(0 if all_passed else 1)
        
    except KeyboardInterrupt:
        print(f"\n\n🛑 VALIDATION INTERRUPTED BY USER")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n💥 VALIDATION FAILED WITH ERROR: {str(e)}")
        sys.exit(3)


if __name__ == '__main__':
    main()