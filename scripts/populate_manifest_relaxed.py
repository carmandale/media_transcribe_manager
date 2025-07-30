#!/usr/bin/env python3
"""
Populate manifest with transcript data for the Scribe chat system.

This script takes the extracted transcript data and integrates it into the 
manifest.min.json file, enabling rich content search in the chat system.
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import argparse
from datetime import datetime
import shutil


class ManifestPopulator:
    """Populates manifest with transcript data."""
    
    def __init__(self, manifest_path: Path, transcripts_path: Path):
        self.manifest_path = manifest_path
        self.transcripts_path = transcripts_path
        self.backup_path = None
        
    def create_backup(self):
        """Create a backup of the original manifest."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = self.manifest_path.parent / f"manifest.min.json.backup.{timestamp}"
        shutil.copy2(self.manifest_path, self.backup_path)
        print(f"📋 Created backup: {self.backup_path}")
    
    def load_manifest(self) -> List[Dict[str, Any]]:
        """Load the current manifest file."""
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_transcripts(self) -> Dict[str, Dict[str, Any]]:
        """Load the extracted transcript data."""
        with open(self.transcripts_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def enhance_interview_metadata(self, interview: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance interview metadata with better parsing."""
        metadata = interview.get('metadata', {})
        interviewee = metadata.get('interviewee', '')
        
        # Extract better interview information from the interviewee field
        enhanced_metadata = metadata.copy()
        
        # Try to extract date from interviewee string
        import re
        date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', interviewee)
        if date_match and not metadata.get('date'):
            date_str = date_match.group(1)
            try:
                # Parse various date formats - basic parsing without dateutil
                # Common format: "13 April 2002"
                months = {
                    'january': '01', 'february': '02', 'march': '03', 'april': '04',
                    'may': '05', 'june': '06', 'july': '07', 'august': '08',
                    'september': '09', 'october': '10', 'november': '11', 'december': '12',
                    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                    'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 
                    'oct': '10', 'nov': '11', 'dec': '12'
                }
                
                parts = date_str.lower().split()
                if len(parts) == 3:
                    day = parts[0].zfill(2)
                    month = months.get(parts[1][:3], '01')
                    year = parts[2]
                    enhanced_metadata['date'] = f"{year}-{month}-{day}"
            except:
                pass  # Keep original date if parsing fails
        
        # Clean up interviewee name (remove redundant information)
        if interviewee:
            # Remove leading numbers and clean up
            clean_name = re.sub(r'^\d+\s*', '', interviewee)
            # Remove date information that we've extracted
            if date_match:
                clean_name = clean_name.replace(date_match.group(1), '').strip()
            # Remove trailing comma and spaces
            clean_name = clean_name.strip(' ,')
            if clean_name and clean_name != interviewee:
                enhanced_metadata['interviewee'] = clean_name
        
        return enhanced_metadata
    
    def populate_manifest(self) -> List[Dict[str, Any]]:
        """Populate manifest with transcript data."""
        print("📄 Loading manifest and transcript data...")
        
        manifest = self.load_manifest()
        transcripts = self.load_transcripts()
        
        print(f"   Manifest entries: {len(manifest)}")
        print(f"   Available transcripts: {len(transcripts)}")
        
        populated_count = 0
        missing_transcripts = []
        
        for interview in manifest:
            interview_id = interview.get('id')
            if not interview_id:
                continue
            
            # Enhance metadata
            interview['metadata'] = self.enhance_interview_metadata(interview)
            
            # Add transcript data if available
            if interview_id in transcripts:
                transcript_data = transcripts[interview_id]
                
                # Add transcripts array following TypeScript interface
                interview['transcripts'] = [transcript_data]
                
                # Generate summary from first part of transcript
                full_text = transcript_data.get('text', '')
                if full_text and not interview['metadata'].get('summary'):
                    # Create a brief summary from the first 200 characters
                    summary = full_text[:200].strip()
                    if len(full_text) > 200:
                        # Try to end at a sentence boundary
                        sentence_end = summary.rfind('.')
                        question_end = summary.rfind('?')
                        exclamation_end = summary.rfind('!')
                        
                        best_end = max(sentence_end, question_end, exclamation_end)
                        if best_end > 100:  # Only use if we have enough content
                            summary = summary[:best_end + 1]
                        else:
                            summary += "..."
                    
                    interview['metadata']['summary'] = summary
                
                populated_count += 1
            else:
                missing_transcripts.append(interview_id)
                # Ensure transcripts array exists even if empty
                interview['transcripts'] = []
        
        print(f"✅ Successfully populated {populated_count} interviews with transcripts")
        
        if missing_transcripts:
            print(f"⚠️  Missing transcripts for {len(missing_transcripts)} interviews:")
            for missing_id in missing_transcripts[:5]:  # Show first 5
                print(f"      - {missing_id}")
            if len(missing_transcripts) > 5:
                print(f"      ... and {len(missing_transcripts) - 5} more")
        
        return manifest
    
    def save_manifest(self, manifest: List[Dict[str, Any]]):
        """Save the populated manifest."""
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved populated manifest to {self.manifest_path}")
    
    def validate_manifest(self, manifest: List[Dict[str, Any]]) -> bool:
        """Validate the populated manifest structure."""
        print("🔍 Validating manifest structure...")
        
        required_fields = ['id', 'metadata', 'assets']
        metadata_fields = ['interviewee', 'date', 'summary']
        
        valid_count = 0
        issues = []
        
        for i, interview in enumerate(manifest):
            # Check required top-level fields
            for field in required_fields:
                if field not in interview:
                    issues.append(f"Interview {i}: Missing required field '{field}'")
                    continue
            
            # Check metadata fields
            metadata = interview.get('metadata', {})
            for field in metadata_fields:
                if field not in metadata or not metadata[field]:
                    issues.append(f"Interview {i} ({interview.get('id', 'unknown')}): Missing or empty metadata field '{field}'")
            
            # Check transcripts structure
            transcripts = interview.get('transcripts', [])
            if transcripts:
                transcript = transcripts[0]
                required_transcript_fields = ['language', 'text', 'cues']
                for field in required_transcript_fields:
                    if field not in transcript:
                        issues.append(f"Interview {i}: Missing transcript field '{field}'")
                
                # Check cues structure
                cues = transcript.get('cues', [])
                if cues:
                    cue = cues[0]
                    required_cue_fields = ['start', 'end', 'text']
                    for field in required_cue_fields:
                        if field not in cue:
                            issues.append(f"Interview {i}: Missing cue field '{field}'")
            
            if not issues or len([issue for issue in issues if f"Interview {i}" in issue]) == 0:
                valid_count += 1
        
        print(f"   ✅ Valid entries: {valid_count}/{len(manifest)}")
        
        if issues:
            print(f"   ⚠️  Found {len(issues)} validation issues:")
            for issue in issues[:10]:  # Show first 10
                print(f"      - {issue}")
            if len(issues) > 10:
                print(f"      ... and {len(issues) - 10} more issues")
            return False
        
        print("   🎉 All entries passed validation!")
        return True
        
    def generate_stats(self, manifest: List[Dict[str, Any]]):
        """Generate statistics about the populated manifest."""
        total_interviews = len(manifest)
        interviews_with_transcripts = sum(1 for interview in manifest if interview.get('transcripts'))
        interviews_with_summaries = sum(1 for interview in manifest if interview.get('metadata', {}).get('summary'))
        interviews_with_dates = sum(1 for interview in manifest if interview.get('metadata', {}).get('date'))
        
        total_text_length = 0
        total_cues = 0
        
        for interview in manifest:
            transcripts = interview.get('transcripts', [])
            if transcripts:
                transcript = transcripts[0]
                total_text_length += len(transcript.get('text', ''))
                total_cues += len(transcript.get('cues', []))
        
        print(f"\n📊 Populated Manifest Statistics:")
        print(f"   Total interviews: {total_interviews}")
        print(f"   With transcripts: {interviews_with_transcripts} ({interviews_with_transcripts/total_interviews*100:.1f}%)")
        print(f"   With summaries: {interviews_with_summaries} ({interviews_with_summaries/total_interviews*100:.1f}%)")
        print(f"   With dates: {interviews_with_dates} ({interviews_with_dates/total_interviews*100:.1f}%)")
        print(f"   Total transcript text: {total_text_length:,} characters")
        print(f"   Total cues: {total_cues:,}")
        
        if interviews_with_transcripts > 0:
            avg_text_per_interview = total_text_length / interviews_with_transcripts
            avg_cues_per_interview = total_cues / interviews_with_transcripts
            print(f"   Average text per interview: {avg_text_per_interview:,.0f} characters")
            print(f"   Average cues per interview: {avg_cues_per_interview:.1f}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Populate manifest with transcript data")
    parser.add_argument(
        "--manifest", 
        type=Path, 
        default=Path("scribe-viewer/public/manifest.min.json"),
        help="Path to manifest file (default: scribe-viewer/public/manifest.min.json)"
    )
    parser.add_argument(
        "--transcripts", 
        type=Path, 
        default=Path("scripts/extracted_transcripts.json"),
        help="Path to extracted transcripts (default: scripts/extracted_transcripts.json)"
    )
    parser.add_argument(
        "--no-backup", 
        action="store_true",
        help="Skip creating backup of original manifest"
    )
    parser.add_argument(
        "--validate-only", 
        action="store_true",
        help="Only validate the current manifest, don't modify it"
    )
    
    args = parser.parse_args()
    
    # Validate input files
    if not args.manifest.exists():
        print(f"ERROR: Manifest file not found: {args.manifest}")
        return 1
    
    if not args.transcripts.exists():
        print(f"ERROR: Transcripts file not found: {args.transcripts}")
        return 1
    
    # Create populator
    populator = ManifestPopulator(args.manifest, args.transcripts)
    
    print(f"🚀 Scribe Manifest Populator")
    print(f"   Manifest: {args.manifest}")
    print(f"   Transcripts: {args.transcripts}")
    print()
    
    if args.validate_only:
        # Just validate current manifest
        manifest = populator.load_manifest()
        populator.validate_manifest(manifest)
        populator.generate_stats(manifest)
        return 0
    
    # Create backup unless disabled
    if not args.no_backup:
        populator.create_backup()
    
    # Populate manifest
    populated_manifest = populator.populate_manifest()
    
    # Validate populated manifest
    if not populator.validate_manifest(populated_manifest):
        print("\n❌ Validation failed - not saving manifest")
        if populator.backup_path:
            print(f"   Original backup available at: {populator.backup_path}")
        return 1
    
    # Save populated manifest
    populator.save_manifest(populated_manifest)
    
    # Generate final statistics
    populator.generate_stats(populated_manifest)
    
    print(f"\n✅ Manifest population complete!")
    print(f"   Search system is now ready for rich content")
    if populator.backup_path:
        print(f"   Original backup: {populator.backup_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())