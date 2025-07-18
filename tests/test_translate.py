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
        
        # With retry decorator, it should re-raise exception after 3 tries
        with pytest.raises(Exception, match="Connection error"):
            translator._translate_microsoft("Hello", "fr", None)
        
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
    
    @pytest.mark.unit
    @patch('scribe.translate.HistoricalTranslator')
    def test_translate_text_function_minimal_params(self, mock_translator_class):
        """Test translate_text convenience function with minimal parameters."""
        mock_instance = Mock()
        mock_instance.translate.return_value = "Translated text"
        mock_translator_class.return_value = mock_instance
        
        result = translate_text("Hello", "de")
        
        assert result == "Translated text"
        mock_translator_class.assert_called_once_with(None)
        mock_instance.translate.assert_called_once_with("Hello", "de", None, None)
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_hebrew_function(self):
        """Test standalone validate_hebrew function."""
        # Test valid Hebrew
        assert validate_hebrew("שלום עולם")
        assert validate_hebrew("Mixed שלום text")
        
        # Test invalid (no Hebrew)
        assert not validate_hebrew("Hello world")
        assert not validate_hebrew("")
        assert not validate_hebrew("123456")
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_hebrew_function_edge_cases(self):
        """Test validate_hebrew function with edge cases."""
        # Test None input
        assert not validate_hebrew(None)
        
        # Test Unicode edge cases
        assert validate_hebrew("\u0590")  # First Hebrew character
        assert validate_hebrew("\u05FF")  # Last Hebrew character
        assert not validate_hebrew("\u058F")  # Before Hebrew range
        assert not validate_hebrew("\u0600")  # After Hebrew range


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


