#!/usr/bin/env python3
"""
Clean Translation Module for Historical Interview Transcripts
----------------------------------------------------------
Preserves authentic voice and speech patterns in translations.
Includes critical Hebrew routing logic (Hebrew → Microsoft/OpenAI, not DeepL).
"""

import os
import re
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from functools import wraps

# Optional imports with graceful fallbacks
try:
    import deepl
except ImportError:
    deepl = None

try:
    import openai
except ImportError:
    openai = None

try:
    import requests
except ImportError:
    requests = None

try:
    from langdetect import detect
except ImportError:
    detect = None

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


def retry(tries=3, delay=1, backoff=2, exceptions=(Exception,), return_on_failure=None):
    """
    Retry decorator with exponential backoff.
    
    Args:
        tries: Number of attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch
        return_on_failure: Value to return on failure (None), or 'raise' to re-raise exception
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            last_exception = None
            
            while attempt < tries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    attempt += 1
                    if attempt >= tries:
                        logger.error(f"Max retries ({tries}) exceeded for {func.__name__}: {e}")
                        if return_on_failure == 'raise':
                            raise e
                        # CRITICAL FIX: Always re-raise the last exception when max attempts exceeded
                        # This prevents silent failures that can cause data loss
                        if last_exception:
                            raise last_exception
                        return return_on_failure
                    
                    logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
            # Fallback (should not reach here, but ensure we don't return None silently)
            if last_exception:
                raise last_exception
            return return_on_failure
        return wrapper
    return decorator


class HistoricalTranslator:
    """
    Translation service optimized for historical interview transcripts.
    
    Key features:
    - Preserves authentic speech patterns (hesitations, repetitions, etc.)
    - Automatic Hebrew routing (DeepL → Microsoft/OpenAI)
    - Multi-provider support with intelligent fallback
    - Chunking for long texts
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize translator with configuration."""
        self.config = config or {}
        self.providers = {}
        self.openai_model = self.config.get('openai_model') or os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize available translation providers."""
        # DeepL
        deepl_key = self.config.get('deepl_api_key') or os.getenv('DEEPL_API_KEY')
        if deepl_key and deepl:
            try:
                self.providers['deepl'] = deepl.Translator(deepl_key)
                logger.info("DeepL provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize DeepL: {e}")
        
        # Microsoft Translator
        ms_key = self.config.get('ms_translator_key') or os.getenv('MS_TRANSLATOR_KEY')
        ms_location = self.config.get('ms_location') or os.getenv('MS_TRANSLATOR_LOCATION', 'global')
        if ms_key and requests:
            self.providers['microsoft'] = {
                'api_key': ms_key,
                'location': ms_location.split()[0].strip() if ms_location and ms_location.strip() else 'global'  # Clean location
            }
            logger.info("Microsoft Translator initialized")
        
        # OpenAI
        openai_key = self.config.get('openai_api_key') or os.getenv('OPENAI_API_KEY')
        if openai_key and openai:
            # Configure with proper timeout
            if httpx:
                self.openai_client = openai.OpenAI(
                    api_key=openai_key,
                    timeout=httpx.Timeout(60.0, connect=5.0),
                    max_retries=3
                )
            else:
                # Fallback without httpx
                self.openai_client = openai.OpenAI(
                    api_key=openai_key,
                    timeout=60.0,
                    max_retries=3
                )
            self.providers['openai'] = True
            logger.info("OpenAI provider initialized with timeout configuration")
        else:
            self.openai_client = None
    
    def translate(self, 
                  text: str, 
                  target_language: str,
                  source_language: Optional[str] = None,
                  provider: Optional[str] = None) -> Optional[str]:
        """
        Translate text to target language with automatic provider selection.
        
        CRITICAL: Automatically routes Hebrew translations to Microsoft/OpenAI.
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'en', 'de', 'he')
            source_language: Source language code (optional)
            provider: Preferred provider (optional, auto-selected for Hebrew)
            
        Returns:
            Translated text or None if failed
        """
        if not text:
            return None
        
        # CRITICAL HEBREW FIX: Auto-route Hebrew to capable providers
        if target_language.lower() in ['he', 'heb', 'hebrew']:
            if provider == 'deepl' or provider is None:
                # DeepL doesn't support Hebrew - switch providers
                # Prefer OpenAI for Hebrew to avoid Microsoft rate limiting
                if 'openai' in self.providers:
                    logger.info("Routing Hebrew translation to OpenAI")
                    provider = 'openai'
                elif 'microsoft' in self.providers:
                    logger.info("Routing Hebrew translation to Microsoft Translator")
                    provider = 'microsoft'
                else:
                    logger.error("No Hebrew-capable provider available")
                    return None
        
        # Select default provider if not specified
        if not provider:
            provider = self._select_default_provider()
        
        if provider not in self.providers:
            logger.error(f"Provider '{provider}' not available")
            return None
        
        # Normalize language codes
        target_lang = self._normalize_language_code(target_language, provider)
        source_lang = self._normalize_language_code(source_language, provider) if source_language else None
        
        try:
            # Route to appropriate provider
            if provider == 'deepl':
                return self._translate_deepl(text, target_lang, source_lang)
            elif provider == 'microsoft':
                return self._translate_microsoft(text, target_lang, source_lang)
            elif provider == 'openai':
                return self._translate_openai(text, target_lang, source_lang)
        except Exception as e:
            logger.error(f"Translation error with {provider}: {e}")
            return None
    
    def batch_translate(self,
                       texts: List[str],
                       target_language: str,
                       source_language: Optional[str] = None,
                       provider: Optional[str] = None) -> List[str]:
        """
        Translate multiple texts in batch for efficiency.
        
        This method optimizes API calls by sending multiple texts at once,
        significantly reducing costs and processing time for subtitle translation.
        
        Args:
            texts: List of texts to translate
            target_language: Target language code (e.g., 'en', 'de', 'he')
            source_language: Source language code (optional)
            provider: Preferred provider (optional, auto-selected for Hebrew)
            
        Returns:
            List of translated texts in same order as input
        """
        if not texts:
            return []
        
        # For single text, use regular translate
        if len(texts) == 1:
            result = self.translate(texts[0], target_language, source_language, provider)
            return [result] if result else ['']
        
        # CRITICAL HEBREW FIX: Auto-route Hebrew to capable providers
        if target_language.lower() in ['he', 'heb', 'hebrew']:
            if provider == 'deepl' or provider is None:
                # DeepL doesn't support Hebrew - switch providers
                if 'openai' in self.providers:
                    logger.info("Routing Hebrew batch translation to OpenAI")
                    provider = 'openai'
                elif 'microsoft' in self.providers:
                    logger.info("Routing Hebrew batch translation to Microsoft Translator")
                    provider = 'microsoft'
                else:
                    logger.error("No Hebrew-capable provider available")
                    return [''] * len(texts)
        
        # Select default provider if not specified
        if not provider:
            provider = self._select_default_provider()
        
        if provider not in self.providers:
            logger.error(f"Provider '{provider}' not available")
            return [''] * len(texts)
        
        # Normalize language codes
        target_lang = self._normalize_language_code(target_language, provider)
        source_lang = self._normalize_language_code(source_language, provider) if source_language else None
        
        try:
            # Route to appropriate batch translation method
            if provider == 'deepl':
                return self._batch_translate_deepl(texts, target_lang, source_lang)
            elif provider == 'microsoft':
                return self._batch_translate_microsoft(texts, target_lang, source_lang)
            elif provider == 'openai':
                return self._batch_translate_openai(texts, target_lang, source_lang)
        except Exception as e:
            logger.error(f"Batch translation error with {provider}: {e}")
            # Fall back to individual translation
            logger.warning("Falling back to individual translation")
            fallback_results = []
            for text in texts:
                try:
                    result = self.translate(text, target_language, source_language, provider)
                    fallback_results.append(result or '')
                except Exception as individual_error:
                    logger.error(f"Individual translation also failed: {individual_error}")
                    fallback_results.append('')
            return fallback_results
    
    def _batch_translate_deepl(self, texts: List[str], target_lang: str, source_lang: Optional[str]) -> List[str]:
        """Batch translate using DeepL."""
        # DeepL accepts multiple texts in a single request
        results = self.providers['deepl'].translate_text(
            texts=texts,
            target_lang=target_lang,
            source_lang=source_lang
        )
        return [result.text for result in results]
    
    def _batch_translate_microsoft(self, texts: List[str], target_lang: str, source_lang: Optional[str]) -> List[str]:
        """Batch translate using Microsoft Translator."""
        api_key = self.providers['microsoft']['api_key']
        location = self.providers['microsoft']['location']
        
        endpoint = "https://api.cognitive.microsofttranslator.com/translate"
        headers = {
            'Ocp-Apim-Subscription-Key': api_key,
            'Ocp-Apim-Subscription-Region': location,
            'Content-type': 'application/json'
        }
        
        params = {
            'api-version': '3.0',
            'to': target_lang
        }
        if source_lang:
            params['from'] = source_lang
        
        # Microsoft accepts array of texts
        body = [{'text': text} for text in texts]
        
        response = requests.post(endpoint, headers=headers, params=params, json=body)
        response.raise_for_status()
        
        results = response.json()
        translations = []
        for result in results:
            if 'translations' in result and len(result['translations']) > 0:
                translations.append(result['translations'][0]['text'])
            else:
                translations.append('')
        
        return translations
    
    def _batch_translate_openai(self, texts: List[str], target_lang: str, source_lang: Optional[str]) -> List[str]:
        """Batch translate using OpenAI by joining texts with separator."""
        # OpenAI doesn't have native batch support, so we use a separator approach
        separator = "\n<<<SEP>>>\n"
        combined_text = separator.join(texts)
        
        # Map language codes to names
        lang_names = {
            'en': 'English', 'de': 'German', 'he': 'Hebrew',
            'fr': 'French', 'es': 'Spanish', 'it': 'Italian'
        }
        target_name = lang_names.get(target_lang.lower(), target_lang)
        
        # System prompt for batch translation
        system_prompt = (
            f"You are a professional translator specializing in historical documents. "
            f"Translate the following texts to {target_name}. "
            "The texts are separated by <<<SEP>>>. "
            "Requirements:\n"
            "1. Translate each text segment independently\n"
            "2. Preserve the <<<SEP>>> separator between translations\n"
            "3. Maintain the exact same number of segments\n"
            "4. Return ONLY the translated texts with separators, no additional formatting\n"
            "5. For Hebrew translations, use proper Hebrew script and grammar"
        )
        
        try:
            # Use the API call method
            translated_combined = self._call_openai_api(system_prompt, combined_text)
            
            if not translated_combined:
                return [''] * len(texts)
            
            # Split back into individual translations
            translations = translated_combined.split(separator)
            
            # Ensure we have the right number of translations
            if len(translations) != len(texts):
                logger.warning(f"Translation count mismatch: expected {len(texts)}, got {len(translations)}")
                # Fall back to individual translation
                return [self.translate(text, target_lang, source_lang, 'openai') or '' for text in texts]
            
            return [t.strip() for t in translations]
            
        except Exception as e:
            logger.error(f"OpenAI batch translation error: {e}")
            # Fall back to individual translation
            return [self.translate(text, target_lang, source_lang, 'openai') or '' for text in texts]
    
    def _translate_deepl(self, text: str, target_lang: str, source_lang: Optional[str]) -> str:
        """Translate using DeepL."""
        result = self.providers['deepl'].translate_text(
            text=text,
            target_lang=target_lang,
            source_lang=source_lang
        )
        return result.text
    
    def _translate_microsoft(self, text: str, target_lang: str, source_lang: Optional[str]) -> Optional[str]:
        """Translate using Microsoft Translator with chunking for long texts."""
        # Microsoft has a 10,000 character limit per request
        if len(text) > 10000:
            chunks = self._split_text_into_chunks(text, 9500)
            translated_chunks = []
            for chunk in chunks:
                translated = self._call_microsoft_api(chunk, target_lang, source_lang)
                if not translated:
                    return None
                translated_chunks.append(translated)
            return "\n\n".join(translated_chunks)
        
        return self._call_microsoft_api(text, target_lang, source_lang)
    
    @retry(tries=3, delay=1, backoff=2, exceptions=(Exception,))
    def _call_microsoft_api(self, text: str, target_lang: str, source_lang: Optional[str]) -> Optional[str]:
        """Make API call to Microsoft Translator with retry logic."""
        api_key = self.providers['microsoft']['api_key']
        location = self.providers['microsoft']['location']
        
        endpoint = "https://api.cognitive.microsofttranslator.com/translate"
        headers = {
            'Ocp-Apim-Subscription-Key': api_key,
            'Ocp-Apim-Subscription-Region': location,
            'Content-type': 'application/json'
        }
        
        params = {
            'api-version': '3.0',
            'to': target_lang
        }
        if source_lang:
            params['from'] = source_lang
        
        body = [{'text': text}]
        
        response = requests.post(endpoint, headers=headers, params=params, json=body)
        response.raise_for_status()
        
        result = response.json()
        if result and len(result) > 0 and 'translations' in result[0]:
            return result[0]['translations'][0]['text']
        return None
    
    def _translate_openai(self, text: str, target_lang: str, source_lang: Optional[str]) -> Optional[str]:
        """
        Translate using OpenAI with focus on preserving authentic speech patterns.
        Optimized for historical interview transcripts.
        """
        # Map language codes to names
        lang_names = {
            'en': 'English', 'de': 'German', 'he': 'Hebrew',
            'fr': 'French', 'es': 'Spanish', 'it': 'Italian'
        }
        target_name = lang_names.get(target_lang.lower(), target_lang)
        
        # System prompt optimized for historical testimony
        system_prompt = (
            f"You are a professional translator specializing in historical documents. "
            f"Translate the following text to {target_name}. "
            "Requirements:\n"
            "1. Preserve the original meaning, tone, and style\n"
            "2. Maintain appropriate historical context and terminology\n"
            "3. Return ONLY the translated text, no additional formatting, quotes, or explanation\n"
            "4. For Hebrew translations, use proper Hebrew script and grammar\n"
            "5. Do not include any JSON formatting or special characters"
        )
        
        try:
            # Handle long texts with chunking
            if len(text) > 30000:
                chunks = self._split_text_into_chunks(text, 15000)
                translations = []
                for chunk in chunks:
                    result = self._call_openai_api(system_prompt, chunk)
                    if result:
                        translations.append(result)
                return "\n\n".join(translations)
            
            return self._call_openai_api(system_prompt, text)
            
        except Exception as e:
            logger.error(f"OpenAI translation error: {e}")
            return None
    
    @retry(tries=3, delay=1, backoff=2, exceptions=(Exception,))
    def _call_openai_api(self, system_prompt: str, text: str) -> Optional[str]:
        """Make API call to OpenAI with retry logic."""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")
            
        response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.3  # Lower temperature for consistency
        )
        
        content = response.choices[0].message.content.strip()
        return content
    
    def _normalize_language_code(self, language: str, provider: str) -> str:
        """Normalize language codes for specific providers."""
        if not language:
            return language
            
        lang = language.lower()
        
        # Provider-specific mappings
        if provider == 'deepl':
            mappings = {
                'en': 'EN-US',
                'de': 'DE',
                'he': 'HE',
                'eng': 'EN-US',
                'ger': 'DE',
                'deu': 'DE',
                'heb': 'HE'
            }
            return mappings.get(lang, language.upper())
        
        elif provider in ['microsoft', 'openai']:
            mappings = {
                'eng': 'en',
                'ger': 'de',
                'deu': 'de',
                'heb': 'he'
            }
            return mappings.get(lang, lang)
        
        return language
    
    def _split_text_into_chunks(self, text: str, max_chars: int = 9500) -> List[str]:
        """Split text into chunks, preserving paragraph boundaries where possible."""
        if not text:
            return []
        
        paragraphs = text.split('\n\n')
        # Remove empty paragraphs
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        if not paragraphs:
            return []
        
        chunks = []
        current_chunk = ""
        
        for i, para in enumerate(paragraphs):
            # If paragraph itself is too long, split it by sentences
            if len(para) > max_chars:
                # First, save current chunk if it exists
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # Split long paragraph by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    
                    # If adding this sentence would exceed max_chars
                    if len(current_chunk) + len(sentence) + 1 > max_chars:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence
                    else:
                        current_chunk += " " + sentence if current_chunk else sentence
            
            # Normal paragraph handling - try to group with current chunk
            else:
                # Calculate space needed to add this paragraph
                separator = "\n\n" if current_chunk else ""
                potential_length = len(current_chunk) + len(separator) + len(para)
                
                if potential_length <= max_chars:
                    # Paragraph fits in current chunk
                    current_chunk += separator + para
                    
                    # For better balance, if we have more paragraphs and adding the next one
                    # would exceed max_chars, but we have sufficient paragraphs left,
                    # consider ending the current chunk for better balance
                    if i + 1 < len(paragraphs):
                        next_para = paragraphs[i + 1]
                        next_separator = "\n\n"
                        next_potential_length = len(current_chunk) + len(next_separator) + len(next_para)
                        
                        # For better balance, if we have exactly 2 paragraphs remaining
                        # and current chunk is reasonable size, and adding the next paragraph
                        # would make it unbalanced, end chunk for better balance
                        if (len(paragraphs) - i - 1 == 2 and
                            len(current_chunk) >= max_chars * 0.3 and
                            next_potential_length > max_chars * 0.6):
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                    
                else:
                    # Paragraph doesn't fit, start new chunk
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = para
        
        # Add final chunk if it exists
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _select_default_provider(self) -> Optional[str]:
        """Select default provider based on availability."""
        # Prefer DeepL for non-Hebrew, then Microsoft, then OpenAI
        if 'deepl' in self.providers:
            return 'deepl'
        elif 'microsoft' in self.providers:
            return 'microsoft'
        elif 'openai' in self.providers:
            return 'openai'
        return None
    
    def validate_hebrew_translation(self, text: str) -> bool:
        """
        Validate that text contains Hebrew characters.
        
        Args:
            text: Text to validate
            
        Returns:
            True if text contains Hebrew characters
        """
        return any('\u0590' <= c <= '\u05FF' for c in text)
    
    def is_same_language(self, lang1: str, lang2: str) -> bool:
        """Check if two language codes refer to the same language."""
        if not lang1 or not lang2:
            return False
            
        # Normalize to lowercase
        lang1, lang2 = lang1.lower(), lang2.lower()
        
        # Language equivalence groups
        equivalents = {
            'en': {'en', 'eng', 'english'},
            'de': {'de', 'deu', 'ger', 'german'},
            'he': {'he', 'heb', 'hebrew'}
        }
        
        # Find which group each language belongs to
        group1 = group2 = None
        for key, group in equivalents.items():
            if lang1 in group:
                group1 = key
            if lang2 in group:
                group2 = key
        
        # If both found in groups, compare groups
        if group1 and group2:
            return group1 == group2
        
        # Otherwise, direct comparison
        return lang1 == lang2


# Convenience functions for direct usage
def translate_text(text: str, 
                   target_language: str,
                   source_language: Optional[str] = None,
                   provider: Optional[str] = None,
                   config: Optional[Dict] = None) -> Optional[str]:
    """
    Translate text preserving authentic speech patterns.
    
    Args:
        text: Text to translate
        target_language: Target language code ('en', 'de', 'he')
        source_language: Source language code (optional)
        provider: Translation provider (optional, auto-selected for Hebrew)
        config: Configuration dict with API keys (optional)
        
    Returns:
        Translated text or None if failed
    """
    translator = HistoricalTranslator(config)
    return translator.translate(text, target_language, source_language, provider)


def validate_hebrew(text: str) -> bool:
    """Check if text contains Hebrew characters."""
    return any('\u0590' <= c <= '\u05FF' for c in text)