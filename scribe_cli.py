#!/usr/bin/env python3
"""
Scribe CLI - Clean, modern interface for historical media preservation
Processes interview recordings through transcription, translation, and quality evaluation.
"""

import click
import logging
from pathlib import Path
from typing import Optional

from scribe.database import Database
from scribe.pipeline import Pipeline, PipelineConfig
from scribe.evaluate import evaluate_file

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('scribe')


@click.group()
@click.version_option(version='2.0.0', prog_name='Scribe')
def cli():
    """Scribe - Preserve historical interviews through accurate transcription and translation.
    
    This tool processes audio/video recordings to create research-ready transcripts
    and translations while maintaining the authentic voice of speakers.
    """
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, help='Scan directories recursively')
def add(path: str, recursive: bool):
    """Add media files to the processing queue.
    
    PATH can be a single file or directory.
    """
    db = Database()
    path_obj = Path(path)
    
    if path_obj.is_file():
        # Single file
        file_id = db.add_file_simple(str(path_obj))
        if file_id:
            click.echo(f"✓ Added: {path_obj.name}")
        else:
            click.echo(f"• Already exists: {path_obj.name}")
    else:
        # Directory
        extensions = {'.mp3', '.mp4', '.wav', '.m4a', '.flac', '.ogg', '.avi', '.mov'}
        pattern = '**/*' if recursive else '*'
        
        added = 0
        skipped = 0
        
        for ext in extensions:
            for file_path in path_obj.glob(f"{pattern}{ext}"):
                if file_path.is_file():
                    file_id = db.add_file_simple(str(file_path))
                    if file_id:
                        added += 1
                    else:
                        skipped += 1
        
        click.echo(f"\n✓ Added {added} files")
        if skipped:
            click.echo(f"• Skipped {skipped} existing files")


@cli.command()
@click.option('--workers', '-w', default=10, help='Number of parallel workers')
@click.option('--limit', '-l', type=int, help='Maximum files to process')
def transcribe(workers: int, limit: Optional[int]):
    """Transcribe pending audio files to text.
    
    Uses ElevenLabs Scribe API for verbatim transcription with speaker diarization.
    """
    pipeline = Pipeline(PipelineConfig(transcription_workers=workers))
    
    # Check for pending files
    db = Database()
    pending_count = len(db.get_pending_files('transcription'))
    
    if not pending_count:
        click.echo("No pending transcriptions")
        return
    
    click.echo(f"Starting transcription of {pending_count} files with {workers} workers...")
    
    results = pipeline.process_transcriptions(limit=limit)
    
    # Summary
    successful = sum(1 for r in results if r.transcribed)
    failed = len(results) - successful
    
    click.echo(f"\n✓ Transcribed: {successful}")
    if failed:
        click.echo(f"✗ Failed: {failed}")


@cli.command()
@click.argument('language', type=click.Choice(['en', 'de', 'he']))
@click.option('--workers', '-w', default=8, help='Number of parallel workers')
@click.option('--limit', '-l', type=int, help='Maximum files to process')
def translate(language: str, workers: int, limit: Optional[int]):
    """Translate transcripts to the specified language.
    
    LANGUAGE can be: en (English), de (German), or he (Hebrew).
    
    Preserves authentic speech patterns and historical context.
    """
    pipeline = Pipeline(PipelineConfig(translation_workers=workers))
    
    # Check for pending files
    db = Database()
    pending_count = len(db.get_pending_files(f'translation_{language}'))
    
    if not pending_count:
        click.echo(f"No pending {language.upper()} translations")
        return
    
    # Language names for display
    lang_names = {'en': 'English', 'de': 'German', 'he': 'Hebrew'}
    click.echo(f"Starting {lang_names[language]} translation of {pending_count} files with {workers} workers...")
    
    results = pipeline.process_translations(language, limit=limit)
    
    # Summary
    successful = sum(1 for r in results if r.translations.get(language, False))
    failed = len(results) - successful
    
    click.echo(f"\n✓ Translated: {successful}")
    if failed:
        click.echo(f"✗ Failed: {failed}")


