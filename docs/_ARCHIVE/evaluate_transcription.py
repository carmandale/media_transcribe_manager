#!/usr/bin/env python3
"""
Transcription Evaluation Tool
-----------------------------
This script recursively scans a directory for audio and video files,
calculates their total duration, and generates a report with estimated
transcription times and costs.
"""

import os
import sys
import argparse
import time
import re
from pathlib import Path
from dotenv import load_dotenv
import csv
import datetime
from tqdm import tqdm
from moviepy.editor import VideoFileClip, AudioFileClip
import json

# Load environment variables
load_dotenv()

# File format extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma', '.aiff'}
ALL_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS.union(AUDIO_EXTENSIONS)

# Rate constants for estimation
TRANSCRIPTION_RATE_FACTOR = 0.5  # Assumes API processes 2x faster than realtime

# ElevenLabs pricing tiers (as of April 2025)
PRICING_TIERS = {
    'creator': {
        'monthly_cost': 22.00,
        'included_hours': 63,
        'overage_cost_per_hour': 0.35
    },
    'pro': {
        'monthly_cost': 99.00,
        'included_hours': 320,
        'overage_cost_per_hour': 0.31
    },
    'scale': {
        'monthly_cost': 330.00,
        'included_hours': 1220,
        'overage_cost_per_hour': 0.27
    },
    'business': {
        'monthly_cost': 1320.00,
        'included_hours': 6000,
        'overage_cost_per_hour': 0.22
    }
}

TARGET_LANGUAGES = ["auto", "eng", "deu", "heb"]  # Auto (original) + target languages

def sanitize_filename(filename):
    """
    Sanitize a filename by removing or replacing problematic characters.
    
    Args:
        filename (str): The original filename
        
    Returns:
        str: A sanitized version of the filename
    """
    # Replace problematic characters with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)
    
    # Replace spaces with underscores for consistency
    sanitized = sanitized.replace(' ', '_')
    
    # Remove leading/trailing periods and spaces
    sanitized = sanitized.strip('. ')
    
    return sanitized

def format_time(seconds):
    """
    Format seconds into a human-readable time string.
    
    Args:
        seconds (float): Time in seconds
        
    Returns:
        str: Formatted time string (HH:MM:SS)
    """
    if seconds is None:
        return "Unknown"
    
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def calculate_media_duration(file_path):
    """
    Calculate the duration of a media file.
    
    Args:
        file_path (Path): Path to the media file
        
    Returns:
        tuple: (duration in seconds or None if error, error message if any)
    """
    try:
        suffix = file_path.suffix.lower()
        
        if suffix in VIDEO_EXTENSIONS:
            clip = VideoFileClip(str(file_path))
            duration = clip.duration
            clip.close()
            return duration, None
        elif suffix in AUDIO_EXTENSIONS:
            clip = AudioFileClip(str(file_path))
            duration = clip.duration
            clip.close()
            return duration, None
        else:
            return None, "Unsupported file format"
    except Exception as e:
        error_msg = f"Error calculating duration: {str(e)}"
        print(f"Error calculating duration for {file_path}: {e}")
        return None, error_msg

def scan_directory(directory_path):
    """
    Recursively scan a directory for media files.
    
    Args:
        directory_path (str): Path to the directory to scan
        
    Returns:
        dict: Dictionary containing information about the found media files
    """
    directory = Path(directory_path)
    
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory")
        return None
    
    print(f"Scanning directory: {directory}")
    
    results = {
        'audio_files': [],
        'video_files': [],
        'problematic_files': [],
        'total_files': 0,
        'total_duration': 0,
        'total_size_bytes': 0,
        'file_details': []
    }
    
    # Create a progress bar that will be updated as we find files
    progress = tqdm(desc="Scanning for media files", unit="files")
    
    # Recursively walk through the directory
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in ALL_MEDIA_EXTENSIONS:
            # Get file info
            file_size = file_path.stat().st_size
            file_type = 'video' if file_path.suffix.lower() in VIDEO_EXTENSIONS else 'audio'
            
            # Calculate duration
            duration, error_msg = calculate_media_duration(file_path)
            
            # Track file in the appropriate category
            if file_type == 'video':
                results['video_files'].append(file_path)
            else:
                results['audio_files'].append(file_path)
            
            # Add to totals
            results['total_files'] += 1
            if duration is not None:
                results['total_duration'] += duration
            results['total_size_bytes'] += file_size
            
            # Store detailed information
            relative_path = file_path.relative_to(directory)
            sanitized_name = sanitize_filename(str(relative_path))
            
            file_info = {
                'path': str(file_path),
                'relative_path': str(relative_path),
                'sanitized_path': sanitized_name,
                'type': file_type,
                'size_bytes': file_size,
                'size_mb': file_size / (1024 * 1024),
                'duration': duration,
                'duration_formatted': format_time(duration),
                'status': 'ok' if duration is not None else 'error',
                'error': error_msg if error_msg else None
            }
            
            results['file_details'].append(file_info)
            
            # Track problematic files
            if duration is None:
                results['problematic_files'].append(file_info)
            
            # Update progress
            progress.update(1)
    
    progress.close()
    return results

