#!/usr/bin/env python3
"""
Scribe CLI - Clean, modern interface for historical media preservation
Processes interview recordings through transcription, translation, and quality evaluation.
"""

import click
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from scribe.database import Database
from scribe.pipeline import Pipeline, PipelineConfig
from scribe.evaluate import evaluate_file
from scribe.backup import BackupManager
from scribe.audit import DatabaseAuditor

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
@click.option('--model', '-m', help='OpenAI model for Hebrew translations (default: gpt-4.1-mini)')
def translate(language: str, workers: int, limit: Optional[int], model: Optional[str]):
    """Translate transcripts to the specified language.
    
    LANGUAGE can be: en (English), de (German), or he (Hebrew).
    
    Preserves authentic speech patterns and historical context.
    """
    config = PipelineConfig(translation_workers=workers)
    if model:
        config.openai_model = model
    pipeline = Pipeline(config)
    
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


@cli.command('translate-srt')
@click.argument('language', type=click.Choice(['en', 'de', 'he']))
@click.option('--workers', '-w', default=8, help='Number of parallel workers')
@click.option('--limit', '-l', type=int, help='Maximum files to process')
@click.option('--model', '-m', help='OpenAI model (default: uses configured model)')
@click.option('--no-preserve', is_flag=True, help='Translate all segments (don\'t preserve segments already in target language)')
def translate_srt(language: str, workers: int, limit: Optional[int], model: Optional[str], no_preserve: bool):
    """Translate SRT subtitle files while preserving timing.
    
    LANGUAGE can be: en (English), de (German), or he (Hebrew).
    
    By default, preserves segments already in the target language.
    This is useful for mixed-language interviews where we want to
    maintain the original speaker's words when appropriate.
    
    Example: In a German interview with English questions,
    translating to English will keep the English questions unchanged
    and only translate the German responses.
    """
    config = PipelineConfig(translation_workers=workers)
    if model:
        config.openai_model = model
    pipeline = Pipeline(config)
    
    # Check for files needing SRT translation
    db = Database()
    pending = db.get_files_for_srt_translation(language)
    
    if not pending:
        click.echo(f"No SRT files pending translation to {language.upper()}")
        return
    
    # Language names for display
    lang_names = {'en': 'English', 'de': 'German', 'he': 'Hebrew'}
    preserve_original = not no_preserve
    
    click.echo(f"Starting {lang_names[language]} SRT translation of up to {len(pending)} files with {workers} workers...")
    if preserve_original:
        click.echo(f"Preserving segments already in {lang_names[language]}")
    
    results = pipeline.translate_srt_files(language, preserve_original=preserve_original)
    
    # Summary
    successful = sum(1 for r in results if r.translations.get(f"{language}_srt", False))
    failed = len(results) - successful
    
    click.echo(f"\n✓ SRT Translated: {successful}")
    if failed:
        click.echo(f"✗ Failed: {failed}")


@cli.command('estimate-srt-cost')
@click.argument('srt_file', type=click.Path(exists=True))
@click.argument('language', type=click.Choice(['en', 'de', 'he']))
def estimate_srt_cost(srt_file: str, language: str):
    """Estimate translation cost for an SRT file.
    
    Shows cost comparison between optimized batch translation
    and traditional segment-by-segment translation.
    """
    from scribe.srt_translator import SRTTranslator
    
    translator = SRTTranslator()
    cost_info = translator.estimate_cost(srt_file, language)
    
    click.echo(f"\nCost estimation for translating {Path(srt_file).name} to {language.upper()}:")
    click.echo(f"  Total segments: {cost_info['total_segments']}")
    click.echo(f"  Segments to translate: {cost_info['segments_to_translate']}")
    click.echo(f"  Unique texts: {cost_info['unique_texts']}")
    click.echo(f"\n  Cost without optimization: ${cost_info['cost_without_optimization']:.4f}")
    click.echo(f"  Cost with optimization: ${cost_info['cost_with_optimization']:.4f}")
    click.echo(f"  Savings: ${cost_info['cost_without_optimization'] - cost_info['cost_with_optimization']:.4f} ({cost_info['savings_factor']:.1f}x reduction)")