@cli.command()
@click.argument('language', type=click.Choice(['en', 'de', 'he']))
@click.option('--sample', '-s', default=20, help='Number of files to evaluate')
def evaluate(language: str, sample: int):
    """Evaluate translation quality for historical accuracy.
    
    LANGUAGE can be: en (English), de (German), or he (Hebrew).
    
    Scores translations on accuracy and speech pattern preservation.
    """
    pipeline = Pipeline()
    
    click.echo(f"Evaluating {sample} {language.upper()} translations...")
    
    scores = pipeline.evaluate_translations(language, sample_size=sample)
    
    if not scores:
        click.echo("No translations to evaluate")
        return
    
    # Calculate statistics
    scores_only = [s[1] for s in scores]
    avg_score = sum(scores_only) / len(scores_only)
    min_score = min(scores_only)
    max_score = max(scores_only)
    
    # Display results
    click.echo(f"\nEvaluated {len(scores)} translations:")
    click.echo(f"Average score: {avg_score:.1f}/10")
    click.echo(f"Range: {min_score:.1f} - {max_score:.1f}")
    
    # Quality breakdown
    excellent = sum(1 for s in scores_only if s >= 8.5)
    good = sum(1 for s in scores_only if 7.0 <= s < 8.5)
    needs_improvement = sum(1 for s in scores_only if s < 7.0)
    
    click.echo(f"\nQuality breakdown:")
    click.echo(f"Excellent (8.5+): {excellent}")
    click.echo(f"Good (7.0-8.4): {good}")
    click.echo(f"Needs improvement (<7.0): {needs_improvement}")


@cli.command()
@click.option('--detailed', '-d', is_flag=True, help='Show detailed statistics')
def status(detailed: bool):
    """Show current processing status and statistics."""
    db = Database()
    summary = db.get_summary()
    
    # Header
    click.echo("\n" + "="*50)
    click.echo("SCRIBE PROCESSING STATUS")
    click.echo("="*50)
    
    # Overall stats
    click.echo(f"\nTotal files: {summary['total_files']}")
    click.echo(f"Transcribed: {summary['transcribed']} ({summary['transcribed']/summary['total_files']*100:.1f}%)")
    
    # Translation stats
    click.echo("\nTranslations:")
    for lang in ['en', 'de', 'he']:
        translated = summary.get(f'{lang}_translated', 0)
        percentage = translated / summary['total_files'] * 100 if summary['total_files'] > 0 else 0
        click.echo(f"  {lang.upper()}: {translated} ({percentage:.1f}%)")
    
    # Pending work
    click.echo("\nPending:")
    pending_transcription = db.get_pending_files('transcription')
    click.echo(f"  Transcription: {len(pending_transcription)}")
    
    for lang in ['en', 'de', 'he']:
        pending = db.get_pending_files(f'translation_{lang}')
        click.echo(f"  {lang.upper()} translation: {len(pending)}")
    
    if detailed:
        # Failed files
        click.echo("\nFailed:")
        failed_query = """
            SELECT 
                SUM(CASE WHEN transcription_status = 'failed' THEN 1 ELSE 0 END) as trans_failed,
                SUM(CASE WHEN translation_en_status = 'failed' THEN 1 ELSE 0 END) as en_failed,
                SUM(CASE WHEN translation_de_status = 'failed' THEN 1 ELSE 0 END) as de_failed,
                SUM(CASE WHEN translation_he_status = 'failed' THEN 1 ELSE 0 END) as he_failed
            FROM processing_status
        """
        failed = db.execute_query(failed_query)[0]
        
        click.echo(f"  Transcription: {failed['trans_failed'] or 0}")
        click.echo(f"  EN translation: {failed['en_failed'] or 0}")
        click.echo(f"  DE translation: {failed['de_failed'] or 0}")
        click.echo(f"  HE translation: {failed['he_failed'] or 0}")
        
        # Quality scores
        click.echo("\nAverage Quality Scores:")
        quality_query = """
            SELECT 
                language,
                AVG(score) as avg_score,
                COUNT(*) as count
            FROM quality_evaluations
            GROUP BY language
        """
        quality_results = db.execute_query(quality_query)
        
        for result in quality_results:
            lang = result['language']
            avg = result['avg_score']
            count = result['count']
            if avg:
                click.echo(f"  {lang.upper()}: {avg:.1f}/10 ({count} evaluated)")


