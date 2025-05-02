#!/usr/bin/env python3
"""
Translation Test Script
-----------------------
Tests and compares translations from different providers using a blind LLM evaluation:
1. DeepL (text-based translation from transcript)
2. OpenAI (text-based translation from transcript) 
3. OpenAI Audio API (direct audio-to-text translation)

The script uses GPT-4.5 to evaluate translations without knowing their source.
"""

import os
import sys
import logging
import argparse
import random
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv

# Import from the project
from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager
from translation import TranslationManager

# OpenAI specific imports
from openai import OpenAI
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def split_audio_file(audio_path: str, max_size_mb: int = 24) -> List[str]:
    """
    Split a large audio file into multiple smaller segments using ffmpeg.
    
    Args:
        audio_path: Path to the audio file to split
        max_size_mb: Maximum size in MB for each segment (default: 24MB to stay under the 25MB limit)
        
    Returns:
        List of paths to the split audio segments
    """
    # Check if file exists
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return []
    
    # Get file size in MB
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    
    # If file is already under the size limit, return it as is
    if file_size_mb <= max_size_mb:
        logger.info(f"Audio file is already under the size limit ({file_size_mb:.2f}MB)")
        return [audio_path]
    
    # Create temporary directory for segments
    temp_dir = tempfile.mkdtemp(prefix="audio_segments_")
    logger.info(f"Created temporary directory for audio segments: {temp_dir}")
    
    # Get audio duration using ffmpeg
    ffprobe_cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]
    
    try:
        duration = float(subprocess.check_output(ffprobe_cmd).decode('utf-8').strip())
        logger.info(f"Audio duration: {duration:.2f} seconds")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting audio duration: {e}")
        shutil.rmtree(temp_dir)
        return []
    
    # Calculate number of segments needed
    num_segments = int(file_size_mb / max_size_mb) + 1
    segment_duration = duration / num_segments
    
    logger.info(f"Splitting audio file into {num_segments} segments of ~{segment_duration:.2f} seconds each")
    
    # Split audio file into segments
    segment_paths = []
    
    for i in range(num_segments):
        start_time = i * segment_duration
        segment_path = os.path.join(temp_dir, f"segment_{i:03d}.mp3")
        
        # For the last segment, ensure we go to the end of the file
        if i == num_segments - 1:
            duration_arg = []  # No duration argument for the last segment
        else:
            duration_arg = ['-t', str(segment_duration)]
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-v', 'warning',
            '-i', audio_path,
            '-ss', str(start_time),
            *duration_arg,
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-ar', '44100',
            '-y',
            segment_path
        ]
        
        logger.info(f"Running ffmpeg command: {' '.join(ffmpeg_cmd)}")
        
        try:
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            segment_paths.append(segment_path)
            logger.info(f"Created segment {i+1}/{num_segments}: {segment_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creating segment {i+1}: {e}")
            # Continue with other segments
    
    return segment_paths

def translate_audio_with_openai(audio_file_path: str, target_language: str) -> str:
    """
    Translate audio directly to target language using OpenAI's Audio API.
    Handles large files by splitting them into smaller segments.
    
    Args:
        audio_file_path: Path to the audio file
        target_language: Target language code
        
    Returns:
        Translated text
    """
    # Check if file exists
    if not os.path.exists(audio_file_path):
        logger.error(f"Audio file not found: {audio_file_path}")
        return "ERROR: Audio file not found"
    
    # Get file size in MB
    file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
    logger.info(f"Audio file size: {file_size_mb:.2f}MB")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Split the file if it's too large
    if file_size_mb > 25:
        logger.info(f"Audio file exceeds 25MB limit. Splitting into smaller segments...")
        segment_paths = split_audio_file(audio_file_path)
        
        if not segment_paths:
            return "ERROR: Failed to split audio file"
        
        # Process each segment
        translations = []
        
        for i, segment_path in enumerate(segment_paths):
            logger.info(f"Processing segment {i+1}/{len(segment_paths)}: {segment_path}")
            
            try:
                # Open the audio segment
                with open(segment_path, "rb") as audio_file:
                    # Make API request to OpenAI
                    response = client.audio.translations.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )
                    
                    # Add to translations
                    translations.append(response)
                    logger.info(f"Successfully translated segment {i+1}/{len(segment_paths)}")
                    
            except Exception as e:
                logger.error(f"OpenAI Audio API error for segment {i+1}: {e}")
                translations.append(f"[Error in segment {i+1}: {str(e)}]")
        
        # Clean up temporary files
        try:
            temp_dir = os.path.dirname(segment_paths[0])
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary files: {e}")
        
        # Combine all translations
        full_translation = " ".join(translations)
        return full_translation
        
    else:
        # Process the file directly if it's under the size limit
        try:
            # Open the audio file
            with open(audio_file_path, "rb") as audio_file:
                # Make API request to OpenAI
                response = client.audio.translations.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                
                # Return the translated text
                return response
                
        except Exception as e:
            logger.error(f"OpenAI Audio API error: {e}")
            return f"ERROR: OpenAI Audio API error - {str(e)}"

