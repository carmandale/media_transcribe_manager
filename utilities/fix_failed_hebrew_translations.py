#!/usr/bin/env python3
"""
Fix failed Hebrew translations in the Scribe system.

This script identifies and fixes Hebrew translations that failed, particularly those
that attempted to use DeepL (which doesn't support Hebrew) instead of the proper
Microsoft/OpenAI routing.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
import sys

def get_failed_hebrew_translations(db_path):
    """Get all failed Hebrew translations from the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.file_id, m.original_path, p.last_updated, 
               e.error_message, e.error_details
        FROM processing_status p
        JOIN media_files m ON p.file_id = m.file_id
        LEFT JOIN (
            SELECT file_id, error_message, error_details,
                   ROW_NUMBER() OVER (PARTITION BY file_id ORDER BY timestamp DESC) as rn
            FROM errors
            WHERE process_stage LIKE '%he%' OR process_stage LIKE '%hebrew%' OR process_stage = 'translation'
        ) e ON p.file_id = e.file_id AND e.rn = 1
        WHERE p.translation_he_status = 'failed'
        ORDER BY p.last_updated DESC
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def categorize_failures(failed_translations):
    """Categorize failures by type."""
    deepl_errors = []
    retry_errors = []
    unknown_errors = []
    
    for trans in failed_translations:
        if trans['error_details'] and 'deepl' in trans['error_details'].lower():
            deepl_errors.append(trans)
        elif trans['error_message'] and 'retry' in trans['error_message'].lower():
            retry_errors.append(trans)
        else:
            unknown_errors.append(trans)
    
    return {
        'deepl_errors': deepl_errors,
        'retry_errors': retry_errors,
        'unknown_errors': unknown_errors
    }

def reset_failed_translations(db_path, file_ids, dry_run=True):
    """Reset failed translations to pending status."""
    if dry_run:
        print(f"\n[DRY RUN] Would reset {len(file_ids)} translations to pending status")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Reset translation status
        cursor.execute('''
            UPDATE processing_status
            SET translation_he_status = 'pending',
                last_updated = datetime('now')
            WHERE file_id IN ({})
        '''.format(','.join('?' * len(file_ids))), file_ids)
        
        # Clear related errors
        cursor.execute('''
            DELETE FROM errors
            WHERE file_id IN ({})
            AND (process_stage LIKE '%he%' OR process_stage LIKE '%hebrew%' OR process_stage = 'translation')
        '''.format(','.join('?' * len(file_ids))), file_ids)
        
        conn.commit()
        print(f"\n✓ Reset {cursor.rowcount} translations to pending status")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error resetting translations: {e}")
        raise
    finally:
        conn.close()

def main():
    """Main function."""
    db_path = 'media_tracking.db'
    
    if not Path(db_path).exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    # Get failed translations
    print("Analyzing failed Hebrew translations...")
    failed_translations = get_failed_hebrew_translations(db_path)
    
    if not failed_translations:
        print("No failed Hebrew translations found!")
        return
    
    # Categorize failures
    categories = categorize_failures(failed_translations)
    
    # Print summary
    print(f"\nFound {len(failed_translations)} failed Hebrew translations:")
    print(f"  - DeepL routing errors: {len(categories['deepl_errors'])}")
    print(f"  - Retry errors: {len(categories['retry_errors'])}")
    print(f"  - Unknown errors: {len(categories['unknown_errors'])}")
    
    # Show DeepL errors (these are the most important to fix)
    if categories['deepl_errors']:
        print("\n" + "="*80)
        print("DEEPL ROUTING ERRORS (need immediate fix):")
        print("="*80)
        for i, trans in enumerate(categories['deepl_errors'], 1):
            print(f"{i}. {trans['file_id']}")
            print(f"   Path: {trans['original_path'][:100]}...")
            print(f"   Last updated: {trans['last_updated']}")
    
    # Show retry errors
    if categories['retry_errors']:
        print("\n" + "="*80)
        print("RETRY ERRORS (may have persistent issues):")
        print("="*80)
        for i, trans in enumerate(categories['retry_errors'][:5], 1):
            print(f"{i}. {trans['file_id']}")
            print(f"   Error: {trans['error_message']}")
            if i == 5 and len(categories['retry_errors']) > 5:
                print(f"   ... and {len(categories['retry_errors']) - 5} more")
    
    # Prompt for action
    print("\n" + "="*80)
    print("RECOMMENDED ACTIONS:")
    print("="*80)
    print("1. Reset ALL failed translations (recommended)")
    print("2. Reset only DeepL routing errors")
    print("3. Export detailed report")
    print("4. Exit without changes")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == '1':
        file_ids = [t['file_id'] for t in failed_translations]
        print(f"\nPreparing to reset {len(file_ids)} failed translations...")
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        if confirm == 'yes':
            reset_failed_translations(db_path, file_ids, dry_run=False)
            print("\n✓ Translations reset successfully!")
            print("\nNext steps:")
            print("1. Run: uv run python scribe_cli.py translate he --workers 8")
            print("2. Monitor progress with: uv run python scribe_cli.py status --detailed")
        else:
            print("Operation cancelled.")
    
    elif choice == '2':
        file_ids = [t['file_id'] for t in categories['deepl_errors']]
        if file_ids:
            print(f"\nPreparing to reset {len(file_ids)} DeepL routing errors...")
            confirm = input("Are you sure? (yes/no): ").strip().lower()
            if confirm == 'yes':
                reset_failed_translations(db_path, file_ids, dry_run=False)
                print("\n✓ DeepL errors reset successfully!")
            else:
                print("Operation cancelled.")
        else:
            print("No DeepL errors to reset.")
    
    elif choice == '3':
        report_path = f"hebrew_failed_detailed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump({
                'summary': {
                    'total_failed': len(failed_translations),
                    'deepl_errors': len(categories['deepl_errors']),
                    'retry_errors': len(categories['retry_errors']),
                    'unknown_errors': len(categories['unknown_errors']),
                    'generated': datetime.now().isoformat()
                },
                'failures': categories
            }, f, indent=2)
        print(f"\n✓ Detailed report saved to: {report_path}")
    
    elif choice == '4':
        print("Exiting without changes.")
    
    else:
        print("Invalid choice. Exiting.")

if __name__ == '__main__':
    main()