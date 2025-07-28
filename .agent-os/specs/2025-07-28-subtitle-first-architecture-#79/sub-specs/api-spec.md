# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-07-28-subtitle-first-architecture-#79/spec.md

> Created: 2025-07-28
> Version: 1.0.0

## API Integration Changes

The subtitle-first architecture requires modifications to how we interact with external transcription and translation APIs to preserve timing accuracy throughout the processing pipeline.

## ElevenLabs Scribe API Integration

### Current Implementation Issues

**Problem:** Current code ignores word-level timestamp data from ElevenLabs Scribe API
**Impact:** All subsequent processing lacks precise timing information

### Enhanced API Response Parsing

**Current Code Pattern:**
```python
# Current: Only extracts text
response = elevenlabs_client.transcribe(audio_file)
transcript_text = response['text']  # Loses all timing data
```

**New Code Pattern:**
```python
# New: Extract word-level timestamps
response = elevenlabs_client.transcribe(audio_file)
word_segments = response['segments']  # Contains timing for each word
transcript_text = response['text']    # Still available for backup
```

### Expected ElevenLabs Response Format

```json
{
  "text": "This is the complete transcript text",
  "segments": [
    {
      "start": 0.0,
      "end": 0.5,
      "text": "This",
      "confidence": 0.95
    },
    {
      "start": 0.5,
      "end": 0.8,
      "text": "is",  
      "confidence": 0.92
    },
    {
      "start": 0.8,
      "end": 1.1,
      "text": "the",
      "confidence": 0.89
    }
  ],
  "language": "en",
  "confidence": 0.92
}
```

### Segment Creation Logic

**Purpose:** Convert word-level timestamps into subtitle-appropriate segments (2-4 seconds each)

```python
def create_subtitle_segments(word_segments, max_duration=4.0, max_words=10):
    """
    Group words into subtitle segments based on natural boundaries
    
    Args:
        word_segments: List of word-level timestamps from ElevenLabs
        max_duration: Maximum segment duration in seconds
        max_words: Maximum words per segment
    
    Returns:
        List of subtitle segments with start/end times and text
    """
    segments = []
    current_segment = {
        'start_time': None,
        'end_time': None, 
        'words': [],
        'text': ''
    }
    
    for word in word_segments:
        # Start new segment if current is empty
        if current_segment['start_time'] is None:
            current_segment['start_time'] = word['start']
        
        # Add word to current segment
        current_segment['words'].append(word)
        current_segment['end_time'] = word['end']
        current_segment['text'] = ' '.join([w['text'] for w in current_segment['words']])
        
        # Check if segment should end
        segment_duration = current_segment['end_time'] - current_segment['start_time']
        should_end_segment = (
            segment_duration >= max_duration or
            len(current_segment['words']) >= max_words or
            word['text'].endswith('.') or  # Natural sentence boundary
            word['text'].endswith('?') or
            word['text'].endswith('!')
        )
        
        if should_end_segment:
            segments.append(current_segment.copy())
            current_segment = {
                'start_time': None,
                'end_time': None,
                'words': [],
                'text': ''
            }
    
    return segments
```

## Translation API Modifications

### DeepL API - Segment-Based Translation

**Current Approach:** Translate entire transcript as single request
**New Approach:** Translate individual segments with context

**Endpoint Usage:**
```
POST https://api-free.deepl.com/v2/translate
```

**Modified Request Pattern:**
```python
def translate_segments_deepl(segments, source_lang, target_lang):
    """
    Translate subtitle segments while preserving timing
    
    Args:
        segments: List of subtitle segments with timing
        source_lang: Source language code  
        target_lang: Target language code
        
    Returns:
        List of segments with translated text added
    """
    translated_segments = []
    
    for segment in segments:
        # Provide context from adjacent segments for better translation
        context_before = get_context_before(segment, segments)
        context_after = get_context_after(segment, segments)
        
        request_payload = {
            'text': [segment['text']],
            'source_lang': source_lang,
            'target_lang': target_lang,
            'context': f"{context_before} {segment['text']} {context_after}",
            'preserve_formatting': True,
            'formality': 'default'
        }
        
        response = deepl_client.translate(**request_payload)
        
        segment_copy = segment.copy()
        segment_copy['translated_text'] = response.translations[0].text
        segment_copy['translation_confidence'] = getattr(response.translations[0], 'confidence', None)
        
        translated_segments.append(segment_copy)
    
    return translated_segments
```

### OpenAI API - Hebrew Translation with Context

**Purpose:** Handle Hebrew translation with cultural/historical context preservation