class TestBatchTranslation:
    """Test batch translation functionality."""
    
    @pytest.mark.unit
    def test_batch_translate_empty_list(self):
        """Test batch translation with empty list."""
        translator = HistoricalTranslator()
        result = translator.batch_translate([], "de")
        assert result == []
    
    @pytest.mark.unit
    def test_batch_translate_single_text(self):
        """Test batch translation with single text falls back to regular translate."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}
        
        with patch.object(translator, 'translate', return_value="Translated") as mock_translate:
            result = translator.batch_translate(["Hello"], "de")
            
            assert result == ["Translated"]
            mock_translate.assert_called_once_with("Hello", "de", None, None)
    
    @pytest.mark.unit
    def test_batch_translate_hebrew_routing(self):
        """Test batch translation routes Hebrew to proper provider."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock(), 'openai': True}
        
        with patch.object(translator, '_batch_translate_openai', return_value=["תרגום1", "תרגום2"]) as mock_openai:
            result = translator.batch_translate(["Text 1", "Text 2"], "he")
            
            assert result == ["תרגום1", "תרגום2"]
            mock_openai.assert_called_once()
    
    @pytest.mark.unit
    def test_batch_translate_provider_not_available(self):
        """Test batch translation when provider not available."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}
        
        result = translator.batch_translate(["Text 1", "Text 2"], "fr", provider="openai")
        
        assert result == ['', '']  # Empty strings for each input
    
    @pytest.mark.unit
    def test_batch_translate_fallback_to_individual(self):
        """Test batch translation falls back to individual translation on error."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}
        
        with patch.object(translator, '_batch_translate_deepl', side_effect=Exception("Batch failed")), \
             patch.object(translator, 'translate', side_effect=["Trans1", "Trans2"]) as mock_translate:
            
            result = translator.batch_translate(["Text 1", "Text 2"], "de")
            
            assert result == ["Trans1", "Trans2"]
            assert mock_translate.call_count == 2
    
    @pytest.mark.unit
    def test_batch_translate_individual_fallback_failure(self):
        """Test batch translation when individual fallback also fails."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}
        
        with patch.object(translator, '_batch_translate_deepl', side_effect=Exception("Batch failed")), \
             patch.object(translator, 'translate', side_effect=["Trans1", None]) as mock_translate:
            
            result = translator.batch_translate(["Text 1", "Text 2"], "de")
            
            assert result == ["Trans1", ""]  # Empty string for failed translation
            assert mock_translate.call_count == 2
    
    @pytest.mark.unit
    def test_batch_translate_deepl_success(self):
        """Test successful DeepL batch translation."""
        translator = HistoricalTranslator()
        mock_deepl = Mock()
        mock_result1 = Mock()
        mock_result1.text = "Hallo"
        mock_result2 = Mock()
        mock_result2.text = "Welt"
        mock_deepl.translate_text.return_value = [mock_result1, mock_result2]
        
        translator.providers['deepl'] = mock_deepl
        
        result = translator._batch_translate_deepl(["Hello", "World"], "de", None)
        
        assert result == ["Hallo", "Welt"]
        mock_deepl.translate_text.assert_called_once_with(
            texts=["Hello", "World"],
            target_lang="de",
            source_lang=None
        )
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_batch_translate_microsoft_success(self, mock_post):
        """Test successful Microsoft batch translation."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {'translations': [{'text': 'Bonjour'}]},
            {'translations': [{'text': 'Monde'}]}
        ]
        mock_post.return_value = mock_response
        
        result = translator._batch_translate_microsoft(["Hello", "World"], "fr", None)
        
        assert result == ["Bonjour", "Monde"]
        
        # Verify API call structure
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['json'] == [{'text': 'Hello'}, {'text': 'World'}]
        assert call_args[1]['params']['to'] == 'fr'
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_batch_translate_microsoft_partial_failure(self, mock_post):
        """Test Microsoft batch translation with partial failures."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Mock API response with missing translation
        mock_response = Mock()
        mock_response.json.return_value = [
            {'translations': [{'text': 'Bonjour'}]},
            {}  # Missing translations key
        ]
        mock_post.return_value = mock_response
        
        result = translator._batch_translate_microsoft(["Hello", "World"], "fr", None)
        
        assert result == ["Bonjour", ""]  # Empty string for failed translation
    
    @pytest.mark.unit
    def test_batch_translate_openai_success(self):
        """Test successful OpenAI batch translation."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Ciao\n<<<SEP>>>\nMondo"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        translator.openai_client = mock_client
        
        result = translator._batch_translate_openai(["Hello", "World"], "it", None)
        
        assert result == ["Ciao", "Mondo"]
        
        # Verify API call
        create_call = mock_client.chat.completions.create
        create_call.assert_called_once()
        call_args = create_call.call_args[1]
        assert "Italian" in call_args['messages'][0]['content']
        assert "Hello\n<<<SEP>>>\nWorld" in call_args['messages'][1]['content']
    
    @pytest.mark.unit
    def test_batch_translate_openai_mismatch_count(self):
        """Test OpenAI batch translation with count mismatch fallback."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Only one translation"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        translator.openai_client = mock_client
        
        with patch.object(translator, 'translate', side_effect=["Trans1", "Trans2"]) as mock_translate:
            result = translator._batch_translate_openai(["Hello", "World"], "it", None)
            
            assert result == ["Trans1", "Trans2"]
            assert mock_translate.call_count == 2
    
    @pytest.mark.unit
    def test_batch_translate_openai_api_error(self):
        """Test OpenAI batch translation with API error fallback."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        translator.openai_client = mock_client
        
        with patch.object(translator, 'translate', side_effect=["Trans1", "Trans2"]) as mock_translate:
            result = translator._batch_translate_openai(["Hello", "World"], "it", None)
            
            assert result == ["Trans1", "Trans2"]
            assert mock_translate.call_count == 2


