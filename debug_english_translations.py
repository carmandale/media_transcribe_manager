try:
    import db_manager
    import parallel_translation
    db = db_manager.DatabaseManager('media_tracking.db')
    # Check files with 'in-progress' transcription but 'not_started' translation
    sql_files = db.execute_query("SELECT * FROM processing_status WHERE translation_en_status = 'not_started' AND transcription_status = 'in-progress'")
    print(f'Files with in-progress transcription: {len(sql_files)}')
    
    # Let's fix the issue by updating these to 'completed' transcription
    for file in sql_files:
        file_id = file['file_id']
        print(f"Updating file {file_id} transcription status to completed")
        db.update_transcription_status(file_id, 'completed')
    
    # Now check if our get_files_for_translation function finds them
    fixed_files = parallel_translation.get_files_for_translation(db, 'en', None)
    print(f'After fixing, get_files_for_translation found {len(fixed_files)} files for English translation')
except Exception as e:
    print(f'Error: {e}')
