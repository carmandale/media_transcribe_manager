#!/usr/bin/env python3
"""
Quality evaluation module for historical interview translations.

This module provides a clean API for evaluating translation quality with a focus on:
- Historical accuracy and content preservation
- Speech pattern fidelity (weighted at 30%)
- Cultural context preservation
- Overall reliability for historical research

The evaluation uses OpenAI's GPT-4 to score translations on a 0-10 scale.
"""

import json
import logging
import re
from typing import Dict, Optional, Tuple, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    import openai
except ImportError:
    logger.error("OpenAI package not installed. Run 'pip install openai'")
    openai = None


# Hebrew Language Detection Utilities
def contains_hebrew(text: str) -> bool:
    """
    Check if text contains Hebrew characters.
    
    Args:
        text: Text to check
        
    Returns:
        True if Hebrew characters are found, False otherwise
    """
    hebrew_pattern = re.compile(r'[\u0590-\u05FF\uFB1D-\uFB4F]')
    return bool(hebrew_pattern.search(text))


def detect_language_ratio(text: str) -> float:
    """
    Detect the ratio of Hebrew vs Latin characters in text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Ratio of Hebrew characters (0.0 = all Latin, 1.0 = all Hebrew)
    """
    hebrew_chars = len(re.findall(r'[\u0590-\u05FF\uFB1D-\uFB4F]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    total_alpha = hebrew_chars + latin_chars
    
    if total_alpha == 0:
        return 0.0
    
    return hebrew_chars / total_alpha


def validate_hebrew_translation(text: str) -> Dict[str, any]:
    """
    Perform sanity checks on Hebrew translation text.
    
    Args:
        text: Hebrew translation text to validate
        
    Returns:
        Dictionary with validation results including:
        - is_valid: Boolean indicating if translation passes basic sanity checks
        - hebrew_ratio: Ratio of Hebrew to Latin characters
        - issues: List of detected issues
        - warnings: List of warnings
    """
    issues = []
    warnings = []
    
    # Check for Hebrew characters
    has_hebrew = contains_hebrew(text)
    if not has_hebrew:
        issues.append("NO_HEBREW_CHARACTERS")
    
    # Check Hebrew character ratio
    hebrew_ratio = detect_language_ratio(text)
    if has_hebrew and hebrew_ratio < 0.3:
        warnings.append(f"LOW_HEBREW_RATIO_{hebrew_ratio:.1%}")
    elif has_hebrew and hebrew_ratio < 0.5:
        warnings.append(f"MODERATE_HEBREW_RATIO_{hebrew_ratio:.1%}")
    
    # Check for common translation placeholder patterns
    placeholder_patterns = [
        r'\[.*translation.*\]',
        r'\[.*hebrew.*\]',
        r'\[.*not.*available.*\]',
        r'translation not available',
        r'hebrew translation',
    ]
    
    for pattern in placeholder_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append("TRANSLATION_PLACEHOLDER_DETECTED")
            break
    
    # Check for suspiciously short translations
    word_count = len(text.split())
    if word_count < 10:
        warnings.append(f"SHORT_TRANSLATION_{word_count}_WORDS")
    
    # Determine if translation is valid
    is_valid = len(issues) == 0
    
    return {
        'is_valid': is_valid,
        'hebrew_ratio': hebrew_ratio,
        'has_hebrew': has_hebrew,
        'word_count': word_count,
        'issues': issues,
        'warnings': warnings
    }


class HistoricalEvaluator:
    """Evaluates translations for historical accuracy and speech pattern preservation."""
    
    # Hebrew-specific evaluation prompt
    HEBREW_EVALUATION_PROMPT = """
You are a bilingual historian specializing in Hebrew translation of oral histories and Holocaust testimonies.
Evaluate how well this Hebrew translation preserves the historical content and speech characteristics of the original testimony.

HEBREW-SPECIFIC EVALUATION CRITERIA:
1. Content Accuracy: 1-10 (10 = perfect preservation of all historical facts, names, dates, events)
2. Speech Pattern Fidelity: 1-10 (10 = maintains speaker's natural voice, hesitations, emotional inflections)
3. Hebrew Language Quality: 1-10 (10 = proper Hebrew grammar, vocabulary, and natural expression)
4. Cultural Context: 1-10 (10 = preserves cultural references, maintains historical terminology)
5. Historical Authenticity: 1-10 (10 = completely reliable for historical research and testimony preservation)

SPECIAL CONSIDERATIONS FOR HEBREW:
- Hebrew right-to-left reading flow preserved
- Proper Hebrew transliteration of names and places
- Appropriate Hebrew register (formal vs. colloquial) matching the original tone
- Preservation of emotional weight and testimony gravity
- Accurate rendering of Holocaust-specific terminology

IMPORTANT: Return your evaluation as a JSON object with this exact structure:
{{
  "scores": {{
    "content_accuracy": <number 1-10>,
    "speech_pattern_fidelity": <number 1-10>,
    "hebrew_language_quality": <number 1-10>,
    "cultural_context": <number 1-10>,
    "historical_authenticity": <number 1-10>
  }},
  "composite_score": <number 1-10>,
  "strengths": [<list of strengths>],
  "issues": [<list of issues, if any>],
  "hebrew_specific_notes": "<notes on Hebrew language quality and authenticity>",
  "suitability": "<statement on suitability for historical research>"
}}

Original text:
{original}

Hebrew translation:
{translation}

Be sure to format your response as a strict JSON object with the exact structure specified above.
"""
    
    # General evaluation prompt focused on historical accuracy
    EVALUATION_PROMPT = """
You are a bilingual historian specializing in oral histories and interview transcripts.
Evaluate how well this translation preserves the historical content and speech characteristics of the original.

EVALUATION CRITERIA:
1. Content Accuracy: 1-10 (10 = perfect preservation of all historical facts, names, dates, events)
2. Speech Pattern Fidelity: 1-10 (10 = perfectly maintains the speaker's natural voice, hesitations, filler words)
3. Cultural Context: 1-10 (10 = perfectly preserves cultural references and idioms)
4. Overall Historical Reliability: 1-10 (10 = completely reliable for historical research purposes)

IMPORTANT: Return your evaluation as a JSON object with this exact structure:
{{
  "scores": {{
    "content_accuracy": <number 1-10>,
    "speech_pattern_fidelity": <number 1-10>,
    "cultural_context": <number 1-10>,
    "overall_historical_reliability": <number 1-10>
  }},
  "composite_score": <number 1-10>,
  "strengths": [<list of strengths>],
  "issues": [<list of issues, if any>],
  "suitability": "<statement on suitability for historical research>"
}}

Original text:
{original}

Translation:
{translation}

Be sure to format your response as a strict JSON object with the exact structure specified above.
"""
    
    # Weights for composite score calculation (general)
    SCORE_WEIGHTS = {
        "content_accuracy": 0.4,
        "speech_pattern_fidelity": 0.3,
        "cultural_context": 0.15,
        "overall_historical_reliability": 0.15
    }
    
    # Hebrew-specific weights for composite score calculation
    HEBREW_SCORE_WEIGHTS = {
        "content_accuracy": 0.3,
        "speech_pattern_fidelity": 0.25,
        "hebrew_language_quality": 0.2,
        "cultural_context": 0.15,
        "historical_authenticity": 0.1
    }
    
    def __init__(self, model: str = "gpt-4"):
        """
        Initialize the evaluator.
        
        Args:
            model: OpenAI model to use for evaluation (default: gpt-4)
        """
        self.model = model
        self.client = None
        
        if openai:
            self.client = openai.OpenAI()
    
    def evaluate(self, original: str, translation: str, language: str = "auto", enhanced: bool = False) -> Optional[Dict]:
        """
        Evaluate a translation for historical accuracy.
        
        Args:
            original: The original transcript text
            translation: The translated text
            language: Target language code ('he' for Hebrew, 'auto' for auto-detection)
            enhanced: Use enhanced evaluation with sanity checks and language-specific prompts
            
        Returns:
            Dictionary with evaluation results or None if evaluation fails
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return None
        
        # Auto-detect Hebrew if language is "auto"
        if language == "auto":
            if contains_hebrew(translation):
                language = "he"
        
        # Perform Hebrew sanity checks if enhanced mode is enabled
        validation_result = None
        if enhanced and language == "he":
            validation_result = validate_hebrew_translation(translation)
            
            # If translation fails basic sanity checks, return early with score 0
            if not validation_result['is_valid']:
                logger.warning(f"Hebrew translation failed sanity check: {validation_result['issues']}")
                return {
                    "scores": {
                        "content_accuracy": 0,
                        "speech_pattern_fidelity": 0,
                        "hebrew_language_quality": 0,
                        "cultural_context": 0,
                        "historical_authenticity": 0
                    },
                    "composite_score": 0.0,
                    "strengths": [],
                    "issues": validation_result['issues'],
                    "warnings": validation_result.get('warnings', []),
                    "hebrew_validation": validation_result,
                    "suitability": "Failed basic sanity check - not suitable for historical research"
                }
        
        # Choose appropriate model and context size based on model capabilities
        max_chars = 40000 if any(x in self.model for x in ["gpt-4", "turbo"]) else 3000
        
        # Truncate texts to avoid token limits
        if len(original) > max_chars:
            original = original[:max_chars] + "\n[...truncated for evaluation...]"
        if len(translation) > max_chars:
            translation = translation[:max_chars] + "\n[...truncated for evaluation...]"
        
        # Choose prompt based on language and enhanced mode
        if enhanced and language == "he":
            prompt = self.HEBREW_EVALUATION_PROMPT.format(
                original=original,
                translation=translation
            )
            score_weights = self.HEBREW_SCORE_WEIGHTS
        else:
            prompt = self.EVALUATION_PROMPT.format(
                original=original,
                translation=translation
            )
            score_weights = self.SCORE_WEIGHTS
        
        try:
            # Try with JSON response format for compatible models
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
        except Exception as e:
            if "response_format" in str(e):
                # Fallback for models that don't support JSON response format
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You must respond with valid JSON only, no other text."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0
                    )
                except Exception as e:
                    logger.error(f"Error calling OpenAI API: {e}")
                    return None
            else:
                logger.error(f"Error calling OpenAI API: {e}")
                return None
        
        # Parse the response
        try:
            result = json.loads(response.choices[0].message.content)
            
            # Calculate composite score if not provided
            if "composite_score" not in result:
                scores = result.get("scores", {})
                composite = sum(
                    scores.get(key, 0) * weight
                    for key, weight in score_weights.items()
                )
                result["composite_score"] = round(composite, 1)
            
            # Add validation results for Hebrew if performed
            if validation_result:
                result["hebrew_validation"] = validation_result
                
                # Add warnings to the result
                if validation_result.get('warnings'):
                    result.setdefault("warnings", []).extend(validation_result['warnings'])
            
            # Add language detection info
            result["detected_language"] = language
            
            return result
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse response as JSON: {response.choices[0].message.content[:200]}...")
            return None
    
    def evaluate_file(self, original_path: Path, translation_path: Path, max_chars: int = 2500, language: str = "auto", enhanced: bool = False) -> Optional[Dict]:
        """
        Evaluate translation quality by reading from files.
        
        Args:
            original_path: Path to original transcript file
            translation_path: Path to translation file
            max_chars: Maximum characters to read from each file
            language: Target language code ('he' for Hebrew, 'auto' for auto-detection)
            enhanced: Use enhanced evaluation with sanity checks and language-specific prompts
            
        Returns:
            Dictionary with evaluation results or None if evaluation fails
        """
        # Read original text
        original = self._read_text(original_path, max_chars)
        if not original:
            logger.error(f"Failed to read original file: {original_path}")
            return None
        
        # Read translation
        translation = self._read_text(translation_path, max_chars)
        if not translation:
            logger.error(f"Failed to read translation file: {translation_path}")
            return None
        
        # Evaluate
        return self.evaluate(original, translation, language=language, enhanced=enhanced)
    
    def get_score(self, result: Dict) -> float:
        """
        Extract the composite score from evaluation results.
        
        Args:
            result: Evaluation result dictionary
            
        Returns:
            Composite score (0-10) or 0 if not found
        """
        return result.get("composite_score", 0)
    
    def get_speech_pattern_score(self, result: Dict) -> float:
        """
        Extract the speech pattern fidelity score from evaluation results.
        
        Args:
            result: Evaluation result dictionary
            
        Returns:
            Speech pattern fidelity score (0-10) or 0 if not found
        """
        scores = result.get("scores", {})
        return scores.get("speech_pattern_fidelity", 0)
    
    def _read_text(self, path: Path, max_chars: int) -> Optional[str]:
        """
        Read text from a file with truncation for large files.
        
        Args:
            path: Path to the file
            max_chars: Maximum characters to read
            
        Returns:
            Text content or None if reading fails
        """
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read(max_chars * 2)
            
            if len(text) <= max_chars:
                return text
            
            # Truncate at sentence boundary
            end = text.rfind('.', 0, max_chars)
            if end == -1:
                end = max_chars
            
            return text[:end+1]
            
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return None


def evaluate_translation(original: str, translation: str, model: str = "gpt-4", language: str = "auto", enhanced: bool = False) -> Tuple[float, Dict]:
    """
    Simple function interface for evaluating translation quality.
    
    Args:
        original: Original transcript text
        translation: Translated text
        model: OpenAI model to use (default: gpt-4)
        language: Target language code ('he' for Hebrew, 'auto' for auto-detection)
        enhanced: Use enhanced evaluation with sanity checks and language-specific prompts
        
    Returns:
        Tuple of (score, full_results) where score is 0-10
    """
    evaluator = HistoricalEvaluator(model=model)
    result = evaluator.evaluate(original, translation, language=language, enhanced=enhanced)
    
    if result:
        score = evaluator.get_score(result)
        return score, result
    else:
        return 0.0, {}


def evaluate_file(original_path: str, translation_path: str, model: str = "gpt-4", language: str = "auto", enhanced: bool = False) -> Tuple[float, Dict]:
    """
    Simple function interface for evaluating translation quality from files.
    
    Args:
        original_path: Path to original transcript file
        translation_path: Path to translation file
        model: OpenAI model to use (default: gpt-4)
        language: Target language code ('he' for Hebrew, 'auto' for auto-detection)
        enhanced: Use enhanced evaluation with sanity checks and language-specific prompts
        
    Returns:
        Tuple of (score, full_results) where score is 0-10
    """
    evaluator = HistoricalEvaluator(model=model)
    result = evaluator.evaluate_file(Path(original_path), Path(translation_path), language=language, enhanced=enhanced)
    
    if result:
        score = evaluator.get_score(result)
        return score, result
    else:
        return 0.0, {}


# Example usage
if __name__ == "__main__":
    import os
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        exit(1)
    
    # Example evaluation
    original_text = "Well, I... I remember, uh, it was in 1943, maybe '44... the soldiers came to our village."
    translation_text = "Well, I... I remember, uh, it was in 1943, maybe '44... the soldiers came to our village."
    
    score, results = evaluate_translation(original_text, translation_text)
    
    print(f"Composite Score: {score}/10")
    print(f"Speech Pattern Score: {results.get('scores', {}).get('speech_pattern_fidelity', 'N/A')}/10")
    print(f"Suitability: {results.get('suitability', 'N/A')}")