class TestProviderMethods:
    """Test provider-specific translation methods with comprehensive scenarios."""
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_call_microsoft_api_success(self, mock_post):
        """Test successful Microsoft API call."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'westus'
        }
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = [
            {'translations': [{'text': 'Bonjour le monde'}]}
        ]
        mock_post.return_value = mock_response
        
        result = translator._call_microsoft_api("Hello world", "fr", "en")
        
        assert result == "Bonjour le monde"
        
        # Verify API call parameters
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['headers']['Ocp-Apim-Subscription-Key'] == 'test_key'
        assert call_args[1]['headers']['Ocp-Apim-Subscription-Region'] == 'westus'
        assert call_args[1]['params']['to'] == 'fr'
        assert call_args[1]['params']['from'] == 'en'
        assert call_args[1]['json'] == [{'text': 'Hello world'}]
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_call_microsoft_api_empty_response(self, mock_post):
        """Test Microsoft API call with empty response."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_post.return_value = mock_response
        
        result = translator._call_microsoft_api("Hello world", "fr", None)
        
        assert result is None
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_call_microsoft_api_malformed_response(self, mock_post):
        """Test Microsoft API call with malformed response."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Mock malformed response
        mock_response = Mock()
        mock_response.json.return_value = [
            {'error': 'Invalid request'}
        ]
        mock_post.return_value = mock_response
        
        result = translator._call_microsoft_api("Hello world", "fr", None)
        
        assert result is None
    
    @pytest.mark.unit
    def test_call_openai_api_success(self):
        """Test successful OpenAI API call."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="  Bonjour le monde  "))]
        mock_client.chat.completions.create.return_value = mock_response
        
        translator.openai_client = mock_client
        translator.openai_model = 'gpt-4'
        
        result = translator._call_openai_api("You are a translator", "Hello world")
        
        assert result == "Bonjour le monde"  # Should be stripped
        
        # Verify API call
        create_call = mock_client.chat.completions.create
        create_call.assert_called_once()
        call_args = create_call.call_args[1]
        assert call_args['model'] == 'gpt-4'
        assert call_args['temperature'] == 0.3
        assert call_args['messages'][0]['content'] == "You are a translator"
        assert call_args['messages'][1]['content'] == "Hello world"
    
    @pytest.mark.unit
    def test_call_openai_api_no_client(self):
        """Test OpenAI API call without initialized client."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        translator.openai_client = None
        
        with pytest.raises(ValueError, match="OpenAI client not initialized"):
            translator._call_openai_api("System prompt", "Hello world")
    
    @pytest.mark.unit
    def test_translate_microsoft_chunking(self):
        """Test Microsoft translation with text chunking."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Create text over 10k characters
        long_text = "This is a test sentence. " * 500  # ~12.5k chars
        
        with patch.object(translator, '_call_microsoft_api', return_value="Translated chunk") as mock_api:
            result = translator._translate_microsoft(long_text, "fr", None)
            
            # Should have made multiple API calls
            assert mock_api.call_count > 1
            assert result == "Translated chunk\n\nTranslated chunk"
    
    @pytest.mark.unit
    def test_translate_microsoft_chunk_failure(self):
        """Test Microsoft translation when chunk translation fails."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Create text over 10k characters
        long_text = "This is a test sentence. " * 500  # ~12.5k chars
        
        with patch.object(translator, '_call_microsoft_api', return_value=None) as mock_api:
            result = translator._translate_microsoft(long_text, "fr", None)
            
            # Should return None when chunk fails
            assert result is None
            assert mock_api.call_count == 1  # Should stop at first failure
    
    @pytest.mark.unit
    def test_translate_openai_chunking(self):
        """Test OpenAI translation with text chunking."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        # Create text over 30k characters
        long_text = "This is a test sentence. " * 1500  # ~37.5k chars
        
        with patch.object(translator, '_call_openai_api', return_value="Translated chunk") as mock_api:
            result = translator._translate_openai(long_text, "fr", None)
            
            # Should have made multiple API calls (improved chunking creates 3 chunks with max_chars=15000)
            assert mock_api.call_count == 3
            assert result == "Translated chunk\n\nTranslated chunk\n\nTranslated chunk"
    
    @pytest.mark.unit
    def test_translate_openai_chunk_failure(self):
        """Test OpenAI translation when chunk translation fails."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        # Create text over 30k characters
        long_text = "This is a test sentence. " * 1500  # ~37.5k chars
        
        with patch.object(translator, '_call_openai_api', return_value=None) as mock_api:
            result = translator._translate_openai(long_text, "fr", None)
            
            # Should return None when chunk fails
            assert result is None
            assert mock_api.call_count == 1  # Should stop at first failure
    
    @pytest.mark.unit
    def test_translate_openai_api_exception(self):
        """Test OpenAI translation with API exception."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        with patch.object(translator, '_call_openai_api', side_effect=Exception("API Error")):
            result = translator._translate_openai("Hello world", "fr", None)
            
            assert result is None


