# Phase 2, Task 4 Implementation Prompt for Claude

## Pre-Task Actions

Before starting Task 4, please update the Taskmaster status for Task 3:

```bash
# Update all subtask statuses
task-master set-status --id=3.1 --status=done
task-master set-status --id=3.2 --status=done
task-master set-status --id=3.3 --status=done
task-master set-status --id=3.4 --status=done

# Update main task status
task-master set-status --id=3 --status=done
```

## Phase 2 Overview: Hebrew Translation Fixes

Phase 1 is complete! The system is stabilized with accurate data. Now we begin fixing the 379 problematic Hebrew translations:
- 328 files with "[HEBREW TRANSLATION]" placeholders
- 51 missing Hebrew files

Phase 2 will implement a robust, cost-effective retranslation pipeline using OpenAI's API.

## Your Assignment: Task 4 - Setup OpenAI API Integration

### Context
We need to retranslate 379 Hebrew files using OpenAI's API. Based on average file sizes, this will cost approximately $200-300. Your task is to create a robust, production-ready API integration with proper error handling, rate limiting, and cost tracking.

### Task 4 Goal
Create a reliable OpenAI API integration that can handle batch translations with retry logic, rate limiting, and detailed cost tracking.

### Subtask Breakdown

#### Subtask 4.1: Configure OpenAI API Client
1. Install required packages:
   ```bash
   pip install openai==1.12.0 python-dotenv tenacity aiofiles
   ```
2. Create `.env` file if not exists with `OPENAI_API_KEY`
3. Set up async OpenAI client with proper configuration
4. Create basic connection test script

#### Subtask 4.2: Implement Rate Limiting and Retry Logic
1. Use `tenacity` library for sophisticated retry logic
2. Handle these specific OpenAI errors:
   - Rate limit errors (429)
   - Server errors (500, 502, 503)
   - Timeout errors
3. Implement exponential backoff
4. Add concurrent request limiting (max 10 concurrent)
5. Log all retry attempts

#### Subtask 4.3: Track API Usage and Costs
1. Create `APIUsageTracker` class to monitor:
   - Total tokens used (prompt + completion)
   - Cost calculation based on model pricing
   - Requests made
   - Errors encountered
2. Implement cost calculation for GPT-4 Turbo:
   - Input: $0.01 per 1K tokens
   - Output: $0.03 per 1K tokens
3. Create running cost logger
4. Save usage stats to JSON file

#### Subtask 4.4: Integrate with Translation Pipeline
1. Create `HebrewTranslator` class that:
   - Accepts English text
   - Returns Hebrew translation
   - Tracks usage/costs
   - Handles errors gracefully
2. Design for batch processing (379 files)
3. Include progress reporting
4. Implement checkpointing for resume capability

#### Subtask 4.5: Test with Sample Data and Error Scenarios
1. Create test suite with:
   - Small sample translation test
   - Rate limit simulation
   - Network error handling
   - Cost calculation verification
2. Test with actual Scribe transcription samples
3. Verify Hebrew output quality
4. Test resume after interruption

### Required Deliverables

1. **Main Module**: `openai_integration.py`
   ```python
   import os
   import asyncio
   import json
   from datetime import datetime
   from pathlib import Path
   from typing import Optional, List, Dict
   from dataclasses import dataclass, asdict
   import openai
   from tenacity import retry, stop_after_attempt, wait_exponential
   from dotenv import load_dotenv
   
   @dataclass
   class APIUsageStats:
       total_requests: int = 0
       successful_requests: int = 0
       failed_requests: int = 0
       total_prompt_tokens: int = 0
       total_completion_tokens: int = 0
       total_tokens: int = 0
       total_cost: float = 0.0
       errors: List[Dict] = None
       
   class HebrewTranslator:
       # Implementation here
   ```

2. **Test Suite**: `test_openai_integration.py`
   - Test API connection
   - Test translation quality
   - Test error handling
   - Test cost tracking
   - Test concurrency limits

3. **Configuration**: Update `.env` with OpenAI API key

4. **Sample Translation**: Translate a few sample files to verify quality

### Implementation Requirements

1. **API Configuration**:
   - Model: `gpt-4-turbo-preview` (or `gpt-4-0125-preview`)
   - Temperature: 0.3 (for consistency)
   - Max tokens: Adjust based on input length
   - System prompt: Professional translation focus

2. **Rate Limiting**:
   - Max 10 concurrent requests
   - Exponential backoff: 4s min, 60s max
   - Max 3 retry attempts per request
   - Track and log all retries

3. **Cost Management**:
   - Log cost after every request
   - Alert if total exceeds $10 increments
   - Save detailed usage report
   - Estimate total cost before starting

4. **Error Handling**:
   - Graceful handling of API errors
   - Clear error messages
   - Resume capability after failures
   - Save progress regularly

### System Prompt for Translation

```
You are a professional translator specializing in historical oral histories. 
Translate the following English transcription to Hebrew. 
Maintain the conversational tone and preserve names, dates, and places exactly as they appear.
Do not add explanations or notes - provide only the Hebrew translation.
```

### Testing Approach

1. **Unit Tests**:
   - Mock OpenAI responses
   - Test error scenarios
   - Verify cost calculations

2. **Integration Tests**:
   - Use real API with small samples
   - Verify Hebrew output
   - Test rate limiting

3. **Load Test**:
   - Simulate batch of 10 translations
   - Monitor rate limits
   - Track total cost

### Cost Estimation

Based on analysis:
- Average file: ~2000 words (~2500 tokens)
- 379 files total
- Estimated tokens: ~950,000 input + ~950,000 output
- Estimated cost: $9.50 + $28.50 = $38 (minimum)
- With retries/errors: Budget $50-60

### Success Criteria

1. Successfully connects to OpenAI API
2. Translates sample English text to Hebrew accurately
3. Handles rate limits without failing
4. Tracks costs within 5% accuracy
5. Can process multiple files concurrently
6. Resumes after interruption
7. All tests pass

### Important Notes

- Start with a small test to verify API key works
- Monitor costs carefully during testing
- Keep translation quality high - these are historical records
- Consider implementing a daily cost limit for safety
- Save all translations immediately after receiving them

### Example Usage

```python
# Initialize translator
translator = HebrewTranslator(api_key=os.getenv('OPENAI_API_KEY'))

# Translate single text
hebrew_text = await translator.translate(
    "This is a test translation.",
    file_id="test_001"
)

# Get usage stats
stats = translator.get_usage_stats()
print(f"Total cost so far: ${stats.total_cost:.2f}")

# Save progress
translator.save_progress("translation_progress.json")
```

### After Completion

Provide a comprehensive summary including:
1. API connection test results
2. Sample translation quality assessment
3. Cost tracking accuracy
4. Error handling verification
5. Performance metrics (requests/minute)
6. Total estimated cost for 379 files
7. Readiness for Task 5 (parallel pipeline)

Remember to update Taskmaster with progress on each subtask as you complete them. 