@cli.command()
@click.option('--reset-all', is_flag=True, help='Reset all stuck files')
def fix_stuck(reset_all: bool):
    """Fix files stuck in 'in-progress' state.
    
    Resets files that have been processing for too long.
    """
    db = Database()
    
    # Find stuck files (in-progress for >30 minutes)
    stuck_query = """
        SELECT file_id, 
               CASE 
                   WHEN transcription_status = 'in-progress' THEN 'transcription'
                   WHEN translation_en_status = 'in-progress' THEN 'translation_en'
                   WHEN translation_de_status = 'in-progress' THEN 'translation_de'
                   WHEN translation_he_status = 'in-progress' THEN 'translation_he'
               END as stuck_stage
        FROM processing_status
        WHERE transcription_status = 'in-progress'
           OR translation_en_status = 'in-progress'
           OR translation_de_status = 'in-progress'
           OR translation_he_status = 'in-progress'
    """
    
    stuck_files = db.execute_query(stuck_query)
    
    if not stuck_files:
        click.echo("No stuck files found")
        return
    
    click.echo(f"Found {len(stuck_files)} stuck files")
    
    if not reset_all:
        if not click.confirm("Reset these files to 'pending'?"):
            return
    
    # Reset stuck files
    reset_count = 0
    for file_info in stuck_files:
        stage = file_info['stuck_stage']
        db.update_status(file_info['file_id'], stage, 'pending')
        reset_count += 1
    
    click.echo(f"✓ Reset {reset_count} files to pending")


@cli.command()
@click.option('--languages', '-l', default='en,de,he', help='Languages to process (comma-separated)')
@click.option('--transcription-workers', default=10, help='Workers for transcription')
@click.option('--translation-workers', default=8, help='Workers for translation')
@click.option('--evaluate-sample', default=20, help='Sample size for evaluation')
def process(languages: str, transcription_workers: int, translation_workers: int, evaluate_sample: int):
    """Run the full pipeline: scan → transcribe → translate → evaluate.
    
    This is the main command for processing the entire archive.
    """
    # Parse languages
    lang_list = [lang.strip() for lang in languages.split(',')]
    
    # Create configuration
    config = PipelineConfig(
        languages=lang_list,
        transcription_workers=transcription_workers,
        translation_workers=translation_workers,
        evaluation_sample_size=evaluate_sample
    )
    
    click.echo("Starting full pipeline processing...")
    click.echo(f"Languages: {', '.join(lang_list)}")
    click.echo(f"Transcription workers: {transcription_workers}")
    click.echo(f"Translation workers: {translation_workers}")
    click.echo("")
    
    # Run pipeline
    pipeline = Pipeline(config)
    pipeline.run_full_pipeline()
    
    click.echo("\n✓ Pipeline complete!")


@cli.command()
@click.argument('file_id')
@click.argument('language', type=click.Choice(['en', 'de', 'he']))
def check_translation(file_id: str, language: str):
    """Check the quality of a specific translation.
    
    FILE_ID is the unique identifier for the file.
    LANGUAGE is the translation to check.
    """
    output_dir = Path('output') / file_id
    transcript_path = output_dir / f"{file_id}_transcript.txt"
    translation_path = output_dir / f"{file_id}_{language}.txt"
    
    if not transcript_path.exists():
        click.echo(f"Transcript not found: {transcript_path}")
        return
        
    if not translation_path.exists():
        click.echo(f"Translation not found: {translation_path}")
        return
    
    click.echo(f"Evaluating {language.upper()} translation for {file_id}...")
    
    try:
        score, results = evaluate_file(str(transcript_path), str(translation_path))
        
        click.echo(f"\nOverall Score: {score:.1f}/10")
        
        if results and 'component_scores' in results:
            click.echo("\nComponent Scores:")
            for component, value in results['component_scores'].items():
                click.echo(f"  {component}: {value:.1f}/10")
        
        if results and 'suitability' in results:
            click.echo(f"\nSuitability: {results['suitability']}")
            
    except Exception as e:
        click.echo(f"Error evaluating translation: {e}")


@cli.command()
def version():
    """Show version and configuration information."""
    import os
    
    click.echo("Scribe - Historical Interview Preservation System")
    click.echo("Version: 2.0.0")
    click.echo("\nConfiguration:")
    click.echo(f"  Database: {os.getenv('DATABASE_PATH', 'media_tracking.db')}")
    click.echo(f"  Input directory: {os.getenv('INPUT_PATH', 'input/')}")
    click.echo(f"  Output directory: {os.getenv('OUTPUT_PATH', 'output/')}")
    
    # Check API keys
    click.echo("\nAPI Keys:")
    keys = {
        'ElevenLabs': 'ELEVENLABS_API_KEY',
        'DeepL': 'DEEPL_API_KEY',
        'Microsoft Translator': 'MS_TRANSLATOR_KEY',
        'OpenAI': 'OPENAI_API_KEY'
    }
    
    for name, env_var in keys.items():
        if os.getenv(env_var):
            click.echo(f"  {name}: ✓ Configured")
        else:
            click.echo(f"  {name}: ✗ Not configured")


if __name__ == '__main__':
    cli()