class TestTextChunkingAdvanced:
    """Test advanced text chunking scenarios."""
    
    @pytest.mark.unit
    def test_split_text_empty_input(self):
        """Test text splitting with empty input."""
        translator = HistoricalTranslator()
        
        assert translator._split_text_into_chunks("") == []
        assert translator._split_text_into_chunks(None) == []
    
    @pytest.mark.unit
    def test_split_text_single_short_paragraph(self):
        """Test splitting single short paragraph."""
        translator = HistoricalTranslator()
        
        text = "This is a short paragraph."
        chunks = translator._split_text_into_chunks(text, max_chars=100)
        
        assert len(chunks) == 1
        assert chunks[0] == "This is a short paragraph."
    
    @pytest.mark.unit
    def test_split_text_balance_remaining_paragraphs(self):
        """Test balanced splitting of remaining paragraphs."""
        translator = HistoricalTranslator()
        
        # Create 4 paragraphs of moderate length
        paragraphs = [f"Paragraph {i} with some content." for i in range(1, 5)]
        text = "\n\n".join(paragraphs)
        
        chunks = translator._split_text_into_chunks(text, max_chars=70)
        
        # Should create balanced chunks
        assert len(chunks) == 2
        assert "Paragraph 1" in chunks[0] and "Paragraph 2" in chunks[0]
        assert "Paragraph 3" in chunks[1] and "Paragraph 4" in chunks[1]
    
    @pytest.mark.unit
    def test_split_text_very_long_paragraph_sentence_split(self):
        """Test splitting very long paragraph by sentences."""
        translator = HistoricalTranslator()
        
        # Create a very long paragraph with sentences
        sentences = [f"This is sentence {i}." for i in range(1, 20)]
        long_paragraph = " ".join(sentences)
        
        chunks = translator._split_text_into_chunks(long_paragraph, max_chars=100)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 100 for chunk in chunks)
        assert all("sentence" in chunk for chunk in chunks)
    
    @pytest.mark.unit
    def test_split_text_whitespace_handling(self):
        """Test text splitting with various whitespace scenarios."""
        translator = HistoricalTranslator()
        
        # Text with extra whitespace
        text = "Para 1.\n\n\n\nPara 2.\n\n   \n\nPara 3."
        chunks = translator._split_text_into_chunks(text, max_chars=20)
        
        assert len(chunks) == 3
        assert all(chunk.strip() for chunk in chunks)  # No empty or whitespace-only chunks
    
    @pytest.mark.unit
    def test_split_text_optimal_balancing(self):
        """Test optimal balancing when remaining text can be split evenly."""
        translator = HistoricalTranslator()
        
        # Create text that can be split into exactly 2 balanced chunks
        text = "\n\n".join([f"Short para {i}." for i in range(1, 5)])
        
        chunks = translator._split_text_into_chunks(text, max_chars=100)
        
        assert len(chunks) == 2
        # Both chunks should be reasonably balanced
        assert abs(len(chunks[0]) - len(chunks[1])) < 20
    
    @pytest.mark.unit
    def test_split_text_sentence_boundary_preservation(self):
        """Test that sentence boundaries are preserved in splits."""
        translator = HistoricalTranslator()
        
        # Long text with clear sentence boundaries
        text = "First sentence. Second sentence! Third sentence? Fourth sentence."
        chunks = translator._split_text_into_chunks(text, max_chars=30)
        
        assert len(chunks) > 1
        # Each chunk should end with proper punctuation
        for chunk in chunks:
            assert chunk.strip().endswith(('.', '!', '?'))
    
    @pytest.mark.unit
    def test_split_text_no_sentences(self):
        """Test splitting text with no sentence boundaries."""
        translator = HistoricalTranslator()
        
        # Text without sentence boundaries
        text = "This is a very long text without any sentence boundaries that should be split based on word boundaries when no other option is available"
        chunks = translator._split_text_into_chunks(text, max_chars=50)
        
        # Should still split somehow
        assert len(chunks) >= 1
        assert all(len(chunk) <= 50 for chunk in chunks)


