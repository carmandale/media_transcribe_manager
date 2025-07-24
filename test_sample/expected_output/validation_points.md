# Validation Points for Subtitle Fix

## Critical Checks

### 1. Timestamp 00:39:42.030 (Line ~3663)
**Current (WRONG):**
```
00:39:42.030 --> 00:39:45.110
much Jews. We know that one
```

**Expected (CORRECT):**
```
00:39:42.030 --> 00:39:45.110
viele Juden. Wir wissen das eine
```
✓ English phrase translated to German

### 2. German Preservation Check
Look for any German segment (e.g., "In die Wehrmacht gekommen?")
- Should remain EXACTLY the same in German output
- Should NOT be retranslated

### 3. Segment Count
- Input: 1835 segments
- Output: 1835 segments (MUST match exactly)
- No segments merged or split

### 4. Timing Preservation
Every timestamp must remain identical:
- Start times unchanged
- End times unchanged
- Duration unchanged

## Language Detection Validation

Run quick check on these phrases:
1. "In die Wehrmacht gekommen?" → Should detect as German (de)
2. "How did you feel about Jews?" → Should detect as English (en)
3. "Wir wussten nicht viel" → Should detect as German (de)
4. "We didn't know much" → Should detect as English (en)

## Performance Metrics

### API Calls (with batch processing)
- Language detection: ~37 calls (50 segments per batch)
- Translation: ~8-10 calls (unique English phrases)
- Total: < 50 API calls (vs 1835 without batching)

### Processing Time
- Should complete in < 2 minutes
- No timeouts
- Smooth progress logging

## File Validation

### German Output (de.srt/de.vtt)
```bash
# Check for English phrases that should be gone
grep -i "much Jews" 25af0f9c-8f96-44c9-be5e-e92cb462a41f.de.srt
# Should return NOTHING

# Check German content preserved
grep -i "Wehrmacht" 25af0f9c-8f96-44c9-be5e-e92cb462a41f.de.srt
# Should find German phrases unchanged
```

### Timing Check
```bash
# Count timing lines in original vs translated
grep -c " --> " 25af0f9c-8f96-44c9-be5e-e92cb462a41f.orig.srt
grep -c " --> " 25af0f9c-8f96-44c9-be5e-e92cb462a41f.de.srt
# Both should return 1835
```

## Visual Inspection in Viewer

1. Play video at 39:42
2. German subtitles should show German text
3. Switch to English subtitles
4. English subtitles should show English text
5. Timing should be perfect in all languages