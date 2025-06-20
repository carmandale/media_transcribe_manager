# Scribe System Validation & Trust Plan

## Current State (June 20, 2025)
- 728 total files in system
- English: 100% complete (728 valid)
- German: 100% complete (728 valid)  
- Hebrew: ~48% actually complete (349 valid, 328 with placeholders, 51 missing)
- Database reports 100% but cannot be trusted

## Immediate Actions Required

### 1. Fix Existing Hebrew Translations (High Priority)
- [ ] Complete translation of 328 files with [HEBREW TRANSLATION] placeholders
- [ ] Create 51 missing Hebrew translation files
- [ ] Estimated cost: ~$200-300 in OpenAI API fees
- [ ] Estimated time: 4-6 hours with parallel processing

### 2. Implement Content Validation (Critical)
```python
# Add to scribe/database.py
def validate_translation_content(self, file_id, language):
    """Validate that translation file contains correct language."""
    # Check file exists
    # Check no placeholders
    # Check language detection (Hebrew chars, German indicators, etc.)
    # Return validation status and issues
```

### 3. Add Database Integrity Checks
```python
# New method for Database class
def validate_and_fix_status(self, file_id):
    """Validate file system matches database and fix discrepancies."""
    # Check all translation files exist
    # Validate content of each file
    # Update database to match reality
    # Log all changes made
```

### 4. Mandatory Evaluation Before Completion
- Modify translation pipeline to require evaluation before marking complete
- No translation should be marked "completed" without:
  1. File exists check
  2. Content validation (correct language, no placeholders)
  3. Quality evaluation score >= 7.0

### 5. Create Validation Test Suite
```python
# tests/test_translation_integrity.py
def test_no_placeholders_in_completed_translations():
    """Ensure no completed translations contain placeholders."""
    
def test_hebrew_files_contain_hebrew():
    """Ensure Hebrew files contain actual Hebrew text."""
    
def test_database_matches_filesystem():
    """Ensure database status matches actual files."""
```

### 6. Add Monitoring & Alerts
- Daily validation report
- Alert if any completed translation has issues
- Track evaluation coverage (must be 100%)

## Implementation Order

1. **Today**: 
   - Stop current processing
   - Run full system audit
   - Fix database to reflect reality
   
2. **Next**:
   - Implement content validation
   - Add to translation pipeline
   - Reprocess all Hebrew translations with validation
   
3. **Then**:
   - Add test suite
   - Set up monitoring
   - Document validation process

## Success Criteria
- 100% of "completed" translations have valid files
- 100% of Hebrew files contain Hebrew text (no placeholders)
- 100% of translations have quality evaluation
- Database can be trusted as single source of truth
- No translation can be marked complete without validation

## Cost Estimate
- Hebrew retranslation: $200-300
- Development time: 8-10 hours
- Total API costs for full validation: ~$50

## Questions for User
1. Should we proceed with fixing the 379 problematic Hebrew translations?
2. Do you want to review Devin's database changes before implementing?
3. Should we add similar validation for transcriptions?
4. What minimum quality score should block completion? (suggest 7.0)