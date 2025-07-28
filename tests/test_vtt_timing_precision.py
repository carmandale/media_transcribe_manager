#!/usr/bin/env python3
"""
VTT Timing Precision Tests
==========================

Specific tests for SRT to VTT conversion timing accuracy.
Validates that the new SubtitleProcessor correctly converts timing formats
while maintaining microsecond precision required for video synchronization.

Key test areas:
1. Millisecond precision preservation (SRT comma -> VTT dot conversion)
2. WebVTT header compliance
3. Edge case timing scenarios (00:00:00,000, overlaps, etc.)
4. Batch conversion consistency
5. Large file performance with timing accuracy
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from decimal import Decimal
import re

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scribe.subtitle_processor import SubtitleProcessor
from scribe.srt_translator import SRTTranslator


class TestVTTTimingPrecision(unittest.TestCase):
    """Test VTT conversion timing precision."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = SubtitleProcessor(self.temp_dir)
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
        
    def create_precision_test_srt(self, test_case: str) -> str:
        """Create SRT content for different precision test cases."""
        
        if test_case == "microsecond":
            return """1
00:00:00,001 --> 00:00:01,999
Microsecond precision test.

2
00:00:02,000 --> 00:00:03,500
Half-second timing.

3
00:00:03,501 --> 00:00:05,999
Edge of precision."""
            
        elif test_case == "zero_start":
            return """1
00:00:00,000 --> 00:00:02,500
Starting at absolute zero.

2
00:00:02,500 --> 00:00:05,000
Standard continuation."""
            
        elif test_case == "rapid_fire":
            # Very short segments that could cause timing issues
            segments = []
            for i in range(20):
                start_ms = i * 100
                end_ms = start_ms + 50  # 50ms segments
                
                start_time = f"00:00:{start_ms//1000:02d},{start_ms%1000:03d}"
                end_time = f"00:00:{end_ms//1000:02d},{end_ms%1000:03d}"
                
                segments.append(f"""{i+1}
{start_time} --> {end_time}
Rapid segment {i+1}.""")
                
            return "\n\n".join(segments)
            
        elif test_case == "hour_boundary":
            return """1
00:59:59,500 --> 01:00:00,500
Crossing hour boundary.

2
01:00:00,500 --> 01:00:02,000
Into the next hour.

3
23:59:59,000 --> 23:59:59,999
End of day boundary."""
            
        else:
            return """1
00:00:00,100 --> 00:00:02,500
Default test case."""
    
    def parse_vtt_timing(self, timing_line: str) -> tuple:
        """Parse VTT timing line and return start/end as decimals."""
        match = re.match(r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})', timing_line)
        if not match:
            raise ValueError(f"Invalid VTT timing format: {timing_line}")
            
        start_str, end_str = match.groups()
        
        def parse_vtt_time(time_str):
            h, m, s_ms = time_str.split(':')
            s, ms = s_ms.split('.')
            return Decimal(int(h) * 3600 + int(m) * 60 + int(s)) + Decimal(int(ms)) / 1000
            
        return parse_vtt_time(start_str), parse_vtt_time(end_str)
    
    def parse_srt_timing(self, timing_line: str) -> tuple:
        """Parse SRT timing line and return start/end as decimals."""
        match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', timing_line)
        if not match:
            raise ValueError(f"Invalid SRT timing format: {timing_line}")
            
        start_str, end_str = match.groups()
        
        def parse_srt_time(time_str):
            h, m, s_ms = time_str.split(':')
            s, ms = s_ms.split(',')
            return Decimal(int(h) * 3600 + int(m) * 60 + int(s)) + Decimal(int(ms)) / 1000
            
        return parse_srt_time(start_str), parse_srt_time(end_str)
    
    def test_microsecond_precision_conversion(self):
        """Test that microsecond-level precision is maintained in SRT->VTT conversion."""
        srt_content = self.create_precision_test_srt("microsecond")
        
        # Create test file
        srt_file = Path(self.temp_dir) / "precision_test.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
            
        # Convert to VTT
        success = self.processor.convert_srt_to_vtt(srt_file)
        self.assertTrue(success, "VTT conversion failed")
        
        # Read both files
        vtt_file = srt_file.with_suffix('.vtt')
        with open(srt_file, 'r', encoding='utf-8') as f:
            srt_lines = f.readlines()
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_lines = f.readlines()
            
        # Extract timing lines
        srt_timings = [line.strip() for line in srt_lines if ' --> ' in line and ',' in line]
        vtt_timings = [line.strip() for line in vtt_lines if ' --> ' in line and '.' in line]
        
        self.assertEqual(len(srt_timings), len(vtt_timings), "Different number of timing lines")
        
        # Verify each timing conversion
        test_cases = [
            ("00:00:00,001 --> 00:00:01,999", "00:00:00.001 --> 00:00:01.999"),
            ("00:00:02,000 --> 00:00:03,500", "00:00:02.000 --> 00:00:03.500"),
            ("00:00:03,501 --> 00:00:05,999", "00:00:03.501 --> 00:00:05.999"),
        ]
        
        for i, (expected_srt, expected_vtt) in enumerate(test_cases):
            self.assertEqual(srt_timings[i], expected_srt, f"SRT timing {i} wrong")
            self.assertEqual(vtt_timings[i], expected_vtt, f"VTT timing {i} wrong")
            
            # Verify numerical equivalence
            srt_start, srt_end = self.parse_srt_timing(expected_srt)
            vtt_start, vtt_end = self.parse_vtt_timing(expected_vtt)
            
            self.assertEqual(srt_start, vtt_start, f"Start time numerical mismatch at {i}")
            self.assertEqual(srt_end, vtt_end, f"End time numerical mismatch at {i}")
    
    def test_zero_timing_edge_cases(self):
        """Test edge cases with zero timings."""
        srt_content = self.create_precision_test_srt("zero_start")
        
        srt_file = Path(self.temp_dir) / "zero_test.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
            
        success = self.processor.convert_srt_to_vtt(srt_file)
        self.assertTrue(success, "Zero timing conversion failed")
        
        vtt_file = srt_file.with_suffix('.vtt')
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
            
        # Verify zero timing conversion
        self.assertIn('00:00:00.000 --> 00:00:02.500', vtt_content)
        self.assertIn('00:00:02.500 --> 00:00:05.000', vtt_content)
        
        # Verify no artifacts from zero conversion
        self.assertNotIn('00:00:00,000', vtt_content)  # No SRT format in VTT
    
    def test_rapid_fire_timing_conversion(self):
        """Test conversion of many short segments (stress test for timing precision)."""
        srt_content = self.create_precision_test_srt("rapid_fire")
        
        srt_file = Path(self.temp_dir) / "rapid_test.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
            
        success = self.processor.convert_srt_to_vtt(srt_file)
        self.assertTrue(success, "Rapid fire conversion failed")
        
        # Parse both files to verify timing accuracy
        translator = SRTTranslator()
        srt_segments = translator.parse_srt(str(srt_file))
        
        vtt_file = srt_file.with_suffix('.vtt')
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
            
        # Extract VTT timing lines
        vtt_timing_lines = []
        for line in vtt_content.split('\n'):
            if ' --> ' in line and '.' in line:
                vtt_timing_lines.append(line.strip())
                
        self.assertEqual(len(srt_segments), len(vtt_timing_lines), 
                        "Different number of segments after conversion")
        
        # Verify each rapid segment timing
        for i, (srt_seg, vtt_timing) in enumerate(zip(srt_segments, vtt_timing_lines)):
            # Convert SRT timing to expected VTT format
            expected_vtt = f"{srt_seg.start_time} --> {srt_seg.end_time}".replace(',', '.')
            
            self.assertEqual(vtt_timing, expected_vtt, 
                           f"Rapid segment {i+1} timing mismatch")
    
    def test_hour_boundary_timing(self):
        """Test timing conversion across hour boundaries."""
        srt_content = self.create_precision_test_srt("hour_boundary")
        
        srt_file = Path(self.temp_dir) / "hour_test.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
            
        success = self.processor.convert_srt_to_vtt(srt_file)
        self.assertTrue(success, "Hour boundary conversion failed")
        
        vtt_file = srt_file.with_suffix('.vtt')
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
            
        # Check specific hour boundary conversions
        hour_boundary_cases = [
            ('00:59:59,500 --> 01:00:00,500', '00:59:59.500 --> 01:00:00.500'),
            ('01:00:00,500 --> 01:00:02,000', '01:00:00.500 --> 01:00:02.000'),
            ('23:59:59,000 --> 23:59:59,999', '23:59:59.000 --> 23:59:59.999'),
        ]
        
        for srt_timing, expected_vtt_timing in hour_boundary_cases:
            self.assertIn(expected_vtt_timing, vtt_content, 
                         f"Hour boundary timing not found: {expected_vtt_timing}")
            self.assertNotIn(srt_timing, vtt_content,
                           f"SRT timing found in VTT: {srt_timing}")
    
    def test_webvtt_header_compliance(self):
        """Test that VTT files have proper WebVTT headers."""
        srt_content = self.create_precision_test_srt("microsecond")
        
        srt_file = Path(self.temp_dir) / "header_test.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
            
        success = self.processor.convert_srt_to_vtt(srt_file)
        self.assertTrue(success, "Header test conversion failed")
        
        vtt_file = srt_file.with_suffix('.vtt')
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_lines = f.readlines()
            
        # WebVTT compliance checks
        self.assertTrue(len(vtt_lines) >= 2, "VTT file too short")
        self.assertEqual(vtt_lines[0].strip(), 'WEBVTT', "Missing WEBVTT header")
        self.assertEqual(vtt_lines[1].strip(), '', "Missing blank line after header")
        
        # Ensure no SRT artifacts
        vtt_content = ''.join(vtt_lines)
        self.assertNotIn(',', vtt_content.replace('WEBVTT,', ''), 
                        "SRT comma format found in VTT")
    
    def test_conversion_preserves_text_content(self):
        """Test that text content is preserved exactly during timing conversion."""
        # Use special characters and formatting that could be affected
        special_srt = """1
00:00:00,100 --> 00:00:02,500
Text with "quotes" and 'apostrophes'.

2
00:00:02,600 --> 00:00:05,000
Unicode: äöü ßÄÖÜ שלום עליכם

3
00:00:05,100 --> 00:00:07,500
Numbers: 1,234.56 and dates: 12/31/1999

4
00:00:07,600 --> 00:00:10,000
Special chars: @#$%^&*()_+-=[]{}|;':\",./<>?"""
        
        srt_file = Path(self.temp_dir) / "special_chars.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(special_srt)
            
        success = self.processor.convert_srt_to_vtt(srt_file)
        self.assertTrue(success, "Special character conversion failed")
        
        # Parse both files
        translator = SRTTranslator()
        srt_segments = translator.parse_srt(str(srt_file))
        
        vtt_file = srt_file.with_suffix('.vtt')
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
            
        # Verify all text content is preserved
        for segment in srt_segments:
            self.assertIn(segment.text, vtt_content, 
                         f"Text not preserved: {segment.text}")
        
        # Verify specific special cases
        test_texts = [
            'Text with "quotes" and \'apostrophes\'.',
            'Unicode: äöü ßÄÖÜ שלום עליכם',
            'Numbers: 1,234.56 and dates: 12/31/1999',
            'Special chars: @#$%^&*()_+-=[]{}|;\':\",./<>?'
        ]
        
        for text in test_texts:
            self.assertIn(text, vtt_content, f"Special text not preserved: {text}")
    
    def test_large_file_conversion_performance(self):
        """Test that large files convert without timing degradation."""
        # Create a large SRT file with many segments
        large_segments = []
        for i in range(1000):  # 1000 segments
            start_seconds = i * 2
            end_seconds = start_seconds + 1.5
            
            start_time = f"{start_seconds//3600:02d}:{(start_seconds%3600)//60:02d}:{start_seconds%60:02d},{(start_seconds*1000)%1000:03d}"
            end_time = f"{int(end_seconds)//3600:02d}:{(int(end_seconds)%3600)//60:02d}:{int(end_seconds)%60:02d},{int(end_seconds*1000)%1000:03d}"
            
            large_segments.append(f"""{i+1}
{start_time} --> {end_time}
Large file segment {i+1} content.""")
            
        large_srt_content = "\n\n".join(large_segments)
        
        srt_file = Path(self.temp_dir) / "large_file.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(large_srt_content)
            
        # Time the conversion
        import time
        start_time = time.time()
        success = self.processor.convert_srt_to_vtt(srt_file)
        conversion_time = time.time() - start_time
        
        self.assertTrue(success, "Large file conversion failed")
        self.assertLess(conversion_time, 5.0, "Conversion too slow for large file")
        
        # Verify conversion accuracy on sample segments
        vtt_file = srt_file.with_suffix('.vtt')
        with open(vtt_file, 'r', encoding='utf-8') as f:
            vtt_content = f.read()
            
        # Check first and last segments for accuracy
        self.assertIn('00:00:00.000 --> 00:00:01.500', vtt_content)  # First segment
        self.assertIn('Large file segment 1 content.', vtt_content)
        self.assertIn('Large file segment 1000 content.', vtt_content)  # Last segment
        
        # Verify no SRT format leaked through
        timing_lines = [line for line in vtt_content.split('\n') if ' --> ' in line]
        for timing_line in timing_lines[:10]:  # Check first 10
            self.assertNotIn(',', timing_line, f"SRT comma in VTT timing: {timing_line}")
            self.assertIn('.', timing_line, f"Missing VTT dot in timing: {timing_line}")


def run_vtt_precision_tests():
    """Run all VTT timing precision tests."""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestVTTTimingPrecision))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n" + "="*50)
        print("✅ VTT TIMING PRECISION TESTS PASSED")
        print("="*50)
        print("Verified:")
        print("• Microsecond precision preservation")
        print("• Zero timing edge cases")
        print("• Rapid-fire segment conversion")
        print("• Hour boundary timing")
        print("• WebVTT header compliance")
        print("• Text content preservation")
        print("• Large file performance")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("❌ VTT TIMING PRECISION TESTS FAILED")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print("="*50)
        
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_vtt_precision_tests()
    sys.exit(0 if success else 1)