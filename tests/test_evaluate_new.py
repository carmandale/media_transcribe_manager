#!/usr/bin/env python3
"""
Comprehensive test suite for the evaluate module.
Tests cover all functionality including Hebrew-specific evaluation, language detection,
and historical accuracy assessment.
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import re

from scribe.evaluate import (
    contains_hebrew,
    detect_language_ratio,
    validate_hebrew_translation,
    HistoricalEvaluator,
    evaluate_translation,
    evaluate_file
)


class TestHebrewUtilities(unittest.TestCase):
    """Test Hebrew language detection and validation utilities."""
    
    def test_contains_hebrew_true(self):
        """Test Hebrew character detection - positive cases."""
        # Pure Hebrew text
        self.assertTrue(contains_hebrew("שלום עולם"))
        self.assertTrue(contains_hebrew("זה טקסט בעברית"))
        
        # Mixed text with Hebrew
        self.assertTrue(contains_hebrew("Hello שלום World"))
        self.assertTrue(contains_hebrew("This is Hebrew: זה עברית"))
        
        # Hebrew with punctuation
        self.assertTrue(contains_hebrew("שלום, עולם!"))
        
        # Hebrew with numbers
        self.assertTrue(contains_hebrew("שלום 123 עולם"))
        
        # Extended Hebrew ranges
        self.assertTrue(contains_hebrew("שלום\uFB1D\uFB4F"))  # Hebrew presentation forms
    
    def test_contains_hebrew_false(self):
        """Test Hebrew character detection - negative cases."""
        # Pure English text
        self.assertFalse(contains_hebrew("Hello World"))
        self.assertFalse(contains_hebrew("This is English text"))
        
        # German text
        self.assertFalse(contains_hebrew("Guten Tag"))
        self.assertFalse(contains_hebrew("Das ist deutscher Text"))
        
        # Empty and whitespace
        self.assertFalse(contains_hebrew(""))
        self.assertFalse(contains_hebrew("   "))
        self.assertFalse(contains_hebrew("\n\t"))
        
        # Numbers and punctuation only
        self.assertFalse(contains_hebrew("123456"))
        self.assertFalse(contains_hebrew("!@#$%^&*()"))
        
        # Other non-Latin scripts (Arabic, but not Hebrew)
        self.assertFalse(contains_hebrew("مرحبا"))  # Arabic
    
    def test_detect_language_ratio_pure_hebrew(self):
        """Test language ratio detection for pure Hebrew text."""
        # Pure Hebrew
        ratio = detect_language_ratio("שלום עולם")
        self.assertEqual(ratio, 1.0)
        
        # Hebrew with spaces and punctuation (should still be 1.0)
        ratio = detect_language_ratio("שלום, עולם!")
        self.assertEqual(ratio, 1.0)
        
        # Hebrew with numbers (should still be 1.0)
        ratio = detect_language_ratio("שלום 123 עולם")
        self.assertEqual(ratio, 1.0)
    
    def test_detect_language_ratio_pure_latin(self):
        """Test language ratio detection for pure Latin text."""
        # Pure English
        ratio = detect_language_ratio("Hello World")
        self.assertEqual(ratio, 0.0)
        
        # English with punctuation
        ratio = detect_language_ratio("Hello, World!")
        self.assertEqual(ratio, 0.0)
        
        # English with numbers
        ratio = detect_language_ratio("Hello 123 World")
        self.assertEqual(ratio, 0.0)
    
    def test_detect_language_ratio_mixed(self):
        """Test language ratio detection for mixed text."""
        # Equal Hebrew and English
        ratio = detect_language_ratio("Hello שלום")
        self.assertEqual(ratio, 0.5)
        
        # More Hebrew than English
        ratio = detect_language_ratio("שלום עולם Hello")
        self.assertAlmostEqual(ratio, 2/3, places=2)
        
        # More English than Hebrew
        ratio = detect_language_ratio("Hello World שלום")
        self.assertAlmostEqual(ratio, 1/3, places=2)
    
    def test_detect_language_ratio_no_alpha(self):
        """Test language ratio detection with no alphabetic characters."""
        # Only punctuation
        ratio = detect_language_ratio("!@#$%^&*()")
        self.assertEqual(ratio, 0.0)
        
        # Only numbers
        ratio = detect_language_ratio("123456")
        self.assertEqual(ratio, 0.0)
        
        # Empty string
        ratio = detect_language_ratio("")
        self.assertEqual(ratio, 0.0)
        
        # Only whitespace
        ratio = detect_language_ratio("   ")
        self.assertEqual(ratio, 0.0)
    
    def test_validate_hebrew_translation_valid(self):
        """Test Hebrew translation validation - valid cases."""
        # Valid Hebrew translation
        result = validate_hebrew_translation("שלום עולם זה תרגום טוב בעברית")
        
        self.assertTrue(result['is_valid'])
        self.assertTrue(result['has_hebrew'])
        self.assertEqual(result['hebrew_ratio'], 1.0)
        self.assertGreater(result['word_count'], 10)
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['warnings'], [])
    
    def test_validate_hebrew_translation_short_but_valid(self):
        """Test Hebrew translation validation - short but valid."""
        # Short Hebrew translation (should have warning but be valid)
        result = validate_hebrew_translation("שלום עולם")
        
        self.assertTrue(result['is_valid'])
        self.assertTrue(result['has_hebrew'])
        self.assertEqual(result['hebrew_ratio'], 1.0)
        self.assertEqual(result['word_count'], 2)
        self.assertEqual(result['issues'], [])
        self.assertIn('SHORT_TRANSLATION_2_WORDS', result['warnings'])
    
    def test_validate_hebrew_translation_no_hebrew(self):
        """Test Hebrew translation validation - no Hebrew characters."""
        # English text passed as Hebrew translation
        result = validate_hebrew_translation("This is English text, not Hebrew")
        
        self.assertFalse(result['is_valid'])
        self.assertFalse(result['has_hebrew'])
        self.assertEqual(result['hebrew_ratio'], 0.0)
        self.assertIn('NO_HEBREW_CHARACTERS', result['issues'])
    
    def test_validate_hebrew_translation_low_hebrew_ratio(self):
        """Test Hebrew translation validation - low Hebrew ratio."""
        # Mixed text with low Hebrew ratio
        result = validate_hebrew_translation("This is mostly English with שלום")
        
        self.assertFalse(result['is_valid'])  # No Hebrew characters issue
        self.assertTrue(result['has_hebrew'])
        self.assertLess(result['hebrew_ratio'], 0.3)
        self.assertIn('NO_HEBREW_CHARACTERS', result['issues'])
    
    def test_validate_hebrew_translation_placeholder_detected(self):
        """Test Hebrew translation validation - placeholder detection."""
        # Various placeholder patterns
        placeholders = [
            "[HEBREW TRANSLATION]",
            "[Hebrew translation]",
            "[NOT AVAILABLE]",
            "Translation not available",
            "hebrew translation",
            "[Hebrew Translation Not Available]"
        ]
        
        for placeholder in placeholders:
            result = validate_hebrew_translation(placeholder)
            
            self.assertFalse(result['is_valid'])
            self.assertIn('TRANSLATION_PLACEHOLDER_DETECTED', result['issues'])
    
    def test_validate_hebrew_translation_mixed_with_moderate_ratio(self):
        """Test Hebrew translation validation - mixed with moderate ratio."""
        # Mixed text with moderate Hebrew ratio
        result = validate_hebrew_translation("שלום עולם Hello World")
        
        self.assertTrue(result['is_valid'])  # Should be valid since it has Hebrew
        self.assertTrue(result['has_hebrew'])
        self.assertEqual(result['hebrew_ratio'], 0.5)
        self.assertIn('MODERATE_HEBREW_RATIO_50%', result['warnings'])


class TestHistoricalEvaluator(unittest.TestCase):
    """Test HistoricalEvaluator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.evaluator = HistoricalEvaluator()
    
    def test_evaluator_initialization_default(self):
        """Test evaluator initialization with default model."""
        evaluator = HistoricalEvaluator()
        self.assertEqual(evaluator.model, "gpt-4")
        # Client initialization depends on openai being available
    
    def test_evaluator_initialization_custom_model(self):
        """Test evaluator initialization with custom model."""
        evaluator = HistoricalEvaluator(model="gpt-4-1106-preview")
        self.assertEqual(evaluator.model, "gpt-4-1106-preview")
    
    @patch('scribe.evaluate.openai')
    def test_evaluator_initialization_with_openai(self, mock_openai):
        """Test evaluator initialization with OpenAI available."""
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        evaluator = HistoricalEvaluator()
        self.assertEqual(evaluator.client, mock_client)
        mock_openai.OpenAI.assert_called_once()
    
    def test_evaluator_initialization_without_openai(self):
        """Test evaluator initialization without OpenAI."""
        with patch('scribe.evaluate.openai', None):
            evaluator = HistoricalEvaluator()
            self.assertIsNone(evaluator.client)
    
    def test_get_score_general_evaluation(self):
        """Test get_score method for general evaluation."""
        result = {
            'scores': {
                'content_accuracy': 8.5,
                'speech_pattern_fidelity': 7.0,
                'cultural_context': 6.0,
                'overall_historical_reliability': 8.0
            }
        }
        
        # Calculate expected score using weights
        expected_score = (8.5 * 0.4) + (7.0 * 0.3) + (6.0 * 0.15) + (8.0 * 0.15)
        expected_score = expected_score  # 7.6
        
        score = self.evaluator.get_score(result)
        self.assertAlmostEqual(score, expected_score, places=2)
    
    def test_get_score_hebrew_evaluation(self):
        """Test get_score method for Hebrew evaluation."""
        result = {
            'scores': {
                'content_accuracy': 9.0,
                'speech_pattern_fidelity': 8.0,
                'hebrew_language_quality': 7.5,
                'cultural_context': 8.5,
                'historical_authenticity': 9.0
            }
        }
        
        # Calculate expected score using Hebrew weights
        expected_score = (9.0 * 0.3) + (8.0 * 0.25) + (7.5 * 0.2) + (8.5 * 0.15) + (9.0 * 0.1)
        expected_score = expected_score  # 8.375
        
        score = self.evaluator.get_score(result)
        self.assertAlmostEqual(score, expected_score, places=2)
    
    def test_get_score_missing_scores(self):
        """Test get_score with missing scores."""
        result = {'scores': {}}
        
        score = self.evaluator.get_score(result)
        self.assertEqual(score, 0.0)
    
    def test_get_score_invalid_result(self):
        """Test get_score with invalid result structure."""
        result = {}
        
        score = self.evaluator.get_score(result)
        self.assertEqual(score, 0.0)
    
    def test_get_speech_pattern_score_general(self):
        """Test get_speech_pattern_score for general evaluation."""
        result = {
            'scores': {
                'speech_pattern_fidelity': 8.5
            }
        }
        
        score = self.evaluator.get_speech_pattern_score(result)
        self.assertEqual(score, 8.5)
    
    def test_get_speech_pattern_score_missing(self):
        """Test get_speech_pattern_score with missing score."""
        result = {'scores': {}}
        
        score = self.evaluator.get_speech_pattern_score(result)
        self.assertEqual(score, 0.0)
    
    def test_read_text_valid_file(self):
        """Test _read_text with valid file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is test content for reading.")
            temp_path = Path(f.name)
        
        try:
            text = self.evaluator._read_text(temp_path, max_chars=1000)
            self.assertEqual(text, "This is test content for reading.")
        finally:
            temp_path.unlink()
    
    def test_read_text_with_max_chars(self):
        """Test _read_text with character limit."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a very long text that should be truncated.")
            temp_path = Path(f.name)
        
        try:
            text = self.evaluator._read_text(temp_path, max_chars=10)
            self.assertEqual(text, "This is a ")
        finally:
            temp_path.unlink()
    
    def test_read_text_nonexistent_file(self):
        """Test _read_text with non-existent file."""
        nonexistent_path = Path("/nonexistent/file.txt")
        
        text = self.evaluator._read_text(nonexistent_path, max_chars=1000)
        self.assertIsNone(text)
    
    def test_read_text_empty_file(self):
        """Test _read_text with empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            text = self.evaluator._read_text(temp_path, max_chars=1000)
            self.assertEqual(text, "")
        finally:
            temp_path.unlink()
    
    @patch('scribe.evaluate.openai')
    def test_evaluate_success(self, mock_openai):
        """Test successful evaluation."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({
            'scores': {
                'content_accuracy': 8.5,
                'speech_pattern_fidelity': 7.0,
                'cultural_context': 6.0,
                'overall_historical_reliability': 8.0
            },
            'composite_score': 7.6,
            'strengths': ['Good content accuracy'],
            'issues': [],
            'suitability': 'Good for historical research'
        })
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client
        
        evaluator = HistoricalEvaluator()
        
        result = evaluator.evaluate("Original text", "Translation text")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['composite_score'], 7.6)
        self.assertEqual(result['strengths'], ['Good content accuracy'])
        self.assertEqual(result['suitability'], 'Good for historical research')
    
    @patch('scribe.evaluate.openai')
    def test_evaluate_hebrew_enhanced(self, mock_openai):
        """Test Hebrew evaluation with enhanced mode."""
        # Mock OpenAI response for Hebrew
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({
            'scores': {
                'content_accuracy': 9.0,
                'speech_pattern_fidelity': 8.0,
                'hebrew_language_quality': 7.5,
                'cultural_context': 8.5,
                'historical_authenticity': 9.0
            },
            'composite_score': 8.4,
            'strengths': ['Excellent Hebrew quality'],
            'issues': [],
            'hebrew_specific_notes': 'Good Hebrew grammar and vocabulary',
            'suitability': 'Excellent for historical research'
        })
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client
        
        evaluator = HistoricalEvaluator()
        
        result = evaluator.evaluate("Original text", "שלום עולם זה תרגום טוב", language="he", enhanced=True)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['composite_score'], 8.4)
        self.assertIn('hebrew_specific_notes', result)
        self.assertEqual(result['hebrew_specific_notes'], 'Good Hebrew grammar and vocabulary')
    
    @patch('scribe.evaluate.openai')
    def test_evaluate_hebrew_enhanced_validation_failure(self, mock_openai):
        """Test Hebrew evaluation with validation failure."""
        mock_openai.OpenAI.return_value = Mock()
        
        evaluator = HistoricalEvaluator()
        
        # Test with placeholder text that should fail validation
        result = evaluator.evaluate("Original text", "[HEBREW TRANSLATION]", language="he", enhanced=True)
        
        self.assertIsNotNone(result)
        self.assertIn('validation_failed', result)
        self.assertIn('validation_issues', result)
        self.assertIn('TRANSLATION_PLACEHOLDER_DETECTED', result['validation_issues'])
    
    def test_evaluate_no_openai_client(self):
        """Test evaluation without OpenAI client."""
        evaluator = HistoricalEvaluator()
        evaluator.client = None
        
        result = evaluator.evaluate("Original text", "Translation text")
        self.assertIsNone(result)
    
    @patch('scribe.evaluate.openai')
    def test_evaluate_openai_error(self, mock_openai):
        """Test evaluation with OpenAI error."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.OpenAI.return_value = mock_client
        
        evaluator = HistoricalEvaluator()
        
        result = evaluator.evaluate("Original text", "Translation text")
        self.assertIsNone(result)
    
    @patch('scribe.evaluate.openai')
    def test_evaluate_invalid_json_response(self, mock_openai):
        """Test evaluation with invalid JSON response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Invalid JSON response"
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client
        
        evaluator = HistoricalEvaluator()
        
        result = evaluator.evaluate("Original text", "Translation text")
        self.assertIsNone(result)
    
    def test_evaluate_file_success(self):
        """Test successful file evaluation."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as original_file:
            original_file.write("Original text content")
            original_path = Path(original_file.name)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as translation_file:
            translation_file.write("Translation text content")
            translation_path = Path(translation_file.name)
        
        try:
            # Mock the evaluate method
            with patch.object(self.evaluator, 'evaluate') as mock_evaluate:
                mock_evaluate.return_value = {'composite_score': 8.0}
                
                result = self.evaluator.evaluate_file(original_path, translation_path)
                
                self.assertIsNotNone(result)
                self.assertEqual(result['composite_score'], 8.0)
                mock_evaluate.assert_called_once_with(
                    "Original text content", 
                    "Translation text content",
                    language="auto",
                    enhanced=False
                )
        finally:
            original_path.unlink()
            translation_path.unlink()
    
    def test_evaluate_file_missing_original(self):
        """Test file evaluation with missing original file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as translation_file:
            translation_file.write("Translation text content")
            translation_path = Path(translation_file.name)
        
        try:
            nonexistent_path = Path("/nonexistent/original.txt")
            
            result = self.evaluator.evaluate_file(nonexistent_path, translation_path)
            self.assertIsNone(result)
        finally:
            translation_path.unlink()
    
    def test_evaluate_file_missing_translation(self):
        """Test file evaluation with missing translation file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as original_file:
            original_file.write("Original text content")
            original_path = Path(original_file.name)
        
        try:
            nonexistent_path = Path("/nonexistent/translation.txt")
            
            result = self.evaluator.evaluate_file(original_path, nonexistent_path)
            self.assertIsNone(result)
        finally:
            original_path.unlink()


class TestModuleFunctions(unittest.TestCase):
    """Test module-level functions."""
    
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_translation_success(self, mock_evaluator_class):
        """Test evaluate_translation function success."""
        # Mock evaluator
        mock_evaluator = Mock()
        mock_result = {
            'composite_score': 8.5,
            'scores': {'content_accuracy': 9.0},
            'strengths': ['Good accuracy']
        }
        mock_evaluator.evaluate.return_value = mock_result
        mock_evaluator.get_score.return_value = 8.5
        mock_evaluator_class.return_value = mock_evaluator
        
        score, details = evaluate_translation("Original", "Translation")
        
        self.assertEqual(score, 8.5)
        self.assertEqual(details, mock_result)
        mock_evaluator_class.assert_called_once_with("gpt-4")
        mock_evaluator.evaluate.assert_called_once_with("Original", "Translation", "auto", False)
    
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_translation_with_params(self, mock_evaluator_class):
        """Test evaluate_translation function with parameters."""
        mock_evaluator = Mock()
        mock_result = {'composite_score': 9.0}
        mock_evaluator.evaluate.return_value = mock_result
        mock_evaluator.get_score.return_value = 9.0
        mock_evaluator_class.return_value = mock_evaluator
        
        score, details = evaluate_translation(
            "Original", 
            "Translation", 
            model="gpt-4-1106-preview",
            language="he",
            enhanced=True
        )
        
        self.assertEqual(score, 9.0)
        mock_evaluator_class.assert_called_once_with("gpt-4-1106-preview")
        mock_evaluator.evaluate.assert_called_once_with("Original", "Translation", "he", True)
    
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_translation_failure(self, mock_evaluator_class):
        """Test evaluate_translation function failure."""
        mock_evaluator = Mock()
        mock_evaluator.evaluate.return_value = None
        mock_evaluator_class.return_value = mock_evaluator
        
        score, details = evaluate_translation("Original", "Translation")
        
        self.assertEqual(score, 0.0)
        self.assertEqual(details, {})
    
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_file_success(self, mock_evaluator_class):
        """Test evaluate_file function success."""
        mock_evaluator = Mock()
        mock_result = {'composite_score': 7.5}
        mock_evaluator.evaluate_file.return_value = mock_result
        mock_evaluator.get_score.return_value = 7.5
        mock_evaluator_class.return_value = mock_evaluator
        
        score, details = evaluate_file("original.txt", "translation.txt")
        
        self.assertEqual(score, 7.5)
        self.assertEqual(details, mock_result)
        mock_evaluator_class.assert_called_once_with("gpt-4")
        mock_evaluator.evaluate_file.assert_called_once_with(
            Path("original.txt"), 
            Path("translation.txt"),
            2500,
            "auto",
            False
        )
    
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_file_with_params(self, mock_evaluator_class):
        """Test evaluate_file function with parameters."""
        mock_evaluator = Mock()
        mock_result = {'composite_score': 8.0}
        mock_evaluator.evaluate_file.return_value = mock_result
        mock_evaluator.get_score.return_value = 8.0
        mock_evaluator_class.return_value = mock_evaluator
        
        score, details = evaluate_file(
            "original.txt", 
            "translation.txt",
            model="gpt-4-1106-preview",
            language="he",
            enhanced=True
        )
        
        self.assertEqual(score, 8.0)
        mock_evaluator_class.assert_called_once_with("gpt-4-1106-preview")
        mock_evaluator.evaluate_file.assert_called_once_with(
            Path("original.txt"), 
            Path("translation.txt"),
            2500,
            "he",
            True
        )
    
    @patch('scribe.evaluate.HistoricalEvaluator')
    def test_evaluate_file_failure(self, mock_evaluator_class):
        """Test evaluate_file function failure."""
        mock_evaluator = Mock()
        mock_evaluator.evaluate_file.return_value = None
        mock_evaluator_class.return_value = mock_evaluator
        
        score, details = evaluate_file("original.txt", "translation.txt")
        
        self.assertEqual(score, 0.0)
        self.assertEqual(details, {})


class TestPrompts(unittest.TestCase):
    """Test evaluation prompts and their structure."""
    
    def test_hebrew_evaluation_prompt_structure(self):
        """Test Hebrew evaluation prompt contains required elements."""
        prompt = HistoricalEvaluator.HEBREW_EVALUATION_PROMPT
        
        # Check key sections
        self.assertIn("HEBREW-SPECIFIC EVALUATION CRITERIA", prompt)
        self.assertIn("SPECIAL CONSIDERATIONS FOR HEBREW", prompt)
        self.assertIn("hebrew_language_quality", prompt)
        self.assertIn("historical_authenticity", prompt)
        self.assertIn("hebrew_specific_notes", prompt)
        
        # Check JSON structure requirements
        self.assertIn("composite_score", prompt)
        self.assertIn("strengths", prompt)
        self.assertIn("issues", prompt)
        self.assertIn("suitability", prompt)
    
    def test_general_evaluation_prompt_structure(self):
        """Test general evaluation prompt contains required elements."""
        prompt = HistoricalEvaluator.EVALUATION_PROMPT
        
        # Check key sections
        self.assertIn("EVALUATION CRITERIA", prompt)
        self.assertIn("content_accuracy", prompt)
        self.assertIn("speech_pattern_fidelity", prompt)
        self.assertIn("cultural_context", prompt)
        self.assertIn("overall_historical_reliability", prompt)
        
        # Check JSON structure requirements
        self.assertIn("composite_score", prompt)
        self.assertIn("strengths", prompt)
        self.assertIn("issues", prompt)
        self.assertIn("suitability", prompt)
    
    def test_score_weights_sum(self):
        """Test that score weights sum to 1.0."""
        # General weights
        general_sum = sum(HistoricalEvaluator.SCORE_WEIGHTS.values())
        self.assertAlmostEqual(general_sum, 1.0, places=2)
        
        # Hebrew weights
        hebrew_sum = sum(HistoricalEvaluator.HEBREW_SCORE_WEIGHTS.values())
        self.assertAlmostEqual(hebrew_sum, 1.0, places=2)
    
    def test_speech_pattern_weight(self):
        """Test that speech pattern fidelity has appropriate weight."""
        # Speech pattern should be weighted at 30% for general evaluation
        general_weight = HistoricalEvaluator.SCORE_WEIGHTS["speech_pattern_fidelity"]
        self.assertEqual(general_weight, 0.3)
        
        # Speech pattern should be weighted at 25% for Hebrew evaluation
        hebrew_weight = HistoricalEvaluator.HEBREW_SCORE_WEIGHTS["speech_pattern_fidelity"]
        self.assertEqual(hebrew_weight, 0.25)


if __name__ == "__main__":
    unittest.main()