class TestLanguageNormalizationAdvanced:
    """Test advanced language normalization scenarios."""
    
    @pytest.mark.unit
    def test_normalize_language_code_case_insensitive(self):
        """Test language normalization is case insensitive."""
        translator = HistoricalTranslator()
        
        # Test various cases
        assert translator._normalize_language_code('EN', 'deepl') == 'EN-US'
        assert translator._normalize_language_code('En', 'deepl') == 'EN-US'
        assert translator._normalize_language_code('eN', 'deepl') == 'EN-US'
        
        assert translator._normalize_language_code('HEB', 'microsoft') == 'he'
        assert translator._normalize_language_code('Heb', 'microsoft') == 'he'
    
    @pytest.mark.unit
    def test_normalize_language_code_unknown_provider(self):
        """Test language normalization with unknown provider."""
        translator = HistoricalTranslator()
        
        # Should return original language code
        assert translator._normalize_language_code('en', 'unknown') == 'en'
        assert translator._normalize_language_code('DE', 'unknown') == 'DE'
    
    @pytest.mark.unit
    def test_normalize_language_code_empty_input(self):
        """Test language normalization with empty input."""
        translator = HistoricalTranslator()
        
        assert translator._normalize_language_code('', 'deepl') == ''
        assert translator._normalize_language_code(None, 'deepl') is None
    
    @pytest.mark.unit
    def test_normalize_language_code_unmapped_language(self):
        """Test normalization of languages not in mapping."""
        translator = HistoricalTranslator()
        
        # DeepL should uppercase unmapped languages
        assert translator._normalize_language_code('ja', 'deepl') == 'JA'
        assert translator._normalize_language_code('ru', 'deepl') == 'RU'
        
        # Microsoft/OpenAI should keep unmapped languages as-is
        assert translator._normalize_language_code('ja', 'microsoft') == 'ja'
        assert translator._normalize_language_code('ru', 'openai') == 'ru'


