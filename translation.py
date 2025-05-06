#!/usr/bin/env python3
"""
Translation Manager for Media Transcription and Translation Tool
---------------------------------------------------------------
Handles all translation operations including:
- Text translation between languages
- Subtitle file creation for target languages
- Management of different translation providers (DeepL, Google, Microsoft, OpenAI)
"""

import os
import re
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
try:
    import requests
except ImportError:
    requests = None
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *args, **kwargs: None

# Import translation libraries if available
try:
    import deepl
except ImportError:
    deepl = None
    
try:
    from google.cloud import translate_v2 as google_translate
except ImportError:
    google_translate = None

try:
    import openai
except ImportError:
    openai = None

try:
    from langdetect import detect
except ImportError:
    detect = None

from db_manager import DatabaseManager
from file_manager import FileManager
from transcription import TranscriptionManager

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class TranslationManager:
    """
    Manages all translation operations for the Media Transcription and Translation Tool.
    
    This class provides methods for:
    - Translating text between languages
    - Creating subtitle files in target languages
    - Managing different translation providers
    """
    
    def __init__(self, db_manager: DatabaseManager, config: Dict[str, Any]):
        """
        Initialize the translation manager.
        
        Args:
            db_manager: Database manager instance
            config: Configuration dictionary
        """
        self.db_manager = db_manager
        self.config = config
        
        # Initialize translation providers based on available API keys and configuration
        self.providers = {}
        self.initialize_providers()
        
        # Load Hebrew glossary
        self.glossary = self._load_hebrew_glossary()
        
        # References to other managers
        self.file_manager = None
        self.transcription_manager = None
    
    def set_managers(self, file_manager: FileManager, transcription_manager: TranscriptionManager) -> None:
        """
        Set references to other managers.
        
        Args:
            file_manager: FileManager instance
            transcription_manager: TranscriptionManager instance
        """
        self.file_manager = file_manager
        self.transcription_manager = transcription_manager
    
    def initialize_providers(self) -> None:
        """
        Initialize translation providers based on configuration and available libraries.
        """
        # Initialize DeepL translator if API key is available
        deepl_api_key = self.config.get('deepl', {}).get('api_key') or os.getenv("DEEPL_API_KEY")
        logger.info(f"DeepL API key available: {bool(deepl_api_key)}")
        logger.info(f"DeepL module available: {bool(deepl)}")
        
        if deepl_api_key and deepl:
            try:
                logger.info(f"Initializing DeepL translator with API key: {deepl_api_key[:5]}...")
                self.providers['deepl'] = deepl.Translator(deepl_api_key)
                logger.info("DeepL translation provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize DeepL translator: {e}")
        else:
            if not deepl_api_key:
                logger.error("DeepL API key not found in config or environment")
            if not deepl:
                logger.error("DeepL module not available (import failed)")
        
        # Initialize Google Cloud Translation if credentials are available
        google_creds = self.config.get('google_translate', {}).get('credentials_file')
        if google_creds and google_translate and os.path.exists(google_creds):
            try:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_creds
                self.providers['google'] = google_translate.Client()
                logger.info("Google Cloud Translation provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Google Cloud Translation: {e}")
        
        # Initialize Microsoft Translator if API key is available
        ms_api_key = self.config.get('microsoft_translator', {}).get('api_key') or os.getenv("MS_TRANSLATOR_KEY")
        ms_location = (
            self.config.get('microsoft_translator', {}).get('location')
            or os.getenv("MS_TRANSLATOR_LOCATION")
            or 'global'
        )
        if ms_api_key:
            # Clean up location (remove trailing comments or whitespace)
            if ms_location:
                ms_location = ms_location.split()[0].strip()
            # Microsoft Translator is implemented using direct REST API calls
            self.providers['microsoft'] = {
                'api_key': ms_api_key,
                'location': ms_location
            }
            logger.info("Microsoft Translator provider initialized")
        
        # Initialize OpenAI Translator if API key is available
        openai_api_key = self.config.get('openai', {}).get('api_key') or os.getenv("OPENAI_API_KEY")
        if openai_api_key and openai:
            try:
                logger.info(f"Initializing OpenAI translator with API key: {openai_api_key[:5]}...")
                # Store the API key for later use
                openai.api_key = openai_api_key
                self.providers['openai'] = True  # Just mark that the provider is available
                logger.info("OpenAI translation provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI translator: {e}")
        else:
            if not openai_api_key:
                logger.error("OpenAI API key not found in config or environment")
            if not openai:
                logger.error("OpenAI module not available (import failed)")
        
        # Set the default provider based on availability
        if 'deepl' in self.providers:
            self.default_provider = 'deepl'
        elif 'google' in self.providers:
            self.default_provider = 'google'
        elif 'microsoft' in self.providers:
            self.default_provider = 'microsoft'
        elif 'openai' in self.providers:
            self.default_provider = 'openai'
        else:
            self.default_provider = None
            logger.warning("No translation providers available")
    
    def normalize_language_code(self, language_code: str, provider: str) -> str:
        """
        Normalize language code for specific translation provider.
        
        Args:
            language_code: Original language code
            provider: Translation provider
            
        Returns:
            Normalized language code for the specified provider
        """
        # Map of common language codes to provider-specific codes
        provider_mappings = {
            'deepl': {
                # Target language codes
                'en': 'EN-US',  # Updated to use EN-US instead of deprecated EN
                'de': 'DE',
                'fr': 'FR',
                'es': 'ES',
                'it': 'IT',
                'nl': 'NL',
                'pl': 'PL',
                'pt': 'PT',
                'ru': 'RU',
                'ja': 'JA',
                'zh': 'ZH',
                'he': 'HE',  # Hebrew
                'eng': 'EN-US',  # Updated to use EN-US instead of deprecated EN
                'ger': 'DE',
                'deu': 'DE',
                'fra': 'FR',
                'jpn': 'JA'
            },
            'deepl_source': {  # Special mapping for DeepL source languages
                'en': 'EN',
                'de': 'DE',
                'fr': 'FR',
                'es': 'ES',
                'it': 'IT',
                'nl': 'NL',
                'pl': 'PL',
                'pt': 'PT',
                'ru': 'RU',
                'ja': 'JA',
                'zh': 'ZH',
                'eng': 'EN',  # Map 'eng' to 'EN' for DeepL source
                'ger': 'DE',
                'deu': 'DE',
                'fra': 'FR',
                'jpn': 'JA'
            },
            'google': {
                'eng': 'en',
                'ger': 'de',
                'deu': 'de',
                'fra': 'fr',
                'jpn': 'ja',
                'chi': 'zh',
                'zho': 'zh'
            },
            'microsoft': {
                'eng': 'en',
                'ger': 'de',
                'deu': 'de',
                'fra': 'fr',
                'jpn': 'ja',
                'chi': 'zh-Hans',
                'zho': 'zh-Hans'
            },
            'openai': {
                'eng': 'en',
                'ger': 'de',
                'deu': 'de',
                'fra': 'fr',
                'jpn': 'ja',
                'chi': 'zh',
                'zho': 'zh'
            }
        }
        
        # Convert to lowercase for case-insensitive matching
        code = language_code.lower()
        
        # Get mapping for the specified provider
        mapping = provider_mappings.get(provider, {})
        
        # Return normalized code if available, otherwise return original
        return mapping.get(code, language_code)
    
    def is_same_language(self, lang1: str, lang2: str) -> bool:
        """
        Check if two language codes refer to the same language.
        
        Args:
            lang1: First language code
            lang2: Second language code
            
        Returns:
            True if languages are the same, False otherwise
        """
        # Normalize language codes to lowercase
        lang1 = lang1.lower() if lang1 else ''
        lang2 = lang2.lower() if lang2 else ''
        
        # Map of language codes to standardized codes
        lang_map = {
            'en': ['en', 'eng', 'english'],
            'de': ['de', 'deu', 'ger', 'german'],
            'he': ['he', 'heb', 'hebrew']
        }
        
        # Get standardized codes
        std_lang1 = lang1
        std_lang2 = lang2
        
        for std_lang, codes in lang_map.items():
            if lang1 in codes:
                std_lang1 = std_lang
            if lang2 in codes:
                std_lang2 = std_lang
                
        return std_lang1 == std_lang2
    
    def translate_text(self, text: str, target_language: str, 
                       source_language: Optional[str] = None,
                       provider: Optional[str] = None,
                       formality: str = 'default') -> Optional[str]:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code (optional)
            provider: Translation provider (optional)
            formality: Formality level ('default', 'more', 'less')
            
        Returns:
            Translated text or None if unsuccessful
        """
        if not text:
            logger.warning("Empty text provided for translation")
            return None
        
        # Prepare for Hebrew polish stage; placeholder logic disabled for now
        glossary_enabled = False
        placeholder_map = {}
        
        provider = provider or self.default_provider
        
        # Determine provider-specific chunk limit and split if text exceeds it
        chunk_limit = 2500 if provider == 'microsoft' else 4500
        if provider in {'microsoft', 'google'} and len(text) > chunk_limit:
            chunks = self._split_text_into_chunks(text, chunk_limit)
            translated_chunks = []
            import time
            norm_source_lang = None
            if source_language:
                norm_source_lang = self.normalize_language_code(
                    source_language,
                    provider if provider in {'microsoft', 'google'} else None,
                )
            for chunk in chunks:
                translated = None

                if provider == 'microsoft':
                    # First try Microsoft
                    translated = self._translate_with_microsoft(
                        text=chunk,
                        target_language=target_language,
                        source_language=None,  # let API auto-detect
                    )
                    # Fallback to Google if Microsoft fails and Google is configured
                    if translated is None and 'google' in self.providers:
                        logger.warning("Microsoft failed for chunk, retrying with Google")
                        google_res = self.providers['google'].translate(
                            values=chunk,
                            target_language=target_language,
                            source_language=norm_source_lang,
                        )
                        translated = (
                            google_res.get('translatedText')
                            if isinstance(google_res, dict)
                            else google_res
                        )
                else:  # provider == 'google'
                    google_res = self.providers['google'].translate(
                        values=chunk,
                        target_language=target_language,
                        source_language=norm_source_lang,
                    )
                    translated = (
                        google_res.get('translatedText')
                        if isinstance(google_res, dict)
                        else google_res
                    )

                if not translated:
                    logger.error("Chunk translation failed; aborting full translation")
                    return None

                translated_chunks.append(translated)
                time.sleep(0.2)

            out_text = "\n\n".join(translated_chunks)
            # Polish Hebrew output if needed
            if target_language.lower() in ['he', 'heb', 'hebrew'] and openai:
                polished = self._polish_hebrew_with_gpt(text, out_text)
                if polished:
                    out_text = polished
            return out_text
        
        # DeepL doesn't support Hebrew as a target language
        # We'll handle Hebrew translations as a special case
        if target_language.lower() in ['he', 'heb', 'hebrew'] and provider == 'deepl':
            logger.info(f"DeepL doesn't support Hebrew as a target language. Using DeepL to translate to English first.")
            
            # Translate to English first
            english_text = self.translate_text(
                text=text,
                target_language='en',
                source_language=source_language,
                provider='deepl',
                formality=formality
            )
            
            # Mark the English text as Hebrew
            if english_text:
                return f"[HEBREW TRANSLATION] {english_text}"
            else:
                return None
        
        # Normalize language codes
        norm_target_lang = self.normalize_language_code(target_language, provider)
        
        # For source language, use a special mapping for DeepL
        if provider == 'deepl' and source_language:
            norm_source_lang = self.normalize_language_code(source_language, 'deepl_source')
        else:
            norm_source_lang = self.normalize_language_code(source_language, provider) if source_language else None
        
        try:
            # Handle based on provider
            if provider == 'deepl':
                # Convert formality setting to DeepL format
                deepl_formality = None
                if formality == 'more':
                    deepl_formality = 'prefer_more'
                elif formality == 'less':
                    deepl_formality = 'prefer_less'
                
                result = self.providers['deepl'].translate_text(
                    text=text,
                    target_lang=norm_target_lang,
                    source_lang=norm_source_lang,
                    formality=deepl_formality
                )
                out = result.text
                if target_language.lower() in ['he', 'heb', 'hebrew'] and openai:
                    polished = self._polish_hebrew_with_gpt(text, out)
                    if polished:
                        out = polished
                return out
                
            elif provider == 'google':
                result = self.providers['google'].translate(
                    values=text,
                    target_language=norm_target_lang,
                    source_language=norm_source_lang
                )
                out = result['translatedText'] if isinstance(result, dict) else result['translatedText'][0]
                if target_language.lower() in ['he', 'heb', 'hebrew'] and openai:
                    polished = self._polish_hebrew_with_gpt(text, out)
                    if polished:
                        out = polished
                return out
                
            elif provider == 'microsoft':
                out = self._translate_with_microsoft(
                    text=text,
                    target_language=norm_target_lang,
                    source_language=None,  # let API auto-detect
                )
                if target_language.lower() in ['he', 'heb', 'hebrew'] and openai:
                    polished = self._polish_hebrew_with_gpt(text, out)
                    if polished:
                        out = polished
                return out
            
            elif provider == 'openai':
                if len(text) > 90000:
                    chunks = self._split_text_into_chunks(text, max_chars=45000)
                    results = [self._translate_with_openai(c, target_language) for c in chunks]
                    return "\n\n".join(filter(None, results))
                out = self._translate_with_openai(
                    text=text,
                    target_language=norm_target_lang,
                    source_language=norm_source_lang
                )
                if target_language.lower() in ['he', 'heb', 'hebrew'] and openai:
                    polished = self._polish_hebrew_with_gpt(text, out)
                    if polished:
                        out = polished
                return out
        
        except Exception as e:
            logger.error(f"Translation error with provider {provider}: {e}")
            return None
    
    def _translate_with_microsoft(self, text: str, target_language: str, 
                                 source_language: Optional[str] = None) -> Optional[str]:
        """
        Translate text using Microsoft Translator API.
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code (optional)
            
        Returns:
            Translated text or None if translation failed
        """
        if 'microsoft' not in self.providers:
            logger.error("Microsoft Translator not initialized")
            return None
        
        try:
            api_key = self.providers['microsoft']['api_key']
            location = self.providers['microsoft']['location']
            
            endpoint = "https://api.cognitive.microsofttranslator.com/translate"
            
            # Construct request headers
            headers = {
                'Ocp-Apim-Subscription-Key': api_key,
                'Ocp-Apim-Subscription-Region': location,
                'Content-type': 'application/json'
            }
            
            # Construct request parameters
            params = {
                'api-version': '3.0',
                'to': target_language
            }
            
            if source_language:
                params['from'] = source_language
            
            # Construct request body
            body = [{
                'text': text
            }]
            
            # Make request
            response = requests.post(endpoint, headers=headers, params=params, json=body)
            if response.status_code != 200:
                logger.error(
                    "Microsoft Translator HTTP %s: %s",
                    response.status_code,
                    response.text[:500],  # cap log length
                )
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            if result and len(result) > 0 and 'translations' in result[0]:
                return result[0]['translations'][0]['text']
            
            return None
            
        except Exception as e:
            logger.error(f"Microsoft Translator API error: {e}")
            return None
    
    def _translate_with_openai(self, text: str, target_language: str, source_language: Optional[str] = None) -> Optional[str]:
        """
        Translate text using OpenAI API via a single-shot JSON-based workflow with automatic fallback.
        Ensures only target-language output; no words from any other language except proper nouns.
        """
        if 'openai' not in self.providers:
            logger.error("OpenAI Translator not initialized")
            return None

        # Map language codes to human-readable names
        language_names = {
            'en': 'English', 'de': 'German', 'he': 'Hebrew',
            'fr': 'French', 'es': 'Spanish', 'it': 'Italian',
            'nl': 'Dutch', 'pl': 'Polish', 'pt': 'Portuguese',
            'ru': 'Russian', 'ja': 'Japanese', 'zh': 'Chinese'
        }
        target_lang_name = language_names.get(target_language.lower(), target_language)

        # Single consolidated system instruction
        system_msg = (
            f"You are a professional translator. "
            f"Translate any incoming text to {target_lang_name} only. "
            "No words from any other language may appear except immutable proper nouns "
            "(people, place, organisation names). "
            "Retain paragraph and line breaks and speaker labels. "
            "Return strict JSON with keys \"translation\" (string) and \"has_foreign\" (boolean)."
        )

        def call_model(model_name: str, user_text: str) -> str:
            resp = openai.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_text}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            return resp.choices[0].message.content.strip()

        try:
            # Primary pass
            content = call_model(self.PRIMARY_MODEL, text)
            obj = json.loads(content)
            translation = obj.get("translation", "").strip()
            has_foreign = obj.get("has_foreign", True)
        except Exception as e:
            logger.warning(f"Primary JSON translate failed: {e}")
            # Fallback to mini model
            try:
                content = call_model(self.FALLBACK_MODEL, text)
                obj = json.loads(content)
                translation = obj.get("translation", "").strip()
                has_foreign = obj.get("has_foreign", False)
            except Exception as e2:
                logger.error(f"Fallback JSON translate failed: {e2}")
                return translation or None

        # Automatic retry if flagged
        if has_foreign:
            try:
                content = call_model(self.FALLBACK_MODEL, translation)
                obj = json.loads(content)
                translation = obj.get("translation", "").strip()
                has_foreign = obj.get("has_foreign", False)
            except Exception as e:
                logger.error(f"Second fallback failed: {e}")

        # Final regex lint for untranslated fragments
        if re.search(r"[äöüßÄÖÜ]", translation):
            raise ValueError("Untranslated fragment detected")

        return translation

    # Model selection for translation passes
    PRIMARY_MODEL = "gpt-4.1"
    FALLBACK_MODEL = "gpt-4.1-mini"

    def translate_file(self, file_id: str, target_language: str, 
                      provider: Optional[str] = None, force: bool = False) -> bool:
        """
        Translate a file's transcription to target language.
        
        Args:
            file_id: Unique ID of the file
            target_language: Target language code
            provider: Translation provider (optional)
            force: Whether to force reprocessing of a failed translation
            
        Returns:
            True if successful, False otherwise
        """
        # Check if managers are set
        if not self.file_manager:
            logger.error("File manager not set in translation manager")
            return False
        
        # Get file details from database
        file_details = self.db_manager.get_file_status(file_id)
        if not file_details:
            logger.error(f"File not found in database: {file_id}")
            return False
        
        # Check if transcription is completed
        if file_details.get('transcription_status') != 'completed':
            logger.error(f"Transcription not completed for file {file_id}")
            self.db_manager.log_error(
                file_id=file_id,
                process_stage=f'translation_{target_language}',
                error_message="Transcription not completed",
                error_details=f"Transcription status: {file_details.get('transcription_status')}"
            )
            return False
        
        # Check translation status field
        status_field = f"translation_{target_language}_status"
        
        # Skip if already translated unless force flag is set
        if not force and file_details.get(status_field) == 'completed':
            logger.info(f"File already translated to {target_language}: {file_id}")
            return True
        
        # Get transcript text
        transcript_text = None
        
        # First try using transcription_manager if available
        if self.transcription_manager:
            transcript_text = self.transcription_manager.get_transcript_text(file_id)
        
        # If transcription_manager not available or didn't return text, try reading file directly
        if not transcript_text and self.file_manager:
            transcript_path = self.file_manager.get_transcript_path(file_id)
            if os.path.exists(transcript_path):
                try:
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        transcript_text = f.read()
                except Exception as e:
                    logger.error(f"Error reading transcript file {transcript_path}: {e}")
        
        if not transcript_text:
            logger.error(f"Transcript text not found for {file_id}")
            self.db_manager.log_error(
                file_id=file_id,
                process_stage=f'translation_{target_language}',
                error_message="Transcript text not found",
                error_details=f"File ID: {file_id}"
            )
            return False
        
        # Get source language from file details
        source_language = file_details.get('detected_language')
        
        # Get translation output path
        translation_path = self.file_manager.get_translation_path(file_id, target_language)
        
        # Update status to in-progress
        try:
            status_update = {
                status_field: 'in-progress'
            }
            self.db_manager.update_status(file_id=file_id, status='in-progress', **status_update)
        except Exception as e:
            logger.warning(f"Could not update status field {status_field}: {e}")
            # Continue with default status fields
        
        try:
            logger.info(f"Translating file {file_id} from {source_language} to {target_language}")
            
            # If langdetect is available, translate paragraph-by-paragraph to avoid re‑translating English text
            if detect and target_language.lower() == 'en':
                translated_text = self._translate_mixed_text_to_target(
                    transcript_text,
                    target_language,
                    provider=provider,
                    formality=self.config.get('deepl', {}).get('formality', 'default'),
                    source_language=source_language,
                )
            else:
                # Translate the text as a single block
                translated_text = self.translate_text(
                    text=transcript_text,
                    target_language=target_language,
                    source_language=source_language,
                    provider=provider,
                    formality=self.config.get('deepl', {}).get('formality', 'default')
                )
            
            # Do not retry the same call with identical parameters to avoid recursion loop
            # If translation failed, translated_text will remain None and be handled below
            
            if not translated_text:
                logger.error(f"Translation failed for {file_id}")
                
                self.db_manager.log_error(
                    file_id=file_id,
                    process_stage=f'translation_{target_language}',
                    error_message="Translation failed",
                    error_details=f"Provider: {provider or self.default_provider}"
                )
                
                status_update = {
                    status_field: 'failed'
                }
                self.db_manager.update_status(file_id=file_id, status='failed', **status_update)
                
                return False
            
            # Save translation to file
            os.makedirs(os.path.dirname(translation_path), exist_ok=True)
            with open(translation_path, 'w', encoding='utf-8') as f:
                f.write(translated_text)
            
            logger.info(f"Translation saved to: {translation_path}")
            
            # Generate subtitle for the translation if enabled in config
            generate_subtitles = self.config.get('subtitles', {}).get('generate_for_translations', True)
            if generate_subtitles:
                subtitle_generated = self.create_translation_subtitle(file_id, target_language)
                if not subtitle_generated:
                    logger.warning(f"Could not generate subtitle for translation to {target_language}")
                    # Continue with translation completion even if subtitle generation fails
            
            # Update status to completed
            status_update = {}
            status_update[status_field] = 'completed'
            
            # Check if all translations are completed
            all_completed = True
            for lang in ['en', 'de', 'he']:  # Target languages
                field = f"translation_{lang}_status"
                if lang == target_language:
                    continue  # Skip current language
                
                if file_details.get(field) != 'completed':
                    all_completed = False
                    break
            
            if all_completed:
                status_update['status'] = 'completed'
            
            # Extract status from status_update to avoid passing it twice
            status = status_update.pop('status', 'completed')
            self.db_manager.update_status(file_id=file_id, status=status, **status_update)
            
            logger.info(f"Translation to {target_language} completed for: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error translating file {file_id}: {e}")
            
            # Log error in database
            self.db_manager.log_error(
                file_id=file_id,
                process_stage=f'translation_{target_language}',
                error_message="Translation error",
                error_details=str(e)
            )
            
            # Update status to failed
            status_update = {}
            status_update[status_field] = 'failed'
            self.db_manager.update_status(file_id=file_id, status='failed', **status_update)
            
            return False
    
    def create_translation_subtitle(self, file_id: str, target_language: str) -> bool:
        """
        Create an SRT subtitle file for a translated transcript using timing from original transcript.
        
        Args:
            file_id: Unique ID of the file
            target_language: Target language code
            
        Returns:
            True if successful, False otherwise
        """
        # Check if managers are set
        if not self.file_manager:
            logger.error("File manager not set in translation manager")
            return False
            
        # Get file details
        file_details = self.db_manager.get_file_status(file_id)
        if not file_details:
            logger.error(f"File not found in database: {file_id}")
            return False
            
        # Get translation path
        translation_path = self.file_manager.get_translation_path(file_id, target_language)
        if not os.path.exists(translation_path):
            logger.error(f"Translation file not found: {translation_path}")
            return False
            
        # Get translation text
        try:
            with open(translation_path, 'r', encoding='utf-8') as f:
                translated_text = f.read()
        except Exception as e:
            logger.error(f"Error reading translation file {translation_path}: {e}")
            return False
            
        # Get original subtitle to extract timing information
        try:
            # Get original subtitle path (using 'orig' as language code)
            original_subtitle_path = self.file_manager.get_subtitle_path(file_id, 'orig')
            if not os.path.exists(original_subtitle_path):
                logger.error(f"Original subtitle file not found: {original_subtitle_path}")
                return False
                
            # Read original subtitle file to extract timing information
            with open(original_subtitle_path, 'r', encoding='utf-8') as f:
                original_subtitle = f.read()
                
            # Split original subtitle into blocks and extract text content
            subtitle_blocks = []
            original_texts = []
            
            for block in original_subtitle.strip().split('\n\n'):
                lines = block.strip().split('\n')
                if len(lines) >= 3:  # Valid subtitle block has at least 3 lines
                    subtitle_index = lines[0]
                    timestamp = lines[1]
                    text = '\n'.join(lines[2:])  # Text might span multiple lines
                    
                    subtitle_blocks.append({
                        'index': subtitle_index,
                        'timestamp': timestamp,
                        'text': text
                    })
                    original_texts.append(text)
            
            # If no valid subtitle blocks were found, abort
            if not subtitle_blocks:
                logger.error(f"No valid subtitle blocks found in {original_subtitle_path}")
                return False
            
            # Split the translated text into segments
            # First try to split by sentences
            sentences = re.split(r'(?<=[.!?])\s+', translated_text.strip())
            
            # If we have only one sentence but multiple blocks, try to split by punctuation
            if len(sentences) == 1 and len(subtitle_blocks) > 1:
                sentences = re.split(r'(?<=[,;:])\s+', translated_text.strip())
            
            # Distribute sentences across subtitle blocks
            translated_segments = []
            
            if len(sentences) >= len(subtitle_blocks):
                # If we have enough sentences, distribute them proportionally
                sentences_per_block = len(sentences) / len(subtitle_blocks)
                for i in range(len(subtitle_blocks)):
                    start_idx = int(i * sentences_per_block)
                    end_idx = int((i + 1) * sentences_per_block)
                    segment = ' '.join(sentences[start_idx:end_idx])
                    translated_segments.append(segment)
            else:
                # If we have fewer sentences than blocks, try to split the text by length ratios
                # Calculate length ratio of each original subtitle text
                total_original_length = sum(len(text) for text in original_texts)
                length_ratios = [len(text)/total_original_length for text in original_texts]
                
                # Split translated text using these ratios
                translated_length = len(translated_text)
                start_pos = 0
                
                for ratio in length_ratios:
                    segment_length = int(translated_length * ratio)
                    end_pos = min(start_pos + segment_length, translated_length)
                    
                    # Find nearest space to avoid cutting words
                    if end_pos < translated_length:
                        while end_pos < translated_length and translated_text[end_pos] != ' ':
                            end_pos += 1
                        if end_pos == translated_length:
                            # If we reached the end, go backward instead
                            end_pos = start_pos + segment_length
                            while end_pos > start_pos and translated_text[end_pos] != ' ':
                                end_pos -= 1
                    
                    # Extract segment
                    segment = translated_text[start_pos:end_pos].strip()
                    translated_segments.append(segment)
                    start_pos = end_pos
            
            # Ensure we have at least one segment for each block
            while len(translated_segments) < len(subtitle_blocks):
                translated_segments.append(translated_segments[-1] if translated_segments else translated_text)
            
            # Build the translated SRT file
            srt_lines = []
            
            for i, block in enumerate(subtitle_blocks):
                srt_lines.append(block['index'])
                srt_lines.append(block['timestamp'])
                srt_lines.append(translated_segments[i])
                srt_lines.append("")  # Empty line between subtitles
            
            # Create subtitle directory if it doesn't exist
            subtitle_path = self.file_manager.get_subtitle_path(file_id, target_language)
            os.makedirs(os.path.dirname(subtitle_path), exist_ok=True)
            
            # Write the translated subtitle file
            with open(subtitle_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_lines))
                
            logger.info(f"Translation subtitle saved to: {subtitle_path}")
            return True
                
        except Exception as e:
            logger.error(f"Error creating subtitle for translation: {e}")
            self.db_manager.log_error(
                file_id=file_id,
                process_stage=f'subtitle_{target_language}',
                error_message="Error creating subtitle for translation",
                error_details=str(e)
            )
            return False
    
    def translate_batch(self, target_languages: List[str], limit: Optional[int] = None, force: bool = False) -> Dict[str, Tuple[int, int]]:
        """
        Translate a batch of files to multiple target languages.
        
        Args:
            target_languages: List of target language codes
            limit: Maximum number of files to process
            force: Whether to force reprocessing of files with failed translation status
            
        Returns:
            Dictionary mapping language to (success_count, fail_count) tuples
        """
        # Get all files that need translation
        if force:
            # When force flag is set, include failed files
            files = self.db_manager.get_files_by_status(['in-progress', 'failed'])
        else:
            files = self.db_manager.get_files_by_status('in-progress')
            
        translation_files = [f for f in files 
                            if f['transcription_status'] == 'completed']
        
        if limit:
            translation_files = translation_files[:limit]
        
        logger.info(f"Found {len(translation_files)} files for translation")
        
        results = {}
        
        # Process each target language
        for target_language in target_languages:
            status_field = f"translation_{target_language}_status"
            
            # Filter files that need translation for this language
            if force:
                # When force is set, include all files regardless of translation status
                language_files = translation_files
            else:
                # Otherwise only include files that aren't already completed
                language_files = [f for f in translation_files 
                                if status_field not in f or f[status_field] != 'completed']
            
            logger.info(f"Found {len(language_files)} files to translate to {target_language}")
            
            success_count = 0
            fail_count = 0
            
            # Process each file
            for file in tqdm(language_files, desc=f"Translating to {target_language}"):
                file_id = file['file_id']
                
                if self.translate_file(file_id, target_language, force=force):
                    success_count += 1
                else:
                    fail_count += 1
            
            logger.info(f"Translation to {target_language} completed. Success: {success_count}, Failed: {fail_count}")
            results[target_language] = (success_count, fail_count)
        
        return results

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _translate_mixed_text_to_target(
        self,
        text: str,
        target_language: str,
        provider: Optional[str] = None,
        formality: str = 'default',
        source_language: Optional[str] = None,
    ) -> Optional[str]:
        """Translate a paragraph‑separated text, leaving segments already in
        the target language untouched.

        Args:
            text: Full transcript text (paragraphs separated by blank lines)
            target_language: ISO code of desired language (e.g. 'en')
            provider, formality, source_language: Passed through to
                `translate_text`.

        Returns:
            New text with only non‑target paragraphs translated, or None on error.
        """

        if not detect:
            # langdetect not installed – fallback to bulk translation
            return None

        paragraphs = text.split('\n\n')
        out_paragraphs = []

        for para in paragraphs:
            stripped = para.strip()
            if not stripped:
                out_paragraphs.append('')
                continue

            try:
                lang = detect(stripped)
            except Exception:
                lang = None

            # If already in target language (or detection failed but guess matches)
            if lang and self.is_same_language(lang, target_language):
                out_paragraphs.append(stripped)
                continue

            # Otherwise translate paragraph
            translated = self.translate_text(
                text=stripped,
                target_language=target_language,
                source_language=lang or source_language,
                provider=provider,
                formality=formality,
            )
            if not translated:
                # Abort if any paragraph fails – caller will handle
                return None
            out_paragraphs.append(translated)

        return '\n\n'.join(out_paragraphs)

    def _split_text_into_chunks(self, text: str, max_chars: int = 4500):
        """Split text into chunks <= max_chars, trying to respect paragraph boundaries."""
        paragraphs = re.split(r"\n{2,}", text)
        chunks = []
        current = ""
        for para in paragraphs:
            if not para:
                continue
            if len(para) > max_chars:
                for i in range(0, len(para), max_chars):
                    chunk_part = para[i:i+max_chars].strip()
                    if chunk_part:
                        chunks.append(chunk_part)
                current = ""
                continue
            # +2 for added paragraph break later
            if len(current) + len(para) + 2 <= max_chars:
                current += para + "\n\n"
            else:
                if current:
                    chunks.append(current.strip())
                current = para + "\n\n"
        if current:
            chunks.append(current.strip())
        return chunks

    def _load_hebrew_glossary(self) -> Dict[str, str]:
        """Load glossary CSV into a dictionary."""
        gloss: Dict[str, str] = {}
        path = Path("docs/glossaries/he_seed.csv")
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if ',' in line:
                            src, heb = line.strip().split(',', 1)
                            gloss[src.strip()] = heb.strip()
            except Exception as exc:
                logger.error(f"Failed to load glossary: {exc}")
        return gloss

    def _insert_glossary_placeholders(self, text: str):
        """Replace glossary terms with unique placeholder tokens."""
        mapping: Dict[str, str] = {}
        if not self.glossary:
            return text, mapping
        idx = 0
        # Replace longer terms first to avoid partial overlaps
        for term in sorted(self.glossary.keys(), key=len, reverse=True):
            if term and term in text:
                token = f"[[G_{idx}]]"
                mapping[token] = self.glossary[term]
                text = text.replace(term, token)
                idx += 1
        return text, mapping

    def _restore_glossary_placeholders(self, text: str, mapping):
        """Restore placeholders with their Hebrew equivalents."""
        for token, heb in mapping.items():
            text = text.replace(token, heb)
        return text

    def _polish_hebrew_with_gpt(self, source_text: str, draft_hebrew: str):
        """Refine Hebrew translation with GPT‑4.1 using glossary enforcement."""
        if not self.glossary or not draft_hebrew:
            return None
        if not openai:
            logger.warning("OpenAI package not available; skipping polish stage")
            return None
        try:
            glossary_lines = "\n".join([f"{k} -> {v}" for k, v in list(self.glossary.items())[:200]])
            prompt = (
                "You are a professional Hebrew translator and editor. "
                "Your task: improve fluency, idiom, grammar, punctuation and RTL formatting while preserving 100% meaning. "
                "Ensure the following glossary mappings are respected exactly. If term appears in the English source, use the given Hebrew equivalent.\n\n"
                "Glossary (source -> Hebrew):\n" + glossary_lines + "\n\n"
                "English (or German) source:\n" + source_text + "\n\n"
                "Current Hebrew draft:\n" + draft_hebrew + "\n\n"
                "Return ONLY the polished Hebrew text."  # No extra commentary
            )
            # Handle both old/new openai SDK
            if hasattr(openai, "OpenAI"):
                client = openai.OpenAI()
                completion = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[{"role": "system", "content": f"You are a professional translator. Translate from the source language to Hebrew accurately and entirely in Hebrew. Do not include any source-language words, except proper nouns."},
                    {"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                return completion.choices[0].message.content.strip()
            else:
                completion = openai.ChatCompletion.create(
                    model="gpt-4.1",
                    messages=[{"role": "system", "content": f"You are a professional translator. Translate from the source language to Hebrew accurately and entirely in Hebrew. Do not include any source-language words, except proper nouns."},
                    {"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                return completion["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error(f"GPT polish error: {exc}")
            return None
