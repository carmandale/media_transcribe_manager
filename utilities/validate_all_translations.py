#!/usr/bin/env python3
"""
Comprehensive validation of all translations and database integrity.
This ensures we can trust the database and file system state.
"""

import os
import re
import json
import hashlib
from pathlib import Path
from collections import defaultdict
import logging

from scribe.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TranslationValidator:
    """Validates translations and database integrity."""
    
    def __init__(self):
        self.db = Database()
        self.issues = defaultdict(list)
        self.stats = defaultdict(int)
        
    def is_hebrew_text(self, text):
        """Check if text contains actual Hebrew characters."""
        # Hebrew Unicode range: \u0590-\u05FF
        hebrew_chars = len(re.findall(r'[\u0590-\u05FF]', text))
        total_chars = len(text)
        if total_chars == 0:
            return False
        hebrew_ratio = hebrew_chars / total_chars
        return hebrew_ratio > 0.3  # At least 30% Hebrew characters
    
    def is_german_text(self, text):
        """Check if text appears to be German."""
        german_indicators = ['der', 'die', 'das', 'und', 'ist', 'nicht', 'ich', 'sie', 'Sie']
        text_lower = text.lower()
        indicator_count = sum(1 for word in german_indicators if f' {word} ' in f' {text_lower} ')
        return indicator_count >= 3
    
    def has_placeholder(self, text):
        """Check if text contains translation placeholders."""
        placeholders = ['[HEBREW TRANSLATION]', '[GERMAN TRANSLATION]', '[ENGLISH TRANSLATION]']
        return any(placeholder in text for placeholder in placeholders)
    
    def validate_file(self, file_id, language):
        """Validate a single translation file."""
        file_path = Path(f'output/{file_id}/{file_id}.{language}.txt')
        
        # Check if file exists
        if not file_path.exists():
            self.issues[file_id].append(f"Missing {language} file")
            return False
            
        # Check file size
        file_size = file_path.stat().st_size
        if file_size == 0:
            self.issues[file_id].append(f"Empty {language} file")
            return False
            
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.issues[file_id].append(f"Error reading {language} file: {e}")
            return False
            
        # Check for placeholders
        if self.has_placeholder(content):
            self.issues[file_id].append(f"{language} file contains placeholder text")
            return False
            
        # Language-specific validation
        if language == 'he':
            if not self.is_hebrew_text(content):
                self.issues[file_id].append(f"{language} file does not contain Hebrew text")
                return False
        elif language == 'de':
            if content and not self.is_german_text(content[:1000]):  # Check first 1000 chars
                # Could be originally German, so just warn
                self.issues[file_id].append(f"WARNING: {language} file may not be German")
                
        return True
    
    def check_database_consistency(self, file_id):
        """Check if database status matches file system."""
        status = self.db.get_status(file_id)
        if not status:
            self.issues[file_id].append("No database record")
            return False
            
        issues = []
        
        # Check each translation status
        for lang in ['en', 'de', 'he']:
            db_status = status.get(f'translation_{lang}_status')
            file_exists = Path(f'output/{file_id}/{file_id}.{lang}.txt').exists()
            
            if db_status == 'completed' and not file_exists:
                issues.append(f"{lang} marked complete but file missing")
            elif db_status != 'completed' and file_exists:
                issues.append(f"{lang} file exists but not marked complete")
                
        if issues:
            self.issues[file_id].extend(issues)
            return False
            
        return True
    
    def validate_all(self):
        """Validate all files in the database."""
        logger.info("Starting comprehensive validation...")
        
        # Get all files from database
        all_files = self.db.execute_query("SELECT file_id FROM media_files ORDER BY file_id")
        total_files = len(all_files)
        
        logger.info(f"Validating {total_files} files...")
        
        for i, file_record in enumerate(all_files):
            file_id = file_record['file_id']
            
            if i % 100 == 0:
                logger.info(f"Progress: {i}/{total_files}")
            
            # Check database consistency
            db_ok = self.check_database_consistency(file_id)
            
            # Validate each translation
            status = self.db.get_status(file_id)
            if status:
                for lang in ['en', 'de', 'he']:
                    if status.get(f'translation_{lang}_status') == 'completed':
                        file_ok = self.validate_file(file_id, lang)
                        if file_ok:
                            self.stats[f'{lang}_valid'] += 1
                        else:
                            self.stats[f'{lang}_invalid'] += 1
                    else:
                        self.stats[f'{lang}_not_completed'] += 1
            
            if not self.issues[file_id]:
                self.stats['fully_valid'] += 1
        
        return self.generate_report(total_files)
    
    def generate_report(self, total_files):
        """Generate validation report."""
        report = []
        report.append("\n" + "="*60)
        report.append("TRANSLATION VALIDATION REPORT")
        report.append("="*60)
        
        report.append(f"\nTotal files: {total_files}")
        report.append(f"Fully valid files: {self.stats['fully_valid']}")
        report.append(f"Files with issues: {len(self.issues)}")
        
        report.append("\n--- Translation Status ---")
        for lang in ['en', 'de', 'he']:
            valid = self.stats.get(f'{lang}_valid', 0)
            invalid = self.stats.get(f'{lang}_invalid', 0)
            not_completed = self.stats.get(f'{lang}_not_completed', 0)
            total_expected = valid + invalid + not_completed
            
            report.append(f"\n{lang.upper()} translations:")
            report.append(f"  Valid: {valid}")
            report.append(f"  Invalid: {invalid}")
            report.append(f"  Not completed: {not_completed}")
            report.append(f"  Total: {total_expected}")
        
        # Sample issues
        if self.issues:
            report.append("\n--- Sample Issues (first 20) ---")
            issue_count = 0
            for file_id, file_issues in list(self.issues.items())[:20]:
                report.append(f"\n{file_id}:")
                for issue in file_issues:
                    report.append(f"  - {issue}")
                issue_count += 1
                
            if len(self.issues) > 20:
                report.append(f"\n... and {len(self.issues) - 20} more files with issues")
        
        report.append("\n" + "="*60)
        
        # Save detailed issues to file
        with open('validation_issues.json', 'w') as f:
            json.dump(dict(self.issues), f, indent=2)
        report.append("\nDetailed issues saved to: validation_issues.json")
        
        return '\n'.join(report)

def main():
    """Run validation."""
    validator = TranslationValidator()
    report = validator.validate_all()
    
    print(report)
    
    # Save report
    with open('validation_report.txt', 'w') as f:
        f.write(report)
    
    logger.info("Validation complete. Report saved to validation_report.txt")

if __name__ == "__main__":
    main()