class TestValidationAdvanced:
    """Test advanced validation scenarios."""
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_hebrew_mixed_content(self):
        """Test Hebrew validation with mixed content."""
        translator = HistoricalTranslator()
        
        # Mixed Hebrew and English
        assert translator.validate_hebrew_translation("Hello שלום World עולם")
        
        # Mixed Hebrew and numbers
        assert translator.validate_hebrew_translation("123 שלום 456")
        
        # Mixed Hebrew and punctuation
        assert translator.validate_hebrew_translation("שלום! עולם?")
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_hebrew_edge_cases(self):
        """Test Hebrew validation edge cases."""
        translator = HistoricalTranslator()
        
        # Empty string
        assert not translator.validate_hebrew_translation("")
        
        # None
        assert not translator.validate_hebrew_translation(None)
        
        # Only punctuation
        assert not translator.validate_hebrew_translation("!@#$%^&*()")
        
        # Only numbers
        assert not translator.validate_hebrew_translation("123456789")
        
        # Only spaces
        assert not translator.validate_hebrew_translation("   ")
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_hebrew_unicode_ranges(self):
        """Test Hebrew validation with different Hebrew Unicode ranges."""
        translator = HistoricalTranslator()
        
        # Basic Hebrew block (U+0590-U+05FF)
        assert translator.validate_hebrew_translation("\u0590\u05FF")  # Edge characters
        assert translator.validate_hebrew_translation("\u05D0\u05E9")  # Aleph and Shin
        
        # Hebrew characters at boundaries
        assert translator.validate_hebrew_translation("\u0590")  # First Hebrew character
        assert translator.validate_hebrew_translation("\u05FF")  # Last Hebrew character
        
        # Just outside Hebrew range
        assert not translator.validate_hebrew_translation("\u058F")  # Before Hebrew
        assert not translator.validate_hebrew_translation("\u0600")  # After Hebrew
    
    @pytest.mark.unit
    def test_is_same_language_case_insensitive(self):
        """Test language comparison is case insensitive."""
        translator = HistoricalTranslator()
        
        assert translator.is_same_language('EN', 'en')
        assert translator.is_same_language('En', 'eN')
        assert translator.is_same_language('ENGLISH', 'english')
        assert translator.is_same_language('HEB', 'heb')
        assert translator.is_same_language('Hebrew', 'HEBREW')
    
    @pytest.mark.unit
    def test_is_same_language_equivalence_groups(self):
        """Test language equivalence groups work correctly."""
        translator = HistoricalTranslator()
        
        # English group
        assert translator.is_same_language('en', 'eng')
        assert translator.is_same_language('eng', 'english')
        assert translator.is_same_language('en', 'english')
        
        # German group
        assert translator.is_same_language('de', 'deu')
        assert translator.is_same_language('deu', 'ger')
        assert translator.is_same_language('de', 'german')
        
        # Hebrew group
        assert translator.is_same_language('he', 'heb')
        assert translator.is_same_language('heb', 'hebrew')
        assert translator.is_same_language('he', 'hebrew')
    
    @pytest.mark.unit
    def test_is_same_language_unknown_languages(self):
        """Test language comparison with unknown languages."""
        translator = HistoricalTranslator()
        
        # Same unknown language
        assert translator.is_same_language('ja', 'ja')
        assert translator.is_same_language('ru', 'ru')
        
        # Different unknown languages
        assert not translator.is_same_language('ja', 'ru')
        assert not translator.is_same_language('fr', 'es')
        
        # Known vs unknown
        assert not translator.is_same_language('en', 'ja')
        assert not translator.is_same_language('fr', 'english')


class TestErrorHandlingAdvanced:
    """Test advanced error handling scenarios."""
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_microsoft_api_http_error(self, mock_post):
        """Test Microsoft API HTTP error handling."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Mock HTTP error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 403 Forbidden")
        mock_post.return_value = mock_response
        
        # Should raise exception due to retry decorator
        with pytest.raises(Exception, match="HTTP 403 Forbidden"):
            translator._call_microsoft_api("Hello", "fr", None)
    
    @pytest.mark.unit
    @patch('scribe.translate.requests.post')
    def test_microsoft_api_network_error(self, mock_post):
        """Test Microsoft API network error handling."""
        translator = HistoricalTranslator()
        translator.providers['microsoft'] = {
            'api_key': 'test_key',
            'location': 'global'
        }
        
        # Mock network error
        mock_post.side_effect = Exception("Network error")
        
        # Should raise exception after retries
        with pytest.raises(Exception, match="Network error"):
            translator._call_microsoft_api("Hello", "fr", None)
        
        # Should have made 3 attempts due to retry decorator
        assert mock_post.call_count == 3
    
    @pytest.mark.unit
    def test_openai_api_model_error(self):
        """Test OpenAI API model error handling."""
        translator = HistoricalTranslator()
        translator.providers['openai'] = True
        
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("Model not found")
        
        translator.openai_client = mock_client
        
        # Should raise exception after retries
        with pytest.raises(Exception, match="Model not found"):
            translator._call_openai_api("System prompt", "Hello world")
        
        # Should have made 3 attempts due to retry decorator
        assert mock_client.chat.completions.create.call_count == 3
    
    @pytest.mark.unit
    def test_translate_with_no_providers(self):
        """Test translation when no providers are available."""
        translator = HistoricalTranslator()
        translator.providers = {}  # No providers
        
        result = translator.translate("Hello", "de")
        
        assert result is None
    
    @pytest.mark.unit
    def test_batch_translate_with_no_providers(self):
        """Test batch translation when no providers are available."""
        translator = HistoricalTranslator()
        translator.providers = {}  # No providers
        
        result = translator.batch_translate(["Hello", "World"], "de")
        
        assert result == ['', '']  # Empty strings for each input
    
    @pytest.mark.unit
    def test_hebrew_no_capable_provider_batch(self):
        """Test Hebrew batch translation with no capable provider."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}  # Only DeepL, no Hebrew support
        
        result = translator.batch_translate(["Hello", "World"], "he")
        
        assert result == ['', '']  # Empty strings for each input
    
    @pytest.mark.unit
    def test_translate_with_invalid_language_code(self):
        """Test translation with invalid language code."""
        translator = HistoricalTranslator()
        translator.providers = {'deepl': Mock()}
        
        with patch.object(translator, '_translate_deepl', return_value="Translated") as mock_deepl:
            result = translator.translate("Hello", "invalid_lang")
            
            # Should still attempt translation
            assert result == "Translated"
            mock_deepl.assert_called_once()


