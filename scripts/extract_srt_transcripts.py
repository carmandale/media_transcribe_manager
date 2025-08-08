#!/usr/bin/env python3
"""
Extract transcript data from .orig.srt files for the Scribe chat system.

This script processes all .orig.srt files in the output/ directory and extracts
clean transcript text with timestamp information for use in the chat system.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse
from dataclasses import dataclass


@dataclass
class TranscriptCue:
    """Represents a single subtitle cue with timing and text."""
    start: float  # Start time in seconds
    end: float    # End time in seconds
    text: str     # Clean text content

    def to_dict(self) -> Dict:
        """Convert to dictionary format matching TypeScript interface."""
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text
        }


@dataclass
class InterviewTranscript:
    """Represents a complete interview transcript."""
    language: str           # Language code (e.g., 'orig')
    text: str              # Full concatenated text
    cues: List[TranscriptCue]  # Time-synchronized cues

    def to_dict(self) -> Dict:
        """Convert to dictionary format matching TypeScript interface."""
        return {
            "language": self.language,
            "text": self.text,
            "cues": [cue.to_dict() for cue in self.cues]
        }


class SRTProcessor:
    """Processes SRT files and extracts transcript data."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.processed_count = 0
        self.error_count = 0
        self.errors = []

    def parse_timestamp(self, timestamp: str) -> float:
        """Convert SRT timestamp to seconds.
        
        Args:
            timestamp: SRT timestamp format (HH:MM:SS,mmm)
            
        Returns:
            Time in seconds as float
        """
        try:
            # Replace comma with dot for milliseconds
            timestamp = timestamp.replace(',', '.')
            
            # Parse HH:MM:SS.mmm
            time_parts = timestamp.split(':')
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            seconds = float(time_parts[2])
            
            return hours * 3600 + minutes * 60 + seconds
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid timestamp format: {timestamp}") from e

    def clean_text(self, text: str) -> str:
        """Clean SRT text content.
        
        Args:
            text: Raw SRT text
            
        Returns:
            Cleaned text suitable for search and display
        """
        # Remove HTML tags if any
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove multiple spaces and normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text

    def parse_srt_file(self, srt_path: Path) -> InterviewTranscript:
        """Parse a single SRT file.
        
        Args:
            srt_path: Path to the SRT file
            
        Returns:
            InterviewTranscript object
            
        Raises:
            ValueError: If file format is invalid
            FileNotFoundError: If file doesn't exist
        """
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")

        cues = []
        full_text_parts = []
        
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(srt_path, 'r', encoding='latin-1') as f:
                content = f.read()

        # Split into subtitle blocks
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            if not block.strip():
                continue
                
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue  # Skip malformed blocks
            
            try:
                # Parse subtitle number (line 0)
                subtitle_num = int(lines[0].strip())
                
                # Parse timestamp (line 1)
                timestamp_line = lines[1].strip()
                timestamp_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', timestamp_line)
                
                if not timestamp_match:
                    continue  # Skip malformed timestamp
                
                start_time = self.parse_timestamp(timestamp_match.group(1))
                end_time = self.parse_timestamp(timestamp_match.group(2))
                
                # Extract text (lines 2+)
                text_lines = lines[2:]
                raw_text = ' '.join(text_lines)
                clean_text = self.clean_text(raw_text)
                
                if clean_text:  # Only add non-empty cues
                    cues.append(TranscriptCue(
                        start=start_time,
                        end=end_time,
                        text=clean_text
                    ))
                    full_text_parts.append(clean_text)
                    
            except (ValueError, IndexError) as e:
                # Log error but continue processing
                self.errors.append(f"Error parsing block in {srt_path}: {e}")
                continue

        # Create full text
        full_text = ' '.join(full_text_parts)
        
        return InterviewTranscript(
            language='orig',  # Original language
            text=full_text,
            cues=cues
        )

    def find_orig_srt_files(self) -> List[Tuple[str, Path]]:
        """Find all .orig.srt files in the output directory.
        
        Returns:
            List of (interview_id, srt_path) tuples
        """
        srt_files = []
        
        for interview_dir in self.output_dir.iterdir():
            if not interview_dir.is_dir():
                continue
                
            interview_id = interview_dir.name
            srt_path = interview_dir / f"{interview_id}.orig.srt"
            
            if srt_path.exists():
                srt_files.append((interview_id, srt_path))
            else:
                self.errors.append(f"Missing .orig.srt for interview: {interview_id}")
        
        return sorted(srt_files)

    def process_all_interviews(self) -> Dict[str, InterviewTranscript]:
        """Process all interviews and extract transcripts.
        
        Returns:
            Dictionary mapping interview_id to InterviewTranscript
        """
        transcripts = {}
        srt_files = self.find_orig_srt_files()
        
        print(f"Found {len(srt_files)} .orig.srt files to process")
        
        for interview_id, srt_path in srt_files:
            try:
                transcript = self.parse_srt_file(srt_path)
                transcripts[interview_id] = transcript
                self.processed_count += 1
                
                if self.processed_count % 50 == 0:
                    print(f"Processed {self.processed_count}/{len(srt_files)} interviews...")
                    
            except Exception as e:
                self.error_count += 1
                error_msg = f"Failed to process {interview_id}: {e}"
                self.errors.append(error_msg)
                print(f"ERROR: {error_msg}")
        
        print(f"\nProcessing complete:")
        print(f"  Successfully processed: {self.processed_count}")
        print(f"  Errors: {self.error_count}")
        
        if self.errors:
            print(f"  First 5 errors:")
            for error in self.errors[:5]:
                print(f"    - {error}")
        
        return transcripts

    def save_transcripts(self, transcripts: Dict[str, InterviewTranscript], output_file: Path):
        """Save extracted transcripts to JSON file.
        
        Args:
            transcripts: Dictionary of transcripts
            output_file: Path to save JSON file
        """
        # Convert to serializable format
        transcript_data = {}
        for interview_id, transcript in transcripts.items():
            transcript_data[interview_id] = transcript.to_dict()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(transcripts)} transcripts to {output_file}")

    def generate_stats(self, transcripts: Dict[str, InterviewTranscript]):
        """Generate and display statistics about the extracted transcripts."""
        if not transcripts:
            print("No transcripts to analyze")
            return
        
        total_cues = sum(len(t.cues) for t in transcripts.values())
        total_text_length = sum(len(t.text) for t in transcripts.values())
        total_duration = sum(
            max(cue.end for cue in t.cues) if t.cues else 0 
            for t in transcripts.values()
        )
        
        avg_cues_per_interview = total_cues / len(transcripts)
        avg_text_length = total_text_length / len(transcripts)
        avg_duration = total_duration / len(transcripts) / 60  # minutes
        
        print(f"\n📊 Transcript Statistics:")
        print(f"  Total interviews: {len(transcripts)}")
        print(f"  Total cues: {total_cues:,}")
        print(f"  Total text characters: {total_text_length:,}")
        print(f"  Total duration: {total_duration/3600:.1f} hours")
        print(f"  Average cues per interview: {avg_cues_per_interview:.1f}")
        print(f"  Average text length: {avg_text_length:,.0f} characters")
        print(f"  Average duration: {avg_duration:.1f} minutes")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Extract transcript data from .orig.srt files")
    parser.add_argument(
        "--output-dir", 
        type=Path, 
        default=Path("output"),
        help="Directory containing interview folders (default: output)"
    )
    parser.add_argument(
        "--save-file", 
        type=Path, 
        default=Path("scripts/extracted_transcripts.json"),
        help="Output file for extracted transcripts (default: scripts/extracted_transcripts.json)"
    )
    parser.add_argument(
        "--stats-only", 
        action="store_true",
        help="Only show statistics, don't save transcripts"
    )
    
    args = parser.parse_args()
    
    # Validate paths
    if not args.output_dir.exists():
        print(f"ERROR: Output directory not found: {args.output_dir}")
        return 1
    
    # Create processor
    processor = SRTProcessor(args.output_dir)
    
    print(f"🎬 Scribe Transcript Extractor")
    print(f"   Processing .orig.srt files from: {args.output_dir}")
    print(f"   Output file: {args.save_file}")
    print()
    
    # Process all interviews
    transcripts = processor.process_all_interviews()
    
    if not transcripts:
        print("No transcripts were successfully processed")
        return 1
    
    # Generate statistics
    processor.generate_stats(transcripts)
    
    # Save transcripts unless stats-only mode
    if not args.stats_only:
        # Ensure output directory exists
        args.save_file.parent.mkdir(parents=True, exist_ok=True)
        processor.save_transcripts(transcripts, args.save_file)
        print(f"\n✅ Transcript extraction complete!")
        print(f"   Ready for manifest integration")
    
    return 0


if __name__ == "__main__":
    exit(main())