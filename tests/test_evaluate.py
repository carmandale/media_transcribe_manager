"""
Comprehensive tests for the evaluate module.

Tests cover all major functionality including:
- Hebrew language detection and validation
- Translation quality evaluation
- Enhanced Hebrew evaluation mode
- Score calculation and weighting
- File-based evaluation
- Error handling and edge cases
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

from scribe.evaluate import (
    contains_hebrew, detect_language_ratio, validate_hebrew_translation,
    HistoricalEvaluator, evaluate_translation, evaluate_file
)


class TestHebrewDetection:
    """Test Hebrew language detection utilities."""
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_contains_hebrew(self):
        """Test Hebrew character detection."""
        # Hebrew text
        assert contains_hebrew("שלום עולם")
        assert contains_hebrew("Hello שלום World")
        assert contains_hebrew("טקסט בעברית עם ניקוד")
        
        # Non-Hebrew text
        assert not contains_hebrew("Hello World")
        assert not contains_hebrew("Привет мир")  # Russian
        assert not contains_hebrew("مرحبا بالعالم")  # Arabic
        assert not contains_hebrew("")
        assert not contains_hebrew("123456")
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_detect_language_ratio(self):
        """Test Hebrew character ratio detection."""
        # Pure Hebrew
        assert detect_language_ratio("שלום עולם") == 1.0
        
        # Pure English
        assert detect_language_ratio("Hello World") == 0.0
        
        # Mixed content
        ratio = detect_language_ratio("Hello שלום World עולם")
        assert 0.4 < ratio < 0.6  # Roughly half Hebrew
        
        # Numbers only
        assert detect_language_ratio("123456") == 0.0
        
        # Empty string
        assert detect_language_ratio("") == 0.0


class TestHebrewValidation:
    """Test Hebrew translation validation."""
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_valid_hebrew(self):
        """Test validation of valid Hebrew translation."""
        result = validate_hebrew_translation("זהו תרגום מלא בעברית עם הרבה מילים")
        
        assert result['is_valid'] is True
        assert result['has_hebrew'] is True
        assert result['hebrew_ratio'] > 0.9
        assert len(result['issues']) == 0
        assert result['word_count'] > 5
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_no_hebrew(self):
        """Test validation of text without Hebrew."""
        result = validate_hebrew_translation("This is English text only")
        
        assert result['is_valid'] is False
        assert result['has_hebrew'] is False
        assert result['hebrew_ratio'] == 0.0
        assert "NO_HEBREW_CHARACTERS" in result['issues']
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_low_hebrew_ratio(self):
        """Test validation with low Hebrew ratio."""
        result = validate_hebrew_translation("This is mostly English with just שלום")
        
        assert result['is_valid'] is True  # Has Hebrew, so technically valid
        assert result['has_hebrew'] is True
        assert result['hebrew_ratio'] < 0.3
        assert any("LOW_HEBREW_RATIO" in w for w in result['warnings'])
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_placeholder_patterns(self):
        """Test detection of translation placeholders."""
        placeholders = [
            "[Hebrew translation not available]",
            "[translation pending]",
            "Hebrew translation: [TODO]",
            "Translation not available"
        ]
        
        for text in placeholders:
            result = validate_hebrew_translation(text)
            assert result['is_valid'] is False
            assert "TRANSLATION_PLACEHOLDER_DETECTED" in result['issues']
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_validate_short_translation(self):
        """Test validation of suspiciously short translations."""
        result = validate_hebrew_translation("שלום")
        
        assert result['is_valid'] is True  # Valid Hebrew, just short
        assert any("SHORT_TRANSLATION" in w for w in result['warnings'])
        assert result['word_count'] == 1


class TestHistoricalEvaluator:
    """Test main evaluator functionality."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def evaluator(self, mock_openai_client):
        """Create evaluator with mocked client."""
        with patch('scribe.evaluate.openai') as mock_openai:
            mock_openai.OpenAI.return_value = mock_openai_client
            evaluator = HistoricalEvaluator(model="gpt-4")
            evaluator.client = mock_openai_client
            return evaluator
    
    @pytest.mark.unit
    def test_evaluate_general_translation(self, evaluator, mock_openai_client):
        """Test evaluation of general (non-Hebrew) translation."""
        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps({
            "scores": {
                "content_accuracy": 9,
                "speech_pattern_fidelity": 8,
                "cultural_context": 9,
                "overall_historical_reliability": 9
            },
            "composite_score": 8.7,
            "strengths": ["Accurate facts", "Natural speech patterns"],
            "issues": [],
            "suitability": "Excellent for historical research"
        })))]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Evaluate
        result = evaluator.evaluate(
            "Well, I... I remember it was 1943",
            "Nun, ich... ich erinnere mich, es war 1943"
        )
        
        assert result is not None
        assert result['composite_score'] == 8.7
        assert result['scores']['content_accuracy'] == 9
        assert result['scores']['speech_pattern_fidelity'] == 8
        assert len(result['strengths']) == 2
        assert result['detected_language'] == 'auto'
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_evaluate_hebrew_enhanced(self, evaluator, mock_openai_client):
        """Test enhanced Hebrew evaluation."""
        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps({
            "scores": {
                "content_accuracy": 9,
                "speech_pattern_fidelity": 8,
                "hebrew_language_quality": 9,
                "cultural_context": 8,
                "historical_authenticity": 9
            },
            "composite_score": 8.6,
            "strengths": ["Excellent Hebrew", "Preserves tone"],
            "issues": [],
            "hebrew_specific_notes": "Natural Hebrew expression",
            "suitability": "Highly suitable for research"
        })))]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Evaluate with Hebrew text
        result = evaluator.evaluate(
            "Well, I remember the soldiers",
            "ובכן, אני זוכר את החיילים",
            language="he",
            enhanced=True
        )
        
        assert result is not None
        assert result['scores']['hebrew_language_quality'] == 9
        assert 'hebrew_validation' in result
        assert result['hebrew_validation']['is_valid'] is True
        assert result['detected_language'] == 'he'
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_evaluate_hebrew_failed_validation(self, evaluator, mock_openai_client):
        """Test Hebrew evaluation that fails sanity check."""
        # Evaluate with non-Hebrew text
        result = evaluator.evaluate(
            "Original text",
            "This is not Hebrew",
            language="he",
            enhanced=True
        )
        
        # Should return early with score 0
        assert result is not None
        assert result['composite_score'] == 0.0
        assert all(score == 0 for score in result['scores'].values())
        assert "NO_HEBREW_CHARACTERS" in result['issues']
        assert result['suitability'] == "Failed basic sanity check - not suitable for historical research"
    
    @pytest.mark.unit
    def test_evaluate_auto_detect_hebrew(self, evaluator, mock_openai_client):
        """Test automatic Hebrew detection."""
        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps({
            "scores": {"content_accuracy": 8},
            "composite_score": 8.0
        })))]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Evaluate with Hebrew text but auto language
        result = evaluator.evaluate(
            "Original",
            "טקסט בעברית",
            language="auto",
            enhanced=True
        )
        
        # Should auto-detect Hebrew and use Hebrew validation
        assert result is not None
        assert 'hebrew_validation' in result
        assert result['detected_language'] == 'he'
    
    @pytest.mark.unit
    def test_evaluate_truncation(self, evaluator, mock_openai_client):
        """Test text truncation for long documents."""
        # Create very long texts
        long_original = "Test sentence. " * 5000  # ~70k chars
        long_translation = "Translated sentence. " * 5000
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps({
            "scores": {"content_accuracy": 7},
            "composite_score": 7.0
        })))]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        result = evaluator.evaluate(long_original, long_translation)
        
        # Check that texts were truncated in the API call
        call_args = mock_openai_client.chat.completions.create.call_args
        prompt = call_args[1]['messages'][0]['content']
        assert "[...truncated for evaluation...]" in prompt
    
    @pytest.mark.unit
    def test_evaluate_api_error(self, evaluator, mock_openai_client):
        """Test handling of API errors."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = evaluator.evaluate("Original", "Translation")
        
        assert result is None
    
    @pytest.mark.unit
    def test_evaluate_json_response_format_fallback(self, evaluator, mock_openai_client):
        """Test fallback when JSON response format not supported."""
        # First call fails with response_format error
        mock_openai_client.chat.completions.create.side_effect = [
            Exception("response_format not supported"),
            Mock(choices=[Mock(message=Mock(content=json.dumps({
                "scores": {"content_accuracy": 8},
                "composite_score": 8.0
            })))])
        ]
        
        result = evaluator.evaluate("Original", "Translation")
        
        assert result is not None
        assert result['composite_score'] == 8.0
        
        # Should have made two calls (retry without response_format)
        assert mock_openai_client.chat.completions.create.call_count == 2
    
    @pytest.mark.unit
    def test_evaluate_invalid_json_response(self, evaluator, mock_openai_client):
        """Test handling of invalid JSON in response."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This is not valid JSON"))]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        result = evaluator.evaluate("Original", "Translation")
        
        assert result is None
    
    @pytest.mark.unit
    def test_calculate_composite_score(self, evaluator, mock_openai_client):
        """Test automatic composite score calculation."""
        # Response without composite_score
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps({
            "scores": {
                "content_accuracy": 8,
                "speech_pattern_fidelity": 7,
                "cultural_context": 9,
                "overall_historical_reliability": 8
            }
        })))]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        result = evaluator.evaluate("Original", "Translation")
        
        # Should calculate composite score using weights
        assert 'composite_score' in result
        expected = (8 * 0.4) + (7 * 0.3) + (9 * 0.15) + (8 * 0.15)
        assert abs(result['composite_score'] - expected) < 0.1
    
    @pytest.mark.unit
    def test_get_scores(self, evaluator):
        """Test score extraction methods."""
        result = {
            "composite_score": 8.5,
            "scores": {
                "speech_pattern_fidelity": 7.5,
                "content_accuracy": 9.0
            }
        }
        
        assert evaluator.get_score(result) == 8.5
        assert evaluator.get_speech_pattern_score(result) == 7.5
        
        # Test missing scores
        assert evaluator.get_score({}) == 0
        assert evaluator.get_speech_pattern_score({}) == 0


