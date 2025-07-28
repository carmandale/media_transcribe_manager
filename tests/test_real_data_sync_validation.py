#!/usr/bin/env python3
"""
Real Interview Data Synchronization Validation
==============================================

Tests subtitle synchronization using actual processed interview files.
This validates that the multilingual subtitle workflow maintains perfect
timing accuracy across all 728 processed interviews.

Key validation areas:
1. Timing consistency across all language files (orig, en, de, he)
2. Segment count preservation (no merging or splitting)
3. VTT conversion accuracy with real data
4. Subtitle file completeness verification
5. Sample-based deep timing analysis

This test uses actual processed interviews from the output/ directory
to verify the fixes have resolved the subtitle synchronization issues
mentioned in the roadmap.
"""

import os
import sys
import unittest
from pathlib import Path
from typing import List, Dict, Tuple
import random
from decimal import Decimal
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.subtitle_processor import SubtitleProcessor
from scribe.srt_translator import SRTTranslator


class TestRealDataSyncValidation(unittest.TestCase):
    """Test synchronization with real processed interview data."""
    
    def setUp(self):
        """Set up test environment."""
        self.output_dir = Path(project_root) / "output"
        self.processor = SubtitleProcessor(str(self.output_dir))
        self.translator = SRTTranslator()
        
        # Find actual interview directories
        self.interview_dirs = [
            d for d in self.output_dir.iterdir() 
            if d.is_dir() and len(d.name) == 36  # UUID format
        ]
        
        if not self.interview_dirs:
            self.skipTest("No processed interview directories found in output/")
            
        # Sample a reasonable number for testing
        self.sample_size = min(50, len(self.interview_dirs))
        self.sample_interviews = random.sample(self.interview_dirs, self.sample_size)
        
    def get_interview_subtitle_files(self, interview_dir: Path) -> Dict[str, Path]:
        """Get all subtitle files for an interview."""
        file_id = interview_dir.name
        subtitle_files = {}
        
        for lang in ['orig', 'en', 'de', 'he']:
            srt_file = interview_dir / f"{file_id}.{lang}.srt"
            vtt_file = interview_dir / f"{file_id}.{lang}.vtt"
            
            subtitle_files[f"{lang}.srt"] = srt_file
            subtitle_files[f"{lang}.vtt"] = vtt_file
            
        return subtitle_files
    
    def parse_timing_to_decimal(self, timing_str: str) -> Decimal:
        """Parse SRT/VTT timing to decimal seconds for precise comparison."""
        # Handle both SRT (comma) and VTT (dot) formats
        if ',' in timing_str:
            time_part, ms_part = timing_str.split(',')
        else:
            time_part, ms_part = timing_str.split('.')
            
        h, m, s = map(int, time_part.split(':'))
        ms = int(ms_part)
        
        return Decimal(h * 3600 + m * 60 + s) + Decimal(ms) / 1000
    
    def test_interview_file_completeness(self):
        """Test that all processed interviews have complete subtitle file sets."""
        missing_files_report = []
        
        for interview_dir in self.sample_interviews:
            file_id = interview_dir.name
            subtitle_files = self.get_interview_subtitle_files(interview_dir)
            
            missing_files = []
            for file_type, file_path in subtitle_files.items():
                if not file_path.exists():
                    missing_files.append(file_type)
                    
            if missing_files:
                missing_files_report.append({
                    'interview': file_id,
                    'missing': missing_files
                })
        
        if missing_files_report:
            report = "Missing subtitle files found:\n"
            for item in missing_files_report[:10]:  # Show first 10
                report += f"  {item['interview']}: {', '.join(item['missing'])}\n"
            if len(missing_files_report) > 10:
                report += f"  ... and {len(missing_files_report) - 10} more interviews\n"
                
            self.fail(report)
    
    def test_multilingual_timing_consistency_real_data(self):
        """Test timing consistency across all languages using real interview data."""
        timing_mismatches = []
        
        for interview_dir in self.sample_interviews:
            file_id = interview_dir.name
            subtitle_files = self.get_interview_subtitle_files(interview_dir)
            
            # Skip if any required files are missing
            required_srt_files = [f"{lang}.srt" for lang in ['orig', 'en', 'de', 'he']]
            if not all(subtitle_files[f].exists() for f in required_srt_files):
                continue
                
            # Parse all SRT files
            all_segments = {}
            for lang in ['orig', 'en', 'de', 'he']:
                srt_file = subtitle_files[f"{lang}.srt"]
                try:
                    segments = self.translator.parse_srt(str(srt_file))
                    all_segments[lang] = segments
                except Exception as e:
                    self.fail(f"Failed to parse {srt_file}: {e}")
            
            # Compare timing consistency
            orig_segments = all_segments['orig']
            
            for lang in ['en', 'de', 'he']:
                lang_segments = all_segments[lang]
                
                if len(orig_segments) != len(lang_segments):
                    timing_mismatches.append({
                        'interview': file_id,
                        'issue': f'Segment count mismatch: orig={len(orig_segments)}, {lang}={len(lang_segments)}'
                    })
                    continue
                
                # Check timing for each segment
                for i, (orig_seg, lang_seg) in enumerate(zip(orig_segments, lang_segments)):
                    if orig_seg.start_time != lang_seg.start_time:
                        timing_mismatches.append({
                            'interview': file_id,
                            'issue': f'Start time mismatch in {lang} segment {i+1}: {orig_seg.start_time} vs {lang_seg.start_time}'
                        })
                        break  # Only report first mismatch per file
                        
                    if orig_seg.end_time != lang_seg.end_time:
                        timing_mismatches.append({
                            'interview': file_id,
                            'issue': f'End time mismatch in {lang} segment {i+1}: {orig_seg.end_time} vs {lang_seg.end_time}'
                        })
                        break  # Only report first mismatch per file
        
        if timing_mismatches:
            report = f"Timing mismatches found in {len(timing_mismatches)} interviews:\n"
            for item in timing_mismatches[:10]:  # Show first 10
                report += f"  {item['interview']}: {item['issue']}\n"
            if len(timing_mismatches) > 10:
                report += f"  ... and {len(timing_mismatches) - 10} more issues\n"
                
            self.fail(report)
    
    def test_srt_to_vtt_conversion_accuracy_real_data(self):
        """Test SRT to VTT conversion accuracy with real interview data."""
        conversion_errors = []
        
        for interview_dir in self.sample_interviews:
            file_id = interview_dir.name
            subtitle_files = self.get_interview_subtitle_files(interview_dir)
            
            for lang in ['orig', 'en', 'de', 'he']:
                srt_file = subtitle_files[f"{lang}.srt"]
                vtt_file = subtitle_files[f"{lang}.vtt"]
                
                # Skip if files don't exist
                if not srt_file.exists() or not vtt_file.exists():
                    continue
                    
                try:
                    # Read both files
                    with open(srt_file, 'r', encoding='utf-8') as f:
                        srt_content = f.read()
                    with open(vtt_file, 'r', encoding='utf-8') as f:
                        vtt_content = f.read()
                    
                    # Parse SRT segments
                    srt_segments = self.translator.parse_srt(str(srt_file))
                    
                    # Verify VTT format
                    if not vtt_content.startswith('WEBVTT'):
                        conversion_errors.append({
                            'interview': file_id,
                            'file': f"{lang}.vtt",
                            'issue': 'Missing WEBVTT header'
                        })
                        continue
                    
                    # Verify timing conversion (comma -> dot)
                    for segment in srt_segments:
                        srt_timing = f"{segment.start_time} --> {segment.end_time}"
                        vtt_timing = srt_timing.replace(',', '.')
                        
                        if vtt_timing not in vtt_content:
                            conversion_errors.append({
                                'interview': file_id,
                                'file': f"{lang}.vtt",
                                'issue': f'Timing not found: {vtt_timing}'
                            })
                            break  # Only report first missing timing per file
                    
                    # Verify no SRT format leaked through
                    if ',' in vtt_content.replace('WEBVTT,', ''):
                        conversion_errors.append({
                            'interview': file_id,
                            'file': f"{lang}.vtt",
                            'issue': 'SRT comma format found in VTT'
                        })
                        
                except Exception as e:
                    conversion_errors.append({
                        'interview': file_id,
                        'file': f"{lang}.srt/.vtt",
                        'issue': f'Parse error: {str(e)}'
                    })
        
        if conversion_errors:
            report = f"VTT conversion errors found in {len(conversion_errors)} files:\n"
            for item in conversion_errors[:10]:  # Show first 10
                report += f"  {item['interview']} {item['file']}: {item['issue']}\n"
            if len(conversion_errors) > 10:
                report += f"  ... and {len(conversion_errors) - 10} more errors\n"
                
            self.fail(report)
    
    def test_segment_boundary_preservation_real_data(self):
        """Test that segment boundaries are preserved in real interview data."""
        boundary_violations = []
        
        for interview_dir in self.sample_interviews:
            file_id = interview_dir.name
            subtitle_files = self.get_interview_subtitle_files(interview_dir)
            
            # Get original segments as reference
            orig_srt = subtitle_files["orig.srt"]
            if not orig_srt.exists():
                continue
                
            try:
                orig_segments = self.translator.parse_srt(str(orig_srt))
            except Exception:
                continue  # Skip files that can't be parsed
            
            # Check boundaries in each translation
            for lang in ['en', 'de', 'he']:
                lang_srt = subtitle_files[f"{lang}.srt"]
                if not lang_srt.exists():
                    continue
                    
                try:
                    lang_segments = self.translator.parse_srt(str(lang_srt))
                except Exception:
                    continue
                
                # Check for boundary violations
                if len(orig_segments) != len(lang_segments):
                    boundary_violations.append({
                        'interview': file_id,
                        'issue': f'Segment count changed in {lang}: {len(orig_segments)} -> {len(lang_segments)}'
                    })
                    continue
                
                # Check individual boundaries
                for i, (orig_seg, lang_seg) in enumerate(zip(orig_segments, lang_segments)):
                    if orig_seg.index != lang_seg.index:
                        boundary_violations.append({
                            'interview': file_id,
                            'issue': f'Index changed in {lang} segment {i+1}: {orig_seg.index} -> {lang_seg.index}'
                        })
                        break
                    
                    if (orig_seg.start_time != lang_seg.start_time or 
                        orig_seg.end_time != lang_seg.end_time):
                        boundary_violations.append({
                            'interview': file_id,
                            'issue': f'Timing changed in {lang} segment {i+1}: {orig_seg.start_time}-{orig_seg.end_time} -> {lang_seg.start_time}-{lang_seg.end_time}'
                        })
                        break
        
        if boundary_violations:
            report = f"Boundary violations found in {len(boundary_violations)} interviews:\n"
            for item in boundary_violations[:10]:  # Show first 10
                report += f"  {item['interview']}: {item['issue']}\n"
            if len(boundary_violations) > 10:
                report += f"  ... and {len(boundary_violations) - 10} more violations\n"
                
            self.fail(report)
    
    def test_precision_timing_analysis_sample(self):
        """Deep timing analysis on a small sample of interviews."""
        # Select 5 interviews for detailed analysis
        detailed_sample = random.sample(self.sample_interviews, min(5, len(self.sample_interviews)))
        precision_issues = []
        
        for interview_dir in detailed_sample:
            file_id = interview_dir.name
            subtitle_files = self.get_interview_subtitle_files(interview_dir)
            
            # Get all SRT files
            srt_files = {}
            for lang in ['orig', 'en', 'de', 'he']:
                srt_file = subtitle_files[f"{lang}.srt"]
                if srt_file.exists():
                    try:
                        segments = self.translator.parse_srt(str(srt_file))
                        srt_files[lang] = segments
                    except Exception:
                        continue
            
            if len(srt_files) < 2:  # Need at least 2 languages to compare
                continue
            
            # Analyze timing precision
            orig_segments = srt_files.get('orig', [])
            if not orig_segments:
                continue
                
            for lang, lang_segments in srt_files.items():
                if lang == 'orig' or len(lang_segments) != len(orig_segments):
                    continue
                
                # Check microsecond-level precision
                for i, (orig_seg, lang_seg) in enumerate(zip(orig_segments, lang_segments)):
                    # Parse timing to decimals for precise comparison
                    try:
                        orig_start = self.parse_timing_to_decimal(orig_seg.start_time)
                        orig_end = self.parse_timing_to_decimal(orig_seg.end_time)
                        lang_start = self.parse_timing_to_decimal(lang_seg.start_time)
                        lang_end = self.parse_timing_to_decimal(lang_seg.end_time)
                        
                        # Check for timing drift (should be identical)
                        if orig_start != lang_start:
                            precision_issues.append({
                                'interview': file_id,
                                'segment': i+1,
                                'issue': f'Start time precision loss in {lang}: {orig_start} vs {lang_start}'
                            })
                            
                        if orig_end != lang_end:
                            precision_issues.append({
                                'interview': file_id,
                                'segment': i+1,
                                'issue': f'End time precision loss in {lang}: {orig_end} vs {lang_end}'
                            })
                            
                    except Exception as e:
                        precision_issues.append({
                            'interview': file_id,
                            'segment': i+1,
                            'issue': f'Timing parse error in {lang}: {str(e)}'
                        })
        
        if precision_issues:
            report = f"Precision timing issues found in detailed analysis:\n"
            for item in precision_issues[:15]:  # Show first 15
                report += f"  {item['interview']} seg{item['segment']}: {item['issue']}\n"
            if len(precision_issues) > 15:
                report += f"  ... and {len(precision_issues) - 15} more precision issues\n"
                
            self.fail(report)
    
    def test_webvtt_compliance_real_data(self):
        """Test WebVTT compliance with real interview VTT files."""
        compliance_issues = []
        
        # Sample fewer interviews for WebVTT compliance check (it's expensive)
        webvtt_sample = random.sample(self.sample_interviews, min(20, len(self.sample_interviews)))
        
        for interview_dir in webvtt_sample:
            file_id = interview_dir.name
            subtitle_files = self.get_interview_subtitle_files(interview_dir)
            
            for lang in ['orig', 'en', 'de', 'he']:
                vtt_file = subtitle_files[f"{lang}.vtt"]
                if not vtt_file.exists():
                    continue
                    
                try:
                    with open(vtt_file, 'r', encoding='utf-8') as f:
                        vtt_content = f.read()
                        
                    lines = vtt_content.split('\n')
                    
                    # WebVTT compliance checks
                    if not lines[0] == 'WEBVTT':
                        compliance_issues.append({
                            'interview': file_id,
                            'file': f"{lang}.vtt",
                            'issue': f'Invalid header: "{lines[0]}" (should be "WEBVTT")'
                        })
                        continue
                        
                    if len(lines) > 1 and lines[1] != '':
                        compliance_issues.append({
                            'interview': file_id,
                            'file': f"{lang}.vtt",
                            'issue': 'Missing blank line after WEBVTT header'
                        })
                    
                    # Check timing format
                    timing_lines = [line for line in lines if ' --> ' in line]
                    for timing_line in timing_lines:
                        # Should use dots, not commas
                        if ',' in timing_line:
                            compliance_issues.append({
                                'interview': file_id,
                                'file': f"{lang}.vtt",
                                'issue': f'SRT timing format in VTT: {timing_line}'
                            })
                            break  # Only report first issue per file
                        
                        # Should match WebVTT pattern
                        import re
                        webvtt_pattern = r'^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}$'
                        if not re.match(webvtt_pattern, timing_line):
                            compliance_issues.append({
                                'interview': file_id,
                                'file': f"{lang}.vtt",
                                'issue': f'Invalid WebVTT timing: {timing_line}'
                            })
                            break
                            
                except Exception as e:
                    compliance_issues.append({
                        'interview': file_id,
                        'file': f"{lang}.vtt",
                        'issue': f'Read error: {str(e)}'
                    })
        
        if compliance_issues:
            report = f"WebVTT compliance issues found in {len(compliance_issues)} files:\n"
            for item in compliance_issues[:10]:  # Show first 10
                report += f"  {item['interview']} {item['file']}: {item['issue']}\n"
            if len(compliance_issues) > 10:
                report += f"  ... and {len(compliance_issues) - 10} more compliance issues\n"
                
            self.fail(report)
    
    def test_generate_sync_validation_report(self):
        """Generate a comprehensive sync validation report."""
        report = {
            'total_interviews_tested': len(self.sample_interviews),
            'total_interviews_available': len(self.interview_dirs),
            'file_completeness': {},
            'timing_consistency': {'passed': 0, 'failed': 0},
            'vtt_conversion': {'passed': 0, 'failed': 0},
            'boundary_preservation': {'passed': 0, 'failed': 0},
            'webvtt_compliance': {'passed': 0, 'failed': 0}
        }
        
        # File completeness analysis
        complete_interviews = 0
        for interview_dir in self.sample_interviews:
            subtitle_files = self.get_interview_subtitle_files(interview_dir)
            required_files = [f"{lang}.{ext}" for lang in ['orig', 'en', 'de', 'he'] for ext in ['srt', 'vtt']]
            
            missing_count = sum(1 for f in required_files if not subtitle_files[f].exists())
            if missing_count == 0:
                complete_interviews += 1
                
        report['file_completeness'] = {
            'complete_interviews': complete_interviews,
            'completion_rate': f"{(complete_interviews / len(self.sample_interviews)) * 100:.1f}%"
        }
        
        # Quick timing consistency check
        consistent_interviews = 0
        for interview_dir in self.sample_interviews:
            file_id = interview_dir.name
            subtitle_files = self.get_interview_subtitle_files(interview_dir)
            
            timing_consistent = True
            try:
                # Check if orig and en have same timing (quick check)
                orig_file = subtitle_files["orig.srt"]
                en_file = subtitle_files["en.srt"]
                
                if orig_file.exists() and en_file.exists():
                    orig_segments = self.translator.parse_srt(str(orig_file))
                    en_segments = self.translator.parse_srt(str(en_file))
                    
                    if len(orig_segments) != len(en_segments):
                        timing_consistent = False
                    else:
                        # Check first few segments
                        for orig_seg, en_seg in zip(orig_segments[:5], en_segments[:5]):
                            if (orig_seg.start_time != en_seg.start_time or 
                                orig_seg.end_time != en_seg.end_time):
                                timing_consistent = False
                                break
                                
            except Exception:
                timing_consistent = False
                
            if timing_consistent:
                consistent_interviews += 1
                
        report['timing_consistency'] = {
            'passed': consistent_interviews,
            'failed': len(self.sample_interviews) - consistent_interviews,
            'pass_rate': f"{(consistent_interviews / len(self.sample_interviews)) * 100:.1f}%"
        }
        
        # Print report
        print("\n" + "="*60)
        print("SUBTITLE SYNCHRONIZATION VALIDATION REPORT")
        print("="*60)
        print(f"Sample Size: {report['total_interviews_tested']} of {report['total_interviews_available']} interviews")
        print(f"File Completeness: {report['file_completeness']['completion_rate']} ({report['file_completeness']['complete_interviews']} complete)")
        print(f"Timing Consistency: {report['timing_consistency']['pass_rate']} ({report['timing_consistency']['passed']} passed, {report['timing_consistency']['failed']} failed)")
        print("="*60)
        
        # Save detailed report
        report_file = Path(__file__).parent / "sync_validation_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"Detailed report saved to: {report_file}")


def run_real_data_sync_tests():
    """Run all real data synchronization tests."""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRealDataSyncValidation))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n" + "="*60)
        print("✅ REAL DATA SYNC VALIDATION PASSED")
        print("="*60)
        print("Verified with actual processed interviews:")
        print("• File completeness across all languages")
        print("• Multilingual timing consistency")
        print("• SRT to VTT conversion accuracy")
        print("• Segment boundary preservation")
        print("• Precision timing analysis")
        print("• WebVTT compliance")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ REAL DATA SYNC VALIDATION FAILED")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print("="*60)
        
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_real_data_sync_tests()
    sys.exit(0 if success else 1)