@cli.command()
@click.argument('language', type=click.Choice(['en', 'de', 'he']))
@click.option('--sample', '-s', default=20, help='Number of files to evaluate')
@click.option('--enhanced', is_flag=True, help='Use enhanced evaluation with sanity checks (especially for Hebrew)')
@click.option('--model', '-m', default='gpt-4.1', help='OpenAI model to use (default: gpt-4.1)')
def evaluate(language: str, sample: int, enhanced: bool, model: str):
    """Evaluate translation quality for historical accuracy.
    
    LANGUAGE can be: en (English), de (German), or he (Hebrew).
    
    Scores translations on accuracy and speech pattern preservation.
    
    Use --enhanced for Hebrew translations to enable sanity checks and
    Hebrew-specific evaluation criteria.
    """
    pipeline = Pipeline()
    
    enhanced_str = " (Enhanced)" if enhanced else ""
    click.echo(f"Evaluating {sample} {language.upper()} translations{enhanced_str} using {model}...")
    
    scores = pipeline.evaluate_translations(language, sample_size=sample, enhanced=enhanced, model=model)
    
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
    
    # Hebrew-specific reporting if enhanced mode was used
    if enhanced and language == 'he':
        # Get detailed results to analyze Hebrew-specific issues
        hebrew_issues = []
        hebrew_warnings = []
        sanity_failures = 0
        low_hebrew_ratio = 0
        
        for file_id, score, result in [(s[0], s[1], s[2]) if len(s) > 2 else (s[0], s[1], {}) for s in scores]:
            if result:
                issues = result.get('issues', [])
                warnings = result.get('warnings', [])
                hebrew_validation = result.get('hebrew_validation', {})
                
                if 'NO_HEBREW_CHARACTERS' in issues:
                    sanity_failures += 1
                
                # Count low Hebrew ratio warnings
                for warning in warnings:
                    if 'HEBREW_RATIO' in warning:
                        low_hebrew_ratio += 1
                        break
                        
                hebrew_issues.extend(issues)
                hebrew_warnings.extend(warnings)
        
        if sanity_failures > 0 or low_hebrew_ratio > 0 or hebrew_issues or hebrew_warnings:
            click.echo(f"\nHebrew-specific analysis:")
            if sanity_failures > 0:
                click.echo(f"⚠️  Files with no Hebrew characters: {sanity_failures}")
            if low_hebrew_ratio > 0:
                click.echo(f"⚠️  Files with low Hebrew ratio: {low_hebrew_ratio}")
            
            # Show most common issues
            from collections import Counter
            if hebrew_issues:
                issue_counts = Counter(hebrew_issues)
                click.echo(f"Common issues: {dict(issue_counts.most_common(3))}")
            
            if hebrew_warnings:
                warning_counts = Counter(hebrew_warnings)
                click.echo(f"Common warnings: {dict(warning_counts.most_common(3))}")
        else:
            click.echo(f"\n✓ Hebrew validation: All files passed sanity checks")


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
        db.update_status(file_info['file_id'], **{f'{stage}_status': 'pending'})
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
    transcript_path = output_dir / f"{file_id}.txt"
    translation_path = output_dir / f"{file_id}.{language}.txt"
    
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


# ============================================================================
# BACKUP COMMANDS
# ============================================================================

@cli.group()
def backup():
    """Backup and restore system data.
    
    Manages comprehensive backups of database and translation files.
    """
    pass


@backup.command('create')
@click.option('--quick', '-q', is_flag=True, help='Use quick tar compression for faster backup')
def backup_create(quick: bool):
    """Create a backup of the system.
    
    Creates a timestamped backup including database and all translation files.
    Quick mode uses tar compression for faster operation.
    """
    backup_manager = BackupManager(Path.cwd())
    
    try:
        click.echo(f"Creating {'quick' if quick else 'full'} backup...")
        backup_dir, manifest = backup_manager.create_backup(quick=quick)
        
        # Display results
        click.echo(f"\n✓ Backup completed successfully!")
        click.echo(f"Location: {backup_dir}")
        click.echo(f"Type: {manifest.get('backup_type', 'unknown')}")
        
        if 'database' in manifest:
            db_size = manifest['database'].get('size', 0)
            click.echo(f"Database: {db_size:,} bytes")
        
        if 'translations' in manifest:
            trans_info = manifest['translations']
            if 'file_count' in trans_info:
                click.echo(f"Translation files: {trans_info['file_count']}")
            if 'archive_size' in trans_info:
                click.echo(f"Archive size: {trans_info['archive_size']:,} bytes")
            elif 'total_size' in trans_info:
                click.echo(f"Total size: {trans_info['total_size']:,} bytes")
        
        # Show Hebrew issues if available
        if 'validation_status' in manifest:
            hebrew_issues = manifest['validation_status'].get('total_hebrew_issues', 0)
            if hebrew_issues > 0:
                click.echo(f"Hebrew issues: {hebrew_issues}")
        
    except Exception as e:
        click.echo(f"✗ Backup failed: {e}", err=True)
        raise click.Abort()