class TestFileEvaluation:
    """Test file-based evaluation functionality."""
    
    @pytest.mark.unit
    def test_evaluate_file_success(self, temp_dir):
        """Test successful file evaluation."""
        # Create test files
        original_file = temp_dir / "original.txt"
        translation_file = temp_dir / "translation.txt"
        
        original_file.write_text("Original text content")
        translation_file.write_text("Translated text content")
        
        with patch('scribe.evaluate.openai') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content=json.dumps({
                "scores": {"content_accuracy": 9},
                "composite_score": 9.0
            })))]
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.OpenAI.return_value = mock_client
            
            evaluator = HistoricalEvaluator()
            evaluator.client = mock_client
            
            result = evaluator.evaluate_file(original_file, translation_file)
            
            assert result is not None
            assert result['composite_score'] == 9.0
    
    @pytest.mark.unit
    def test_evaluate_file_not_found(self, temp_dir):
        """Test handling of missing files."""
        evaluator = HistoricalEvaluator()
        
        result = evaluator.evaluate_file(
            temp_dir / "nonexistent.txt",
            temp_dir / "translation.txt"
        )
        
        assert result is None
    
    @pytest.mark.unit
    def test_read_text_truncation(self, temp_dir):
        """Test text reading with truncation."""
        evaluator = HistoricalEvaluator()
        
        # Create file with long content
        test_file = temp_dir / "long.txt"
        long_text = "This is a sentence. " * 1000
        test_file.write_text(long_text)
        
        # Read with truncation
        text = evaluator._read_text(test_file, max_chars=100)
        
        assert text is not None
        assert len(text) <= 101  # May include trailing period
        assert text.endswith(".")  # Should end at sentence boundary
    
    @pytest.mark.unit
    def test_read_text_encoding_error(self, temp_dir):
        """Test handling of encoding errors."""
        evaluator = HistoricalEvaluator()
        
        # Create file with invalid UTF-8
        test_file = temp_dir / "bad_encoding.txt"
        test_file.write_bytes(b"Valid text \xff\xfe Invalid bytes")
        
        # Should handle encoding errors gracefully
        text = evaluator._read_text(test_file, max_chars=100)
        
        assert text is not None
        assert "Valid text" in text


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    @pytest.mark.unit
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_translation_function(self, mock_evaluator_class):
        """Test evaluate_translation convenience function."""
        mock_evaluator = Mock()
        mock_evaluator.evaluate.return_value = {
            "composite_score": 8.5,
            "scores": {"content_accuracy": 9}
        }
        mock_evaluator.get_score.return_value = 8.5
        mock_evaluator_class.return_value = mock_evaluator
        
        score, results = evaluate_translation(
            "Original text",
            "Translated text",
            model="gpt-4",
            language="de",
            enhanced=True
        )
        
        assert score == 8.5
        assert results['composite_score'] == 8.5
        
        # Verify evaluator was called correctly
        mock_evaluator_class.assert_called_once_with(model="gpt-4")
        mock_evaluator.evaluate.assert_called_once_with(
            "Original text",
            "Translated text",
            language="de",
            enhanced=True
        )
    
    @pytest.mark.unit
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_file_function(self, mock_evaluator_class):
        """Test evaluate_file convenience function."""
        mock_evaluator = Mock()
        mock_evaluator.evaluate_file.return_value = {
            "composite_score": 7.0
        }
        mock_evaluator.get_score.return_value = 7.0
        mock_evaluator_class.return_value = mock_evaluator
        
        score, results = evaluate_file(
            "/path/to/original.txt",
            "/path/to/translation.txt",
            model="gpt-3.5-turbo",
            language="he",
            enhanced=False
        )
        
        assert score == 7.0
        assert results['composite_score'] == 7.0
    
    @pytest.mark.unit
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_functions_failure(self, mock_evaluator_class):
        """Test convenience functions when evaluation fails."""
        mock_evaluator = Mock()
        mock_evaluator.evaluate.return_value = None
        mock_evaluator_class.return_value = mock_evaluator
        
        score, results = evaluate_translation("Original", "Translation")
        
        assert score == 0.0
        assert results == {}