class TestRetryDecoratorAdvanced:
    """Test advanced retry decorator scenarios."""
    
    @pytest.mark.unit
    @patch('time.sleep')
    def test_retry_specific_exception_types(self, mock_sleep):
        """Test retry only catches specified exception types."""
        mock_func = Mock(side_effect=[ValueError("value error"), "success"])
        
        @retry(tries=3, delay=0.01, exceptions=(ValueError,))
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 2
    
    @pytest.mark.unit
    @patch('time.sleep')
    def test_retry_unhandled_exception(self, mock_sleep):
        """Test retry doesn't catch unhandled exception types."""
        mock_func = Mock(side_effect=RuntimeError("runtime error"))
        
        @retry(tries=3, delay=0.01, exceptions=(ValueError,))
        def test_func():
            return mock_func()
        
        with pytest.raises(RuntimeError, match="runtime error"):
            test_func()
        
        # Should not retry for unhandled exception
        assert mock_func.call_count == 1
    
    @pytest.mark.unit
    @patch('time.sleep')
    def test_retry_return_on_failure_none(self, mock_sleep):
        """Test retry returns None on failure when return_on_failure=None."""
        mock_func = Mock(side_effect=Exception("persistent failure"))
        
        @retry(tries=2, delay=0.01, return_on_failure=None)
        def test_func():
            return mock_func()
        
        # Should re-raise the exception, not return None
        with pytest.raises(Exception, match="persistent failure"):
            test_func()
        
        assert mock_func.call_count == 2
    
    @pytest.mark.unit
    @patch('time.sleep')
    def test_retry_return_on_failure_custom(self, mock_sleep):
        """Test retry with custom return value on failure."""
        mock_func = Mock(side_effect=Exception("persistent failure"))
        
        @retry(tries=2, delay=0.01, return_on_failure="default_value")
        def test_func():
            return mock_func()
        
        # Should re-raise the exception regardless of return_on_failure
        with pytest.raises(Exception, match="persistent failure"):
            test_func()
        
        assert mock_func.call_count == 2
    
    @pytest.mark.unit
    @patch('time.sleep')
    def test_retry_backoff_progression(self, mock_sleep):
        """Test retry backoff progression works correctly."""
        mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), Exception("fail")])
        
        @retry(tries=3, delay=0.5, backoff=3)
        def test_func():
            return mock_func()
        
        with pytest.raises(Exception, match="fail"):
            test_func()
        
        # Check sleep progression: 0.5, 1.5 (0.5 * 3)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(0.5), call(1.5)])
