#!/usr/bin/env python3
"""
Generate Missing Subtitle Files for Scribe System
------------------------------------------------
This utility generates SRT subtitle files for translations that are missing them.
It uses the word-level timing information from the original transcription JSON files
to create synchronized subtitles for all language translations.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import click
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SubtitleGenerationResult:
    """Result of subtitle generation operation."""
    file_id: str
    language: str
    srt_path: Path
    success: bool
    error: Optional[str] = None


class SubtitleGenerator:
    """Generates SRT subtitle files from translation text and timing data."""
    
    def __init__(self, output_dir: Path = Path("output"), db_path: Path = Path("media_tracking.db")):
        """Initialize generator with paths."""
        self.output_dir = output_dir
        self.db_path = db_path
        
    def get_missing_subtitles(self) -> Dict[str, List[str]]:
        """Get list of missing subtitle files by language."""
        missing = {
            'en': [],
            'de': [],
            'he': [],
            'original': []
        }
        
        # Connect to database to get all file IDs
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all files
        cursor.execute("SELECT file_id FROM media_files")
        files = cursor.fetchall()
        conn.close()
        
        for row in files:
            file_id = row['file_id']
            file_dir = self.output_dir / file_id
            
            if not file_dir.exists():
                continue
                
            # Check for missing SRT files
            # Original transcription
            if (file_dir / f"{file_id}.txt").exists() and not (file_dir / f"{file_id}.srt").exists():
                missing['original'].append(file_id)
                
            # English translation
            if (file_dir / f"{file_id}.en.txt").exists() and not (file_dir / f"{file_id}.en.srt").exists():
                missing['en'].append(file_id)
                
            # German translation  
            if (file_dir / f"{file_id}.de.txt").exists() and not (file_dir / f"{file_id}.de.srt").exists():
                missing['de'].append(file_id)
                
            # Hebrew translation
            if (file_dir / f"{file_id}.he.txt").exists() and not (file_dir / f"{file_id}.he.srt").exists():
                missing['he'].append(file_id)
                
        return missing
    
    def generate_subtitle(self, file_id: str, language: str) -> SubtitleGenerationResult:
        """Generate SRT subtitle file for a specific file and language."""
        file_dir = self.output_dir / file_id
        
        # Determine file paths
        if language == 'original':
            text_path = file_dir / f"{file_id}.txt"
            srt_path = file_dir / f"{file_id}.srt"
        else:
            text_path = file_dir / f"{file_id}.{language}.txt"
            srt_path = file_dir / f"{file_id}.{language}.srt"
            
        json_path = file_dir / f"{file_id}.txt.json"
        
        # Check if required files exist
        if not text_path.exists():
            return SubtitleGenerationResult(
                file_id=file_id,
                language=language,
                srt_path=srt_path,
                success=False,
                error=f"Text file not found: {text_path}"
            )
            
        if not json_path.exists():
            return SubtitleGenerationResult(
                file_id=file_id,
                language=language,
                srt_path=srt_path,
                success=False,
                error=f"JSON timing file not found: {json_path}"
            )
            
        try:
            # Read text content
            text_content = text_path.read_text(encoding='utf-8')
            
            # Read timing data
            timing_data = json.loads(json_path.read_text(encoding='utf-8'))
            
            # Generate SRT content
            srt_content = self._create_srt_from_timing(text_content, timing_data, language)
            
            # Write SRT file
            srt_path.write_text(srt_content, encoding='utf-8')
            
            return SubtitleGenerationResult(
                file_id=file_id,
                language=language,
                srt_path=srt_path,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error generating subtitle for {file_id} ({language}): {e}")
            return SubtitleGenerationResult(
                file_id=file_id,
                language=language,
                srt_path=srt_path,
                success=False,
                error=str(e)
            )
    
    def _create_srt_from_timing(self, text: str, timing_data: Dict[str, Any], 
                               language: str, max_chars: int = 80, 
                               max_duration: float = 5.0) -> str:
        """Create SRT content using word timing data."""
        # Get words from timing data
        words = timing_data.get('words', [])
        if not words:
            logger.warning("No word timing data available")
            return ""
            
        # For translations, we need to map the translated text to timing
        # This is approximate since we don't have word-level timing for translations
        if language != 'original':
            return self._create_srt_for_translation(text, words, max_chars, max_duration)
        else:
            # For original transcription, use exact word timing
            return self._create_srt_from_words(words, max_chars, max_duration)
    
    def _create_srt_from_words(self, words: List[Dict[str, Any]], 
                               max_chars: int = 80, max_duration: float = 5.0) -> str:
        """Create SRT from word-level timing data."""
        if not words:
            return ""
            
        srt_lines = []
        subtitle_index = 1
        current_words = []
        start_time = None
        
        for i, word_data in enumerate(words):
            # Skip non-word entries
            if word_data.get('type') != 'word':
                continue
                
            word_text = word_data.get('text', '')
            word_start = word_data.get('start', 0)
            word_end = word_data.get('end', 0)
            
            if not word_text.strip():
                continue
                
            # Initialize subtitle
            if not current_words:
                start_time = word_start
                current_words.append(word_text)
                continue
                
            # Check constraints
            current_text = ' '.join(current_words)
            new_text = f"{current_text} {word_text}"
            duration = word_end - start_time
            
            if len(new_text) > max_chars or duration > max_duration:
                # Finalize current subtitle
                end_time = words[i-1].get('end', word_start)
                
                srt_lines.append(str(subtitle_index))
                srt_lines.append(f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}")
                srt_lines.append(current_text)
                srt_lines.append("")
                
                # Start new subtitle
                subtitle_index += 1
                current_words = [word_text]
                start_time = word_start
            else:
                current_words.append(word_text)
        
        # Add final subtitle
        if current_words and start_time is not None:
            end_time = words[-1].get('end', start_time + 2.0)
            srt_lines.append(str(subtitle_index))
            srt_lines.append(f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}")
            srt_lines.append(' '.join(current_words))
            srt_lines.append("")
            
        return '\n'.join(srt_lines)
    
    def _create_srt_for_translation(self, translated_text: str, original_words: List[Dict[str, Any]], 
                                   max_chars: int = 80, max_duration: float = 5.0) -> str:
        """Create SRT for translated text using original timing as reference."""
        # Split translated text into sentences
        sentences = self._split_into_sentences(translated_text)
        if not sentences or not original_words:
            return ""
            
        # Get total duration from original timing
        word_timings = [w for w in original_words if w.get('type') == 'word' and w.get('start') is not None]
        if not word_timings:
            return ""
            
        total_duration = word_timings[-1].get('end', 0) - word_timings[0].get('start', 0)
        if total_duration <= 0:
            return ""
            
        # Distribute sentences across the timeline
        srt_lines = []
        subtitle_index = 1
        start_time = word_timings[0].get('start', 0)
        time_per_char = total_duration / len(translated_text)
        
        current_subtitle = []
        current_start = start_time
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Check if adding this sentence exceeds max_chars
            current_text = ' '.join(current_subtitle)
            if current_subtitle and len(current_text + ' ' + sentence) > max_chars:
                # Finalize current subtitle
                subtitle_duration = len(current_text) * time_per_char
                end_time = current_start + min(subtitle_duration, max_duration)
                
                srt_lines.append(str(subtitle_index))
                srt_lines.append(f"{self._format_srt_time(current_start)} --> {self._format_srt_time(end_time)}")
                srt_lines.append(current_text)
                srt_lines.append("")
                
                subtitle_index += 1
                current_subtitle = [sentence]
                current_start = end_time
            else:
                current_subtitle.append(sentence)
                
        # Add final subtitle
        if current_subtitle:
            current_text = ' '.join(current_subtitle)
            end_time = min(current_start + len(current_text) * time_per_char, 
                          word_timings[-1].get('end', current_start + 2.0))
            
            srt_lines.append(str(subtitle_index))
            srt_lines.append(f"{self._format_srt_time(current_start)} --> {self._format_srt_time(end_time)}")
            srt_lines.append(current_text)
            srt_lines.append("")
            
        return '\n'.join(srt_lines)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Basic sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Further split long sentences at natural breaks
        result = []
        for sentence in sentences:
            if len(sentence) > 100:
                # Split at commas or semicolons if sentence is too long
                parts = re.split(r'[,;]\s*', sentence)
                current = ""
                for part in parts:
                    if not current:
                        current = part
                    elif len(current + ", " + part) < 80:
                        current += ", " + part
                    else:
                        result.append(current)
                        current = part
                if current:
                    result.append(current)
            else:
                result.append(sentence)
                
        return result
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds as SRT timestamp (00:00:00,000)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def generate_all_missing(self, languages: Optional[List[str]] = None, 
                           limit: Optional[int] = None) -> Dict[str, List[SubtitleGenerationResult]]:
        """Generate all missing subtitles."""
        if languages is None:
            languages = ['en', 'de', 'he', 'original']
            
        missing = self.get_missing_subtitles()
        results = {}
        
        total_processed = 0
        
        for lang in languages:
            if lang not in missing:
                continue
                
            results[lang] = []
            file_ids = missing[lang]
            
            if limit and total_processed >= limit:
                break
                
            for file_id in file_ids:
                if limit and total_processed >= limit:
                    break
                    
                logger.info(f"Generating {lang} subtitle for {file_id}")
                result = self.generate_subtitle(file_id, lang)
                results[lang].append(result)
                
                if result.success:
                    logger.info(f"✓ Generated: {result.srt_path}")
                else:
                    logger.error(f"✗ Failed: {result.error}")
                    
                total_processed += 1
                
        return results


@click.group()
def cli():
    """Generate missing subtitle files for Scribe translations."""
    pass


@cli.command()
def status():
    """Show status of missing subtitle files."""
    generator = SubtitleGenerator()
    missing = generator.get_missing_subtitles()
    
    click.echo("\nMissing Subtitle Files:")
    click.echo("=" * 40)
    
    total = 0
    for lang, files in missing.items():
        count = len(files)
        total += count
        lang_name = {
            'en': 'English',
            'de': 'German', 
            'he': 'Hebrew',
            'original': 'Original'
        }.get(lang, lang)
        click.echo(f"{lang_name:.<20} {count:>4} files")
        
    click.echo("=" * 40)
    click.echo(f"{'Total':.<20} {total:>4} files")


@cli.command()
@click.option('--language', '-l', type=click.Choice(['en', 'de', 'he', 'original', 'all']), 
              default='all', help='Language to generate subtitles for')
@click.option('--limit', '-n', type=int, help='Maximum number of files to process')
@click.option('--file-id', '-f', help='Generate subtitle for specific file ID')
def generate(language: str, limit: Optional[int], file_id: Optional[str]):
    """Generate missing subtitle files."""
    generator = SubtitleGenerator()
    
    if file_id:
        # Generate for specific file
        click.echo(f"Generating {language} subtitle for {file_id}")
        result = generator.generate_subtitle(file_id, language)
        
        if result.success:
            click.echo(f"✓ Generated: {result.srt_path}")
        else:
            click.echo(f"✗ Failed: {result.error}")
    else:
        # Generate for all missing
        languages = None if language == 'all' else [language]
        
        click.echo(f"Generating missing subtitles...")
        if limit:
            click.echo(f"Limit: {limit} files")
            
        results = generator.generate_all_missing(languages, limit)
        
        # Show summary
        click.echo("\nGeneration Summary:")
        click.echo("=" * 50)
        
        total_success = 0
        total_failed = 0
        
        for lang, lang_results in results.items():
            success = sum(1 for r in lang_results if r.success)
            failed = sum(1 for r in lang_results if not r.success)
            
            total_success += success
            total_failed += failed
            
            lang_name = {
                'en': 'English',
                'de': 'German',
                'he': 'Hebrew', 
                'original': 'Original'
            }.get(lang, lang)
            
            click.echo(f"{lang_name:.<20} Success: {success:>4}, Failed: {failed:>4}")
            
        click.echo("=" * 50)
        click.echo(f"{'Total':.<20} Success: {total_success:>4}, Failed: {total_failed:>4}")


@cli.command()
@click.argument('file_id')
@click.argument('language', type=click.Choice(['en', 'de', 'he', 'original']))
def test(file_id: str, language: str):
    """Test subtitle generation for a specific file."""
    generator = SubtitleGenerator()
    
    # Check if files exist
    file_dir = generator.output_dir / file_id
    if language == 'original':
        text_path = file_dir / f"{file_id}.txt"
    else:
        text_path = file_dir / f"{file_id}.{language}.txt"
        
    json_path = file_dir / f"{file_id}.txt.json"
    
    click.echo(f"\nChecking files for {file_id} ({language}):")
    click.echo(f"Text file exists: {text_path.exists()}")
    click.echo(f"JSON file exists: {json_path.exists()}")
    
    if text_path.exists() and json_path.exists():
        # Try to generate
        result = generator.generate_subtitle(file_id, language)
        
        if result.success:
            click.echo(f"\n✓ Successfully generated: {result.srt_path}")
            
            # Show first few lines of SRT
            srt_content = result.srt_path.read_text(encoding='utf-8')
            lines = srt_content.split('\n')[:20]
            
            click.echo("\nFirst few lines of generated SRT:")
            click.echo("-" * 40)
            for line in lines:
                click.echo(line)
        else:
            click.echo(f"\n✗ Generation failed: {result.error}")
    else:
        click.echo("\nRequired files not found!")


if __name__ == "__main__":
    cli()