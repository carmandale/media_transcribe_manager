#!/usr/bin/env python3
"""
Focused Subtitle Synchronization Validation
===========================================

Direct validation of subtitle synchronization using the existing processed
interview files to verify timing accuracy and consistency.

This test focuses on the core question: "Are subtitle synchronization issues
resolved in the new multilingual subtitle workflow?"

Test Strategy:
1. Use existing files to avoid mocking complexity
2. Test actual SRT and VTT files for timing consistency
3. Validate the SubtitleProcessor convert_srt_to_vtt function directly
4. Check real interview data for synchronization
"""

import os
import sys
import unittest
from pathlib import Path
import random

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.subtitle_processor import SubtitleProcessor
from scribe.srt_translator import SRTTranslator


class TestFocusedSyncValidation(unittest.TestCase):
    """Focused tests for subtitle synchronization validation."""
    
    def setUp(self):
        """Set up test environment."""
        self.output_dir = Path(project_root) / "output"
        self.processor = SubtitleProcessor(str(self.output_dir))
        self.translator = SRTTranslator()
        
        # Find processed interviews with complete file sets
        self.complete_interviews = []
        if self.output_dir.exists():
            for interview_dir in self.output_dir.iterdir():
                if interview_dir.is_dir() and len(interview_dir.name) == 36:
                    file_id = interview_dir.name
                    
                    # Check if has all required files
                    required_files = [
                        f"{file_id}.orig.srt",
                        f"{file_id}.en.srt", 
                        f"{file_id}.de.srt",
                        f"{file_id}.he.srt"
                    ]
                    
                    if all((interview_dir / f).exists() for f in required_files):
                        self.complete_interviews.append(interview_dir)
        
        # Use a sample for testing
        self.test_sample = random.sample(
            self.complete_interviews, 
            min(10, len(self.complete_interviews))
        )
    
    def test_srt_to_vtt_conversion_direct(self):
        """Test the SRT to VTT conversion function directly."""
        if not self.complete_interviews:
            self.skipTest("No complete interview files found")
            
        # Test with one complete interview
        interview_dir = self.complete_interviews[0]
        file_id = interview_dir.name
        orig_srt = interview_dir / f"{file_id}.orig.srt"
        
        # Test conversion
        success = self.processor.convert_srt_to_vtt(orig_srt)
        self.assertTrue(success, "SRT to VTT conversion failed")
        
        # Check that VTT file was created
        vtt_file = orig_srt.with_suffix('.vtt')
        self.assertTrue(vtt_file.exists(), "VTT file not created")
        
        # Read both files
        with open(orig_srt, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
            
        # Basic format checks
        self.assertTrue(vtt_content.startswith('WEBVTT'), "VTT missing header")
        
        # Check timing conversion (comma to dot)
        srt_lines = srt_content.split('\n')
        vtt_lines = vtt_content.split('\n')
        
        srt_timing_lines = [line for line in srt_lines if ' --> ' in line and ',' in line]
        vtt_timing_lines = [line for line in vtt_lines if ' --> ' in line and '.' in line]
        
        self.assertEqual(len(srt_timing_lines), len(vtt_timing_lines), 
                        "Different number of timing lines after conversion")
        
        # Check that at least one timing was converted correctly
        if srt_timing_lines:
            srt_timing = srt_timing_lines[0]
            expected_vtt_timing = srt_timing.replace(',', '.')
            self.assertIn(expected_vtt_timing, vtt_content, 
                         "Timing conversion not found in VTT")
    
    def test_existing_file_timing_consistency(self):
        """Test timing consistency in existing processed files."""
        if not self.test_sample:
            self.skipTest("No complete interview files found")
            
        timing_issues = []
        
        for interview_dir in self.test_sample:
            file_id = interview_dir.name
            
            # Parse all SRT files
            srt_files = {}
            for lang in ['orig', 'en', 'de', 'he']:
                srt_file = interview_dir / f"{file_id}.{lang}.srt"
                if srt_file.exists():
                    try:
                        segments = self.translator.parse_srt(str(srt_file))
                        srt_files[lang] = segments
                    except Exception as e:
                        timing_issues.append(f"{file_id}: Failed to parse {lang}.srt - {str(e)}")
                        continue
            
            # Check timing consistency between orig and translations
            if 'orig' not in srt_files:
                timing_issues.append(f"{file_id}: Missing orig.srt")
                continue
                
            orig_segments = srt_files['orig']
            
            for lang in ['en', 'de', 'he']:
                if lang not in srt_files:
                    timing_issues.append(f"{file_id}: Missing {lang}.srt")
                    continue
                    
                lang_segments = srt_files[lang]
                
                # Check segment count
                if len(orig_segments) != len(lang_segments):
                    timing_issues.append(f"{file_id}: Segment count mismatch in {lang} - orig:{len(orig_segments)} vs {lang}:{len(lang_segments)}")
                    continue
                
                # Check timing for first few segments (quick validation)
                check_count = min(5, len(orig_segments))
                for i in range(check_count):
                    orig_seg = orig_segments[i]
                    lang_seg = lang_segments[i]
                    
                    if orig_seg.start_time != lang_seg.start_time:
                        timing_issues.append(f"{file_id}: Start time mismatch in {lang} segment {i+1}")
                        break
                        
                    if orig_seg.end_time != lang_seg.end_time:
                        timing_issues.append(f"{file_id}: End time mismatch in {lang} segment {i+1}")
                        break
        
        # Report any timing issues found
        if timing_issues:
            issue_summary = f"Found {len(timing_issues)} timing issues in {len(self.test_sample)} interviews:\n"
            for issue in timing_issues[:10]:  # Show first 10
                issue_summary += f"  • {issue}\n"
            if len(timing_issues) > 10:
                issue_summary += f"  ... and {len(timing_issues) - 10} more issues\n"
            self.fail(issue_summary)
    
    def test_vtt_files_exist_and_valid(self):
        """Test that VTT files exist and have valid format."""
        if not self.test_sample:
            self.skipTest("No complete interview files found")
            
        vtt_issues = []
        
        for interview_dir in self.test_sample:
            file_id = interview_dir.name
            
            for lang in ['orig', 'en', 'de', 'he']:
                vtt_file = interview_dir / f"{file_id}.{lang}.vtt"
                
                if not vtt_file.exists():
                    vtt_issues.append(f"{file_id}: Missing {lang}.vtt")
                    continue
                
                try:
                    with open(vtt_file, 'r', encoding='utf-8') as f:
                        vtt_content = f.read()
                    
                    # Basic VTT format validation
                    if not vtt_content.startswith('WEBVTT'):
                        vtt_issues.append(f"{file_id}: Invalid VTT header in {lang}.vtt")
                        continue
                    
                    # Check for timing lines with proper format
                    lines = vtt_content.split('\n')
                    timing_lines = [line for line in lines if ' --> ' in line]
                    
                    if not timing_lines:
                        vtt_issues.append(f"{file_id}: No timing lines found in {lang}.vtt")
                        continue
                    
                    # Check first timing line format
                    timing_line = timing_lines[0]
                    if ',' in timing_line:  # Should use dots, not commas
                        vtt_issues.append(f"{file_id}: SRT format found in {lang}.vtt: {timing_line}")
                        
                except Exception as e:
                    vtt_issues.append(f"{file_id}: Error reading {lang}.vtt - {str(e)}")
        
        if vtt_issues:
            issue_summary = f"Found {len(vtt_issues)} VTT issues in {len(self.test_sample)} interviews:\n"
            for issue in vtt_issues[:10]:  # Show first 10
                issue_summary += f"  • {issue}\n"
            if len(vtt_issues) > 10:
                issue_summary += f"  ... and {len(vtt_issues) - 10} more issues\n"
            self.fail(issue_summary)
    
    def test_subtitle_processor_validation_function(self):
        """Test the SubtitleProcessor validation function."""
        if not self.complete_interviews:
            self.skipTest("No complete interview files found")
            
        # Test validation on a few interviews
        validation_issues = []
        
        for interview_dir in self.complete_interviews[:5]:  # Test first 5
            file_id = interview_dir.name
            
            # Use the processor's validation function
            validation = self.processor.validate_subtitle_files(file_id)
            
            # Check for any missing files
            missing_files = [file_type for file_type, exists in validation.items() if not exists]
            
            if missing_files:
                validation_issues.append(f"{file_id}: Missing files - {', '.join(missing_files)}")
        
        if validation_issues:
            issue_summary = f"Validation issues found:\n"
            for issue in validation_issues:
                issue_summary += f"  • {issue}\n"
            self.fail(issue_summary)
    
    def test_sample_deep_timing_analysis(self):
        """Deep timing analysis on a small sample."""
        if not self.complete_interviews:
            self.skipTest("No complete interview files found")
            
        # Select one interview for deep analysis
        interview_dir = self.complete_interviews[0]
        file_id = interview_dir.name
        
        print(f"\nDeep timing analysis for interview: {file_id}")
        
        # Parse all language files
        all_segments = {}
        for lang in ['orig', 'en', 'de', 'he']:
            srt_file = interview_dir / f"{file_id}.{lang}.srt"
            if srt_file.exists():
                segments = self.translator.parse_srt(str(srt_file))
                all_segments[lang] = segments
                print(f"  {lang}.srt: {len(segments)} segments")
        
        # Detailed timing comparison
        if 'orig' in all_segments:
            orig_segments = all_segments['orig']
            
            for lang in ['en', 'de', 'he']:
                if lang in all_segments:
                    lang_segments = all_segments[lang]
                    
                    if len(orig_segments) == len(lang_segments):
                        # Check all segments for timing consistency
                        mismatch_count = 0
                        for i, (orig_seg, lang_seg) in enumerate(zip(orig_segments, lang_segments)):
                            if (orig_seg.start_time != lang_seg.start_time or 
                                orig_seg.end_time != lang_seg.end_time):
                                mismatch_count += 1
                        
                        print(f"  {lang} timing mismatches: {mismatch_count}/{len(orig_segments)}")
                        
                        if mismatch_count > 0:
                            self.fail(f"Found {mismatch_count} timing mismatches in {lang} translation")
                    else:
                        self.fail(f"Segment count mismatch: orig={len(orig_segments)} vs {lang}={len(lang_segments)}")
    
    def test_generate_sync_status_report(self):
        """Generate a status report on subtitle synchronization."""
        total_interviews = len(self.complete_interviews)
        
        if total_interviews == 0:
            self.skipTest("No processed interviews found for analysis")
        
        print(f"\n" + "="*60)
        print("SUBTITLE SYNCHRONIZATION STATUS REPORT")
        print("="*60)
        print(f"Total processed interviews analyzed: {total_interviews}")
        
        # Sample analysis
        sample_size = min(20, total_interviews)
        sample_interviews = random.sample(self.complete_interviews, sample_size)
        
        issues_found = []
        perfect_sync_count = 0
        
        for interview_dir in sample_interviews:
            file_id = interview_dir.name
            interview_issues = []
            
            # Check file completeness
            validation = self.processor.validate_subtitle_files(file_id)
            missing_files = [f for f, exists in validation.items() if not exists]
            
            if missing_files:
                interview_issues.append(f"Missing files: {', '.join(missing_files[:3])}")
            
            # Quick timing check (orig vs en)
            orig_file = interview_dir / f"{file_id}.orig.srt"
            en_file = interview_dir / f"{file_id}.en.srt"
            
            if orig_file.exists() and en_file.exists():
                try:
                    orig_segments = self.translator.parse_srt(str(orig_file))
                    en_segments = self.translator.parse_srt(str(en_file))
                    
                    if len(orig_segments) != len(en_segments):
                        interview_issues.append("Segment count mismatch")
                    else:
                        # Check first 3 segments for timing
                        timing_ok = True
                        for i in range(min(3, len(orig_segments))):
                            if (orig_segments[i].start_time != en_segments[i].start_time or
                                orig_segments[i].end_time != en_segments[i].end_time):
                                timing_ok = False
                                break
                        
                        if not timing_ok:
                            interview_issues.append("Timing inconsistency detected")
                            
                except Exception:
                    interview_issues.append("Parse error")
            
            if interview_issues:
                issues_found.append(f"{file_id}: {'; '.join(interview_issues)}")
            else:
                perfect_sync_count += 1
        
        sync_rate = (perfect_sync_count / sample_size) * 100
        
        print(f"Sample size: {sample_size} interviews")
        print(f"Perfect synchronization: {perfect_sync_count}/{sample_size} ({sync_rate:.1f}%)")
        
        if issues_found:
            print(f"Issues found: {len(issues_found)}")
            print("\nSample issues:")
            for issue in issues_found[:5]:
                print(f"  • {issue}")
            if len(issues_found) > 5:
                print(f"  ... and {len(issues_found) - 5} more")
        else:
            print("✅ No synchronization issues detected in sample")
        
        print("="*60)
        
        # Assert based on results
        if sync_rate < 80:  # Less than 80% perfect sync is concerning
            self.fail(f"Low synchronization rate: {sync_rate:.1f}% - indicates subtitle sync issues")


def run_focused_validation():
    """Run focused subtitle synchronization validation."""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFocusedSyncValidation))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n" + "="*60)
        print("✅ FOCUSED SUBTITLE SYNC VALIDATION PASSED")
        print("="*60)
        print("Key findings:")
        print("• SRT to VTT conversion working correctly")
        print("• Existing files show timing consistency")
        print("• VTT files have proper format")
        print("• SubtitleProcessor validation functions work")
        print("• Deep timing analysis shows accuracy")
        print("• Overall synchronization status is good")
        print("="*60)
    else:
        print("\n" + "="*60)  
        print("❌ FOCUSED SUBTITLE SYNC VALIDATION FAILED")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print("="*60)
        
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_focused_validation()
    sys.exit(0 if success else 1)