def generate_estimate(scan_results, pricing_tier='creator'):
    """
    Generate transcription time and cost estimates from scan results.
    
    Args:
        scan_results (dict): Results from the scan_directory function
        pricing_tier (str): ElevenLabs pricing tier to use for cost calculation
                          (creator, pro, scale, business)
        
    Returns:
        dict: Dictionary containing estimation data
    """
    if not scan_results:
        return None
    
    # Validate pricing tier
    pricing_tier = pricing_tier.lower()
    if pricing_tier not in PRICING_TIERS:
        print(f"Warning: Unknown pricing tier '{pricing_tier}'. Defaulting to 'creator'.")
        pricing_tier = 'creator'
    
    tier_data = PRICING_TIERS[pricing_tier]
    
    total_duration = scan_results['total_duration']
    problematic_count = len(scan_results['problematic_files'])
    
    # Calculate hours
    total_hours = total_duration / 3600
    
    # Base estimates (for single language)
    estimated_time_seconds = total_duration * TRANSCRIPTION_RATE_FACTOR
    
    # Calculate cost based on the pricing tier
    if total_hours <= tier_data['included_hours']:
        # If within included hours, just pay the monthly subscription
        estimated_cost = tier_data['monthly_cost']
        overage_hours = 0
    else:
        # Base cost plus overage
        overage_hours = total_hours - tier_data['included_hours']
        overage_cost = overage_hours * tier_data['overage_cost_per_hour']
        estimated_cost = tier_data['monthly_cost'] + overage_cost
    
    # Multi-language estimates
    languages_count = len(TARGET_LANGUAGES)
    multi_lang_time = estimated_time_seconds * languages_count
    multi_lang_cost = estimated_cost * languages_count
    
    return {
        'total_duration_seconds': total_duration,
        'total_duration_formatted': format_time(total_duration),
        'total_hours': total_hours,
        'problematic_files_count': problematic_count,
        'pricing_tier': pricing_tier,
        'pricing_details': tier_data,
        'single_language_estimate': {
            'time_seconds': estimated_time_seconds,
            'time_formatted': format_time(estimated_time_seconds),
            'cost_usd': estimated_cost,
            'overage_hours': overage_hours
        },
        'multi_language_estimate': {
            'languages': TARGET_LANGUAGES,
            'time_seconds': multi_lang_time,
            'time_formatted': format_time(multi_lang_time),
            'cost_usd': multi_lang_cost
        }
    }

