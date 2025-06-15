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
from typing import Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    import openai
except ImportError:
    logger.error("OpenAI package not installed. Run 'pip install openai'")
    openai = None


class HistoricalEvaluator:
    """Evaluates translations for historical accuracy and speech pattern preservation."""
    
    # Evaluation prompt focused on historical accuracy
    EVALUATION_PROMPT = """
You are a bilingual historian specializing in oral histories and interview transcripts.
Evaluate how well this translation preserves the historical content and speech characteristics of the original.

EVALUATION CRITERIA:
1. Content Accuracy: 1-10 (10 = perfect preservation of all historical facts, names, dates, events)
2. Speech Pattern Fidelity: 1-10 (10 = perfectly maintains the speaker's natural voice, hesitations, filler words)
3. Cultural Context: 1-10 (10 = perfectly preserves cultural references and idioms)
4. Overall Historical Reliability: 1-10 (10 = completely reliable for historical research purposes)

IMPORTANT: Return your evaluation as a JSON object with this exact structure:
{
  "scores": {
    "content_accuracy": <number 1-10>,
    "speech_pattern_fidelity": <number 1-10>,
    "cultural_context": <number 1-10>,
    "overall_historical_reliability": <number 1-10>
  },
  "composite_score": <number 1-10>,
  "strengths": [<list of strengths>],
  "issues": [<list of issues, if any>],
  "suitability": "<statement on suitability for historical research>"
}

Original text:
{original}

Translation:
{translation}

Be sure to format your response as a strict JSON object with the exact structure specified above.
"""
    
    # Weights for composite score calculation
    SCORE_WEIGHTS = {
        "content_accuracy": 0.4,
        "speech_pattern_fidelity": 0.3,
        "cultural_context": 0.15,
        "overall_historical_reliability": 0.15
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
    
    def evaluate(self, original: str, translation: str) -> Optional[Dict]:
        """
        Evaluate a translation for historical accuracy.
        
        Args:
            original: The original transcript text
            translation: The translated text
            
        Returns:
            Dictionary with evaluation results or None if evaluation fails
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return None
        
        # Format the prompt
        prompt = self.EVALUATION_PROMPT.format(
            original=original,
            translation=translation
        )
        
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
                    for key, weight in self.SCORE_WEIGHTS.items()
                )
                result["composite_score"] = round(composite, 1)
            
            return result
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse response as JSON: {response.choices[0].message.content[:200]}...")
            return None
    
    def evaluate_file(self, original_path: Path, translation_path: Path, max_chars: int = 2500) -> Optional[Dict]:
        """
        Evaluate translation quality by reading from files.
        
        Args:
            original_path: Path to original transcript file
            translation_path: Path to translation file
            max_chars: Maximum characters to read from each file
            
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
        return self.evaluate(original, translation)
    
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


def evaluate_translation(original: str, translation: str, model: str = "gpt-4") -> Tuple[float, Dict]:
    """
    Simple function interface for evaluating translation quality.
    
    Args:
        original: Original transcript text
        translation: Translated text
        model: OpenAI model to use (default: gpt-4)
        
    Returns:
        Tuple of (score, full_results) where score is 0-10
    """
    evaluator = HistoricalEvaluator(model=model)
    result = evaluator.evaluate(original, translation)
    
    if result:
        score = evaluator.get_score(result)
        return score, result
    else:
        return 0.0, {}


def evaluate_file(original_path: str, translation_path: str, model: str = "gpt-4") -> Tuple[float, Dict]:
    """
    Simple function interface for evaluating translation quality from files.
    
    Args:
        original_path: Path to original transcript file
        translation_path: Path to translation file
        model: OpenAI model to use (default: gpt-4)
        
    Returns:
        Tuple of (score, full_results) where score is 0-10
    """
    evaluator = HistoricalEvaluator(model=model)
    result = evaluator.evaluate_file(Path(original_path), Path(translation_path))
    
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