#!/usr/bin/env python3
"""
Reporter for Media Transcription and Translation Tool
----------------------------------------------------
Handles report generation and provides summaries of processing status.
"""

import os
import logging
import json
# Optional import for YAML report formatting
try:
    import yaml
except ImportError:
    yaml = None
import time
from typing import Dict, Any, Optional, List
import datetime
from pathlib import Path

from db_manager import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


class Reporter:
    """
    Generates reports on processing status for the Media Transcription and Translation Tool.
    
    This class provides methods for:
    - Summarizing processing statistics
    - Generating detailed reports
    - Formatting output for different report types
    """
    
    def __init__(self, db_manager: DatabaseManager, config: Dict[str, Any]):
        """
        Initialize the reporter.
        
        Args:
            db_manager: Database manager instance
            config: Configuration dictionary
        """
        self.db_manager = db_manager
        self.config = config
        
        # Output directory for reports
        self.output_dir = config.get('output_directory', './output')
        self.reports_dir = os.path.join(self.output_dir, 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def display_summary(self) -> None:
        """
        Display a summary of processing statistics to the console.
        """
        stats = self.db_manager.get_summary_statistics()
        
        print("\nSummary Report")
        print("=" * 50)
        
        # Overall statistics
        print(f"Total files: {stats['total_files']}")
        
        # Status counts
        print("\nStatus Summary:")
        for status, count in stats.get('status_counts', {}).items():
            print(f"  {status}: {count}")
        
        # Media type counts
        print("\nMedia Types:")
        for media_type, count in stats.get('media_type_counts', {}).items():
            print(f"  {media_type}: {count}")
        
        # Language distribution
        print("\nLanguage Distribution:")
        if not stats.get('language_counts'):
            print("  No language data available")
        else:
            for language, count in stats.get('language_counts', {}).items():
                if language == 'None' or language == 'unknown':
                    print(f"  unknown: {count}")
                else:
                    print(f"  {language}: {count}")
        
        # Content statistics
        print("\nContent Statistics:")
        
        # Duration statistics
        duration_stats = stats.get('duration_stats', {})
        if duration_stats and duration_stats.get('total_duration'):
            total_hours = duration_stats.get('total_duration', 0) / 3600
            completed_hours = stats.get('completed_duration', 0) / 3600
            print(f"  Total Duration: {total_hours:.2f} hours ({int(total_hours * 60)} minutes)")
            print(f"  Transcribed: {completed_hours:.2f} hours ({stats.get('completed_transcriptions', 0)}/{stats['total_files']} files)")
            if duration_stats.get('avg_duration'):
                print(f"  Average Duration: {duration_stats.get('avg_duration', 0) / 60:.2f} minutes")
            
            # Word counts from actual transcriptions
            word_stats = stats.get('word_count_stats', {})
            if word_stats and word_stats.get('total_words', 0) > 0:
                print(f"  Total Words: {word_stats.get('total_words', 0):,} (from {word_stats.get('file_count', 0)} transcripts)")
                print(f"  Average Words per File: {word_stats.get('avg_words_per_file', 0):,}")
                if 'min_words' in word_stats and 'max_words' in word_stats:
                    print(f"  Words Range: {word_stats.get('min_words', 0):,} - {word_stats.get('max_words', 0):,}")
            else:
                # Fallback to estimate if no actual word count available
                word_count = stats.get('word_count_estimate', 0)
                if word_count > 0:
                    print(f"  Estimated Words: {word_count:,} (based on 150 words/minute)")
            
            # File size statistics
            size_stats = stats.get('size_stats', {})
            if size_stats and size_stats.get('total_size'):
                # Convert bytes to more readable units
                total_gb = size_stats.get('total_size', 0) / (1024**3)
                avg_mb = size_stats.get('avg_size', 0) / (1024**2)
                print(f"  Total Size: {total_gb:.2f} GB")
                print(f"  Average Size: {avg_mb:.2f} MB")
            else:
                print("  No file size data available")
        
        # Stage completion
        print("\nStage Completion:")
        for stage, counts in stats.get('stage_counts', {}).items():
            print(f"  {stage}:")
            for status, count in counts.items():
                print(f"    {status}: {count}")
        
        # Error counts
        print("\nErrors by Stage:")
        if not stats.get('error_counts'):
            print("  No errors reported")
        else:
            for stage, count in stats.get('error_counts', {}).items():
                print(f"  {stage}: {count}")
        
        # Add detailed error analysis if errors exist
        if stats.get('error_counts') and sum(stats.get('error_counts', {}).values()) > 0:
            self.display_error_analysis()
        
        print("\nFor more detailed information, generate a full report using --report option.")
        print("=" * 50)
    
    def analyze_error_patterns(self, recent_only: bool = True, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze error patterns from the database to find common issues
        and correlate them with file attributes.
        
        Args:
            recent_only: If True, only consider errors from the last 'hours'
            hours: Hours to look back for recent errors
            
        Returns:
            Dictionary containing error analysis information
        """
        # Query all errors with file details
        time_filter = ""
        if recent_only:
            # Add time filter for recent errors only
            time_filter = f"AND e.timestamp >= datetime('now', '-{hours} hours')"
            
        query = f"""
        SELECT 
            e.file_id, e.process_stage, e.error_message, e.error_details, e.timestamp,
            m.file_size, m.duration, m.media_type, m.original_path
        FROM 
            errors e
        JOIN 
            media_files m ON e.file_id = m.file_id
        WHERE 
            1=1 {time_filter}
        ORDER BY 
            e.timestamp DESC
        """
        
        errors = self.db_manager.execute_query(query)
        
        if not errors:
            return {"error_count": 0, "patterns": [], "recommendations": [], "time_filter": f"Last {hours} hours" if recent_only else "All time"}
        
        # Group errors by stage and message pattern
        error_groups = {}
        stage_errors = {}
        size_related_errors = {
            "large_files": [],
            "small_files": []
        }
        
        # Define patterns to look for in error messages
        memory_patterns = ["memory", "allocation", "out of memory", "MemoryError"]
        codec_patterns = ["codec", "format", "unsupported"]
        api_limit_patterns = ["quota", "limit", "exceeded", "credit"]
        
        # Analyze each error
        for error in errors:
            stage = error['process_stage']
            message = str(error['error_message']) + " " + str(error['error_details'] or "")
            file_size_mb = error['file_size'] / (1024 * 1024) if error['file_size'] else 0
            
            # Group by stage
            if stage not in stage_errors:
                stage_errors[stage] = []
            stage_errors[stage].append(error)
            
            # Check for memory issues
            if any(pattern in message.lower() for pattern in memory_patterns):
                category = "memory_issues"
            # Check for codec issues
            elif any(pattern in message.lower() for pattern in codec_patterns):
                category = "codec_issues"
            # Check for API limits
            elif any(pattern in message.lower() for pattern in api_limit_patterns):
                category = "api_limits"
            # Default category
            else:
                category = "other_issues"
            
            # Add to appropriate category
            if category not in error_groups:
                error_groups[category] = []
            error_groups[category].append(error)
            
            # Track size-related issues
            if file_size_mb > 500:  # Large files (>500MB)
                size_related_errors["large_files"].append(error)
            else:
                size_related_errors["small_files"].append(error)
        
        # Generate size correlation statistics
        size_correlation = {
            "large_file_errors": len(size_related_errors["large_files"]),
            "small_file_errors": len(size_related_errors["small_files"]),
            "avg_size_failed_files": sum(e['file_size'] for e in errors if e['file_size']) / sum(1 for e in errors if e['file_size']) / (1024 * 1024) if sum(1 for e in errors if e['file_size']) > 0 else 0
        }
        
        # Generate recommendations based on patterns
        recommendations = []
        
        if error_groups.get("memory_issues", []):
            if len(size_related_errors["large_files"]) > len(size_related_errors["small_files"]):
                recommendations.append({
                    "issue": "Memory-related failures in large files",
                    "action": "Use ffmpeg for audio extraction of large files instead of moviepy",
                    "details": f"Found {len(error_groups.get('memory_issues', []))} memory-related errors, mostly in files over 500MB"
                })
        
        if error_groups.get("api_limits", []):
            recommendations.append({
                "issue": "API quota limits reached",
                "action": "Consider upgrading API subscription or implementing batch processing with delays",
                "details": f"Found {len(error_groups.get('api_limits', []))} quota limit errors"
            })
        
        if error_groups.get("codec_issues", []):
            recommendations.append({
                "issue": "Media codec compatibility issues",
                "action": "Pre-convert problematic files to standard formats (e.g., MP4/H.264)",
                "details": f"Found {len(error_groups.get('codec_issues', []))} codec-related errors"
            })
        
        # Return compiled analysis
        return {
            "error_count": len(errors),
            "errors_by_stage": {stage: len(errs) for stage, errs in stage_errors.items()},
            "error_categories": {category: len(errs) for category, errs in error_groups.items()},
            "size_correlation": size_correlation,
            "recent_errors": errors[:10],  # Just include 10 most recent errors with details
            "recommendations": recommendations,
            "time_filter": f"Last {hours} hours" if recent_only else "All time"
        }
    
    def display_error_analysis(self, recent_only: bool = True, hours: int = 24) -> None:
        """
        Display detailed error analysis with actionable recommendations.
        
        Args:
            recent_only: If True, only consider errors from the last 'hours'
            hours: Hours to look back for recent errors
        """
        analysis = self.analyze_error_patterns(recent_only, hours)
        
        if analysis["error_count"] == 0:
            return
        
        print("\n" + "=" * 50)
        print("ERROR ANALYSIS AND RECOMMENDATIONS")
        print("=" * 50)
        
        # Show time filter
        print(f"\nShowing errors from: {analysis['time_filter']}")
        
        # Show error distribution
        print("\nError Distribution by Stage:")
        for stage, count in analysis["errors_by_stage"].items():
            print(f"  {stage}: {count} errors")
        
        # Show error categories
        print("\nError Categories:")
        for category, count in analysis["error_categories"].items():
            print(f"  {category.replace('_', ' ').title()}: {count} errors")
        
        # Show size correlation
        size_corr = analysis["size_correlation"]
        print("\nFile Size Correlation:")
        print(f"  Large Files (>500MB): {size_corr['large_file_errors']} errors")
        print(f"  Small Files: {size_corr['small_file_errors']} errors")
        print(f"  Average Size of Failed Files: {size_corr['avg_size_failed_files']:.2f} MB")
        
        # Show recent error examples
        print("\nRecent Error Examples:")
        for i, error in enumerate(analysis["recent_errors"][:3], 1):
            file_size_mb = error['file_size'] / (1024 * 1024) if error['file_size'] else 0
            print(f"  {i}. File: {os.path.basename(error['original_path'])} ({file_size_mb:.2f} MB)")
            print(f"     Stage: {error['process_stage']}")
            print(f"     Error: {error['error_message']}")
            # Truncate very long error details
            details = error['error_details'] or ""
            if len(details) > 100:
                details = details[:97] + "..."
            print(f"     Details: {details}")
            print(f"     Time: {error['timestamp']}")
            print()
        
        # Show actionable recommendations
        if analysis["recommendations"]:
            print("\nACTIONABLE RECOMMENDATIONS:")
            for i, rec in enumerate(analysis["recommendations"], 1):
                print(f"  {i}. Issue: {rec['issue']}")
                print(f"     Action: {rec['action']}")
                print(f"     Details: {rec['details']}")
                print()
    
    def generate_report(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a detailed processing report.
        
        Args:
            output_file: Path to save the report (optional)
            
        Returns:
            Report data as a dictionary
        """
        # Get summary statistics
        stats = self.db_manager.get_summary_statistics()
        
        # Get files by status
        files_by_status = {}
        for status in ['pending', 'in-progress', 'completed', 'failed']:
            files_by_status[status] = self.db_manager.get_files_by_status(status)
        
        # Get error analysis
        error_analysis = self.analyze_error_patterns()
        
        # Build report data
        report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'summary': stats,
            'error_analysis': error_analysis,
            'files': {
                status: [
                    {
                        'file_id': file['file_id'],
                        'path': file['original_path'],
                        'media_type': file['media_type'],
                        'size': file['file_size'],
                        'duration': file['duration'],
                        'language': file['detected_language'],
                        'attempts': file['attempts'],
                        'started_at': file['started_at'],
                        'completed_at': file['completed_at'],
                        'transcription_status': file['transcription_status'],
                        'translation_en_status': file['translation_en_status'],
                        'translation_he_status': file['translation_he_status']
                    }
                    for file in files
                ]
                for status, files in files_by_status.items()
            }
        }
        
        # Save report if output file is specified
        if output_file:
            try:
                # Determine format based on file extension
                ext = os.path.splitext(output_file)[1].lower()
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
                
                if ext == '.json':
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(report, f, indent=2, default=str)
                elif ext in ['.yml', '.yaml']:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        yaml.dump(report, f, default_flow_style=False)
                else:
                    # Default to text format
                    self._save_text_report(report, output_file)
                
                logger.info(f"Report saved to: {output_file}")
                print(f"Report saved to: {output_file}")
                
            except Exception as e:
                logger.error(f"Error saving report to {output_file}: {e}")
                print(f"Error saving report: {e}")
        
        return report
    
    def _save_text_report(self, report_data: Dict[str, Any], output_file: str) -> None:
        """
        Save a report in human-readable text format.
        
        Args:
            report_data: Report data as a dictionary
            output_file: Path to save the report
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Media Transcription and Translation Tool - Processing Report\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Generated: {report_data['timestamp']}\n\n")
            
            # Summary statistics
            stats = report_data['summary']
            f.write(f"Total files: {stats['total_files']}\n\n")
            
            # Status counts
            f.write("Status Summary:\n")
            for status, count in stats.get('status_counts', {}).items():
                f.write(f"  {status}: {count}\n")
            f.write("\n")
            
            # Media type counts
            f.write("Media Types:\n")
            for media_type, count in stats.get('media_type_counts', {}).items():
                f.write(f"  {media_type}: {count}\n")
            f.write("\n")
            
            # Stage completion
            f.write("Stage Completion:\n")
            for stage, counts in stats.get('stage_counts', {}).items():
                f.write(f"  {stage}:\n")
                for status, count in counts.items():
                    f.write(f"    {status}: {count}\n")
            f.write("\n")
            
            # Error counts
            f.write("Errors by Stage:\n")
            if not stats.get('error_counts'):
                f.write("  No errors reported\n")
            else:
                for stage, count in stats.get('error_counts', {}).items():
                    f.write(f"  {stage}: {count}\n")
            f.write("\n")
            
            # Error analysis
            error_analysis = report_data['error_analysis']
            if error_analysis['error_count'] > 0:
                f.write("Error Analysis:\n")
                f.write(f"  Total Errors: {error_analysis['error_count']}\n")
                f.write("  Error Distribution by Stage:\n")
                for stage, count in error_analysis['errors_by_stage'].items():
                    f.write(f"    {stage}: {count}\n")
                f.write("  Error Categories:\n")
                for category, count in error_analysis['error_categories'].items():
                    f.write(f"    {category.replace('_', ' ').title()}: {count}\n")
                f.write("  File Size Correlation:\n")
                f.write(f"    Large Files (>500MB): {error_analysis['size_correlation']['large_file_errors']} errors\n")
                f.write(f"    Small Files: {error_analysis['size_correlation']['small_file_errors']} errors\n")
                f.write(f"    Average Size of Failed Files: {error_analysis['size_correlation']['avg_size_failed_files']:.2f} MB\n")
                f.write("  Recent Error Examples:\n")
                for i, error in enumerate(error_analysis['recent_errors'][:3], 1):
                    file_size_mb = error['file_size'] / (1024 * 1024) if error['file_size'] else 0
                    f.write(f"    {i}. File: {os.path.basename(error['original_path'])} ({file_size_mb:.2f} MB)\n")
                    f.write(f"       Stage: {error['process_stage']}\n")
                    f.write(f"       Error: {error['error_message']}\n")
                    # Truncate very long error details
                    details = error['error_details'] or ""
                    if len(details) > 100:
                        details = details[:97] + "..."
                    f.write(f"       Details: {details}\n")
                f.write("  Actionable Recommendations:\n")
                for i, rec in enumerate(error_analysis['recommendations'], 1):
                    f.write(f"    {i}. Issue: {rec['issue']}\n")
                    f.write(f"       Action: {rec['action']}\n")
                    f.write(f"       Details: {rec['details']}\n")
            
            # Files by status
            for status, files in report_data['files'].items():
                if files:
                    f.write(f"\n{status.upper()} FILES ({len(files)}):\n")
                    f.write("-" * 80 + "\n")
                    
                    for file in files:
                        f.write(f"ID: {file['file_id']}\n")
                        f.write(f"Path: {file['path']}\n")
                        f.write(f"Type: {file['media_type']}\n")
                        f.write(f"Size: {file['size']} bytes\n")
                        f.write(f"Duration: {file['duration']} seconds\n")
                        f.write(f"Language: {file['language']}\n")
                        f.write(f"Attempts: {file['attempts']}\n")
                        f.write(f"Started: {file['started_at']}\n")
                        f.write(f"Completed: {file['completed_at']}\n")
                        f.write(f"Transcription: {file['transcription_status']}\n")
                        f.write(f"Translation EN: {file['translation_en_status']}\n")
                        f.write(f"Translation HE: {file['translation_he_status']}\n")
                        f.write("-" * 40 + "\n")
                    
                    f.write("\n")
    
    def generate_status_report(self, file_ids: List[str], output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a status report for specific files.
        
        Args:
            file_ids: List of file IDs to include in the report
            output_file: Path to save the report (optional)
            
        Returns:
            Report data as a dictionary
        """
        file_details = []
        
        for file_id in file_ids:
            details = self.db_manager.get_file_status(file_id)
            if details:
                file_details.append(details)
        
        # Build report data
        report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'files': [{
                'file_id': file['file_id'],
                'path': file['original_path'],
                'media_type': file['media_type'],
                'size': file['file_size'],
                'duration': file['duration'],
                'language': file['detected_language'],
                'status': file['status'],
                'attempts': file['attempts'],
                'started_at': file['started_at'],
                'completed_at': file['completed_at'],
                'transcription_status': file['transcription_status'],
                'translation_en_status': file['translation_en_status'],
                'translation_he_status': file['translation_he_status']
            } for file in file_details]
        }
        
        # Save report if output file is specified
        if output_file:
            try:
                # Determine format based on file extension
                ext = os.path.splitext(output_file)[1].lower()
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
                
                if ext == '.json':
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(report, f, indent=2, default=str)
                elif ext in ['.yml', '.yaml']:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        yaml.dump(report, f, default_flow_style=False)
                else:
                    # Default to text format
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write("Status Report\n")
                        f.write("=" * 50 + "\n\n")
                        f.write(f"Generated: {report['timestamp']}\n\n")
                        
                        for file in report['files']:
                            f.write(f"File ID: {file['file_id']}\n")
                            f.write(f"Path: {file['path']}\n")
                            f.write(f"Status: {file['status']}\n")
                            f.write(f"Media Type: {file['media_type']}\n")
                            f.write(f"Language: {file['language']}\n")
                            f.write(f"Attempts: {file['attempts']}\n")
                            f.write(f"Transcription: {file['transcription_status']}\n")
                            f.write(f"Translation EN: {file['translation_en_status']}\n")
                            f.write(f"Translation HE: {file['translation_he_status']}\n")
                            f.write("-" * 40 + "\n\n")
                
                logger.info(f"Status report saved to: {output_file}")
                print(f"Status report saved to: {output_file}")
                
            except Exception as e:
                logger.error(f"Error saving status report to {output_file}: {e}")
                print(f"Error saving status report: {e}")
        
        return report
