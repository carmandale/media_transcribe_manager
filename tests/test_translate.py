"""
Comprehensive tests for the translate module.

Tests cover all major functionality including:
- Hebrew routing logic (critical feature)
- Multi-provider support (DeepL, Microsoft, OpenAI)
- Retry logic and error handling
- Text chunking for long documents
- Language code normalization
- Provider selection and fallbacks
"""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Optional

from scribe.translate import (
    HistoricalTranslator, translate_text, validate_hebrew, retry
)


class TestRetryDecorator:
    """Test the retry decorator functionality."""
    
    @pytest.mark.unit
    def test_retry_success_first_attempt(self):
        """Test function succeeds on first attempt."""
        mock_func = Mock(return_value="success")
        
        @retry(tries=3, delay=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 1
    
    @pytest.mark.unit
    def test_retry_success_after_failures(self):
        """Test function succeeds after failures."""
        mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        
        @retry(tries=3, delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    @pytest.mark.unit
    def test_retry_max_attempts_exceeded(self):
        """Test retry gives up after max attempts."""
        mock_func = Mock(side_effect=Exception("persistent failure"))
        
        @retry(tries=2, delay=0.01)
        def test_func():
            return mock_func()
        
        with pytest.raises(Exception) as exc_info:
            test_func()
        
        assert "persistent failure" in str(exc_info.value)
        assert mock_func.call_count == 2
    
    @pytest.mark.unit
    @patch('time.sleep')
    def test_retry_exponential_backoff(self, mock_sleep):
        """Test exponential backoff between retries."""
        mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        
        @retry(tries=3, delay=1, backoff=2)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        
        # Check sleep calls: 1s, then 2s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(1), call(2)])


class TestHistoricalTranslatorInitialization:
    """Test translator initialization and provider setup."""
    
    @pytest.mark.unit
    @patch.dict('os.environ', {
        'DEEPL_API_KEY': 'test_deepl_key',
        'MS_TRANSLATOR_KEY': 'test_ms_key',
        'OPENAI_API_KEY': 'test_openai_key'
    })
    def test_initialize_all_providers(self, mock_env_vars):
        """Test initialization with all providers available."""
        with patch('scribe.translate.deepl') as mock_deepl, \
             patch('scribe.translate.openai') as mock_openai, \
             patch('scribe.translate.requests') as mock_requests:
            
            # Mock modules exist
            mock_deepl.Translator = Mock()
            
            translator = HistoricalTranslator()
            
            assert 'deepl' in translator.providers
            assert 'microsoft' in translator.providers
            assert 'openai' in translator.providers
            assert translator.openai_model == 'gpt-4.1-mini'
    
    @pytest.mark.unit
    def test_initialize_with_config(self):
        """Test initialization with custom config."""
        config = {
            'deepl_api_key': 'config_deepl_key',
            'ms_translator_key': 'config_ms_key',
            'openai_api_key': 'config_openai_key',
            'openai_model': 'gpt-4',
            'ms_location': 'westus'
        }
        
        with patch('scribe.translate.deepl') as mock_deepl:
            mock_deepl.Translator = Mock()
            
            translator = HistoricalTranslator(config)
            
            assert translator.openai_model == 'gpt-4'
            assert translator.providers['microsoft']['location'] == 'westus'
    
    @pytest.mark.unit
    def test_initialize_missing_modules(self):
        """Test graceful handling of missing modules."""
        with patch('scribe.translate.deepl', None), \
             patch('scribe.translate.openai', None), \
             patch('scribe.translate.requests', None):
            
            translator = HistoricalTranslator({
                'deepl_api_key': 'key',
                'ms_translator_key': 'key',
                'openai_api_key': 'key'
            })
            
            assert len(translator.providers) == 0
    
    @pytest.mark.unit
    @patch('scribe.translate.deepl.Translator')
    def test_deepl_initialization_failure(self, mock_deepl_class):
        """Test handling of DeepL initialization failure."""
        mock_deepl_class.side_effect = Exception("Invalid API key")
        
        translator = HistoricalTranslator({'deepl_api_key': 'bad_key'})
        
        assert 'deepl' not in translator.providers


class TestHebrewRouting:
    """Test critical Hebrew routing logic."""
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_hebrew_routing_from_deepl_to_openai(self):
        """Test Hebrew requests are routed away from DeepL to OpenAI."""
        translator = HistoricalTranslator()
        translator.providers = {
            'deepl': Mock(),
            'openai': True,
            'microsoft': {}
        }
        translator.openai_client = Mock()
        
        with patch.object(translator, '_translate_openai', return_value="תרגום עברי") as mock_openai:
            result = translator.translate("Hello", "he", provider="deepl")
            
            mock_openai.assert_called_once()
            assert result == "תרגום עברי"
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_hebrew_routing_auto_select_openai(self):
        """Test Hebrew auto-selects OpenAI when available."""
        translator = HistoricalTranslator()
        translator.providers = {
            'deepl': Mock(),
            'openai': True,
            'microsoft': {}
        }
        
        with patch.object(translator, '_translate_openai', return_value="תרגום") as mock_openai:
            result = translator.translate("Test", "hebrew")
            
            mock_openai.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_hebrew_fallback_to_microsoft(self):
        """Test Hebrew falls back to Microsoft if OpenAI unavailable."""
        translator = HistoricalTranslator()
        translator.providers = {
            'deepl': Mock(),
            'microsoft': {'api_key': 'key', 'location': 'global'}
        }
        
        with patch.object(translator, '_translate_microsoft', return_value="תרגום") as mock_ms:
            result = translator.translate("Test", "HE")
            
            mock_ms.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_hebrew_no_capable_provider(self):
        """Test error when no Hebrew-capable provider available."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}  # Only DeepL available
        
        result = translator.translate("Test", "he")
        
        assert result is None


class TestProviderTranslations:
    """Test individual provider translation methods."""
    
    @pytest.mark.unit
    def test_translate_deepl(self):
        """Test DeepL translation."""
        translator = HistoricalTranslator()
        mock_deepl = Mock()
        mock_result = Mock()
        mock_result.text = "Hallo Welt"
        mock_deepl.translate_text.return_value = mock_result
        
        translator.providers['deepl'] = mock_deepl
        
        result = translator._translate_deepl("Hello World", "DE", "EN")
        
        assert result == "Hallo Welt"
        mock_deepl.translate_text.assert_called_once_with(
            text="Hello World",
            target_lang="DE",
            source_lang="EN"
        )
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_translate_microsoft(self, mock_post):
        """Test Microsoft Translator."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {'translations': [{'text': 'Bonjour le monde'}]}
        ]
        mock_post.return_value = mock_response
        
        result = translator._translate_microsoft("Hello World", "fr", "en")
        
        assert result == "Bonjour le monde"
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['headers']['Ocp-Apim-Subscription-Key'] == 'test_key'
        assert call_args[1]['params']['to'] == 'fr'
        assert call_args[1]['json'] == [{'text': 'Hello World'}]
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_translate_microsoft_long_text(self, mock_post):
        """Test Microsoft Translator with text chunking."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Create long text (>10k chars)
        long_text = "Test sentence. " * 1000  # ~14k chars
        
        # Mock responses for chunks
        mock_response = Mock()
        mock_response.json.return_value = [
            {'translations': [{'text': 'Phrase de test. '}]}
        ]
        mock_post.return_value = mock_response
        
        result = translator._translate_microsoft(long_text, "fr", None)
        
        # Should have made multiple API calls
        assert mock_post.call_count > 1
        assert result is not None
        assert "Phrase de test" in result
    
    @pytest.mark.unit
    def test_translate_openai(self):
        """Test OpenAI translation."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Ciao mondo"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        translator.openai_client = mock_client
        translator.openai_model = 'gpt-4'
        
        result = translator._translate_openai("Hello world", "it", None)
        
        assert result == "Ciao mondo"
        
        # Verify API call
        create_call = mock_client.chat.completions.create
        create_call.assert_called_once()
        call_args = create_call.call_args[1]
        assert call_args['model'] == 'gpt-4'
        assert call_args['temperature'] == 0.3
        assert len(call_args['messages']) == 2
        assert "Italian" in call_args['messages'][0]['content']
    
    @pytest.mark.unit
    def test_translate_openai_hebrew(self):
        """Test OpenAI Hebrew translation prompt."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="שלום עולם"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        translator.openai_client = mock_client
        
        result = translator._translate_openai("Hello world", "he", None)
        
        assert result == "שלום עולם"
        
        # Verify Hebrew-specific instructions in prompt
        create_call = mock_client.chat.completions.create
        system_prompt = create_call.call_args[1]['messages'][0]['content']
        assert "Hebrew" in system_prompt
        assert "Hebrew script" in system_prompt


class TestLanguageHandling:
    """Test language code normalization and comparison."""
    
    @pytest.mark.unit
    def test_normalize_language_code_deepl(self):
        """Test language code normalization for DeepL."""
        translator = HistoricalTranslator()
        
        assert translator._normalize_language_code('en', 'deepl') == 'EN-US'
        assert translator._normalize_language_code('de', 'deepl') == 'DE'
        assert translator._normalize_language_code('eng', 'deepl') == 'EN-US'
        assert translator._normalize_language_code('ger', 'deepl') == 'DE'
        assert translator._normalize_language_code('deu', 'deepl') == 'DE'
        assert translator._normalize_language_code('fr', 'deepl') == 'FR'  # Unmapped
    
    @pytest.mark.unit
    def test_normalize_language_code_microsoft(self):
        """Test language code normalization for Microsoft."""
        translator = HistoricalTranslator()
        
        assert translator._normalize_language_code('eng', 'microsoft') == 'en'
        assert translator._normalize_language_code('ger', 'microsoft') == 'de'
        assert translator._normalize_language_code('deu', 'microsoft') == 'de'
        assert translator._normalize_language_code('heb', 'microsoft') == 'he'
        assert translator._normalize_language_code('en', 'microsoft') == 'en'
    
    @pytest.mark.unit
    def test_is_same_language(self):
        """Test language equivalence checking."""
        translator = HistoricalTranslator()
        
        # Same language, different codes
        assert translator.is_same_language('en', 'eng')
        assert translator.is_same_language('de', 'deu')
        assert translator.is_same_language('de', 'ger')
        assert translator.is_same_language('he', 'hebrew')
        
        # Different languages
        assert not translator.is_same_language('en', 'de')
        assert not translator.is_same_language('he', 'en')
        
        # Edge cases
        assert not translator.is_same_language(None, 'en')
        assert not translator.is_same_language('', 'en')
        assert translator.is_same_language('en', 'en')


class TestTextChunking:
    """Test text splitting functionality."""
    
    @pytest.mark.unit
    def test_split_text_basic(self):
        """Test basic text splitting."""
        translator = HistoricalTranslator()
        
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        chunks = translator._split_text_into_chunks(text, max_chars=20)
        
        assert len(chunks) == 3
        assert chunks[0] == "Paragraph 1."
        assert chunks[1] == "Paragraph 2."
        assert chunks[2] == "Paragraph 3."
    
    @pytest.mark.unit
    def test_split_text_long_paragraph(self):
        """Test splitting of long paragraphs."""
        translator = HistoricalTranslator()
        
        # Create a long paragraph with multiple sentences
        long_para = "Short sentence. " * 10  # ~160 chars
        chunks = translator._split_text_into_chunks(long_para, max_chars=50)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 50 for chunk in chunks)
    
    @pytest.mark.unit
    def test_split_text_preserve_paragraphs(self):
        """Test that paragraph boundaries are preserved when possible."""
        translator = HistoricalTranslator()
        
        text = "Para 1.\n\nPara 2.\n\nPara 3.\n\nPara 4."
        chunks = translator._split_text_into_chunks(text, max_chars=30)
        
        # Should group paragraphs when they fit
        assert len(chunks) == 2
        assert "Para 1" in chunks[0] and "Para 2" in chunks[0]
        assert "Para 3" in chunks[1] and "Para 4" in chunks[1]


class TestProviderSelection:
    """Test provider selection logic."""
    
    @pytest.mark.unit
    def test_select_default_provider_preference(self):
        """Test default provider selection preference."""
        translator = HistoricalTranslator()
        
        # Test DeepL preferred
        translator.providers = {'deepl': Mock(), 'microsoft': {}, 'openai': True}
        assert translator._select_default_provider() == 'deepl'
        
        # Test Microsoft if no DeepL
        translator.providers = {'microsoft': {}, 'openai': True}
        assert translator._select_default_provider() == 'microsoft'
        
        # Test OpenAI as last resort
        translator.providers = {'openai': True}
        assert translator._select_default_provider() == 'openai'
        
        # Test none available
        translator.providers = {}
        assert translator._select_default_provider() is None
    
    @pytest.mark.unit
    def test_translate_with_explicit_provider(self):
        """Test translation with explicitly specified provider."""
        translator = HistoricalTranslator()
        translator.providers = {
            'deepl': Mock(),
            'microsoft': {'api_key': 'key', 'location': 'global'}
        }
        
        with patch.object(translator, '_translate_microsoft', return_value="Translated") as mock_ms:
            result = translator.translate("Hello", "fr", provider="microsoft")
            
            mock_ms.assert_called_once()
            assert result == "Translated"
    
    @pytest.mark.unit
    def test_translate_provider_not_available(self):
        """Test error when requested provider not available."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}
        
        result = translator.translate("Hello", "fr", provider="openai")
        
        assert result is None


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.unit
    def test_translate_empty_text(self):
        """Test handling of empty text."""
        translator = HistoricalTranslator()
        
        assert translator.translate("", "de") is None
        assert translator.translate(None, "de") is None
    
    @pytest.mark.unit
    def test_translate_with_exception(self):
        """Test handling of translation exceptions."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}
        
        with patch.object(translator, '_translate_deepl', side_effect=Exception("API Error")):
            result = translator.translate("Hello", "de")
            
            assert result is None
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_microsoft_api_error(self, mock_post):
        """Test handling of Microsoft API errors."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Mock API error
        mock_post.side_effect = Exception("Connection error")
        
        # With retry decorator, it should try 3 times
        result = translator._translate_microsoft("Hello", "fr", None)
        
        assert result is None
        assert mock_post.call_count == 3


class TestValidation:
    """Test validation functions."""
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_hebrew_translation(self):
        """Test Hebrew text validation."""
        translator = HistoricalTranslator()
        
        # Valid Hebrew text
        assert translator.validate_hebrew_translation("שלום עולם")
        assert translator.validate_hebrew_translation("Mixed text עברית English")
        
        # Invalid (no Hebrew)
        assert not translator.validate_hebrew_translation("Hello world")
        assert not translator.validate_hebrew_translation("")
        assert not translator.validate_hebrew_translation("123456")
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_hebrew_function(self):
        """Test standalone Hebrew validation function."""
        assert validate_hebrew("טקסט בעברית")
        assert validate_hebrew("Some Hebrew: שלום")
        assert not validate_hebrew("No Hebrew here")


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    @pytest.mark.unit
    @patch('scribe.translate.HistoricalTranslator')
    def test_translate_text_function(self, mock_translator_class):
        """Test translate_text convenience function."""
        mock_instance = Mock()
        mock_instance.translate.return_value = "Translated text"
        mock_translator_class.return_value = mock_instance
        
        result = translate_text(
            "Hello",
            "de",
            source_language="en",
            provider="deepl",
            config={'api_key': 'test'}
        )
        
        assert result == "Translated text"
        mock_translator_class.assert_called_once_with({'api_key': 'test'})
        mock_instance.translate.assert_called_once_with("Hello", "de", "en", "deepl")


class TestIntegration:
    """Integration tests with mocked external services."""
    
    @pytest.mark.integration
    @patch.dict('os.environ', {
        'DEEPL_API_KEY': 'test_deepl',
        'OPENAI_API_KEY': 'test_openai'
    })
    @patch('scribe.translate.deepl.Translator')
    @patch('scribe.translate.openai.OpenAI')
    def test_hebrew_routing_integration(self, mock_openai_class, mock_deepl_class):
        """Test complete Hebrew routing flow."""
        # Setup mocks
        mock_deepl = Mock()
        mock_deepl_class.return_value = mock_deepl
        
        mock_openai_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="תרגום עברי מושלם"))]
        mock_openai_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_openai_client
        
        # Create translator and translate to Hebrew
        translator = HistoricalTranslator()
        result = translator.translate(
            "This is a test of Hebrew routing",
            "he"
        )
        
        # Verify Hebrew was routed to OpenAI, not DeepL
        assert result == "תרגום עברי מושלם"
        mock_deepl.translate_text.assert_not_called()
        mock_openai_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.integration
    @patch('scribe.translate.requests.post')
    def test_long_document_translation(self, mock_post):
        """Test translation of long document with chunking."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Create a long document
        long_doc = "\n\n".join([f"Paragraph {i}. " * 20 for i in range(50)])
        
        # Mock responses
        mock_response = Mock()
        mock_response.json.return_value = [
            {'translations': [{'text': 'Translated chunk'}]}
        ]
        mock_post.return_value = mock_response
        
        result = translator._translate_microsoft(long_doc, "fr", None)
        
        # Should have made multiple calls due to chunking
        assert mock_post.call_count > 1
        assert result is not None
        assert "Translated chunk" in result