**Modified Request Pattern:**
```python
def translate_segments_openai_hebrew(segments, context_info):
    """
    Translate segments to Hebrew with historical context awareness
    
    Args:
        segments: List of subtitle segments
        context_info: Interview metadata for context
        
    Returns:
        List of segments with Hebrew translations
    """
    system_prompt = f"""
    You are translating historical testimony segments to Hebrew. 
    
    Context: {context_info['description']}
    Time Period: {context_info.get('time_period', 'Unknown')}
    
    Requirements:
    - Preserve historical accuracy of names and places
    - Maintain formal tone appropriate for historical testimony
    - Keep segment length similar to original
    - Preserve timing by not adding explanatory text
    """
    
    translated_segments = []
    
    for segment in segments:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Translate this segment: '{segment['text']}'"}
        ]
        
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.1,  # Low temperature for consistency
            max_tokens=len(segment['text']) * 2  # Reasonable limit
        )
        
        segment_copy = segment.copy()
        segment_copy['hebrew_text'] = response.choices[0].message.content
        translated_segments.append(segment_copy)
    
    return translated_segments
```

## Quality Validation Endpoints

### Synchronization Validation API

**Purpose:** Validate that generated subtitles align correctly with video timing

```python
def validate_subtitle_synchronization(interview_id, segments):
    """
    Validate subtitle-video synchronization quality
    
    Args:
        interview_id: Database ID of interview
        segments: List of subtitle segments to validate
        
    Returns:
        Validation results with quality metrics
    """
    validation_results = {
        'interview_id': interview_id,
        'total_segments': len(segments),
        'timing_issues': [],
        'quality_score': 0.0,
        'recommendations': []
    }
    
    # Check for timing gaps
    for i in range(len(segments) - 1):
        current_end = segments[i]['end_time']
        next_start = segments[i + 1]['start_time']
        gap = next_start - current_end
        
        if gap > 1.0:  # Gap longer than 1 second
            validation_results['timing_issues'].append({
                'type': 'large_gap',
                'segment_index': i,
                'gap_duration': gap,
                'severity': 'warning' if gap < 3.0 else 'error'
            })
    
    # Check segment duration reasonableness
    for i, segment in enumerate(segments):
        duration = segment['end_time'] - segment['start_time']
        if duration < 0.5:
            validation_results['timing_issues'].append({
                'type': 'too_short',
                'segment_index': i,
                'duration': duration,
                'severity': 'warning'
            })
        elif duration > 10.0:
            validation_results['timing_issues'].append({
                'type': 'too_long',
                'segment_index': i, 
                'duration': duration,
                'severity': 'error'
            })
    
    # Calculate overall quality score
    total_issues = len(validation_results['timing_issues'])
    error_count = len([issue for issue in validation_results['timing_issues'] if issue['severity'] == 'error'])
    
    if error_count > 0:
        validation_results['quality_score'] = max(0.0, 0.5 - (error_count * 0.1))
    else:
        validation_results['quality_score'] = max(0.7, 1.0 - (total_issues * 0.05))
    
    return validation_results
```

## Error Handling Strategies

### API Failure Recovery

**ElevenLabs Timeout/Failure:**
```python
def transcribe_with_fallback(audio_file, max_retries=3):
    """Transcribe with automatic retry and fallback"""
    for attempt in range(max_retries):
        try:
            result = elevenlabs_client.transcribe(audio_file)
            if 'segments' in result and len(result['segments']) > 0:
                return result
        except Exception as e:
            if attempt == max_retries - 1:
                # Final fallback: create basic segments from text-only response
                return create_fallback_segments(audio_file)
            time.sleep(2 ** attempt)  # Exponential backoff
```

**Translation Service Degradation:**
```python  
def translate_with_quality_check(segments, source_lang, target_lang):
    """Translate with quality validation"""
    result = translate_segments_deepl(segments, source_lang, target_lang)
    
    # Validate translation quality
    quality_score = assess_translation_quality(segments, result)
    
    if quality_score < 0.7:
        # Retry with different service or parameters
        logging.warning(f"Translation quality low ({quality_score}), retrying...")
        return translate_segments_openai(segments, source_lang, target_lang)
    
    return result
```

## Rate Limiting and Optimization

### API Call Optimization

**Batch Processing Strategy:**
- ElevenLabs: Process interviews sequentially to respect rate limits
- DeepL: Batch multiple segments per request (up to API limits)
- OpenAI: Use segment context to reduce API calls

**Cost Optimization:**
- Cache translation results at segment level
- Reuse translations for identical text segments across interviews
- Implement progressive quality checks to avoid unnecessary retries