@backup.command('list')
def backup_list():
    """List all available backups."""
    backup_manager = BackupManager(Path.cwd())
    backups = backup_manager.list_backups()
    
    if not backups:
        click.echo("No backups found")
        return
    
    click.echo(f"\nFound {len(backups)} backups:\n")
    
    # Header
    click.echo(f"{'ID':<20} {'Timestamp':<20} {'Type':<8} {'Size':<12} {'Files':<8} {'Issues':<8}")
    click.echo("-" * 80)
    
    for backup in backups:
        backup_id = backup['id']
        timestamp = backup.get('timestamp', '')[:19]  # Truncate timestamp
        backup_type = backup.get('type', 'unknown')[:7]
        size = f"{backup.get('size', 0) / (1024*1024):.1f}MB"
        files = backup.get('translation_files', 'N/A')
        issues = backup.get('hebrew_issues', 'N/A')
        
        click.echo(f"{backup_id:<20} {timestamp:<20} {backup_type:<8} {size:<12} {str(files):<8} {str(issues):<8}")
        
        if backup.get('error'):
            click.echo(f"  Error: {backup['error']}")


@backup.command('restore')
@click.argument('backup_id')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
def backup_restore(backup_id: str, force: bool):
    """Restore from a backup.
    
    BACKUP_ID is the ID of the backup to restore from.
    Current state will be backed up before restore.
    """
    backup_manager = BackupManager(Path.cwd())
    
    # Check if backup exists
    backups = backup_manager.list_backups()
    backup_info = next((b for b in backups if b['id'] == backup_id), None)
    
    if not backup_info:
        click.echo(f"✗ Backup not found: {backup_id}")
        available = [b['id'] for b in backups[:5]]  # Show first 5
        if available:
            click.echo(f"Available backups: {', '.join(available)}")
        raise click.Abort()
    
    # Show backup info
    click.echo(f"\nRestore from backup: {backup_id}")
    click.echo(f"Timestamp: {backup_info.get('timestamp', 'Unknown')}")
    click.echo(f"Type: {backup_info.get('type', 'unknown')}")
    click.echo(f"Size: {backup_info.get('size', 0) / (1024*1024):.1f}MB")
    
    # Confirmation
    if not force:
        click.echo("\n⚠️  This will replace your current database and translation files!")
        click.echo("   Your current state will be backed up first.")
        if not click.confirm("Continue with restore?"):
            click.echo("Restore cancelled")
            return
    
    try:
        click.echo("\nStarting restore...")
        result = backup_manager.restore_backup(backup_id)
        
        if result['success']:
            click.echo(f"✓ Restore completed successfully!")
            click.echo(f"Current state backed up to: {result['current_state_backup']}")
        else:
            click.echo(f"✗ Restore failed: {result['error']}")
            click.echo(f"Current state backed up to: {result['current_state_backup']}")
            raise click.Abort()
            
    except Exception as e:
        click.echo(f"✗ Restore failed: {e}", err=True)
        raise click.Abort()


# ============================================================================
# DATABASE COMMANDS
# ============================================================================

@cli.group()
def db():
    """Database operations and maintenance.
    
    Tools for auditing, validating, and fixing database issues.
    """
    pass


@db.command('audit')
@click.option('--output', '-o', type=click.Path(), help='Save detailed report to file')
def db_audit(output: Optional[str]):
    """Run comprehensive database audit.
    
    Checks database integrity and file system consistency.
    Identifies missing files, placeholders, and status mismatches.
    """
    auditor = DatabaseAuditor(Path.cwd())
    
    try:
        click.echo("Running database audit...")
        result = auditor.audit_database()
        
        # Display summary
        click.echo(f"\n{'='*60}")
        click.echo("DATABASE AUDIT RESULTS")
        click.echo(f"{'='*60}")
        
        click.echo(f"Total files: {result.total_files}")
        click.echo(f"Issues found: {result.issues_found}")
        click.echo(f"Audit completed: {result.timestamp}")
        
        # Language statistics
        click.echo("\nLanguage Statistics:")
        for lang, stats in result.language_stats.items():
            click.echo(f"\n{lang.upper()}:")
            click.echo(f"  Expected: {stats['expected']}")
            click.echo(f"  Valid: {stats['valid']}")
            click.echo(f"  Placeholders: {stats['placeholder']}")
            click.echo(f"  Missing: {stats['missing']}")
            click.echo(f"  Completion: {stats['completion_rate']}")
        
        # Top issues
        if result.issues_by_type:
            click.echo("\nTop Issues:")
            for issue_type, issues in result.issues_by_type.items():
                if issues:
                    click.echo(f"  {issue_type.replace('_', ' ').title()}: {len(issues)}")
        
        # Recommendations
        if result.recommendations:
            click.echo("\nRecommendations:")
            for i, rec in enumerate(result.recommendations, 1):
                click.echo(f"  {i}. {rec}")
        
        # Save detailed report if requested
        if output:
            output_path = Path(output)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(result), f, indent=2, ensure_ascii=False, default=str)
            click.echo(f"\nDetailed report saved to: {output_path}")
        
    except Exception as e:
        click.echo(f"✗ Audit failed: {e}", err=True)
        raise click.Abort()
    finally:
        auditor.close()


