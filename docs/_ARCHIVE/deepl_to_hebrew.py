#!/usr/bin/env python3
"""
DeepL English to Hebrew Translation Test
---------------------------------------
Takes an existing DeepL English translation and converts it to Hebrew using OpenAI.
Then evaluates both translations against the original German using GPT-4.5.
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import necessary modules from the scribe project
sys.path.append('.')
from translation import TranslationManager
from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

def evaluate_translation_with_gpt45(
    original_text: str, 
    translation: str, 
    target_language: str,
    language_name: str
) -> Dict[str, Any]:
    """
    Evaluate a translation against the original using GPT-4.5.
    
    Args:
        original_text: The original German text
        translation: The translated text to evaluate
        target_language: The target language code
        language_name: The human-readable language name
        
    Returns:
        Dictionary with evaluation results
    """
    # Create the evaluation prompt
    prompt = f"""You are a professional translator evaluation expert. I will provide you with an original text in German and a translation in {language_name}.

Please evaluate the translation according to the following criteria:
1. Accuracy: How well does the translation convey the original meaning?
2. Fluency: How natural and fluid is the language?
3. Completeness: Does the translation include all the information from the original?
4. Cultural appropriateness: Does the translation respect cultural nuances?

Provide:
- A score from 1-10 for each criterion
- Brief comments explaining your scoring
- An overall assessment and total score (out of 40)

Original German text:
```
{original_text}
```

{language_name} translation to evaluate:
```
{translation}
```
"""
    
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
        return {"evaluation": evaluation}
        
    except Exception as e:
        logger.error(f"GPT-4.5 evaluation error: {e}")
        return {"evaluation": f"Error during evaluation: {str(e)}"}

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Test DeepL English to Hebrew translation pipeline')
    parser.add_argument('--file-id', type=str, required=True, help='File ID to use for translation test')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return
    
    # Load configuration
    config = {
        'database': {
            'path': './media_tracking.db'
        },
        'output_dir': './output',
        'openai': {
            'api_key': openai_api_key
        }
    }
    
    # Initialize managers
    db_manager = DatabaseManager(config['database']['path'])
    file_manager = FileManager(db_manager, config)
    transcription_manager = TranscriptionManager(db_manager, config)
    translation_manager = TranslationManager(db_manager, config)
    
    # Set up manager references
    translation_manager.set_managers(file_manager, transcription_manager)
    
    # Get the file ID from arguments
    file_id = args.file_id
    
    # Load the original German transcript
    transcript_path = file_manager.get_transcript_path(file_id)
    if not os.path.exists(transcript_path):
        logger.error(f"Transcript file not found: {transcript_path}")
        return
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        german_transcript = f.read()
        logger.info(f"Loaded German transcript: {len(german_transcript)} characters")
    
    # Load the existing DeepL English translation
    deepl_en_path = file_manager.get_translation_path(file_id, 'en')
    if not os.path.exists(deepl_en_path):
        logger.error(f"DeepL English translation not found: {deepl_en_path}")
        return
    
    with open(deepl_en_path, 'r', encoding='utf-8') as f:
        deepl_en_text = f.read()
        logger.info(f"Loaded DeepL English translation: {len(deepl_en_text)} characters")
    
    # Translate the DeepL English to Hebrew using OpenAI
    logger.info("Translating DeepL English to Hebrew using OpenAI...")
    hebrew_translation = translation_manager.translate_text(
        text=deepl_en_text,
        target_language='he',
        source_language='en',
        provider='openai'
    )
    
    # Create output directory
    output_dir = Path("./output/translation_tests")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the Hebrew translation
    hebrew_path = output_dir / f"{file_id}_he_deepl_openai.txt"
    with open(hebrew_path, 'w', encoding='utf-8') as f:
        f.write(hebrew_translation)
        logger.info(f"Saved Hebrew translation to: {hebrew_path}")
    
    # Evaluate the DeepL English translation
    logger.info("Evaluating DeepL English translation with GPT-4.5...")
    english_evaluation = evaluate_translation_with_gpt45(
        original_text=german_transcript,
        translation=deepl_en_text,
        target_language='en',
        language_name='English'
    )
    
    # Evaluate the Hebrew translation
    logger.info("Evaluating DeepL+OpenAI Hebrew translation with GPT-4.5...")
    hebrew_evaluation = evaluate_translation_with_gpt45(
        original_text=german_transcript,
        translation=hebrew_translation,
        target_language='he',
        language_name='Hebrew'
    )
    
    # Save the evaluations
    evaluation_path = output_dir / f"{file_id}_evaluations.txt"
    with open(evaluation_path, 'w', encoding='utf-8') as f:
        f.write("===== ENGLISH TRANSLATION EVALUATION =====\n\n")
        f.write(english_evaluation['evaluation'])
        f.write("\n\n===== HEBREW TRANSLATION EVALUATION =====\n\n")
        f.write(hebrew_evaluation['evaluation'])
    
    # Display evaluations
    print("\n===== ENGLISH TRANSLATION EVALUATION =====")
    print(english_evaluation['evaluation'])
    print("\n===== HEBREW TRANSLATION EVALUATION =====")
    print(hebrew_evaluation['evaluation'])
    
    logger.info(f"Evaluations saved to: {evaluation_path}")

if __name__ == "__main__":
    main()
