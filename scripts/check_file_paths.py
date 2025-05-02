import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import argparse
from db_manager import DatabaseManager
from file_manager import FileManager

def main():
    parser = argparse.ArgumentParser(description="Check FileManager path resolution.")
    parser.add_argument('--file-id', required=True, help='File ID to test')
    parser.add_argument('--languages', default='en,de,he', help='Comma-separated list of languages')
    args = parser.parse_args()

    # Load config as in process_translations.py
    config = {
        'output_dir': './output',
        'deepl': {
            'api_key': os.getenv('DEEPL_API_KEY'),
            'formality': 'default'
        },
        'google_translate': {
            'credentials_file': os.getenv('GOOGLE_TRANSLATE_CREDENTIALS')
        },
        'microsoft_translator': {
            'api_key': os.getenv('MS_TRANSLATOR_KEY'),
            'location': os.getenv('MS_TRANSLATOR_LOCATION', 'global')
        }
    }

    db = DatabaseManager(db_file='./media_tracking.db')
    fm = FileManager(db, config)

    print(f"File ID: {args.file_id}\n")

    # Transcript path
    try:
        tpath = fm.get_transcript_path(args.file_id)
        print(f"Transcript path: {tpath} | Exists: {os.path.exists(tpath)}")
    except Exception as e:
        print(f"Transcript path error: {e}")

    # Translation paths
    for lang in args.languages.split(','):
        try:
            xpath = fm.get_translation_path(args.file_id, lang)
            print(f"Translation path ({lang}): {xpath} | Dir exists: {os.path.isdir(os.path.dirname(xpath))}")
        except Exception as e:
            print(f"Translation path ({lang}) error: {e}")

    # Subtitle path
    try:
        spath = fm.get_subtitle_path(args.file_id, 'orig')
        print(f"Subtitle path: {spath} | Exists: {os.path.exists(spath)}")
    except Exception as e:
        print(f"Subtitle path error: {e}")

    # Audio path
    try:
        apath = fm.get_audio_path(args.file_id)
        print(f"Audio path: {apath} | Exists: {os.path.exists(apath)}")
    except Exception as e:
        print(f"Audio path error: {e}")

    # Video path (if any)
    try:
        vpath = fm.get_video_path(args.file_id)
        print(f"Video path: {vpath} | Exists: {os.path.exists(vpath) if vpath else False}")
    except Exception as e:
        print(f"Video path error: {e}")

if __name__ == '__main__':
    main()