class TestPromptGeneration:
    """Test evaluation prompt generation."""
    
    @pytest.mark.unit
    def test_general_prompt(self):
        """Test general evaluation prompt format."""
        evaluator = HistoricalEvaluator()
        
        prompt = evaluator.EVALUATION_PROMPT.format(
            original="Original text",
            translation="Translated text"
        )
        
        assert "Original text:" in prompt
        assert "Translation:" in prompt
        assert "Content Accuracy: 1-10" in prompt
        assert "Speech Pattern Fidelity: 1-10" in prompt
        assert "JSON object" in prompt
    
    @pytest.mark.unit
    @pytest.mark.hebrew
    def test_hebrew_prompt(self):
        """Test Hebrew-specific evaluation prompt."""
        evaluator = HistoricalEvaluator()
        
        prompt = evaluator.HEBREW_EVALUATION_PROMPT.format(
            original="Original text",
            translation="תרגום עברי"
        )
        
        assert "Hebrew translation:" in prompt
        assert "Hebrew Language Quality: 1-10" in prompt
        assert "Hebrew-specific" in prompt
        assert "right-to-left" in prompt
        assert "Holocaust" in prompt


class TestModelCompatibility:
    """Test compatibility with different OpenAI models."""
    
    @pytest.mark.unit
    def test_model_max_chars(self):
        """Test character limits for different models."""
        # GPT-4 models should allow more characters
        evaluator = HistoricalEvaluator(model="gpt-4")
        assert evaluator.model == "gpt-4"
        
        evaluator = HistoricalEvaluator(model="gpt-4-turbo")
        assert evaluator.model == "gpt-4-turbo"
        
        evaluator = HistoricalEvaluator(model="gpt-3.5-turbo")
        assert evaluator.model == "gpt-3.5-turbo"