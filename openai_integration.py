#!/usr/bin/env python3
"""
OpenAI API integration for Hebrew translation.
Provides robust, production-ready API integration with proper error handling, 
rate limiting, and cost tracking.
"""

import os
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable
from dataclasses import dataclass, asdict

import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model pricing per 1M tokens (updated June 2025)
PRICING = {
    "gpt-4.5-preview": {"input": 75.0, "output": 150.0},  # DO NOT USE - retiring July 14, 2025
    "gpt-4-turbo-preview": {"input": 10.0, "output": 30.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4.1": {"input": 2.0, "output": 8.0},  # RECOMMENDED
    "gpt-4.1-mini": {"input": 0.4, "output": 1.6},
    "gpt-4o": {"input": 5.0, "output": 20.0},
    "gpt-4o-mini": {"input": 0.6, "output": 2.4},
    "gpt-4-0125-preview": {"input": 10.0, "output": 30.0},  # Fallback
}


@dataclass
class APIUsageStats:
    """Track OpenAI API usage and costs."""
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    errors: List[Dict] = None
    last_cost_warning: float = 0.0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Calculate cost for a request."""
        pricing = PRICING.get(model, PRICING["gpt-4-0125-preview"])  # Default fallback
        
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost
    
    def update(self, prompt_tokens: int, completion_tokens: int, model: str, success: bool = True):
        """Update usage statistics."""
        self.total_requests += 1
        
        if success:
            self.successful_requests += 1
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_tokens += prompt_tokens + completion_tokens
            
            cost = self.calculate_cost(prompt_tokens, completion_tokens, model)
            self.total_cost += cost
            
            # Warn at $10 increments
            if self.total_cost >= self.last_cost_warning + 10.0:
                self.last_cost_warning = int(self.total_cost // 10) * 10
                logger.warning(f"Total API cost has exceeded ${self.last_cost_warning:.2f}")
        else:
            self.failed_requests += 1
    
    def add_error(self, error_type: str, message: str, file_id: str = None):
        """Add error to tracking."""
        self.errors.append({
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': message,
            'file_id': file_id
        })


@dataclass
class TranslationProgress:
    """Track translation progress and completion status."""
    
    completed_files: List[str] = None
    failed_files: List[Dict] = None
    
    def __post_init__(self):
        if self.completed_files is None:
            self.completed_files = []
        if self.failed_files is None:
            self.failed_files = []
    
    def mark_completed(self, file_id: str):
        """Mark a file as successfully completed."""
        if file_id not in self.completed_files:
            self.completed_files.append(file_id)
    
    def mark_failed(self, file_id: str, reason: str):
        """Mark a file as failed with reason."""
        self.failed_files.append({
            'file_id': file_id,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })
    
    def is_completed(self, file_id: str) -> bool:
        """Check if file is already completed."""
        return file_id in self.completed_files
    
    def save(self, file_path: Path):
        """Save progress to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, file_path: Path) -> 'TranslationProgress':
        """Load progress from file."""
        if not file_path.exists():
            return cls()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**data)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Could not load progress from {file_path}, starting fresh")
            return cls()


class HebrewTranslator:
    """
    OpenAI-powered Hebrew translator with rate limiting, retry logic, and cost tracking.
    """
    
    def __init__(
        self, 
        api_key: str = None,
        model: str = "gpt-4.1-mini",  # Default to cost-effective model
        max_concurrent: int = 10,
        timeout: int = 60,
        progress_file: Path = None
    ):
        """
        Initialize Hebrew translator.
        
        Args:
            api_key: OpenAI API key (if None, loads from environment)
            model: OpenAI model to use
            max_concurrent: Maximum concurrent requests
            timeout: Request timeout in seconds
            progress_file: Path to save progress
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.model = model
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        
        # Initialize OpenAI client
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            timeout=self.timeout
        )
        
        # Initialize tracking
        self.usage_stats = APIUsageStats()
        self.progress_file = progress_file or Path("translation_progress.json")
        self.progress = TranslationProgress.load(self.progress_file)
        
        # Semaphore for rate limiting
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        logger.info(f"Hebrew translator initialized with model {model}, max_concurrent={max_concurrent}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError
        ))
    )
    async def _make_translation_request(self, text: str) -> Optional[str]:
        """Make a single translation request with retry logic."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a professional translator specializing in historical testimonies and interviews. 
Your task is to translate English text to Hebrew while preserving:
1. The exact meaning and emotional tone
2. Historical context and terminology
3. Speech patterns and authentic voice
4. Cultural nuances