def generate_markdown_report(scan_results, estimates, output_path):
    """
    Generate a markdown report from the scan results and estimates.
    
    Args:
        scan_results (dict): Results from the scan_directory function
        estimates (dict): Results from the generate_estimate function
        output_path (str): Path to save the markdown report
        
    Returns:
        str: Path to the generated report
    """
    output_file = Path(output_path) / "transcription_estimate.md"
    
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Title and summary
        f.write("# Transcription Estimation Report\n\n")
        f.write(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Overall statistics
        f.write("## Summary\n\n")
        f.write(f"- **Total Files Found**: {scan_results['total_files']}\n")
        f.write(f"  - Video Files: {len(scan_results['video_files'])}\n")
        f.write(f"  - Audio Files: {len(scan_results['audio_files'])}\n")
        f.write(f"  - **Problematic Files**: {estimates['problematic_files_count']} (unable to determine duration)\n")
        f.write(f"- **Total Media Duration**: {estimates['total_duration_formatted']} (excludes problematic files)\n")
        f.write(f"- **Total Hours**: {estimates['total_hours']:.2f} hours\n")
        f.write(f"- **Total Size**: {scan_results['total_size_bytes'] / (1024 * 1024 * 1024):.2f} GB\n\n")
        
        # Estimates
        f.write("## Transcription Estimates\n\n")
        f.write(f"Using **{estimates['pricing_tier'].capitalize()} tier** pricing (${estimates['pricing_details']['monthly_cost']:.2f}/month, ")
        f.write(f"{estimates['pricing_details']['included_hours']} hours included, ")
        f.write(f"${estimates['pricing_details']['overage_cost_per_hour']:.2f}/hour overage)\n\n")
        
        f.write("### Single Language (Original)\n\n")
        f.write(f"- **Estimated Processing Time**: {estimates['single_language_estimate']['time_formatted']}\n")
        f.write(f"- **Monthly Subscription Cost**: ${estimates['pricing_details']['monthly_cost']:.2f}\n")
        
        if estimates['single_language_estimate']['overage_hours'] > 0:
            f.write(f"- **Overage Hours**: {estimates['single_language_estimate']['overage_hours']:.2f} hours\n")
            f.write(f"- **Overage Cost**: ${estimates['single_language_estimate']['overage_hours'] * estimates['pricing_details']['overage_cost_per_hour']:.2f}\n")
        
        f.write(f"- **Total Estimated Cost**: ${estimates['single_language_estimate']['cost_usd']:.2f}\n\n")
        
        f.write("### Multi-Language (All Target Languages)\n\n")
        f.write(f"- **Target Languages**: {', '.join(estimates['multi_language_estimate']['languages'])}\n")
        f.write(f"- **Estimated Processing Time**: {estimates['multi_language_estimate']['time_formatted']}\n")
        f.write(f"- **Total Estimated Cost**: ${estimates['multi_language_estimate']['cost_usd']:.2f}\n\n")
        
        # File details table
        f.write("## File Details\n\n")
        f.write("| # | Filename | Type | Duration | Size (MB) | Status | Sanitized Name |\n")
        f.write("|---|----------|------|----------|-----------|--------|---------------|\n")
        
        for i, file_info in enumerate(scan_results['file_details'], 1):
            status = "✓" if file_info['status'] == 'ok' else "❌ Failed to open"
            f.write(f"| {i} | {file_info['relative_path']} | {file_info['type']} | ")
            f.write(f"{file_info['duration_formatted']} | {file_info['size_mb']:.2f} | ")
            f.write(f"{status} | {file_info['sanitized_path']} |\n")
        
        # Problematic files section
        if estimates['problematic_files_count'] > 0:
            f.write("\n## Problematic Files\n\n")
            f.write("The following files could not be properly analyzed. They may be corrupted or have invalid formats:\n\n")
            f.write("| # | Filename | Type | Size (MB) | Error |\n")
            f.write("|---|----------|------|-----------|-------|\n")
            
            for i, file_info in enumerate(scan_results['problematic_files'], 1):
                error_msg = file_info['error'] if file_info['error'] else "Unknown error"
                # Truncate error message if too long
                if len(error_msg) > 80:
                    error_msg = error_msg[:77] + "..."
                
                f.write(f"| {i} | {file_info['relative_path']} | {file_info['type']} | ")
                f.write(f"{file_info['size_mb']:.2f} | {error_msg} |\n")
    
    print(f"Markdown report saved to: {output_file}")
    return str(output_file)

def generate_csv_report(scan_results, estimates, output_path):
    """
    Generate a CSV report from the scan results and estimates.
    
    Args:
        scan_results (dict): Results from the scan_directory function
        estimates (dict): Results from the generate_estimate function
        output_path (str): Path to save the CSV report
        
    Returns:
        str: Path to the generated report
    """
    output_file = Path(output_path) / "transcription_estimate.csv"
    problematic_file = Path(output_path) / "problematic_files.csv"
    
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate main CSV report
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        
        # Write header
        writer.writerow([
            'Filename', 'Type', 'Duration', 'Size (MB)', 'Status', 'Sanitized Name'
        ])
        
        # Write file details
        for file_info in scan_results['file_details']:
            status = "OK" if file_info['status'] == 'ok' else "ERROR"
            writer.writerow([
                file_info['relative_path'],
                file_info['type'],
                file_info['duration_formatted'],
                f"{file_info['size_mb']:.2f}",
                status,
                file_info['sanitized_path']
            ])
    
    # Generate problematic files report if any exist
    if estimates['problematic_files_count'] > 0:
        with open(problematic_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            
            # Write header
            writer.writerow([
                'Filename', 'Type', 'Size (MB)', 'Error'
            ])
            
            # Write problematic file details
            for file_info in scan_results['problematic_files']:
                error_msg = file_info['error'] if file_info['error'] else "Unknown error"
                writer.writerow([
                    file_info['relative_path'],
                    file_info['type'],
                    f"{file_info['size_mb']:.2f}",
                    error_msg
                ])
        print(f"Problematic files report saved to: {problematic_file}")
    
    print(f"CSV report saved to: {output_file}")
    return str(output_file)

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Evaluate a directory for transcription by scanning for media files and estimating processing time"
    )
    
    # Required arguments
    parser.add_argument(
        "directory", 
        help="Path to the directory to scan recursively for media files"
    )
    
    # Optional arguments
    parser.add_argument(
        "-o", "--output", 
        default="./reports",
        help="Directory to save the evaluation reports (default: ./reports)"
    )
    
    parser.add_argument(
        "-t", "--tier",
        choices=["creator", "pro", "scale", "business"],
        default="creator",
        help="ElevenLabs pricing tier to use for cost estimates (default: creator)"
    )
    
    args = parser.parse_args()
    
    # Scan the directory
    print(f"Starting evaluation of directory: {args.directory}")
    scan_results = scan_directory(args.directory)
    
    if not scan_results or scan_results['total_files'] == 0:
        print("No media files found. Exiting.")
        sys.exit(1)
    
    # Generate estimates
    estimates = generate_estimate(scan_results, args.tier)
    
    # Display summary
    print(f"\nFound {scan_results['total_files']} media files:")
    print(f"- {len(scan_results['video_files'])} video files")
    print(f"- {len(scan_results['audio_files'])} audio files")
    print(f"- {len(scan_results['problematic_files'])} problematic files (unable to determine duration)")
    print(f"Total duration: {format_time(scan_results['total_duration'])} (excluding problematic files)")
    
    # Display estimates
    print("\n----- Transcription Estimates -----")
    print(f"Using {args.tier.capitalize()} tier pricing:")
    print(f"- ${estimates['pricing_details']['monthly_cost']:.2f}/month")
    print(f"- {estimates['pricing_details']['included_hours']} hours included")
    print(f"- ${estimates['pricing_details']['overage_cost_per_hour']:.2f}/hour overage")
    
    print(f"\nSingle language processing time: {estimates['single_language_estimate']['time_formatted']}")
    
    if estimates['single_language_estimate']['overage_hours'] > 0:
        print(f"Overage hours: {estimates['single_language_estimate']['overage_hours']:.2f}")
        print(f"Overage cost: ${estimates['single_language_estimate']['overage_hours'] * estimates['pricing_details']['overage_cost_per_hour']:.2f}")
    
    print(f"Single language estimated cost: ${estimates['single_language_estimate']['cost_usd']:.2f}")
    print(f"Multi-language processing time: {estimates['multi_language_estimate']['time_formatted']}")
    print(f"Multi-language estimated cost: ${estimates['multi_language_estimate']['cost_usd']:.2f}")
    
    # Generate reports
    markdown_report = generate_markdown_report(scan_results, estimates, args.output)
    csv_report = generate_csv_report(scan_results, estimates, args.output)
    
    print("\nEvaluation complete! Reports generated:")
    print(f"- Markdown report: {markdown_report}")
    print(f"- CSV report: {csv_report}")
    
    if estimates['problematic_files_count'] > 0:
        print(f"- Problematic files report: {Path(args.output) / 'problematic_files.csv'}")
        print(f"\nNOTE: {estimates['problematic_files_count']} files could not be analyzed. Check the reports for details.")

if __name__ == "__main__":
    main()