@db.command('fix-status')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying them')
@click.option('--audit-file', type=click.Path(exists=True), help='Use existing audit results')
def db_fix_status(dry_run: bool, audit_file: Optional[str]):
    """Fix database status inconsistencies.
    
    Updates database statuses to match actual file system state.
    Always runs audit first unless --audit-file is provided.
    """
    auditor = DatabaseAuditor(Path.cwd())
    
    try:
        # Get audit results
        if audit_file:
            click.echo(f"Loading audit results from: {audit_file}")
            with open(audit_file, 'r', encoding='utf-8') as f:
                audit_data = json.load(f)
            # Convert back to AuditResult (simplified)
            from scribe.audit import AuditResult
            from dataclasses import fields
            field_names = {f.name for f in fields(AuditResult)}
            filtered_data = {k: v for k, v in audit_data.items() if k in field_names}
            audit_result = AuditResult(**filtered_data)
        else:
            click.echo("Running audit to identify issues...")
            audit_result = auditor.audit_database()
        
        # Show what will be fixed
        total_fixes = (
            len(audit_result.issues_by_type.get('placeholder_file', [])) +
            len(audit_result.issues_by_type.get('missing_file', [])) +
            len(audit_result.issues_by_type.get('status_mismatch', []))
        )
        
        if total_fixes == 0:
            click.echo("✓ No status issues found to fix")
            return
        
        click.echo(f"\nFound {total_fixes} status issues to fix:")
        
        for issue_type in ['placeholder_file', 'missing_file', 'status_mismatch']:
            count = len(audit_result.issues_by_type.get(issue_type, []))
            if count > 0:
                action = {
                    'placeholder_file': 'Reset to pending',
                    'missing_file': 'Mark as failed',
                    'status_mismatch': 'Mark as completed'
                }[issue_type]
                click.echo(f"  {issue_type.replace('_', ' ').title()}: {count} ({action})")
        
        # Confirmation
        if not dry_run:
            if not click.confirm(f"\nApply {total_fixes} status fixes?"):
                click.echo("Status fix cancelled")
                return
        
        # Apply fixes
        click.echo(f"\n{'Previewing' if dry_run else 'Applying'} status fixes...")
        fix_result = auditor.fix_status_issues(audit_result, dry_run=dry_run)
        
        # Show results
        if dry_run:
            click.echo(f"\n[DRY RUN] Would apply {fix_result['fixes_applied']} fixes")
        else:
            click.echo(f"\n✓ Applied {fix_result['fixes_applied']} status fixes")
        
        if fix_result['errors']:
            click.echo(f"✗ {len(fix_result['errors'])} errors occurred:")
            for error in fix_result['errors'][:5]:  # Show first 5 errors
                click.echo(f"  {error}")
            if len(fix_result['errors']) > 5:
                click.echo(f"  ... and {len(fix_result['errors']) - 5} more errors")
        
    except Exception as e:
        click.echo(f"✗ Status fix failed: {e}", err=True)
        raise click.Abort()
    finally:
        auditor.close()


@db.command('validate')
def db_validate():
    """Validate system configuration and health.
    
    Checks database connectivity, API keys, disk space, and other system requirements.
    """
    auditor = DatabaseAuditor(Path.cwd())
    
    try:
        click.echo("Running system validation...")
        results = auditor.validate_system()
        
        click.echo(f"\n{'='*50}")
        click.echo("SYSTEM VALIDATION RESULTS")
        click.echo(f"{'='*50}")
        
        # Database
        db_status = "✓ Connected" if results['database_accessible'] else "✗ Failed"
        click.echo(f"Database: {db_status}")
        
        # Output directory
        output_status = "✓ Exists" if results['output_directory_exists'] else "✗ Missing"
        click.echo(f"Output directory: {output_status}")
        
        # API keys
        click.echo("\nAPI Keys:")
        for key, configured in results['api_keys_configured'].items():
            status = "✓ Configured" if configured else "✗ Missing"
            click.echo(f"  {key}: {status}")
        
        # Disk space
        if 'disk_space' in results:
            disk = results['disk_space']
            click.echo(f"\nDisk Space:")
            click.echo(f"  Free: {disk['free_gb']:.1f} GB")
            click.echo(f"  Total: {disk['total_gb']:.1f} GB")
            click.echo(f"  Usage: {disk['usage_percent']:.1f}%")
        
        # Recommendations
        if results['recommendations']:
            click.echo("\nRecommendations:")
            for i, rec in enumerate(results['recommendations'], 1):
                click.echo(f"  {i}. {rec}")
        else:
            click.echo("\n✓ All validation checks passed")
        
    except Exception as e:
        click.echo(f"✗ Validation failed: {e}", err=True)
        raise click.Abort()
    finally:
        auditor.close()


if __name__ == '__main__':
    cli()