Translate to Modern Hebrew script. Maintain the natural flow and authenticity of the original testimony.
Return ONLY the Hebrew translation, no explanations or additional text."""
                    },
                    {
                        "role": "user",
                        "content": f"Translate this text to Hebrew:\n\n{text}"
                    }
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            hebrew_text = response.choices[0].message.content.strip()
            
            # Update usage stats
            usage = response.usage
            self.usage_stats.update(
                usage.prompt_tokens,
                usage.completion_tokens, 
                self.model,
                success=True
            )
            
            return hebrew_text
            
        except Exception as e:
            error_type = type(e).__name__
            self.usage_stats.add_error(error_type, str(e))
            logger.error(f"Translation request failed: {error_type}: {e}")
            raise
    
    async def translate(self, text: str, file_id: str) -> Optional[str]:
        """
        Translate text to Hebrew with rate limiting and error handling.
        
        Args:
            text: English text to translate
            file_id: Unique identifier for tracking
            
        Returns:
            Hebrew translation or None if failed
        """
        # Skip if already completed
        if self.progress.is_completed(file_id):
            logger.info(f"Skipping {file_id} - already completed")
            return None
        
        if not text or not text.strip():
            logger.warning(f"Empty text for {file_id}")
            return None
        
        async with self.semaphore:
            try:
                hebrew = await self._make_translation_request(text)
                
                if hebrew:
                    self.progress.mark_completed(file_id)
                    logger.info(f"Successfully translated {file_id}")
                    
                    # Save progress periodically
                    if len(self.progress.completed_files) % 10 == 0:
                        self.save_progress()
                    
                    return hebrew
                else:
                    self.progress.mark_failed(file_id, "Empty translation returned")
                    return None
                    
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                self.progress.mark_failed(file_id, error_msg)
                self.usage_stats.update(0, 0, self.model, success=False)
                logger.error(f"Failed to translate {file_id}: {error_msg}")
                return None
    
    async def translate_batch(
        self, 
        texts: List[Tuple[str, str]], 
        progress_callback: Callable[[int, int], None] = None
    ) -> Dict[str, str]:
        """
        Translate multiple texts in parallel.
        
        Args:
            texts: List of (file_id, text) tuples
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping file_id to Hebrew translation
        """
        logger.info(f"Starting batch translation of {len(texts)} files")
        
        results = {}
        completed = 0
        
        async def translate_one(file_id: str, text: str):
            nonlocal completed
            hebrew = await self.translate(text, file_id)
            if hebrew:
                results[file_id] = hebrew
            
            completed += 1
            if progress_callback:
                progress_callback(completed, len(texts))
        
        # Process all translations concurrently
        tasks = [translate_one(file_id, text) for file_id, text in texts]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Batch translation completed: {len(results)}/{len(texts)} successful")
        return results
    
    def estimate_cost(self, texts: List[str]) -> Dict:
        """
        Estimate translation cost for a batch of texts.
        
        Args:
            texts: List of texts to estimate
            
        Returns:
            Dictionary with cost estimation details
        """
        total_chars = sum(len(text) for text in texts)
        
        # Rough estimation: 1 token ≈ 4 characters
        estimated_input_tokens = total_chars / 4
        estimated_output_tokens = estimated_input_tokens  # Assume 1:1 ratio for translation
        
        cost = self.usage_stats.calculate_cost(
            int(estimated_input_tokens),
            int(estimated_output_tokens), 
            self.model
        )
        
        return {
            'total_characters': total_chars,
            'estimated_input_tokens': int(estimated_input_tokens),
            'estimated_output_tokens': int(estimated_output_tokens),
            'estimated_total_cost': cost,
            'cost_per_file': cost / len(texts) if texts else 0,
            'model': self.model
        }
    
    async def test_connection(self) -> bool:
        """Test API connection with a small request."""
        try:
            await self._make_translation_request("Hello")
            logger.info("API connection test successful")
            return True
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False
    
    def save_progress(self):
        """Save current progress to file."""
        self.progress.save(self.progress_file)
    
    def get_usage_stats(self) -> APIUsageStats:
        """Get current usage statistics."""
        return self.usage_stats
    
    def save_usage_report(self, file_path: Path):
        """Save detailed usage report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'model_config': {
                'model': self.model,
                'max_concurrent': self.max_concurrent,
                'timeout': self.timeout
            },
            'usage_stats': asdict(self.usage_stats),
            'progress': {
                'completed_files': len(self.progress.completed_files),
                'failed_files': len(self.progress.failed_files),
                'completion_rate': len(self.progress.completed_files) / 
                                 (len(self.progress.completed_files) + len(self.progress.failed_files))
                                 if (len(self.progress.completed_files) + len(self.progress.failed_files)) > 0 else 0.0
            }
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Usage report saved to {file_path}")


# Convenience functions for backward compatibility
async def translate_to_hebrew(text: str, file_id: str = None, **kwargs) -> Optional[str]:
    """Convenience function for single translation."""
    translator = HebrewTranslator(**kwargs)
    return await translator.translate(text, file_id or f"temp_{int(time.time())}")


async def batch_translate_hebrew(texts: List[Tuple[str, str]], **kwargs) -> Dict[str, str]:
    """Convenience function for batch translation.""" 
    translator = HebrewTranslator(**kwargs)
    return await translator.translate_batch(texts)