def evaluate_translations_with_llm(original_text: str, translations: Dict[str, str], target_language: str) -> Dict[str, Any]:
    """
    Use GPT-4.5 to evaluate translations in a blind manner.
    
    Args:
        original_text: The original source text
        translations: Dictionary mapping translation method to translated text
        target_language: The target language of the translations
        
    Returns:
        Dictionary with evaluation results
    """
    # Create a blind test by assigning anonymous labels
    methods = list(translations.keys())
    random.shuffle(methods)
    
    blind_map = {f"Translation {chr(65+i)}": method for i, method in enumerate(methods)}
    reverse_map = {method: label for label, method in blind_map.items()}
    
    blind_translations = {label: translations[method] for label, method in blind_map.items()}
    
    # Create the evaluation prompt
    language_names = {
        'en': 'English',
        'de': 'German',
        'he': 'Hebrew'
    }
    target_lang_name = language_names.get(target_language, target_language)
    
    prompt = f"""You are a professional translator evaluation expert. I will provide you with an original text in German and several translations in {target_lang_name}.

Please evaluate each translation according to the following criteria:
1. Accuracy: How well does the translation convey the original meaning?
2. Fluency: How natural and fluid is the language?
3. Completeness: Does the translation include all the information from the original?
4. Cultural appropriateness: Does the translation respect cultural nuances?

For each translation, provide:
- A score from 1-10 for each criterion
- Brief comments explaining your scoring
- An overall assessment and total score (out of 40)
- A ranking of the translations from best to worst

Original German text:
```
{original_text}
```

{target_lang_name} translations to evaluate:

"""
    
    for label, text in blind_translations.items():
        prompt += f"\n{label}:\n```\n{text}\n```\n"
    
    # Call the GPT-4.5 API
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-4.5-preview",  # Using GPT-4.5 as specified
            messages=[
                {"role": "system", "content": "You are a professional translation evaluator with expertise in German and multiple target languages."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        evaluation = response.choices[0].message.content
        
        # Return both the evaluation and the mapping
        return {
            "evaluation": evaluation,
            "blind_map": blind_map,
            "reverse_map": reverse_map
        }
        
    except Exception as e:
        logger.error(f"GPT-4.5 evaluation error: {e}")
        return {
            "evaluation": f"Error during evaluation: {str(e)}",
            "blind_map": blind_map,
            "reverse_map": reverse_map
        }

def main():
    parser = argparse.ArgumentParser(description='Test different translation providers')
    parser.add_argument('--file-id', type=str, required=True, help='File ID to use for translation test')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    # Load configuration
    config = {
        'database': {
            'path': './media_tracking.db'
        },
        'output_dir': './output',
        'subtitles': {
            'generate_for_translations': True
        }
    }
    
    # Initialize database manager and file manager
    db_manager = DatabaseManager(config['database']['path'])
    file_manager = FileManager(db_manager, config)
    transcription_manager = TranscriptionManager(db_manager, config)
    translation_manager = TranslationManager(db_manager, config)
    
    # Set reference to other managers (only TranslationManager has this method)
    translation_manager.set_managers(file_manager, transcription_manager)
    
    # Get file details
    file_id = args.file_id
    file_details = db_manager.get_file_status(file_id)
    
    if not file_details:
        logger.error(f"File not found: {file_id}")
        return
    
    # Get paths using the file_manager methods
    transcript_path = file_manager.get_transcript_path(file_id)
    audio_path = file_manager.get_audio_path(file_id)
    deepl_en_path = file_manager.get_translation_path(file_id, 'en')
    
    # Check if paths exist
    if not os.path.exists(transcript_path):
        logger.error(f"Transcript file not found: {transcript_path}")
        return
    
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return
    
    # Get original German transcript
    with open(transcript_path, 'r', encoding='utf-8') as f:
        german_transcript = f.read()
    
    # Get existing DeepL English translation if available
    deepl_en_text = None
    
    if os.path.exists(deepl_en_path):
        with open(deepl_en_path, 'r', encoding='utf-8') as f:
            deepl_en_text = f.read()
            logger.info(f"Found existing DeepL English translation: {deepl_en_path}")
    else:
        # Generate DeepL English translation
        logger.info("Generating DeepL English translation...")
        deepl_en_text = translation_manager.translate_text(
            text=german_transcript,
            target_language='en',
            source_language='de',
            provider='deepl'
        )
    
    print("\n" + "="*80)
    print(f"EVALUATING TRANSLATIONS FOR FILE: {file_id}")
    print("="*80)
    
    # Evaluate the DeepL English translation
    print("\n" + "="*80)
    print("EVALUATING ENGLISH TRANSLATION...")
    print("="*80)
    
    english_evaluation = evaluate_translations_with_llm(
        original_text=german_transcript,
        translations={"DeepL (text)": deepl_en_text},
        target_language='en'
    )
    
    # Generate Hebrew translation from the DeepL English text
    print("\n" + "="*80)
    print("GENERATING HEBREW TRANSLATION FROM DEEPL ENGLISH...")
    print("="*80)
    
    deepl_openai_he = translation_manager.translate_text(
        text=deepl_en_text,
        target_language='he',
        source_language='en',
        provider='openai'
    )
    
    # Evaluate the Hebrew translation
    print("\n" + "="*80)
    print("EVALUATING HEBREW TRANSLATION...")
    print("="*80)
    
    hebrew_evaluation = evaluate_translations_with_llm(
        original_text=german_transcript,
        translations={"DeepL+OpenAI (text)": deepl_openai_he},
        target_language='he'
    )
    
    # Create output directory for evaluations
    output_dir = Path(config.get('output_dir', './output'))
    results_dir = output_dir / "translation_comparison"
    results_dir.mkdir(exist_ok=True)
    
    # Save raw translations for reference
    with open(results_dir / f"{file_id}_raw_translations.json", 'w', encoding='utf-8') as f:
        json.dump({
            "original_german": german_transcript,
            "english_translations": {"DeepL (text)": deepl_en_text},
            "hebrew_translations": {"DeepL+OpenAI (text)": deepl_openai_he}
        }, f, ensure_ascii=False, indent=2)
    
    # Save evaluations
    with open(results_dir / f"{file_id}_evaluations.json", 'w', encoding='utf-8') as f:
        json.dump({
            "english": english_evaluation,
            "hebrew": hebrew_evaluation
        }, f, ensure_ascii=False, indent=2)
    
    # Display the evaluations
    print("\n" + "="*80)
    print("ENGLISH TRANSLATION EVALUATION")
    print("="*80)
    print(english_evaluation["evaluation"])
    
    print("\n" + "="*80)
    print("HEBREW TRANSLATION EVALUATION")
    print("="*80)
    print(hebrew_evaluation["evaluation"])
    
    print(f"\nDetailed results saved to: {results_dir / f'{file_id}_evaluations.json'}")
    print(f"Raw translations saved to: {results_dir / f'{file_id}_raw_translations.json'}")

if __name__ == "__main__":
    main()
